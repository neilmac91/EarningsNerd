"""Single source of truth for serializing a summary's structured sections.

``raw_summary["sections"]`` holds **structured** dicts/lists (not markdown strings). The PDF
exporter, the CSV exporter, and the on-page UI used to each decide independently how to render
those sections, which is exactly why they diverged (page = 9 sections, PDF = 5, CSV = 2) and why
the PDF crashed (a dict was fed to a markdown-string formatter that called ``.strip()`` on it).

This module renders ``sections`` into an ordered list of format-agnostic ``Section``/``Block``
objects. ``export_service`` turns those into HTML (PDF) and CSV rows, so the two formats can never
drift apart again. The placeholder filtering and risk normalization mirror the frontend
(``frontend/components/SummarySections.tsx`` + ``frontend/lib/formatters.ts``) so exports match
exactly what the user sees on the page.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

from app.services import metric_delta_service

# Mirror frontend SummarySections.tsx PLACEHOLDER_PATTERNS so exports drop the same
# "data unavailable" filler the page hides.
PLACEHOLDER_PATTERNS = (
    "not available",
    "unavailable",
    "n/a",
    "retry",
    "requires full",
    "data pending",
    "being processed",
    "taking longer",
    "preliminary",
    "placeholder",
    "available in the full",
)


def is_placeholder(text: Any) -> bool:
    """Mirror of the frontend ``isPlaceholderText``: non-strings/empties count as placeholder."""
    if not isinstance(text, str):
        return True
    lowered = text.strip().lower()
    if not lowered:
        return True
    return any(pattern in lowered for pattern in PLACEHOLDER_PATTERNS)


def _clean(value: Any) -> str:
    """Return a trimmed string for str/number inputs, else ""."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    return ""


def _str_list(value: Any) -> List[str]:
    """Normalize a list-ish value into a list of clean, non-empty strings."""
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple, set)):
        return []
    out: List[str] = []
    for item in value:
        cleaned = _clean(item)
        if cleaned:
            out.append(cleaned)
    return out


def _format_evidence(value: Any) -> str:
    """Collapse supporting-evidence (str/list/dict) into one string. Mirrors the frontend."""
    if isinstance(value, (list, tuple, set)):
        return "; ".join(_clean(item) for item in value if _clean(item))
    if isinstance(value, dict):
        return "; ".join(_clean(item) for item in value.values() if _clean(item))
    return _clean(value)


@dataclass
class Block:
    """A format-agnostic piece of content within a section.

    kind:
        - "paragraph": ``text``
        - "subheading": ``text`` (a labelled lead-in for the block(s) that follow)
        - "quote":     ``text`` + optional ``speaker``
        - "bullets":   optional ``text`` (group label) + ``items``
        - "table":     ``headers`` + ``rows`` (list of equal-length string rows)
    """

    kind: str
    text: str = ""
    speaker: str = ""
    items: List[str] = field(default_factory=list)
    headers: List[str] = field(default_factory=list)
    rows: List[List[str]] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (self.text or self.items or self.rows)


@dataclass
class Section:
    title: str
    blocks: List[Block] = field(default_factory=list)

    @property
    def has_content(self) -> bool:
        return any(not block.is_empty for block in self.blocks)


# --- Per-section builders ----------------------------------------------------------------------
# Each returns a Section (possibly empty — callers drop empties) given the full ``sections`` dict.


def _executive_snapshot(sections: dict) -> Section:
    section = Section("Executive Assessment")
    data = sections.get("executive_snapshot")
    if isinstance(data, str):
        text = _clean(data)
        if text and not is_placeholder(text):
            section.blocks.append(Block("paragraph", text=text))
        return section
    if not isinstance(data, dict):
        return section

    headline = _clean(data.get("headline"))
    if headline and not is_placeholder(headline):
        section.blocks.append(Block("paragraph", text=headline))
    tone = _clean(data.get("tone"))
    if tone and tone.lower() not in ("neutral", ""):
        section.blocks.append(
            Block("paragraph", text=f"Management's disclosed tone was {tone.lower()}.")
        )
    points = [p for p in _str_list(data.get("key_points") or data.get("keyPoints")) if not is_placeholder(p)]
    if points:
        section.blocks.append(Block("bullets", items=points))
    return section


