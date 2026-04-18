import { NextRequest, NextResponse } from "next/server";

/**
 * Node.js runtime: reliable streaming proxy to FastAPI on Vercel (recommended).
 * Switch to `export const runtime = "edge"` only if you need Edge; this handler
 * uses Web Streams + fetch and is compatible with both.
 */
export const runtime = "nodejs";

/** Avoid accidental static caching of the proxy response. */
export const dynamic = "force-dynamic";

function jsonLine(obj: unknown) {
  return JSON.stringify(obj) + "\n";
}

type ResolveResult =
  | { ok: true; apiUrl: string }
  | { ok: false; missing: string[] };

/**
 * Read backend URL from env (Vercel: Project → Settings → Environment Variables).
 * Never throws; trims and validates.
 */
function resolveBackendApiUrl(): ResolveResult {
  const baseUrl = process.env.NEXT_PUBLIC_BACKEND_URL?.trim();
  const streamPath = process.env.NEXT_PUBLIC_BACKEND_STREAM_PATH?.trim();
  if (!baseUrl || !streamPath) {
    const missing: string[] = [];
    if (!baseUrl) missing.push("NEXT_PUBLIC_BACKEND_URL");
    if (!streamPath) missing.push("NEXT_PUBLIC_BACKEND_STREAM_PATH");
    return { ok: false, missing };
  }

  const normalizedBase = baseUrl.replace(/\/+$/, "");
  const normalizedPath = streamPath.startsWith("/") ? streamPath : `/${streamPath}`;
  return { ok: true, apiUrl: `${normalizedBase}${normalizedPath}` };
}

type JsonError = { error: string; message: string; missing?: string[] };

function jsonError(payload: JsonError, status: number) {
  return NextResponse.json(payload, { status });
}

/**
 * Parse incoming JSON and forward to backend with defaults merged in.
 * Non-JSON bodies are forwarded as-is (e.g. future clients).
 */
async function buildUpstreamBody(req: NextRequest): Promise<
  | { ok: true; body: string; contentType: string }
  | { ok: false; response: NextResponse }
> {
  const contentType = req.headers.get("content-type") || "";

  if (contentType.includes("application/json")) {
    const raw = await req.json().catch(() => null);
    if (raw === null || typeof raw !== "object" || Array.isArray(raw)) {
      return {
        ok: false,
        response: jsonError(
          {
            error: "invalid_request",
            message: "Request body must be a JSON object.",
          },
          400,
        ),
      };
    }

    const o = raw as Record<string, unknown>;
    const query = typeof o.query === "string" ? o.query.trim() : "";
    if (!query) {
      return {
        ok: false,
        response: jsonError(
          {
            error: "invalid_request",
            message: 'Field "query" is required and must be a non-empty string.',
          },
          400,
        ),
      };
    }

    const forwarded = {
      ...o,
      query,
      stream: o.stream !== false,
      include_traces: o.include_traces !== false,
    };

    return {
      ok: true,
      body: JSON.stringify(forwarded),
      contentType: "application/json",
    };
  }

  const text = await req.text();
  if (!text.trim()) {
    return {
      ok: false,
      response: jsonError(
        {
          error: "invalid_request",
          message: "Request body is empty or not supported. Send JSON with a \"query\" field.",
        },
        400,
      ),
    };
  }

  return { ok: true, body: text, contentType: contentType || "application/octet-stream" };
}

