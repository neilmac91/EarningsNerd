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
