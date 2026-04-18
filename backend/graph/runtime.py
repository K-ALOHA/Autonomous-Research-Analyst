from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Iterable, Mapping, Optional

from backend.agents.analyst import AnalystAgent
from backend.agents.critic import CriticAgent
from backend.agents.editor import EditorAgent
from backend.agents.planner import PlannerAgent, PlannerConfig
from backend.agents.search import SearchAgent
from backend.clients.openrouter import get_openrouter_client
from backend.graph.workflow import WorkflowAgents, build_workflow
from backend.utils.config import get_settings


def _to_openrouter_messages(messages: Iterable[Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for m in list(messages or []):
        content = getattr(m, "content", None)
        if content is None:
            content = str(m)

        mtype = (getattr(m, "type", None) or "").lower()
        role = "user"
        if mtype in {"system"}:
            role = "system"
        elif mtype in {"human", "user"}:
            role = "user"
        elif mtype in {"ai", "assistant"}:
            role = "assistant"
        else:
            name = (m.__class__.__name__ or "").lower()
            if "system" in name:
                role = "system"
            elif "human" in name:
                role = "user"
            elif "ai" in name:
                role = "assistant"

        out.append({"role": role, "content": str(content)})
    return out


class OpenRouterChatModel:
    """
    Minimal LangChain-compatible chat model wrapper used by `AnalystAgent`.

    Uses OpenRouter with the OpenAI-compatible SDK client.
    """

    def __init__(
        self,
        *,
        model: str = "deepseek/deepseek-chat",
        api_key: Optional[str] = None,
        base_url: str = "https://openrouter.ai/api/v1",
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self._client = None

    def _get_client(self):
        if self._client is None:
            self._client = get_openrouter_client(api_key=self.api_key, base_url=self.base_url)
        return self._client

    def invoke(self, input: Any, **kwargs: Any) -> Any:
        messages = _to_openrouter_messages(input if isinstance(input, list) else [input])
        resp = self._get_client().chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=_pop_float(kwargs, "temperature"),
            timeout=kwargs.pop("timeout", None),
        )
        content = (resp.choices[0].message.content or "").strip()
        return type("LCMessage", (), {"content": content})()

    async def ainvoke(self, input: Any, **kwargs: Any) -> Any:
        messages = _to_openrouter_messages(input if isinstance(input, list) else [input])
        temperature = _pop_float(kwargs, "temperature")
        timeout = kwargs.pop("timeout", None)
        import anyio

        def _run() -> Any:
            resp = self._get_client().chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                timeout=timeout,
            )
            content = (resp.choices[0].message.content or "").strip()
            return type("LCMessage", (), {"content": content})()

        return await anyio.to_thread.run_sync(_run)


def _pop_float(kwargs: dict[str, Any], key: str) -> Optional[float]:
    value = kwargs.pop(key, None)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@lru_cache(maxsize=1)
def get_compiled_workflow():
    """
    Lazily construct and cache the compiled LangGraph workflow.

    This is process-local. If you run multiple Uvicorn workers, each worker will
    build its own instance.
    """
    settings = get_settings()
    planner = PlannerAgent(
        config=PlannerConfig(
            base_url=settings.openrouter_base_url,
            model=settings.planner_model,
        ),
        api_key=settings.openrouter_api_key,
    )
    search = SearchAgent(api_key=settings.tavily_api_key)
    analyst_llm = OpenRouterChatModel(
        model=settings.analyst_model or (os.getenv("ANALYST_MODEL") or "deepseek/deepseek-chat"),
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
    )
    analyst = AnalystAgent(analyst_llm)
    critic = CriticAgent()
    editor = EditorAgent()

    agents = WorkflowAgents(planner=planner, search=search, analyst=analyst, critic=critic, editor=editor)
    return build_workflow(agents=agents)


def extract_result(state: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "report_markdown": state.get("report_markdown") or "",
        "report_sources": state.get("report_sources") or [],
        "failed": bool(state.get("failed")),
        "errors": state.get("errors") or [],
    }
