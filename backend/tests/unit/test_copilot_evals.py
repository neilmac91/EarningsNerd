"""Unit tests for the Copilot eval scorers (P8).

Pure, no-network checks of refusal calibration, citation faithfulness, and numeric accuracy — the
deterministic gates that make the harness CI-runnable on every change.
"""
import pytest

from app.services.provenance_service import normalize_for_match
from evals.copilot_schema import CopilotQACase
from evals.copilot_scorers import (
    score_citation_faithfulness,
    score_copilot_answer,
    score_fact_marker_adjacency,
    score_numeric_recall,
    score_refusal,
)
from evals.schema import GroundTruthFact

FILING = (
    "Item 7 — Management's Discussion and Analysis. "
    "Revenue increased to $391.0 billion in fiscal 2024 driven by strong iPhone demand. "
    "Operating margins expanded year over year."
)
NORM = normalize_for_match(FILING)

VERIFIED_EXCERPT = "Revenue increased to $391.0 billion in fiscal 2024 driven by strong iPhone demand."
FABRICATED_EXCERPT = "The company declared a special dividend of five dollars per share this quarter."


def _text_cite(excerpt, verified=True):
    return {"n": 1, "excerpt": excerpt, "section_ref": "Item 7 — MD&A", "verified": verified}


def _xbrl_cite():
    return {"n": "F1", "excerpt": "Revenue = $391.04B USD", "section_ref": "XBRL · us-gaap:Revenue", "verified": True}


def _fact_cite(n, value, *, excerpt="Revenue = $391.04B USD (FY2024)", value_kind=None):
    return {
        "n": n,
        "excerpt": excerpt,
        "section_ref": "XBRL · us-gaap:Revenues",
        "verified": True,
        "value": value,
        "value_kind": value_kind,
    }


# --- refusal calibration -----------------------------------------------------------------------

@pytest.mark.unit
def test_score_refusal_both_directions():
    assert score_refusal("answer", disclosed=True) is True          # answered a disclosed Q ✓
    assert score_refusal("not_disclosed", disclosed=False) is True  # refused an undisclosed Q ✓
    assert score_refusal("answer", disclosed=False) is False        # answered an undisclosed Q ✗
    assert score_refusal("not_disclosed", disclosed=True) is False  # refused a disclosed Q ✗


# --- citation faithfulness ---------------------------------------------------------------------

@pytest.mark.unit
def test_citation_faithfulness_verifies_real_excerpt():
    ratio, unverified = score_citation_faithfulness([_text_cite(VERIFIED_EXCERPT)], NORM)
    assert ratio == 1.0
    assert unverified == []


@pytest.mark.unit
def test_citation_faithfulness_flags_fabricated_excerpt_even_if_marked_verified():
    # The citation lies that it's verified; the scorer independently catches it.
    ratio, unverified = score_citation_faithfulness([_text_cite(FABRICATED_EXCERPT, verified=True)], NORM)
    assert ratio == 0.0
    assert unverified == [FABRICATED_EXCERPT]


@pytest.mark.unit
def test_citation_faithfulness_exempts_xbrl_and_handles_empty():
    # XBRL citation isn't verbatim filing text but is exempt → no penalty.
    ratio, unverified = score_citation_faithfulness([_xbrl_cite()], NORM)
    assert ratio == 1.0 and unverified == []
    # No citations at all → nothing to falsify.
    assert score_citation_faithfulness([], NORM) == (1.0, [])


# --- fact-marker adjacency ---------------------------------------------------------------------

@pytest.mark.unit
def test_fact_adjacency_passes_marker_on_its_own_figure():
    ratio, violations = score_fact_marker_adjacency(
        "Revenue was $391.04 billion in fiscal 2024 [1].", [_fact_cite(1, 391_040_000_000.0)]
    )
    assert ratio == 1.0 and violations == []


@pytest.mark.unit
def test_fact_adjacency_flags_marker_on_wrong_figure():
    # The field case shape: a revenue-backed chip decorating a different metric's figure.
    ratio, violations = score_fact_marker_adjacency(
        "Revenue was $391.04 billion [1]. Net income fell to $93.74 billion [1].",
        [_fact_cite(1, 391_040_000_000.0)],
    )
    assert ratio == 0.5
    assert len(violations) == 1 and violations[0].startswith("[1]")


@pytest.mark.unit
def test_fact_adjacency_window_bounded_by_previous_marker():
    # The correct figure sits just before the PREVIOUS marker — it must not vouch for the reuse.
    ratio, violations = score_fact_marker_adjacency(
        "Revenue was $391.04B [1], and $93.74B [1].", [_fact_cite(1, 391_040_000_000.0)]
    )
    assert ratio == 0.5 and len(violations) == 1


