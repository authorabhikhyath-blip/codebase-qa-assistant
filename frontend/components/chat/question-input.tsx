"use client";

import { FormEvent, KeyboardEvent, useState } from "react";

const EXAMPLES = [
  "How does a request move through the application?",
  "Where should I start reading this project?",
  "How does authentication work?",
  "Why are BM25 and vector search combined?",
];

export function QuestionInput({ disabled, busy, onAsk }: { disabled: boolean; busy: boolean; onAsk: (question: string) => void }) {
  const [question, setQuestion] = useState("");
  function submit(event?: FormEvent) {
    event?.preventDefault();
    const value = question.trim();
    if (!value || disabled || busy) return;
    setQuestion("");
    onAsk(value);
  }
  function keyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }
  return <div className="sticky bottom-0 bg-[var(--background)] pt-3">
    {disabled && <p className="mb-2 text-center text-xs text-[var(--muted)]">Scan and index a repository before asking questions.</p>}
    <form onSubmit={submit} className="rounded-xl border border-[var(--border)] bg-[#111821] p-2 shadow-lg shadow-black/10 focus-within:border-slate-500">
      <label htmlFor="question" className="sr-only">Question about this codebase</label>
      <textarea id="question" value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={keyDown} disabled={disabled || busy} rows={2} placeholder="Ask anything about your codebase..." className="max-h-36 min-h-14 w-full resize-y bg-transparent px-2 py-2 text-sm leading-6 outline-none placeholder:text-slate-500 disabled:cursor-not-allowed" />
      <div className="flex items-center justify-between px-1 pb-1">
        <p className="text-[11px] text-[var(--muted)]">Enter to send · Shift+Enter for a new line</p>
        <button aria-label="Send question" type="submit" disabled={disabled || busy || !question.trim()} className="grid size-8 place-items-center rounded-lg bg-[var(--accent)] text-slate-950 transition-opacity disabled:cursor-not-allowed disabled:opacity-40">{busy ? <span className="size-3 animate-spin rounded-full border-2 border-slate-700 border-t-transparent" /> : <span aria-hidden="true">↑</span>}</button>
      </div>
    </form>
    {!disabled && <div className="mt-3 flex flex-wrap justify-center gap-2">{EXAMPLES.map((example) => <button type="button" key={example} disabled={busy} onClick={() => onAsk(example)} className="rounded-full border border-[var(--border)] px-3 py-1.5 text-xs text-slate-300 transition-colors hover:bg-white/[0.05] disabled:opacity-50">{example}</button>)}</div>}
  </div>;
}
