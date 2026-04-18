from __future__ import annotations

import json
import os
import random
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class PlannerError(RuntimeError):
    pass


class PlannerRetryableError(PlannerError):
    pass


@dataclass(frozen=True)
class PlannerConfig:
    base_url: str = OPENROUTER_BASE_URL
    model: str = "deepseek/deepseek-chat"
    max_attempts: int = 5
    initial_backoff_s: float = 0.5
    max_backoff_s: float = 8.0
    timeout_s: float = 45.0


def _sleep_with_jitter(seconds: float) -> None:
    time.sleep(seconds + random.uniform(0, min(0.25, seconds)))


def _retry(
    fn: Callable[[], Any],
    *,
    max_attempts: int,
    initial_backoff_s: float,
    max_backoff_s: float,
) -> tuple[Any, int]:
    attempt = 1
    backoff = max(0.0, initial_backoff_s)
    last_err: Optional[BaseException] = None

    while attempt <= max_attempts:
        try:
            return fn(), attempt
        except PlannerRetryableError as e:
            last_err = e
        except Exception as e:  # noqa: BLE001
            last_err = e
            raise

        if attempt >= max_attempts:
            break

        _sleep_with_jitter(min(max_backoff_s, backoff))
        backoff = min(max_backoff_s, max(initial_backoff_s, backoff * 2))
        attempt += 1

    raise PlannerError(f"planner_failed_after_retries: {last_err}") from last_err


def _coerce_to_plan_dict(obj: Any) -> dict[str, Any]:
    if isinstance(obj, dict):
        return obj
    raise PlannerError("planner_invalid_json: expected object at top-level")


def _validate_plan_shape(plan: dict[str, Any]) -> dict[str, Any]:
    plan.setdefault("version", "1")
    if "goal" not in plan or not isinstance(plan["goal"], str) or not plan["goal"].strip():
        raise PlannerError("planner_invalid_json: missing non-empty 'goal'")

    subtasks = plan.get("subtasks")
    if not isinstance(subtasks, list) or not subtasks:
        raise PlannerError("planner_invalid_json: missing non-empty 'subtasks' list")

    for i, st in enumerate(subtasks):
        if not isinstance(st, dict):
            raise PlannerError(f"planner_invalid_json: subtask[{i}] must be an object")
        if "id" not in st:
            st["id"] = f"task_{i+1}"
        if "title" not in st or not isinstance(st["title"], str) or not st["title"].strip():
            raise PlannerError(f"planner_invalid_json: subtask[{i}] missing non-empty 'title'")
        st.setdefault("description", "")
        st.setdefault("depends_on", [])
        st.setdefault("acceptance_criteria", [])
        st.setdefault("priority", "medium")

    return plan


