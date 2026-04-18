from __future__ import annotations

import asyncio
import os
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    title: str
    url: str
    content: Optional[str] = None
    score: Optional[float] = None
    published_date: Optional[str] = None

    normalized_url: str
    source: str = "tavily"


class SearchQueryResult(BaseModel):
    query: str
    results: list[SearchResult] = Field(default_factory=list)
    took_ms: int
    error: Optional[str] = None


class SearchBatchResult(BaseModel):
    queries: list[SearchQueryResult]
    total_took_ms: int
    created_at: datetime


_WS_RE = re.compile(r"\s+")


def _clean_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    v = unicodedata.normalize("NFKC", value)
    v = _WS_RE.sub(" ", v).strip()
    return v or None


_DROP_QUERY_KEYS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "ref_src",
    "ref_url",
    "spm",
}


def _normalize_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""

    parts = urlsplit(raw)
    scheme = (parts.scheme or "https").lower()
    netloc = parts.netloc.lower()
    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[: -len(":80")]
    if netloc.endswith(":443") and scheme == "https":
        netloc = netloc[: -len(":443")]

    path = parts.path or "/"
    path = re.sub(r"/{2,}", "/", path)

    q = []
    for k, v in parse_qsl(parts.query, keep_blank_values=False):
        if not k:
            continue
        if k.lower() in _DROP_QUERY_KEYS:
            continue
        q.append((k, v))
    q.sort(key=lambda kv: (kv[0].lower(), kv[1]))
    query = urlencode(q, doseq=True)

    fragment = ""
    return urlunsplit((scheme, netloc, path, query, fragment))


def _dedupe_results(results: list[SearchResult]) -> list[SearchResult]:
    seen: set[str] = set()
    out: list[SearchResult] = []
    for r in results:
        key = r.normalized_url or (r.url or "")
        if not key:
            key = (r.title or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


class TavilySearchRequest(BaseModel):
    query: str
    max_results: int = 8
    search_depth: str = "basic"
    include_answer: bool = False
    include_raw_content: bool = False
    include_images: bool = False


class SearchAgent:
    """
    Search agent backed by Tavily.

    - Parallelizes across queries using asyncio
    - Normalizes + dedupes results for stable downstream consumption
    - Returns structured pydantic models
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: str = "https://api.tavily.com",
        timeout_s: float = 20.0,
        max_concurrency: int = 8,
    ) -> None:
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        if not self.api_key:
            raise ValueError("Missing Tavily API key. Set TAVILY_API_KEY.")
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self._sem = asyncio.Semaphore(max(1, int(max_concurrency)))

    async def search(
        self,
        query: str,
        *,
        max_results: int = 8,
        search_depth: str = "basic",
    ) -> SearchQueryResult:
        started = asyncio.get_running_loop().time()
        q_clean = _clean_text(query) or ""
        if not q_clean:
            return SearchQueryResult(query=query, results=[], took_ms=0, error="empty_query")

        payload = TavilySearchRequest(
            query=q_clean,
            max_results=max(1, int(max_results)),
            search_depth=search_depth,
        ).model_dump()
        payload["api_key"] = self.api_key

        try:
            async with self._sem:
                async with httpx.AsyncClient(
                    base_url=self.base_url,
                    timeout=httpx.Timeout(self.timeout_s),
                    headers={"accept": "application/json"},
                ) as client:
                    resp = await client.post("/search", json=payload)
                    resp.raise_for_status()
                    data = resp.json()

            results: list[SearchResult] = []
            for item in (data.get("results") or []):
                title = _clean_text(item.get("title")) or ""
                url = _clean_text(item.get("url")) or ""
                content = _clean_text(item.get("content"))
                score = item.get("score")
                try:
                    score_f = float(score) if score is not None else None
                except (TypeError, ValueError):
                    score_f = None

                norm = _normalize_url(url)
                if not title and not url:
                    continue
                results.append(
                    SearchResult(
                        title=title or url,
                        url=url,
                        content=content,
                        score=score_f,
                        published_date=_clean_text(item.get("published_date")),
                        normalized_url=norm,
                    )
                )

            results = _dedupe_results(results)
            if any(r.score is not None for r in results):
                results.sort(key=lambda r: (r.score is None, -(r.score or 0.0)))

            took_ms = int((asyncio.get_running_loop().time() - started) * 1000)
            return SearchQueryResult(query=q_clean, results=results, took_ms=took_ms)
        except httpx.HTTPStatusError as e:
            took_ms = int((asyncio.get_running_loop().time() - started) * 1000)
            msg = f"http_{e.response.status_code}"
            return SearchQueryResult(query=q_clean, results=[], took_ms=took_ms, error=msg)
        except Exception as e:  # noqa: BLE001 - surface error string to caller
            took_ms = int((asyncio.get_running_loop().time() - started) * 1000)
            return SearchQueryResult(
                query=q_clean, results=[], took_ms=took_ms, error=_clean_text(str(e)) or "error"
            )

    async def search_many(
        self,
        queries: list[str],
        *,
        max_results: int = 8,
        search_depth: str = "basic",
    ) -> SearchBatchResult:
        batch_started = asyncio.get_running_loop().time()

        tasks = [
            self.search(q, max_results=max_results, search_depth=search_depth) for q in (queries or [])
        ]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        total_took_ms = int((asyncio.get_running_loop().time() - batch_started) * 1000)
        return SearchBatchResult(
            queries=results,
            total_took_ms=total_took_ms,
            created_at=datetime.now(timezone.utc),
        )


def normalize_search_batch(result: SearchBatchResult) -> dict[str, Any]:
    """
    Convenience helper to emit a JSON-serializable, stable structure.
    """

    return result.model_dump(mode="json")

