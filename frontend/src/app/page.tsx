/* eslint-disable @next/next/no-img-element */
"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { TracePanel } from "@/components/TracePanel";
import type { FinalResultPayload, TraceEvent } from "@/lib/streaming";
import { readNdjsonOrTextStream } from "@/lib/streaming";

type RunState = "idle" | "running" | "error";

function Spinner() {
  return (
    <div
      className="h-4 w-4 animate-spin rounded-full border-2 border-gray-300 border-t-gray-800"
      aria-label="Loading"
    />
  );
}

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
        throw new Error(t || `Request failed: ${res.status}`);
      }

      for await (const msg of readNdjsonOrTextStream(res)) {
        if (msg.type === "token") {
          setAnswer((prev) => prev + msg.text);
        } else if (msg.type === "trace") {
          setEvents((prev) => [...prev, msg.event]);
        } else if (msg.type === "final") {
          const data = (msg.data ?? {}) as FinalResultPayload;
          setFinalResult(data);
          if (typeof data.report_markdown === "string" && data.report_markdown.trim()) {
            setAnswer(data.report_markdown);
          }
        } else if (msg.type === "error") {
          throw new Error(msg.message);
        }
      }

      setState("idle");
    } catch (e) {
      if ((e as any)?.name === "AbortError") return;
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
      <header className="mx-auto max-w-6xl px-6 pt-10">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div>
            <div className="text-sm font-semibold text-blue-700">
              Autonomous Research Analyst
            </div>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight text-gray-900">
              Streaming research UI
            </h1>
            <p className="mt-2 max-w-2xl text-sm text-gray-600">
              Type a question, watch the answer stream in, and inspect the agent
              trace as it runs.
            </p>
          </div>

          <div className="flex items-center gap-2 rounded-2xl border border-gray-200 bg-white px-3 py-2 text-xs text-gray-600 shadow-sm">
            <div className="h-2 w-2 rounded-full bg-green-500" />
            <span>UI ready</span>
            <span className="text-gray-300">•</span>
            <span className="text-gray-500">backend configurable</span>
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-6xl grid-cols-1 gap-6 px-6 pb-12 pt-8 lg:grid-cols-[1.5fr_1fr]">
        <section className="flex min-h-0 flex-col gap-4">
          <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
            <label className="text-sm font-semibold text-gray-900">
              Query
            </label>
            <div className="mt-2 flex gap-2">
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) onRun();
                }}
                placeholder="Ask a research question…"
                className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 outline-none transition focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
                disabled={state === "running"}
              />
              {state === "running" ? (
                <button
                  type="button"
                  onClick={onStop}
                  className="rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-gray-700 shadow-sm transition hover:bg-gray-50"
                >
                  Stop
                </button>
              ) : (
                <button
                  type="button"
                  onClick={onRun}
                  disabled={!canSubmit}
                  className="inline-flex items-center gap-2 rounded-xl bg-gray-900 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-black disabled:cursor-not-allowed disabled:bg-gray-300"
                >
                  Run
                </button>
              )}
            </div>
            <div className="mt-2 text-xs text-gray-500">
              Tip: press <span className="font-medium">⌘/Ctrl + Enter</span> to
              run.
            </div>
          </div>

          <div className="flex min-h-0 flex-1 flex-col rounded-2xl border border-gray-200 bg-white shadow-sm">
            <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3">
              <div>
                <div className="text-sm font-semibold text-gray-900">
                  Streaming response
                </div>
                <div className="text-xs text-gray-500">
                  NDJSON tokens + trace events
                </div>
              </div>
              <div className="flex items-center gap-2 text-xs text-gray-600">
                {runId ? (
                  <button
                    type="button"
                    onClick={onDownloadPdf}
                    disabled={state === "running" || isDownloading}
                    className="rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-xs font-medium text-gray-700 transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {isDownloading ? "Preparing PDF..." : "Download PDF"}
                  </button>
                ) : null}
                {state === "running" ? (
                  <>
                    <Spinner />
                    <span>Streaming…</span>
                  </>
                ) : (
                  <span className="text-gray-400">idle</span>
                )}
              </div>
            </div>

            <div className="min-h-0 flex-1 overflow-auto p-4">
              {error ? (
                <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">
                  <div className="font-semibold">Error</div>
                  <div className="mt-1 whitespace-pre-wrap">{error}</div>
                </div>
              ) : null}

              {answer ? (
                <pre className="whitespace-pre-wrap break-words text-sm leading-relaxed text-gray-900">
                  {answer}
                </pre>
              ) : state === "running" ? (
                <div className="text-sm text-gray-500">
                  Waiting for first tokens…
                </div>
              ) : (
                <div className="text-sm text-gray-500">
                  Enter a query and click Run.
                </div>
              )}

              {reportSources.length > 0 ? (
                <div className="mt-6 rounded-xl border border-gray-200 bg-gray-50 p-3">
                  <div className="text-xs font-semibold uppercase tracking-wide text-gray-600">
                    Citations
                  </div>
                  <ul className="mt-2 space-y-1">
                    {reportSources.map((src, idx) => (
                      <li key={`${src.url ?? "src"}-${idx}`} className="text-sm">
                        {src.url ? (
                          <a
                            href={src.url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-blue-700 underline decoration-blue-300 underline-offset-2 hover:text-blue-800"
                          >
                            {src.title || src.url || `Source ${idx + 1}`}
                          </a>
                        ) : (
                          <span className="text-gray-700">{src.title || `Source ${idx + 1}`}</span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              <div ref={answerEndRef} />
            </div>
          </div>
        </section>

        <aside className="min-h-0">
          <TracePanel
            events={events}
            selectedId={selectedEventId}
            onSelect={setSelectedEventId}
            agentStatuses={agentStatuses}
          />
        </aside>
      </main>

      <footer className="mx-auto max-w-6xl px-6 pb-10 text-xs text-gray-500">
        <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
          <div className="font-semibold text-gray-900">Backend integration</div>
          <div className="mt-1">
            By default, the frontend uses a mock stream. To connect the real
            backend stream, set{" "}
            <span className="font-medium">BACKEND_STREAM_PATH</span> and{" "}
            <span className="font-medium">NEXT_PUBLIC_BACKEND_URL</span>.
          </div>
        </div>
      </footer>
    </div>
  );
}

