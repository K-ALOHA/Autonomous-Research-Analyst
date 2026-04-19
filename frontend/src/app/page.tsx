"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import { AppHeader } from "@/components/AppHeader";
import { GlassPanel } from "@/components/GlassPanel";
import { QueryComposer } from "@/components/QueryComposer";
import { ReportViewer } from "@/components/ReportViewer";
import { TracePanel } from "@/components/TracePanel";
import type { FinalResultPayload, TraceEvent } from "@/lib/streaming";
import { readNdjsonOrTextStream } from "@/lib/streaming";

type RunState = "idle" | "running" | "error";

export default function HomePage() {
  const [query, setQuery] = useState("");
  const [state, setState] = useState<RunState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [answer, setAnswer] = useState("");
  const [finalResult, setFinalResult] = useState<FinalResultPayload | null>(null);
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);

  const abortRef = useRef<AbortController | null>(null);
  const answerEndRef = useRef<HTMLDivElement | null>(null);

  const canSubmit = useMemo(() => query.trim().length > 0 && state !== "running", [query, state]);
  const reportSources = useMemo(() => {
    const raw = finalResult?.report_sources;
    if (!Array.isArray(raw)) return [];
    return raw.filter((s): s is { title?: string; url?: string } => Boolean(s && typeof s === "object"));
  }, [finalResult]);
  const runId = typeof finalResult?.run_id === "string" ? finalResult.run_id : "";

  const agentStatuses = useMemo(() => {
    const status: Record<string, "pending" | "running" | "done"> = {
      Planner: "pending",
      Search: "pending",
      Analyst: "pending",
      Critic: "pending",
      Editor: "pending",
    };

    for (const e of events) {
      const payload = e.payload;
      if (!payload || typeof payload !== "object") continue;
      const p = payload as Record<string, unknown>;
      if (p.plan && typeof p.plan === "object") status.Planner = "done";
      if (Array.isArray(p.search_query_results)) status.Search = "done";
      if (typeof p.analyst_answer === "string" && p.analyst_answer.trim()) status.Analyst = "done";
      if (typeof p.critic_confidence === "number") status.Critic = "done";
      if (typeof p.report_markdown === "string" && p.report_markdown.trim()) status.Editor = "done";
    }

    if (state === "running") {
      const order: Array<keyof typeof status> = ["Planner", "Search", "Analyst", "Critic", "Editor"];
      const firstPending = order.find((a) => status[a] !== "done");
      if (firstPending) status[firstPending] = "running";
    }

    return status;
  }, [events, state]);

  useEffect(() => {
    answerEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [answer]);

  async function onRun() {
    const q = query.trim();
    if (!q) return;

    abortRef.current?.abort();
    abortRef.current = new AbortController();

    setState("running");
    setError(null);
    setAnswer("");
    setFinalResult(null);
    setEvents([]);
    setSelectedEventId(null);

    try {
      const res = await fetch("/api/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q }),
        signal: abortRef.current.signal,
      });

      if (!res.ok) {
        const t = await res.text().catch(() => "");
        try {
          const j = JSON.parse(t) as { message?: string; error?: string };
          throw new Error(j.message || j.error || t || `Request failed: ${res.status}`);
        } catch (e) {
          if (e instanceof SyntaxError) {
            throw new Error(t || `Request failed: ${res.status}`);
          }
          throw e;
        }
      }

      for await (const msg of readNdjsonOrTextStream(res)) {
        if (msg.type === "token") {
          setAnswer((prev) => prev + msg.text);
        } else if (msg.type === "trace") {
          setEvents((prev) => [...prev, msg.event]);
        } else if (msg.type === "final") {
          const data = (msg.data ?? {}) as FinalResultPayload;
          setFinalResult(data);
          setAnswer((prev) => {
            if (prev.trim().length > 0) return prev;
            const fromData = typeof data.report_markdown === "string" ? data.report_markdown.trim() : "";
            if (fromData) return fromData;
            const fromMsg = typeof msg.text === "string" ? msg.text.trim() : "";
            if (fromMsg) return fromMsg;
            return prev;
          });
        } else if (msg.type === "error") {
          throw new Error(msg.message);
        }
      }

      setState("idle");
    } catch (e) {
      if ((e as { name?: string })?.name === "AbortError") return;
      setState("error");
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  function onStop() {
    abortRef.current?.abort();
    abortRef.current = null;
    setState("idle");
  }

  async function onDownloadPdf() {
    if (!runId || isDownloading) return;
    setIsDownloading(true);
    try {
      const res = await fetch(`/api/research/${encodeURIComponent(runId)}/export/pdf`, { method: "GET" });
      if (!res.ok) {
        const t = await res.text().catch(() => "");
        throw new Error(t || `Download failed: ${res.status}`);
      }
      const blob = await res.blob();
      const href = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = href;
      a.download = `research-${runId.slice(0, 8)}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(href);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setIsDownloading(false);
    }
  }

  return (
    <div className="min-h-screen">
      <AppHeader />

      <main className="mx-auto max-w-7xl px-4 pb-16 pt-8 md:px-8">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          className="mb-8 text-center md:text-left"
        >
          <p className="text-sm text-zinc-400 md:max-w-2xl">
            Premium streaming workspace: watch tokens arrive, inspect each graph transition, and export a polished PDF
            when the run completes.
          </p>
        </motion.div>

        <QueryComposer
          query={query}
          onChange={setQuery}
          onRun={onRun}
          onStop={onStop}
          running={state === "running"}
          canSubmit={canSubmit}
        />

        <div className="mt-8 grid grid-cols-1 gap-8 lg:grid-cols-[minmax(0,1.55fr)_minmax(320px,1fr)] lg:items-start">
          <section className="flex min-h-0 flex-col gap-6">
            <ReportViewer
              error={error}
              answer={answer}
              running={state === "running"}
              runId={runId}
              isDownloading={isDownloading}
              onDownloadPdf={onDownloadPdf}
              reportSources={reportSources}
              answerEndRef={answerEndRef}
            />
          </section>

          <aside className="min-h-0">
            <TracePanel
              events={events}
              selectedId={selectedEventId}
              onSelect={setSelectedEventId}
              agentStatuses={agentStatuses}
            />
          </aside>
        </div>
      </main>

      <footer className="mx-auto max-w-7xl px-4 pb-12 md:px-8">
        <GlassPanel padding="p-5">
          <div className="text-xs font-semibold uppercase tracking-[0.16em] text-zinc-500">Backend</div>
          <p className="mt-2 text-sm leading-relaxed text-zinc-400">
            Calls your FastAPI service via{" "}
            <span className="font-medium text-zinc-200">NEXT_PUBLIC_BACKEND_URL</span> and{" "}
            <span className="font-medium text-zinc-200">NEXT_PUBLIC_BACKEND_STREAM_PATH</span> (for example{" "}
            <code className="rounded border border-white/10 bg-black/40 px-1.5 py-0.5 font-mono text-[11px] text-violet-200">
              /research
            </code>
            ). Configure both in production; the UI does not use a mock stream.
          </p>
        </GlassPanel>
      </footer>
    </div>
  );
}
