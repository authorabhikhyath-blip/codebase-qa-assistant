from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.indexing import IndexAlreadyRunning, IndexJobManager, RepositoryIndexingService
from app.services.ollama import LocalOllamaService, OllamaUnavailable
from app.services.python_parser import PythonTreeSitterParser
from app.services.qa import LocalQAService
from app.services.vector_store import LocalChromaStore


class DeterministicEmbedder:
    """Small deterministic vectors for tests; no model download is needed."""

    @staticmethod
    def _vector(text: str) -> list[float]:
        words = set(text.lower().replace("_", " ").replace("(", " ").replace(")", " ").split())
        auth_words = {"auth", "authenticate", "authentication", "password", "token", "login", "credential"}
        db_words = {"database", "sqlite", "connection", "query", "select", "cursor"}
        return [float(bool(words & auth_words)), float(bool(words & db_words)), 0.05]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


class StubOllama:
    def __init__(self, answer: str = "Authentication checks the password before issuing a token [auth.py:1-3]."):
        self.answer = answer
        self.prompt = ""

    def generate(self, prompt: str) -> str:
        self.prompt = prompt
        return self.answer


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    (tmp_path / "auth.py").write_text(
        "def authenticate_user(password):\n    if password:\n        return issue_token()\n    return None\n",
        encoding="utf-8",
    )
    (tmp_path / "storage.py").write_text(
        "def open_database(path):\n    connection = sqlite3.connect(path)\n    return connection\n",
        encoding="utf-8",
    )
    return tmp_path


def test_tree_sitter_extracts_function_class_method_and_imports() -> None:
    parser = PythonTreeSitterParser()
    source = "import os\n\nclass UserService:\n    def authenticate(self, password):\n        return bool(password)\n\ndef logout():\n    return None\n"

    chunks, syntax_error = parser.parse(
        source,
        repository_id="repo-id",
        repository_name="sample",
        repository_path="/tmp/sample",
        file_path="service.py",
    )

    assert not syntax_error
    assert {chunk.chunk_type for chunk in chunks} >= {"module", "import", "class", "method", "function"}
    assert any(chunk.symbol == "UserService" and chunk.start_line == 3 for chunk in chunks)
    method = next(chunk for chunk in chunks if chunk.chunk_type == "method")
    assert method.symbol == "authenticate"
    assert method.start_line == 4 and method.end_line == 5
    assert "return bool(password)" in method.source_code


def test_tree_sitter_reports_syntax_errors_without_throwing() -> None:
    parser = PythonTreeSitterParser()
    chunks, syntax_error = parser.parse(
        "def broken(:\n    pass\n\ndef usable():\n    return 1\n",
        repository_id="repo-id",
        repository_name="sample",
        repository_path="/tmp/sample",
        file_path="broken.py",
    )

    assert syntax_error
    assert any(chunk.symbol == "usable" for chunk in chunks)


def test_indexing_and_chroma_retrieval_preserve_metadata(repository: Path, tmp_path: Path) -> None:
    embedder = DeterministicEmbedder()
    store = LocalChromaStore(tmp_path / "vectors")
    indexer = RepositoryIndexingService(embedder=embedder, vector_store=store)

    indexed = indexer.index_repository(str(repository))
    retrieved = store.search(str(indexed["repository_id"]), embedder.embed_query("How does login verify a password?"), 3)

    assert indexed["status"] == "completed"
    assert indexed["files_indexed"] == 2
    assert indexed["chunks_indexed"] > 0
    assert retrieved
    assert any(item["metadata"]["file_path"] == "auth.py" for item in retrieved)
    assert all({"repository_id", "file_path", "chunk_type", "start_line", "end_line"} <= item["metadata"].keys() for item in retrieved)


