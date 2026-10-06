# Codebase QA Assistant — Technical Architecture Specification

## 1. System Overview

Codebase QA Assistant is a local-first retrieval-augmented generation application designed for deep, grounded code questioning without cloud exposure.

The application adheres to three strict architectural invariants:
1. **Local Isolation**: Repository source, embeddings, indices, and inference must never leave the user's workstation.
2. **AST-Aware Representation**: Code is parsed into structural entities (functions, classes, methods, module preambles) rather than arbitrary line slices.
3. **Multi-Stage Grounding**: Retrieved candidates undergo hybrid fusion (sparse + dense), redundancy filtering, and reranking before being formatted into strict evidence prompts.

---

## 2. Component Architecture

### 2.1 Scanner & AST Parsing (`backend/app/services/repository_ingestion.py`, `python_parser.py`)
- Discovers Python source files without traversing generated/cache directories such as `.git`, `.pnpm-store`, `node_modules`, `.venv`, and `__pycache__`; directory and file symlinks are not followed.
- Uses `tree_sitter_python` to build syntax trees.
- Extracts:
  - `class_definition` (records class name, line span, docstring)
  - `function_definition` (records function/method name, parent symbol, parameters)
  - `module_preamble` (groups contiguous imports, module constants, and global assignments into a single preamble chunk to eliminate single-line import noise).

### 2.2 Dual Indexing Layer
1. **Dense Vector Store (`backend/app/services/vector_store.py`)**:
   - Uses `fastembed` with `BAAI/bge-small-en-v1.5` (384-dimensional embeddings via ONNX Runtime).
   - Stores chunk embeddings, source snippets, and rich symbol metadata in persistent ChromaDB collections.
2. **Sparse Lexical Store (`backend/app/services/bm25.py`)**:
   - Custom in-memory and disk-persisted Okapi BM25 implementation ($k_1=1.5, b=0.75$).
   - Tokenizer splits snake_case and camelCase identifiers to ensure sub-token and whole-token matches.

### 2.3 Retrieval & Hybrid Fusion (`backend/app/services/hybrid.py` & `qa.py`)
- Focused questions retrieve a modest candidate set from ChromaDB and BM25. Broad architecture, interaction, lifecycle, and multi-component questions expand candidate retrieval and, when named code components appear in the question, add focused BM25 searches for those names. The existing RRF and reranking pipeline combines these with general results, then prioritizes distinct files before filling remaining context slots.
- Combines candidate ranks via **Reciprocal Rank Fusion (RRF)**:
  $$RRF(d) = \sum_{m \in \{\text{dense}, \text{sparse}\}} \frac{1}{k_{\text{rrf}} + \text{rank}_m(d)}$$
  Default constant: $k_{\text{rrf}} = 60$.

### 2.4 Diversity & Overlap Filter (`backend/app/services/qa.py`)
- Prevents retrieval duplication between parent scopes and child methods.
- Broad architecture and relationship questions cap early results at two chunks per file in addition to the overlap check, so the context can represent multiple components.
- If two candidate chunks from the same file overlap by $\ge 30\%$ of the smaller chunk's span, the lower-ranked chunk is discarded until target top-$k$ is filled.

### 2.5 Local Cross-Reranker (`backend/app/services/reranker.py`)
- Cross-scores surviving candidates:
  $$\text{Score} = w_{\text{ident}} \cdot S_{\text{ident}} + w_{\text{cov}} \cdot S_{\text{cov}} + w_{\text{rrf}} \cdot S_{\text{norm\_rrf}}$$
  - $S_{\text{ident}}$: Boosts matches on symbol name, parent class name, or file stem.
  - $S_{\text{cov}}$: Proportion of query tokens present in the chunk body + exact phrase bonus.
  - $S_{\text{norm\_rrf}}$: Normalized RRF score.

### 2.6 Local Inference (`backend/app/services/ollama.py`)
- Connects strictly to loopback `http://127.0.0.1:11434`.
- Instructs `qwen2.5-coder:3b` with a grounding system prompt:
  - Retrieved source evidence is the source of truth; answers distinguish code behavior from inference and connect files for architecture questions.
  - Must explicitly state when context is insufficient, avoid claims about files it has not seen, and cite code claims in exact `[file_path:start-end]` format.
- Response length is adapted to the question rather than a fixed answer template.
- The generation prompt distinguishes embedding, base search, fusion, and reranking so ranking weights are not described as search weights.

### 2.7 Frontend workspace
- The workspace centers the conversation, with repository selection and compact index statistics in a sidebar/header.
- The API boundary validates response JSON at runtime before typed chat answers, citations, overview data, and source snippets reach UI components.
- Source navigation continues to use the backend's repository-root and symlink validation before displaying snippets.

### 2.7 Security & Source Navigation (`backend/app/services/overview.py`)
- Canonical path resolution prevents directory traversal attacks (`../`).
- Rejects paths containing null bytes (`\0`).
- Validates that symlinks do not target paths outside the canonical repository root.
- Safely slices source files for line-level preview.
