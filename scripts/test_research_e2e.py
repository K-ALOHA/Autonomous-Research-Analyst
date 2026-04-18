#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import os
import pathlib
import sys
from typing import Any

import httpx
from dotenv import load_dotenv

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.main import app


def _die(message: str, code: int = 1) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


def _require_env() -> None:
    missing = [k for k in ("OPENROUTER_API_KEY", "TAVILY_API_KEY") if not os.getenv(k, "").strip()]
    if missing:
        _die(
            f"Missing required environment variables: {', '.join(missing)}.\n"
            "Set them in .env, then re-run this test.",
            2,
        )


def _has_nonempty(s: Any) -> bool:
    return isinstance(s, str) and bool(s.strip())


async def _run(query: str) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver", timeout=180.0) as client:
        resp = await client.post(
            "/research",
            json={"query": query, "stream": False, "include_traces": True},
        )

    if resp.status_code != 200:
        _die(f"/research returned {resp.status_code}: {resp.text}")

    try:
        payload = resp.json()
    except Exception as exc:  # noqa: BLE001
        _die(f"/research returned non-JSON payload: {exc}\nBody:\n{resp.text}")

    run_id = payload.get("run_id")
    result = payload.get("result") or {}
    traces = payload.get("traces") or []

    if not _has_nonempty(run_id):
        _die("Invalid response: missing run_id")
    if not isinstance(result, dict):
        _die("Invalid response: result must be an object")
    if not isinstance(traces, list):
        _die("Invalid response: traces must be a list")

    report_markdown = result.get("report_markdown")
    report_sources = result.get("report_sources")
    errors = result.get("errors")

    if not _has_nonempty(report_markdown):
        _die("Invalid response: result.report_markdown is empty")
    if not isinstance(report_sources, list):
        _die("Invalid response: result.report_sources must be a list")
    if not isinstance(errors, list):
        _die("Invalid response: result.errors must be a list")

    if result.get("failed") and errors:
        combined = " | ".join(str(e.get("error", "")) for e in errors if isinstance(e, dict))
        lowered = combined.lower()
        if any(m in lowered for m in ("quota", "billing", "resource_exhausted", "limit: 0")):
            _die(
                "OpenRouter quota/billing blocker detected during live execution.\n"
                f"Planner error: {combined}",
                3,
            )

    saw_plan = False
    saw_search = False
    saw_analyst = False
    saw_critic = False
    saw_editor = _has_nonempty(report_markdown)
    search_result_items = 0

    for st in traces:
        if not isinstance(st, dict):
            continue
        if isinstance(st.get("plan"), dict):
            saw_plan = True
        if isinstance(st.get("search_query_results"), list):
            saw_search = True
            for qr in st.get("search_query_results") or []:
                if isinstance(qr, dict):
                    results = qr.get("results")
                    if isinstance(results, list):
                        search_result_items += len(results)
        if _has_nonempty(st.get("analyst_answer")):
            saw_analyst = True
        if st.get("critic_confidence") is not None:
            saw_critic = True

    if not saw_plan:
        _die("Planner stage not observed in traces.")
    if not saw_search:
        _die("Search stage not observed in traces.")
    if search_result_items <= 0:
        _die("Tavily returned zero search items; cannot validate search integration.")
    if not saw_analyst:
        _die("Analyst stage not observed in traces (OpenRouter output missing).")
    if not saw_critic:
        _die("Critic stage not observed in traces.")
    if not saw_editor:
        _die("Editor stage not observed in final result.")

    summary = {
        "run_id": run_id,
        "query": query,
        "checks": {
            "openrouter_integration": saw_analyst,
            "tavily_results": search_result_items > 0,
            "agent_sequence": all([saw_plan, saw_search, saw_analyst, saw_critic, saw_editor]),
            "structured_output": True,
        },
        "counts": {
            "trace_states": len(traces),
            "search_results": search_result_items,
            "report_sources": len(report_sources),
        },
    }
    print(json.dumps(summary, indent=2))


def main() -> None:
    load_dotenv()
    _require_env()
    query = "Latest US and global EV market outlook with key risks and growth drivers"
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:]).strip() or query
    asyncio.run(_run(query))


if __name__ == "__main__":
    main()
