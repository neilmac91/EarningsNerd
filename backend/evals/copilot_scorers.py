"""Deterministic scorers for the "Ask this Filing" Copilot eval (P8).

Four reproducible, no-network checks that encode the feature's core promises:

* **Citation faithfulness** — every text citation's excerpt must appear verbatim in the filing
  (reusing the product's own ``verify_excerpt_in_text``). A citation that doesn't verify is the exact
  hallucination the feature claims to prevent, so it's a hard gate. XBRL/tool citations are exempt
  (their provenance is the ``financial_fact`` table, not the filing prose)...
* **Fact-marker adjacency** — ...but XBRL citations get their own gate: every inline marker backed by
  a tool fact must sit adjacent to a figure matching that fact's value (field report: revenue markers
  reused as year labels on other metrics' figures). Reuses the production matcher + window rule from
  ``copilot_service`` — one definition of "adjacent" and "matches".
* **Refusal calibration** — a question the filing does not disclose must be refused ("not disclosed"),
  and a disclosed one must be answered. Measures honest "I don't know" behaviour both ways.
* **Numeric accuracy** — for targeted numeric questions, the expected figure must appear in the answer
  (reuses the summary harness's value-rendering matcher).

The LLM judge stays a corroborating signal elsewhere; these gates are the primary, deterministic verdict.
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from app.services.copilot_service import _adjacency_window, _fact_matches_adjacent_number
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


def score_fact_marker_adjacency(answer: str, citations: List[dict]) -> Tuple[float, List[str]]:
    """Independently re-verify VALUE ADJACENCY for every fact-backed marker in the final answer.

    The production resolver strips misplaced fact markers before the answer ships, so a violation
    here means the invariant regressed (or a prompt/model change found a new way to break it) —
    the shipped chip opens provenance for a different figure than the claim it decorates. Like
    ``score_citation_faithfulness``, this does not trust the pipeline: it re-runs the same matcher
    (``_fact_matches_adjacent_number``) and window rule (``_adjacency_window``) the product uses,
    over the answer the user actually sees.

    Returns ``(ratio_ok, violations)`` where each violation names the marker and its excerpt.
    Citations without a machine-readable ``value`` (older payloads) can't be checked and are
    skipped; no fact markers at all → 1.0 (nothing to falsify).
    """
    facts_by_n: dict[str, dict] = {
        str(c.get("n")): c
        for c in citations
        if _is_xbrl_citation(c) and isinstance(c.get("value"), (int, float))
    }
    if not facts_by_n:
        return 1.0, []

    checked = 0
    violations: List[str] = []
    prev_marker_end = 0
    for match in re.finditer(r"\[(\d+)\]", answer):
        window = _adjacency_window(answer, match.start(), prev_marker_end)
        prev_marker_end = match.end()  # every marker (text or fact) ends the previous claim span
        cite = facts_by_n.get(match.group(1))
        if cite is None:
            continue
        checked += 1
        fact = {"value": cite["value"], "kind": cite.get("value_kind")}
        if not _fact_matches_adjacent_number(fact, window):
            violations.append(f"[{match.group(1)}] {cite.get('excerpt', '')}".strip())
    if not checked:
        return 1.0, []
    return round((checked - len(violations)) / checked, 4), violations


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
    adjacency, misplaced = score_fact_marker_adjacency(answer, citations)

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
    if misplaced:
        gate_failures.append(f"ADJACENCY: {len(misplaced)} fact marker(s) not on their own figure")
    if missing:
        gate_failures.append(f"NUMERIC: missing expected figure(s): {', '.join(missing)}")

    return CopilotAnswerScore(
        question=qa.question,
        kind=kind,
        refusal_correct=refusal_correct,
        citation_faithfulness=faithfulness,
        unverified_excerpts=unverified,
        fact_adjacency=adjacency,
        misplaced_fact_citations=misplaced,
        numeric_recall=numeric_recall,
        missing_metrics=missing,
        grounded=sum(1 for c in citations if c.get("verified")),
        gate_failures=gate_failures,
    )
