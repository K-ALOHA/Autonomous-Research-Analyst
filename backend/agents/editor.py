from __future__ import annotations

import re
import unicodedata
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, Field

_WS_RE = re.compile(r"[ \t]+")
_MULTI_NL_RE = re.compile(r"\n{3,}")
_HEADING_RE = re.compile(r"^\s*#{1,6}\s+\S+", re.M)
_BULLET_RE = re.compile(r"^\s*[•·]\s+", re.M)
_BARE_URL_RE = re.compile(r"(?P<url>https?://[^\s)>\]]+)")

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


def _clean_text(value: Optional[str]) -> str:
    v = (value or "").strip()
    v = unicodedata.normalize("NFKC", v)
    v = v.replace("\r\n", "\n").replace("\r", "\n")
    # Preserve paragraph structure while normalizing horizontal whitespace.
    lines = [_WS_RE.sub(" ", line).rstrip() for line in v.split("\n")]
    return "\n".join(lines).strip()


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


class EditorSource(BaseModel):
    title: str = Field(..., description="Human-readable source title")
    url: str = Field(..., description="Source URL")

    normalized_url: str = Field("", description="Normalized URL (stable for dedupe)")

    def model_post_init(self, __context: object) -> None:  # type: ignore[override]
        if not self.normalized_url:
            object.__setattr__(self, "normalized_url", _normalize_url(self.url))


class EditorInput(BaseModel):
    draft: str = Field(..., description="Draft report text (markdown or plain text)")
    sources: list[EditorSource] = Field(default_factory=list)
    title: Optional[str] = Field(None, description="Optional report title")


class EditorOutput(BaseModel):
    report_markdown: str
    citations: list[EditorSource] = Field(default_factory=list)


def _dedupe_sources(sources: list[EditorSource]) -> list[EditorSource]:
    seen: set[str] = set()
    out: list[EditorSource] = []
    for s in sources or []:
        key = s.normalized_url or _normalize_url(s.url) or _clean_text(s.title).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def _ensure_headings(md: str, *, title: Optional[str]) -> str:
    body = (md or "").strip()
    if not body:
        return (f"## {title}\n" if title else "## Report\n")

    if not _HEADING_RE.search(body):
        heading = title or "Overview"
        body = f"## {heading}\n\n{body}"
    return body


def _normalize_markdown(md: str) -> str:
    text = (md or "").replace("\r\n", "\n").replace("\r", "\n")
    text = _BULLET_RE.sub("- ", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = _MULTI_NL_RE.sub("\n\n", text).strip() + "\n"
    return text


def _apply_citations(md: str, sources: list[EditorSource]) -> tuple[str, list[EditorSource]]:
    sources = _dedupe_sources(sources)
    if not sources:
        return md, []

    url_to_idx: dict[str, int] = {}
    for i, s in enumerate(sources, start=1):
        for u in {s.url, s.normalized_url}:
            nu = _normalize_url(u)
            if nu and nu not in url_to_idx:
                url_to_idx[nu] = i

    used: set[int] = set()

    def repl(m: re.Match[str]) -> str:
        raw = m.group("url")
        nu = _normalize_url(raw)
        idx = url_to_idx.get(nu)
        if idx is None:
            return raw
        used.add(idx)
        return f"[{idx}]"

    out = _BARE_URL_RE.sub(repl, md)

    used_sources = [s for i, s in enumerate(sources, start=1) if i in used]
    if not used_sources:
        return out, []

    refs_lines = ["", "## Sources", ""]
    for i, s in enumerate(sources, start=1):
        if i not in used:
            continue
        title = _clean_text(s.title) or _normalize_url(s.url) or s.url
        url = s.url.strip()
        refs_lines.append(f"{i}. [{title}]({url})")
    refs_lines.append("")

    out = out.rstrip("\n") + "\n" + "\n".join(refs_lines)
    return out, used_sources


class EditorAgent:
    """
    Editor agent that turns a draft into a clean, cited Markdown report.

    Responsibilities:
    - Add headings when missing
    - Improve readability (normalize whitespace, list bullets, spacing)
    - Add citations by converting known source URLs into [n] markers and appending a Sources section
    """

    def edit(self, draft: str, *, sources: Optional[list[EditorSource]] = None, title: Optional[str] = None) -> EditorOutput:
        text = _clean_text(draft)
        md = _ensure_headings(text, title=title)
        md = _normalize_markdown(md)
        md, used_sources = _apply_citations(md, sources or [])
        md = _normalize_markdown(md)
        return EditorOutput(report_markdown=md, citations=used_sources)

    def edit_input(self, inp: EditorInput) -> EditorOutput:
        return self.edit(inp.draft, sources=inp.sources, title=inp.title)

