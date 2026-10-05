from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.services.indexing import RepositoryIndexingService
from app.services.overview import get_repository_overview, get_repository_source_snippet
from app.services.vector_store import LocalChromaStore


class DeterministicEmbedder:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(t) % 13), float(len(t) % 17)] for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return [float(len(text) % 13), float(len(text) % 17)]


def create_sample_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "sample_repo"
    repo.mkdir()
    (repo / "main.py").write_text(
        "import os\n\nclass AppServer:\n    def start(self):\n        return True\n\ndef helper():\n    return 42\n",
        encoding="utf-8",
    )
    (repo / "utils.py").write_text(
        "def format_name(name: str) -> str:\n    return name.title()\n",
        encoding="utf-8",
    )
    return repo


def test_repository_overview_derives_statistics(tmp_path: Path) -> None:
    repo = create_sample_repo(tmp_path)
    store = LocalChromaStore(tmp_path / "vectors")
    indexer = RepositoryIndexingService(embedder=DeterministicEmbedder(), vector_store=store)
    result = indexer.index_repository(str(repo))

    repo_id = str(result["repository_id"])
    overview = get_repository_overview(repo_id, data_dir=tmp_path)

    assert overview is not None
    assert overview["repository_id"] == repo_id
    assert overview["repository_name"] == "sample_repo"
    assert overview["files_count"] == 2
    assert overview["chunks_count"] > 0
    assert overview["classes_count"] == 1
    assert overview["methods_count"] == 1
    assert overview["functions_count"] == 2
    assert overview["supported_languages"] == ["Python"]
    assert "indexed_at" in overview


def test_repository_source_snippet_retrieval(tmp_path: Path) -> None:
    repo = create_sample_repo(tmp_path)
    store = LocalChromaStore(tmp_path / "vectors")
    indexer = RepositoryIndexingService(embedder=DeterministicEmbedder(), vector_store=store)
    result = indexer.index_repository(str(repo))
    repo_id = str(result["repository_id"])

    # Retrieve slice
    snippet = get_repository_source_snippet(
        repo_id,
        "main.py",
        start_line=3,
        end_line=5,
        data_dir=tmp_path,
    )

    assert snippet["file_path"] == "main.py"
    assert snippet["start_line"] == 3
    assert snippet["end_line"] == 5
    assert "class AppServer:" in snippet["code"]
    assert "def start(self):" in snippet["code"]


def test_source_navigation_prevents_path_traversal(tmp_path: Path) -> None:
    repo = create_sample_repo(tmp_path)
    store = LocalChromaStore(tmp_path / "vectors")
    indexer = RepositoryIndexingService(embedder=DeterministicEmbedder(), vector_store=store)
    result = indexer.index_repository(str(repo))
    repo_id = str(result["repository_id"])

    # 1. Path traversal using ../../
    with pytest.raises(PermissionError, match="traversal"):
        get_repository_source_snippet(
            repo_id,
            "../../secret.txt",
            data_dir=tmp_path,
        )

    # 2. Null byte injection
    with pytest.raises(ValueError, match="Invalid"):
        get_repository_source_snippet(
            repo_id,
            "main.py\0secret.txt",
            data_dir=tmp_path,
        )

    # 3. Nonexistent file
    with pytest.raises(FileNotFoundError):
        get_repository_source_snippet(
            repo_id,
            "nonexistent.py",
            data_dir=tmp_path,
        )


def test_api_overview_and_source_endpoints(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings
    monkeypatch.setattr(settings, "chroma_data_dir", tmp_path / "data" / "chroma")

    repo = create_sample_repo(tmp_path)
    store = LocalChromaStore(tmp_path / "data" / "chroma")
    indexer = RepositoryIndexingService(embedder=DeterministicEmbedder(), vector_store=store)
    result = indexer.index_repository(str(repo))
    repo_id = str(result["repository_id"])

    client = TestClient(app)

    # GET overview
    overview_resp = client.get(f"/api/repositories/{repo_id}/overview")
    assert overview_resp.status_code == 200
    data = overview_resp.json()
    assert data["repository_id"] == repo_id
    assert data["files_count"] == 2
    assert data["classes_count"] >= 1

    # GET source snippet
    source_resp = client.get(f"/api/repositories/{repo_id}/source?file_path=main.py&start_line=1&end_line=4")
    assert source_resp.status_code == 200
    src_data = source_resp.json()
    assert src_data["file_path"] == "main.py"
    assert "import os" in src_data["code"]

    # Security check via API
    forbidden_resp = client.get(f"/api/repositories/{repo_id}/source?file_path=../../outside.txt")
    assert forbidden_resp.status_code == 403

