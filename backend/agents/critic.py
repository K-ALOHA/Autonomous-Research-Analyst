from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Iterable, Mapping, Sequence


@dataclass(frozen=True)
class CriticIssue:
    """A single quality issue found in a model output."""

    kind: str
    severity: str  # "low" | "medium" | "high"
    message: str
    span: tuple[int, int] | None = None
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CritiqueResult:
    """Structured critique suitable for programmatic gating."""

    overall_confidence: float  # 0..1
    low_confidence: bool
    issues: tuple[CriticIssue, ...] = ()
    signals: dict[str, Any] = field(default_factory=dict)


class CriticAgent:
    """
    Detect hallucinations and inconsistencies in generated text.

    This agent is intentionally dependency-light: it uses heuristics plus optional
    provided facts/evidence to validate outputs.

    Expected `context` (all optional):
    - facts: Mapping[str, Any]
        Canonical facts keyed by name (e.g., {"capital_of_france": "Paris"}).
    - fact_patterns: Sequence[tuple[re.Pattern[str], str]]
        Regex patterns that extract a comparable value; each item is (pattern, fact_key).
        The first capture group is used as the extracted value unless `group` is provided
        in the pattern via a (?P<value>...) named group.
    - grounded_text: str
        A trusted reference passage; if present, named entities/numbers not appearing in
        grounded_text will be treated as higher risk.
    - now: date | datetime
        Used only for time-sensitivity checks (defaults to today).
    """

    _HEDGE_RE = re.compile(
        r"\b(?:might|maybe|probably|possibly|i think|i believe|not sure|uncertain|"
        r"can't confirm|cannot confirm|approx(?:\.|imately)?|roughly|around)\b",
        flags=re.IGNORECASE,
    )
    _OVERCONFIDENT_RE = re.compile(
        r"\b(?:guarantee|always|never|100%|certainly|definitely|proven)\b", flags=re.IGNORECASE
    )
    _TIME_SENSITIVE_RE = re.compile(
        r"\b(?:latest|currently|as of now|today|this year|recently|up to date)\b",
        flags=re.IGNORECASE,
    )
    _URL_RE = re.compile(r"https?://[^\s)]+", flags=re.IGNORECASE)
    _CITATION_CUE_RE = re.compile(
        r"\b(?:source|sources|citation|cited|according to|ref|references?)\b",
        flags=re.IGNORECASE,
    )

    # A pragmatic numeric fact extractor: captures number + unit-ish suffix.
    _NUMBER_RE = re.compile(
        r"(?P<num>\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b|\b\d+(?:\.\d+)?\b)\s*(?P<unit>%|[a-zA-Z]{1,10})?",
        flags=0,
    )

    def critique(self, output: str, *, context: Mapping[str, Any] | None = None) -> CritiqueResult:
        ctx: Mapping[str, Any] = context or {}
        issues: list[CriticIssue] = []
        signals: dict[str, Any] = {"engine": "heuristic"}

        now = ctx.get("now")
        if isinstance(now, datetime):
            today = now.date()
        elif isinstance(now, date):
            today = now
        else:
            today = date.today()

        hedge_hits = list(self._find_spans(self._HEDGE_RE, output))
        if hedge_hits:
            issues.append(
                CriticIssue(
                    kind="low_confidence_language",
                    severity="low",
                    message="Output uses hedging / uncertainty language; some claims may be unverified.",
                    evidence={"matches": hedge_hits[:25]},
                )
            )
            signals["hedge_match_count"] = len(hedge_hits)

        overconf_hits = list(self._find_spans(self._OVERCONFIDENT_RE, output))
        if overconf_hits:
            issues.append(
                CriticIssue(
                    kind="overconfident_language",
                    severity="medium",
                    message="Output uses overly absolute language; verify any universal claims.",
                    evidence={"matches": overconf_hits[:25]},
                )
            )
            signals["overconfident_match_count"] = len(overconf_hits)

        # Time-sensitive statements should ideally be anchored with dates/sources.
        if self._TIME_SENSITIVE_RE.search(output) and not self._contains_date_anchor(output):
            issues.append(
                CriticIssue(
                    kind="time_sensitive_unanchored",
                    severity="medium",
                    message=f"Output contains time-sensitive phrasing but no explicit date anchor (today is {today.isoformat()}).",
                )
            )

        # Citation cues without actual URLs are a common hallucination smell.
        if self._CITATION_CUE_RE.search(output) and not self._URL_RE.search(output):
            issues.append(
                CriticIssue(
                    kind="citation_without_reference",
                    severity="low",
                    message="Output suggests sources/citations but provides no concrete references (e.g., URLs).",
                )
            )

        issues.extend(self._validate_against_facts(output, ctx))
        issues.extend(self._detect_internal_inconsistencies(output))
        issues.extend(self._grounding_gap_checks(output, ctx))

        confidence = self._score_confidence(issues)
        low_conf = confidence < 0.6 or any(i.severity == "high" for i in issues)
        return CritiqueResult(
            overall_confidence=confidence,
            low_confidence=low_conf,
            issues=tuple(issues),
            signals=signals,
        )

    def _validate_against_facts(self, output: str, ctx: Mapping[str, Any]) -> list[CriticIssue]:
        facts = ctx.get("facts")
        patterns = ctx.get("fact_patterns")
        if not isinstance(facts, Mapping) or not patterns:
            return []

        extracted: list[tuple[str, str, tuple[int, int]]] = []
        compiled: list[tuple[re.Pattern[str], str]] = []
        for item in patterns:
            if (
                isinstance(item, tuple)
                and len(item) == 2
                and isinstance(item[0], re.Pattern)
                and isinstance(item[1], str)
            ):
                compiled.append((item[0], item[1]))

        for pattern, fact_key in compiled:
            for m in pattern.finditer(output):
                if "value" in m.groupdict():
                    value = m.group("value")
                elif m.groups():
                    value = m.group(1)
                else:
                    continue
                extracted.append((fact_key, value.strip(), (m.start(), m.end())))

        issues: list[CriticIssue] = []
        for fact_key, value, span in extracted:
            if fact_key not in facts:
                issues.append(
                    CriticIssue(
                        kind="unknown_fact_key",
                        severity="low",
                        message=f"Extracted fact key '{fact_key}' is not present in provided facts; cannot validate.",
                        span=span,
                        evidence={"fact_key": fact_key, "extracted_value": value},
                    )
                )
                continue
            expected = facts[fact_key]
            if not self._loosely_equal(value, expected):
                issues.append(
                    CriticIssue(
                        kind="fact_mismatch",
                        severity="high",
                        message=f"Claim conflicts with provided fact '{fact_key}'.",
                        span=span,
                        evidence={"fact_key": fact_key, "expected": expected, "extracted_value": value},
                    )
                )
        return issues

    def _detect_internal_inconsistencies(self, output: str) -> list[CriticIssue]:
        """
        Heuristic contradiction detector for numeric claims.

        It groups numbers by a short lexical window prefix (a "key") and flags when the
        same key appears with multiple different numeric values.
        """
        mentions: dict[str, list[tuple[str, tuple[int, int]]]] = {}
        for m in self._NUMBER_RE.finditer(output):
            raw = m.group("num")
            num = raw.replace(",", "")
            unit = (m.group("unit") or "").lower()
            key = self._numeric_key(output, m.start(), m.end())
            if not key:
                continue
            mentions.setdefault(f"{key}|{unit}", []).append((num, (m.start(), m.end())))

        issues: list[CriticIssue] = []
        for k, vals in mentions.items():
            distinct = {}
            for v, span in vals:
                distinct.setdefault(v, []).append(span)
            if len(distinct) >= 2 and len(vals) >= 2:
                # Only flag if it's not obviously a list/range ("1, 2, 3") by requiring separation.
                issues.append(
                    CriticIssue(
                        kind="internal_numeric_inconsistency",
                        severity="medium",
                        message="Output contains inconsistent numeric values for what appears to be the same quantity.",
                        evidence={
                            "key": k,
                            "values": {v: spans[:3] for v, spans in list(distinct.items())[:5]},
                        },
                    )
                )
        return issues

    def _grounding_gap_checks(self, output: str, ctx: Mapping[str, Any]) -> list[CriticIssue]:
        grounded_text = ctx.get("grounded_text")
        if not isinstance(grounded_text, str) or not grounded_text.strip():
            return []

        grounded_nums = {m.group("num").replace(",", "") for m in self._NUMBER_RE.finditer(grounded_text)}
        output_nums = [(m.group("num").replace(",", ""), (m.start(), m.end())) for m in self._NUMBER_RE.finditer(output)]
        novel_nums = [(n, span) for (n, span) in output_nums if n not in grounded_nums]

        if not novel_nums:
            return []

        # Novel numbers often indicate hallucinated specificity unless explicitly derived.
        return [
            CriticIssue(
                kind="ungrounded_specificity",
                severity="medium",
                message="Output introduces specific numbers not present in the provided grounded text.",
                evidence={"novel_numbers": novel_nums[:20]},
            )
        ]

    def _score_confidence(self, issues: Sequence[CriticIssue]) -> float:
        score = 1.0
        for issue in issues:
            if issue.severity == "high":
                score -= 0.45
            elif issue.severity == "medium":
                score -= 0.2
            else:
                score -= 0.08
        return max(0.0, min(1.0, score))

    def _contains_date_anchor(self, text: str) -> bool:
        # Looks for YYYY-MM-DD, YYYY/MM/DD, Month YYYY, or bare years.
        iso = re.search(r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b", text)
        month = re.search(
            r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{4}\b",
            text,
            flags=re.IGNORECASE,
        )
        year = re.search(r"\b(19|20)\d{2}\b", text)
        return bool(iso or month or year)

    def _numeric_key(self, text: str, start: int, end: int) -> str | None:
        # Take up to ~6 words preceding the number as the "key".
        left = text[max(0, start - 120) : start]
        words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{1,30}", left)
        if not words:
            return None
        key_words = words[-6:]
        # Normalize out common stopwords to reduce false positives.
        stop = {"the", "a", "an", "of", "to", "in", "for", "and", "or", "is", "are", "was", "were"}
        filtered = [w.lower() for w in key_words if w.lower() not in stop]
        if not filtered:
            filtered = [w.lower() for w in key_words[-2:]]
        return " ".join(filtered[-4:])[:80]

    def _find_spans(self, pattern: re.Pattern[str], text: str) -> Iterable[dict[str, Any]]:
        for m in pattern.finditer(text):
            yield {"match": m.group(0), "span": (m.start(), m.end())}

    def _loosely_equal(self, extracted: str, expected: Any) -> bool:
        if expected is None:
            return extracted.strip().lower() in {"none", "null", "n/a", "na"}
        if isinstance(expected, (int, float)):
            try:
                return float(extracted.replace(",", "")) == float(expected)
            except ValueError:
                return False
        if isinstance(expected, str):
            return self._norm(extracted) == self._norm(expected)
        if isinstance(expected, Sequence) and not isinstance(expected, (str, bytes, bytearray)):
            return any(self._loosely_equal(extracted, item) for item in expected)
        return self._norm(extracted) == self._norm(str(expected))

    def _norm(self, s: str) -> str:
        return re.sub(r"\s+", " ", s.strip().lower())

