from __future__ import annotations

import collections
import json
import math
import re
from functools import lru_cache
from pathlib import Path

from app.core.config import settings
from app.models.rag import CodeChunk
from app.services.vector_store import LocalChromaStore


def tokenize_code(text: str) -> list[str]:
    """Tokenize source code and identifiers into lowercased whole and sub-tokens."""
    raw_tokens = re.findall(r"[A-Za-z0-9_]+", text)
    tokens: list[str] = []
    for token in raw_tokens:
        lower = token.lower()
        tokens.append(lower)

        # Split snake_case identifiers
        if "_" in token:
            for part in token.split("_"):
                if part and part.lower() != lower:
                    tokens.append(part.lower())

        # Split camelCase / PascalCase identifiers
        camel_parts = re.findall(r"[A-Z]?[a-z0-9]+|[A-Z]+(?=[A-Z][a-z]|\b)", token)
        if len(camel_parts) > 1:
            for part in camel_parts:
                if part and part.lower() != lower:
                    tokens.append(part.lower())

    return tokens


def make_lexical_document(chunk: CodeChunk) -> str:
    """Build a search-optimized text representation of a CodeChunk."""
    symbol_header = f"{chunk.symbol} {chunk.parent_symbol} {Path(chunk.file_path).stem}".strip()
    return (
        f"{symbol_header}\n"
        f"File: {chunk.file_path}\n"
        f"Symbol: {chunk.symbol}\n"
        f"Parent: {chunk.parent_symbol}\n"
        f"Type: {chunk.chunk_type}\n"
        f"{chunk.source_code}"
    )


class LocalBM25Store:
    def __init__(self, data_dir: str | Path | None = None, k1: float = 1.5, b: float = 0.75) -> None:
        self.data_dir = Path(data_dir or settings.bm25_data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.k1 = k1
        self.b = b
        self._memory_cache: dict[str, dict[str, object]] = {}

    def _file_path(self, repository_id: str) -> Path:
        return self.data_dir / f"bm25_{repository_id[:32]}.json"

    def replace_repository_chunks(self, repository_id: str, chunks: list[CodeChunk]) -> int:
        if not chunks:
            file_path = self._file_path(repository_id)
            if file_path.exists():
                file_path.unlink()
            self._memory_cache.pop(repository_id, None)
            return 0

        doc_lengths: list[int] = []
        documents_data: list[dict[str, object]] = []
        inverted_index: dict[str, list[list[int]]] = collections.defaultdict(list)

        for doc_idx, chunk in enumerate(chunks):
            doc_text = make_lexical_document(chunk)
            tokens = tokenize_code(doc_text)
            doc_len = len(tokens)
            doc_lengths.append(doc_len)

            tf_counter = collections.Counter(tokens)
            for token, tf in tf_counter.items():
                inverted_index[token].append([doc_idx, tf])

            chunk_id = LocalChromaStore.chunk_id(chunk)
            metadata = LocalChromaStore.metadata(chunk)
            documents_data.append({
                "chunk_id": chunk_id,
                "source_code": chunk.source_code,
                "metadata": metadata,
            })

        avgdl = sum(doc_lengths) / len(doc_lengths) if doc_lengths else 0.0

        index_payload = {
            "repository_id": repository_id,
            "doc_count": len(chunks),
            "avgdl": avgdl,
            "doc_lengths": doc_lengths,
            "inverted_index": dict(inverted_index),
            "documents": documents_data,
        }

        # Write to disk atomically
        file_path = self._file_path(repository_id)
        temp_path = file_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(index_payload, ensure_ascii=False), encoding="utf-8")
        temp_path.replace(file_path)

        self._memory_cache[repository_id] = index_payload
        return len(chunks)

    def _load_index(self, repository_id: str) -> dict[str, object] | None:
        if repository_id in self._memory_cache:
            return self._memory_cache[repository_id]

        file_path = self._file_path(repository_id)
        if not file_path.exists():
            return None

        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
            self._memory_cache[repository_id] = payload
            return payload
        except (json.JSONDecodeError, OSError):
            return None

    def search(self, repository_id: str, query: str, top_k: int) -> list[dict[str, object]]:
        index_data = self._load_index(repository_id)
        if not index_data:
            return []

        doc_count = int(index_data["doc_count"])
        if doc_count == 0:
            return []

        avgdl = float(index_data["avgdl"])
        doc_lengths: list[int] = index_data["doc_lengths"]
        inverted_index: dict[str, list[list[int]]] = index_data["inverted_index"]
        documents: list[dict[str, object]] = index_data["documents"]

        query_tokens = tokenize_code(query)
        if not query_tokens:
            return []

        scores: dict[int, float] = collections.defaultdict(float)
        query_token_counts = collections.Counter(query_tokens)

        for token in query_token_counts:
            postings = inverted_index.get(token)
            if not postings:
                continue

            nq = len(postings)
            idf = math.log((doc_count - nq + 0.5) / (nq + 0.5) + 1.0)
            if idf <= 0:
                idf = 0.001

            for doc_idx, tf in postings:
                dl = doc_lengths[doc_idx]
                denom = tf + self.k1 * (1.0 - self.b + self.b * (dl / avgdl if avgdl > 0 else 1.0))
                term_score = idf * ((tf * (self.k1 + 1.0)) / denom)
                scores[doc_idx] += term_score

        if not scores:
            return []

        sorted_doc_indices = sorted(scores.keys(), key=lambda idx: scores[idx], reverse=True)[:top_k]

        results: list[dict[str, object]] = []
        for idx in sorted_doc_indices:
            doc = documents[idx]
            results.append({
                "source_code": doc["source_code"],
                "metadata": dict(doc["metadata"]),
                "score": scores[idx],
                "chunk_id": doc["chunk_id"],
            })

        return results

    def count(self, repository_id: str) -> int:
        index_data = self._load_index(repository_id)
        if not index_data:
            return 0
        return int(index_data.get("doc_count", 0))

    def delete_repository(self, repository_id: str) -> None:
        self._memory_cache.pop(repository_id, None)
        file_path = self._file_path(repository_id)
        if file_path.exists():
            file_path.unlink()


@lru_cache(maxsize=4)
def get_local_bm25_store(data_dir: str | Path | None = None) -> LocalBM25Store:
    return LocalBM25Store(data_dir)
