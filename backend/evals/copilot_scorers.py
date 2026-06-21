"""Deterministic scorers for the "Ask this Filing" Copilot eval (P8).

Three reproducible, no-network checks that encode the feature's core promises:

* **Citation faithfulness** — every text citation's excerpt must appear verbatim in the filing
  (reusing the product's own ``verify_excerpt_in_text``). A citation that doesn't verify is the exact
  hallucination the feature claims to prevent, so it's a hard gate. XBRL/tool citations are exempt
  (their provenance is the ``financial_fact`` table, not the filing prose).
* **Refusal calibration** — a question the filing does not disclose must be refused ("not disclosed"),
  and a disclosed one must be answered. Measures honest "I don't know" behaviour both ways.
* **Numeric accuracy** — for targeted numeric questions, the expected figure must appear in the answer
  (reuses the summary harness's value-rendering matcher).

The LLM judge stays a corroborating signal elsewhere; these gates are the primary, deterministic verdict.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from app.services.provenance_service import normalize_for_match, verify_excerpt_in_text
from evals.copilot_schema import CopilotAnswerScore, CopilotQACase
from evals.scorers import score_numeric_accuracy


def _is_xbrl_citation(citation: dict) -> bool:
    """XBRL/tool citations are grounded in financial_fact, not the filing prose — exempt from the
    verbatim-text check (their section_ref is rendered as ``XBRL · <tag>``)."""
    return str(citation.get("section_ref") or "").strip().upper().startswith("XBRL")


def score_citation_faithfulness(
    citations: List[dict], normalized_source: str
) -> Tuple[float, List[str]]:
    """Independently re-verify each text citation's excerpt against the (normalized) filing text.

    Returns ``(ratio_verified, unverified_excerpts)``. We do NOT trust the answer's own ``verified``
    flag — the whole point is to catch a citation the product wrongly trusted. With no text citations
    the ratio is 1.0 (nothing to falsify)."""
    text_citations = [c for c in citations if not _is_xbrl_citation(c)]
    if not text_citations:
        return 1.0, []
    unverified: List[str] = []
    for cite in text_citations:
        excerpt = str(cite.get("excerpt") or "")
        if not verify_excerpt_in_text(excerpt, normalized_source):
            unverified.append(excerpt)
    verified = len(text_citations) - len(unverified)
    return round(verified / len(text_citations), 4), unverified


def score_refusal(kind: str, disclosed: bool) -> bool:
    """True when the model's answer/refusal matches whether the filing discloses the answer."""
    refused = kind == "not_disclosed"
    return refused == (not disclosed)


def score_numeric_recall(answer: str, qa: CopilotQACase) -> Tuple[float, List[str]]:
    """Fraction of the case's expected financial facts that appear in the answer prose (1.0 when the
    case lists none). Only meaningful for disclosed numeric questions."""
    if not qa.expected_facts:
        return 1.0, []
    recall, _matched, missing = score_numeric_accuracy(answer, qa.expected_facts)
    return recall, missing


def score_copilot_answer(
    qa: CopilotQACase,
    *,
    answer: str,
    citations: List[dict],
    kind: str,
    filing_text: Optional[str] = None,
    normalized_source: Optional[str] = None,
) -> CopilotAnswerScore:
    """Score one answered question into a :class:`CopilotAnswerScore` with hard gate failures.

    Pass either ``filing_text`` (normalized here) or a pre-computed ``normalized_source``.
    """
    if normalized_source is None:
        normalized_source = normalize_for_match(filing_text or "")

    refusal_correct = score_refusal(kind, qa.disclosed)
    faithfulness, unverified = score_citation_faithfulness(citations, normalized_source)

    # Numeric recall only applies to a disclosed question that was actually answered.
    if qa.disclosed and kind != "not_disclosed":
        numeric_recall, missing = score_numeric_recall(answer, qa)
    else:
        numeric_recall, missing = 1.0, []

    gate_failures: List[str] = []
    if not refusal_correct:
        gate_failures.append(
            "REFUSAL: answered a not-disclosed question"
            if not qa.disclosed
            else "REFUSAL: refused a disclosed question"
        )
    if unverified:
        gate_failures.append(f"CITATION: {len(unverified)} excerpt(s) not found verbatim in filing")
    if missing:
        gate_failures.append(f"NUMERIC: missing expected figure(s): {', '.join(missing)}")

    return CopilotAnswerScore(
        question=qa.question,
        kind=kind,
        refusal_correct=refusal_correct,
        citation_faithfulness=faithfulness,
        unverified_excerpts=unverified,
        numeric_recall=numeric_recall,
        missing_metrics=missing,
        grounded=sum(1 for c in citations if c.get("verified")),
        gate_failures=gate_failures,
    )
