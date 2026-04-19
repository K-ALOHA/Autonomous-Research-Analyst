"use client";

import type { RefObject } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { clsx } from "clsx";
import { ResearchMarkdown } from "@/components/ResearchMarkdown";

function Spinner({ className }: { className?: string }) {
  return (
    <span
      className={clsx(
        "inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/25 border-t-cyan-300",
        className,
      )}
      aria-label="Loading"
    />
  );
}

function ReportSkeleton() {
  return (
    <div className="shimmer-bg space-y-4 rounded-xl border border-white/[0.06] bg-white/[0.02] p-6">
      <div className="h-8 w-2/3 rounded-lg bg-white/[0.06]" />
      <div className="space-y-2">
        <div className="h-3 w-full rounded bg-white/[0.05]" />
        <div className="h-3 w-full rounded bg-white/[0.05]" />
        <div className="h-3 w-4/5 rounded bg-white/[0.05]" />
      </div>
      <div className="h-24 rounded-lg bg-white/[0.04]" />
      <div className="space-y-2 pt-2">
        <div className="h-3 w-full rounded bg-white/[0.05]" />
        <div className="h-3 w-[92%] rounded bg-white/[0.05]" />
        <div className="h-3 w-full rounded bg-white/[0.05]" />
      </div>
    </div>
  );
}

export function ReportViewer({
  error,
  answer,
  running,
  runId,
  isDownloading,
  onDownloadPdf,
  reportSources,
  answerEndRef,
}: {
  error: string | null;
  answer: string;
  running: boolean;
  runId: string;
  isDownloading: boolean;
  onDownloadPdf: () => void;
  reportSources: Array<{ title?: string; url?: string }>;
  answerEndRef: RefObject<HTMLDivElement | null>;
}) {
  const showSkeleton = running && !answer.trim();
  const showEmpty = !running && !answer.trim() && !error;

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, delay: 0.08, ease: [0.22, 1, 0.36, 1] }}
      className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border border-white/[0.08] bg-white/[0.03] shadow-[0_12px_48px_rgba(0,0,0,0.4)] backdrop-blur-xl"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.06] px-4 py-3.5 sm:px-5">
        <div>
          <h2 className="text-sm font-semibold tracking-tight text-white">Research document</h2>
          <p className="text-xs text-zinc-500">Premium markdown · live tokens</p>
        </div>
        <div className="flex items-center gap-2">
          {runId ? (
            <motion.button
              type="button"
              onClick={onDownloadPdf}
              disabled={running || isDownloading}
              whileHover={{ scale: running || isDownloading ? 1 : 1.02 }}
              whileTap={{ scale: running || isDownloading ? 1 : 0.98 }}
              className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-white/[0.06] px-3 py-1.5 text-xs font-medium text-zinc-200 shadow-inner transition hover:border-violet-500/30 hover:bg-white/[0.1] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isDownloading ? <Spinner /> : null}
              {isDownloading ? "Preparing…" : "Export PDF"}
            </motion.button>
          ) : null}
          <div className="flex items-center gap-2 rounded-full border border-white/10 bg-black/30 px-3 py-1 text-[11px] text-zinc-400">
            {running ? (
              <>
                <Spinner />
                <span className="text-zinc-300">Streaming</span>
              </>
            ) : (
              <span>Ready</span>
            )}
          </div>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-auto px-4 py-5 sm:px-6 sm:py-6">
        <AnimatePresence mode="wait">
          {error ? (
            <motion.div
              key="error"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.3 }}
              className="rounded-xl border border-red-500/25 bg-red-500/10 p-4 text-sm text-red-100 backdrop-blur-md"
            >
              <div className="font-semibold text-red-200">Something went wrong</div>
              <div className="mt-2 whitespace-pre-wrap text-red-100/90">{error}</div>
            </motion.div>
          ) : null}
        </AnimatePresence>

        {showSkeleton ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.35 }}
          >
            <ReportSkeleton />
          </motion.div>
        ) : null}

        {showEmpty ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="rounded-xl border border-dashed border-white/10 bg-white/[0.02] p-8 text-center"
          >
            <p className="text-sm text-zinc-400">
              Enter a research question to generate a cited, structured report with a live agent trace.
            </p>
          </motion.div>
        ) : null}

        {answer.trim() ? (
          <div className="mx-auto max-w-[52rem]">
            <div className={running ? "report-stream-pulse" : undefined}>
              <ResearchMarkdown markdown={answer} />
            </div>
            {running ? (
              <span
                className="streaming-cursor ml-0.5 inline-block h-5 w-px translate-y-0.5 bg-gradient-to-b from-violet-400 to-cyan-400 align-middle"
                aria-hidden
              />
            ) : null}
          </div>
        ) : null}

        {reportSources.length > 0 ? (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
            className="mx-auto mt-10 max-w-[52rem] rounded-xl border border-white/[0.08] bg-white/[0.03] p-4 backdrop-blur-md"
          >
            <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-500">
              Sources
            </div>
            <ul className="mt-3 space-y-2">
              {reportSources.map((src, idx) => (
                <li key={`${src.url ?? "src"}-${idx}`} className="text-sm">
                  {src.url ? (
                    <a
                      href={src.url}
                      target="_blank"
                      rel="noreferrer"
                      className="font-medium text-cyan-300 underline decoration-cyan-500/35 underline-offset-4 transition hover:text-cyan-200"
                    >
                      {src.title || src.url || `Source ${idx + 1}`}
                    </a>
                  ) : (
                    <span className="text-zinc-300">{src.title || `Source ${idx + 1}`}</span>
                  )}
                </li>
              ))}
            </ul>
          </motion.div>
        ) : null}
        <div ref={answerEndRef} />
      </div>
    </motion.div>
  );
}
