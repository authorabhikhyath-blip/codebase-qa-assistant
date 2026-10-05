"use client";

import { useEffect, useState } from "react";

type Status = "checking" | "connected" | "offline";

export function BackendStatus() {
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 3000);
    fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}/health`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error("Health check failed");
        return response.json();
      })
      .then((data: { status?: string }) => setStatus(data.status === "ok" ? "connected" : "offline"))
      .catch(() => setStatus("offline"))
      .finally(() => window.clearTimeout(timeout));
    return () => {
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, []);

  const label = status === "checking" ? "Backend: Checking" : `Backend: ${status === "connected" ? "Connected" : "Offline"}`;
  return <div aria-live="polite" className="flex items-center gap-2 text-xs text-[var(--muted)]">
    <span className={`size-2 rounded-full ${status === "connected" ? "bg-emerald-400" : status === "offline" ? "bg-rose-400" : "bg-amber-400"}`} />
    {label}
  </div>;
}