class PlannerAgent:
    """
    Breaks a user query into structured subtasks (JSON only).

    Uses OpenRouter via OpenAI-compatible API.
    """

    def __init__(self, *, config: Optional[PlannerConfig] = None, api_key: Optional[str] = None):
        if config is None:
            env_model = os.getenv("PLANNER_MODEL") or os.getenv("OPENROUTER_MODEL")
            env_base_url = os.getenv("OPENROUTER_BASE_URL") or OPENROUTER_BASE_URL
            self.config = PlannerConfig(
                base_url=env_base_url,
                model=(env_model or "deepseek/deepseek-chat"),
            )
        else:
            self.config = config
        self.api_key = api_key

    def plan(self, user_query: str, *, context: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        if not isinstance(user_query, str) or not user_query.strip():
            raise PlannerError("planner_input_invalid: user_query must be a non-empty string")

        context = context or {}

        def _run_once() -> dict[str, Any]:
            try:
                from openai import APIConnectionError, APIError, APITimeoutError, RateLimitError
            except Exception as e:  # noqa: BLE001
                raise PlannerError("openai_sdk_missing: add 'openai' to requirements and install dependencies") from e

            from clients.openrouter import get_openrouter_client

            api_key = self.api_key or os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                raise PlannerError("openrouter_api_key_missing: set OPENROUTER_API_KEY")

            try:
                client = get_openrouter_client(api_key=api_key, base_url=self.config.base_url)
            except RuntimeError as e:
                raise PlannerError(str(e)) from e

            system = (
                "You are a Planner Agent. Break the user's request into a small, actionable set of subtasks.\n"
                "Return JSON only (no markdown, no prose) matching this shape:\n"
                "{\n"
                '  "version": "1",\n'
                '  "goal": string,\n'
                '  "subtasks": [\n'
                "    {\n"
                '      "id": string,\n'
                '      "title": string,\n'
                '      "description": string,\n'
                '      "depends_on": string[],\n'
                '      "acceptance_criteria": string[],\n'
                '      "priority": "low"|"medium"|"high"\n'
                "    }\n"
                "  ]\n"
                "}\n"
                "Rules:\n"
                "- Include 3-8 subtasks.\n"
                "- Each subtask must be independently testable.\n"
                "- Use depends_on to express ordering.\n"
            )
            user = {"query": user_query, "context": context}

            try:
                resp = _request_plan(
                    client=client,
                    model=self.config.model,
                    system=system,
                    user_payload=json.dumps(user, ensure_ascii=False),
                    timeout_s=self.config.timeout_s,
                )
            except (RateLimitError, APITimeoutError, APIConnectionError) as e:
                raise PlannerRetryableError(str(e)) from e
            except APIError as e:
                status = getattr(e, "status_code", None)
                msg = str(e).lower()
                if status in (408, 409, 425, 429, 500, 502, 503, 504):
                    raise PlannerRetryableError(str(e)) from e
                if any(m in msg for m in ("quota", "billing", "insufficient")):
                    raise PlannerError(f"planner_openrouter_quota_error: {e}") from e
                raise PlannerError(f"planner_openrouter_error: {e}") from e
            except Exception as e:  # noqa: BLE001
                msg = str(e).lower()
                if any(m in msg for m in ("quota", "billing", "insufficient")):
                    raise PlannerError(f"planner_openrouter_quota_error: {e}") from e
                if any(m in msg for m in ("timeout", "rate limit", "temporarily", "unavailable")):
                    raise PlannerRetryableError(str(e)) from e
                raise PlannerError(f"planner_openrouter_error: {e}") from e

            content = (resp.choices[0].message.content or "").strip()
            if not content:
                raise PlannerRetryableError("planner_empty_response")
            content = _extract_json_block(_strip_code_fences(content))

            try:
                parsed = json.loads(content)
            except json.JSONDecodeError as e:
                raise PlannerRetryableError(f"planner_non_json_response: {e}") from e

            plan = _validate_plan_shape(_coerce_to_plan_dict(parsed))
            plan.setdefault("meta", {})
            plan["meta"].setdefault("model", self.config.model)
            plan["meta"].setdefault("attempts", None)
            plan["meta"].setdefault("request_id", getattr(resp, "id", None))
            return plan

        result, attempts = _retry(
            _run_once,
            max_attempts=self.config.max_attempts,
            initial_backoff_s=self.config.initial_backoff_s,
            max_backoff_s=self.config.max_backoff_s,
        )
        if isinstance(result, dict):
            result.setdefault("meta", {})
            result["meta"]["attempts"] = attempts
        return result


def _request_plan(*, client: Any, model: str, system: str, user_payload: str, timeout_s: float) -> Any:
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_payload},
    ]
    try:
        return client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.2,
            timeout=timeout_s,
        )
    except Exception:
        # Fallback for providers/models that don't support response_format=json_object.
        return client.chat.completions.create(
            model=model,
            messages=messages
            + [
                {
                    "role": "user",
                    "content": "Return only valid JSON, no markdown fences, no explanations.",
                }
            ],
            temperature=0.2,
            timeout=timeout_s,
        )


def _strip_code_fences(text: str) -> str:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


def _extract_json_block(text: str) -> str:
    s = (text or "").strip()
    if not s:
        return s
    if s.startswith("{") and s.endswith("}"):
        return s
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        return s[start : end + 1]
    return s
