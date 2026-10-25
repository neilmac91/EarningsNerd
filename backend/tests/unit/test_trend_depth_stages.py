"""The depth harness's stages (evals/trend_depth/{generate,judge,causes,semantics,report}.py) over run records.

Pins what keeps a paid result from being lost or misread: a record still owed a repair is neither audited nor
judged; an audit or a verdict of an output that has since changed is redone, and the report leaves it out;
a failed audit or judge call keeps its cost; and generate retries only a failed repair, keeping the calls of
a generation it replaces. The stages are imported over a stub bootstrap whose records live in ``tmp_path``,
so the real bootstrap (which rewrites the process's database and AI settings) never loads, and every model
call is faked.
"""
from __future__ import annotations

import asyncio
import hashlib
import importlib
import json
import sys
import types
from pathlib import Path
from typing import Any

import pytest

from evals.trend_depth.providers import CallResult
from evals.trend_depth.records import output_sha256

STAGES = ("generate", "judge", "causes", "semantics", "report")
LABEL, TICKER = "test", "T"


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    stub = types.ModuleType("evals.trend_depth.bootstrap")
    stub.RECORDS = tmp_path
    stub.BACKEND = Path(__file__).resolve().parents[2]
    stub.PRODUCTION_MODEL = "stub"
    monkeypatch.setitem(sys.modules, "evals.trend_depth.bootstrap", stub)
    for name in (*STAGES, "gold"):
        monkeypatch.delitem(sys.modules, f"evals.trend_depth.{name}", raising=False)
    stages = types.SimpleNamespace(**{name: importlib.import_module(f"evals.trend_depth.{name}") for name in STAGES})

    async def no_call(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("this test sends no model call")

    for module in (stages.judge, stages.causes, stages.generate):
        monkeypatch.setattr(module, "call", no_call)
    yield stages
    for name in [n for n in sys.modules if n.split(".")[-1] in (*STAGES, "gold") and n.startswith("evals.trend_depth.")]:
        del sys.modules[name]  # the next test imports them afresh, over its own records


def _write(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record))


def _generation(harness: Any, system: str, **fields: Any) -> dict[str, Any]:
    record = {"ticker": TICKER, "arm": system, "generation_ok": True, "output": {"sections": [{"text": system}]}, **fields}
    _write(harness.generate.RUNS / LABEL / system / f"{TICKER}.json", record)
    return record


def _result(text: str, cost: float) -> CallResult:
    return CallResult(text, 1000, 0, 100, 0, 1.0, cost, "openai_compat", "m", {"stop_reason": "end_turn"})


def _auditable(harness: Any, monkeypatch: pytest.MonkeyPatch) -> list:
    """Stub the evidence an audit reads, so an audit reaches its model call; return the calls attempted."""
    item = {"sentence": "Revenue grew because demand rose.", "passages": [{"id": "P1", "filing": "10-K", "text": "Demand rose."}]}
    check = types.SimpleNamespace(CITATION_RE=harness.causes.factcheck.CITATION_RE, check=lambda sentences, pack: {
        "detail": [{"text": "Revenue was 5.", "claims": [{"status": "verified", "ids": ["V1"], "claim": "5"}]}]})
    for module in (harness.causes, harness.semantics):
        monkeypatch.setattr(module, "load_pack", lambda ticker: {"split": "dev", "values": {}})
        monkeypatch.setattr(module, "sentences_of", lambda output: [])
    monkeypatch.setattr(harness.causes, "cause_items", lambda sentences, pack: [item])
    monkeypatch.setattr(harness.semantics, "factcheck", check)
    monkeypatch.setattr(harness.semantics, "_describe", lambda matched, ids, pack: "revenue, 2025")
    attempted: list = []

    async def auditor(arm: Any, system: str, user: str, **kwargs: Any) -> CallResult:
        attempted.append(kwargs.get("tag"))
        return _result('{"claims": [{"n": 1, "label": "supported"}], "items": [{"n": 1, "label": "consistent"}]}', 0.1)

    monkeypatch.setattr(harness.causes, "call", auditor)
    return attempted


