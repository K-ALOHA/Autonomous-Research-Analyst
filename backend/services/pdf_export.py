from __future__ import annotations

import re
from typing import Any


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-") or "research-report"


def _clean_md(text: str) -> str:
    out = (text or "").strip()
    out = re.sub(r"`([^`]+)`", r"\1", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"\1", out)
    out = re.sub(r"\*([^*]+)\*", r"\1", out)
    out = re.sub(r"^#{1,6}\s*", "", out, flags=re.M)
    out = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1 (\2)", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def _soft_wrap_long_tokens(text: str, *, max_token_len: int = 90) -> str:
    parts: list[str] = []
    for token in (text or "").split(" "):
        if len(token) <= max_token_len:
            parts.append(token)
            continue
        chunks = [token[i : i + max_token_len] for i in range(0, len(token), max_token_len)]
        parts.append(" ".join(chunks))
    return " ".join(parts)


def _sanitize_for_pdf(text: str) -> str:
    # Core14 fonts support latin-1; replace unsupported symbols.
    return (text or "").encode("latin-1", errors="replace").decode("latin-1")


def _safe_multicell(pdf: Any, text: str, *, line_h: int) -> None:
    from fpdf.errors import FPDFException

    epw = pdf.w - pdf.l_margin - pdf.r_margin
    safe = _sanitize_for_pdf(_soft_wrap_long_tokens(text))
    try:
        pdf.multi_cell(epw, line_h, safe)
    except FPDFException:
        # Last-resort fallback for pathological lines.
        pdf.multi_cell(epw, line_h, safe[:4000])


def _extract_summary(markdown: str) -> str:
    text = _clean_md(markdown)
    for chunk in text.split("\n\n"):
        line = chunk.strip()
        if len(line) > 30:
            return line[:800]
    return text[:800]


def render_report_pdf(*, run_id: str, query: str, result: dict[str, Any]) -> tuple[bytes, str]:
    try:
        from fpdf import FPDF
    except ImportError as e:
        raise RuntimeError("pdf_export_dependency_missing: install fpdf2 (see requirements.txt)") from e

    report_markdown = str(result.get("report_markdown") or "").strip()
    report_sources = result.get("report_sources") or []

    title = f"Research Report - {query.strip()[:80]}" if query.strip() else "Research Report"
    summary = _extract_summary(report_markdown)
    body = _soft_wrap_long_tokens(_clean_md(report_markdown))

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    _safe_multicell(pdf, title, line_h=8)
    pdf.ln(2)

    pdf.set_font("Helvetica", size=10)
    pdf.set_text_color(90, 90, 90)
    _safe_multicell(pdf, f"Run ID: {run_id}", line_h=6)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(1)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Summary", ln=True)
    pdf.set_font("Helvetica", size=11)
    _safe_multicell(pdf, summary or "No summary available.", line_h=6)
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Report", ln=True)
    pdf.set_font("Helvetica", size=11)
    _safe_multicell(pdf, body or "No report content available.", line_h=6)
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Sources", ln=True)
    pdf.set_font("Helvetica", size=10)
    if isinstance(report_sources, list) and report_sources:
        for i, src in enumerate(report_sources, start=1):
            if not isinstance(src, dict):
                continue
            s_title = str(src.get("title") or "Source").strip()
            s_url = str(src.get("url") or "").strip()
            line = f"{i}. {s_title}" + (f" - {s_url}" if s_url else "")
            _safe_multicell(pdf, line, line_h=5)
    else:
        _safe_multicell(pdf, "No sources recorded.", line_h=5)

    filename = f"{_slug(query)}-{run_id[:8]}.pdf"
    return bytes(pdf.output(dest="S")), filename
