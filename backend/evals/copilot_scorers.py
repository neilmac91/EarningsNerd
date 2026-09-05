"""Deterministic scorers for the "Ask this Filing" Copilot eval (P8).

Four reproducible, no-network checks that encode the feature's core promises:

* **Citation faithfulness** — every text citation's excerpt must appear verbatim in the filing
  (reusing the product's own ``verify_excerpt_in_text``). A citation that doesn't verify is the exact
  hallucination the feature claims to prevent, so it's a hard gate. XBRL/tool citations are exempt
  (their provenance is the ``financial_fact`` table, not the filing prose)...
* **Fact-marker adjacency** — ...but XBRL citations get their own gate: every inline marker backed by
  a tool fact must sit adjacent to a figure matching that fact's value AND must not sit on a claim
  naming a different metric (field report: revenue markers reused as year labels on other metrics'
  figures). Reuses the production matchers + window rule from ``copilot_service`` — one definition
  of "adjacent", "matches", and "mislabeled".
* **Figure coverage** (WARN, not gated) — fraction of financial figures in the final answer that sit
  inside some citation's claim span. The misplacement guards convert wrongly-cited figures into
  UNCITED ones, so falling coverage after a prompt/model change is the drift signal to watch.
* **Refusal calibration** — a question the filing does not disclose must be refused ("not disclosed"),
  and a disclosed one must be answered. Measures honest "I don't know" behaviour both ways.
* **Numeric accuracy** — for targeted numeric questions, the expected figure must appear in the answer
  (reuses the summary harness's value-rendering matcher).

The LLM judge stays a corroborating signal elsewhere; these gates are the primary, deterministic verdict.
"""
from __future__ import annotations

import math
import re
from datetime import date
from typing import List, Optional, Tuple

