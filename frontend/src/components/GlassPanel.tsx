import { clsx } from "clsx";
import type { ReactNode } from "react";

export function GlassPanel({
  children,
  className,
  padding = "p-5",
}: {
  children: ReactNode;
  className?: string;
  padding?: string;
}) {
  return (
    <div
      className={clsx(
        "rounded-2xl border border-white/[0.08] bg-white/[0.03] shadow-[0_8px_40px_rgba(0,0,0,0.45)] backdrop-blur-xl",
        padding,
        className,
      )}
    >
      {children}
    </div>
  );
}
