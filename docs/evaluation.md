# Codebase QA Assistant — Internal Evaluation Report

> [!NOTE]
> **Disclaimer**: This is an internal project evaluation conducted on the Codebase QA Assistant codebase.
> It does not claim industry-wide SWE-bench or HumanEval-RAG scores.

- **Evaluated Corpus**: `backend/app`
- **Total Questions**: 14
- **Timestamp**: 2026-10-05T17:32:51.264186+00:00
- **Evaluated Modes**: semantic, bm25, hybrid, hybrid_rerank

## 1. Summary Metrics Comparison

| Mode | File Recall | Symbol Recall | Evidence Recall | Grounded Answer Rate |
| :--- | :---: | :---: | :---: | :---: |
| **semantic** | 92.9% | 100.0% | 92.9% | 92.9% |
| **bm25** | 100.0% | 100.0% | 100.0% | 100.0% |
| **hybrid** | 100.0% | 100.0% | 100.0% | 100.0% |
| **hybrid_rerank** | 100.0% | 100.0% | 100.0% | 100.0% |

## 2. Per-Question Results Matrix

| ID | Category | Question | Semantic | BM25 | Hybrid RRF | Hybrid+Rerank | Expected Evidence |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `q01_exact_id_rrf_k` | exact_identifier | Where is rrf_k configured in settings? | PASS (Full) | PASS (Full) | PASS (Full) | PASS (Full) | `core/config.py` / `rrf_k,Settings` |
| `q02_exact_id_retrieval_top_k` | exact_identifier | What is retrieval_top_k in the settings configuration? | PARTIAL (Symbol) | PASS (Full) | PASS (Full) | PASS (Full) | `core/config.py` / `retrieval_top_k` |
| `q03_func_reciprocal_rank_fusion` | function | What does reciprocal_rank_fusion do in the hybrid retrieval service? | PASS (Full) | PASS (Full) | PASS (Full) | PASS (Full) | `services/hybrid.py` / `reciprocal_rank_fusion` |
| `q04_func_tokenize_code` | function | How does tokenize_code construct search tokens from source text? | PASS (Full) | PASS (Full) | PASS (Full) | PASS (Full) | `services/bm25.py` / `tokenize_code` |
| `q05_class_local_reranker` | class | What methods and attributes does LocalReranker have? | PASS (Full) | PASS (Full) | PASS (Full) | PASS (Full) | `services/reranker.py` / `LocalReranker` |
| `q06_class_overview_response` | class | What fields are defined on the RepositoryOverviewResponse model? | PASS (Full) | PASS (Full) | PASS (Full) | PASS (Full) | `models/repository.py` / `RepositoryOverviewResponse` |
| `q07_arch_hybrid_fusion` | architecture | How are hybrid retrieval results fused and filtered in LocalQAService? | PASS (Full) | PASS (Full) | PASS (Full) | PASS (Full) | `services/qa.py,services/hybrid.py` / `LocalQAService,reciprocal_rank_fusion` |
| `q08_arch_indexing_pipeline` | architecture | How does the indexing service persist chunks into ChromaDB and BM25? | PASS (Full) | PASS (Full) | PASS (Full) | PASS (Full) | `services/indexing.py` / `RepositoryIndexingService,index_repository` |
| `q09_cross_chat_request_flow` | cross_component | How does the chat route pass retrieval mode to LocalQAService? | PASS (Full) | PASS (Full) | PASS (Full) | PASS (Full) | `api/routes.py,services/qa.py` / `chat,LocalQAService` |
| `q10_cross_overview_indexing` | cross_component | How does RepositoryOverviewResponse connect with save_repository_overview in indexing? | PASS (Full) | PASS (Full) | PASS (Full) | PASS (Full) | `services/overview.py,services/indexing.py` / `save_repository_overview,RepositoryIndexingService` |
| `q11_detail_source_traversal_prevention` | implementation_detail | How does get_repository_source_snippet prevent directory traversal and symlink attacks? | PASS (Full) | PASS (Full) | PASS (Full) | PASS (Full) | `services/overview.py` / `get_repository_source_snippet` |
| `q12_detail_select_diverse_chunks` | implementation_detail | How does select_diverse_chunks prevent overlapping code chunks from duplicating evidence? | PASS (Full) | PASS (Full) | PASS (Full) | PASS (Full) | `services/qa.py` / `select_diverse_chunks` |
| `q13_loc_ollama_client` | location | Where is LocalOllamaService implemented and how does it query Ollama? | PASS (Full) | PASS (Full) | PASS (Full) | PASS (Full) | `services/ollama.py` / `LocalOllamaService,generate` |
| `q14_expl_rrf_scoring` | explanation | Explain how reciprocal rank fusion combines rankings using rrf_k in reciprocal_rank_fusion. | PASS (Full) | PASS (Full) | PASS (Full) | PASS (Full) | `services/hybrid.py` / `reciprocal_rank_fusion` |