from app.services.copilot_service import (
    _adjacency_window,
    _fact_matches_adjacent_concept,
    _fact_matches_adjacent_currency,
    _fact_matches_adjacent_number,
    count_uncited_figures,
)
from app.services.copilot_tools import canonical_unit
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
    """Independently re-verify VALUE + CONCEPT adjacency for every fact-backed marker in the
    final answer.

    The production resolver strips misplaced fact markers before the answer ships, so a violation
    here means the invariant regressed (or a prompt/model change found a new way to break it) —
    the shipped chip opens provenance for a different figure or metric than the claim it
    decorates. Like ``score_citation_faithfulness``, this does not trust the pipeline: it re-runs
    the same matchers (``_fact_matches_adjacent_number`` / ``_fact_matches_adjacent_concept``) and
    window rule (``_adjacency_window``) the product uses, over the answer the user actually sees.

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
        fact = {"value": cite["value"], "kind": cite.get("value_kind"), "concept": cite.get("concept"), "unit": cite.get("unit")}
        if not _fact_matches_adjacent_number(fact, window) or not _fact_matches_adjacent_concept(
            fact, window
        ) or not _fact_matches_adjacent_currency(fact, window):
            violations.append(f"[{match.group(1)}] {cite.get('excerpt', '')}".strip())
    if not checked:
        return 1.0, []
    return round((checked - len(violations)) / checked, 4), violations


def score_figure_coverage(answer: str, valid_count: Optional[int] = None) -> Tuple[float, int, int]:
    """Fraction of financial-looking figures in the final answer that sit inside some citation's
    claim span — ``(coverage_ratio, figure_count, uncited_count)``, 1.0 when there are no figures.

    Reuses the production ``count_uncited_figures`` (single definition of "figure" and "covered");
    ``valid_count`` = the resolved citations count, so literal leftover brackets don't grant
    coverage credit. WARN-level, not a hard gate: legitimate uncited numbers exist (a count in
    prose, a rounding restatement), but a *falling* coverage ratio after a prompt/model change
    means the model is stating more figures than it sources — the failure mode the misplacement
    guards convert into silent uncited prose.
    """
    figure_count, uncited = count_uncited_figures(answer, valid_count)
    if not figure_count:
        return 1.0, 0, 0
    return round((figure_count - uncited) / figure_count, 4), figure_count, uncited


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


def score_filing_provenance(citations: List[dict], accession: Optional[str],
                            report_period: Optional[str], currency: Optional[str]) -> List[str]:
    """Check every declared XBRL citation, including malformed/value-less ones.

    Display links and the pipeline's verified flag are never origin evidence. Direct older
    comparative periods are allowed only inside the viewed accession; derived operands must
    each carry the same origin and explicit duration basis.
    """
    def valid(row: dict, *, operand: bool = False) -> bool:
        if not isinstance(row, dict) or not accession or row.get('accession') != accession:
            return False
        if not re.fullmatch(r'\d{10}-\d{2}-\d{6}', accession):
            return False
        value = row.get('value')
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
            return False
        unit = canonical_unit(row.get('unit'))
        if unit is None or (currency and unit not in {currency, currency + '/shares', 'shares', 'pure'}):
            return False
        if any(not isinstance(row.get(k), str) or not row[k].strip() for k in ('concept', 'raw_tag')):
            return False
        try:
            end = date.fromisoformat(row['period_end'])
            start = date.fromisoformat(row['period_start']) if row.get('period_start') else None
            if start and start > end:
                return False
            if report_period and end > date.fromisoformat(report_period):
                return False
        except (KeyError, ValueError, TypeError):
            return False
        kind = row.get('value_kind') or row.get('kind')
        if kind is not None:
            parts = row.get('source_facts')
            if operand or kind not in {'margin', 'yoy_growth'} or unit != 'pure':
                return False
            if not isinstance(parts, list) or len(parts) != 2:
                return False
            if not all(valid(p, operand=True) and p.get('period_start') for p in parts):
                return False
        return True
    return [f"[{c.get('n', '?')}] invalid viewed-filing provenance" for c in citations
            if _is_xbrl_citation(c) and not valid(c)]


def score_copilot_answer(
    qa: CopilotQACase,
    *,
    answer: str,
    citations: List[dict],
    kind: str,
    filing_text: Optional[str] = None,
    normalized_source: Optional[str] = None,
    accession_number: Optional[str] = None,
    period_of_report: Optional[str] = None,
    reporting_currency: Optional[str] = None,
) -> CopilotAnswerScore:
    """Score one answered question into a :class:`CopilotAnswerScore` with hard gate failures.

    Pass either ``filing_text`` (normalized here) or a pre-computed ``normalized_source``.
    """
    if normalized_source is None:
        normalized_source = normalize_for_match(filing_text or "")

    refusal_correct = score_refusal(kind, qa.disclosed)
    faithfulness, unverified = score_citation_faithfulness(citations, normalized_source)
    adjacency, misplaced = score_fact_marker_adjacency(answer, citations)
    # Coverage only applies to answered questions: a refusal's explanation sentence carries no
    # citations by design, so counting its figures as "uncited" is pure noise in the report.
    if kind != "not_disclosed":
        figure_coverage, figure_count, uncited_figures = score_figure_coverage(answer, len(citations))
    else:
        figure_coverage, figure_count, uncited_figures = 1.0, 0, 0

    # Numeric recall only applies to a disclosed question that was actually answered.
    if qa.disclosed and kind != "not_disclosed":
        numeric_recall, missing = score_numeric_recall(answer, qa)
    else:
        numeric_recall, missing = 1.0, []

    invalid_provenance = score_filing_provenance(citations, accession_number, period_of_report, reporting_currency)
    contradictory_currencies = [f.metric for f in qa.expected_facts
        if not _fact_matches_adjacent_currency({"value": f.value, "unit": f.unit}, answer)]
    gate_failures: List[str] = []
    if invalid_provenance:
        gate_failures.append(f"PROVENANCE: {len(invalid_provenance)} invalid XBRL citation(s)")
    if contradictory_currencies:
        gate_failures.append("CURRENCY: " + ", ".join(contradictory_currencies))
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
        figure_coverage=figure_coverage,
        figure_count=figure_count,
        uncited_figures=uncited_figures,
        numeric_recall=numeric_recall,
        missing_metrics=missing,
        grounded=sum(1 for c in citations if c.get("verified")),
        gate_failures=gate_failures,
        invalid_provenance=invalid_provenance,
        contradictory_currencies=contradictory_currencies,
    )
