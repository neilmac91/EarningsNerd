"""The fixed E7 rubric never trades a material defect for average model scores."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from evals.acceptance_ai_decision import decide, expected_identities


def _case():
    path = Path(__file__).resolve().parents[3] / "tasks/review-evidence/acceptance-2026-09-19/candidate-manifest.json"
    manifest = json.loads(path.read_text())
    rows = [{"slot_id": slot, "completeness": 5, "usefulness": 5,
             "completeness_reason": "Synthetic coverage", "usefulness_reason": "Synthetic clarity",
             "semantic": {"model": "cli:claude-fable-5-1", "contract_version": "2",
                          "status": "complete", "grounding_truncated": False, "verdict": "pass"},
             "checks": {k: "checked" for k in
                        ("numeric_claims", "causal_claims", "financial_basis", "quotations", "citations")},
             "findings": []} for slot in expected_identities(manifest)]
    return manifest, rows


def _finding(**changes):
    return {"id": "F1", "claim": "Revenue was $999B", "source_locator": "Selected filing, table 1",
            "source_context": "The source table reports $99B", "reason": "Wrong number",
            "severity": "S1", "disposition": "confirmed", "category": "claim",
            "refutations": ["Checked display units", "Checked reporting period"], **changes}


def test_fixed_rubric_joint_scores_and_filing_repeatability():
    manifest, rows = _case()
    result = decide(manifest, rows)
    assert result["status"] == "pass"
    assert result["joint_at_least_4"] == 90
    assert result["human_acceptance"] is False
    assert result["paired_comparison"] == {"better": 0, "tied": 30, "worse": 0, "mixed": 0, "missing": 0}
    # Four weak scores spread over four filings are allowed, exactly at 86/90.
    by_slot = {r["slot_id"]: r for r in rows}
    for i in range(1, 5):
        by_slot[f"H{i:02d}-candidate-1"]["completeness"] = 3
    assert decide(manifest, rows)["status"] == "pass"
    by_slot["H05-candidate-1"]["usefulness"] = 3
    assert decide(manifest, rows)["status"] == "fail"
    # Failing either dimension on two draws vetoes even when aggregate joint count is 88.
    _, rows = _case()
    by_slot = {r["slot_id"]: r for r in rows}
    by_slot["H01-candidate-1"]["completeness"] = 3
    by_slot["H01-candidate-2"]["usefulness"] = 3
    result = decide(manifest, rows)
    assert result["joint_at_least_4"] == 88
    assert result["status"] == "fail"


@pytest.mark.parametrize("change,expected", [
    ({}, "fail"),
    ({"severity": "S0"}, "fail"),
    ({"severity": "S3", "category": "fabricated_quote"}, "fail"),
    ({"severity": "S3", "category": "misleading_citation"}, "fail"),
    ({"disposition": "unresolved"}, "incomplete"),
    ({"disposition": "rejected"}, "pass"),
    ({"severity": "S2"}, "incomplete"),
    ({"source_context": None}, "incomplete"),
])
def test_supported_source_findings_cannot_be_averaged_away(change, expected):
    manifest, rows = _case()
    rows[0]["findings"] = [_finding(**change)]
    result = decide(manifest, rows)
    assert result["status"] == expected
    if expected in {"fail", "pass"}:
        assert len(result["defects"]) == 1  # Rejected allegations are retained too.


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "bool_score", "judge_error", "judge_truncated",
                                      "judge_changed", "missing_checks", "negative_without_reason"])
def test_measurement_gaps_are_incomplete_never_excluded(mutation):
    manifest, rows = _case()
    if mutation == "missing":
        rows.pop()
    elif mutation == "duplicate":
        rows.append(deepcopy(rows[0]))
    elif mutation == "bool_score":
        rows[0]["completeness"] = True
    elif mutation == "missing_checks":
        rows[0]["checks"].pop("citations")
    elif mutation == "negative_without_reason":
        rows[0]["semantic"]["verdict"] = "fail"
    else:
        key, value = {"judge_error": ("status", "error"), "judge_truncated": ("grounding_truncated", True),
                      "judge_changed": ("model", "another-model")}[mutation]
        rows[0]["semantic"][key] = value
    result = decide(manifest, rows)
    assert result["status"] == "incomplete"
    assert result["expected_candidate_outputs"] == 90
    assert result["expected_comparator_outputs"] == 30


def test_comparator_defects_and_incomplete_candidate_evidence_stay_distinct():
    manifest, rows = _case()
    control = next(row for row in rows if "-comparator-" in row["slot_id"])
    control["findings"] = [_finding()]
    result = decide(manifest, rows)
    assert result["status"] == "pass"
    assert len(result["defects"]) == 1
    rows[0]["findings"] = [_finding(id="F2")]
    result = decide(manifest, rows[:-1], measurement_issues=["source adapter unavailable"])
    assert result["status"] == "fail"
    assert result["incomplete_reasons"]