export async function POST(req: NextRequest) {
  const resolved = resolveBackendApiUrl();
  if (!resolved.ok) {
    return jsonError(
      {
        error: "backend_not_configured",
        message:
          "Set NEXT_PUBLIC_BACKEND_URL and NEXT_PUBLIC_BACKEND_STREAM_PATH in the environment (Vercel: Project Settings → Environment Variables).",
        missing: resolved.missing,
      },
      503,
    );
  }

  const built = await buildUpstreamBody(req);
  if (!built.ok) {
    return built.response;
  }

  const headers: HeadersInit = {
    "Content-Type": built.contentType,
  };
  const accept = req.headers.get("accept");
  if (accept) {
    headers.Accept = accept;
  }

  let upstream: Response;
  try {
    upstream = await fetch(resolved.apiUrl, {
      method: "POST",
      headers,
      body: built.body,
      signal: req.signal,
    });
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "Failed to connect to upstream backend.";
    return jsonError(
      {
        error: "upstream_unreachable",
        message,
      },
      502,
    );
  }

  if (!upstream.ok) {
    const text = await upstream.text().catch(() => "");
    let detail = text;
    try {
      const parsed = JSON.parse(text) as { message?: string; detail?: string };
      if (typeof parsed?.message === "string") {
        detail = parsed.message;
      }
    } catch {
      // keep raw text
    }
    const status =
      upstream.status >= 400 && upstream.status < 600 ? upstream.status : 502;
    return jsonError(
      {
        error: "upstream_error",
        message: detail || `Backend returned status ${upstream.status}.`,
      },
      status,
    );
  }

  const contentType = upstream.headers.get("content-type") || "";

  // FastAPI StreamingResponse: SSE → normalize to NDJSON for the client parser.
  if (contentType.includes("text/event-stream") && upstream.body) {
    return new Response(sseToNdjson(upstream.body), {
      headers: {
        "Content-Type": "application/x-ndjson; charset=utf-8",
        "Cache-Control": "no-cache, no-transform",
      },
    });
  }

  // NDJSON / JSONL: pass through for the same client parser.
  if (
    upstream.body &&
    (contentType.includes("ndjson") ||
      contentType.includes("application/jsonl") ||
      contentType.includes("application/x-ndjson"))
  ) {
    return new Response(upstream.body, {
      headers: {
        "Content-Type": "application/x-ndjson; charset=utf-8",
        "Cache-Control": "no-cache, no-transform",
      },
    });
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type":
        upstream.headers.get("content-type") || "application/octet-stream",
      "Cache-Control": "no-cache, no-transform",
    },
  });
}

function sseToNdjson(input: ReadableStream<Uint8Array>): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  const decoder = new TextDecoder();

  return new ReadableStream<Uint8Array>({
    start(controller) {
      void (async () => {
        const reader = input.getReader();
        let buf = "";
        let eventName = "";
        let dataLines: string[] = [];

        const flushEvent = () => {
          if (!dataLines.length) {
            eventName = "";
            return;
          }

          const raw = dataLines.join("\n");
          dataLines = [];

          let payload: unknown;
          try {
            payload = JSON.parse(raw);
          } catch {
            eventName = "";
            return;
          }

          const p = payload as Record<string, unknown>;

          if (p?.type === "meta") {
            controller.enqueue(
              encoder.encode(
                jsonLine({
                  type: "trace",
                  event: {
                    id: String(p.run_id ?? crypto.randomUUID()),
                    ts: Date.now(),
                    type: "run.started",
                    payload: p,
                  },
                }),
              ),
            );
          } else if (p?.type === "trace") {
            const step = Number(p.step ?? 0);
            const ts = Date.parse(String(p.ts ?? "")) || Date.now();
            controller.enqueue(
              encoder.encode(
                jsonLine({
                  type: "trace",
                  event: {
                    id: `${p.run_id ?? "run"}:${step || crypto.randomUUID()}`,
                    ts,
                    type: "workflow.trace",
                    payload: p.state ?? p,
                  },
                }),
              ),
            );
          } else if (p?.type === "result") {
            const result = p.result as Record<string, unknown> | undefined;
            const report = String(result?.report_markdown ?? "");
            if (report) {
              controller.enqueue(encoder.encode(jsonLine({ type: "token", text: report })));
            }
            controller.enqueue(
              encoder.encode(
                jsonLine({
                  type: "final",
                  data: {
                    ...(result ?? {}),
                    run_id: p.run_id,
                  },
                }),
              ),
            );
          } else if (p?.type === "error") {
            const errObj = p.error as Record<string, unknown> | undefined;
            controller.enqueue(
              encoder.encode(
                jsonLine({
                  type: "error",
                  message: String(errObj?.message ?? "Backend error"),
                  details: p.error ?? p,
                }),
              ),
            );
          } else if (eventName === "result") {
            controller.enqueue(encoder.encode(jsonLine({ type: "final", data: p })));
          }

          eventName = "";
        };

        try {
          while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            buf += decoder.decode(value, { stream: true });

            while (true) {
              const nl = buf.indexOf("\n");
              if (nl === -1) break;
              const line = buf.slice(0, nl).replace(/\r$/, "");
              buf = buf.slice(nl + 1);

              if (!line) {
                flushEvent();
                continue;
              }
              if (line.startsWith("event:")) {
                eventName = line.slice("event:".length).trim();
                continue;
              }
              if (line.startsWith("data:")) {
                dataLines.push(line.slice("data:".length).trimStart());
              }
            }
          }

          if (buf.trim()) {
            dataLines.push(buf.trim());
          }
          flushEvent();
        } finally {
          controller.close();
        }
      })();
    },
  });
}
