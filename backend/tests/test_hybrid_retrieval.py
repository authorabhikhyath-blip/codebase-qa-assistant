from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.models.rag import CodeChunk
from app.services.bm25 import LocalBM25Store, tokenize_code
from app.services.hybrid import reciprocal_rank_fusion
from app.services.indexing import RepositoryIndexingService
from app.services.qa import LocalQAService
from app.services.vector_store import LocalChromaStore


class DeterministicEmbedder:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(text) % 17), float((len(text) * 3) % 23)] for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return [float(len(text) % 17), float((len(text) * 3) % 23)]


class StubOllama:
    def __init__(self) -> None:
        self.prompt = ""

    def generate(self, prompt: str) -> str:
        self.prompt = prompt
        return "Grounded hybrid answer citing [service.py:1-10]."


def make_chunk(repo_id: str, file_path: str, symbol: str, parent: str, chunk_type: str,
               start: int, end: int, code: str) -> CodeChunk:
    return CodeChunk(
        repository_id=repo_id,
        repository_name="sample",
        repository_path="/workspace/sample",
        file_path=file_path,
        symbol=symbol,
        parent_symbol=parent,
        chunk_type=chunk_type,
        start_line=start,
        end_line=end,
        source_code=code,
    )


def test_bm25_indexing_and_tokenization(tmp_path: Path) -> None:
    store = LocalBM25Store(tmp_path / "bm25")
    chunks = [
        make_chunk("repo1", "scanner.py", "scan_repository", "", "function", 1, 10,
                   "def scan_repository(path):\n    # traverse directories\n    pass"),
        make_chunk("repo1", "qa.py", "LocalQAService", "", "class", 1, 20,
                   "class LocalQAService:\n    def ask(self, question): pass"),
    ]

    indexed = store.replace_repository_chunks("repo1", chunks)
    assert indexed == 2
    assert store.count("repo1") == 2

    # Check tokenization contains whole tokens and sub-tokens
    tokens = tokenize_code("LocalQAService.scan_repository()")
    assert "localqaservice" in tokens
    assert "local" in tokens
    assert "qa" in tokens
    assert "service" in tokens
    assert "scan_repository" in tokens
    assert "scan" in tokens
    assert "repository" in tokens


def test_bm25_exact_identifier_retrieval(tmp_path: Path) -> None:
    store = LocalBM25Store(tmp_path / "bm25")
    chunks = [
        make_chunk("repo1", "ingestion.py", "scan_repository", "", "function", 1, 20,
                   "def scan_repository(repository_path: str):\n    return discover_files(repository_path)"),
        make_chunk("repo1", "vector.py", "replace_repository_chunks", "LocalChromaStore", "method", 10, 30,
                   "def replace_repository_chunks(self, repository_id, chunks):\n    pass"),
        make_chunk("repo1", "parser.py", "PythonTreeSitterParser", "", "class", 1, 50,
                   "class PythonTreeSitterParser:\n    def parse(self, source): pass"),
    ]
    store.replace_repository_chunks("repo1", chunks)

    # Exact query matching scan_repository
    results = store.search("repo1", "What does scan_repository do?", top_k=3)
    assert len(results) > 0
    top = results[0]
    assert top["metadata"]["symbol"] == "scan_repository"
    assert top["metadata"]["file_path"] == "ingestion.py"
    assert top["score"] > 0


def test_bm25_repository_isolation(tmp_path: Path) -> None:
    store = LocalBM25Store(tmp_path / "bm25")
    repo_a_chunks = [
        make_chunk("repo_a", "alpha.py", "render_alpha_view", "", "function", 1, 10,
                   "def render_alpha_view(): return 'alpha'"),
    ]
    repo_b_chunks = [
        make_chunk("repo_b", "beta.py", "render_beta_view", "", "function", 1, 10,
                   "def render_beta_view(): return 'beta'"),
    ]
    store.replace_repository_chunks("repo_a", repo_a_chunks)
    store.replace_repository_chunks("repo_b", repo_b_chunks)

    # Search repo_a for beta token should find nothing
    results_a = store.search("repo_a", "beta", top_k=3)
    assert len(results_a) == 0

    # Search repo_b for beta token should find 1 result
    results_b = store.search("repo_b", "beta", top_k=3)
    assert len(results_b) == 1
    assert results_b[0]["metadata"]["symbol"] == "render_beta_view"


