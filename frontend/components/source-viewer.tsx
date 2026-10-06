"use client";

import { useState } from "react";
import { SourceReference, SourceSnippet } from "@/lib/api";

export function SourceViewer({ source, snippet, loading, error, onClose }: { source: SourceReference | null; snippet: SourceSnippet | null; loading: boolean; error: string | null; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  if (!source) return null;
  async function copy() {
    if (!snippet) return;
    try { await navigator.clipboard.writeText(snippet.code); setCopied(true); window.setTimeout(() => setCopied(false), 1500); } catch { /* Clipboard can be unavailable in insecure contexts. */ }
  }
  return <div role="presentation" className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <section role="dialog" aria-modal="true" aria-label={`Source ${source.file_path}`} className="flex max-h-[88vh] w-full max-w-4xl flex-col overflow-hidden rounded-xl border border-[var(--border)] bg-[#101720] shadow-2xl">
      <header className="flex items-center justify-between gap-4 border-b border-[var(--border)] px-5 py-4">
        <div className="min-w-0"><h2 className="truncate font-mono text-sm text-slate-100">{source.file_path}</h2><p className="mt-1 text-xs text-[var(--muted)]">{source.symbol || source.chunk_type} · lines {source.start_line}–{source.end_line}</p></div>
        <div className="flex shrink-0 gap-2"><button type="button" onClick={() => void copy()} disabled={!snippet} className="rounded-md border border-[var(--border)] px-3 py-1.5 text-xs disabled:opacity-40">{copied ? "Copied" : "Copy code"}</button><button type="button" onClick={onClose} className="rounded-md border border-[var(--border)] px-3 py-1.5 text-xs">Close</button></div>
      </header>
      <div className="overflow-auto p-4">
        {loading && <p role="status" className="py-6 text-sm text-[var(--muted)]">Loading source…</p>}
        {error && <p role="alert" className="rounded-md bg-rose-950/40 p-3 text-sm text-rose-200">{error}</p>}
        {snippet && <div className="overflow-auto rounded-lg bg-[#080d13] py-2 text-xs leading-6">
          {snippet.code.split("\n").map((line, index) => <div key={index} className="grid min-w-max grid-cols-[3.5rem_1fr] px-3 hover:bg-white/[0.025]"><span className="select-none pr-4 text-right text-slate-600">{snippet.start_line + index}</span><code className="whitespace-pre font-mono text-slate-200">{highlightPython(line)}</code></div>)}
        </div>}
      </div>
    </section>
  </div>;
}

function highlightPython(line: string) {
  const tokenPattern = /(#[^'"`]*$|'''[^']*'''|"""[^"]*"""|'[^'\\]*(?:\\.[^'\\]*)*'|"[^"\\]*(?:\\.[^"\\]*)*"|\b(?:async|await|class|def|return|if|elif|else|for|while|try|except|finally|with|as|import|from|raise|yield|pass|break|continue|lambda|and|or|not|in|is|True|False|None)\b|\b\d+(?:\.\d+)?\b)/g;
  const parts: React.ReactNode[] = [];
  let last = 0;
  for (const match of line.matchAll(tokenPattern)) {
    const start = match.index ?? 0;
    if (start > last) parts.push(line.slice(last, start));
    const token = match[0];
    const color = token.startsWith("#") ? "text-slate-500" : /^[\'\"]/.test(token) ? "text-amber-200" : /^\d/.test(token) ? "text-purple-300" : "text-sky-300";
    parts.push(<span key={`${start}-${token}`} className={color}>{token}</span>);
    last = start + token.length;
  }
  if (last < line.length) parts.push(line.slice(last));
  return parts;
}
