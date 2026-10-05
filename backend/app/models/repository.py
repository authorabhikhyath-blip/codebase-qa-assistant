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