@pytest.mark.unit
def test_fact_adjacency_percent_kind_and_qualitative_skip():
    # Margin fact (fraction) matches its percent rendering...
    ratio, _ = score_fact_marker_adjacency(
        "Gross margin was 46.2% [1].", [_fact_cite(1, 0.462, value_kind="margin")]
    )
    assert ratio == 1.0
    # ...and a figure-free window (years don't count) can't falsify the placement.
    ratio, _ = score_fact_marker_adjacency(
        "Revenue growth stalled in 2024 [1].", [_fact_cite(1, 391_040_000_000.0)]
    )
    assert ratio == 1.0


@pytest.mark.unit
def test_fact_adjacency_skips_text_citations_and_valueless_facts():
    # Text citations and fact citations without a machine-readable value aren't checkable.
    ratio, violations = score_fact_marker_adjacency(
        "A special dividend was announced [1]; revenue context [2].",
        [_text_cite(VERIFIED_EXCERPT), _fact_cite(2, None)],
    )
    assert ratio == 1.0 and violations == []


# --- numeric recall ----------------------------------------------------------------------------

@pytest.mark.unit
def test_numeric_recall_present_and_missing():
    present = CopilotQACase(question="Revenue?", expected_facts=[GroundTruthFact("revenue", 391_000_000_000.0, "USD")])
    recall, missing = score_numeric_recall("Revenue rose to $391.0 billion.", present)
    assert recall == 1.0 and missing == []

    absent = CopilotQACase(question="Revenue?", expected_facts=[GroundTruthFact("revenue", 999_000_000_000.0, "USD")])
    recall, missing = score_numeric_recall("Revenue rose to $391.0 billion.", absent)
    assert recall == 0.0 and missing == ["revenue"]


# --- end-to-end answer scoring (gates) ---------------------------------------------------------

@pytest.mark.unit
def test_score_answer_clean_pass():
    qa = CopilotQACase(
        question="How did revenue do?",
        disclosed=True,
        expected_facts=[GroundTruthFact("revenue", 391_000_000_000.0, "USD")],
    )
    score = score_copilot_answer(
        qa,
        answer="Revenue increased to $391.0 billion [1].",
        citations=[_text_cite(VERIFIED_EXCERPT)],
        kind="answer",
        filing_text=FILING,
    )
    assert score.passed
    assert score.gate_failures == []
    assert score.refusal_correct and score.citation_faithfulness == 1.0 and score.numeric_recall == 1.0


@pytest.mark.unit
def test_score_answer_refuses_unanswerable_passes():
    qa = CopilotQACase(question="What is next year's guidance?", disclosed=False)
    score = score_copilot_answer(qa, answer="This filing does not disclose forward guidance.",
                                 citations=[], kind="not_disclosed", filing_text=FILING)
    assert score.passed
    assert score.refusal_correct is True


@pytest.mark.unit
def test_score_answer_fabricated_answer_to_unanswerable_fails_refusal_gate():
    qa = CopilotQACase(question="What is next year's guidance?", disclosed=False)
    score = score_copilot_answer(qa, answer="Guidance is $500B [1].",
                                 citations=[_text_cite(VERIFIED_EXCERPT)], kind="answer", filing_text=FILING)
    assert not score.passed
    assert any(g.startswith("REFUSAL") for g in score.gate_failures)


@pytest.mark.unit
def test_score_answer_unverified_citation_fails_citation_gate():
    qa = CopilotQACase(question="Any dividend?", disclosed=True)
    score = score_copilot_answer(qa, answer="A special dividend was announced [1].",
                                 citations=[_text_cite(FABRICATED_EXCERPT)], kind="answer", filing_text=FILING)
    assert not score.passed
    assert any(g.startswith("CITATION") for g in score.gate_failures)


@pytest.mark.unit
def test_score_answer_misplaced_fact_marker_fails_adjacency_gate():
    qa = CopilotQACase(question="How did revenue and profit trend?", disclosed=True)
    score = score_copilot_answer(
        qa,
        answer="Revenue was $391.04 billion [1]. Net income fell to $93.74 billion [1].",
        citations=[_fact_cite(1, 391_040_000_000.0)],
        kind="answer",
        filing_text=FILING,
    )
    assert not score.passed
    assert any(g.startswith("ADJACENCY") for g in score.gate_failures)
    assert score.fact_adjacency == 0.5


@pytest.mark.unit
def test_score_answer_missing_numeric_fails_numeric_gate():
    qa = CopilotQACase(
        question="What was revenue?",
        disclosed=True,
        expected_facts=[GroundTruthFact("revenue", 391_000_000_000.0, "USD")],
    )
    score = score_copilot_answer(qa, answer="Revenue grew strongly year over year [1].",
                                 citations=[_text_cite(VERIFIED_EXCERPT)], kind="answer", filing_text=FILING)
    assert not score.passed
    assert any(g.startswith("NUMERIC") for g in score.gate_failures)
