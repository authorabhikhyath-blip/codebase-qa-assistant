from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.core.config import settings
from app.models.rag import ChatRequest, ChatResponse, IndexJobResponse, OllamaStatusResponse, RepositoryIndexRequest
from app.models.repository import (
    RepositoryOverviewResponse,
    RepositoryScanRequest,
    RepositoryScanResponse,
    SourceCodeResponse,
)
from app.services.embeddings import EmbeddingServiceError
from app.services.indexing import IndexAlreadyRunning, IndexJobManager
from app.services.ollama import LocalOllamaService, OllamaUnavailable
from app.services.overview import get_repository_overview, get_repository_source_snippet
from app.services.qa import LocalQAService, RepositoryNotIndexed
from app.services.repository_ingestion import RepositoryScanError, scan_repository

router = APIRouter()
index_jobs = IndexJobManager()


@router.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/api/repositories/scan", response_model=RepositoryScanResponse, tags=["repositories"])
def scan_local_repository(request: RepositoryScanRequest) -> RepositoryScanResponse:
    try:
        result = scan_repository(request.path)
    except RepositoryScanError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error
    return RepositoryScanResponse(**result)


@router.post("/api/repositories/index", response_model=IndexJobResponse, status_code=202, tags=["repositories"])
def index_local_repository(request: RepositoryIndexRequest, background_tasks: BackgroundTasks) -> IndexJobResponse:
    try:
        job = index_jobs.submit(request.path)
    except IndexAlreadyRunning as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except (OSError, RuntimeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=f"Repository path cannot be accessed: {error}") from error
    background_tasks.add_task(index_jobs.run, str(job["job_id"]), str(job["repository_path"]))
    return IndexJobResponse(**job)


@router.get("/api/repositories/index/{job_id}", response_model=IndexJobResponse, tags=["repositories"])
def repository_index_status(job_id: str) -> IndexJobResponse:
    job = index_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Indexing job was not found. It may have expired after a backend restart.")
    return IndexJobResponse(**job)


@router.get("/api/ollama/status", response_model=OllamaStatusResponse, tags=["models"])
def ollama_status() -> OllamaStatusResponse:
    try:
        result = LocalOllamaService().status()
    except ValueError as error:
        result = {"available": False, "model": settings.ollama_model, "model_available": False, "detail": str(error)}
    return OllamaStatusResponse(**result)


@router.post("/api/chat", response_model=ChatResponse, tags=["chat"])
def chat(request: ChatRequest) -> ChatResponse:
    try:
        result = LocalQAService().ask(request.path, request.question, request.top_k, request.retrieval_mode)
    except RepositoryNotIndexed as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except OllamaUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except EmbeddingServiceError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except (OSError, RuntimeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=f"Could not query this repository: {error}") from error
    return ChatResponse(**result)


@router.get("/api/repositories/{id}/overview", response_model=RepositoryOverviewResponse, tags=["repositories"])
def repository_overview(id: str) -> RepositoryOverviewResponse:
    overview = get_repository_overview(id)
    if overview is None:
        raise HTTPException(status_code=404, detail="Repository overview not found. Run repository indexing first.")
    return RepositoryOverviewResponse(**overview)


@router.get("/api/repositories/{id}/source", response_model=SourceCodeResponse, tags=["repositories"])
def repository_source(
    id: str,
    file_path: str,
    start_line: int | None = None,
    end_line: int | None = None,
) -> SourceCodeResponse:
    try:
        snippet = get_repository_source_snippet(id, file_path, start_line, end_line)
        return SourceCodeResponse(**snippet)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

