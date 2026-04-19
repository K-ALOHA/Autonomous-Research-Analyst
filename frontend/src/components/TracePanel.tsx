"use client";

import { clsx } from "clsx";
import { AnimatePresence, motion } from "framer-motion";
import type { TraceEvent } from "@/lib/streaming";

function formatTime(ts: number) {
  try {
    return new Date(ts).toLocaleTimeString();
  } catch {
    return "";
  }
}

function AgentIcon({ name }: { name: string }) {
  const common = "h-4 w-4 shrink-0";
  switch (name) {
    case "Planner":
      return (
        <svg className={common} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 0 0 2.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 0 0-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75 2.25 2.25 0 0 0-.1-.664m-5.8 0A2.251 2.251 0 0 1 13.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25ZM6.75 12h.008v.008H6.75V12Zm0 3h.008v.008H6.75V15Zm0 3h.008v.008H6.75V18Z" />
        </svg>
      );
    case "Search":
      return (
        <svg className={common} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden>
          <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
        </svg>
      );
    case "Analyst":
      return (
        <svg className={common} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z" />
        </svg>
      );
    case "Critic":
      return (
        <svg className={common} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z" />
        </svg>
      );
    case "Editor":
      return (
        <svg className={common} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden>
          <path strokeLinecap="round" strokeLinejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10" />
        </svg>
      );
    default:
      return (
        <svg className={common} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
        </svg>
      );
  }
}

function StatusPill({ status }: { status: "pending" | "running" | "done" }) {
  const label = status === "done" ? "Done" : status === "running" ? "Active" : "Pending";
  return (
    <motion.span
      layout
      initial={false}
      animate={{
        scale: status === "running" ? [1, 1.03, 1] : 1,
        boxShadow:
          status === "done"
            ? "0 0 20px rgba(52,211,153,0.25)"
            : status === "running"
              ? "0 0 18px rgba(56,189,248,0.22)"
              : "none",
      }}
      transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      className={clsx(
        "rounded-full border px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        status === "done" && "border-emerald-500/35 bg-emerald-500/15 text-emerald-200",
        status === "running" && "border-sky-500/40 bg-sky-500/15 text-sky-200",
        status === "pending" && "border-white/10 bg-white/[0.04] text-zinc-500",
      )}
    >
      {label}
    </motion.span>
  );
}

export function TracePanel({
  events,
  selectedId,
  onSelect,
  agentStatuses,
}: {
  events: TraceEvent[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  agentStatuses: Record<string, "pending" | "running" | "done">;
}) {
  const selected = selectedId ? events.find((e) => e.id === selectedId) : null;
  const agents = ["Planner", "Search", "Analyst", "Critic", "Editor"] as const;

  return (
    <motion.div
      initial={{ opacity: 0, x: 14 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.45, delay: 0.06, ease: [0.22, 1, 0.36, 1] }}
      className="flex max-h-[min(100vh-7rem,920px)] min-h-[420px] flex-col overflow-hidden rounded-2xl border border-white/[0.08] bg-white/[0.03] shadow-[0_12px_48px_rgba(0,0,0,0.4)] backdrop-blur-xl lg:sticky lg:top-24 lg:self-start"
    >
      <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-3.5">
        <div>
          <h2 className="text-sm font-semibold tracking-tight text-white">Agent trace</h2>
          <p className="text-xs text-zinc-500">{events.length} events · live</p>
        </div>
        <span className="rounded-full border border-emerald-500/25 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-200">
          Orchestrator
        </span>
      </div>

      <div className="grid min-h-0 flex-1 grid-rows-[auto_minmax(0,1fr)_auto]">
        <div className="border-b border-white/[0.06] p-3.5">
          <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-zinc-500">Pipeline</div>
          <div className="mt-3 space-y-2">
            {agents.map((agent) => {
              const status = agentStatuses[agent] ?? "pending";
              return (
                <motion.div
                  key={agent}
                  layout
                  className={clsx(
                    "flex items-center justify-between gap-3 rounded-xl border px-3 py-2 transition-colors",
                    status === "done" && "border-emerald-500/20 bg-emerald-500/[0.06]",
                    status === "running" && "border-sky-500/25 bg-sky-500/[0.07]",
                    status === "pending" && "border-white/[0.06] bg-black/20",
                  )}
                >
                  <div className="flex min-w-0 items-center gap-2.5">
                    <span
                      className={clsx(
                        "inline-flex rounded-lg p-1.5",
                        status === "done" && "text-emerald-200",
                        status === "running" && "text-sky-200",
                        status === "pending" && "text-zinc-500",
                      )}
                    >
                      <AgentIcon name={agent} />
                    </span>
                    <span className="truncate text-xs font-medium text-zinc-200">{agent}</span>
                  </div>
                  <StatusPill status={status} />
                </motion.div>
              );
            })}
          </div>
        </div>

        <div className="min-h-0 overflow-auto p-2.5">
          {events.length === 0 ? (
            <div className="rounded-xl border border-dashed border-white/10 bg-white/[0.02] px-3 py-10 text-center text-xs text-zinc-500">
              Trace events appear here as the graph executes.
            </div>
          ) : (
            <ol className="space-y-1.5">
              {events.map((e, i) => (
                <li key={e.id}>
                  <motion.button
                    type="button"
                    layout
                    onClick={() => onSelect(e.id)}
                    whileHover={{ scale: 1.01 }}
                    whileTap={{ scale: 0.99 }}
                    className={clsx(
                      "w-full rounded-xl border px-3 py-2.5 text-left transition",
                      selectedId === e.id
                        ? "border-violet-500/35 bg-violet-500/10 shadow-[0_0_24px_rgba(139,92,246,0.12)]"
                        : "border-transparent bg-transparent hover:border-white/10 hover:bg-white/[0.04]",
                    )}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="truncate text-xs font-semibold text-zinc-100">
                        Step {i + 1}: {e.type}
                      </div>
                      <div className="shrink-0 text-[10px] text-zinc-500">{formatTime(e.ts)}</div>
                    </div>
                    {e.payload !== undefined ? (
                      <div className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-zinc-500">
                        {typeof e.payload === "string" ? e.payload : JSON.stringify(e.payload)}
                      </div>
                    ) : null}
                  </motion.button>
                </li>
              ))}
            </ol>
          )}
        </div>

        <div className="border-t border-white/[0.06] p-3.5">
          <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-zinc-500">Selected payload</div>
          <pre className="mt-2 max-h-48 overflow-auto rounded-xl border border-white/[0.08] bg-black/40 p-3 text-[10px] leading-relaxed text-zinc-300 backdrop-blur-md">
            <AnimatePresence mode="wait">
              <motion.code
                key={selected?.id ?? "none"}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.25 }}
                className="block whitespace-pre-wrap break-words font-mono"
              >
                {selected ? JSON.stringify(selected, null, 2) : "—"}
              </motion.code>
            </AnimatePresence>
          </pre>
        </div>
      </div>
    </motion.div>
  );
}