def test_bm25_reindexing_behavior(tmp_path: Path) -> None:
    store = LocalBM25Store(tmp_path / "bm25")
    initial_chunks = [
        make_chunk("repo1", "old_file.py", "obsolete_metric", "", "function", 1, 10, "def obsolete_metric(): pass"),
        make_chunk("repo1", "keep_file.py", "stable_worker", "", "function", 1, 10, "def stable_worker(): pass"),
    ]
    store.replace_repository_chunks("repo1", initial_chunks)
    assert store.count("repo1") == 2

    # Reindex with new single chunk
    updated_chunks = [
        make_chunk("repo1", "new_file.py", "modern_processor", "", "function", 1, 10, "def modern_processor(): pass"),
    ]
    store.replace_repository_chunks("repo1", updated_chunks)
    assert store.count("repo1") == 1

    # Old obsolete function token must not be searchable anymore
    assert len(store.search("repo1", "obsolete", top_k=3)) == 0
    # New function token must be searchable
    assert len(store.search("repo1", "modern", top_k=3)) == 1


def test_rrf_fusion_ordering() -> None:
    # Item A is rank 1 in semantic, rank 3 in BM25
    item_a = {"chunk_id": "chunk_A", "source_code": "code A", "metadata": {"symbol": "A"}}
    # Item B is rank 2 in semantic, rank 1 in BM25 -> strong cross-modal support!
    item_b = {"chunk_id": "chunk_B", "source_code": "code B", "metadata": {"symbol": "B"}}
    # Item C is rank 3 in semantic only
    item_c = {"chunk_id": "chunk_C", "source_code": "code C", "metadata": {"symbol": "C"}}
    # Item D is rank 2 in BM25 only
    item_d = {"chunk_id": "chunk_D", "source_code": "code D", "metadata": {"symbol": "D"}}

    semantic_ranked = [item_a, item_b, item_c]
    bm25_ranked = [item_b, item_d, item_a]

    fused = reciprocal_rank_fusion([semantic_ranked, bm25_ranked], rrf_k=60)
    assert len(fused) == 4

    # B has rank 2 in semantic (1/62) + rank 1 in BM25 (1/61) = 0.016129 + 0.016393 = 0.032522
    # A has rank 1 in semantic (1/61) + rank 3 in BM25 (1/63) = 0.016393 + 0.015873 = 0.032266
    # Therefore B must rank #1!
    assert fused[0]["chunk_id"] == "chunk_B"
    assert fused[1]["chunk_id"] == "chunk_A"
    assert fused[0]["rrf_score"] > fused[1]["rrf_score"]


def test_rrf_duplicate_candidate_handling() -> None:
    item = {"chunk_id": "duplicate_id", "source_code": "code", "metadata": {"symbol": "dup"}}
    # Both lists contain the exact same item
    fused = reciprocal_rank_fusion([[item], [item]], rrf_k=60)
    # Must contain item exactly once
    assert len(fused) == 1
    # Score should be 1/(60+1) + 1/(60+1) = 2/61
    expected_score = (1.0 / 61.0) + (1.0 / 61.0)
    assert abs(fused[0]["rrf_score"] - expected_score) < 1e-6


