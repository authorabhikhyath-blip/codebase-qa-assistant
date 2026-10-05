# Codebase QA Assistant

## Purpose and architecture

Build a local-first application for asking grounded questions about Python repositories. The Next.js and TypeScript frontend calls a modular FastAPI backend. Repository source, embeddings, indexes, and inference stay on the user's machine; core functionality must not depend on a cloud database or AI service.

## Technology choices

- Frontend: Next.js App Router, TypeScript, Tailwind CSS, with shadcn/ui-compatible conventions.
- Backend: Python, FastAPI, and Pydantic under `backend/app` (API, core, models, and services).
- Implemented local pipeline: repository scanning, Tree-sitter Python parsing/chunking, FastEmbed embeddings, persistent ChromaDB, local BM25 lexical store, Reciprocal Rank Fusion (RRF), diversity/overlap filtering, local cross-encoder reranking, Ollama generation (`qwen2.5-coder:3b`), and secure source navigation.
- Evaluated and verified: reproducible 14-question benchmark across 8 question categories comparing semantic, BM25, hybrid RRF, and hybrid + rerank modes.
- Supabase may be considered only as an optional local service for metadata; it must not be required for Code QA.

## Privacy and cost

- Never send repository paths or source code to cloud AI APIs.
- Do not add cloud LLM APIs or mandatory hosted vector databases.
- Prefer open-source dependencies, local inference, and free development tools; add no paid services.
- Do not download large models during setup or routine checks. Model downloads require an explicit user decision as part of model setup.
- Keep credentials, local indexes, model caches, and machine-specific state out of version control.

## Coding conventions

- Keep frontend and backend responsibilities separate and modules focused.
- Use TypeScript types and Python type hints at application interfaces.
- Read service URLs and settings from environment variables with safe local defaults; document them.
- Handle errors explicitly. Do not fabricate or silently substitute functionality.
- Keep changes scoped. Explain architectural deviations in project documentation.
- Python is the only supported repository language until a language-specific parser milestone is approved.

## Testing and development workflow

- Add meaningful tests for backend routes and services as they are implemented.
- Run checks relevant to changed code and report commands and results accurately.
- Run frontend and backend independently using the documented commands.
- Never claim a service, model, or feature was exercised unless it was.
- Before handoff, inspect `git status`, check ignored runtime artifacts, and ensure no secrets or generated data are staged.

## Milestone status and roadmap

1. Foundation, health endpoint, and local development docs: complete.
2. Safe local Python repository selection and file discovery: complete.
3. Tree-sitter parsing/chunking, local embeddings, and Chroma indexing: complete.
4. Semantic retrieval, local Ollama answers, and source references: complete.
5. BM25/hybrid retrieval and local reranking: complete.
6. Evaluation system, repository intelligence, source navigation, and UI polish: complete.
7. Next milestone recommendation: Multi-turn conversational memory, multi-repository management, and exportable benchmark reports.

## Scope and accuracy rules

- Do not fabricate features, test results, source references, model availability, or answer quality.
- Do not present placeholder or mock RAG behavior as working functionality.
- Do not replace the Next.js + FastAPI local-first architecture without a concrete engineering reason documented for review.
- Keep milestone scope explicit. Do not add multi-language parsing, authentication, Supabase, cloud services, or unrequested RAG components.
