"use client";

import { FormEvent, ReactNode } from "react";
import { BackendStatus } from "@/components/backend-status";
import { IndexJob, OllamaStatus, RepositoryOverviewResponse, ScanResult } from "@/lib/api";

interface Props {
  children: ReactNode;
  repositoryName: string;
  path: string;
  scanning: boolean;
  scan: ScanResult | null;
  job: IndexJob | null;
  overview: RepositoryOverviewResponse | null;
  indexed: boolean;
  ollama: OllamaStatus | null;
  error: string | null;
  onPathChange: (value: string) => void;
  onScan: () => void;
  onIndex: () => void;
}

export function AppShell(props: Props) {
  const { children, repositoryName, path, scanning, scan, job, overview, indexed, ollama } = props;
  function submitPath(event: FormEvent) {
    event.preventDefault();
    props.onScan();
  }
  const busy = scanning || job?.status === "queued" || job?.status === "indexing";

  return (
    <div className="min-h-screen bg-[var(--background)]">
      <header className="flex h-14 items-center justify-between border-b border-[var(--border)] px-5 lg:px-7">
        <div className="flex items-center gap-3">
          <div className="grid size-7 place-items-center rounded-md bg-[var(--accent)] text-xs font-semibold text-slate-950">CQ</div>
          <span className="text-sm font-semibold">Codebase QA</span>
        </div>
        <BackendStatus />
      </header>
      <div className="mx-auto grid min-h-[calc(100vh-3.5rem)] max-w-[1440px] lg:grid-cols-[260px_minmax(0,1fr)]">
        <aside className="border-b border-[var(--border)] px-5 py-5 lg:border-b-0 lg:border-r lg:px-4">
          <p className="mb-2 px-2 text-xs font-medium text-[var(--muted)]">Workspace</p>
          <nav className="mb-7 space-y-1 text-sm">
            <a href="#overview" className="block rounded-md px-2 py-2 text-slate-300 hover:bg-white/[0.04]">Overview</a>
            <a href="#conversation" className="block rounded-md bg-white/[0.06] px-2 py-2 text-slate-100">Chat</a>
          </nav>
          <div className="px-2">
            <h2 className="text-xs font-medium text-[var(--muted)]">Current repository</h2>
            <p className="mt-2 truncate text-sm font-medium" title={repositoryName}>{repositoryName}</p>
            {scan && <p className="mt-1 break-all font-mono text-[11px] leading-5 text-[var(--muted)]">{scan.repository_path}</p>}
            <form onSubmit={submitPath} className="mt-4 space-y-2">
              <label htmlFor="repo-path" className="text-xs text-[var(--muted)]">Repository folder</label>
              <input id="repo-path" value={path} onChange={(event) => props.onPathChange(event.target.value)} placeholder="Enter a local folder path" className="w-full rounded-md border border-[var(--border)] bg-[#0c1118] px-3 py-2 text-xs outline-none placeholder:text-slate-600 focus:border-[var(--accent)]" />
              <button type="submit" disabled={scanning || !path.trim()} className="w-full rounded-md border border-[var(--border)] px-3 py-2 text-xs font-medium text-slate-200 hover:bg-white/[0.04] disabled:opacity-50">{scanning ? "Scanning…" : "Scan repository"}</button>
            </form>
            {scan && <button type="button" onClick={props.onIndex} disabled={busy || scan.python_file_count === 0} className="mt-2 w-full rounded-md bg-[var(--accent)] px-3 py-2 text-xs font-semibold text-slate-950 disabled:opacity-50">{busy ? "Indexing…" : indexed ? "Re-index repository" : "Build code index"}</button>}
            {props.error && <p role="alert" className="mt-3 rounded-md bg-rose-950/40 px-3 py-2 text-xs leading-5 text-rose-200">{props.error}</p>}
          </div>
          <div className="mt-7 border-t border-[var(--border)] pt-5">
            <p className="px-2 text-xs font-medium text-[var(--muted)]">Settings</p>
            <div className="mt-3 px-2 text-xs leading-5 text-slate-300">Answer model<br/><span className="font-mono text-[11px] text-[var(--muted)]">{ollama?.model ?? "Checking…"}</span></div>
            <p className={`mt-2 px-2 text-xs ${ollama?.available && ollama.model_available ? "text-emerald-300" : "text-amber-300"}`}>{ollama?.available && ollama.model_available ? "Ready" : ollama ? "Not ready" : "Checking status"}</p>
          </div>
          <p className="mt-7 border-t border-[var(--border)] pt-4 px-2 text-xs leading-5 text-[var(--muted)]">Repository indexing, parsing, embeddings, retrieval, and answer generation run locally.</p>
        </aside>
        <main className="min-w-0 px-5 py-6 lg:px-10 lg:py-8">
          <div className="mx-auto max-w-4xl">{props.children}</div>
        </main>
      </div>
    </div>
  );
}
