from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings
from app.models.rag import CodeChunk


class Embedder(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


def repository_identity(repository_path: str | Path) -> tuple[str, str]:
    root = Path(repository_path).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Repository path must point to a directory.")
    canonical = str(root).casefold() if root.drive else str(root)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest(), str(root)


class LocalChromaStore:
    def __init__(self, data_dir: str | Path | None = None) -> None:
        path = Path(data_dir or settings.chroma_data_dir)
        path.mkdir(parents=True, exist_ok=True)
        self.data_dir = path
        self._client = chromadb.PersistentClient(
            path=str(path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )

    @staticmethod
    def collection_name(repository_id: str) -> str:
        return f"repo_{repository_id[:32]}"

    def _collection(self, repository_id: str):
        return self._client.get_or_create_collection(
            name=self.collection_name(repository_id),
            metadata={"repository_id": repository_id},
        )

    def replace_repository_chunks(self, repository_id: str, chunks: list[CodeChunk],
                                  embeddings: list[list[float]]) -> int:
        if len(chunks) != len(embeddings):
            raise ValueError("Each code chunk must have exactly one embedding.")
        collection = self._collection(repository_id)
        ids = [self.chunk_id(chunk) for chunk in chunks]
        if chunks:
            collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=[chunk.source_code for chunk in chunks],
                metadatas=[self.metadata(chunk) for chunk in chunks],
            )
        existing = collection.get(include=[]).get("ids", [])
        stale = list(set(existing) - set(ids))
        if stale:
            collection.delete(ids=stale)
        return collection.count()

    def search(self, repository_id: str, embedding: list[float], top_k: int) -> list[dict[str, object]]:
        try:
            collection = self._client.get_collection(name=self.collection_name(repository_id))
        except Exception as error:
            if "does not exist" in str(error).lower():
                return []
            raise
        count = collection.count()
        if count == 0:
            return []
        result = collection.query(
            query_embeddings=[embedding],
            n_results=min(top_k, count),
            include=["documents", "metadatas", "distances"],
        )
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        return [
            {"source_code": document, "metadata": metadata, "distance": distance}
            for document, metadata, distance in zip(documents, metadatas, distances)
        ]

    def count(self, repository_id: str) -> int:
        try:
            return self._client.get_collection(name=self.collection_name(repository_id)).count()
        except Exception as error:
            if "does not exist" in str(error).lower():
                return 0
            raise

    @staticmethod
    def chunk_id(chunk: CodeChunk) -> str:
        key = "\0".join((chunk.repository_id, chunk.file_path, chunk.chunk_type, chunk.symbol,
                          chunk.parent_symbol, str(chunk.start_line), str(chunk.end_line), chunk.source_code))
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    @staticmethod
    def metadata(chunk: CodeChunk) -> dict[str, str | int]:
        return {
            "repository_id": chunk.repository_id,
            "repository_name": chunk.repository_name,
            "repository_path": chunk.repository_path,
            "file_path": chunk.file_path,
            "symbol": chunk.symbol,
            "parent_symbol": chunk.parent_symbol,
            "chunk_type": chunk.chunk_type,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
        }


@lru_cache(maxsize=4)
def get_local_chroma_store(data_dir: str | None = None) -> LocalChromaStore:
    return LocalChromaStore(data_dir)
