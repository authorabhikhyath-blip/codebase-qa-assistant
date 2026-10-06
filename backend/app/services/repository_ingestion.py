from __future__ import annotations

import os
from pathlib import Path


IGNORED_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
    ".pnpm-store",
    ".npm",
    ".yarn",
    ".next",
    ".turbo",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".cache",
    ".idea",
    ".vscode",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "dist",
    "build",
    "coverage",
    "site-packages",
}


class RepositoryScanError(Exception):
    def __init__(self, message: str, status_code: int) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _line_count(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8", errors="replace", newline=None) as source:
            return sum(1 for _ in source)
    except OSError as error:
        raise RepositoryScanError(f"Could not read source file '{path.name}': {error.strerror or error}.", 403) from error


def scan_repository(repository_path: str) -> dict[str, object]:
    """Discover local Python sources without following directory or file symlinks."""
    try:
        root = Path(repository_path).expanduser().resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as error:
        raise RepositoryScanError(f"Repository path cannot be accessed: {error}.", 400) from error

    if not root.is_dir():
        raise RepositoryScanError("Repository path must point to a directory.", 400)

    python_files: list[dict[str, object]] = []
    total_discovered_files = 0
    walk_error: OSError | None = None

    def on_walk_error(error: OSError) -> None:
        nonlocal walk_error
        walk_error = error

    try:
        for current, directory_names, file_names in os.walk(root, topdown=True, followlinks=False, onerror=on_walk_error):
            current_path = Path(current)
            directory_names[:] = [
                name
                for name in directory_names
                if name.lower() not in IGNORED_DIRECTORIES and not (current_path / name).is_symlink()
            ]
            for file_name in file_names:
                file_path = current_path / file_name
                if file_path.is_symlink():
                    continue
                total_discovered_files += 1
                if file_path.suffix.lower() != ".py":
                    continue
                line_count = _line_count(file_path)
                python_files.append({
                    "path": file_path.relative_to(root).as_posix(),
                    "line_count": line_count,
                })
    except OSError as error:
        raise RepositoryScanError(f"Repository could not be scanned: {error.strerror or error}.", 403) from error

    if walk_error is not None:
        raise RepositoryScanError(f"Repository contains an inaccessible directory: {walk_error.strerror or walk_error}.", 403)

    python_files.sort(key=lambda item: str(item["path"]).casefold())
    return {
        "repository_path": str(root),
        "repository_name": root.name or str(root),
        "python_file_count": len(python_files),
        "total_line_count": sum(int(item["line_count"]) for item in python_files),
        "total_discovered_files": total_discovered_files,
        "discovered_files": python_files,
        "scan_status": "completed",
    }
