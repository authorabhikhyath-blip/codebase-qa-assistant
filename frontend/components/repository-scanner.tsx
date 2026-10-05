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
type Source = { file_path: string; symbol: string; chunk_type: string; start_line: number; end_line: number };
type ChatEntry = { id: number; question: string; answer?: string; sources?: Source[]; error?: string; loading: boolean };
type OllamaStatus = { available: boolean; model: string; model_available: boolean; detail: string };

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export function RepositoryScanner() {
  const [path, setPath] = useState("");
  const [result, setResult] = useState<ScanResult | null>(null);
  const [indexJob, setIndexJob] = useState<IndexJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isScanning, setIsScanning] = useState(false);
  const [isIndexing, setIsIndexing] = useState(false);
  const [ollama, setOllama] = useState<OllamaStatus | null>(null);
  const [question, setQuestion] = useState("");
  const [chat, setChat] = useState<ChatEntry[]>([]);
  const [isAsking, setIsAsking] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/ollama/status`)
      .then(async (response) => {
        if (!response.ok) throw new Error("Could not check Ollama status.");
        setOllama(await response.json() as OllamaStatus);
      })
      .catch(() => setOllama({ available: false, model: "local model", model_available: false, detail: "Could not reach the backend to check local Ollama." }));
  }, []);

  async function scan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setResult(null);
    setIndexJob(null);
    setChat([]);
    setIsScanning(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/repositories/scan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: path.trim() }),
      });
      const data: ScanResult | { detail?: string } = await response.json();
      if (!response.ok) throw new Error("detail" in data && data.detail ? data.detail : `Repository scan failed (${response.status}).`);
      setResult(data as ScanResult);
    } catch (scanError) {
      setError(scanError instanceof Error ? scanError.message : "Could not scan the repository. Check that the backend is running.");
    } finally {
      setIsScanning(false);
    }
  }

  async function indexRepository() {
    if (!result) return;
    setError(null);
    setIsIndexing(true);
    setIndexJob(null);
    setChat([]);
    try {
      const started = await fetch(`${API_BASE_URL}/api/repositories/index`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: result.repository_path }),
      });
      const initial: IndexJob | { detail?: string } = await started.json();
      if (!started.ok) throw new Error("detail" in initial && initial.detail ? initial.detail : `Indexing could not start (${started.status}).`);
      const job = initial as IndexJob;
      setIndexJob(job);

      for (;;) {
        const response = await fetch(`${API_BASE_URL}/api/repositories/index/${job.job_id}`, { cache: "no-store" });
        const update: IndexJob | { detail?: string } = await response.json();
        if (!response.ok) throw new Error("detail" in update && update.detail ? update.detail : "Could not read indexing status.");
        const current = update as IndexJob;
        setIndexJob(current);
        if (current.status === "completed" || current.status === "failed") {
          if (current.status === "failed") setError(current.error || "Repository indexing failed.");
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

  async function askQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!result || !question.trim()) return;
    const submittedQuestion = question.trim();
    const id = Date.now();
    setQuestion("");
    setIsAsking(true);
    setChat((entries) => [...entries, { id, question: submittedQuestion, loading: true }]);
    try {
      const response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: result.repository_path, question: submittedQuestion }),
      });
      const data = await response.json() as { answer?: string; sources?: Source[]; detail?: string };
      if (!response.ok) throw new Error(data.detail || `Question failed (${response.status}).`);
      setChat((entries) => entries.map((entry) => entry.id === id
        ? { ...entry, answer: data.answer, sources: data.sources ?? [], loading: false }
        : entry));
    } catch (chatError) {
      setChat((entries) => entries.map((entry) => entry.id === id
        ? { ...entry, error: chatError instanceof Error ? chatError.message : "Could not get an answer.", loading: false }
        : entry));
    } finally {
      setIsAsking(false);
    }
  }

  const indexed = indexJob?.status === "completed" && indexJob.chunks_indexed > 0;

  return (
    <>
      <section className="mt-8 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6">
        <div>
          <h2 className="text-base font-medium">Repository</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">Enter a folder path available to this backend process. Repository files remain local.</p>
        </div>
        <form onSubmit={scan} className="mt-5 flex flex-col gap-3 sm:flex-row">
          <label htmlFor="repository-path" className="sr-only">Local repository path</label>
          <input
            id="repository-path"
            type="text"
            required
            value={path}
            onChange={(event) => setPath(event.target.value)}
            placeholder="C:\\Users\\you\\projects\\my-repository"
            className="min-w-0 flex-1 rounded-lg border border-[var(--border)] bg-[#0b111a] px-4 py-3 font-mono text-sm text-[var(--foreground)] outline-none placeholder:text-slate-600 focus:border-[var(--accent)]"
          />
          <button type="submit" disabled={isScanning || isIndexing || !path.trim()} className="rounded-lg bg-[var(--accent)] px-5 py-3 text-sm font-semibold text-[#0b1716] transition-opacity disabled:cursor-not-allowed disabled:opacity-50">
            {isScanning ? "Scanning…" : "Scan repository"}
          </button>
        </form>
        {isScanning && <p role="status" className="mt-4 text-sm text-[var(--muted)]">Scanning Python source files…</p>}
        {error && <p role="alert" className="mt-4 rounded-lg border border-rose-900/70 bg-rose-950/30 px-4 py-3 text-sm text-rose-300">{error}</p>}
        {result && (
          <div className="mt-6 border-t border-[var(--border)] pt-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <h3 className="text-lg font-medium">{result.repository_name}</h3>
                <p className="mt-1 break-all font-mono text-xs text-[var(--muted)]">{result.repository_path}</p>
              </div>
              <span className="rounded-full border border-emerald-900 bg-emerald-950/40 px-3 py-1 font-mono text-xs text-emerald-300">{indexJob?.status ?? result.scan_status}</span>
            </div>
            <div className="mt-5 grid gap-3 sm:grid-cols-4">
              <Stat label="Python files" value={result.python_file_count} />
              <Stat label="Python lines" value={result.total_line_count} />
              <Stat label="Discovered files" value={result.total_discovered_files} />
              <Stat label="Indexed chunks" value={indexJob?.chunks_indexed ?? 0} />
            </div>
            <div className="mt-5 flex flex-wrap items-center gap-4">
              <button type="button" onClick={indexRepository} disabled={isIndexing || result.python_file_count === 0} className="rounded-lg border border-[var(--accent)] px-4 py-2.5 text-sm font-medium text-[var(--accent)] transition-colors hover:bg-emerald-950/30 disabled:cursor-not-allowed disabled:opacity-45">
                {isIndexing ? "Indexing…" : indexJob?.status === "completed" ? "Re-index repository" : "Index repository"}
              </button>
              {indexJob && <p role="status" className="text-sm text-[var(--muted)]">
                {indexJob.status === "indexing" || indexJob.status === "queued"
                  ? `${indexJob.status === "queued" ? "Waiting to index" : `Parsed ${indexJob.files_processed} of ${indexJob.files_total} files`} · ${indexJob.chunks_total} chunks extracted`
                  : indexJob.status === "completed" ? `Indexed ${indexJob.files_indexed} files · ${indexJob.chunks_indexed} chunks` : "Indexing failed"}
              </p>}
            </div>
            {!!indexJob?.warnings.length && <ul className="mt-4 space-y-1 text-xs text-amber-300">{indexJob.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>}
            <details className="mt-5">
              <summary className="cursor-pointer text-sm text-[var(--muted)]">Discovered Python files ({result.discovered_files.length})</summary>
              <ul className="mt-3 max-h-48 divide-y divide-[var(--border)] overflow-y-auto rounded-lg border border-[var(--border)]">
                {result.discovered_files.map((file) => <li key={file.path} className="flex justify-between gap-3 px-4 py-2 text-xs"><span className="break-all font-mono text-slate-300">{file.path}</span><span className="shrink-0 text-[var(--muted)]">{file.line_count} lines</span></li>)}
              </ul>
            </details>
          </div>
        )}
        {ollama && <p className={`mt-5 border-t border-[var(--border)] pt-4 text-xs ${ollama.available && ollama.model_available ? "text-emerald-300" : "text-amber-300"}`}>
          Local model: {ollama.available && ollama.model_available ? `${ollama.model} ready` : ollama.detail}
        </p>}
      </section>

      <section className="mt-8 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6">
        <h2 className="text-base font-medium">Ask about your code</h2>
        <form onSubmit={askQuestion} className="mt-4 flex flex-col gap-3 sm:flex-row">
          <label htmlFor="code-question" className="sr-only">Question about this codebase</label>
          <input id="code-question" value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="How does authentication work?" className="min-w-0 flex-1 rounded-lg border border-[var(--border)] bg-[#0b111a] px-4 py-3 text-sm outline-none placeholder:text-slate-600 focus:border-[var(--accent)]" />
          <button type="submit" disabled={!indexed || isAsking || !question.trim()} className="rounded-lg bg-[var(--accent)] px-5 py-3 text-sm font-semibold text-[#0b1716] disabled:cursor-not-allowed disabled:opacity-45">{isAsking ? "Thinking…" : "Ask"}</button>
        </form>
        {!indexed && <p className="mt-3 text-xs text-[var(--muted)]">Scan and index a repository before asking questions.</p>}
        {chat.length > 0 ? <div className="mt-6 space-y-4 border-t border-[var(--border)] pt-5">
          {chat.map((entry) => <article key={entry.id} className="rounded-lg border border-[var(--border)] bg-[#0b111a] p-4">
            <h3 className="text-sm font-medium text-slate-200">{entry.question}</h3>
            {entry.loading && <p role="status" className="mt-3 text-sm text-[var(--muted)]">Retrieving code and asking the local model…</p>}
            {entry.error && <p role="alert" className="mt-3 text-sm text-rose-300">{entry.error}</p>}
            {entry.answer && <>
              <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-300">{entry.answer}</p>
              {!!entry.sources?.length && <div className="mt-4 border-t border-[var(--border)] pt-3">
                <h4 className="text-xs font-medium uppercase tracking-wide text-[var(--muted)]">Retrieved sources</h4>
                <ul className="mt-2 space-y-1">{entry.sources.map((source, index) => <li key={`${source.file_path}:${source.start_line}:${index}`} className="font-mono text-xs text-[var(--accent)]">
                  {source.file_path}:{source.start_line}-{source.end_line}{source.symbol ? ` · ${source.symbol}` : ` · ${source.chunk_type}`}
                </li>)}</ul>
              </div>}
            </>}
          </article>)}
        </div> : <p className="mt-6 border-t border-[var(--border)] pt-5 text-sm text-[var(--muted)]">Your questions and answers will appear here for this session.</p>}
      </section>
    </>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return <div className="rounded-lg border border-[var(--border)] bg-[#0b111a] p-4">
    <p className="font-mono text-xl text-[var(--foreground)]">{value.toLocaleString()}</p>
    <p className="mt-1 text-xs text-[var(--muted)]">{label}</p>
  </div>;
}
