"""SummaryDoc v2 — the content schema for the Tier-3.1 re-architecture.

The v1 summary taxonomy (``openai_service._TRACKED_STRUCTURED_SECTIONS``) is a data-dump: nine
sections that repeat the same figures and split trend framing across three of them. v2 is the
finance-grounded architecture from ``docs/summary-quality-improvement-plan.md`` Part 3.1 — an
inverted pyramid where **each number has exactly one home**, with two new analytical sections
(``earnings_quality``, ``value_drivers``) and the redundant ``management_discussion_insights`` /
``three_year_trend`` dissolved.

This module is the single source of truth for the v2 SHAPE. Three consumers reference it:

1. the v2 render builders (``summary_sections._BUILDERS_V2``) turn these shapes into Section/Block;
2. the generation ``schema_template`` (Tier-3.1 PR B) mirrors these fields for the model to emit;
3. the quality badge (``summary_generation_service._verdict_coverage``) counts ``TRACKED_SECTIONS_V2``.

Fields are intentionally lenient (optional, ``extra="ignore"``): the model may omit a section a
filing does not support (a 6-K rarely has segments), and the render builders already drop empty
sections. ``SummaryDoc.model_validate`` is used to sanity-check shape in tests and (PR B) to validate
parsed model output before json-repair fallback — it rejects wrong TYPES, not missing sections.

The v1 taxonomy is NOT defined here — it lives at its original site and keeps rendering legacy rows
via the v1 builders. This module adds v2 alongside; it never edits v1.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# --- section-key taxonomies by schema version --------------------------------------------------
# The quality badge (summary_generation_service._verdict_coverage) counts a stored row's populated
# sections against the taxonomy for THAT row's schema_version. Both tuples are FROZEN LITERALS here
# — deliberately NOT imported from openai_service, whose ``_TRACKED_STRUCTURED_SECTIONS`` is the
# generation-side "what we emit NOW" and flips to v2 at the cutover. The badge's notion of "what a v1
# row was supposed to contain" is historical fact and must not follow that flip: if the v1 badge arm
# tracked the generation constant, every legacy v1 row would count 0/9 and tier "partial" (billing
# off with AI_QUALITY_GATE) the moment PR B re-points the generation tuple to v2.
TRACKED_SECTIONS_V1: tuple[str, ...] = (
    "executive_snapshot",
    "financial_highlights",
    "risk_factors",
    "management_discussion_insights",
    "segment_performance",
    "liquidity_capital_structure",
    "guidance_outlook",
    "notable_footnotes",
    "three_year_trend",
)

# The canonical v2 section keys, in on-page order. `openai_service` (PR B) emits these; the quality
# badge counts them; the render builders key off them. Keep this tuple, SummaryDocSections' field
# names, and _BUILDERS_V2's order in lockstep.
TRACKED_SECTIONS_V2: tuple[str, ...] = (
    "the_print",
    "results_that_matter",
    "earnings_quality",
    "value_drivers",
    "forward_signals",
    "risks",
    "segments",
    "balance_sheet_liquidity",
    "notable_footnotes",
)

# Display metadata for each v2 section, consumed by the render builders so titles/roles live in one
# place. `role` marks specially-rendered sections (the web matches on the stable role, not the title).
SECTION_META: dict[str, dict[str, str]] = {
    "the_print": {"title": "The Print"},
    "results_that_matter": {"title": "Results That Matter"},
    "earnings_quality": {"title": "Earnings Quality & Cash Conversion"},
    "value_drivers": {"title": "Value Drivers & Capital Allocation"},
    "forward_signals": {"title": "Forward Signals"},
    "risks": {"title": "Risks", "role": "risks"},
    "segments": {"title": "Segments"},
    "balance_sheet_liquidity": {"title": "Balance Sheet & Liquidity"},
    "notable_footnotes": {"title": "Notable Footnotes"},
}


class _V2Base(BaseModel):
    # Lenient by design — the model emits JSON that may carry extra keys or omit optional ones.
    model_config = ConfigDict(extra="ignore")


# --- shared row/item sub-models ----------------------------------------------------------------


class PLMetricRow(_V2Base):
    """One row of the §2 P&L table. Values are model-emitted; the renderer computes the Change cell
    from current/prior via metric_delta_service (ppts for margins) — the model's own `change` text is
    a fallback only. `commentary` is the one-line driver."""

    metric: str = ""
    current_period: str = ""
    prior_period: str = ""
    change: str = ""
    commentary: str = ""


class ManagementQuote(_V2Base):
    """A verbatim, attributed management quote (§5 — forward-looking or unusual statements only)."""

    speaker: str = ""
    quote: str = ""
    context: str = ""


class RiskItem(_V2Base):
    """§6 risk tied to a specific line item with anchored evidence. Same shape as v1 risk_factors so
    the risks render path + the frontend SummaryRisks trace-to-source treatment carry over."""

    summary: str = ""
    supporting_evidence: str = ""
    materiality: str = ""
    source_section_ref: str = ""


class SegmentRow(_V2Base):
    """§7 segment row: revenue + operating income + change + mix commentary."""

    segment: str = ""
    revenue: str = ""
    operating_income: str = ""
    change: str = ""
    commentary: str = ""
    source_section_ref: str = ""


class FootnoteItem(_V2Base):
    """§9 fine-print item (SBC, related-party, rev-rec changes, contingencies, concentrations)."""

    item: str = ""
    impact: str = ""
    source_section_ref: str = ""


# --- object sections ---------------------------------------------------------------------------


class ThePrint(_V2Base):
    """§1 — the reaction-note lead. Absorbs Key Takeaways; echoes ≤3 headline figures by reference,
    each with driver + so-what; states what this filing changes."""

    headline: str = ""
    key_takeaways: List[str] = Field(default_factory=list)
    what_changed: str = ""
    tone: str = ""
    source_section_ref: str = ""


class ResultsThatMatter(_V2Base):
    """§2 — the single P&L table (revenue, operating income, operating margin in ppts, diluted EPS),
    each with a one-line driver. Cash lines live in §3, never here."""

    table: List[PLMetricRow] = Field(default_factory=list)
    source_section_ref: str = ""


class EarningsQuality(_V2Base):
    """§3 — the differentiator: operating-vs-one-time bridge (adjusted vs reported), the NI-vs-CFO
    accrual read + FCF/conversion, and a red-flag scan. Model-extracted in T3.1; T5 adds
    deterministic feeds."""

    operating_vs_one_time: str = ""
    cash_conversion: str = ""
    red_flags: List[str] = Field(default_factory=list)
    source_section_ref: str = ""


class ValueDrivers(_V2Base):
    """§4 — capital allocation this period (buybacks/dividends/M&A/capex) with a value verdict, and
    ROIC level + trend from the filing's own XBRL (no cost-of-capital judgment — WACC is not filing
    data)."""

    capital_allocation: str = ""
    returns_on_capital: str = ""
    highlights: List[str] = Field(default_factory=list)
    source_section_ref: str = ""


class ForwardSignals(_V2Base):
    """§5 — guidance as the filing itself states it (raised/cut/maintained/not given, with why it
    matters when absent), known trends & uncertainties (Item 303), subsequent events, and management
    quoted verbatim only when forward-looking or unusual."""

    guidance: str = ""
    known_trends: List[str] = Field(default_factory=list)
    subsequent_events: List[str] = Field(default_factory=list)
    quotes: List[ManagementQuote] = Field(default_factory=list)
    tone: str = ""
    source_section_ref: str = ""


class BalanceSheetLiquidity(_V2Base):
    """§8 — leverage, debt maturities and covenants, liquidity runway, and working-capital dynamics.
    Absorbs the v1 orphan `covenants_contingencies` node. Shareholder returns live in §4."""

    leverage: str = ""
    liquidity: str = ""
    working_capital: str = ""
    maturities_covenants: List[str] = Field(default_factory=list)
    source_section_ref: str = ""


class SummaryDocSections(_V2Base):
    """The nine v2 sections. All optional — an absent section is dropped by the render builder, not an
    error (a 6-K may legitimately carry only §1 + §5)."""

    the_print: Optional[ThePrint] = None
    results_that_matter: Optional[ResultsThatMatter] = None
    earnings_quality: Optional[EarningsQuality] = None
    value_drivers: Optional[ValueDrivers] = None
    forward_signals: Optional[ForwardSignals] = None
    risks: List[RiskItem] = Field(default_factory=list)
    segments: List[SegmentRow] = Field(default_factory=list)
    balance_sheet_liquidity: Optional[BalanceSheetLiquidity] = None
    notable_footnotes: List[FootnoteItem] = Field(default_factory=list)

    @field_validator("risks", "segments", "notable_footnotes", mode="before")
    @classmethod
    def _none_to_empty(cls, v):
        """A model rendering "no items" as ``null`` (common alongside omission) means ``[]``, not a
        type error — so ``"risks": null`` validates to an empty list rather than spuriously routing an
        otherwise-good payload into the json-repair fallback (PR B validates model output with this).
        A wrong type (``"risks": "a string"``) still rejects."""
        return [] if v is None else v


class SummaryDocMetadata(_V2Base):
    company_name: str = ""
    filing_type: str = ""
    reporting_period: str = ""
    filing_date: str = ""
    currency: str = ""
    has_prior_period: bool = False


class SummaryDoc(_V2Base):
    """The v2 content document the generator emits: metadata + the nine sections."""

    metadata: SummaryDocMetadata = Field(default_factory=SummaryDocMetadata)
    sections: SummaryDocSections = Field(default_factory=SummaryDocSections)
