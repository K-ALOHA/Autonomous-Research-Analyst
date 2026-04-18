from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field


class ErrorEnvelope(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: Optional[str] = None


class RunCreateRequest(BaseModel):
    input: dict[str, Any]
    options: dict[str, Any] = Field(default_factory=dict)


class RunCreateResponse(BaseModel):
    run_id: str
    status: Literal["queued", "running"]
    created_at: datetime


class RunOut(BaseModel):
    run_id: str
    status: Literal["queued", "running", "succeeded", "failed", "cancelled", "cancelling"]
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    input: dict[str, Any]
    options: dict[str, Any]
    progress: dict[str, Any] = Field(default_factory=dict)
    final_artifact_id: Optional[str] = None
    error: Optional[dict[str, Any]] = None


class CancelResponse(BaseModel):
    run_id: str
    status: Literal["cancelling", "cancelled"]


class ArtifactOut(BaseModel):
    artifact_id: str
    run_id: str
    type: str
    mime: str
    size_bytes: int
    created_at: datetime


class ArtifactGetResponse(BaseModel):
    artifact: ArtifactOut
    content: Optional[Union[str, dict[str, Any]]] = None


class EventOut(BaseModel):
    event_id: str
    run_id: str
    ts: datetime
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