## 3. Failure & Evidence Inspection

Detailed inspection of failure modes and retrieved chunks per question:

### `q01_exact_id_rrf_k`: Where is rrf_k configured in settings?
- **Category**: `exact_identifier`
- **Expected Files**: `core/config.py`
- **Expected Symbols**: `rrf_k, Settings`

| Mode | File Found | Symbol Found | Evidence Found | Retrieved Files / Symbols | Answer Preview |
| :--- | :---: | :---: | :---: | :--- | :--- |
| **semantic** | True | True | True | `core/config.py, core/config.py, services/qa.py` / `Settings, config, __init__` |  |
| **bm25** | True | True | True | `services/qa.py, services/hybrid.py, core/config.py` / `LocalQAService, reciprocal_rank_fusion, Settings` |  |
| **hybrid** | True | True | True | `core/config.py, services/qa.py, core/config.py` / `Settings, LocalQAService, config` |  |
| **hybrid_rerank** | True | True | True | `core/config.py, services/qa.py, services/hybrid.py` / `Settings, LocalQAService, reciprocal_rank_fusion` | rrf_k is configured in the `Settings` class, which is defined in `core/config.py`. |

### `q02_exact_id_retrieval_top_k`: What is retrieval_top_k in the settings configuration?
- **Category**: `exact_identifier`
- **Expected Files**: `core/config.py`
- **Expected Symbols**: `retrieval_top_k`

| Mode | File Found | Symbol Found | Evidence Found | Retrieved Files / Symbols | Answer Preview |
| :--- | :---: | :---: | :---: | :--- | :--- |
| **semantic** | False | True | False | `services/qa.py, services/bm25.py, services/qa.py` / `select_diverse_chunks, search, ask` |  |
| **bm25** | True | True | True | `services/qa.py, core/config.py, models/rag.py` / `ask, Settings, ChatRequest` |  |
| **hybrid** | True | True | True | `services/qa.py, services/qa.py, services/bm25.py` / `select_diverse_chunks, ask, search` |  |
| **hybrid_rerank** | True | True | True | `core/config.py, services/qa.py, api/routes.py` / `Settings, ask, chat` | The value of `retrieval_top_k` in the settings configuration is 5. This can be seen in the `Settings` class definition in `core/config.py`, where `retrieval_top... |

### `q03_func_reciprocal_rank_fusion`: What does reciprocal_rank_fusion do in the hybrid retrieval service?
- **Category**: `function`
- **Expected Files**: `services/hybrid.py`
- **Expected Symbols**: `reciprocal_rank_fusion`

| Mode | File Found | Symbol Found | Evidence Found | Retrieved Files / Symbols | Answer Preview |
| :--- | :---: | :---: | :---: | :--- | :--- |
| **semantic** | True | True | True | `services/hybrid.py, services/qa.py, services/reranker.py` / `reciprocal_rank_fusion, ask, rerank` |  |
| **bm25** | True | True | True | `services/qa.py, services/hybrid.py, services/qa.py` / `ask, reciprocal_rank_fusion, qa` |  |
| **hybrid** | True | True | True | `services/hybrid.py, services/qa.py, services/reranker.py` / `reciprocal_rank_fusion, ask, rerank` |  |
| **hybrid_rerank** | True | True | True | `services/hybrid.py, services/qa.py, services/qa.py` / `reciprocal_rank_fusion, LocalQAService, qa` | Reciprocal Rank Fusion (RRF) is a technique used in hybrid retrieval services to combine multiple ranked candidate lists into a single ranking. The function `re... |

### `q04_func_tokenize_code`: How does tokenize_code construct search tokens from source text?
- **Category**: `function`
- **Expected Files**: `services/bm25.py`
- **Expected Symbols**: `tokenize_code`

