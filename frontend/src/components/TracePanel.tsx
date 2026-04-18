import { clsx } from "clsx";
import type { TraceEvent } from "@/lib/streaming";

function formatTime(ts: number) {
  try {
    return new Date(ts).toLocaleTimeString();
  } catch {
    return "";
  }
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
  const agents = ["Planner", "Search", "Analyst", "Critic", "Editor"];

  function badge(status: "pending" | "running" | "done") {
    if (status === "done") return "border-emerald-200 bg-emerald-50 text-emerald-700";
    if (status === "running") return "border-blue-200 bg-blue-50 text-blue-700";
    return "border-gray-200 bg-gray-50 text-gray-500";
  }

  return (
    <div className="flex h-full min-h-0 flex-col rounded-2xl border border-gray-200 bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3">
        <div>
          <div className="text-sm font-semibold text-gray-900">Agent trace</div>
          <div className="text-xs text-gray-500">{events.length} events</div>
        </div>
        <div className="text-xs text-gray-400">live</div>
      </div>

      <div className="grid min-h-0 flex-1 grid-rows-[auto_1fr_auto]">
        <div className="border-b border-gray-100 p-3">
          <div className="text-xs font-semibold text-gray-900">Agent progress</div>
          <div className="mt-2 grid grid-cols-1 gap-2">
            {agents.map((agent) => {
              const status = agentStatuses[agent] ?? "pending";
              return (
                <div
                  key={agent}
                  className="flex items-center justify-between rounded-lg border border-gray-100 px-2 py-1.5"
                >
                  <span className="text-xs font-medium text-gray-800">{agent}</span>
                  <span
                    className={clsx(
                      "rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                      badge(status),
                    )}
                  >
                    {status}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        <div className="min-h-0 overflow-auto p-2">
          {events.length === 0 ? (
            <div className="px-2 py-6 text-center text-sm text-gray-500">
              Trace events will appear here.
            </div>
          ) : (
            <ol className="space-y-1">
              {events.map((e, i) => (
                <li key={e.id}>
                  <button
                    type="button"
                    onClick={() => onSelect(e.id)}
                    className={clsx(
                      "w-full rounded-lg border px-3 py-2 text-left transition",
                      selectedId === e.id
                        ? "border-blue-200 bg-blue-50"
                        : "border-transparent hover:border-gray-200 hover:bg-gray-50",
                    )}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="truncate text-xs font-medium text-gray-900">
                        Step {i + 1}: {e.type}
                      </div>
                      <div className="shrink-0 text-[11px] text-gray-500">
                        {formatTime(e.ts)}
                      </div>
                    </div>
                    {e.payload !== undefined ? (
                      <div className="mt-1 line-clamp-2 text-[11px] text-gray-600">
                        {typeof e.payload === "string"
                          ? e.payload
                          : JSON.stringify(e.payload)}
                      </div>
                    ) : null}
                  </button>
                </li>
              ))}
            </ol>
          )}
        </div>

        <div className="border-t border-gray-100 p-3">
          <div className="text-xs font-semibold text-gray-900">Selected</div>
          <pre className="mt-2 max-h-44 overflow-auto rounded-xl border border-gray-200 bg-gray-50 p-3 text-[11px] leading-relaxed text-gray-800">
            {selected ? JSON.stringify(selected, null, 2) : "—"}
          </pre>
        </div>
      </div>
    </div>
  );
}

