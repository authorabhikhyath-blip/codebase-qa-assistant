import { RepositoryOverviewResponse, ScanResult } from "@/lib/api";

export function RepositoryOverview({ overview, scan }: { overview: RepositoryOverviewResponse | null; scan: ScanResult | null }) {
  if (!overview && !scan) return null;
  return <section className="mb-6 border-b border-[var(--border)] pb-4">
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-300">
      <span>{overview?.files_count ?? scan?.python_file_count ?? 0} Python files</span>
      <span className="text-[var(--muted)]">·</span>
      <span>{overview?.chunks_count ?? 0} chunks</span>
      <span className="text-[var(--muted)]">·</span>
      <span>{(overview?.lines_count ?? scan?.total_line_count ?? 0).toLocaleString()} lines</span>
    </div>
    {overview && <p className="mt-2 text-xs text-[var(--muted)]">{overview.classes_count} classes · {overview.functions_count} functions · {overview.methods_count} methods · indexed {new Date(overview.indexed_at).toLocaleString()}</p>}
  </section>;
}
