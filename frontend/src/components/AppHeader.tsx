"use client";

import { motion } from "framer-motion";

export function AppHeader() {
  return (
    <motion.header
      initial={{ opacity: 0, y: -12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      className="sticky top-0 z-40 border-b border-white/[0.06] bg-[#0a0a0a]/75 backdrop-blur-xl"
    >
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-4 md:px-8">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="inline-flex h-2 w-2 shrink-0 rounded-full bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.65)]" />
            <p className="truncate text-[11px] font-semibold uppercase tracking-[0.2em] text-zinc-500">
              Live orchestration
            </p>
          </div>
          <h1 className="mt-1 truncate bg-gradient-to-r from-violet-300 via-sky-300 to-cyan-300 bg-clip-text text-xl font-semibold tracking-tight text-transparent md:text-2xl">
            Autonomous Research Analyst
          </h1>
        </div>
        <div className="hidden shrink-0 items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-xs text-zinc-400 shadow-inner sm:flex">
          <span className="font-medium text-zinc-300">Multi-agent</span>
          <span className="text-white/20">·</span>
          <span>Stream + trace</span>
        </div>
      </div>
      <div
        className="h-px w-full bg-gradient-to-r from-transparent via-violet-500/50 via-sky-500/40 to-transparent"
        aria-hidden
      />
    </motion.header>
  );
}
