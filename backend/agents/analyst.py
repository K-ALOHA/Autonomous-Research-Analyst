from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Iterable, Optional, Protocol, Sequence

if TYPE_CHECKING:  # pragma: no cover
    from langchain_core.messages import BaseMessage
    from langchain_core.prompts import ChatPromptTemplate
else:  # Avoid import-time hard dependency in minimal environments.
    BaseMessage = Any  # type: ignore[assignment,misc]
    ChatPromptTemplate = Any  # type: ignore[assignment,misc]

from pydantic import BaseModel, Field


class SupportsChatModel(Protocol):
    """Minimal protocol for a LangChain chat model."""

    def invoke(self, input: Any, **kwargs: Any) -> BaseMessage: ...

    async def ainvoke(self, input: Any, **kwargs: Any) -> BaseMessage: ...


@dataclass(frozen=True)
class NormalizedSearchResult:
    title: str
    url: Optional[str] = None
    snippet: Optional[str] = None
    content: Optional[str] = None
    score: Optional[float] = None
    source: Optional[str] = None

    @staticmethod
    def from_any(item: Any) -> "NormalizedSearchResult":
        if isinstance(item, NormalizedSearchResult):
            return item
        if isinstance(item, dict):
            return NormalizedSearchResult(
                title=str(item.get("title") or item.get("name") or "Untitled"),
                url=item.get("url") or item.get("link"),
                snippet=item.get("snippet") or item.get("summary") or item.get("description"),
                content=item.get("content") or item.get("text"),
                score=item.get("score"),
                source=item.get("source") or item.get("provider"),
            )
        # Pydantic models (e.g. backend.agents.search.SearchResult) often support model_dump().
        dump = getattr(item, "model_dump", None)
        if callable(dump):
            try:
                data = dump()
                if isinstance(data, dict):
                    return NormalizedSearchResult.from_any(data)
            except Exception:
                pass
        return NormalizedSearchResult(title=str(item))


class AnalystContext(BaseModel):
    """Context the analyst should stay consistent with across calls."""

    question: str = Field(..., description="The user question / research objective.")
    audience: str = Field(default="general", description="Who the output is written for.")
    prior_insights: list[str] = Field(default_factory=list, description="Rolling insights to keep consistent.")
    constraints: list[str] = Field(default_factory=list, description="Hard requirements, e.g. scope/time/format.")
    assumptions: list[str] = Field(default_factory=list, description="Assumptions already made upstream.")


class AnalystOutput(BaseModel):
    answer: str
    key_insights: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list, description="URLs or source identifiers used.")


