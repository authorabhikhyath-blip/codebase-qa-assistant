"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { ChatPanel, ChatTurn } from "@/components/chat/chat-panel";
import { RepositoryHeader } from "@/components/repository-header";
import { RepositoryOverview } from "@/components/repository-overview";
import { SourceViewer } from "@/components/source-viewer";
import {
  API_BASE_URL, ChatResponse, IndexJob, OllamaStatus, RepositoryOverviewResponse, ScanResult,
  SourceReference, SourceSnippet, parseChatResponse, parseIndexJob, parseOverview, parseScanResult,
  parseSourceSnippet, requestJson,
} from "@/lib/api";

export function Workspace() {
  const [path, setPath] = useState("");
  const [scan, setScan] = useState<ScanResult | null>(null);
  const [job, setJob] = useState<IndexJob | null>(null);
  const [overview, setOverview] = useState<RepositoryOverviewResponse | null>(null);
  const [ollama, setOllama] = useState<OllamaStatus | null>(null);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [busy, setBusy] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState<SourceReference | null>(null);
  const [snippet, setSnippet] = useState<SourceSnippet | null>(null);
  const [sourceLoading, setSourceLoading] = useState(false);
  const [sourceError, setSourceError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    requestJson(`${API_BASE_URL}/api/ollama/status`)
      .then((raw) => {
        if (!active) return;
        const data = raw as OllamaStatus;
        if (typeof data.available !== "boolean" || typeof data.model_available !== "boolean" || typeof data.detail !== "string" || typeof data.model !== "string") throw new Error("invalid status");
        setOllama(data);
      })
      .catch(() => active && setOllama({ available: false, model: "Ollama", model_available: false, detail: "Start Ollama to generate answers." }));
    return () => { active = false; };
  }, []);

  async function scanRepository(repositoryPath: string) {
    setPath(repositoryPath);
    setError(null);
    setScanning(true);
    setScan(null);
    setJob(null);
    setOverview(null);
    setTurns([]);
    try {
      const raw = await requestJson(`${API_BASE_URL}/api/repositories/scan`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path: repositoryPath.trim() }),
      });
      const result = parseScanResult(raw);
      setScan(result);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not scan this repository.");
    } finally {
      setScanning(false);
    }
  }

  async function indexRepository() {
    if (!scan || busy) return;
    setError(null);
    setBusy(true);
    setJob(null);
    try {
      const started = parseIndexJob(await requestJson(`${API_BASE_URL}/api/repositories/index`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path: scan.repository_path }),
      }));
      setJob(started);
      for (;;) {
        await new Promise((resolve) => window.setTimeout(resolve, 600));
        const current = parseIndexJob(await requestJson(`${API_BASE_URL}/api/repositories/index/${started.job_id}`, { cache: "no-store" }));
        setJob(current);
        if (current.status === "failed") throw new Error(current.error || "Repository indexing failed. Please try again.");
        if (current.status === "completed") {
          setOverview(parseOverview(await requestJson(`${API_BASE_URL}/api/repositories/${current.repository_id}/overview`)));
          break;
        }
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not index this repository.");
    } finally {
      setBusy(false);
    }
  }

  async function ask(question: string) {
    if (!scan || !indexed || busy || !question.trim()) return;
    const id = Date.now() + Math.random();
    setTurns((current) => [...current, { id, question: question.trim(), loading: true }]);
    setBusy(true);
    try {
      const payload = await requestJson(`${API_BASE_URL}/api/chat`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: scan.repository_path, question: question.trim(), retrieval_mode: "hybrid" }),
      });
      const response: ChatResponse = parseChatResponse(payload);
      setTurns((current) => current.map((turn) => turn.id === id ? { ...turn, loading: false, response } : turn));
    } catch (cause) {
      setTurns((current) => current.map((turn) => turn.id === id ? {
        ...turn, loading: false, error: cause instanceof Error ? cause.message : "I couldn't get an answer. Please try again.",
      } : turn));
    } finally {
      setBusy(false);
    }
  }

  async function openSource(reference: SourceReference) {
    const repositoryId = overview?.repository_id || job?.repository_id;
    if (!repositoryId) return;
    setSource(reference);
    setSnippet(null);
    setSourceError(null);
    setSourceLoading(true);
    try {
      const url = `${API_BASE_URL}/api/repositories/${repositoryId}/source?file_path=${encodeURIComponent(reference.file_path)}&start_line=${reference.start_line}&end_line=${reference.end_line}`;
      setSnippet(parseSourceSnippet(await requestJson(url)));
    } catch (cause) {
      setSourceError(cause instanceof Error ? cause.message : "Could not open this source snippet.");
    } finally {
      setSourceLoading(false);
    }
  }

  const indexed = Boolean(overview && overview.chunks_count > 0);
  const activeName = overview?.repository_name || scan?.repository_name || "No repository selected";

  return (
    <AppShell
      repositoryName={activeName}
      path={path}
      scanning={scanning}
      scan={scan}
      job={job}
      overview={overview}
      indexed={indexed}
      ollama={ollama}
      error={error}
      onPathChange={setPath}
      onScan={() => void scanRepository(path)}
      onIndex={() => void indexRepository()}
    >
      <RepositoryHeader scan={scan} overview={overview} job={job} indexed={indexed} />
      <RepositoryOverview overview={overview} scan={scan} />
      <ChatPanel turns={turns} busy={busy} indexed={indexed} onAsk={(question) => void ask(question)} onOpenSource={(reference) => void openSource(reference)} />
      <SourceViewer source={source} snippet={snippet} loading={sourceLoading} error={sourceError} onClose={() => setSource(null)} />
    </AppShell>
  );
}