def _financial_highlights(sections: dict) -> Section:
    section = Section("Financial Highlights")
    data = sections.get("financial_highlights")
    if not isinstance(data, dict):
        return section

    rows: List[List[str]] = []
    table = data.get("table")
    if isinstance(table, list):
        for row in table:
            if not isinstance(row, dict):
                continue
            metric = _clean(row.get("metric"))
            if not metric:
                continue
            # Single delta policy (T1.5): compute the Change cell from current/prior so CSV+PDF match
            # the table and chips (ppts for margins), falling back to the model's text only when the
            # displayed values don't parse.
            _delta = metric_delta_service.delta_for_row(row)
            change_cell = _delta.display if _delta and _delta.display else _clean(row.get("change"))
            rows.append(
                [
                    metric,
                    _clean(row.get("current_period") or row.get("currentPeriod")),
                    _clean(row.get("prior_period") or row.get("priorPeriod")),
                    change_cell,
                    _clean(row.get("commentary")),
                ]
            )
    if rows:
        section.blocks.append(
            Block(
                "table",
                headers=["Metric", "Current Period", "Prior Period", "Change", "Investor Takeaway"],
                rows=rows,
            )
        )

    for label, key, alt in (
        ("Profitability", "profitability", None),
        ("Cash flow", "cash_flow", "cashFlow"),
        ("Balance sheet", "balance_sheet", "balanceSheet"),
    ):
        items = _str_list(data.get(key) or (data.get(alt) if alt else None))
        items = [item for item in items if not is_placeholder(item)]
        if items:
            section.blocks.append(Block("bullets", text=label, items=items))

    notes = _clean(data.get("notes"))
    if notes and not is_placeholder(notes):
        section.blocks.append(Block("paragraph", text=notes))
    return section


def _risk_factors(sections: dict) -> Section:
    """Risks, filtered to match the page: each must have non-placeholder supporting evidence."""
    section = Section("Investment Risks & Concerns")
    risks = sections.get("risk_factors")
    if not isinstance(risks, list):
        return section

    rows: List[List[str]] = []
    for risk in risks:
        normalized = _normalize_risk(risk)
        if not normalized:
            continue
        risk_text, evidence = normalized
        rows.append([str(len(rows) + 1), risk_text, evidence])
    if rows:
        section.blocks.append(
            Block("table", headers=["#", "Risk", "Supporting Evidence"], rows=rows)
        )
    return section


def _normalize_risk(risk: Any) -> Optional[tuple]:
    """Mirror frontend ``normalizeRisk`` + the page's placeholder filter.

    Returns ``(risk_text, evidence)`` for a risk that should be shown, or ``None`` to drop it
    (no summary candidate, or missing / placeholder supporting evidence, or placeholder
    description) — matching ``SummarySections.tsx``.
    """
    if not isinstance(risk, dict):
        return None
    title = _clean(risk.get("title"))
    description = _clean(risk.get("description"))
    summary = _clean(risk.get("summary")) or description or title
    if not summary:
        return None

    evidence = _format_evidence(
        risk.get("supporting_evidence")
        or risk.get("supportingEvidence")
        or risk.get("evidence")
        or risk.get("source")
    )
    if not evidence or is_placeholder(evidence):
        return None
    if description and is_placeholder(description):
        return None

    if title and description:
        risk_text = f"{title}: {description}"
    elif title and summary and summary.lower() != title.lower():
        risk_text = f"{title}: {summary}"
    else:
        risk_text = summary or title or description
    return (risk_text, evidence)


def _management_discussion(sections: dict) -> Section:
    section = Section("Management Strategy & Execution")
    data = sections.get("management_discussion_insights")
    if isinstance(data, str):
        text = _clean(data)
        if text and not is_placeholder(text):
            section.blocks.append(Block("paragraph", text=text))
        return section
    if not isinstance(data, dict):
        return section

    themes = [t for t in _str_list(data.get("themes")) if not is_placeholder(t)]
    if themes:
        section.blocks.append(Block("bullets", text="Themes", items=themes))
    capital = _str_list(data.get("capital_allocation") or data.get("capitalAllocation"))
    capital = [c for c in capital if not is_placeholder(c)]
    if capital:
        section.blocks.append(Block("bullets", text="Capital allocation", items=capital))
    quotes = data.get("quotes")
    if isinstance(quotes, list):
        for quote in quotes:
            if not isinstance(quote, dict):
                continue
            text = _clean(quote.get("quote"))
            if text and not is_placeholder(text):
                section.blocks.append(Block("quote", text=text, speaker=_clean(quote.get("speaker"))))
    return section


def _segment_performance(sections: dict) -> Section:
    section = Section("Business Segment Analysis")
    data = sections.get("segment_performance")
    rows: List[List[str]] = []
    if isinstance(data, list):
        for seg in data:
            if not isinstance(seg, dict):
                continue
            name = _clean(seg.get("segment") or seg.get("name"))
            if not name:
                continue
            rows.append(
                [name, _clean(seg.get("revenue")), _clean(seg.get("change")), _clean(seg.get("commentary"))]
            )
    if rows:
        section.blocks.append(
            Block("table", headers=["Segment", "Revenue", "Change", "Commentary"], rows=rows)
        )
    return section


