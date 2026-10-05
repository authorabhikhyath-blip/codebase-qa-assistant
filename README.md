# Codebase QA Assistant

A local-first developer tool for exploring Python repositories. A Next.js frontend sends requests to a modular FastAPI backend. Repository scanning, parsing, embeddings, vector storage, retrieval, and inference run locally; repository paths and source are not sent to hosted AI or vector services.

## Architecture

```text
Browser (Next.js / TypeScript)
   ↓ local HTTP
FastAPI
   ├── repository scan and index jobs
   ├── Tree-sitter Python parsing and AST-aware chunks
   ├── FastEmbed local embeddings
   ├── persistent local ChromaDB
   └── semantic retrieval and local Ollama generation
```

Indexing jobs run in the backend process and expose pollable progress. Job status is in memory and is lost on backend restart; the Chroma index persists locally. Re-indexing replaces prior chunks for the same canonical repository path. Python is the only implemented parser.

## Requirements

- Node.js 20.9+ and pnpm (recommended) or npm.
- Python 3.11+ and pip.
- Ollama is needed for local answer generation. It is not needed for backend tests or scanning/indexing.
- No paid account, cloud AI API, hosted vector database, or database service is required.

## Start the frontend

From the repository root:

```powershell
cd frontend
pnpm install --frozen-lockfile
Copy-Item .env.example .env.local
pnpm dev
```

Open http://localhost:3000. Set `NEXT_PUBLIC_API_BASE_URL` in `frontend/.env.local` if FastAPI is not at its default `http://localhost:8000`. The browser cannot grant the backend filesystem access; enter a repository path that the backend process itself can read.

## Start the backend

From the repository root:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --app-dir .
```

The backend health endpoint is `GET /health`. The UI scans with `POST /api/repositories/scan`, starts local indexing with `POST /api/repositories/index`, polls `GET /api/repositories/index/{job_id}`, and asks questions with `POST /api/chat` using `{"path":"C:\\path\\to\\repository","question":"How does authentication work?"}`. `GET /api/ollama/status` reports local Ollama/model readiness.

Run backend tests from `backend`:

```powershell
python -m pytest
```

## Local models and configuration

Backend settings use the `CODEQA_` prefix, load `.env` from the backend working directory, and default to local storage and loopback services.

| Variable | Default | Purpose |
| --- | --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | FastAPI URL used by the browser |
| `CODEQA_CHROMA_DATA_DIR` | `backend/data/chroma` | Persistent local vector index |
| `CODEQA_EMBEDDING_CACHE_DIR` | `backend/data/models` | Local embedding model cache |
| `CODEQA_EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | FastEmbed model run locally via ONNX Runtime |
| `CODEQA_OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Local Ollama address; non-loopback URLs are rejected |
| `CODEQA_OLLAMA_MODEL` | `qwen2.5-coder:3b` | Local Ollama model name |
| `CODEQA_RETRIEVAL_TOP_K` | `5` | Number of retrieved chunks per question |

The first indexing operation downloads the configured FastEmbed model to the local cache (about 67 MB for the default model). Model downloads do not occur during dependency installation or tests. With a populated cache, `HF_HUB_OFFLINE=1` can prevent FastEmbed from checking online sources.

Install Ollama from [ollama.com/download](https://ollama.com/download), start its local service, and fetch the default model when ready:

```powershell
ollama pull qwen2.5-coder:3b
```

The default quantized model is about 1.9 GB. Ollama is optional for scanning and indexing. Without a running local server/model, the readiness endpoint reports the issue and chat returns a setup error. Configure only a loopback Ollama URL; hosted Ollama endpoints are rejected.

## Current project status

Implemented: repository scanning, Python Tree-sitter parsing and AST-aware chunking, local FastEmbed embeddings, persistent per-repository Chroma storage, background indexing progress, semantic retrieval, local Ollama generation, source metadata, and current-session chat history.

Not implemented: BM25/hybrid retrieval, reranking, additional languages, Supabase, authentication, and deployment infrastructure. Generated answer quality has not been verified against a suitable local coding model and representative repositories; retrieval and citations need hands-on review before relying on answer quality.

## Planned next milestones

1. Run the application with the intended local model on representative repositories and review retrieval, grounding, and source references.
2. Use that review to guide BM25/hybrid retrieval and local reranking.
3. Improve repository overview and developer workflows, then polish the interface.

RAG functionality is implemented incrementally; planned work above is not claimed as completed.
