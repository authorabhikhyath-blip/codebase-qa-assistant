"use client";

import { FormEvent, useEffect, useState } from "react";

type ScannedFile = { path: string; line_count: number };
type ScanResult = {
  repository_path: string;
  repository_name: string;
  python_file_count: number;
  total_line_count: number;
  total_discovered_files: number;
  discovered_files: ScannedFile[];
  scan_status: string;
};

type IndexJob = {
  job_id: string;
  repository_id: string;
  repository_name: string;
  repository_path: string;
  status: "queued" | "indexing" | "completed" | "failed";
  files_total: number;
  files_processed: number;
  files_indexed: number;
  chunks_total: number;
  chunks_indexed: number;
  syntax_error_files: number;
  warnings: string[];
  error?: string | null;
};

type RepositoryOverview = {
  repository_id: string;
  repository_name: string;
  repository_path: string;
  supported_languages: string[];
  files_count: number;
  lines_count: number;
  chunks_count: number;
  classes_count: number;
  functions_count: number;
  methods_count: number;
  modules_count: number;
  indexed_at: string;
  embedding_model: string;
  llm_model: string;
  default_retrieval_mode: string;
};

type Source = {
  file_path: string;
  symbol: string;
  parent_symbol?: string;
  chunk_type: string;
  start_line: number;
  end_line: number;
};

type SourceSnippet = {
  repository_id: string;
  file_path: string;
  start_line: number;
  end_line: number;
  total_lines: number;
  code?: string;
  content?: string;
};

type ChatEntry = {
  id: number;
  question: string;
  answer?: string;
  sources?: Source[];
  retrievalMode?: string;
  error?: string;
  loading: boolean;
};

