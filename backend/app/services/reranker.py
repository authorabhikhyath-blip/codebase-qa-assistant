from __future__ import annotations

import re
from pathlib import Path
from typing import Any


class LocalReranker:
    """
    Local cross-scoring reranker for code RAG candidates.
    Evaluates query-candidate alignment across symbol naming, token density, and semantic fusion rank.
    """

    def __init__(self, identifier_weight: float = 0.4, coverage_weight: float = 0.3, rrf_weight: float = 0.3) -> None:
        self.identifier_weight = identifier_weight
        self.coverage_weight = coverage_weight
        self.rrf_weight = rrf_weight

    def _extract_query_terms(self, query: str) -> set[str]:
        raw = re.findall(r"[A-Za-z0-9_]+", query)
        terms: set[str] = set()
        for token in raw:
            terms.add(token.lower())
            if "_" in token:
                for part in token.split("_"):
                    if part:
                        terms.add(part.lower())
            camel = re.findall(r"[A-Z]?[a-z0-9]+|[A-Z]+(?=[A-Z][a-z]|\b)", token)
            if len(camel) > 1:
                for part in camel:
                    terms.add(part.lower())
        return terms

    def score_candidate(self, candidate: dict[str, Any], query: str, query_terms: set[str], max_rrf: float) -> float:
        metadata = candidate.get("metadata", {})
        symbol = str(metadata.get("symbol", "")).lower()
        parent_symbol = str(metadata.get("parent_symbol", "")).lower()
        file_path = str(metadata.get("file_path", "")).lower()
        file_stem = Path(file_path).stem.lower()
        source_code = str(candidate.get("source_code", "")).lower()

        # 1. Identifier alignment (0.0 to 1.0)
        ident_score = 0.0
        if symbol and symbol in query_terms:
            ident_score += 0.6
        if parent_symbol and parent_symbol in query_terms:
            ident_score += 0.3
        if file_stem in query_terms or file_path in query.lower():
            ident_score += 0.3
        ident_score = min(1.0, ident_score)

        # 2. Lexical coverage in source code (0.0 to 1.0)
        matched_terms = sum(1 for term in query_terms if term in source_code)
        coverage_score = (matched_terms / len(query_terms)) if query_terms else 0.0

        # Exact phrase bonus (e.g. if query contains an exact multi-word function call or name)
        clean_query = query.strip().lower()
        if len(clean_query) > 5 and clean_query in source_code:
            coverage_score = min(1.0, coverage_score + 0.3)

        # 3. Normalized RRF score (0.0 to 1.0)
        raw_rrf = float(candidate.get("rrf_score", 0.0))
        norm_rrf = (raw_rrf / max_rrf) if max_rrf > 0 else 0.5

        return (
            self.identifier_weight * ident_score
            + self.coverage_weight * coverage_score
            + self.rrf_weight * norm_rrf
        )

    def rerank(self, candidates: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
        if not candidates:
            return []

        query_terms = self._extract_query_terms(query)
        max_rrf = max((float(c.get("rrf_score", 0.0)) for c in candidates), default=1.0)

        scored: list[tuple[float, dict[str, Any]]] = []
        for candidate in candidates:
            score = self.score_candidate(candidate, query, query_terms, max_rrf)
            cand_copy = dict(candidate)
            cand_copy["rerank_score"] = score
            scored.append((score, cand_copy))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [pair[1] for pair in scored]
