export type TraceEvent = {
  id: string;
  ts: number;
  type: string;
  payload?: unknown;
};

export type FinalResultPayload = {
  run_id?: string;
  report_markdown?: string;
  report_sources?: Array<{ title?: string; url?: string }>;
  failed?: boolean;
  errors?: unknown[];
};

export type StreamMessage =
  | { type: "token"; text: string }
  | { type: "trace"; event: TraceEvent }
  | { type: "final"; text?: string; data?: FinalResultPayload | unknown }
  | { type: "error"; message: string; details?: unknown };

function safeJsonParse(line: string): unknown | undefined {
  try {
    return JSON.parse(line);
  } catch {
    return undefined;
  }
}

/**
 * Parses a newline-delimited stream where each line is either:
 * - JSON: {"type":"token","text":"..."} or {"type":"trace",...}
 * - Plain text: treated as token chunks
 *
 * This intentionally supports multiple backend formats so the frontend is usable
 * while the API contract stabilizes.
 */
export async function* readNdjsonOrTextStream(
  response: Response,
): AsyncGenerator<StreamMessage, void, void> {
  if (!response.body) {
    yield { type: "error", message: "No response body (streaming not supported)." };
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buf += decoder.decode(value, { stream: true });

    while (true) {
      const nl = buf.indexOf("\n");
      if (nl === -1) break;

      const line = buf.slice(0, nl).trimEnd();
      buf = buf.slice(nl + 1);
      if (!line.trim()) continue;

      // Attempt JSON line
      const parsed = safeJsonParse(line);
      if (parsed && typeof parsed === "object") {
        const msg = parsed as Partial<StreamMessage> & Record<string, unknown>;
        if (msg.type === "token" && typeof (msg as any).text === "string") {
          yield { type: "token", text: (msg as any).text };
          continue;
        }
        if (msg.type === "trace" && typeof (msg as any).event === "object") {
          const e = (msg as any).event as any;
          yield {
            type: "trace",
            event: {
              id: String(e.id ?? crypto.randomUUID()),
              ts: Number(e.ts ?? Date.now()),
              type: String(e.type ?? "event"),
              payload: e.payload,
            },
          };
          continue;
        }
        if (msg.type === "final") {
          yield { type: "final", text: typeof (msg as any).text === "string" ? (msg as any).text : undefined, data: (msg as any).data };
          continue;
        }
        if (msg.type === "error") {
          yield { type: "error", message: String((msg as any).message ?? "Error"), details: (msg as any).details };
          continue;
        }
      }

      // Fallback: treat as token chunk
      yield { type: "token", text: line + "\n" };
    }
  }

  if (buf.trim()) {
    yield { type: "token", text: buf };
  }
}

