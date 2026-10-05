from pydantic import BaseModel, Field


class CodeChunk(BaseModel):
    repository_id: str
    repository_name: str
    repository_path: str
    file_path: str
    symbol: str = ""
    parent_symbol: str = ""
    chunk_type: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    source_code: str


class RepositoryIndexRequest(BaseModel):
    path: str = Field(min_length=1)


class IndexJobResponse(BaseModel):
    job_id: str
    repository_id: str
    repository_name: str
    repository_path: str
    status: str
    stage: str = "queued"
    files_total: int = 0
    files_processed: int = 0
    files_indexed: int = 0
    chunks_total: int = 0
    chunks_indexed: int = 0
    syntax_error_files: int = 0
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


class ChatRequest(BaseModel):
    path: str = Field(min_length=1)
    question: str = Field(min_length=1, max_length=4000)
    top_k: int | None = Field(default=None, ge=1, le=20)
    retrieval_mode: str = Field(default="hybrid", pattern="^(hybrid|semantic|bm25|hybrid_rerank|hybrid\\+rerank)$")


class SourceReference(BaseModel):
    file_path: str
    symbol: str = ""
    parent_symbol: str = ""
    chunk_type: str
    start_line: int
    end_line: int


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceReference]
    retrieved_chunks: int
    repository_id: str
    repository_name: str
    retrieval_mode: str = "hybrid"


class OllamaStatusResponse(BaseModel):
    available: bool
    model: str
    model_available: bool
    detail: str
