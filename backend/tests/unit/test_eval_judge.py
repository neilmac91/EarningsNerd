"""Offline tests for the LLM-judge helpers (Artifact 2).

`build_judge_messages` and `parse_judge_response` are pure — no network — so the judge's
construction and verdict logic are provable without a model call."""
import json

from evals.judge import build_judge_messages, parse_judge_response


def test_parse_clean_pass():
    raw = json.dumps({
        "gate_failures": [],
        "dimensions": {"faithfulness": 5, "insight": 4, "clarity": 5, "specificity": 4},
        "verdict": "PASS", "notes": "well grounded",
    })
    v = parse_judge_response(raw)
    assert v.verdict == "PASS" and v.passed is True
    assert v.mean_dimension == 4.5 and v.error is None


def test_parse_fenced_json_is_handled():
    raw = "```json\n" + json.dumps({
        "gate_failures": [], "dimensions": {"faithfulness": 4, "insight": 4, "clarity": 4, "specificity": 4},
        "verdict": "PASS",
    }) + "\n```"
    v = parse_judge_response(raw)
    assert v.verdict == "PASS" and v.mean_dimension == 4.0


def test_gate_failure_forces_fail_even_if_model_says_pass():
    raw = json.dumps({
        "gate_failures": ["G3 hallucinated_facts: claims an acquisition not in the filing"],
        "dimensions": {"faithfulness": 5, "insight": 5, "clarity": 5, "specificity": 5},
        "verdict": "PASS",  # model contradicts itself — gates win
    })
    v = parse_judge_response(raw)
    assert v.verdict == "FAIL" and v.passed is False
    assert v.gate_failures


def test_low_dimensions_fail_when_verdict_absent():
    raw = json.dumps({
        "gate_failures": [],
        "dimensions": {"faithfulness": 2, "insight": 2, "clarity": 3, "specificity": 2},
    })
    v = parse_judge_response(raw)
    assert v.verdict == "FAIL" and v.passed is False  # mean 2.25 < threshold


def test_parse_garbage_is_fail_with_error():
    v = parse_judge_response("the summary looks fine to me")
    assert v.verdict == "FAIL" and v.error is not None
    assert v.gate_failures  # records an unparseable failure


def test_build_judge_messages_includes_source_and_summary():
    summary = {"executive_summary": "Revenue grew.", "financial_highlights": {"revenue": "$10B"}}
    system, user = build_judge_messages(
        summary, "Acme Corp", "10-K", excerpt="Net sales were $10 billion.", xbrl_text='{"revenue": 10e9}',
    )
    assert "adversarial" in system.lower()
    assert "Acme Corp" in user and "10-K" in user
    assert "Net sales were $10 billion" in user  # source excerpt present → judge can verify
    assert "Revenue grew" in user  # summary under test present
    assert "G2" in user and "G3" in user  # gate instructions present
