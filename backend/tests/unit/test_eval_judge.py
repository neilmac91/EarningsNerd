"""Offline tests for the LLM-judge helpers (Artifact 2).

`build_judge_messages` and `parse_judge_response` are pure — no network — so the judge's
construction and verdict logic are provable without a model call. The backend-dispatch tests
(`judge_backend`, `judge_summary`, and the `_judge_via_*` credential/subprocess paths) are also
offline: they assert routing and graceful-degradation without any model call."""
import asyncio
import json

import pytest

import evals.judge as judge_mod
from evals.runner import _XBRL_TEXT_CHAR_CAP, _xbrl_to_text
from evals.judge import (
    JudgeVerdict,
    build_judge_messages,
    judge_backend,
    judge_summary,
    parse_judge_response,
)


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


def test_explicit_fail_with_high_dimensions_is_not_a_pass():
    # The judge says FAIL but reports no gates and high scores — must NOT be counted as a pass.
    raw = json.dumps({
        "gate_failures": [],
        "dimensions": {"faithfulness": 5, "insight": 5, "clarity": 5, "specificity": 5},
        "verdict": "FAIL",
    })
    v = parse_judge_response(raw)
    assert v.verdict == "FAIL" and v.passed is False


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


# --- judge XBRL-view fidelity (the _xbrl_to_text cap) --------------------------------------

def test_xbrl_to_text_does_not_truncate_full_metric_set():
    """The judge must see EVERY standardized metric the generator grounds on. A metric-rich filer
    (AAPL FY25 = ~12.2k chars of metrics JSON) previously overran the old 8,000-char cap, dropping
    late keys (free_cash_flow, ROE/ROA, working capital, current ratio) out of the judge's view and
    triggering false G3 'hallucination' flags. Assert the late keys survive."""
    metrics = {"reporting_currency": "USD"}

    def _period(v):
        # Mirror the real extracted shape (value/period/unit/raw_tag) so the JSON size is realistic.
        return {"value": v, "period": "2025-09-27", "unit": "USD",
                "raw_tag": "us-gaap:SomeStandardizedConceptName"}

    # 40 metrics each with current+prior comfortably exceeds the old 8k cap (like AAPL FY25's ~12k).
    for i in range(40):
        metrics[f"metric_{i:02d}"] = {"current": _period(123456789012.0 + i),
                                      "prior": _period(111111111111.0 + i)}
    # The keys that were being truncated out on the real AAPL run — appended LAST so they sit past 8k:
    metrics["free_cash_flow"] = {"current": _period(98_767_000_000.0)}
    metrics["return_on_assets"] = {"current": {"value": 31.2, "period": "2025-09-27", "unit": "pure"}}

    text = _xbrl_to_text(metrics)
    assert len(json.dumps(metrics, default=str)) > 8000  # would have been cut under the old cap
    assert "free_cash_flow" in text and "return_on_assets" in text  # now visible to the judge
    assert len(text) <= _XBRL_TEXT_CHAR_CAP  # still bounded against a corrupted/oversized dict


# --- backend dispatch (offline; no model call) --------------------------------------------

@pytest.mark.parametrize(
    "model_id, expected",
    [
        ("claude-opus-4-8", "anthropic"),
        ("claude-sonnet-5", "anthropic"),
        ("", "anthropic"),
        ("cli:sonnet", "cli"),
        ("cli:opus", "cli"),
        ("subscription:sonnet", "cli"),
        ("glm-5.2", "openai"),
        ("GLM-5.2", "openai"),
        ("openai:glm-5.2", "openai"),
        ("openai:some-model", "openai"),
    ],
)
def test_judge_backend_routing(model_id, expected):
    assert judge_backend(model_id) == expected


@pytest.mark.asyncio
async def test_judge_summary_dispatches_by_model_id(monkeypatch):
    """judge_summary routes to exactly the backend judge_backend selects."""
    calls = []

    def make_backend(name):
        async def _impl(system, user, model_id, max_tokens):
            calls.append(name)
            return JudgeVerdict(verdict="PASS", dimensions={"faithfulness": 4})
        return _impl

    monkeypatch.setattr(judge_mod, "_judge_via_cli", make_backend("cli"))
    monkeypatch.setattr(judge_mod, "_judge_via_openai", make_backend("openai"))
    monkeypatch.setattr(judge_mod, "_judge_via_anthropic", make_backend("anthropic"))

    for model_id, expected in [("cli:sonnet", "cli"), ("glm-5.2", "openai"), ("claude-opus-4-8", "anthropic")]:
        await judge_summary({}, "Acme", "10-K", "excerpt", "{}", model_id=model_id)
    assert calls == ["cli", "openai", "anthropic"]