def _liquidity(sections: dict) -> Section:
    section = Section("Liquidity & Capital Structure")
    data = sections.get("liquidity_capital_structure")
    if isinstance(data, str):
        text = _clean(data)
        if text and not is_placeholder(text):
            section.blocks.append(Block("paragraph", text=text))
        return section
    if not isinstance(data, dict):
        return section

    leverage = _clean(data.get("leverage"))
    if leverage and not is_placeholder(leverage):
        section.blocks.append(Block("paragraph", text=f"Leverage: {leverage}"))
    liquidity = _clean(data.get("liquidity"))
    if liquidity and not is_placeholder(liquidity):
        section.blocks.append(Block("paragraph", text=f"Liquidity: {liquidity}"))
    returns = _str_list(data.get("shareholder_returns") or data.get("shareholderReturns"))
    returns = [r for r in returns if not is_placeholder(r)]
    if returns:
        section.blocks.append(Block("bullets", text="Shareholder returns", items=returns))
    return section


def _guidance_outlook(sections: dict) -> Section:
    section = Section("Forward Outlook & Investment Implications")
    data = sections.get("guidance_outlook")
    if isinstance(data, str):
        text = _clean(data)
        if text and not is_placeholder(text):
            section.blocks.append(Block("paragraph", text=text))
        return section
    if not isinstance(data, dict):
        return section

    # AI schema uses "guidance"; the pipeline's wrap variant uses "outlook".
    guidance = _clean(data.get("guidance") or data.get("outlook"))
    if guidance and guidance != "Not disclosed" and not is_placeholder(guidance):
        # Prose, not a "Guidance:" field-name scaffold (T1.1) — matches the web renderer.
        section.blocks.append(Block("paragraph", text=guidance))
    tone = _clean(data.get("tone"))
    if tone and tone.lower() not in ("neutral", ""):
        section.blocks.append(
            Block("paragraph", text=f"Management's outlook tone was {tone.lower()}.")
        )
    for label, key, alt in (
        ("Drivers", "drivers", None),
        ("Watch items", "watch_items", "watchItems"),
        ("Targets", "targets", None),
        ("Assumptions", "assumptions", None),
    ):
        items = _str_list(data.get(key) or (data.get(alt) if alt else None))
        items = [item for item in items if not is_placeholder(item)]
        if items:
            section.blocks.append(Block("bullets", text=label, items=items))
    return section


def _notable_footnotes(sections: dict) -> Section:
    section = Section("Notable Footnotes")
    data = sections.get("notable_footnotes")
    rows: List[List[str]] = []
    if isinstance(data, list):
        for fn in data:
            if isinstance(fn, dict):
                item = _clean(fn.get("item"))
                impact = _clean(fn.get("impact"))
                if item or impact:
                    rows.append([item, impact])
            else:
                text = _clean(fn)
                if text and not is_placeholder(text):
                    rows.append([text, ""])
    if rows:
        section.blocks.append(Block("table", headers=["Item", "Impact"], rows=rows))
    return section


def _three_year_trend(sections: dict) -> Section:
    section = Section("3-Year Investment Perspective")
    data = sections.get("three_year_trend")
    if isinstance(data, str):
        text = _clean(data)
        if text and not is_placeholder(text):
            section.blocks.append(Block("paragraph", text=text))
        return section
    if not isinstance(data, dict):
        return section

    summary = _clean(data.get("trend_summary") or data.get("summary"))
    if summary and not is_placeholder(summary):
        section.blocks.append(Block("paragraph", text=summary))
    inflections = [i for i in _str_list(data.get("inflections")) if not is_placeholder(i)]
    if inflections:
        section.blocks.append(Block("bullets", text="Inflections", items=inflections))
    compare = data.get("compare_prior_period") or data.get("comparePriorPeriod")
    if isinstance(compare, dict):
        insights = [i for i in _str_list(compare.get("insights")) if not is_placeholder(i)]
        if insights:
            section.blocks.append(Block("bullets", text="Prior-period comparison", items=insights))
    return section


# Ordered to mirror the on-page tab order (with segments/footnotes slotted near their kin).
_BUILDERS: tuple[Callable[[dict], Section], ...] = (
    _executive_snapshot,
    _financial_highlights,
    _risk_factors,
    _management_discussion,
    _segment_performance,
    _liquidity,
    _guidance_outlook,
    _notable_footnotes,
    _three_year_trend,
)


def render_sections(raw_summary: Optional[dict]) -> List[Section]:
    """Turn a summary's ``raw_summary`` into an ordered list of non-empty rendered sections."""
    raw_summary = raw_summary or {}
    sections = raw_summary.get("sections") if isinstance(raw_summary, dict) else None
    if not isinstance(sections, dict):
        return []
    rendered: List[Section] = []
    for builder in _BUILDERS:
        section = builder(sections)
        if section.has_content:
            rendered.append(section)
    return rendered
