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
 * Map one NDJSON line (complete JSON object) to a stream message.
 */
function messageFromParsed(parsed: unknown): StreamMessage | undefined {
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    return undefined;
  }
  const msg = parsed as Record<string, unknown>;

  if (msg.type === "token" && typeof msg.text === "string") {
    return { type: "token", text: msg.text };
  }
  if (msg.type === "trace" && msg.event && typeof msg.event === "object") {
    const e = msg.event as Record<string, unknown>;
    return {
      type: "trace",
      event: {
        id: String(e.id ?? crypto.randomUUID()),
        ts: Number(e.ts ?? Date.now()),
        type: String(e.type ?? "event"),
        payload: e.payload,
      },
    };
  }
  if (msg.type === "final") {
    return {
      type: "final",
      text: typeof msg.text === "string" ? msg.text : undefined,
      data: msg.data,
    };
  }
  if (msg.type === "error") {
    return {
      type: "error",
      message: String(msg.message ?? "Error"),
      details: msg.details,
    };
  }
  return undefined;
}

/**
 * Try to interpret a full line as JSON NDJSON; otherwise treat as plain text chunk.
 */
function consumeLine(line: string): StreamMessage {
  const trimmed = line.replace(/\r$/, "").trimEnd();
  if (!trimmed) {
    return { type: "token", text: "" };
  }

  const parsed = safeJsonParse(trimmed);
  if (parsed !== undefined) {
    const m = messageFromParsed(parsed);
    if (m) return m;
  }

  return { type: "token", text: trimmed + "\n" };
}

/**
 * Parses a newline-delimited stream where each line is either:
 * - JSON: {"type":"token","text":"..."} or {"type":"trace",...}
 * - Plain text: treated as token chunks
 *
 * Uses ReadableStream.getReader() + TextDecoder with { stream: true } so UTF-8
 * split across chunk boundaries is handled correctly. Buffers until a newline
 * so large JSON lines are parsed atomically.
 */
export async function* readNdjsonOrTextStream(
  response: Response,
): AsyncGenerator<StreamMessage, void, void> {
  if (!response.body) {
    yield { type: "error", message: "No response body (streaming not supported)." };
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buf = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buf += decoder.decode(value, { stream: true });

      while (true) {
        const nl = buf.indexOf("\n");
        if (nl === -1) break;

        const line = buf.slice(0, nl);
        buf = buf.slice(nl + 1);

        const msg = consumeLine(line);
        if (msg.type === "token" && msg.text === "") continue;
        yield msg;
      }
    }

    // End of stream: flush decoder (surrogate pairs, etc.)
    const tail = decoder.decode();
    if (tail) {
      buf += tail;
    }

    // Remaining buffer: often a final NDJSON line with no trailing newline
    if (buf.length > 0) {
      const msg = consumeLine(buf);
      if (!(msg.type === "token" && msg.text === "")) {
        yield msg;
      }
    }
  } finally {
    reader.releaseLock();
  }
}