type OllamaStatus = {
  available: boolean;
  model: string;
  model_available: boolean;
  detail: string;
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export function RepositoryScanner() {
  const [path, setPath] = useState("");
  const [result, setResult] = useState<ScanResult | null>(null);
  const [indexJob, setIndexJob] = useState<IndexJob | null>(null);
  const [overview, setOverview] = useState<RepositoryOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isScanning, setIsScanning] = useState(false);
  const [isIndexing, setIsIndexing] = useState(false);
  const [ollama, setOllama] = useState<OllamaStatus | null>(null);
  const [retrievalMode, setRetrievalMode] = useState<string>("hybrid_rerank");
  const [question, setQuestion] = useState("");
  const [chat, setChat] = useState<ChatEntry[]>([]);
  const [isAsking, setIsAsking] = useState(false);

  // Source snippet modal/drawer state
  const [selectedSource, setSelectedSource] = useState<Source | null>(null);
  const [sourceSnippet, setSourceSnippet] = useState<SourceSnippet | null>(null);
  const [loadingSnippet, setLoadingSnippet] = useState(false);
  const [snippetError, setSnippetError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/ollama/status`)
      .then(async (response) => {
        if (!response.ok) throw new Error("Could not check Ollama status.");
        setOllama((await response.json()) as OllamaStatus);
      })
      .catch(() =>
        setOllama({
          available: false,
          model: "local model",
          model_available: false,
          detail: "Could not reach the backend to check local Ollama.",
        })
      );
  }, []);

  async function fetchOverview(repoId: string) {
    try {
      const resp = await fetch(`${API_BASE_URL}/api/repositories/${repoId}/overview`);
      if (resp.ok) {
        const data = (await resp.json()) as RepositoryOverview;
        setOverview(data);
      }
    } catch {
      // overview endpoint is optional/fallback
    }
  }

  async function scan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setResult(null);
    setIndexJob(null);
    setOverview(null);
    setChat([]);
    setIsScanning(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/repositories/scan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: path.trim() }),
      });
      const data: ScanResult | { detail?: string } = await response.json();
      if (!response.ok)
        throw new Error("detail" in data && data.detail ? data.detail : `Repository scan failed (${response.status}).`);
      setResult(data as ScanResult);
    } catch (scanError) {
      setError(
        scanError instanceof Error ? scanError.message : "Could not scan the repository. Check that the backend is running."
      );
    } finally {
      setIsScanning(false);
    }
  }

  async function indexRepository() {
    if (!result) return;
    setError(null);
    setIsIndexing(true);
    setIndexJob(null);
    setOverview(null);
    setChat([]);
    try {
      const started = await fetch(`${API_BASE_URL}/api/repositories/index`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: result.repository_path }),
      });
      const initial: IndexJob | { detail?: string } = await started.json();
      if (!started.ok)
        throw new Error("detail" in initial && initial.detail ? initial.detail : `Indexing could not start (${started.status}).`);
      const job = initial as IndexJob;
      setIndexJob(job);

      for (;;) {
        const response = await fetch(`${API_BASE_URL}/api/repositories/index/${job.job_id}`, { cache: "no-store" });
        const update: IndexJob | { detail?: string } = await response.json();
        if (!response.ok) throw new Error("detail" in update && update.detail ? update.detail : "Could not read indexing status.");
        const current = update as IndexJob;
        setIndexJob(current);
        if (current.status === "completed" || current.status === "failed") {
          if (current.status === "failed") {
            setError(current.error || "Repository indexing failed.");
          } else {
            // Load repository overview
            await fetchOverview(current.repository_id);
          }
          break;
        }
        await new Promise((resolve) => window.setTimeout(resolve, 800));
      }
    } catch (indexError) {
      setError(indexError instanceof Error ? indexError.message : "Could not index the repository.");
    } finally {
      setIsIndexing(false);
    }
  }

  async function openSourceViewer(source: Source) {
    const repoId = indexJob?.repository_id || overview?.repository_id;
    if (!repoId) return;

    setSelectedSource(source);
    setLoadingSnippet(true);
    setSnippetError(null);
    setSourceSnippet(null);

    try {
      const url = `${API_BASE_URL}/api/repositories/${repoId}/source?file_path=${encodeURIComponent(
        source.file_path
      )}&start_line=${source.start_line}&end_line=${source.end_line}`;
      const resp = await fetch(url);
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.detail || `Failed to fetch source snippet (${resp.status})`);
      }
      setSourceSnippet(data as SourceSnippet);
    } catch (err) {
      setSnippetError(err instanceof Error ? err.message : "Could not load source snippet.");
    } finally {
      setLoadingSnippet(false);
    }
  }

  async function askQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!result || !question.trim()) return;
    const submittedQuestion = question.trim();
    const id = Date.now();
    setQuestion("");
    setIsAsking(true);
    setChat((entries) => [
      ...entries,
      { id, question: submittedQuestion, retrievalMode, loading: true },
    ]);
    try {
      const response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          path: result.repository_path,
          question: submittedQuestion,
          retrieval_mode: retrievalMode,
        }),
      });
      const data = (await response.json()) as { answer?: string; sources?: Source[]; detail?: string };
      if (!response.ok) throw new Error(data.detail || `Question failed (${response.status}).`);
      setChat((entries) =>
        entries.map((entry) =>
          entry.id === id
            ? {
                ...entry,
                answer: data.answer,
                sources: data.sources ?? [],
                loading: false,
              }
            : entry
        )
      );
    } catch (chatError) {
      setChat((entries) =>
        entries.map((entry) =>
          entry.id === id
            ? {
                ...entry,
                error: chatError instanceof Error ? chatError.message : "Could not get an answer.",
                loading: false,
              }
            : entry
        )
      );
    } finally {
      setIsAsking(false);
    }
  }

  const indexed = (indexJob?.status === "completed" && indexJob.chunks_indexed > 0) || overview !== null;

  return (
    <>
      {/* Privacy / Local-First Banner */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-emerald-900/60 bg-[#091515] px-4 py-3 text-xs text-emerald-300">
        <div className="flex items-center gap-2">
          <span className="inline-block h-2 w-2 rounded-full bg-emerald-400"></span>
          <span className="font-semibold uppercase tracking-wider text-emerald-200">Local / Offline AI</span>
          <span className="hidden text-emerald-400/80 sm:inline">—</span>
          <span className="text-emerald-400/90">
            Repository indexing, AST chunking, embeddings, and answer generation run entirely locally.
          </span>
        </div>
        <span className="font-mono text-[11px] text-emerald-500/80">No Cloud LLM · No Cloud Vector DB</span>
      </div>

      {/* Repository Section */}
      <section className="mt-4 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6">
        <div>
          <h2 className="text-base font-medium">Repository</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Enter a folder path available to this backend process. Repository files remain local.
          </p>
        </div>
        <form onSubmit={scan} className="mt-5 flex flex-col gap-3 sm:flex-row">
          <label htmlFor="repository-path" className="sr-only">
            Local repository path
          </label>
          <input
            id="repository-path"
            type="text"
            required
            value={path}
            onChange={(event) => setPath(event.target.value)}
            placeholder="C:\\Users\\you\\projects\\my-repository"
            className="min-w-0 flex-1 rounded-lg border border-[var(--border)] bg-[#0b111a] px-4 py-3 font-mono text-sm text-[var(--foreground)] outline-none placeholder:text-slate-600 focus:border-[var(--accent)]"
          />
          <button
            type="submit"
            disabled={isScanning || isIndexing || !path.trim()}
            className="rounded-lg bg-[var(--accent)] px-5 py-3 text-sm font-semibold text-[#0b1716] transition-opacity disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isScanning ? "Scanning…" : "Scan repository"}
          </button>
        </form>
        {isScanning && <p role="status" className="mt-4 text-sm text-[var(--muted)]">Scanning Python source files…</p>}
        {error && (
          <p role="alert" className="mt-4 rounded-lg border border-rose-900/70 bg-rose-950/30 px-4 py-3 text-sm text-rose-300">
            {error}
          </p>
        )}

        {result && (
          <div className="mt-6 border-t border-[var(--border)] pt-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <h3 className="text-lg font-medium">{result.repository_name}</h3>
                <p className="mt-1 break-all font-mono text-xs text-[var(--muted)]">{result.repository_path}</p>
              </div>
              <span className="rounded-full border border-emerald-900 bg-emerald-950/40 px-3 py-1 font-mono text-xs text-emerald-300">
                {indexJob?.status ?? result.scan_status}
              </span>
            </div>

            {/* Standard Stats */}
            <div className="mt-5 grid gap-3 sm:grid-cols-4">
              <Stat label="Python files" value={result.python_file_count} />
              <Stat label="Python lines" value={result.total_line_count} />
              <Stat label="Discovered files" value={result.total_discovered_files} />
              <Stat label="Indexed chunks" value={indexJob?.chunks_indexed ?? (overview?.chunks_count ?? 0)} />
            </div>

            {/* Repository Overview Intelligence Card */}
            {overview && (
              <div className="mt-5 rounded-lg border border-[var(--border)] bg-[#0c1420] p-4">
                <div className="flex items-center justify-between border-b border-[var(--border)] pb-2">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--accent)]">
                    AST Repository Overview
                  </h4>
                  <span className="font-mono text-[11px] text-[var(--muted)]">
                    Indexed {new Date(overview.indexed_at).toLocaleTimeString()}
                  </span>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-6">
                  <div className="rounded border border-[var(--border)] bg-[#070c14] p-2.5 text-center">
                    <span className="block font-mono text-lg font-bold text-slate-200">{overview.classes_count}</span>
                    <span className="text-[11px] text-[var(--muted)]">Classes</span>
                  </div>
                  <div className="rounded border border-[var(--border)] bg-[#070c14] p-2.5 text-center">
                    <span className="block font-mono text-lg font-bold text-slate-200">{overview.functions_count}</span>
                    <span className="text-[11px] text-[var(--muted)]">Functions</span>
                  </div>
                  <div className="rounded border border-[var(--border)] bg-[#070c14] p-2.5 text-center">
                    <span className="block font-mono text-lg font-bold text-slate-200">{overview.methods_count}</span>
                    <span className="text-[11px] text-[var(--muted)]">Methods</span>
                  </div>
                  <div className="rounded border border-[var(--border)] bg-[#070c14] p-2.5 text-center">
                    <span className="block font-mono text-lg font-bold text-slate-200">{overview.chunks_count}</span>
                    <span className="text-[11px] text-[var(--muted)]">AST Chunks</span>
                  </div>
                  <div className="col-span-2 rounded border border-[var(--border)] bg-[#070c14] p-2.5 text-left">
                    <div className="text-[11px] text-[var(--muted)]">Embeddings: <span className="font-mono text-slate-300">{overview.embedding_model}</span></div>
                    <div className="mt-1 text-[11px] text-[var(--muted)]">LLM: <span className="font-mono text-slate-300">{overview.llm_model}</span></div>
                  </div>
                </div>
              </div>
            )}

            <div className="mt-5 flex flex-wrap items-center gap-4">
              <button
                type="button"
                onClick={indexRepository}
                disabled={isIndexing || result.python_file_count === 0}
                className="rounded-lg border border-[var(--accent)] px-4 py-2.5 text-sm font-medium text-[var(--accent)] transition-colors hover:bg-emerald-950/30 disabled:cursor-not-allowed disabled:opacity-45"
              >
                {isIndexing ? "Indexing…" : indexJob?.status === "completed" || overview ? "Re-index repository" : "Index repository"}
              </button>
              {indexJob && (
                <p role="status" className="text-sm text-[var(--muted)]">
                  {indexJob.status === "indexing" || indexJob.status === "queued"
                    ? `${indexJob.status === "queued" ? "Waiting to index" : `Parsed ${indexJob.files_processed} of ${indexJob.files_total} files`} · ${indexJob.chunks_total} chunks extracted`
                    : indexJob.status === "completed"
                    ? `Indexed ${indexJob.files_indexed} files · ${indexJob.chunks_indexed} chunks`
                    : "Indexing failed"}
                </p>
              )}
            </div>
            {!!indexJob?.warnings.length && (
              <ul className="mt-4 space-y-1 text-xs text-amber-300">
                {indexJob.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            )}
            <details className="mt-5">
              <summary className="cursor-pointer text-sm text-[var(--muted)]">
                Discovered Python files ({result.discovered_files.length})
              </summary>
              <ul className="mt-3 max-h-48 divide-y divide-[var(--border)] overflow-y-auto rounded-lg border border-[var(--border)]">
                {result.discovered_files.map((file) => (
                  <li key={file.path} className="flex justify-between gap-3 px-4 py-2 text-xs">
                    <span className="break-all font-mono text-slate-300">{file.path}</span>
                    <span className="shrink-0 text-[var(--muted)]">{file.line_count} lines</span>
                  </li>
                ))}
              </ul>
            </details>
          </div>
        )}
        {ollama && (
          <p
            className={`mt-5 border-t border-[var(--border)] pt-4 text-xs ${
              ollama.available && ollama.model_available ? "text-emerald-300" : "text-amber-300"
            }`}
          >
            Local model: {ollama.available && ollama.model_available ? `${ollama.model} ready` : ollama.detail}
          </p>
        )}
      </section>

      {/* Ask Question Section */}
      <section className="mt-8 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-base font-medium">Ask about your code</h2>
          {/* Retrieval Mode Selector */}
          <div className="flex items-center gap-2 text-xs">
            <span className="text-[var(--muted)]">Mode:</span>
            <select
              value={retrievalMode}
              onChange={(e) => setRetrievalMode(e.target.value)}
              className="rounded border border-[var(--border)] bg-[#0b111a] px-2.5 py-1 text-xs text-slate-200 outline-none focus:border-[var(--accent)]"
            >
              <option value="hybrid_rerank">Hybrid + Rerank (Recommended)</option>
              <option value="hybrid">Hybrid RRF</option>
              <option value="semantic">Semantic Only</option>
              <option value="bm25">BM25 Only</option>
            </select>
          </div>
        </div>

        <form onSubmit={askQuestion} className="mt-4 flex flex-col gap-3 sm:flex-row">
          <label htmlFor="code-question" className="sr-only">
            Question about this codebase
          </label>
          <input
            id="code-question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="How does hybrid retrieval and reranking work?"
            className="min-w-0 flex-1 rounded-lg border border-[var(--border)] bg-[#0b111a] px-4 py-3 text-sm outline-none placeholder:text-slate-600 focus:border-[var(--accent)]"
          />
          <button
            type="submit"
            disabled={!indexed || isAsking || !question.trim()}
            className="rounded-lg bg-[var(--accent)] px-5 py-3 text-sm font-semibold text-[#0b1716] disabled:cursor-not-allowed disabled:opacity-45"
          >
            {isAsking ? "Thinking…" : "Ask"}
          </button>
        </form>

        {!indexed && (
          <div className="mt-3 rounded-md border border-amber-900/40 bg-amber-950/20 px-3 py-2 text-xs text-amber-300">
            ℹ️ Scan and index a repository before asking questions.
          </div>
        )}

        {/* Chat History */}
        {chat.length > 0 ? (
          <div className="mt-6 space-y-5 border-t border-[var(--border)] pt-5">
            {chat.map((entry) => (
              <article key={entry.id} className="rounded-lg border border-[var(--border)] bg-[#0b111a] p-4">
                <div className="flex items-center justify-between border-b border-[var(--border)] pb-2">
                  <h3 className="text-sm font-medium text-slate-200">Q: {entry.question}</h3>
                  <span className="font-mono text-[10px] uppercase text-[var(--muted)]">
                    {entry.retrievalMode ?? "hybrid"}
                  </span>
                </div>

                {entry.loading && (
                  <p role="status" className="mt-3 text-sm text-[var(--muted)] animate-pulse">
                    Retrieving AST evidence and asking local Ollama model…
                  </p>
                )}

                {entry.error && (
                  <p role="alert" className="mt-3 text-sm text-rose-300">
                    {entry.error}
                  </p>
                )}

                {entry.answer && (
                  <div className="mt-3">
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Answer</h4>
                    <p className="mt-1.5 whitespace-pre-wrap text-sm leading-6 text-slate-300">{entry.answer}</p>
                  </div>
                )}

                {/* Sources Section */}
                {entry.sources !== undefined && (
                  <div className="mt-4 border-t border-[var(--border)] pt-3">
                    <div className="flex items-center justify-between">
                      <h4 className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
                        Retrieved Evidence ({entry.sources.length} sources)
                      </h4>
                      {entry.sources.length === 0 && (
                        <span className="text-xs text-amber-400">No relevant evidence retrieved</span>
                      )}
                    </div>

                    {entry.sources.length > 0 && (
                      <ul className="mt-2 space-y-2">
                        {entry.sources.map((source, index) => (
                          <li
                            key={`${source.file_path}:${source.start_line}:${index}`}
                            className="flex flex-wrap items-center justify-between gap-2 rounded border border-[var(--border)] bg-[#070d14] px-3 py-2 text-xs"
                          >
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="font-mono font-medium text-[var(--accent)]">
                                {source.file_path}:{source.start_line}-{source.end_line}
                              </span>
                              <span className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[11px] text-slate-300">
                                {source.symbol
                                  ? source.parent_symbol
                                    ? `${source.parent_symbol}.${source.symbol}`
                                    : source.symbol
                                  : source.chunk_type}
                              </span>
                              <span className="text-[11px] text-[var(--muted)]">({source.chunk_type})</span>
                            </div>
                            <button
                              type="button"
                              onClick={() => openSourceViewer(source)}
                              className="rounded border border-slate-700 bg-slate-800/80 px-2 py-1 text-[11px] text-slate-200 transition-colors hover:border-[var(--accent)] hover:text-[var(--accent)]"
                            >
                              View source snippet
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </article>
            ))}
          </div>
        ) : (
          <p className="mt-6 border-t border-[var(--border)] pt-5 text-sm text-[var(--muted)]">
            Your questions, grounded answers, and source citations will appear here.
          </p>
        )}
      </section>

      {/* Safe Source Viewer Modal */}
      {selectedSource && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm">
          <div className="flex max-h-[85vh] w-full max-w-3xl flex-col rounded-xl border border-[var(--border)] bg-[#0f1724] shadow-2xl">
            <div className="flex items-center justify-between border-b border-[var(--border)] px-5 py-4">
              <div>
                <h3 className="font-mono text-sm font-semibold text-[var(--accent)]">
                  {selectedSource.file_path}
                </h3>
                <p className="mt-0.5 text-xs text-[var(--muted)]">
                  Lines {selectedSource.start_line}–{selectedSource.end_line} ·{" "}
                  {selectedSource.symbol || selectedSource.chunk_type}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedSource(null)}
                className="rounded-lg border border-[var(--border)] bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-slate-700"
              >
                Close
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-5">
              {loadingSnippet && (
                <p className="text-sm text-[var(--muted)] animate-pulse">Loading snippet from repository…</p>
              )}
              {snippetError && (
                <p className="rounded border border-rose-900/60 bg-rose-950/30 p-3 text-xs text-rose-300">
                  {snippetError}
                </p>
              )}
              {sourceSnippet && (
                <div className="rounded-lg border border-[var(--border)] bg-[#070b12] p-4">
                  <div className="mb-2 flex items-center justify-between text-[11px] text-[var(--muted)]">
                    <span>
                      Showing lines {sourceSnippet.start_line}–{sourceSnippet.end_line} of {sourceSnippet.total_lines}
                    </span>
                    <button
                      type="button"
                      onClick={() => navigator.clipboard.writeText(sourceSnippet.code || sourceSnippet.content || "")}
                      className="text-xs text-[var(--accent)] hover:underline"
                    >
                      Copy snippet
                    </button>
                  </div>
                  <pre className="overflow-x-auto font-mono text-xs leading-5 text-slate-200">
                    <code>
                      {(sourceSnippet.code || sourceSnippet.content || "").split("\n").map((line, idx) => (
                        <div key={idx} className="table-row">
                          <span className="table-cell select-none pr-4 text-right text-slate-600">
                            {sourceSnippet.start_line + idx}
                          </span>
                          <span className="table-cell">{line}</span>
                        </div>
                      ))}
                    </code>
                  </pre>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[#0b111a] p-4">
      <p className="font-mono text-xl text-[var(--foreground)]">{value.toLocaleString()}</p>
      <p className="mt-1 text-xs text-[var(--muted)]">{label}</p>
    </div>
  );
}
