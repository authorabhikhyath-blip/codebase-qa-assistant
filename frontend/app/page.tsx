import { BackendStatus } from "@/components/backend-status";
import { RepositoryScanner } from "@/components/repository-scanner";

export default function Home() {
  return (
    <main className="min-h-screen">
      <header className="flex h-16 items-center justify-between border-b border-[var(--border)] px-8">
        <div className="flex items-center gap-3">
          <div className="grid size-8 place-items-center rounded-lg bg-[var(--accent)] font-mono font-bold text-[#0b1716]">{ "{ }" }</div>
          <span className="text-sm font-semibold tracking-wide">Codebase QA</span>
        </div>
        <BackendStatus />
      </header>
      <div className="mx-auto max-w-5xl px-8 py-20">
        <p className="font-mono text-xs uppercase tracking-[0.22em] text-[var(--accent)]">Local code intelligence</p>
        <h1 className="mt-5 max-w-2xl text-4xl font-semibold tracking-tight sm:text-5xl">Understand your codebase, with your code staying local.</h1>
        <p className="mt-5 max-w-xl text-base leading-7 text-[var(--muted)]">Scan a Python repository, index its code locally, and ask questions with retrieved source references.</p>
        <section className="mt-12 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h2 className="text-base font-medium">Local workspace</h2>
              <p className="mt-1 text-sm text-[var(--muted)]">Repository data, embeddings, and inference stay on this machine.</p>
            </div>
            <span className="rounded-full border border-[var(--border)] px-3 py-1 font-mono text-xs text-[var(--accent)]">Python · Local RAG</span>
          </div>
          <p className="mt-5 border-t border-[var(--border)] pt-4 text-xs text-[var(--muted)]">Tree-sitter · local FastEmbed · persistent ChromaDB · local Ollama</p>
        </section>
        <RepositoryScanner />
      </div>
    </main>
  );
}