def test_diversity_filtering_after_fusion(tmp_path: Path) -> None:
    # Overlapping class (lines 10-60) and method (lines 20-35)
    class_chunk = {
        "chunk_id": "cls",
        "source_code": "class Service:\n    def run(self): pass",
        "metadata": {
            "file_path": "service.py",
            "symbol": "Service",
            "parent_symbol": "",
            "chunk_type": "class",
            "start_line": 10,
            "end_line": 60,
        },
    }
    method_chunk = {
        "chunk_id": "meth",
        "source_code": "def run(self): pass",
        "metadata": {
            "file_path": "service.py",
            "symbol": "run",
            "parent_symbol": "Service",
            "chunk_type": "method",
            "start_line": 20,
            "end_line": 35,
        },
    }
    other_chunk = {
        "chunk_id": "other",
        "source_code": "def helper(): pass",
        "metadata": {
            "file_path": "utils.py",
            "symbol": "helper",
            "parent_symbol": "",
            "chunk_type": "function",
            "start_line": 1,
            "end_line": 10,
        },
    }

    # Semantic returned method first; BM25 returned class first
    semantic = [method_chunk, other_chunk]
    bm25 = [class_chunk, method_chunk]

    fused = reciprocal_rank_fusion([semantic, bm25], rrf_k=60)
    assert len(fused) == 3

    # Diversity selection filters out overlapping class when method is present
    selected = LocalQAService.select_diverse_chunks(fused, target_k=2)
    assert len(selected) == 2
    # Distinct files represented
    files = {item["metadata"]["file_path"] for item in selected}
    assert "service.py" in files
    assert "utils.py" in files


def test_hybrid_retrieval_modes(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "service.py").write_text(
        "import os\n\ndef scan_repository(path):\n    return True\n\nclass LocalQAService:\n    pass\n",
        encoding="utf-8",
    )

    embedder = DeterministicEmbedder()
    store = LocalChromaStore(tmp_path / "vectors")
    bm25 = LocalBM25Store(tmp_path / "bm25")
    indexer = RepositoryIndexingService(embedder=embedder, vector_store=store, bm25_store=bm25)
    indexer.index_repository(str(repo))

    ollama = StubOllama()
    qa = LocalQAService(embedder=embedder, vector_store=store, bm25_store=bm25, ollama=ollama)

    # 1. Semantic mode
    res_sem = qa.ask(str(repo), "scan_repository", top_k=3, retrieval_mode="semantic")
    assert res_sem["retrieval_mode"] == "semantic"
    assert res_sem["retrieved_chunks"] > 0

    # 2. BM25 mode
    res_bm25 = qa.ask(str(repo), "scan_repository", top_k=3, retrieval_mode="bm25")
    assert res_bm25["retrieval_mode"] == "bm25"
    assert any(s["symbol"] == "scan_repository" for s in res_bm25["sources"])

    # 3. Hybrid mode
    res_hybrid = qa.ask(str(repo), "scan_repository", top_k=3, retrieval_mode="hybrid")
    assert res_hybrid["retrieval_mode"] == "hybrid"
    assert any(s["symbol"] == "scan_repository" for s in res_hybrid["sources"])


def test_chat_api_supports_retrieval_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("def hello(): return 'world'\n", encoding="utf-8")

    embedder = DeterministicEmbedder()
    store = LocalChromaStore(tmp_path / "vectors")
    bm25 = LocalBM25Store(tmp_path / "bm25")
    RepositoryIndexingService(embedder=embedder, vector_store=store, bm25_store=bm25).index_repository(str(repo))
    qa = LocalQAService(embedder=embedder, vector_store=store, bm25_store=bm25, ollama=StubOllama())

    import app.api.routes as routes
    monkeypatch.setattr(routes, "LocalQAService", lambda: qa)

    client = TestClient(app)
    response = client.post("/api/chat", json={
        "path": str(repo),
        "question": "What does hello do?",
        "retrieval_mode": "hybrid",
    })

    assert response.status_code == 200
    payload = response.json()
    assert payload["retrieval_mode"] == "hybrid"
    assert payload["retrieved_chunks"] > 0
    assert payload["sources"]
