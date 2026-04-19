"use client";

import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";
import type { ReactNode } from "react";

const ease = [0.22, 1, 0.36, 1] as const;

function FadeBlock({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.38, ease }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

const markdownComponents: Components = {
  h1: ({ children, ...props }) => (
    <FadeBlock className="not-prose mb-6 mt-2">
      <h1
        {...props}
        className="bg-gradient-to-r from-violet-200 via-sky-200 to-cyan-200 bg-clip-text text-3xl font-bold tracking-tight text-transparent md:text-4xl"
      >
        {children}
      </h1>
      <div className="mt-4 h-px w-full bg-gradient-to-r from-violet-500/40 via-sky-500/30 to-transparent" />
    </FadeBlock>
  ),
  h2: ({ children, ...props }) => (
    <FadeBlock className="not-prose mb-4 mt-10">
      <h2
        {...props}
        className="border-b border-white/[0.08] pb-2 text-2xl font-semibold tracking-tight md:text-[1.65rem]"
      >
        <span className="bg-gradient-to-r from-violet-300 to-cyan-300 bg-clip-text text-transparent">
          {children}
        </span>
      </h2>
    </FadeBlock>
  ),
  h3: ({ children, ...props }) => (
    <FadeBlock className="not-prose mb-3 mt-8">
      <h3 {...props} className="text-lg font-semibold tracking-tight md:text-xl">
        <span className="bg-gradient-to-r from-violet-200/95 to-sky-200/90 bg-clip-text text-transparent">
          {children}
        </span>
      </h3>
    </FadeBlock>
  ),
  hr: () => (
    <motion.div
      initial={{ opacity: 0, scaleX: 0.92 }}
      animate={{ opacity: 1, scaleX: 1 }}
      transition={{ duration: 0.4, ease }}
      className="not-prose my-10"
      aria-hidden
    >
      <div className="h-px w-full bg-gradient-to-r from-transparent via-white/15 to-transparent" />
    </motion.div>
  ),
  p: ({ children }) => (
    <motion.p
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.32, ease }}
      className="leading-[1.75] text-zinc-300"
    >
      {children}
    </motion.p>
  ),
  ul: ({ children }) => (
    <motion.ul
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.32, ease }}
      className="my-4 space-y-2 text-zinc-300 marker:text-violet-400/90"
    >
      {children}
    </motion.ul>
  ),
  ol: ({ children }) => (
    <motion.ol
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.32, ease }}
      className="my-4 list-decimal space-y-2 pl-6 text-zinc-300 marker:text-sky-400/90"
    >
      {children}
    </motion.ol>
  ),
  li: ({ children, ...props }) => (
    <li {...props} className="pl-1 leading-relaxed">
      {children}
    </li>
  ),
  blockquote: ({ children }) => (
    <motion.blockquote
      initial={{ opacity: 0, x: -6 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.35, ease }}
      className="not-prose my-6 border-l-2 border-violet-500/50 bg-white/[0.03] py-3 pl-4 pr-3 text-zinc-300 italic backdrop-blur-sm"
    >
      {children}
    </motion.blockquote>
  ),
  a: ({ children, href, ...props }) => (
    <a
      {...props}
      href={href}
      className="font-medium text-cyan-300 underline decoration-cyan-500/40 underline-offset-4 transition hover:text-cyan-200 hover:decoration-cyan-400/70"
    >
      {children}
    </a>
  ),
  strong: ({ children, ...props }) => (
    <strong
      {...props}
      className="font-semibold text-cyan-50/95 [text-shadow:0_0_24px_rgba(34,211,238,0.15)]"
    >
      {children}
    </strong>
  ),
  code: ({ className, children, ...props }) => {
    const isFenced = typeof className === "string" && className.includes("language-");
    if (isFenced) {
      return (
        <code {...props} className={className}>
          {children}
        </code>
      );
    }
    const isLikelyBlock = String(children ?? "").includes("\n");
    if (isLikelyBlock) {
      return (
        <code {...props} className="block bg-transparent p-0 font-mono text-sm leading-relaxed text-zinc-200">
          {children}
        </code>
      );
    }
    return (
      <code
        {...props}
        className="rounded-md border border-white/10 bg-black/40 px-1.5 py-0.5 font-mono text-[0.9em] text-violet-200"
      >
        {children}
      </code>
    );
  },
  pre: ({ children }) => (
    <motion.pre
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease }}
      className="not-prose my-6 overflow-x-auto rounded-xl border border-white/[0.1] bg-black/55 p-4 text-sm leading-relaxed text-zinc-200 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] backdrop-blur-md"
    >
      {children}
    </motion.pre>
  ),
  table: ({ children, ...props }) => (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease }}
      className="not-prose my-6 overflow-x-auto rounded-xl border border-white/[0.08] bg-white/[0.02]"
    >
      <table {...props} className="w-full border-collapse text-left text-sm text-zinc-300">
        {children}
      </table>
    </motion.div>
  ),
  thead: ({ children, ...props }) => (
    <thead {...props} className="border-b border-white/10 bg-white/[0.04] text-zinc-100">
      {children}
    </thead>
  ),
  th: ({ children, ...props }) => (
    <th {...props} className="px-3 py-2 text-xs font-semibold uppercase tracking-wide">
      {children}
    </th>
  ),
  td: ({ children, ...props }) => (
    <td {...props} className="border-t border-white/[0.06] px-3 py-2">
      {children}
    </td>
  ),
};

export function ResearchMarkdown({ markdown }: { markdown: string }) {
  return (
    <article
      className={[
        "prose prose-invert max-w-none",
        "prose-p:text-[1.05rem] prose-p:leading-[1.8]",
        "prose-li:marker:text-violet-400",
        "prose-headings:scroll-mt-24",
      ].join(" ")}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
        {markdown}
      </ReactMarkdown>
    </article>
  );
}
