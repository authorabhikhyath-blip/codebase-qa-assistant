from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Callable
from uuid import uuid4

from app.core.config import settings
from app.models.rag import CodeChunk
from app.services.embeddings import get_embedding_service
from app.services.python_parser import PythonTreeSitterParser
from app.services.repository_ingestion import scan_repository
from app.services.vector_store import LocalChromaStore, get_local_chroma_store, repository_identity


class RepositoryIndexingService:
    def __init__(self, *, embedder=None, vector_store: LocalChromaStore | None = None,
                 parser: PythonTreeSitterParser | None = None) -> None:
        self.embedder = embedder or get_embedding_service()
        self.vector_store = vector_store or get_local_chroma_store()
        self.parser = parser or PythonTreeSitterParser()

    def index_repository(self, path: str, progress: Callable[..., None] | None = None) -> dict[str, object]:
        scan = scan_repository(path)
        repository_id, canonical_path = repository_identity(scan["repository_path"])
        repository_name = str(scan["repository_name"])
        files = scan["discovered_files"]
        if progress:
            progress(files_total=len(files), repository_id=repository_id, repository_name=repository_name,
                     repository_path=canonical_path, stage="parsing")
        chunks: list[CodeChunk] = []
        warnings: list[str] = []
        syntax_error_files = 0
        for index, file_info in enumerate(files, start=1):
            relative_path = str(file_info["path"])
            source_path = Path(canonical_path) / Path(relative_path)
            try:
                source = source_path.read_text(encoding="utf-8", errors="replace")
                file_chunks, has_syntax_error = self.parser.parse(
                    source,
                    repository_id=repository_id,
                    repository_name=repository_name,
                    repository_path=canonical_path,
                    file_path=relative_path,
                )
                chunks.extend(file_chunks)
                if has_syntax_error:
                    syntax_error_files += 1
                    warnings.append(f"Tree-sitter reported syntax errors in {relative_path}; valid syntax regions were indexed where available.")
            except (OSError, UnicodeError) as error:
                warnings.append(f"Could not parse {relative_path}: {error}")
            if progress:
                progress(files_processed=index, chunks_total=len(chunks), syntax_error_files=syntax_error_files)

        if progress:
            progress(stage="embedding")
        vectors: list[list[float]] = []
        for offset in range(0, len(chunks), 64):
            batch = chunks[offset:offset + 64]
            vectors.extend(self.embedder.embed_documents([
                f"File: {chunk.file_path}\nSymbol: {chunk.symbol}\nType: {chunk.chunk_type}\n{chunk.source_code}"
                for chunk in batch
            ]))
        if progress:
            progress(stage="storing")
        chunks_indexed = self.vector_store.replace_repository_chunks(repository_id, chunks, vectors)
        return {
            "repository_id": repository_id,
            "repository_name": repository_name,
            "repository_path": canonical_path,
            "files_total": len(files),
            "files_processed": len(files),
            "files_indexed": len(files),
            "chunks_total": len(chunks),
            "chunks_indexed": chunks_indexed,
            "syntax_error_files": syntax_error_files,
            "warnings": warnings,
            "status": "completed",
            "stage": "completed",
        }


class IndexJobManager:
    def __init__(self, indexing_service: RepositoryIndexingService | None = None) -> None:
        self.indexing_service = indexing_service
        self._jobs: dict[str, dict[str, object]] = {}
        self._lock = Lock()

    def submit(self, path: str) -> dict[str, object]:
        repository_id, canonical_path = repository_identity(path)
        job_id = uuid4().hex
        job: dict[str, object] = {
            "job_id": job_id,
            "repository_id": repository_id,
            "repository_name": Path(canonical_path).name,
            "repository_path": canonical_path,
            "status": "queued",
            "files_total": 0,
            "files_processed": 0,
            "files_indexed": 0,
            "chunks_total": 0,
            "chunks_indexed": 0,
            "syntax_error_files": 0,
            "warnings": [],
            "error": None,
        }
        with self._lock:
            if any(job["repository_id"] == repository_id and job["status"] in {"queued", "indexing"}
                   for job in self._jobs.values()):
                raise IndexAlreadyRunning("An indexing job for this repository is already running.")
            self._jobs[job_id] = job
        return dict(job)

    def run(self, job_id: str, path: str) -> None:
        self._update(job_id, status="indexing")
        try:
            service = self.indexing_service or RepositoryIndexingService()
            result = service.index_repository(path, lambda **updates: self._update(job_id, **updates))
            self._update(job_id, **result)
        except Exception as error:
            self._update(job_id, status="failed", error=str(error))

    def get(self, job_id: str) -> dict[str, object] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def _update(self, job_id: str, **updates: object) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].update(updates)


class IndexAlreadyRunning(RuntimeError):
    pass