def test_indexing_continues_when_a_file_has_syntax_errors(tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text("def broken(:\n    pass\n", encoding="utf-8")
    (tmp_path / "valid.py").write_text("def usable():\n    return True\n", encoding="utf-8")
    result = RepositoryIndexingService(
        embedder=DeterministicEmbedder(), vector_store=LocalChromaStore(tmp_path / "vectors")
    ).index_repository(str(tmp_path))

    assert result["files_indexed"] == 2
    assert result["syntax_error_files"] == 1
    assert any("broken.py" in warning for warning in result["warnings"])
    assert result["chunks_indexed"] > 0


def test_reindex_replaces_previous_chunks_without_duplicates(repository: Path, tmp_path: Path) -> None:
    embedder = DeterministicEmbedder()
    store = LocalChromaStore(tmp_path / "vectors")
    indexer = RepositoryIndexingService(embedder=embedder, vector_store=store)

    first = indexer.index_repository(str(repository))
    (repository / "auth.py").write_text("def authenticate():\n    return True\n", encoding="utf-8")
    second = indexer.index_repository(str(repository))

    assert first["repository_id"] == second["repository_id"]
    assert second["chunks_indexed"] == second["chunks_total"]
    assert store.count(str(second["repository_id"])) == second["chunks_total"]


def test_chat_builds_grounded_prompt_and_source_references(repository: Path, tmp_path: Path) -> None:
    embedder = DeterministicEmbedder()
    store = LocalChromaStore(tmp_path / "vectors")
    RepositoryIndexingService(embedder=embedder, vector_store=store).index_repository(str(repository))
    ollama = StubOllama()
    qa = LocalQAService(embedder=embedder, vector_store=store, ollama=ollama)

    response = qa.ask(str(repository), "How does login verify a password?", top_k=3)

    assert response["answer"].startswith("Authentication checks")
    assert any(source["file_path"] == "auth.py" for source in response["sources"])
    assert "Question: How does login verify a password?" in ollama.prompt
    assert "auth.py:" in ollama.prompt
    assert "Do not invent repository facts" in ollama.prompt
    assert "Do not claim a file or symbol is absent" in ollama.prompt


def test_chat_api_returns_retrieval_and_source_metadata(repository: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    embedder = DeterministicEmbedder()
    store = LocalChromaStore(tmp_path / "vectors")
    RepositoryIndexingService(embedder=embedder, vector_store=store).index_repository(str(repository))
    qa = LocalQAService(embedder=embedder, vector_store=store, ollama=StubOllama())

    import app.api.routes as routes
    monkeypatch.setattr(routes, "LocalQAService", lambda: qa)
    response = TestClient(app).post("/api/chat", json={"path": str(repository), "question": "How does login authenticate a password?"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["retrieved_chunks"] > 0
    assert payload["sources"]
    assert all(source["start_line"] >= 1 for source in payload["sources"])


def test_chat_api_gives_actionable_error_for_unindexed_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class EmptyQA:
        def ask(self, *_args, **_kwargs):
            from app.services.qa import RepositoryNotIndexed
            raise RepositoryNotIndexed("This repository has no indexed chunks. Run repository indexing first.")

    import app.api.routes as routes
    monkeypatch.setattr(routes, "LocalQAService", EmptyQA)
    response = TestClient(app).post("/api/chat", json={"path": str(tmp_path), "question": "What does this project do?"})

    assert response.status_code == 409
    assert "indexing first" in response.json()["detail"]


def test_ollama_is_restricted_to_local_loopback_urls() -> None:
    with pytest.raises(ValueError, match="loopback"):
        LocalOllamaService("https://example.com", "local-model")


def test_ollama_cloud_models_are_rejected() -> None:
    with pytest.raises(ValueError, match="cloud models are not allowed"):
        LocalOllamaService("http://127.0.0.1:11434", "remote-model:cloud")


def test_ollama_status_does_not_accept_registered_cloud_models(monkeypatch: pytest.MonkeyPatch) -> None:
    response = httpx.Response(200, json={"models": [
        {"name": "local-model:latest"},
        {"name": "remote-model:cloud", "remote_model": "remote-model", "remote_host": "https://ollama.com"},
    ]}, request=httpx.Request("GET", "http://localhost"))
    monkeypatch.setattr(httpx, "get", lambda *_args, **_kwargs: response)

    status = LocalOllamaService("http://localhost:11434", "remote-model").status()
    assert status["model_available"] is False


def test_ollama_status_endpoint_reports_invalid_remote_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.api.routes as routes
    monkeypatch.setattr(routes, "LocalOllamaService", lambda: (_ for _ in ()).throw(ValueError("Ollama cloud models are not allowed.")))

    response = TestClient(app).get("/api/ollama/status")

    assert response.status_code == 200
    assert response.json()["available"] is False
    assert "cloud models are not allowed" in response.json()["detail"]


def test_ollama_status_reports_not_running(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_request(*_args, **_kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "get", fail_request)
    status = LocalOllamaService("http://127.0.0.1:11434", "test-model").status()

    assert status["available"] is False
    assert "Install/start Ollama locally" in status["detail"]


def test_ollama_generate_uses_installed_local_model(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(*_args, **_kwargs):
        return httpx.Response(200, json={"models": [{"name": "test-model"}]}, request=httpx.Request("GET", "http://localhost"))

    def fake_post(*_args, **kwargs):
        assert kwargs["json"]["model"] == "test-model"
        assert kwargs["json"]["stream"] is False
        return httpx.Response(200, json={"response": "answer"}, request=httpx.Request("POST", "http://localhost"))

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "post", fake_post)

    assert LocalOllamaService("http://localhost:11434", "test-model").generate("prompt") == "answer"


def test_indexing_api_starts_and_exposes_progress(repository: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.api.routes as routes
    from app.services.indexing import RepositoryIndexingService

    monkeypatch.setattr(routes.index_jobs, "indexing_service", RepositoryIndexingService(
        embedder=DeterministicEmbedder(),
        vector_store=LocalChromaStore(tmp_path / "vectors"),
    ))
    client = TestClient(app)

    started = client.post("/api/repositories/index", json={"path": str(repository)})

    assert started.status_code == 202
    job_id = started.json()["job_id"]
    status = client.get(f"/api/repositories/index/{job_id}")
    assert status.status_code == 200
    assert status.json()["status"] == "completed"
    assert status.json()["stage"] == "completed"
    assert status.json()["files_indexed"] == 2
    assert status.json()["chunks_indexed"] > 0


def test_index_job_manager_prevents_parallel_duplicate_jobs(repository: Path) -> None:
    manager = IndexJobManager()
    manager.submit(str(repository))

    with pytest.raises(IndexAlreadyRunning):
        manager.submit(str(repository))


def test_indexing_api_rejects_invalid_path() -> None:
    response = TestClient(app).post("/api/repositories/index", json={"path": "Z:/missing/codebase-qa-test"})

    assert response.status_code == 400
    assert "cannot be accessed" in response.json()["detail"]


def test_indexing_api_rejects_non_directory_path(tmp_path: Path) -> None:
    file_path = tmp_path / "module.py"
    file_path.write_text("pass\n", encoding="utf-8")

    response = TestClient(app).post("/api/repositories/index", json={"path": str(file_path)})

    assert response.status_code == 400
    assert "must point to a directory" in response.json()["detail"]
