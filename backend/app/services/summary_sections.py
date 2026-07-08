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

import re
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


# Model prose can carry INLINE markdown: the analyst prompt is markdown-first ("YOU PRODUCE A
# SINGLE, COHESIVE MARKDOWN SUMMARY") and demonstrates **bold** in its own examples, so the model is
# primed to emit it inside JSON string fields too. Every prior web path fed those strings through
# ReactMarkdown, which silently beautified them; the structured page renders raw text nodes, so the
# same string would show literal "**Revenue**" on the page while rendering bold in the derived
# markdown and raw in the CSV — three cosmetic renderings of one string. Normalize inline markup
# ONCE here, at the single projection, so web / markdown / PDF / CSV all agree by construction.
_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")   # [text](url) -> text
_MD_BOLD = re.compile(r"\*\*(.+?)\*\*")            # **bold**   -> bold
_MD_CODE = re.compile(r"`([^`]+)`")                # `code`     -> code
_MD_ITALIC = re.compile(r"\*([^*\n]+)\*")          # *italic*   -> italic (after bold is unwrapped)


def _strip_inline_markdown(text: str) -> str:
    """Unwrap inline markdown emphasis/links to plain text (leaves lone ``*`` and prose untouched)."""
    text = _MD_LINK.sub(r"\1", text)
    text = _MD_BOLD.sub(r"\1", text)
    text = _MD_CODE.sub(r"\1", text)
    text = _MD_ITALIC.sub(r"\1", text)
    return text


def _clean(value: Any) -> str:
    """Return a trimmed, inline-markdown-normalized string for str/number inputs, else ""."""
    if isinstance(value, str):
        return _strip_inline_markdown(value.strip())
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
        - "metrics":   a financial-highlights table — ``headers`` + ``rows`` (the string projection
                       every surface renders) PLUS ``metric_rows`` (typed row dicts carrying the
                       computed change_display/direction/tone + per-metric provenance) that the web
                       renders richly (FinancialMetricsTable). Exports treat it exactly like a table.
        - "callout":   ``label`` (a short tag, e.g. "Red flag") + ``text`` — a highlighted note.
    """

    kind: str
    text: str = ""
    speaker: str = ""
    label: str = ""
    items: List[str] = field(default_factory=list)
    headers: List[str] = field(default_factory=list)
    rows: List[List[str]] = field(default_factory=list)
    # Typed rows for the "metrics" kind (the web renders these; the string ``rows`` above are the
    # export/markdown projection of the same data). Left empty for every other kind.
    metric_rows: List[dict] = field(default_factory=list)
    # Optional anchored citation for a block/claim {excerpt, section_ref, verified, fragment_url};
    # plumbed here for the Tier-4 citation upgrade, unused until then.
    evidence: Optional[dict] = None

    @property
    def is_empty(self) -> bool:
        return not (self.text or self.items or self.rows or self.metric_rows)

    def to_dict(self) -> dict:
        """JSON-serializable projection consumed by the web (rendered_sections). Omits empty fields."""
        out: dict = {"kind": self.kind}
        if self.text:
            out["text"] = self.text
        if self.speaker:
            out["speaker"] = self.speaker
        if self.label:
            out["label"] = self.label
        if self.items:
            out["items"] = self.items
        if self.headers:
            out["headers"] = self.headers
        if self.rows:
            out["rows"] = self.rows
        if self.metric_rows:
            out["metric_rows"] = self.metric_rows
        if self.evidence:
            out["evidence"] = self.evidence
        return out


def _slugify(title: str) -> str:
    """Stable anchor slug from a section title (for the web TOC / deep links)."""
    slug = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")
    return slug or "section"


@dataclass
class Section:
    title: str
    blocks: List[Block] = field(default_factory=list)
    id: str = ""
    # Explicit machine contract for specially-rendered sections (e.g. "risks"), so the web matches on
    # a stable role instead of a hand-mirrored title slug that a title tweak would silently break.
    role: str = ""
    # Management's disclosed/outlook sentiment, surfaced by the web as a Badge (T1.2 treatment) rather
    # than a prose sentence — set only for a clear non-neutral tone.
    tone: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = _slugify(self.title)

    @property
    def has_content(self) -> bool:
        return any(not block.is_empty for block in self.blocks)

    def to_dict(self) -> dict:
        out: dict = {
            "id": self.id,
            "title": self.title,
            "blocks": [b.to_dict() for b in self.blocks if not b.is_empty],
        }
        if self.role:
            out["role"] = self.role
        if self.tone:
            out["tone"] = self.tone
        return out


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
    # Tone rides on the Section (rendered as a Badge), not as a leading prose sentence — otherwise
    # "Management's disclosed tone was positive." becomes sentence two of the homepage-hero excerpt.
    tone = _clean(data.get("tone"))
    if tone and tone.lower() not in ("neutral", ""):
        section.tone = tone.lower()
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
    metric_rows: List[dict] = []
    table = data.get("table")
    if isinstance(table, list):
        for row in table:
            if not isinstance(row, dict):
                continue
            metric = _clean(row.get("metric"))
            if not metric:
                continue
            # Single delta policy (T1.5): compute the Change cell from current/prior so CSV+PDF match
            # the table and chips (ppts for margins). When it's not computable (mixed/unparseable
            # values), show no delta ("—") — the SAME fallback the web table uses — rather than the
            # model's own unverified change text, which would reintroduce the divergence T1.5 kills.
            _delta = metric_delta_service.delta_for_row(row)
            change_cell = _delta.display if _delta and _delta.display else "—"
            rows.append(
                [
                    metric,
                    _clean(row.get("current_period") or row.get("currentPeriod")),
                    _clean(row.get("prior_period") or row.get("priorPeriod")),
                    change_cell,
                    _clean(row.get("commentary")),
                ]
            )
            # Typed row the web renders richly (tone colours + provenance chips). Pass the row
            # through (it carries change_display/direction/tone + source_* once enriched) and
            # ensure the delta fields exist even on the unenriched pipeline path. String values are
            # inline-markdown-normalized so the web table (which renders these raw dicts, not the
            # string projection above) shows the same clean prose as every other surface.
            typed = {
                key: (_strip_inline_markdown(val) if isinstance(val, str) else val)
                for key, val in row.items()
            }
            if _delta and _delta.display:
                typed.setdefault("change_display", _delta.display)
                typed.setdefault("change_direction", _delta.direction)
                typed.setdefault("change_tone", _delta.tone)
            metric_rows.append(typed)
    if rows:
        section.blocks.append(
            Block(
                "metrics",
                headers=["Metric", "Current Period", "Prior Period", "Change", "Investor Takeaway"],
                rows=rows,
                metric_rows=metric_rows,
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
    section = Section("Investment Risks & Concerns", role="risks")
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
    # Outlook sentiment as a Badge (consistent with the exec section), not a prose sentence.
    tone = _clean(data.get("tone"))
    if tone and tone.lower() not in ("neutral", ""):
        section.tone = tone.lower()
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


def _builders_for(schema_version: Any) -> tuple[Callable[[dict], Section], ...]:
    """Select the section builders for a summary's schema version. Only v1 exists today (and
    legacy/NULL rows are v1); the Tier-3 content re-architecture registers a v2 builder set here so
    render_sections keeps rendering old rows correctly after the cutover."""
    return _BUILDERS


def render_sections(raw_summary: Optional[dict]) -> List[Section]:
    """Turn a summary's ``raw_summary`` into an ordered list of non-empty rendered sections."""
    raw_summary = raw_summary or {}
    if not isinstance(raw_summary, dict):
        return []
    sections = raw_summary.get("sections")
    if not isinstance(sections, dict):
        return []
    rendered: List[Section] = []
    for builder in _builders_for(raw_summary.get("schema_version")):
        section = builder(sections)
        if section.has_content:
            rendered.append(section)
    return rendered


