from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional

from fastapi import APIRouter
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from backend.graph.runtime import extract_result, get_compiled_workflow
from backend.models.api import ErrorEnvelope
from backend.services.run_store import run_store
from backend.utils.config import get_settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health", tags=["health"])
def health() -> dict[str, str]:
    settings = get_settings()
    return {"status": "ok", "environment": settings.environment, "app": settings.app_name}


class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    stream: bool = Field(default=True, description="If true, respond as SSE.")
    include_traces: bool = Field(default=True, description="If true, emit intermediate trace events.")
    options: dict[str, Any] = Field(default_factory=dict, description="Reserved for future workflow options.")


def _missing_runtime_env() -> list[str]:
    settings = get_settings()
    missing: list[str] = []
    if not settings.openrouter_api_key:
        missing.append("OPENROUTER_API_KEY")
    if not settings.tavily_api_key:
        missing.append("TAVILY_API_KEY")
    return missing


def _sse(data: dict[str, Any], *, event: Optional[str] = None) -> bytes:
    payload = json.dumps(data, ensure_ascii=False)
    if event:
        return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")
    return f"data: {payload}\n\n".encode("utf-8")


@router.post("/research", tags=["research"])
async def research(req: ResearchRequest, request: Request):
    """
    Trigger the full LangGraph workflow.

    - Streams as Server-Sent Events (SSE) by default.
    - Emits workflow state snapshots as "trace" events.
    - Finishes with a "result" event containing the final report.
    """
    run_id = str(uuid.uuid4())
    missing_env = _missing_runtime_env()
    if missing_env:
        err = ErrorEnvelope(
            code="missing_runtime_config",
            message="Missing required environment variables for research workflow.",
            details={"missing": missing_env},
            request_id=run_id,
        )
        if req.stream:
            async def error_stream() -> AsyncIterator[bytes]:
                yield _sse({"type": "error", "run_id": run_id, "error": err.model_dump(mode="json")}, event="error")

            return StreamingResponse(
                error_stream(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=err.model_dump(mode="json"),
        )

    async def run_stream() -> AsyncIterator[bytes]:
        started_at = datetime.now(timezone.utc).isoformat()
        yield _sse({"type": "meta", "run_id": run_id, "started_at": started_at}, event="meta")

        try:
            workflow = get_compiled_workflow()
        except Exception as e:  # noqa: BLE001
            err = ErrorEnvelope(
                code="workflow_init_failed",
                message=str(e) or "failed to initialize workflow",
                details={},
                request_id=run_id,
            )
            yield _sse({"type": "error", "error": err.model_dump(mode="json")}, event="error")
            return

        last_state: dict[str, Any] = {}
        step = 0

        try:
            stream_mode = "values"
            async for state in workflow.astream({"user_query": req.query}, stream_mode=stream_mode):
                if isinstance(state, dict):
                    last_state = state
                step += 1
                if req.include_traces:
                    yield _sse(
                        {
                            "type": "trace",
                            "run_id": run_id,
                            "step": step,
                            "ts": datetime.now(timezone.utc).isoformat(),
                            "state": state,
                        },
                        event="trace",
                    )

            result = extract_result(last_state or {})
            run_store.save(run_id=run_id, query=req.query, result=result)
            yield _sse({"type": "result", "run_id": run_id, "result": result}, event="result")
        except HTTPException as e:
            err = ErrorEnvelope(
                code="http_error",
                message=str(e.detail) if e.detail else "request failed",
                details={"status_code": e.status_code},
                request_id=run_id,
            )
            yield _sse({"type": "error", "run_id": run_id, "error": err.model_dump(mode="json")}, event="error")
        except Exception as e:  # noqa: BLE001
            logger.exception("research_failed", extra={"run_id": run_id})
            err = ErrorEnvelope(
                code="research_failed",
                message=f"{type(e).__name__}: {e}",
                details={},
                request_id=run_id,
            )
            yield _sse({"type": "error", "run_id": run_id, "error": err.model_dump(mode="json")}, event="error")

    if req.stream:
        return StreamingResponse(
            run_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                # Helpful when behind certain proxies.
                "X-Accel-Buffering": "no",
            },
        )

    # Non-streaming JSON mode: collect traces in-memory (if requested).
    traces: list[dict[str, Any]] = []
    last_state: dict[str, Any] = {}
    try:
        workflow = get_compiled_workflow()
        async for state in workflow.astream({"user_query": req.query}, stream_mode="values"):
            if isinstance(state, dict):
                last_state = state
            if req.include_traces:
                traces.append(state if isinstance(state, dict) else {"value": state})
        result = extract_result(last_state or {})
        run_store.save(run_id=run_id, query=req.query, result=result)
        return {
            "run_id": run_id,
            "result": result,
            "traces": traces if req.include_traces else [],
        }
    except Exception as e:  # noqa: BLE001
        err = ErrorEnvelope(
            code="research_failed",
            message=f"{type(e).__name__}: {e}",
            details={},
            request_id=run_id,
        )
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=err.model_dump(mode="json"))


@router.get("/research/{run_id}/export/pdf", tags=["research"])
async def export_research_pdf(run_id: str):
    stored = run_store.get(run_id)
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"run_id '{run_id}' not found or expired",
        )

    try:
        from backend.services.pdf_export import render_report_pdf

        pdf_bytes, filename = render_report_pdf(
            run_id=stored.run_id, query=stored.query, result=stored.result
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("pdf_export_failed", extra={"run_id": run_id})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF generation failed: {type(e).__name__}: {e}",
        ) from e

    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers=headers,
    )
