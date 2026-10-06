import { IndexJob, RepositoryOverviewResponse, ScanResult } from "@/lib/api";

export function RepositoryHeader({ scan, overview, job, indexed }: { scan: ScanResult | null; overview: RepositoryOverviewResponse | null; job: IndexJob | null; indexed: boolean }) {
  const name = overview?.repository_name || scan?.repository_name;
  const stage = job?.status === "failed" ? "Indexing failed" : indexed ? "Ready to chat" : scan ? stageLabel(job) : "Select a repository";
  return <header id="overview" className="mb-4 flex flex-wrap items-start justify-between gap-4">
    <div>
      <p className="text-xs text-[var(--muted)]">Repository</p>
      <h1 className="mt-1 text-xl font-semibold tracking-tight">{name || "Understand your codebase"}</h1>
      {name && <p className="mt-1 text-sm text-[var(--muted)]">Python codebase</p>}
    </div>
    <span className={`rounded-full px-2.5 py-1 text-xs ${indexed ? "bg-emerald-950/60 text-emerald-300" : job?.status === "failed" ? "bg-rose-950/60 text-rose-300" : "bg-white/[0.05] text-slate-300"}`}>{stage}</span>
  </header>;
}

function stageLabel(job: IndexJob | null): string {
  if (!job) return "Not indexed";
  if (job.status === "queued") return "Waiting to start";
  if (job.status !== "indexing") return "Not indexed";
  const labels: Record<string, string> = {
    scanning: "Scanning repository",
    parsing: `Parsing source structure · ${job.files_processed}/${job.files_total}`,
    embedding: "Building semantic index",
    semantic_index: "Storing semantic index",
    lexical_index: "Building lexical index",
  };
  return labels[job.stage] || "Preparing code index";
}
