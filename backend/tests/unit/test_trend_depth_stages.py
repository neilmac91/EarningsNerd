"""The depth harness's stages (evals/trend_depth/{generate,judge,causes,semantics,report}.py) over run records.

Pins what keeps a paid result from being lost or misread: a record still owed a repair is neither audited nor
judged; an audit or a verdict of an output that has since changed is redone, and the report leaves it out;
a failed audit or judge call keeps its cost; and generate retries only a failed repair, keeping the calls of
a generation it replaces. Also that every stage reads the prompt and the evidence pack of the system it reads.
The stages are imported over a stub bootstrap whose records, pack directories included, live in ``tmp_path``,
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

from evals.trend_depth.providers import ARMS, CANDIDATE_PROMPT, FROZEN_PROMPT, CallResult, packs_dir
from evals.trend_depth.records import output_sha256, pack_sha256

STAGES = ("generate", "judge", "causes", "semantics", "report")
LABEL, TICKER = "test", "T"
REPO = Path(__file__).resolve().parents[3]


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
    monkeypatch.setattr(stages.generate, "PROMPT_DRAFT", "")  # a TREND_DEPTH_PROMPT in the shell changes nothing here
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


def _packs(harness: Any, **fields: Any) -> dict[str, dict[str, Any]]:
    """Write the company's pack into every pack directory an arm reads, each pack naming its directory; return them
    by directory. They share a snapshot_id, as packs built from one dataset do."""
    folders = {packs_dir(name, harness.generate.RUNS.parent) for name in [*ARMS, "current"]}
    packs = {}
    for folder in folders:
        packs[folder.name] = {"split": "dev", "profile": "p", "window": "w", "snapshot_id": "s1", "dir": folder.name, **fields}
        _write(folder / f"{TICKER}.json", packs[folder.name])
    return packs


def _auditable(harness: Any, monkeypatch: pytest.MonkeyPatch) -> list:
    """Stub the evidence an audit reads, so an audit reaches its model call; return the calls attempted."""
    item = {"sentence": "Revenue grew because demand rose.", "passages": [{"id": "P1", "filing": "10-K", "text": "Demand rose."}]}
    check = types.SimpleNamespace(CITATION_RE=harness.causes.factcheck.CITATION_RE, check=lambda sentences, pack: {
        "detail": [{"text": "Revenue was 5.", "claims": [{"status": "verified", "ids": ["V1"], "claim": "5"}]}]},
        parse_claims=lambda text: ["5"])  # one parsed figure per claim, as the gate records them
    for module in (harness.causes, harness.semantics):
        monkeypatch.setattr(module, "load_pack", lambda ticker, system="": {"split": "dev", "values": {}})
        monkeypatch.setattr(module, "sentences_of", lambda output: [])
    monkeypatch.setattr(harness.causes, "cause_items", lambda sentences, pack: [item])
    monkeypatch.setattr(harness.semantics, "factcheck", check)
    monkeypatch.setattr(harness.semantics, "_describe", lambda matched, ids, pack, figure: "revenue, 2025")
    attempted: list = []

    async def auditor(arm: Any, system: str, user: str, **kwargs: Any) -> CallResult:
        attempted.append(kwargs.get("tag"))
        return _result('{"claims": [{"n": 1, "label": "supported"}], "items": [{"n": 1, "label": "consistent"}]}', 0.1)

    monkeypatch.setattr(harness.causes, "call", auditor)
    return attempted


def test_a_record_awaiting_its_repair_is_neither_audited_nor_judged_and_is_counted_apart(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
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
    monkeypatch.setattr(harness.judge, "load_pack", lambda ticker, system="": {"split": "dev"})
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
    monkeypatch.setattr(causes, "load_pack", lambda ticker, system="": {"split": "dev"})
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
    _packs(harness, snapshot_id=snapshot)
    monkeypatch.setattr(generate, "system_prompt", lambda arm_name: "the prompt")
    monkeypatch.setattr(generate, "user_message", lambda pack: "the pack")

    async def repair(arm: Any, system: str, user: str, record: dict[str, Any], pack: Any, tag: str, checkpoint: Any = None) -> None:
        events.append("repair")
        record.pop("repair_error")

    async def regenerate(arm_name: str, ticker: str, tag: str = "", checkpoint: Any = None) -> dict[str, Any]:
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


@pytest.mark.parametrize("failed", [{"error": "RateLimitError", "generation_ok": False}])  # a rebuilt pack: label_conflicts
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


def test_an_interrupted_judge_keeps_the_order_it_paid_for(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    _generation(harness, "deepseek-flash"), _generation(harness, "claude-sonnet-5-5")
    monkeypatch.setattr(harness.judge, "load_pack", lambda ticker, system="": {"split": "dev"})
    monkeypatch.setattr(harness.judge, "reader_text", lambda record, pack: record["arm"])
    bought: list = []
    interrupt = [True]

    async def one_order(judge: str, pack: Any, text_a: str, text_b: str, tag: str = "") -> dict[str, Any]:
        bought.append(text_a)
        if len(bought) == 2 and interrupt.pop():
            raise KeyboardInterrupt  # Ctrl-C while order 2 streams, once
        return _usable(0.1)

    monkeypatch.setattr(harness.judge, "_one_order", one_order)
    pair = (LABEL, TICKER, "deepseek-flash", "claude-sonnet-5-5", "gemma-4-31b")
    with pytest.raises(KeyboardInterrupt):
        asyncio.run(harness.judge.judge_pair(*pair, asyncio.Semaphore(1)))
    path = harness.generate.RUNS / LABEL / "judge" / "gemma-4-31b" / f"{TICKER}__deepseek-flash__claude-sonnet-5-5.json"
    kept = json.loads(path.read_text())
    assert kept["error"].startswith("interrupted") and [o["position"] for o in kept["orders"]] == [1]
    bought.clear()
    record = asyncio.run(harness.judge.judge_pair(*pair, asyncio.Semaphore(1)))
    assert bought == ["claude-sonnet-5-5"] and "result" in record  # only order 2 was bought again


def test_a_judge_reply_missing_a_criterion_is_not_a_verdict(harness: Any) -> None:
    from evals.trend_depth.judge import CRITERIA

    whole = {"verdict": {"overall": "A", "criteria": {c: "B" for c in CRITERIA}}}
    assert harness.judge.usable(whole)
    assert harness.judge.usable({"verdict": {"overall": "tie", "criteria": {c: "Tie" for c in CRITERIA}}})
    assert not harness.judge.usable({"verdict": {"overall": "A", "criteria": {}}})
    assert not harness.judge.usable({"verdict": {"overall": "A", "criteria": {**whole["verdict"]["criteria"], CRITERIA[0]: "Draft A"}}})
    assert not harness.judge.usable({"verdict": {"overall": "", "criteria": whole["verdict"]["criteria"]}})


def test_an_audit_reply_with_no_usable_label_is_a_failed_audit(harness: Any) -> None:
    result = _result("{}", 0.2)
    for entries in ([{"n": 1, "verdict": "supported"}], [{"n": 0, "label": "supported"}], [{"n": 1, "label": "  "}]):
        with pytest.raises(harness.causes.NoLabels):
            harness.causes.labels_or_raise(result, entries, 1)
    assert harness.causes.labels_or_raise(result, [{"n": "1.", "label": "partial"}], 1)[1]["label"] == "partial"
    assert harness.causes.labels_or_raise(result, [], 0) == {}  # nothing to label, nothing asked


def test_a_first_pass_is_kept_while_its_repair_is_in_flight(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    generate = harness.generate
    monkeypatch.setattr(generate, "load_pack", lambda ticker, system="": {"split": "dev", "profile": "p", "window": "w", "snapshot_id": "s1"})
    monkeypatch.setattr(generate, "system_prompt", lambda arm_name: "the prompt")
    monkeypatch.setattr(generate, "user_message", lambda pack: "the pack")
    monkeypatch.setattr(generate, "validate", lambda parsed: [])
    monkeypatch.setattr(generate, "word_count", lambda parsed: 1)
    monkeypatch.setattr(generate, "sentences_of", lambda parsed: [])
    monkeypatch.setattr(generate.factcheck, "check", lambda sentences, pack: {
        "passed": False, "claims": 1, "verified": 0, "failed_claims": 1, "failures": [{"section": "s", "failure": "f", "sentence": "x"}]})
    calls: list = []

    async def provider(arm: Any, system: str, user: str, **kwargs: Any) -> CallResult:
        calls.append(user)
        if len(calls) == 2:
            raise KeyboardInterrupt  # Ctrl-C while the repair streams
        return _result('{"sections": []}', 0.3)

    monkeypatch.setattr(generate, "call", provider)
    with pytest.raises(KeyboardInterrupt):
        asyncio.run(generate.run(LABEL, ["deepseek-flash"], [TICKER], 1))
    kept = json.loads((generate.RUNS / LABEL / "deepseek-flash" / f"{TICKER}.json").read_text())
    assert kept["repair_error"].startswith("interrupted") and kept["cost_usd"] == 0.3  # the paid first pass stands
    assert kept["prompt_sha256"] == hashlib.sha256(b"the prompt").hexdigest() and kept["snapshot_id"] == "s1"


@pytest.mark.parametrize("held, paid", [
    ({"copied_from": "causes", "cost_usd": 0.3}, 0.8),  # a copy of the v1 audit the source itself replaced
    ({"cost_usd": 0.3}, 1.1),  # an audit of v1 paid for in the target folder on its own
    ({"error": "NoLabels", "cost_usd": 0.2}, 1.0),  # a failed call of the target folder's own
])
def test_each_paid_audit_is_counted_once_across_the_two_folders(harness: Any, held: dict[str, Any], paid: float) -> None:
    from evals.trend_depth.records import own_spend

    record = _generation(harness, "deepseek-flash")
    runs = harness.generate.RUNS / LABEL
    default = runs / "causes" / "deepseek-flash" / f"{TICKER}.json"
    same = runs / "causes-by-claude-opus-5-5" / "deepseek-flash" / f"{TICKER}.json"
    # The default folder audited v1 (0.3) and then v2 (0.5), carrying v1's cost.
    _write(default, {"auditor": "claude-opus-5-5", "output_sha256": output_sha256(record), "items": [], "cost_usd": 0.5,
                     "prior_cost_usd": 0.3})
    _write(same, {"auditor": "claude-opus-5-5", "output_sha256": "the v1 output", "items": [], **held})
    harness.causes.reuse_audit(LABEL, "causes", "deepseek-flash", TICKER, "claude-opus-5-5", output_sha256(record))
    copy = json.loads(same.read_text())
    assert copy["output_sha256"] == output_sha256(record) and copy["copied_from"] == "causes"
    assert own_spend(json.loads(default.read_text())) + own_spend(copy) == pytest.approx(paid)  # every paid call, once
    copy_again = {**copy, "output_sha256": "an output that changes later"}
    _write(same, copy_again)
    assert harness.causes.earlier_audit(same, output_sha256(record))[1] == pytest.approx(own_spend(copy))


def test_the_report_counts_provider_errors_and_unjudged_pairs_apart(harness: Any) -> None:
    errored = {"ticker": TICKER, "arm": "claude-sonnet-5-5", "generation_ok": False, "error": "GenerationError: BudgetExceeded",
               "attempts": [], "cost_usd": 0.0}
    refused = {"ticker": TICKER, "arm": "claude-sonnet-5-5", "generation_ok": False, "attempts": [], "cost_usd": 0.0}
    stats = harness.report.arm_stats([errored, refused])
    assert stats["provider_errors"] == 1 and stats["generated"] == 0
    rx, ry = _generation(harness, "deepseek-flash"), _generation(harness, "claude-sonnet-5-5")
    _write(harness.generate.RUNS / LABEL / "judge" / "claude-opus-5-5" / f"{TICKER}__deepseek-flash__claude-sonnet-5-5.json",
           {"ticker": TICKER, "x": "deepseek-flash", "y": "claude-sonnet-5-5", "judge": "claude-opus-5-5",
            "x_sha256": output_sha256(rx), "y_sha256": output_sha256(ry), "error": "NoVerdict", "orders": []})
    matrix = harness.report.judge_matrix(LABEL, ["deepseek-flash", "claude-sonnet-5-5"], [TICKER])
    assert matrix["unjudged_pairs"] == 1 and matrix["incomplete_panels"] == 0


def _real_generate(harness: Any, monkeypatch: pytest.MonkeyPatch, replies: list, gates: list) -> list:
    """Run generate's own code over stubbed evidence: each call takes the next of ``replies`` (a result, or an
    exception to raise), each gate check the next of ``gates``. Returns the user messages the calls were sent."""
    generate = harness.generate
    monkeypatch.setattr(generate, "load_pack", lambda ticker, system="": {"split": "dev", "profile": "p", "window": "w", "snapshot_id": "s1"})
    monkeypatch.setattr(generate, "system_prompt", lambda arm_name: "the prompt")
    monkeypatch.setattr(generate, "user_message", lambda pack: "the pack")
    monkeypatch.setattr(generate, "validate", lambda parsed: [] if parsed else ["not JSON"])
    monkeypatch.setattr(generate, "word_count", lambda parsed: 1)
    monkeypatch.setattr(generate, "sentences_of", lambda parsed: [])
    failure = {"section": "s", "failure": "f", "sentence": "x"}
    monkeypatch.setattr(generate.factcheck, "check", lambda sentences, pack: {
        "passed": gates.pop(0), "claims": 1, "verified": 0, "failed_claims": 1, "failures": [failure]})
    sent: list = []

    async def provider(arm: Any, system: str, user: str, **kwargs: Any) -> CallResult:
        sent.append(user)
        reply = replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        return reply

    monkeypatch.setattr(generate, "call", provider)
    return sent


def _first_pass(harness: Any, **fields: Any) -> None:
    _generation(harness, "deepseek-flash", repair_error="APIConnectionError", snapshot_id="s1",
                prompt_sha256=hashlib.sha256(b"the prompt").hexdigest(), gate={"passed": False, "claims": 1, "verified": 0,
                "failed_claims": 1, "failures": [{"section": "s", "failure": "f", "sentence": "x"}]},
                attempts=[{"attempt": 0, "cost_usd": 0.2}], usage={"input_tokens": 1, "cached_input_tokens": 0,
                "output_tokens": 1, "reasoning_tokens": 0}, latency_s=1.0, cost_usd=0.2, **fields)


def _incomplete(cost: float) -> Exception:
    from evals.trend_depth.providers import IncompleteReply

    return IncompleteReply("the reply stopped at max_tokens", _result("{", cost))


@pytest.mark.parametrize("reply, settled, attempts", [
    (_result('{"sections": ["repaired"]}', 0.3), True, 2),  # the retried repair returns: settled, one repair added
    (RuntimeError("overloaded"), False, 1),  # it fails again: the first pass stands, still owed its repair
    (_incomplete(0.4), False, 2),  # it stops at its cap: paid for, so its attempt is kept
])
def test_a_retried_repair_runs_the_real_repair(harness: Any, monkeypatch: pytest.MonkeyPatch, reply: Any, settled: bool,
                                               attempts: int) -> None:
    sent = _real_generate(harness, monkeypatch, [reply], [True])
    _first_pass(harness)
    asyncio.run(harness.generate.run(LABEL, ["deepseek-flash"], [TICKER], 1))
    record = json.loads((harness.generate.RUNS / LABEL / "deepseek-flash" / f"{TICKER}.json").read_text())
    assert len(sent) == 1 and "Your analysis was checked" in sent[0]  # the repair message, never a new first pass
    assert ("repair_error" not in record) is settled and len(record["attempts"]) == attempts
    assert record["output"] == ({"sections": ["repaired"]} if settled else {"sections": [{"text": "deepseek-flash"}]})


def test_the_first_attempt_is_on_disk_before_the_json_retry_is_sent(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    path = harness.generate.RUNS / LABEL / "deepseek-flash" / f"{TICKER}.json"
    seen: list = []

    class Killed(BaseException):
        pass

    def retry_sent() -> Any:
        seen.append(json.loads(path.read_text()))  # what a kill now would leave
        raise Killed

    sent = _real_generate(harness, monkeypatch, [], [])
    replies = [_result("not JSON", 0.3)]  # fails validation, so a JSON retry follows
    _generation(harness, "deepseek-flash", generation_ok=False, error="RateLimitError",  # a failed earlier run, paid
                attempts=[{"attempt": 0, "cost_usd": 0.1}])

    async def provider(arm: Any, system: str, user: str, **kwargs: Any) -> CallResult:
        sent.append(user)
        return replies.pop(0) if replies else retry_sent()

    monkeypatch.setattr(harness.generate, "call", provider)
    with pytest.raises(Killed):
        asyncio.run(harness.generate.run(LABEL, ["deepseek-flash"], [TICKER], 1))
    assert seen[0]["error"].startswith("interrupted") and seen[0]["cost_usd"] == 0.3 and len(seen[0]["attempts"]) == 1
    assert seen[0]["prior_attempts"] == [{"attempt": 0, "cost_usd": 0.1}] and seen[0]["prior_cost_usd"] == 0.1


def test_judge_order_one_is_on_disk_before_order_two_is_sent(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    rx, ry = _generation(harness, "deepseek-flash"), _generation(harness, "claude-sonnet-5-5")
    monkeypatch.setattr(harness.judge, "load_pack", lambda ticker, system="": {"split": "dev"})
    monkeypatch.setattr(harness.judge, "reader_text", lambda record, pack: record["arm"])
    path = harness.generate.RUNS / LABEL / "judge" / "gemma-4-31b" / f"{TICKER}__deepseek-flash__claude-sonnet-5-5.json"
    # An earlier run paid for an unusable order 1 on these drafts, and an order on a draft since replaced.
    _write(path, {"x_sha256": output_sha256(rx), "y_sha256": output_sha256(ry), "error": "NoVerdict",
                  "orders": [{"verdict": {}, "cost_usd": 0.3, "unusable": True, "position": 1}],
                  "superseded": [{"verdict": {}, "cost_usd": 0.2, "position": 1}]})
    seen: list = []

    async def one_order(judge: str, pack: Any, text_a: str, text_b: str, tag: str = "") -> dict[str, Any]:
        if text_a == "claude-sonnet-5-5":  # order 2: what a kill now would leave
            seen.append(json.loads(path.read_text()))
        return _usable(0.1)

    monkeypatch.setattr(harness.judge, "_one_order", one_order)
    asyncio.run(harness.judge.judge_pair(LABEL, TICKER, "deepseek-flash", "claude-sonnet-5-5", "gemma-4-31b", asyncio.Semaphore(1)))
    assert [o["position"] for o in seen[0]["orders"]] == [1, 1] and seen[0]["error"].startswith("interrupted")
    assert len(seen[0]["superseded"]) == 1 and seen[0]["cost_usd"] == pytest.approx(0.6)  # 0.1 + 0.3 + 0.2
    final = json.loads(path.read_text())
    assert "error" not in final and final["cost_usd"] == pytest.approx(0.7)  # replaced once order 2 returned


def test_the_report_shows_unjudged_pairs_when_none_was_judged(harness: Any) -> None:
    empty = {"judged_pairs": 0, "incomplete_panels": 0, "unjudged_pairs": 2, "stale_verdicts": 1}
    summary = {"splits": {split: {"companies": 1, "arms": {}, "causes": {}, "semantics": {}, "judge": empty}
                          for split in ("dev", "holdout", "all")}}
    text = harness.report.render(LABEL, ["deepseek-flash"], summary)
    assert "pairs with no verdict yet (each judge call failed or was refused): 2" in text
    assert "has changed since: 1" in text


def test_a_first_pass_from_another_prompt_is_refused_not_repaired(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    sent = _real_generate(harness, monkeypatch, [_result('{"sections": []}', 0.1)], [True])
    _first_pass(harness)
    path = harness.generate.RUNS / LABEL / "deepseek-flash" / f"{TICKER}.json"
    _write(path, {**json.loads(path.read_text()), "prompt_sha256": "another prompt"})
    before = path.read_text()
    with pytest.raises(SystemExit, match="test/deepseek-flash/T was made with prompt sha256 another prom"):
        asyncio.run(harness.generate.run(LABEL, ["deepseek-flash"], [TICKER], 1))  # a label holds one build of an arm
    assert sent == [] and path.read_text() == before


def test_a_models_own_failure_is_kept_not_bought_again(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    sent = _real_generate(harness, monkeypatch, [], [])
    _generation(harness, "deepseek-flash", generation_ok=False, gate={"passed": False}, attempts=[{"attempt": 0, "cost_usd": 0.1}])
    asyncio.run(harness.generate.run(LABEL, ["deepseek-flash"], [TICKER], 1))
    assert sent == []


def test_a_first_pass_cut_at_its_cap_keeps_its_cost(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    _real_generate(harness, monkeypatch, [_incomplete(0.5)], [])
    asyncio.run(harness.generate.run(LABEL, ["deepseek-flash"], [TICKER], 1))
    record = json.loads((harness.generate.RUNS / LABEL / "deepseek-flash" / f"{TICKER}.json").read_text())
    assert "IncompleteReply" in record["error"] and record["cost_usd"] == 0.5 and len(record["attempts"]) == 1


def test_a_finished_verdict_on_a_changed_draft_is_redone(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    record, bought = _judge(harness, monkeypatch, {"x_sha256": "an earlier draft", "result": {"overall": {"final": "tie"}},
                                                   "orders": [{**_usable(0.5), "position": 1}, {**_usable(0.5), "position": 2}]})
    assert bought == ["deepseek-flash", "claude-sonnet-5-5"] and len(record["superseded"]) == 2
    assert record["cost_usd"] == pytest.approx(1.2)


def _judge_calls(harness: Any, monkeypatch: pytest.MonkeyPatch, replies: list) -> tuple[Any, list]:
    """judge_pair over the real _one_order, with each judge call taking the next of ``replies``."""
    _generation(harness, "deepseek-flash"), _generation(harness, "claude-sonnet-5-5")
    monkeypatch.setattr(harness.judge, "load_pack", lambda ticker, system="": {"split": "dev"})
    monkeypatch.setattr(harness.judge, "reader_text", lambda record, pack: record["arm"])
    monkeypatch.setattr(harness.judge, "_user", lambda pack, a, b: a)
    sent: list = []

    async def judge_call(arm: Any, system: str, user: str, **kwargs: Any) -> CallResult:
        sent.append(user)
        reply = replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        return reply

    monkeypatch.setattr(harness.judge, "call", judge_call)
    pair = (LABEL, TICKER, "deepseek-flash", "claude-sonnet-5-5", "gemma-4-31b")
    return (lambda: asyncio.run(harness.judge.judge_pair(*pair, asyncio.Semaphore(1)))), sent


@pytest.mark.parametrize("reply, cost", [(_result('{"overall": ""}', 0.1), 0.1), (_incomplete(0.2), 0.2)])
def test_a_judge_reply_with_no_verdict_keeps_its_cost(harness: Any, monkeypatch: pytest.MonkeyPatch, reply: Any, cost: float) -> None:
    judge_pair, _ = _judge_calls(harness, monkeypatch, [reply])
    record = judge_pair()
    assert "error" in record and record["orders"][0]["unusable"] and record["cost_usd"] == pytest.approx(cost)


def test_a_refused_pair_is_recorded_once(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    refusal = CallResult("", 1000, 0, 5, 0, 1.0, 0.05, "anthropic", "m", {"stop_reason": "refusal"})
    judge_pair, sent = _judge_calls(harness, monkeypatch, [refusal])
    record = judge_pair()
    assert record["refused"] == "gemma-4-31b" and "error" not in record
    assert judge_pair() == record and len(sent) == 1  # never bought again


def test_semantics_audits_are_tied_to_their_output_and_left_out_when_not(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    _auditable(harness, monkeypatch)
    replies = [_result('{"items": [{"n": 0, "label": "consistent"}]}', 0.2), _result('{"items": [{"n": 1, "label": "consistent"}]}', 0.3)]

    async def auditor(*args: Any, **kwargs: Any) -> CallResult:
        return replies.pop(0)

    monkeypatch.setattr(harness.causes, "call", auditor)
    record = _generation(harness, "deepseek-flash")
    out = harness.generate.RUNS / LABEL / "semantics" / "deepseek-flash" / f"{TICKER}.json"
    asyncio.run(harness.semantics.run(LABEL, ["deepseek-flash"], [TICKER], 1))
    assert "error" in json.loads(out.read_text())  # numbered from 0: labelled nothing asked about
    assert harness.report.semantic_support(LABEL, ["deepseek-flash"], [TICKER])["deepseek-flash"]["left_out"] == {"pending": 1}
    asyncio.run(harness.semantics.run(LABEL, ["deepseek-flash"], [TICKER], 1))
    audit = json.loads(out.read_text())
    assert audit["output_sha256"] == output_sha256(record) and audit["prior_cost_usd"] == pytest.approx(0.2)
    support = harness.report.semantic_support(LABEL, ["deepseek-flash"], [TICKER])["deepseek-flash"]
    assert support["analyses"] == 1 and support["counts"] == {"consistent": 1}
    _generation(harness, "deepseek-flash", output={"sections": [{"text": "changed"}]})
    assert harness.report.semantic_support(LABEL, ["deepseek-flash"], [TICKER])["deepseek-flash"]["left_out"] == {"pending": 1}
    _write(out, {**audit, "output_sha256": output_sha256(json.loads((harness.generate.RUNS / LABEL / "deepseek-flash" / f"{TICKER}.json").read_text())),
                 "refused": True})
    assert harness.report.semantic_support(LABEL, ["deepseek-flash"], [TICKER])["deepseek-flash"]["left_out"] == {"refused": 1}


def test_the_report_prices_every_paid_call_and_counts_each_failure_once(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    from evals.trend_depth.providers import ARMS, list_cost

    monkeypatch.setattr(harness.report, "load_pack", lambda ticker, system="": {})
    monkeypatch.setattr(harness.report, "factcheck", types.SimpleNamespace(check=lambda sentences, pack: {"passed": True}))
    one = {"attempt": 0, "backend": "openai_compat", "input_tokens": 1000, "cached_input_tokens": 0, "output_tokens": 100, "cost_usd": 0.0}
    gate = {"passed": True, "claims": 1, "failed_claims": 0, "failures": [], "detail": []}
    settled = {"ticker": "A", "arm": "deepseek-flash", "generation_ok": True, "attempts": [one], "prior_attempts": [one],
               "output": {"sections": [{"sentences": [{"type": "fact", "text": "x"}]}]}, "gate": gate, "words": 10,
               "usage": {"input_tokens": 1000, "output_tokens": 100}, "latency_s": 1.0}
    failed = {"ticker": "B", "arm": "deepseek-flash", "generation_ok": False, "attempts": [one], "gate": {"passed": False}}
    errored = {"ticker": "C", "arm": "deepseek-flash", "generation_ok": False, "error": "BudgetExceeded", "attempts": [],
               "prior_attempts": [one]}
    pending = {**settled, "ticker": "D", "repair_error": "APIConnectionError", "prior_attempts": []}
    stats = harness.report.arm_stats([settled, failed, errored, pending])
    call_cost = list_cost(ARMS["deepseek-flash"], 1000, 0, 100)
    assert (stats["generated"], stats["failed_generations"], stats["provider_errors"], stats["pending_repairs"]) == (1, 1, 1, 1)
    assert stats["cost_mean"] == pytest.approx(5 * call_cost / 4)  # five paid calls over four generations
    assert stats["failed_generation_cost"] == pytest.approx(3 * call_cost)  # the failure, the error, the replaced one


def _prompt(relative: str) -> str:
    return (REPO / relative).read_text()


@pytest.mark.parametrize("arm, prompt, folder", [
    ("deepseek-flash", FROZEN_PROMPT, "packs"), ("deepseek-flash-p", FROZEN_PROMPT, "packs-v2"),
    ("deepseek-flash-q", CANDIDATE_PROMPT, "packs"), ("deepseek-flash-c", CANDIDATE_PROMPT, "packs-v2"),
])
def test_each_arm_generates_from_its_own_prompt_and_pack(harness: Any, monkeypatch: pytest.MonkeyPatch, arm: str,
                                                         prompt: str, folder: str) -> None:
    generate, packs, gated, sent = harness.generate, _packs(harness), [], []
    monkeypatch.setattr(generate, "user_message", lambda pack: pack["dir"])
    monkeypatch.setattr(generate, "validate", lambda parsed: [])
    monkeypatch.setattr(generate, "word_count", lambda parsed: 1)
    monkeypatch.setattr(generate, "sentences_of", lambda parsed: [])
    monkeypatch.setattr(generate.factcheck, "check", lambda sentences, pack: gated.append(pack["dir"]) or {"passed": True})

    async def provider(arm_: Any, system: str, user: str, **kwargs: Any) -> CallResult:
        sent.append((system, user))
        return _result('{"sections": []}', 0.1)

    monkeypatch.setattr(generate, "call", provider)
    record = asyncio.run(generate.generate_proposed(arm, TICKER))
    assert sent == [(_prompt(prompt), folder)] and gated == [folder]  # the prompt it pins, on its pack, gated on it
    assert record["prompt_sha256"] == hashlib.sha256(_prompt(prompt).encode()).hexdigest()
    assert (record["packs"], record["pack_sha256"], record["snapshot_id"]) == (folder, pack_sha256(packs[folder]), "s1")


@pytest.mark.parametrize("built, expected", [("now", ["repair"]), ("before a rebuild", [])])
def test_a_repair_is_retried_only_on_the_pack_build_its_first_pass_read(harness: Any, monkeypatch: pytest.MonkeyPatch,
                                                                         built: str, expected: list) -> None:
    events = _stub_generate(harness, monkeypatch, "s1")  # packs-v2 rebuilt in place keeps its snapshot_id
    pack = harness.generate.load_pack(TICKER, "deepseek-flash-c")
    _generation(harness, "deepseek-flash-c", repair_error="APIConnectionError", snapshot_id="s1",
                prompt_sha256=hashlib.sha256(b"the prompt").hexdigest(), attempts=[{"attempt": 0, "cost_usd": 0.2}],
                pack_sha256=pack_sha256(pack) if built == "now" else "an earlier build of packs-v2")
    if expected:
        asyncio.run(harness.generate.run(LABEL, ["deepseek-flash-c"], [TICKER], 1))
    else:  # neither repaired nor regenerated: the label refuses a second build of the arm
        with pytest.raises(SystemExit, match="was made from evidence pack sha256 an earlier b"):
            asyncio.run(harness.generate.run(LABEL, ["deepseek-flash-c"], [TICKER], 1))
    assert events == expected


def test_copying_checks_each_arm_against_its_own_prompt_and_pack(harness: Any) -> None:
    packs, source = _packs(harness), harness.generate.RUNS / "source"
    frozen, candidate = (hashlib.sha256(_prompt(p).encode()).hexdigest() for p in (FROZEN_PROMPT, CANDIDATE_PROMPT))
    eval_v1 = {"ticker": TICKER, "generation_ok": True, "prompt_sha256": frozen, "snapshot_id": "s1"}  # no pack hash
    _write(source / "deepseek-flash" / f"{TICKER}.json", {**eval_v1, "arm": "deepseek-flash"})
    _write(source / "deepseek-flash-c" / f"{TICKER}.json", {**eval_v1, "arm": "deepseek-flash-c", "prompt_sha256": candidate,
                                                             "pack_sha256": pack_sha256(packs["packs-v2"])})
    assert harness.generate.copy_systems("source", LABEL, ["deepseek-flash", "deepseek-flash-c"], [TICKER]) == 2
    for arm, record in (("deepseek-flash-q", eval_v1),  # the control's prompt, under an arm on the candidate
                        ("deepseek-flash-p", {**eval_v1, "pack_sha256": pack_sha256(packs["packs"])})):  # read packs/
        _write(source / arm / f"{TICKER}.json", {**record, "arm": arm})
        with pytest.raises(SystemExit):
            harness.generate.copy_systems("source", LABEL, [arm], [TICKER])


def test_the_audits_and_the_judge_read_each_systems_own_pack(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    _packs(harness)
    _generation(harness, "deepseek-flash"), _generation(harness, "deepseek-flash-c")
    read: list = []
    monkeypatch.setattr(harness.causes, "cause_items", lambda sentences, pack: read.append(("causes", pack["dir"])) or [])
    monkeypatch.setattr(harness.semantics, "factcheck", types.SimpleNamespace(
        check=lambda sentences, pack: read.append(("semantics", pack["dir"])) or {"detail": []}))
    asyncio.run(harness.causes.run(LABEL, ["deepseek-flash-c"], [TICKER], 1))
    asyncio.run(harness.semantics.run(LABEL, ["deepseek-flash-c"], [TICKER], 1))
    monkeypatch.setattr(harness.judge, "reader_text", lambda record, pack: read.append((record["arm"], pack["dir"])) or record["arm"])

    async def one_order(judge: str, pack: Any, text_a: str, text_b: str, tag: str = "") -> dict[str, Any]:
        read.append(("judge's header", pack["dir"]))
        return _usable(0.1)

    monkeypatch.setattr(harness.judge, "_one_order", one_order)
    asyncio.run(harness.judge.judge_pair(LABEL, TICKER, "deepseek-flash", "deepseek-flash-c", "claude-opus-5-5",
                                         asyncio.Semaphore(1)))
    assert read == [("causes", "packs-v2"), ("semantics", "packs-v2"), ("deepseek-flash", "packs"),
                    ("deepseek-flash-c", "packs-v2"), ("judge's header", "packs"), ("judge's header", "packs")]


def test_the_report_reads_each_systems_own_pack(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    _packs(harness)
    read: list = []
    monkeypatch.setattr(harness.report, "factcheck", types.SimpleNamespace(
        check=lambda sentences, pack: read.append(pack["dir"]) or {"passed": True}))
    monkeypatch.setattr(harness.report, "classify_flag", lambda item, sentences, pack, view: read.append(pack["dir"]) or "substantive")
    record = _generation(harness, "deepseek-flash-c", gate={"passed": True, "claims": 1, "failed_claims": 0, "failures": []},
                         output={"sections": [{"sentences": [{"type": "fact", "text": "x"}]}]}, words=10, latency_s=1.0,
                         usage={"input_tokens": 1000, "output_tokens": 100})
    harness.report.arm_stats([record])  # the final output and its first pass, under the gate as it is now
    _write(harness.generate.RUNS / LABEL / "semantics" / "deepseek-flash-c" / f"{TICKER}.json",
           {"auditor": "claude-opus-5-5", "output_sha256": output_sha256(record),
            "items": [{"label": "mismatch", "claim": "5", "sentence": "x", "reason": "r"}]})
    harness.report.semantic_support(LABEL, ["deepseek-flash-c"], [TICKER])
    assert read == ["packs-v2", "packs-v2", "packs-v2"]


def test_these_tests_leave_the_real_bootstrap_unloaded() -> None:
    assert "evals.trend_depth.bootstrap" not in sys.modules
