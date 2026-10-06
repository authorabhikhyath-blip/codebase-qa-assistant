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
    assert {chunk.chunk_type for chunk in chunks} == {"module_preamble", "class", "method", "function"}
    assert not any(chunk.chunk_type == "import" for chunk in chunks)
    assert not any(chunk.chunk_type == "module" for chunk in chunks)
    preamble = next(chunk for chunk in chunks if chunk.chunk_type == "module_preamble")
    assert "import os" in preamble.source_code
    assert preamble.start_line == 1 and preamble.end_line == 1

    cls_chunk = next(chunk for chunk in chunks if chunk.chunk_type == "class")
    assert cls_chunk.symbol == "UserService"
    assert cls_chunk.parent_symbol == ""
    assert cls_chunk.start_line == 3

    method = next(chunk for chunk in chunks if chunk.chunk_type == "method")
    assert method.symbol == "authenticate"
    assert method.parent_symbol == "UserService"
    assert method.start_line == 4 and method.end_line == 5
    assert "return bool(password)" in method.source_code

    func_chunk = next(chunk for chunk in chunks if chunk.chunk_type == "function")
    assert func_chunk.symbol == "logout"
    assert func_chunk.parent_symbol == ""


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
    assert "local codebase understanding assistant" in ollama.prompt
    assert "connect evidence from the different supplied files" in ollama.prompt
    assert "Every repository-specific claim must include an inline citation" in ollama.prompt
    assert "Keep pipeline stages distinct" in ollama.prompt
    assert "do not infer its behavior from a related backend endpoint" in ollama.prompt
    assert "non-Python files such as TypeScript are not included as evidence" in ollama.prompt
    assert "do not force a fixed answer template" in ollama.prompt


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
    assert isinstance(payload["answer"], str)
    assert payload["retrieved_chunks"] > 0
    assert payload["sources"]
    assert all(source["start_line"] >= 1 and isinstance(source["file_path"], str) for source in payload["sources"])
    assert payload["repository_id"]
    assert payload["repository_name"] == repository.name
    assert isinstance(payload["retrieval_mode"], str)


def test_broad_questions_expand_retrieval_for_multi_file_evidence(tmp_path: Path) -> None:
    def candidate(path: str, line: int) -> dict[str, object]:
        return {
            "chunk_id": f"{path}-{line}",
            "source_code": f"def step_{line}(): return {line}",
            "metadata": {"file_path": path, "start_line": line, "end_line": line + 1, "symbol": f"step_{line}", "chunk_type": "function"},
        }

    class TrackingVectorStore:
        def __init__(self) -> None:
            self.data_dir = tmp_path / "chroma"
            self.requested_k: list[int] = []

        def count(self, _repository_id: str) -> int:
            return 1

        def search(self, _repository_id: str, _embedding: list[float], top_k: int) -> list[dict[str, object]]:
            self.requested_k.append(top_k)
            return [candidate(f"frontend/part_{index}.py", index) for index in range(top_k)]

    class TrackingBM25Store:
        def __init__(self) -> None:
            self.requested_k: list[int] = []

        def count(self, _repository_id: str) -> int:
            return 1

        def search(self, _repository_id: str, _question: str, top_k: int) -> list[dict[str, object]]:
            self.requested_k.append(top_k)
            return [candidate(f"backend/part_{index}.py", index + 100) for index in range(top_k)]

    class Embedder:
        def embed_query(self, _query: str) -> list[float]:
            return [1.0]

    repository = tmp_path / "repository"
    repository.mkdir()
    vectors = TrackingVectorStore()
    lexical = TrackingBM25Store()
    qa = LocalQAService(embedder=Embedder(), vector_store=vectors, bm25_store=lexical, ollama=StubOllama())

    broad = qa.retrieve(str(repository), "How does the backend combine semantic and lexical search, and where is RRF applied?", retrieval_mode="hybrid")
    broad_candidate_count = vectors.requested_k[-1]
    focused = qa.retrieve(str(repository), "Where is rrf_k configured?", retrieval_mode="hybrid")
    focused_candidate_count = vectors.requested_k[-1]

    assert broad_candidate_count == 64
    assert focused_candidate_count < broad_candidate_count
    assert len(broad) == 8
    assert len({item["metadata"]["file_path"] for item in broad}) == len(broad)


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