def test_a_record_awaiting_its_repair_is_neither_audited_judged_nor_counted(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    attempted = _auditable(harness, monkeypatch)
    pending = _generation(harness, "deepseek-flash", repair_error="APIConnectionError: reset", gate={"passed": False})
    _generation(harness, "claude-sonnet-5-5")
    runs = harness.generate.RUNS / LABEL
    verdict = asyncio.run(harness.judge.judge_pair(LABEL, TICKER, "deepseek-flash", "claude-sonnet-5-5", "gemma-4-31b",
                                                   asyncio.Semaphore(1)))
    assert verdict is None and not (runs / "judge").exists()
    asyncio.run(harness.causes.run(LABEL, ["deepseek-flash"], [TICKER], 1))
    asyncio.run(harness.semantics.run(LABEL, ["deepseek-flash"], [TICKER], 1))
    assert attempted == [] and not (runs / "causes").exists() and not (runs / "semantics").exists()
    asyncio.run(harness.causes.run(LABEL, ["claude-sonnet-5-5"], [TICKER], 1))  # the stubs reach the call once settled
    asyncio.run(harness.semantics.run(LABEL, ["claude-sonnet-5-5"], [TICKER], 1))
    assert len(attempted) == 2 and (runs / "causes" / "claude-sonnet-5-5" / f"{TICKER}.json").exists()
    assert (runs / "semantics" / "claude-sonnet-5-5" / f"{TICKER}.json").exists()
    stats = harness.report.arm_stats([pending])
    assert stats["generated"] == 0 and stats["pending_repairs"] == 1 and "final_gate" not in stats


def _usable(cost: float) -> dict[str, Any]:
    from evals.trend_depth.judge import CRITERIA

    return {"verdict": {"overall": "A", "criteria": {c: "A" for c in CRITERIA}}, "cost_usd": cost}


def _judge(harness: Any, monkeypatch: pytest.MonkeyPatch, cached: dict[str, Any]) -> tuple[dict[str, Any], list]:
    rx, ry = _generation(harness, "deepseek-flash"), _generation(harness, "claude-sonnet-5-5")
    path = harness.generate.RUNS / LABEL / "judge" / "gemma-4-31b" / f"{TICKER}__deepseek-flash__claude-sonnet-5-5.json"
    _write(path, {"x_sha256": output_sha256(rx), "y_sha256": output_sha256(ry), **cached})
    bought: list = []

    async def one_order(judge: str, pack: Any, text_a: str, text_b: str, tag: str = "") -> dict[str, Any]:
        bought.append(text_a)
        return _usable(0.1)

    monkeypatch.setattr(harness.judge, "_one_order", one_order)
    monkeypatch.setattr(harness.judge, "load_pack", lambda ticker: {"split": "dev"})
    monkeypatch.setattr(harness.judge, "reader_text", lambda record, pack: record["arm"])
    record = asyncio.run(harness.judge.judge_pair(LABEL, TICKER, "deepseek-flash", "claude-sonnet-5-5", "gemma-4-31b",
                                                  asyncio.Semaphore(1)))
    return record, bought


def test_a_judge_retry_reuses_a_paid_order_on_the_same_drafts(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    record, bought = _judge(harness, monkeypatch, {"error": "NoVerdict", "orders": [{**_usable(0.5), "position": 1}]})
    assert bought == ["claude-sonnet-5-5"]  # only order 2, with the drafts swapped
    assert "result" in record and record["cost_usd"] == pytest.approx(0.6)


def test_a_verdict_on_a_changed_draft_is_redone_and_its_cost_kept(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    record, bought = _judge(harness, monkeypatch, {"x_sha256": "an earlier draft", "error": "NoVerdict",
                                                   "orders": [{**_usable(0.5), "position": 1}]})
    assert bought == ["deepseek-flash", "claude-sonnet-5-5"]  # the paid order read another draft: both bought
    assert len(record["superseded"]) == 1 and record["cost_usd"] == pytest.approx(0.7)
    assert record["x_sha256"] == output_sha256(json.loads((harness.generate.RUNS / LABEL / "deepseek-flash" / f"{TICKER}.json").read_text()))


def test_a_failed_audit_keeps_its_cost_and_a_stale_one_is_redone(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    causes = harness.causes
    item = {"sentence": "Revenue grew because demand rose.", "passages": [{"id": "P1", "filing": "10-K", "text": "Demand rose."}]}
    monkeypatch.setattr(causes, "cause_items", lambda sentences, pack: [item])
    monkeypatch.setattr(causes, "load_pack", lambda ticker: {"split": "dev"})
    monkeypatch.setattr(causes, "sentences_of", lambda output: [])
    replies = [_result('{"claims": []}', 0.2), _result('{"claims": [{"n": 1, "label": "supported", "reason": "r"}]}', 0.3),
               _result('{"claims": [{"n": 1, "label": "partial", "reason": "r"}]}', 0.3)]

    async def auditor(*args: Any, **kwargs: Any) -> CallResult:
        return replies.pop(0)

    monkeypatch.setattr(causes, "call", auditor)
    _generation(harness, "deepseek-flash")
    out = harness.generate.RUNS / LABEL / "causes" / "deepseek-flash" / f"{TICKER}.json"
    asyncio.run(causes.run(LABEL, ["deepseek-flash"], [TICKER], 1))
    failed = json.loads(out.read_text())
    assert "error" in failed and failed["cost_usd"] == 0.2 and "items" not in failed  # labelled nothing: not a result
    asyncio.run(causes.run(LABEL, ["deepseek-flash"], [TICKER], 1))
    audit = json.loads(out.read_text())
    assert audit["items"][0]["label"] == "supported" and audit["prior_cost_usd"] == pytest.approx(0.2)
    asyncio.run(causes.run(LABEL, ["deepseek-flash"], [TICKER], 1))
    assert replies, "a finished audit of an unchanged output is never bought again"
    _generation(harness, "deepseek-flash", output={"sections": [{"text": "repaired"}]})
    asyncio.run(causes.run(LABEL, ["deepseek-flash"], [TICKER], 1))
    redone = json.loads(out.read_text())
    assert redone["items"][0]["label"] == "partial" and redone["prior_cost_usd"] == pytest.approx(0.5) and not replies


def test_reuse_copies_only_a_finished_audit_of_the_same_output(harness: Any) -> None:
    record = _generation(harness, "deepseek-flash")
    runs = harness.generate.RUNS / LABEL
    default = runs / "causes" / "deepseek-flash" / f"{TICKER}.json"  # deepseek-flash's default auditor is Opus
    same = runs / "causes-by-claude-opus-5-5" / "deepseek-flash" / f"{TICKER}.json"
    _write(default, {"auditor": "claude-opus-5-5", "output_sha256": output_sha256(record), "error": "NoLabels", "cost_usd": 0.2})
    harness.causes.reuse_audit(LABEL, "causes", "deepseek-flash", TICKER, "claude-opus-5-5", output_sha256(record))
    assert not same.exists()
    _write(default, {"auditor": "claude-opus-5-5", "output_sha256": "an earlier output", "items": [], "cost_usd": 0.3})
    harness.causes.reuse_audit(LABEL, "causes", "deepseek-flash", TICKER, "claude-opus-5-5", output_sha256(record))
    assert not same.exists()
    _write(default, {"auditor": "claude-opus-5-5", "output_sha256": output_sha256(record), "items": [], "cost_usd": 0.3})
    harness.causes.reuse_audit(LABEL, "causes", "deepseek-flash", TICKER, "claude-opus-5-5", output_sha256(record))
    assert json.loads(same.read_text())["cost_usd"] == 0.3


def _stub_generate(harness: Any, monkeypatch: pytest.MonkeyPatch, snapshot: str) -> list:
    generate, events = harness.generate, []
    monkeypatch.setattr(generate, "load_pack", lambda ticker: {"snapshot_id": snapshot})
    monkeypatch.setattr(generate, "system_prompt", lambda: "the prompt")
    monkeypatch.setattr(generate, "user_message", lambda pack: "the pack")

    async def repair(arm: Any, system: str, user: str, record: dict[str, Any], pack: Any, tag: str) -> None:
        events.append("repair")
        record.pop("repair_error")

    async def regenerate(arm_name: str, ticker: str, tag: str = "") -> dict[str, Any]:
        events.append("generate")
        return {"ticker": ticker, "arm": arm_name, "generation_ok": True, "attempts": [{"attempt": 0, "cost_usd": 0.1}], "cost_usd": 0.1}

    monkeypatch.setattr(generate, "repair_or_mark", repair)
    monkeypatch.setattr(generate, "generate_proposed", regenerate)
    return events


def test_generate_retries_only_a_failed_repair_on_the_same_prompt_and_pack(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    events = _stub_generate(harness, monkeypatch, "s1")
    _generation(harness, "deepseek-flash", repair_error="APIConnectionError", snapshot_id="s1",
                prompt_sha256=hashlib.sha256(b"the prompt").hexdigest(), attempts=[{"attempt": 0, "cost_usd": 0.2}])
    asyncio.run(harness.generate.run(LABEL, ["deepseek-flash"], [TICKER], 1))
    record = json.loads((harness.generate.RUNS / LABEL / "deepseek-flash" / f"{TICKER}.json").read_text())
    assert events == ["repair"] and "repair_error" not in record and record["attempts"] == [{"attempt": 0, "cost_usd": 0.2}]


@pytest.mark.parametrize("failed", [{"repair_error": "APIConnectionError", "snapshot_id": "s0"},  # the pack was rebuilt
                                    {"error": "RateLimitError", "generation_ok": False}])
def test_a_regenerated_record_keeps_the_calls_of_the_one_it_replaced(harness: Any, monkeypatch: pytest.MonkeyPatch,
                                                                     failed: dict[str, Any]) -> None:
    events = _stub_generate(harness, monkeypatch, "s1")
    _generation(harness, "deepseek-flash", prompt_sha256=hashlib.sha256(b"the prompt").hexdigest(),
                attempts=[{"attempt": 0, "cost_usd": 0.2}], **failed)
    asyncio.run(harness.generate.run(LABEL, ["deepseek-flash"], [TICKER], 1))
    record = json.loads((harness.generate.RUNS / LABEL / "deepseek-flash" / f"{TICKER}.json").read_text())
    assert events == ["generate"]
    assert record["prior_attempts"] == [{"attempt": 0, "cost_usd": 0.2}] and record["prior_cost_usd"] == 0.2


def test_the_report_leaves_out_refused_and_stale_audits_and_verdicts(harness: Any) -> None:
    record, other = _generation(harness, "deepseek-flash"), _generation(harness, "claude-sonnet-5-5")
    runs = harness.generate.RUNS / LABEL
    _write(runs / "causes" / "deepseek-flash" / f"{TICKER}.json",
           {"auditor": "claude-opus-5-5", "output_sha256": "an earlier output", "items": [{"label": "supported"}]})
    _write(runs / "causes" / "claude-sonnet-5-5" / f"{TICKER}.json",
           {"auditor": "deepseek-v4-pro", "output_sha256": output_sha256(other), "refused": True, "claims": 3})  # ADR-0008
    support = harness.report.cause_support(LABEL, ["deepseek-flash", "claude-sonnet-5-5"], [TICKER])
    assert support["deepseek-flash"] == {"counts": {}, "auditors": {}, "left_out": {"pending": 1}}
    assert support["claude-sonnet-5-5"]["left_out"] == {"refused": 1}
    _write(runs / "judge" / "gemma-4-31b" / f"{TICKER}__deepseek-flash__claude-sonnet-5-5.json",
           {"ticker": TICKER, "x": "deepseek-flash", "y": "claude-sonnet-5-5", "judge": "gemma-4-31b",
            "x_sha256": "an earlier draft", "y_sha256": output_sha256(other), "result": {}})
    matrix = harness.report.judge_matrix(LABEL, ["deepseek-flash", "claude-sonnet-5-5"], [TICKER])
    assert matrix["stale_verdicts"] == 1 and matrix["judged_pairs"] == 0
    assert output_sha256(record) != "an earlier output"


def test_these_tests_leave_the_real_bootstrap_unloaded() -> None:
    assert "evals.trend_depth.bootstrap" not in sys.modules
