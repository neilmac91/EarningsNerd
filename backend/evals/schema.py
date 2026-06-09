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
    missing_sections: List[str] = field(default_factory=list)
    matched_facts: List[str] = field(default_factory=list)
    missing_facts: List[str] = field(default_factory=list)

    def aggregate(self) -> float:
        """Single 0-1 quality number. Weights schema-validity, grounding, and coverage.

        Numeric accuracy is weighted highest because a confidently-wrong financial summary is
        the worst activation outcome; schema validity is a gate-style signal (the whole point
        of S1) so it carries real weight too."""
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
