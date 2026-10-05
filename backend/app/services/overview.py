from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.services.bm25 import get_local_bm25_store


def repositories_dir(data_dir: Path | str | None = None) -> Path:
    if data_dir is not None:
        p = Path(data_dir)
        base = p if p.name == "repositories" else p / "repositories"
    else:
        base = Path(settings.chroma_data_dir).parent / "repositories"
    base.mkdir(parents=True, exist_ok=True)
    return base


def overview_path(repository_id: str, data_dir: Path | str | None = None) -> Path:
    return repositories_dir(data_dir) / f"overview_{repository_id[:32]}.json"


def save_repository_overview(overview: dict[str, Any], data_dir: Path | str | None = None) -> None:
    repo_id = str(overview["repository_id"])
    target = overview_path(repo_id, data_dir)
    temp = target.with_suffix(".tmp")
    temp.write_text(json.dumps(overview, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(target)


def get_repository_overview(repository_id: str, data_dir: Path | str | None = None) -> dict[str, Any] | None:
    target = overview_path(repository_id, data_dir)
    if target.exists():
        try:
            return json.loads(target.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    # Fallback: attempt to reconstruct from BM25 index
    bm25_dir = Path(data_dir or settings.bm25_data_dir)
    bm25_store = get_local_bm25_store(bm25_dir)
    index_data = bm25_store._load_index(repository_id)
    if not index_data:
        return None

    documents = index_data.get("documents", [])
    if not documents:
        return None

    first_meta = documents[0].get("metadata", {})
    repo_path = first_meta.get("repository_path", "")
    repo_name = first_meta.get("repository_name", "") or Path(repo_path).name

    files: set[str] = set()
    classes_count = 0
    functions_count = 0
    methods_count = 0
    modules_count = 0

    for doc in documents:
        meta = doc.get("metadata", {})
        fp = meta.get("file_path")
        if fp:
            files.add(fp)
        ctype = meta.get("chunk_type")
        if ctype == "class":
            classes_count += 1
        elif ctype == "function":
            functions_count += 1
        elif ctype == "method":
            methods_count += 1
        elif ctype in {"module", "module_preamble"}:
            modules_count += 1

    return {
        "repository_id": repository_id,
        "repository_name": repo_name,
        "repository_path": repo_path,
        "supported_languages": ["Python"],
        "files_count": len(files),
        "lines_count": sum(int(doc.get("metadata", {}).get("end_line", 0)) for doc in documents if doc.get("metadata", {}).get("chunk_type") in {"module", "module_preamble"}),
        "chunks_count": len(documents),
        "classes_count": classes_count,
        "functions_count": functions_count,
        "methods_count": methods_count,
        "modules_count": modules_count,
        "indexed_at": datetime.now(timezone.utc).isoformat(),
        "embedding_model": settings.embedding_model,
        "llm_model": settings.ollama_model,
        "default_retrieval_mode": "hybrid",
    }


def get_repository_source_snippet(
    repository_id: str,
    file_path: str,
    start_line: int | None = None,
    end_line: int | None = None,
    data_dir: Path | str | None = None,
) -> dict[str, Any]:
    if not file_path or "\0" in file_path:
        raise ValueError("Invalid file path.")

    overview = get_repository_overview(repository_id, data_dir)
    if not overview or not overview.get("repository_path"):
        raise KeyError(f"Repository {repository_id} is not indexed.")

    canonical_root = Path(overview["repository_path"]).resolve()
    target = (canonical_root / file_path).resolve()

    # SECURITY: Verify strict containment within the canonical repository root
    try:
        target.relative_to(canonical_root)
    except ValueError as err:
        raise PermissionError("Access denied: path traversal outside repository root.") from err

    # SECURITY: Check symlinks do not point outside repository root
    if target.is_symlink():
        symlink_target = target.resolve()
        try:
            symlink_target.relative_to(canonical_root)
        except ValueError as err:
            raise PermissionError("Access denied: unsafe symlink points outside repository root.") from err

    if not target.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    full_text = target.read_text(encoding="utf-8", errors="replace")
    all_lines = full_text.splitlines(keepends=True)
    total_lines = len(all_lines)

    s = max(1, start_line) if start_line is not None else 1
    e = min(total_lines, end_line) if end_line is not None else total_lines
    if s > total_lines:
        snippet = ""
    else:
        snippet = "".join(all_lines[s - 1 : max(s, e)])

    return {
        "repository_id": repository_id,
        "file_path": file_path,
        "start_line": s,
        "end_line": max(s, e),
        "total_lines": total_lines,
        "code": snippet,
        "content": snippet,
        "full_content": full_text,
    }