def render_sections_json(raw_summary: Optional[dict]) -> List[dict]:
    """render_sections serialized to JSON-friendly dicts (the web's ``rendered_sections`` payload)."""
    return [s.to_dict() for s in render_sections(raw_summary)]


def _md_cell(text: Any) -> str:
    """Escape a table cell for GFM (pipes + newlines break the grid)."""
    return str(text).replace("|", "\\|").replace("\n", " ").strip()


def _markdown_table(headers: List[str], rows: List[List[str]]) -> str:
    if not rows:
        return ""
    cols = len(headers) if headers else max((len(r) for r in rows), default=0)
    if cols == 0:
        return ""

    def _line(cells: List[str]) -> str:
        padded = list(cells) + [""] * (cols - len(cells))
        return "| " + " | ".join(_md_cell(c) for c in padded[:cols]) + " |"

    head = headers if headers else [""] * cols
    out = [_line(head), "| " + " | ".join(["---"] * cols) + " |"]
    out += [_line(r) for r in rows]
    return "\n".join(out)


def _block_to_markdown(block: Block) -> str:
    if block.kind == "paragraph":
        return block.text.strip()
    if block.kind == "subheading":
        return f"### {block.text.strip()}"
    if block.kind == "quote":
        speaker = f" — {block.speaker.strip()}" if block.speaker else ""
        return f'> "{block.text.strip()}"{speaker}'
    if block.kind == "bullets":
        lines: List[str] = []
        if block.text:
            lines.append(f"**{block.text.strip()}**")
        lines += [f"- {item}" for item in block.items if str(item).strip()]
        return "\n".join(lines)
    if block.kind in ("table", "metrics"):
        return _markdown_table(block.headers, block.rows)
    if block.kind == "callout":
        label = f"**{block.label.strip()}:** " if block.label else ""
        return f"{label}{block.text.strip()}"
    return ""


def sections_to_markdown(sections: List[Section]) -> str:
    """Flatten rendered Section/Block output into clean GFM markdown.

    This is the DERIVED ``business_overview`` — produced from the SAME ``render_sections`` projection
    that feeds the PDF and CSV, so the three surfaces can never diverge (Tier 2). Section titles
    become H2; ``table``/``metrics`` become GFM tables; there are no leaked field-name labels.
    """
    parts: List[str] = []
    for section in sections:
        block_md = [md for md in (_block_to_markdown(b) for b in section.blocks if not b.is_empty) if md]
        if not block_md:
            continue
        parts.append(f"## {section.title}")
        parts.append("\n\n".join(block_md))
    return "\n\n".join(parts).strip()