| Mode | File Found | Symbol Found | Evidence Found | Retrieved Files / Symbols | Answer Preview |
| :--- | :---: | :---: | :---: | :--- | :--- |
| **semantic** | True | True | True | `services/bm25.py, services/reranker.py, services/vector_store.py` / `tokenize_code, _extract_query_terms, search` |  |
| **bm25** | True | True | True | `services/bm25.py, services/bm25.py, services/bm25.py` / `tokenize_code, search, replace_repository_chunks` |  |
| **hybrid** | True | True | True | `services/bm25.py, services/reranker.py, services/bm25.py` / `tokenize_code, _extract_query_terms, search` |  |
| **hybrid_rerank** | True | True | True | `services/bm25.py, services/bm25.py, services/vector_store.py` / `tokenize_code, search, search` | To answer the question "How does tokenize_code construct search tokens from source text?", I will analyze the provided code snippet from `services/bm25.py`.  Th... |

### `q05_class_local_reranker`: What methods and attributes does LocalReranker have?
- **Category**: `class`
- **Expected Files**: `services/reranker.py`
- **Expected Symbols**: `LocalReranker`

| Mode | File Found | Symbol Found | Evidence Found | Retrieved Files / Symbols | Answer Preview |
| :--- | :---: | :---: | :---: | :--- | :--- |
| **semantic** | True | True | True | `services/qa.py, services/reranker.py, services/vector_store.py` / `LocalQAService, LocalReranker, LocalChromaStore` |  |
| **bm25** | True | True | True | `services/reranker.py, services/reranker.py, services/qa.py` / `__init__, _extract_query_terms, __init__` |  |
| **hybrid** | True | True | True | `services/qa.py, services/reranker.py, services/reranker.py` / `LocalQAService, __init__, _extract_query_terms` |  |
| **hybrid_rerank** | True | True | True | `services/reranker.py, services/reranker.py, services/qa.py` / `LocalReranker, reranker, LocalQAService` | Based on the provided code context, the `LocalReranker` class has the following methods and attributes:  ### Methods: 1. **`__init__`**: Initializes the reranke... |

### `q06_class_overview_response`: What fields are defined on the RepositoryOverviewResponse model?
- **Category**: `class`
- **Expected Files**: `models/repository.py`
- **Expected Symbols**: `RepositoryOverviewResponse`

| Mode | File Found | Symbol Found | Evidence Found | Retrieved Files / Symbols | Answer Preview |
| :--- | :---: | :---: | :---: | :--- | :--- |
| **semantic** | True | True | True | `models/repository.py, models/repository.py, models/repository.py` / `RepositoryOverviewResponse, RepositoryScanRequest, RepositoryScanResponse` |  |
| **bm25** | True | True | True | `api/routes.py, models/repository.py, api/routes.py` / `repository_overview, RepositoryOverviewResponse, routes` |  |
| **hybrid** | True | True | True | `models/repository.py, api/routes.py, models/repository.py` / `RepositoryOverviewResponse, repository_overview, RepositoryScanRequest` |  |
| **hybrid_rerank** | True | True | True | `models/repository.py, models/repository.py, models/repository.py` / `RepositoryOverviewResponse, RepositoryScanResponse, SourceCodeResponse` | Based on the provided code snippets, the `RepositoryOverviewResponse` model is defined in the `models/repository.py` file. The fields defined on this model are:... |

### `q07_arch_hybrid_fusion`: How are hybrid retrieval results fused and filtered in LocalQAService?
- **Category**: `architecture`
- **Expected Files**: `services/qa.py, services/hybrid.py`
- **Expected Symbols**: `LocalQAService, reciprocal_rank_fusion`

