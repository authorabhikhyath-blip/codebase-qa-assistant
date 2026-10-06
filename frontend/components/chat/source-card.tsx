import { SourceReference } from "@/lib/api";

export function SourceCard({ source, onOpen }: { source: SourceReference; onOpen: (source: SourceReference) => void }) {
  const symbol = source.symbol
    ? `${source.parent_symbol ? `${source.parent_symbol}.` : ""}${source.symbol}${["function", "method"].includes(source.chunk_type) ? "()" : ""}`
    : source.chunk_type;
  return <li className="flex items-center justify-between gap-4 py-2.5">
    <div className="min-w-0">
      <p className="truncate font-medium text-slate-200">{symbol}</p>
      <p className="mt-0.5 truncate font-mono text-xs text-[var(--muted)]">{source.file_path} · lines {source.start_line}–{source.end_line}</p>
    </div>
    <button type="button" onClick={() => onOpen(source)} className="shrink-0 text-xs text-[var(--accent)] hover:underline">View source</button>
  </li>;
}