@pytest.mark.asyncio
async def test_anthropic_backend_missing_key_is_graceful(monkeypatch):
    # Degrades to a FAIL-with-error, never a crash. Which error depends on the environment: the
    # `anthropic` SDK is optional (absent in CI) → "SDK not installed"; present-but-no-key →
    # "missing ANTHROPIC_API_KEY". Either is the graceful path this asserts.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    v = await judge_mod._judge_via_anthropic("sys", "user", "claude-opus-4-8", 4096)
    assert v.verdict == "FAIL"
    assert ("ANTHROPIC_API_KEY" in (v.error or "")) or ("anthropic SDK not installed" in (v.error or ""))


@pytest.mark.asyncio
async def test_openai_backend_missing_creds_is_graceful(monkeypatch):
    for var in ("JUDGE_OPENAI_BASE_URL", "JUDGE_OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    v = await judge_mod._judge_via_openai("sys", "user", "glm-5.2", 4096)
    assert v.verdict == "FAIL" and "OPENAI" in (v.error or "")


@pytest.mark.asyncio
async def test_judge_with_retry_retries_then_parses(monkeypatch):
    attempts = {"n": 0}
    good = json.dumps({
        "gate_failures": [], "verdict": "PASS",
        "dimensions": {"faithfulness": 4, "insight": 4, "clarity": 4, "specificity": 4},
    })

    async def flaky():
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("transient 529")
        return good

    v = await judge_mod._judge_with_retry(flaky)
    assert attempts["n"] == 2 and v.verdict == "PASS" and v.error is None


@pytest.mark.asyncio
async def test_judge_with_retry_reports_error_after_two_failures():
    async def always_fail():
        raise RuntimeError("boom")

    v = await judge_mod._judge_with_retry(always_fail)
    assert v.verdict == "FAIL" and "boom" in (v.error or "")


class _FakeProc:
    """Minimal stand-in for an asyncio subprocess for the CLI-backend test."""

    def __init__(self, stdout: bytes, returncode: int = 0):
        self._stdout = stdout
        self.returncode = returncode

    async def communicate(self, _stdin=None):
        return self._stdout, b""

    def kill(self):  # pragma: no cover - only the timeout path calls this
        pass

    async def wait(self):  # pragma: no cover
        return self.returncode


@pytest.mark.asyncio
async def test_cli_backend_unsets_api_key_and_parses_result(monkeypatch):
    """The subscription CLI path must strip ANTHROPIC_API_KEY from the child env (so it uses the
    subscription/OAuth, not API credits) and parse the judge JSON out of the `result` wrapper."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-not-leak")
    judge_json = json.dumps({
        "gate_failures": [], "verdict": "PASS",
        "dimensions": {"faithfulness": 5, "insight": 4, "clarity": 5, "specificity": 4},
    })
    cli_wrapper = json.dumps({"type": "result", "subtype": "success", "result": judge_json}).encode()
    captured = {}

    async def fake_exec(*args, **kwargs):
        captured["args"] = args
        captured["env"] = kwargs.get("env", {})
        return _FakeProc(cli_wrapper)

    monkeypatch.setattr(judge_mod.asyncio, "create_subprocess_exec", fake_exec)
    v = await judge_mod._judge_via_cli("sys", "user", "cli:sonnet", 4096)

    assert v.verdict == "PASS" and v.mean_dimension == 4.5 and v.error is None
    assert "ANTHROPIC_API_KEY" not in captured["env"]  # forced onto subscription auth
    assert "--model" in captured["args"] and "sonnet" in captured["args"]
    assert "--output-format" in captured["args"] and "json" in captured["args"]


@pytest.mark.asyncio
async def test_cli_backend_error_result_is_reported(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    err_wrapper = json.dumps({"type": "result", "subtype": "error_during_execution",
                              "is_error": True, "result": "quota exhausted"}).encode()

    async def fake_exec(*args, **kwargs):
        return _FakeProc(err_wrapper)

    monkeypatch.setattr(judge_mod.asyncio, "create_subprocess_exec", fake_exec)
    v = await judge_mod._judge_via_cli("sys", "user", "cli:opus", 4096)
    assert v.verdict == "FAIL" and v.error is not None


@pytest.mark.asyncio
async def test_cli_backend_reaps_subprocess_on_cancellation(monkeypatch):
    """On task cancellation (CancelledError is a BaseException, not Exception), the child must be
    killed and reaped — never left as a zombie — and the cancellation must still propagate."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    reaped = {"kill": False, "wait": False}

    class _CancelProc:
        returncode = None

        async def communicate(self, _stdin=None):
            raise asyncio.CancelledError()

        def kill(self):
            reaped["kill"] = True

        async def wait(self):
            reaped["wait"] = True
            return 0

    async def fake_exec(*args, **kwargs):
        return _CancelProc()

    monkeypatch.setattr(judge_mod.asyncio, "create_subprocess_exec", fake_exec)
    with pytest.raises(asyncio.CancelledError):
        await judge_mod._judge_via_cli("sys", "user", "cli:sonnet", 4096)
    assert reaped["kill"] and reaped["wait"]  # killed + reaped before re-raising
