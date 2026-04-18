import { NextResponse } from "next/server";

export const runtime = "nodejs";

function jsonLine(obj: unknown) {
  return JSON.stringify(obj) + "\n";
}

async function mockStream(query: string) {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      const id = () => crypto.randomUUID();

      controller.enqueue(
        encoder.encode(
          jsonLine({
            type: "trace",
            event: { id: id(), ts: Date.now(), type: "run.started", payload: { query } },
          }),
        ),
      );

      const text =
        "Mock stream (set NEXT_PUBLIC_BACKEND_URL + BACKEND_STREAM_PATH to use the real backend).\n\n" +
        `Query: ${query}\n\n` +
        "This UI supports token streaming + trace events.\n";

      let i = 0;
      const interval = setInterval(() => {
        if (i >= text.length) {
          clearInterval(interval);
          controller.enqueue(
            encoder.encode(
              jsonLine({
                type: "trace",
                event: {
                  id: id(),
                  ts: Date.now(),
                  type: "run.completed",
                  payload: { ok: true },
                },
              }),
            ),
          );
          controller.enqueue(encoder.encode(jsonLine({ type: "final" })));
          controller.close();
          return;
        }

        // emit token chunks
        controller.enqueue(
          encoder.encode(jsonLine({ type: "token", text: text.slice(i, i + 6) })),
        );
        if (i % 24 === 0) {
          controller.enqueue(
            encoder.encode(
              jsonLine({
                type: "trace",
                event: {
                  id: id(),
                  ts: Date.now(),
                  type: "agent.step",
                  payload: { step: Math.floor(i / 24) + 1 },
                },
              }),
            ),
          );
        }
        i += 6;
      }, 50);
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "application/x-ndjson; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
    },
  });
}

export async function POST(req: Request) {
  const body = await req.json().catch(() => null);
  const query = typeof body?.query === "string" ? body.query : "";

  const backendUrl =
    process.env.NEXT_PUBLIC_BACKEND_URL ||
    process.env.BACKEND_URL ||
    "http://localhost:8000";
  const streamPath = process.env.BACKEND_STREAM_PATH || "/research";

  // If backend stream isn't configured, fall back to mock streaming so the
  // frontend remains usable end-to-end.
  if (!process.env.BACKEND_STREAM_PATH) {
    return mockStream(query);
  }

  const url = new URL(streamPath, backendUrl).toString();

  const upstream = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query,
      stream: true,
      include_traces: true,
    }),
  }).catch((err) => {
    return NextResponse.json(
      { error: "Failed to reach backend", details: String(err) },
      { status: 502 },
    );
  });

  if (upstream instanceof NextResponse) return upstream;
  if (!upstream.ok) {
    const text = await upstream.text().catch(() => "");
    return NextResponse.json(
      { error: "Backend error", status: upstream.status, body: text },
      { status: 502 },
    );
  }

  // Normalize backend SSE into frontend NDJSON contract.
  const contentType = upstream.headers.get("content-type") || "";
  if (contentType.includes("text/event-stream") && upstream.body) {
    return new Response(sseToNdjson(upstream.body), {
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

          let payload: any;
          try {
            payload = JSON.parse(raw);
          } catch {
            eventName = "";
            return;
          }

          if (payload?.type === "meta") {
            controller.enqueue(
              encoder.encode(
                jsonLine({
                  type: "trace",
                  event: {
                    id: String(payload.run_id || crypto.randomUUID()),
                    ts: Date.now(),
                    type: "run.started",
                    payload,
                  },
                }),
              ),
            );
          } else if (payload?.type === "trace") {
            const step = Number(payload.step || 0);
            const ts = Date.parse(String(payload.ts || "")) || Date.now();
            controller.enqueue(
              encoder.encode(
                jsonLine({
                  type: "trace",
                  event: {
                    id: `${payload.run_id || "run"}:${step || crypto.randomUUID()}`,
                    ts,
                    type: "workflow.trace",
                    payload: payload.state ?? payload,
                  },
                }),
              ),
            );
          } else if (payload?.type === "result") {
            const report = String(payload.result?.report_markdown || "");
            if (report) {
              controller.enqueue(encoder.encode(jsonLine({ type: "token", text: report })));
            }
            controller.enqueue(
              encoder.encode(
                jsonLine({
                  type: "final",
                  data: {
                    ...(payload.result ?? {}),
                    run_id: payload.run_id,
                  },
                }),
              ),
            );
          } else if (payload?.type === "error") {
            controller.enqueue(
              encoder.encode(
                jsonLine({
                  type: "error",
                  message: String(payload.error?.message || "Backend error"),
                  details: payload.error ?? payload,
                }),
              ),
            );
          } else if (eventName === "result") {
            controller.enqueue(encoder.encode(jsonLine({ type: "final", data: payload })));
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
