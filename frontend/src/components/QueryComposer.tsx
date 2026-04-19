"use client";

import { motion } from "framer-motion";
import { clsx } from "clsx";

function SparkIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      aria-hidden
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.847a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.847.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456Z"
      />
    </svg>
  );
}

export function QueryComposer({
  query,
  onChange,
  onRun,
  onStop,
  running,
  canSubmit,
}: {
  query: string;
  onChange: (v: string) => void;
  onRun: () => void;
  onStop: () => void;
  running: boolean;
  canSubmit: boolean;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, delay: 0.05, ease: [0.22, 1, 0.36, 1] }}
      className="rounded-2xl border border-white/[0.08] bg-white/[0.04] p-1.5 shadow-[0_12px_48px_rgba(0,0,0,0.35)] backdrop-blur-2xl"
    >
      <label className="sr-only" htmlFor="research-query">
        Research query
      </label>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-stretch">
        <div className="relative min-w-0 flex-1">
          <div className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-violet-300/90">
            <SparkIcon className="h-5 w-5" />
          </div>
          <input
            id="research-query"
            value={query}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) onRun();
            }}
            placeholder="Ask a deep research question…"
            disabled={running}
            className={clsx(
              "h-14 w-full rounded-xl border border-white/[0.08] bg-black/30 pl-12 pr-4 text-sm text-zinc-100 shadow-inner outline-none transition",
              "placeholder:text-zinc-500",
              "focus:border-violet-500/40 focus:shadow-[0_0_0_3px_rgba(139,92,246,0.2),0_0_28px_rgba(56,189,248,0.12)]",
              "disabled:cursor-not-allowed disabled:opacity-60",
            )}
          />
        </div>
        <div className="flex shrink-0 gap-2 sm:w-auto">
          {running ? (
            <motion.button
              type="button"
              layout
              onClick={onStop}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className="inline-flex h-14 flex-1 items-center justify-center rounded-xl border border-white/15 bg-white/[0.06] px-5 text-sm font-medium text-zinc-200 transition hover:bg-white/[0.1] sm:flex-initial"
            >
              Stop
            </motion.button>
          ) : (
            <motion.button
              type="button"
              layout
              onClick={onRun}
              disabled={!canSubmit}
              whileHover={canSubmit ? { scale: 1.03, boxShadow: "0 0 32px rgba(139,92,246,0.35)" } : {}}
              whileTap={canSubmit ? { scale: 0.98 } : {}}
              className={clsx(
                "inline-flex h-14 flex-1 items-center justify-center gap-2 rounded-xl px-6 text-sm font-semibold text-white shadow-lg transition sm:min-w-[120px] sm:flex-initial",
                "bg-gradient-to-r from-violet-600 via-blue-600 to-cyan-500",
                "disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none",
              )}
            >
              <SparkIcon className="h-4 w-4 opacity-90" />
              Run
            </motion.button>
          )}
        </div>
      </div>
      <p className="px-2 pb-1 pt-2 text-center text-[11px] text-zinc-500 sm:text-left sm:pl-3">
        <kbd className="rounded border border-white/10 bg-white/[0.05] px-1.5 py-0.5 font-mono text-[10px] text-zinc-400">
          ⌘ / Ctrl
        </kbd>{" "}
        +{" "}
        <kbd className="rounded border border-white/10 bg-white/[0.05] px-1.5 py-0.5 font-mono text-[10px] text-zinc-400">
          Enter
        </kbd>{" "}
        to run · Streaming NDJSON preserved
      </p>
    </motion.div>
  );
}
