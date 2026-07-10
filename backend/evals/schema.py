"""Canonical data shapes for the eval harness.

The harness compares every candidate (baseline pipeline, gemini+JSON-mode, Claude, Qwen,
Kimi, DeepSeek, ...) on the SAME canonical summary shape so scoring is apples-to-apples.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# The structured shape every candidate must produce. Kept deliberately small and close to
# what the product renders, so a win here is a win in the product.
EVAL_SUMMARY_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "executive_summary": {"type": "string"},
        "financial_highlights": {
            "type": "object",
            "properties": {
                "revenue": {"type": "string"},
                "net_income": {"type": "string"},
                "eps": {"type": "string"},
                "key_metrics": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["revenue", "net_income", "eps", "key_metrics"],
            "additionalProperties": False,
        },
        "risk_factors": {"type": "array", "items": {"type": "string"}},
        "management_discussion": {"type": "string"},
        "outlook": {"type": "string"},
    },
    "required": [
        "executive_summary",
        "financial_highlights",
        "risk_factors",
        "management_discussion",
        "outlook",
    ],
    "additionalProperties": False,
}

# Sections scored for "substantive coverage". Mirrors the schema's top-level fields.
REQUIRED_SECTIONS = (
    "executive_summary",
    "financial_highlights",
    "risk_factors",
    "management_discussion",
    "outlook",
)


@dataclass
class GroundTruthFact:
    """A financial fact the summary must get right, normally sourced from XBRL."""

    metric: str  # e.g. "revenue", "net_income", "eps"
    value: float  # absolute value in `unit` terms (USD for currency; per-share for eps)
    unit: str = "USD"  # "USD" | "USD_per_share"
    # Alternate acceptable renderings of the SAME fact. The canonical case is EPS: ground truth
    # carries basic EPS as `value` and diluted EPS here, because a summary that reports diluted
    # EPS (the headline figure investors use) is correct, not a miss. A fact counts as matched/
    # non-contradicted when the output renders `value` OR any `alt_values` entry.
    alt_values: List[float] = field(default_factory=list)


@dataclass
class GoldenFiling:
    """One entry in the golden set."""

    ticker: str
    cik: str
    accession_number: str
    filing_type: str  # "10-K" | "10-Q"
    document_url: str
    company_name: str
    ground_truth: List[GroundTruthFact] = field(default_factory=list)
    # Operator must confirm accession/url against EDGAR + ground_truth before trusting scores.
    verified: bool = False
    notes: str = ""

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GoldenFiling":
        facts = [GroundTruthFact(**f) for f in d.get("ground_truth", [])]
        return cls(
            ticker=d["ticker"],
            cik=str(d["cik"]),
            accession_number=d["accession_number"],
            filing_type=d["filing_type"],
            document_url=d["document_url"],
            company_name=d.get("company_name", d["ticker"]),
            ground_truth=facts,
            verified=bool(d.get("verified", False)),
            notes=d.get("notes", ""),
        )


@dataclass
class RubricScore:
    """Per-filing score for a single candidate."""

    schema_valid: bool  # parsed against EVAL_SUMMARY_JSON_SCHEMA without repair
    repaired: bool  # needed JSON repair to parse (a soft failure of "enforced structure")
    numeric_accuracy: float  # [0,1] recall of ground-truth facts present in output
    coverage: float  # [0,1] fraction of required sections with substantive content
    # [0,1] precision of labeled financial fields: do the numbers in revenue/net_income/eps
    # match ground truth (vs. a confidently-wrong figure)? Recall asks "are the right numbers
    # present"; precision asks "are the present numbers right" — a hallucinated figure alongside
    # the correct one passes recall but fails precision. Closes the recall-only gap.
    numeric_precision: float = 1.0
    # [0,1] fraction of {cash_flow, balance_sheet, margins} surfaced with real figures
    # (report-quality P1). Reported alongside the aggregate (not folded into it, to keep the
    # adoption math stable) — it tracks whether the depth work is landing, run over run.
    financial_depth: float = 1.0
    # [0,1] narrative specificity (Wave 2): penalises vague boilerplate in the prose fields and
    # credits explicit period-over-period framing. Reported alongside the aggregate (NOT folded in),
    # so de-boilerplating prompt changes are measurable in CI without the LLM judge.
    specificity: float = 1.0
    # [0,1] currency-labeling fidelity for foreign (non-USD) filers (Wave 3 / FPI go-live): 1.0 for
    # USD/domestic; for RMB/EUR/DKK/TWD filers it falls toward 0 as figures are rendered as bare '$'
    # instead of the reporting currency — a mislabel the currency-agnostic numeric scorers can't see.
    # Reported alongside the aggregate (NOT folded in); WARN-gated (see regression_gate) pending
    # promotion to a hard FPI-adoption gate once the intermittent model slip is fixed.
    currency_consistency: float = 1.0
    # [0,1] "one home per number" (T3.0, plan defect c): penalises the same scaled/percent figure
    # being restated across the narrative prose sections of the rendered summary instead of living in
    # one home (the metrics/segment/footnote tables + at most a headline echo in the exec summary).
    # Measured by splitting the rendered markdown on its section headings and excluding the table
    # "home" sections. Reported alongside the aggregate (NOT folded in); WARN-gated in regression_gate
    # until a v2 run re-pins the baseline.
    redundancy: float = 1.0
    # [0,1] prose/table delta consistency (T3.0, plan defect g's prose residual): a direction-cued
    # percentage stated in the prose must not contradict the code-computed change in the metrics
    # table. Levels (e.g. "74.9%") and ppt/bps deltas are never compared, so it only fires on clear
    # contradictions. Reported alongside the aggregate (NOT folded in); WARN-gated.
    delta_consistency: float = 1.0
    # [0,1] §5 forward-quote verbatim fidelity (T5.4): fraction of Forward Signals blockquotes in
    # the rendered markdown locatable verbatim in the filing text, under the SAME normalization the
    # production forward_quote_gate / T4 evidence badge / copilot citations use. Neutral 1.0 when
    # there is no filing-text referent, no rendered markdown, or no verifiable quotes. Reported
    # alongside the aggregate (NOT folded in); WARN-gated in regression_gate — binds only after a
    # future re-pin records it (the gate skips metrics absent from the pinned baseline).
    forward_quote_fidelity: float = 1.0
    # Artifact-1 HARD GATES. A non-empty list is a promotion VETO independent of `aggregate()`:
    # a single fabricated number or leaked notice fails the summary no matter how good the prose.
    gate_failures: List[str] = field(default_factory=list)
    missing_sections: List[str] = field(default_factory=list)
    matched_facts: List[str] = field(default_factory=list)
    missing_facts: List[str] = field(default_factory=list)

    @property
    def passed_gates(self) -> bool:
        """True when no hard gate failed. Gate-passing is required for promotion."""
        return not self.gate_failures

    def aggregate(self) -> float:
        """Single 0-1 quality number. Weights schema-validity, grounding, and coverage.

        Numeric accuracy is weighted highest because a confidently-wrong financial summary is
        the worst activation outcome; schema validity is a gate-style signal (the whole point
        of S1) so it carries real weight too. NOTE: hard gates (`gate_failures`) are a separate
        veto and are deliberately NOT folded into this number — aggregate ranks the candidates
        that already cleared the gates."""
        schema_component = 1.0 if (self.schema_valid and not self.repaired) else (
            0.5 if self.schema_valid else 0.0
        )
        return round(
            0.30 * schema_component + 0.45 * self.numeric_accuracy + 0.25 * self.coverage,
            4,
        )


@dataclass
class EvalResult:
    """Result of running one candidate over one filing."""

    candidate: str
    ticker: str
    filing_type: str
    score: RubricScore
    latency_seconds: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    error: Optional[str] = None
