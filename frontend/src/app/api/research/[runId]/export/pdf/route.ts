import { NextResponse } from "next/server";

export const runtime = "nodejs";

export async function GET(
  _req: Request,
  context: { params: Promise<{ runId: string }> },
) {
  const { runId } = await context.params;
  if (!runId?.trim()) {
    return NextResponse.json({ error: "Missing run id" }, { status: 400 });
  }

  const backendUrl =
    process.env.NEXT_PUBLIC_BACKEND_URL ||
    process.env.BACKEND_URL ||
    "http://localhost:8000";
  const url = new URL(`/research/${encodeURIComponent(runId)}/export/pdf`, backendUrl).toString();

  const upstream = await fetch(url, { method: "GET" }).catch((err) => {
    return NextResponse.json(
      { error: "Failed to reach backend", details: String(err) },
      { status: 502 },
    );
  });
  if (upstream instanceof NextResponse) return upstream;

  if (!upstream.ok) {
    const body = await upstream.text().catch(() => "");
    return NextResponse.json(
      { error: "Backend error", status: upstream.status, body },
      { status: 502 },
    );
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition":
        upstream.headers.get("content-disposition") || `attachment; filename="research-${runId}.pdf"`,
      "Cache-Control": "no-cache, no-transform",
    },
  });
}
