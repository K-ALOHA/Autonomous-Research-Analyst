from __future__ import annotations

import logging
import operator
from dataclasses import dataclass
from typing import Any, Callable, Optional

from typing_extensions import Annotated, NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy, Send

from backend.agents.analyst import AnalystAgent
from backend.agents.critic import CriticAgent
from backend.agents.editor import EditorAgent, EditorSource
from backend.agents.planner import PlannerAgent
from backend.agents.search import SearchAgent, normalize_search_batch

logger = logging.getLogger(__name__)


class WorkflowState(TypedDict, total=False):
    """
    Shared state carried across the workflow.

    Reducers (Annotated[..., operator.add]) are critical for fan-out parallelism:
    each parallel Search worker returns a one-item list which gets merged.
    """

    # Input
    user_query: str

    # Planner output
    plan: dict[str, Any]
    search_queries: list[str]

    # Search fan-out state
    current_search_query: NotRequired[str]  # set per-worker via Send arg
    search_query_results: Annotated[list[dict[str, Any]], operator.add]

    # Analyst output
    analyst_answer: str
    analyst_key_insights: list[str]
    analyst_open_questions: list[str]
    analyst_citations: list[str]

    # Critic output
    critic_confidence: float
    critic_low_confidence: bool
    critic_issues: list[dict[str, Any]]

    # Editor output
    report_markdown: str
    report_sources: list[dict[str, str]]

    # Error handling
    failed: bool
    errors: Annotated[list[dict[str, Any]], operator.add]


def _err(where: str, exc: BaseException) -> dict[str, Any]:
    return {"where": where, "error": f"{type(exc).__name__}: {exc}"}


def _as_sources_from_search_results(search_query_results: list[dict[str, Any]]) -> list[EditorSource]:
    """
    Convert normalized Tavily-like search results into editor sources.
    """
    sources: list[EditorSource] = []
    for qr in search_query_results or []:
        for item in (qr.get("results") or []):
            url = (item.get("url") or "").strip()
            title = (item.get("title") or url or "Source").strip()
            if not url:
                continue
            sources.append(EditorSource(title=title, url=url))
    return sources


def _node_retry_policy() -> RetryPolicy:
    # Conservative default: fast retries for transient network/API errors.
    return RetryPolicy(max_attempts=3, initial_interval=0.5, max_interval=8.0, backoff_factor=2.0)


@dataclass(frozen=True)
class WorkflowAgents:
    planner: PlannerAgent
    search: SearchAgent
    analyst: AnalystAgent
    critic: CriticAgent
    editor: EditorAgent


def _planner_node(agents: WorkflowAgents) -> Callable[[WorkflowState], WorkflowState]:
    def run(state: WorkflowState) -> WorkflowState:
        if state.get("failed"):
            return {}
        user_query = (state.get("user_query") or "").strip()
        if not user_query:
            return {"failed": True, "errors": [{"where": "planner", "error": "missing_user_query"}]}

        try:
            plan = agents.planner.plan(user_query)
            # Heuristic: seed search queries from subtask titles and goal.
            queries: list[str] = []
            goal = (plan.get("goal") or "").strip()
            if goal:
                queries.append(goal)
            for st in (plan.get("subtasks") or [])[:6]:
                title = (st.get("title") or "").strip()
                if title:
                    queries.append(f"{goal} {title}".strip() if goal else title)
            # Deduplicate while preserving order.
            seen: set[str] = set()
            deduped: list[str] = []
            for q in queries:
                qn = " ".join(q.split())
                if not qn or qn.lower() in seen:
                    continue
                seen.add(qn.lower())
                deduped.append(qn)

            return {
                "plan": plan,
                "search_queries": deduped[:8] or [user_query],
                "failed": False,
            }
        except Exception as e:  # noqa: BLE001
            logger.exception("planner_failed")
            return {"failed": True, "errors": [_err("planner", e)]}

    return run


def _search_dispatch(state: WorkflowState) -> list[Send]:
    if state.get("failed"):
        return [Send("editor", {})]

    queries = [q for q in (state.get("search_queries") or []) if isinstance(q, str) and q.strip()]
    if not queries:
        # Nothing to fan out, still advance the workflow.
        return [Send("analyst", {})]

    return [Send("search", {"current_search_query": q}) for q in queries]


def _search_node(agents: WorkflowAgents) -> Callable[[WorkflowState], WorkflowState]:
    async def run(state: WorkflowState) -> WorkflowState:
        if state.get("failed"):
            return {}
        q = (state.get("current_search_query") or "").strip()
        if not q:
            return {"errors": [{"where": "search", "error": "missing_current_search_query"}]}

        try:
            batch = await agents.search.search_many([q], max_results=8, search_depth="basic")
            normalized = normalize_search_batch(batch)
            # Normalize shape: we store per-query dicts in a reducer-backed list.
            one = (normalized.get("queries") or [{}])[0] if isinstance(normalized, dict) else {}
            return {"search_query_results": [one]}
        except Exception as e:  # noqa: BLE001
            logger.exception("search_failed")
            return {"errors": [_err("search", e)], "search_query_results": [{"query": q, "results": [], "error": str(e)}]}

    return run


