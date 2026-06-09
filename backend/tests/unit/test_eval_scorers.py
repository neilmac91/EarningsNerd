"""Offline tests for the eval harness scorers (roadmap S3).

These are deterministic and need no network/AI, so they prove the harness's scoring logic is
correct independent of any model run."""
import json

import pytest

from evals.schema import GroundTruthFact
from evals.scorers import (
    parse_model_json,
    score_coverage,
    score_numeric_accuracy,
    score_summary,
    validate_schema,
)

# Apple FY2023-ish figures used as fixtures (values, not claims about a specific filing).
REVENUE = GroundTruthFact(metric="revenue", value=383_285_000_000.0, unit="USD")
NET_INCOME = GroundTruthFact(metric="net_income", value=96_995_000_000.0, unit="USD")
EPS = GroundTruthFact(metric="eps", value=6.13, unit="USD_per_share")


@pytest.mark.parametrize(
    "text",
    [
        "Revenue was $383.3 billion this year.",
        "Total revenue of 383,285 (in millions).",
        "revenue reached 383.285 billion dollars",
        "FY revenue: 383285000000",
    ],
)
def test_numeric_accuracy_matches_common_renderings(text):
    recall, matched, missing = score_numeric_accuracy(text, [REVENUE])
    assert recall == 1.0
    assert matched == ["revenue"]
    assert missing == []


def test_numeric_accuracy_partial_and_eps():
    text = "Revenue was $383.3B and diluted EPS of $6.13."
    recall, matched, missing = score_numeric_accuracy(text, [REVENUE, NET_INCOME, EPS])
    assert "revenue" in matched and "eps" in matched
    assert "net_income" in missing
    assert recall == pytest.approx(2 / 3, abs=1e-3)


def test_numeric_accuracy_no_ground_truth_is_not_penalized():
    recall, matched, missing = score_numeric_accuracy("anything", [])
    assert recall == 1.0


def test_validate_schema_accepts_canonical_shape():
    payload = {
        "executive_summary": "x",
        "financial_highlights": {"revenue": "1", "net_income": "2", "eps": "3", "key_metrics": []},
        "risk_factors": [],
        "management_discussion": "y",
        "outlook": "z",
    }
    valid, problems = validate_schema(payload)
    assert valid and problems == []


def test_validate_schema_flags_missing_keys_and_bad_types():
    valid, problems = validate_schema({"executive_summary": "x", "financial_highlights": []})
    assert not valid
    assert any("financial_highlights is not an object" in p for p in problems)
    assert any("missing key" in p for p in problems)


def test_parse_model_json_clean_vs_fenced_vs_garbage():
    payload, repaired = parse_model_json('{"a": 1}')
    assert payload == {"a": 1} and repaired is False

    payload, repaired = parse_model_json('```json\n{"a": 1}\n```')
    assert payload == {"a": 1} and repaired is True

    payload, repaired = parse_model_json("not json at all")
    assert payload is None and repaired is True


def test_coverage_ignores_placeholders():
    payload = {
        "executive_summary": "A detailed multi-sentence overview of the business and results.",
        "financial_highlights": {"revenue": "Not disclosed", "net_income": "N/A", "eps": "n/a", "key_metrics": []},
        "risk_factors": ["A substantive risk about supply chain concentration and tariffs."],
        "management_discussion": "short",  # too short → not substantive
        "outlook": "Management expects mid-single-digit revenue growth next fiscal year.",
    }
    ratio, missing = score_coverage(payload)
    assert "financial_highlights" in missing  # all placeholder values
    assert "management_discussion" in missing  # under length threshold
    assert "executive_summary" not in missing
    assert ratio == pytest.approx(3 / 5)


def test_score_summary_good_beats_bad_aggregate():
    good = json.dumps({
        "executive_summary": "Apple posted record results driven by Services growth and strong iPhone demand.",
        "financial_highlights": {"revenue": "$383.3 billion", "net_income": "$96.995 billion",
                                 "eps": "$6.13", "key_metrics": ["Services revenue up double digits"]},
        "risk_factors": ["Concentration in iPhone revenue exposes results to demand swings."],
        "management_discussion": "Management cited gross-margin expansion and disciplined opex control.",
        "outlook": "The company expects continued Services momentum and steady capital returns.",
    })
    bad = json.dumps({
        "executive_summary": "short",
        "financial_highlights": {"revenue": "Not disclosed", "net_income": "N/A", "eps": "n/a", "key_metrics": []},
        "risk_factors": [],
        "management_discussion": "n/a",
        "outlook": "pending",
    })
    gt = [REVENUE, NET_INCOME, EPS]
    good_score = score_summary(good, gt)
    bad_score = score_summary(bad, gt)

    assert good_score.schema_valid and not good_score.repaired
    assert good_score.numeric_accuracy == 1.0
    assert good_score.aggregate() > bad_score.aggregate()
    assert bad_score.numeric_accuracy == 0.0


def test_score_summary_unparseable_is_zero_floor():
    score = score_summary("totally not json", [REVENUE])
    assert score.schema_valid is False
    assert score.aggregate() == 0.0
