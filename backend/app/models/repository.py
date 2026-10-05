from pydantic import BaseModel, Field


class RepositoryScanRequest(BaseModel):
    path: str = Field(min_length=1, description="Absolute or relative path to a local repository")


class DiscoveredPythonFile(BaseModel):
    path: str
    line_count: int


class RepositoryScanResponse(BaseModel):
    repository_path: str
    repository_name: str
    python_file_count: int
    total_line_count: int
    total_discovered_files: int
    discovered_files: list[DiscoveredPythonFile]
    scan_status: str


class RepositoryOverviewResponse(BaseModel):
    repository_id: str
    repository_name: str
    repository_path: str
    supported_languages: list[str] = Field(default_factory=lambda: ["Python"])
    files_count: int
    lines_count: int
    chunks_count: int
    classes_count: int
    functions_count: int
    methods_count: int
    modules_count: int = 0
    indexed_at: str
    embedding_model: str
    llm_model: str
    default_retrieval_mode: str = "hybrid"


class SourceCodeResponse(BaseModel):
    repository_id: str
    file_path: str
    start_line: int
    end_line: int
    total_lines: int
    code: str
    full_content: str | None = None