| Mode | File Found | Symbol Found | Evidence Found | Retrieved Files / Symbols | Answer Preview |
| :--- | :---: | :---: | :---: | :--- | :--- |
| **semantic** | True | True | True | `services/qa.py, services/qa.py, services/vector_store.py` / `ask, select_diverse_chunks, search` |  |
| **bm25** | True | True | True | `services/qa.py, services/qa.py, api/routes.py` / `ask, __init__, chat` |  |
| **hybrid** | True | True | True | `services/qa.py, services/qa.py, services/qa.py` / `ask, select_diverse_chunks, __init__` |  |
| **hybrid_rerank** | True | True | True | `services/qa.py, services/qa.py, services/hybrid.py` / `LocalQAService, qa, reciprocal_rank_fusion` | Hybrid retrieval results are fused and filtered in the `LocalQAService` class by the `ask` method. The `ask` method first determines the retrieval mode (e.g., "... |

### `q08_arch_indexing_pipeline`: How does the indexing service persist chunks into ChromaDB and BM25?
- **Category**: `architecture`
- **Expected Files**: `services/indexing.py`
- **Expected Symbols**: `RepositoryIndexingService, index_repository`

| Mode | File Found | Symbol Found | Evidence Found | Retrieved Files / Symbols | Answer Preview |
| :--- | :---: | :---: | :---: | :--- | :--- |
| **semantic** | True | True | True | `services/indexing.py, services/bm25.py, services/vector_store.py` / `RepositoryIndexingService, LocalBM25Store, LocalChromaStore` |  |
| **bm25** | True | True | True | `services/qa.py, services/indexing.py, services/indexing.py` / `ask, __init__, indexing` |  |
| **hybrid** | True | True | True | `services/indexing.py, services/qa.py, services/bm25.py` / `RepositoryIndexingService, ask, LocalBM25Store` |  |
| **hybrid_rerank** | True | True | True | `services/indexing.py, services/bm25.py, services/indexing.py` / `indexing, bm25, RepositoryIndexingService` | The indexing service persists chunks into ChromaDB and BM25 by using the `LocalChromaStore` and `LocalBM25Store` classes respectively. Here's how it works:  1. ... |

### `q09_cross_chat_request_flow`: How does the chat route pass retrieval mode to LocalQAService?
- **Category**: `cross_component`
- **Expected Files**: `api/routes.py, services/qa.py`
- **Expected Symbols**: `chat, LocalQAService`

| Mode | File Found | Symbol Found | Evidence Found | Retrieved Files / Symbols | Answer Preview |
| :--- | :---: | :---: | :---: | :--- | :--- |
| **semantic** | True | True | True | `api/routes.py, services/qa.py, models/rag.py` / `chat, LocalQAService, ChatRequest` |  |
| **bm25** | True | True | True | `api/routes.py, services/qa.py, models/rag.py` / `chat, ask, ChatResponse` |  |
| **hybrid** | True | True | True | `api/routes.py, services/qa.py, models/rag.py` / `chat, LocalQAService, ChatRequest` |  |
| **hybrid_rerank** | True | True | True | `services/qa.py, api/routes.py, services/qa.py` / `LocalQAService, chat, qa` | The chat route passes the retrieval mode to LocalQAService by calling the `ask` method of the `LocalQAService` class with the `retrieval_mode` parameter. This p... |

### `q10_cross_overview_indexing`: How does RepositoryOverviewResponse connect with save_repository_overview in indexing?
- **Category**: `cross_component`
- **Expected Files**: `services/overview.py, services/indexing.py`
- **Expected Symbols**: `save_repository_overview, RepositoryIndexingService`

| Mode | File Found | Symbol Found | Evidence Found | Retrieved Files / Symbols | Answer Preview |
| :--- | :---: | :---: | :---: | :--- | :--- |
| **semantic** | True | True | True | `api/routes.py, models/repository.py, services/overview.py` / `repository_overview, RepositoryOverviewResponse, get_repository_overview` |  |
| **bm25** | True | True | True | `services/overview.py, api/routes.py, services/indexing.py` / `save_repository_overview, repository_overview, indexing` |  |
| **hybrid** | True | True | True | `api/routes.py, services/overview.py, models/repository.py` / `repository_overview, save_repository_overview, RepositoryOverviewResponse` |  |
| **hybrid_rerank** | True | True | True | `services/overview.py, models/repository.py, services/indexing.py` / `save_repository_overview, RepositoryOverviewResponse, indexing` | RepositoryOverviewResponse connects with save_repository_overview in indexing through the following mechanism:  1. In the `RepositoryIndexingService` class, the... |

### `q11_detail_source_traversal_prevention`: How does get_repository_source_snippet prevent directory traversal and symlink attacks?
- **Category**: `implementation_detail`
- **Expected Files**: `services/overview.py`
- **Expected Symbols**: `get_repository_source_snippet`

| Mode | File Found | Symbol Found | Evidence Found | Retrieved Files / Symbols | Answer Preview |
| :--- | :---: | :---: | :---: | :--- | :--- |
| **semantic** | True | True | True | `services/overview.py, services/repository_ingestion.py, api/routes.py` / `get_repository_source_snippet, scan_repository, repository_source` |  |
| **bm25** | True | True | True | `services/overview.py, api/routes.py, services/repository_ingestion.py` / `get_repository_source_snippet, repository_source, scan_repository` |  |
| **hybrid** | True | True | True | `services/overview.py, services/repository_ingestion.py, api/routes.py` / `get_repository_source_snippet, scan_repository, repository_source` |  |
| **hybrid_rerank** | True | True | True | `services/overview.py, services/repository_ingestion.py, api/routes.py` / `get_repository_source_snippet, scan_repository, repository_source` | The `get_repository_source_snippet` function in `services/overview.py` prevents directory traversal and symlink attacks by performing the following checks:  1. ... |

### `q12_detail_select_diverse_chunks`: How does select_diverse_chunks prevent overlapping code chunks from duplicating evidence?
- **Category**: `implementation_detail`
- **Expected Files**: `services/qa.py`
- **Expected Symbols**: `select_diverse_chunks`

| Mode | File Found | Symbol Found | Evidence Found | Retrieved Files / Symbols | Answer Preview |
| :--- | :---: | :---: | :---: | :--- | :--- |
| **semantic** | True | True | True | `services/qa.py, services/vector_store.py, services/reranker.py` / `select_diverse_chunks, replace_repository_chunks, LocalReranker` |  |
| **bm25** | True | True | True | `services/qa.py, services/qa.py, services/vector_store.py` / `select_diverse_chunks, ask, LocalChromaStore` |  |
| **hybrid** | True | True | True | `services/qa.py, services/vector_store.py, services/qa.py` / `select_diverse_chunks, replace_repository_chunks, ask` |  |
| **hybrid_rerank** | True | True | True | `services/qa.py, services/qa.py, services/vector_store.py` / `select_diverse_chunks, ask, LocalChromaStore` | The `select_diverse_chunks` method in the `LocalQAService` class prevents overlapping code chunks from duplicating evidence by checking for line overlap between... |

### `q13_loc_ollama_client`: Where is LocalOllamaService implemented and how does it query Ollama?
- **Category**: `location`
- **Expected Files**: `services/ollama.py`
- **Expected Symbols**: `LocalOllamaService, generate`

| Mode | File Found | Symbol Found | Evidence Found | Retrieved Files / Symbols | Answer Preview |
| :--- | :---: | :---: | :---: | :--- | :--- |
| **semantic** | True | True | True | `services/ollama.py, api/routes.py, services/ollama.py` / `LocalOllamaService, ollama_status, OllamaUnavailable` |  |
| **bm25** | True | True | True | `services/ollama.py, services/ollama.py, services/qa.py` / `__init__, status, LocalQAService` |  |
| **hybrid** | True | True | True | `services/ollama.py, services/qa.py, api/routes.py` / `LocalOllamaService, LocalQAService, ollama_status` |  |
| **hybrid_rerank** | True | True | True | `services/ollama.py, services/ollama.py, services/qa.py` / `LocalOllamaService, ollama, LocalQAService` | LocalOllamaService is implemented in the file `services/ollama.py` starting at line 15 and ending at line 72. It queries Ollama by making HTTP requests to the O... |

### `q14_expl_rrf_scoring`: Explain how reciprocal rank fusion combines rankings using rrf_k in reciprocal_rank_fusion.
- **Category**: `explanation`
- **Expected Files**: `services/hybrid.py`
- **Expected Symbols**: `reciprocal_rank_fusion`

| Mode | File Found | Symbol Found | Evidence Found | Retrieved Files / Symbols | Answer Preview |
| :--- | :---: | :---: | :---: | :--- | :--- |
| **semantic** | True | True | True | `services/hybrid.py, services/reranker.py, services/reranker.py` / `reciprocal_rank_fusion, rerank, score_candidate` |  |
| **bm25** | True | True | True | `services/hybrid.py, services/qa.py, services/qa.py` / `reciprocal_rank_fusion, ask, qa` |  |
| **hybrid** | True | True | True | `services/hybrid.py, services/reranker.py, services/qa.py` / `reciprocal_rank_fusion, rerank, ask` |  |
| **hybrid_rerank** | True | True | True | `services/hybrid.py, services/qa.py, services/qa.py` / `reciprocal_rank_fusion, ask, qa` | Reciprocal Rank Fusion (RRF) combines rankings using the formula:  \[ \text{score}(d) = \sum_{\text{rank}} \frac{1.0}{\text{rrf\_k} + \text{rank}} \]  where \( ... |