def test_imports_grouped_into_single_preamble_chunk() -> None:
    parser = PythonTreeSitterParser()
    source = (
        '"""Module docstring."""\n'
        'from __future__ import annotations\n\n'
        'import os\n'
        'import sys\n'
        'from pathlib import Path\n\n'
        'def main():\n'
        '    return 0\n'
    )
    chunks, syntax_error = parser.parse(
        source,
        repository_id="repo-id",
        repository_name="sample",
        repository_path="/tmp/sample",
        file_path="main.py",
    )

    assert not syntax_error
    preambles = [c for c in chunks if c.chunk_type == "module_preamble"]
    assert len(preambles) == 1
    assert "import os" in preambles[0].source_code
    assert "import sys" in preambles[0].source_code
    assert "from pathlib import Path" in preambles[0].source_code
    assert not any(c.chunk_type == "import" for c in chunks)
    assert any(c.chunk_type == "function" and c.symbol == "main" for c in chunks)


def test_nested_classes_and_methods_track_parent_symbols() -> None:
    parser = PythonTreeSitterParser()
    source = (
        "class Outer:\n"
        "    class Inner:\n"
        "        def inner_method(self):\n"
        "            return 1\n"
        "    def outer_method(self):\n"
        "        return 2\n"
    )
    chunks, _ = parser.parse(
        source,
        repository_id="repo-id",
        repository_name="sample",
        repository_path="/tmp/sample",
        file_path="nested.py",
    )

    outer_class = next(c for c in chunks if c.chunk_type == "class" and c.symbol == "Outer")
    assert outer_class.parent_symbol == ""

    inner_class = next(c for c in chunks if c.chunk_type == "class" and c.symbol == "Inner")
    assert inner_class.parent_symbol == "Outer"

    inner_method = next(c for c in chunks if c.chunk_type == "method" and c.symbol == "inner_method")
    assert inner_method.parent_symbol == "Outer.Inner"

    outer_method = next(c for c in chunks if c.chunk_type == "method" and c.symbol == "outer_method")
    assert outer_method.parent_symbol == "Outer"


def test_select_diverse_chunks_filters_overlapping_class_and_method() -> None:
    candidates = [
        # Rank 1: Method 'authenticate' inside UserService
        {
            "source_code": "def authenticate(self): return True",
            "metadata": {
                "file_path": "services/auth.py",
                "symbol": "authenticate",
                "parent_symbol": "UserService",
                "chunk_type": "method",
                "start_line": 20,
                "end_line": 35,
            },
        },
        # Rank 2: Entire UserService class (encompasses lines 10-60, completely overlapping with rank 1)
        {
            "source_code": "class UserService:\n    ...",
            "metadata": {
                "file_path": "services/auth.py",
                "symbol": "UserService",
                "parent_symbol": "",
                "chunk_type": "class",
                "start_line": 10,
                "end_line": 60,
            },
        },
        # Rank 3: Another method from a completely different file
        {
            "source_code": "def parse(): pass",
            "metadata": {
                "file_path": "services/parser.py",
                "symbol": "parse",
                "parent_symbol": "Parser",
                "chunk_type": "method",
                "start_line": 15,
                "end_line": 40,
            },
        },
        # Rank 4: Module preamble from services/auth.py (lines 1-8, non-overlapping with method authenticate)
        {
            "source_code": "import os\nfrom pathlib import Path",
            "metadata": {
                "file_path": "services/auth.py",
                "symbol": "auth",
                "parent_symbol": "",
                "chunk_type": "module_preamble",
                "start_line": 1,
                "end_line": 8,
            },
        },
    ]

    selected = LocalQAService.select_diverse_chunks(candidates, target_k=3)
    # The duplicate containing class (Rank 2) must be skipped because it heavily overlaps with Rank 1!
    assert len(selected) == 3
    assert selected[0]["metadata"]["symbol"] == "authenticate"
    assert selected[1]["metadata"]["symbol"] == "parse"
    assert selected[2]["metadata"]["chunk_type"] == "module_preamble"
    assert not any(item["metadata"]["symbol"] == "UserService" for item in selected)
