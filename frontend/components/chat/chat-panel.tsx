"use client";

import { ChatResponse, SourceReference } from "@/lib/api";
import { QuestionInput } from "@/components/chat/question-input";
import { SourceCard } from "@/components/chat/source-card";

export interface ChatTurn {
  id: number;
  question: string;
  response?: ChatResponse;
  error?: string;
  loading: boolean;
}

export function ChatPanel({ turns, busy, indexed, onAsk, onOpenSource }: { turns: ChatTurn[]; busy: boolean; indexed: boolean; onAsk: (question: string) => void; onOpenSource: (source: SourceReference) => void }) {
  return <section id="conversation" className="flex min-h-[calc(100vh-13rem)] flex-col">
    <div className="mb-4 flex items-center justify-between">
      <div><h2 className="text-sm font-semibold">Conversation</h2><p className="mt-1 text-xs text-[var(--muted)]">Answers are grounded in retrieved repository code.</p></div>
    </div>
    <div className="flex-1">
      {turns.length === 0 && <div className="flex min-h-[36vh] flex-col items-center justify-center py-10 text-center">
        <div className="mb-4 grid size-10 place-items-center rounded-xl bg-white/[0.05] text-lg text-[var(--accent)]">⌕</div>
        <h3 className="text-lg font-medium">Understand your codebase</h3>
        <p className="mt-2 max-w-lg text-sm leading-6 text-[var(--muted)]">Ask about architecture, implementation, dependencies, data flow, security, or anything else in the indexed repository.</p>
      </div>}
      <div className="space-y-7">
        {turns.map((turn) => <article key={turn.id} className="space-y-4">
          <div className="ml-auto max-w-[88%] rounded-2xl rounded-br-sm bg-[#19232e] px-4 py-3 text-sm leading-6 text-slate-100">{turn.question}</div>
          {turn.loading && <div role="status" className="flex items-center gap-2 text-sm text-[var(--muted)]"><span className="size-2 animate-pulse rounded-full bg-[var(--accent)]" />Retrieving relevant code and generating an answer…</div>}
          {turn.error && <p role="alert" className="rounded-lg bg-rose-950/40 px-4 py-3 text-sm leading-6 text-rose-200">{turn.error}</p>}
          {turn.response && <div className="max-w-3xl">
            <div className="answer-content text-sm leading-7 text-slate-200">{renderAnswer(turn.response.answer)}</div>
            {turn.response.sources.length > 0 && <div className="mt-5 border-t border-[var(--border)] pt-3">
              <p className="text-xs font-medium text-[var(--muted)]">Sources · {turn.response.sources.length}</p>
              <ul className="mt-1 divide-y divide-[var(--border)]">{turn.response.sources.map((source, index) => <SourceCard key={`${source.file_path}:${source.start_line}:${index}`} source={source} onOpen={onOpenSource} />)}</ul>
            </div>}
          </div>}
        </article>)}
      </div>
    </div>
    <QuestionInput disabled={!indexed} busy={busy} onAsk={onAsk} />
  </section>;
}

function renderAnswer(answer: string) {
  const lines = answer.split("\n");
  const result: React.ReactNode[] = [];
  let list: string[] = [];
  const flush = () => {
    if (list.length) { result.push(<ul key={`list-${result.length}`} className="my-2 list-disc space-y-1 pl-5">{list.map((item, index) => <li key={index}>{inlineCode(item)}</li>)}</ul>); list = []; }
  };
  lines.forEach((line, index) => {
    const heading = line.match(/^#{1,3}\s+(.+)$/);
    const item = line.match(/^\s*(?:[-*]|\d+\.)\s+(.+)$/);
    if (item) { list.push(item[1]); return; }
    flush();
    if (heading) result.push(<h3 key={`heading-${index}`} className="mb-1 mt-4 text-base font-semibold text-slate-100">{inlineCode(heading[1])}</h3>);
    else if (line.trim()) result.push(<p key={`paragraph-${index}`} className="my-2">{inlineCode(line)}</p>);
  });
  flush();
  return result;
}

function inlineCode(text: string) {
  return text.split(/(`[^`]+`)/g).map((part, index) => part.startsWith("`") && part.endsWith("`")
    ? <code key={index} className="rounded bg-white/[0.07] px-1 py-0.5 font-mono text-[0.92em] text-emerald-200">{part.slice(1, -1)}</code>
    : part);
}
