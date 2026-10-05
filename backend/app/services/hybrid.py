from __future__ import annotations

from typing import Any


def item_identity(item: dict[str, Any]) -> str:
    """Extract a unique identity for a retrieved chunk item."""
    if item.get("chunk_id"):
        return str(item["chunk_id"])
    meta = item.get("metadata", {})
    return "\0".join((
        str(meta.get("file_path", "")),
        str(meta.get("start_line", "")),
        str(meta.get("end_line", "")),
        str(meta.get("symbol", "")),
        str(meta.get("parent_symbol", "")),
    ))


def reciprocal_rank_fusion(
    ranked_lists: list[list[dict[str, Any]]],
    rrf_k: int = 60,
) -> list[dict[str, Any]]:
    """
    Fuse multiple ranked candidate lists using Reciprocal Rank Fusion (RRF).

    Formula:
        score(d) = sum(1.0 / (rrf_k + rank)) for each ranking list containing d.
    """
    scores: dict[str, float] = {}
    items_by_id: dict[str, dict[str, Any]] = {}

    for ranked_list in ranked_lists:
        for rank, item in enumerate(ranked_list, start=1):
            doc_id = item_identity(item)
            if doc_id not in scores:
                scores[doc_id] = 0.0
                items_by_id[doc_id] = item
            scores[doc_id] += 1.0 / (rrf_k + rank)

    sorted_ids = sorted(scores.keys(), key=lambda doc_id: scores[doc_id], reverse=True)

    fused: list[dict[str, Any]] = []
    for doc_id in sorted_ids:
        candidate = dict(items_by_id[doc_id])
        candidate["rrf_score"] = scores[doc_id]
        fused.append(candidate)

    return fused