class AnalystAgent:
    """
    Analyst agent: combines multiple search results into context-aware insights.

    - Uses LLM summarization via a LangChain-compatible chat model
      (OpenAI-compatible clients, including OpenRouter, work via runtime wiring).
    - Maintains context awareness by carrying forward a rolling context object.
    """

    def __init__(
        self,
        llm: SupportsChatModel,
        *,
        max_chunk_chars: int = 10_000,
        max_results_per_chunk: int = 8,
        temperature: Optional[float] = None,
        model_kwargs: Optional[dict[str, Any]] = None,
    ) -> None:
        self._llm = llm
        self._max_chunk_chars = max(2_000, int(max_chunk_chars))
        self._max_results_per_chunk = max(1, int(max_results_per_chunk))
        self._temperature = temperature
        self._model_kwargs = model_kwargs or {}

        self._context: Optional[AnalystContext] = None
        self._map_prompt: Any = None
        self._reduce_prompt: Any = None

    def _ensure_prompts(self) -> None:
        if self._map_prompt is not None and self._reduce_prompt is not None:
            return
        try:
            from langchain_core.prompts import ChatPromptTemplate as _ChatPromptTemplate
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(
                "AnalystAgent requires 'langchain-core' to be installed (cannot import langchain_core)."
            ) from e

        self._map_prompt = _ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are an expert research analyst. Summarize the provided search results "
                    "faithfully and compactly. Do not invent facts. If results conflict, note it.",
                ),
                (
                    "human",
                    "Research question:\n{question}\n\n"
                    "Audience:\n{audience}\n\n"
                    "Constraints:\n{constraints}\n\n"
                    "Prior insights to stay consistent with:\n{prior_insights}\n\n"
                    "Search results:\n{results}\n\n"
                    "Return:\n"
                    "- 5-10 bullet insights (grounded in results)\n"
                    "- 0-5 contradictions/uncertainties\n"
                    "- source list (urls or source identifiers)\n",
                ),
            ]
        )

        self._reduce_prompt = _ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are an expert research analyst. Combine partial summaries into a single "
                    "coherent, context-aware answer. Prefer high-signal, actionable insights. "
                    "Do not invent facts; keep claims tied to sources.",
                ),
                (
                    "human",
                    "Research question:\n{question}\n\n"
                    "Audience:\n{audience}\n\n"
                    "Constraints:\n{constraints}\n\n"
                    "Prior insights to stay consistent with:\n{prior_insights}\n\n"
                    "Partial summaries:\n{partials}\n\n"
                    "Return JSON only (no markdown fences) with this exact shape:\n"
                    "{{\n"
                    '  "answer": string,\n'
                    '  "key_insights": string[],\n'
                    '  "open_questions": string[],\n'
                    '  "citations": string[]\n'
                    "}}\n",
                ),
            ]
        )

    def set_context(self, context: AnalystContext) -> None:
        self._context = context

    def get_context(self) -> Optional[AnalystContext]:
        return self._context

    def update_context(self, *, add_prior_insights: Optional[Iterable[str]] = None) -> None:
        if not self._context:
            return
        if add_prior_insights:
            self._context.prior_insights.extend([s for s in add_prior_insights if s and s.strip()])

    def analyze(
        self,
        results: Sequence[Any],
        *,
        context: Optional[AnalystContext] = None,
        question: Optional[str] = None,
        audience: Optional[str] = None,
        constraints: Optional[Sequence[str]] = None,
        prior_insights: Optional[Sequence[str]] = None,
    ) -> AnalystOutput:
        """Synchronous analysis entrypoint."""
        self._ensure_prompts()
        ctx = self._resolve_context(
            context=context,
            question=question,
            audience=audience,
            constraints=constraints,
            prior_insights=prior_insights,
        )
        normalized = [NormalizedSearchResult.from_any(r) for r in (results or [])]
        chunks = list(self._chunk_results(normalized))

        partials: list[str] = []
        citations: set[str] = set()
        for chunk in chunks:
            rendered = self._render_results(chunk)
            msg = self._invoke_prompt(
                self._map_prompt,
                question=ctx.question,
                audience=ctx.audience,
                constraints=self._render_list(ctx.constraints),
                prior_insights=self._render_list(ctx.prior_insights),
                results=rendered,
            )
            text = (msg.content or "").strip()
            partials.append(text)
            citations.update(self._extract_citations(chunk))

        final_msg = self._invoke_prompt(
            self._reduce_prompt,
            question=ctx.question,
            audience=ctx.audience,
            constraints=self._render_list(ctx.constraints),
            prior_insights=self._render_list(ctx.prior_insights),
            partials="\n\n---\n\n".join(partials) if partials else "(no results)",
        )
        parsed = self._parse_structured_output((final_msg.content or "").strip())
        merged_citations = set(parsed.citations) | citations
        out = AnalystOutput(
            answer=parsed.answer,
            key_insights=parsed.key_insights,
            open_questions=parsed.open_questions,
            citations=sorted(merged_citations),
        )
        self._context = ctx
        # Light-touch context carry-forward: keep the final answer as a prior insight.
        if out.answer:
            self.update_context(add_prior_insights=[out.answer[:1200]])
        return out

    async def aanalyze(
        self,
        results: Sequence[Any],
        *,
        context: Optional[AnalystContext] = None,
        question: Optional[str] = None,
        audience: Optional[str] = None,
        constraints: Optional[Sequence[str]] = None,
        prior_insights: Optional[Sequence[str]] = None,
    ) -> AnalystOutput:
        """Async analysis entrypoint."""
        self._ensure_prompts()
        ctx = self._resolve_context(
            context=context,
            question=question,
            audience=audience,
            constraints=constraints,
            prior_insights=prior_insights,
        )
        normalized = [NormalizedSearchResult.from_any(r) for r in (results or [])]
        chunks = list(self._chunk_results(normalized))

        partials: list[str] = []
        citations: set[str] = set()
        for chunk in chunks:
            rendered = self._render_results(chunk)
            msg = await self._ainvoke_prompt(
                self._map_prompt,
                question=ctx.question,
                audience=ctx.audience,
                constraints=self._render_list(ctx.constraints),
                prior_insights=self._render_list(ctx.prior_insights),
                results=rendered,
            )
            text = (msg.content or "").strip()
            partials.append(text)
            citations.update(self._extract_citations(chunk))

        final_msg = await self._ainvoke_prompt(
            self._reduce_prompt,
            question=ctx.question,
            audience=ctx.audience,
            constraints=self._render_list(ctx.constraints),
            prior_insights=self._render_list(ctx.prior_insights),
            partials="\n\n---\n\n".join(partials) if partials else "(no results)",
        )
        parsed = self._parse_structured_output((final_msg.content or "").strip())
        merged_citations = set(parsed.citations) | citations
        out = AnalystOutput(
            answer=parsed.answer,
            key_insights=parsed.key_insights,
            open_questions=parsed.open_questions,
            citations=sorted(merged_citations),
        )
        self._context = ctx
        if out.answer:
            self.update_context(add_prior_insights=[out.answer[:1200]])
        return out

    def _resolve_context(
        self,
        *,
        context: Optional[AnalystContext],
        question: Optional[str],
        audience: Optional[str],
        constraints: Optional[Sequence[str]],
        prior_insights: Optional[Sequence[str]],
    ) -> AnalystContext:
        if context is not None:
            return context
        if self._context is not None:
            # Allow lightweight overrides for the current call.
            data = self._context.model_copy(deep=True)
            if question:
                data.question = question
            if audience:
                data.audience = audience
            if constraints is not None:
                data.constraints = list(constraints)
            if prior_insights is not None:
                data.prior_insights = list(prior_insights)
            return data
        if not question:
            raise ValueError("AnalystAgent requires a `question` or an explicit `context`.")
        return AnalystContext(
            question=question,
            audience=audience or "general",
            constraints=list(constraints or []),
            prior_insights=list(prior_insights or []),
        )

    def _chunk_results(
        self, results: Sequence[NormalizedSearchResult]
    ) -> Iterable[list[NormalizedSearchResult]]:
        chunk: list[NormalizedSearchResult] = []
        chunk_chars = 0

        for r in results:
            rendered = self._render_one(r)
            if (
                chunk
                and (
                    len(chunk) >= self._max_results_per_chunk
                    or chunk_chars + len(rendered) > self._max_chunk_chars
                )
            ):
                yield chunk
                chunk = []
                chunk_chars = 0
            chunk.append(r)
            chunk_chars += len(rendered)

        if chunk:
            yield chunk

    def _render_results(self, results: Sequence[NormalizedSearchResult]) -> str:
        return "\n\n".join(self._render_one(r) for r in results)

    def _render_one(self, r: NormalizedSearchResult) -> str:
        parts: list[str] = [f"Title: {r.title}"]
        if r.url:
            parts.append(f"URL: {r.url}")
        if r.source:
            parts.append(f"Source: {r.source}")
        if r.score is not None:
            parts.append(f"Score: {r.score}")
        if r.snippet:
            parts.append(f"Snippet: {r.snippet}")
        if r.content:
            parts.append(f"Content: {r.content[:4000]}")
        return "\n".join(parts)

    def _extract_citations(self, results: Sequence[NormalizedSearchResult]) -> set[str]:
        cites: set[str] = set()
        for r in results:
            if r.url:
                cites.add(r.url)
            elif r.source:
                cites.add(r.source)
        return cites

    def _render_list(self, items: Sequence[str]) -> str:
        cleaned = [s.strip() for s in items if s and s.strip()]
        return "\n".join(f"- {s}" for s in cleaned) if cleaned else "- (none)"

    def _invoke_prompt(self, prompt: ChatPromptTemplate, **vars: Any) -> BaseMessage:
        self._ensure_prompts()
        messages = prompt.format_messages(**vars)
        kwargs = dict(self._model_kwargs)
        if self._temperature is not None:
            kwargs.setdefault("temperature", self._temperature)
        return self._llm.invoke(messages, **kwargs)

    async def _ainvoke_prompt(self, prompt: ChatPromptTemplate, **vars: Any) -> BaseMessage:
        self._ensure_prompts()
        messages = prompt.format_messages(**vars)
        kwargs = dict(self._model_kwargs)
        if self._temperature is not None:
            kwargs.setdefault("temperature", self._temperature)
        return await self._llm.ainvoke(messages, **kwargs)

    def _parse_structured_output(self, text: str) -> AnalystOutput:
        raw = (text or "").strip()
        if not raw:
            return AnalystOutput(answer="")

        cleaned = self._extract_json_block(self._strip_code_fences(raw))
        try:
            data = json.loads(cleaned)
            if not isinstance(data, dict):
                raise ValueError("top-level JSON must be an object")
        except Exception:
            # Fallback for non-JSON responses: keep backward compatibility.
            return AnalystOutput(answer=raw)

        answer = str(data.get("answer") or "").strip()
        key_insights = self._coerce_str_list(data.get("key_insights"))
        open_questions = self._coerce_str_list(data.get("open_questions"))
        citations = self._coerce_str_list(data.get("citations"))
        return AnalystOutput(
            answer=answer,
            key_insights=key_insights,
            open_questions=open_questions,
            citations=citations,
        )

    def _coerce_str_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        out: list[str] = []
        for item in value:
            s = str(item or "").strip()
            if s:
                out.append(s)
        return out

    def _strip_code_fences(self, text: str) -> str:
        raw = (text or "").strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
            raw = re.sub(r"\s*```$", "", raw)
        return raw.strip()

    def _extract_json_block(self, text: str) -> str:
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