def _analyst_node(agents: WorkflowAgents) -> Callable[[WorkflowState], WorkflowState]:
    async def run(state: WorkflowState) -> WorkflowState:
        if state.get("failed"):
            return {}

        user_query = (state.get("user_query") or "").strip()
        results: list[Any] = []
        for qr in state.get("search_query_results") or []:
            results.extend(qr.get("results") or [])

        try:
            out = await agents.analyst.aanalyze(results, question=user_query or "Research question")
            return {
                "analyst_answer": out.answer,
                "analyst_key_insights": list(out.key_insights or []),
                "analyst_open_questions": list(out.open_questions or []),
                "analyst_citations": list(out.citations or []),
            }
        except Exception as e:  # noqa: BLE001
            logger.exception("analyst_failed")
            return {"failed": True, "errors": [_err("analyst", e)], "analyst_answer": ""}

    return run


def _critic_node(agents: WorkflowAgents) -> Callable[[WorkflowState], WorkflowState]:
    def run(state: WorkflowState) -> WorkflowState:
        if state.get("failed"):
            return {}
        text = state.get("analyst_answer") or ""
        try:
            critique = agents.critic.critique(text, context={"grounded_text": text})
            issues = [
                {
                    "kind": i.kind,
                    "severity": i.severity,
                    "message": i.message,
                    "span": i.span,
                    "evidence": i.evidence,
                }
                for i in (critique.issues or ())
            ]
            return {
                "critic_confidence": critique.overall_confidence,
                "critic_low_confidence": critique.low_confidence,
                "critic_issues": issues,
            }
        except Exception as e:  # noqa: BLE001
            logger.exception("critic_failed")
            return {"failed": True, "errors": [_err("critic", e)]}

    return run


def _editor_node(agents: WorkflowAgents) -> Callable[[WorkflowState], WorkflowState]:
    def run(state: WorkflowState) -> WorkflowState:
        errors = state.get("errors") or []
        failed = bool(state.get("failed"))

        if failed:
            draft = "## Workflow failed\n\n"
            if errors:
                draft += "### Errors\n\n"
                for e in errors[-10:]:
                    draft += f"- {e.get('where')}: {e.get('error')}\n"
            else:
                draft += "No additional error details were captured.\n"
            edited = agents.editor.edit(draft, sources=[], title="Failure report")
            return {
                "report_markdown": edited.report_markdown,
                "report_sources": [],
            }

        draft_parts: list[str] = []
        if state.get("plan"):
            draft_parts.append("## Plan\n")
            goal = (state["plan"].get("goal") or "").strip()
            if goal:
                draft_parts.append(f"- Goal: {goal}\n")
            subtasks = state["plan"].get("subtasks") or []
            if subtasks:
                draft_parts.append("\n## Subtasks\n")
                for st in subtasks:
                    title = (st.get("title") or "").strip()
                    desc = (st.get("description") or "").strip()
                    if not title:
                        continue
                    draft_parts.append(f"- **{title}**{(': ' + desc) if desc else ''}\n")

        answer = (state.get("analyst_answer") or "").strip()
        if answer:
            draft_parts.append("\n## Analysis\n\n")
            draft_parts.append(answer.rstrip() + "\n")

        if state.get("critic_low_confidence"):
            draft_parts.append("\n## Quality flags\n\n")
            draft_parts.append(
                f"Critic confidence: {state.get('critic_confidence', 0.0):.2f}\n\n"
            )
            for issue in state.get("critic_issues") or []:
                draft_parts.append(f"- ({issue.get('severity')}) {issue.get('message')}\n")

        sources = _as_sources_from_search_results(state.get("search_query_results") or [])
        edited = agents.editor.edit("\n".join(draft_parts).strip(), sources=sources, title="Research Report")
        # If no inline URL markers were present in the generated draft, EditorAgent may
        # return zero "used" citations. Keep source attribution available in API output.
        citations = edited.citations or sources
        return {
            "report_markdown": edited.report_markdown,
            "report_sources": [s.model_dump(mode="json") for s in citations],
        }

    return run


def build_workflow(*, agents: WorkflowAgents):
    """
    Build a production-ready LangGraph workflow:
      Planner → Search (fan-out parallel) → Analyst → Critic → Editor

    Returns a compiled runnable graph.
    """
    g = StateGraph(WorkflowState)

    g.add_node("planner", _planner_node(agents), retry=_node_retry_policy())
    g.add_node("search", _search_node(agents), retry=_node_retry_policy())
    g.add_node("analyst", _analyst_node(agents), retry=_node_retry_policy())
    g.add_node("critic", _critic_node(agents), retry=_node_retry_policy())
    g.add_node("editor", _editor_node(agents), retry=_node_retry_policy())

    g.add_edge(START, "planner")
    g.add_conditional_edges("planner", _search_dispatch, ["search", "analyst", "editor"])

    # Fan-in: all parallel "search" executions complete, then the workflow advances.
    g.add_edge("search", "analyst")
    g.add_edge("analyst", "critic")
    g.add_edge("critic", "editor")
    g.add_edge("editor", END)

    return g.compile()
