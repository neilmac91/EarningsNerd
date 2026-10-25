"""The depth harness's version-2 repair loop (evals/trend_depth/generate.py ``--pipeline v2``; DEEPSEEK-ERRORS.md
fixes 1, 2, 5 and 13), run over scripted provider replies and a synthetic pack, with the real gate.

Pins: the gate on the model's own output is kept before the code fixes, and a first pass the code fixes make whole
is never sent to a repair; the repair message lists what each cited ID holds and never asks for "the cited value";
patches change the failed sentences alone, byte for byte everywhere else, and an unusable patch list falls back to
the full repair, with the paid patch call on disk first; a retype-only repair that keeps an explanatory clause
still fails; and version 1 runs exactly as eval-v1 did. ``generate`` is imported over a stub bootstrap whose
records live in ``tmp_path`` (the fixture is ``test_trend_depth_stages.py``'s), so the real bootstrap never loads.
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

STAGES = ("generate",)
LABEL, TICKER, ARM = "test", "T", "deepseek-flash"


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

    monkeypatch.setattr(stages.generate, "call", no_call)
    monkeypatch.setattr(stages.generate, "PROMPT_DRAFT", "")  # a TREND_DEPTH_PROMPT in the shell changes nothing here
    yield stages
    for name in [n for n in sys.modules if n.split(".")[-1] in (*STAGES, "gold") and n.startswith("evals.trend_depth.")]:
        del sys.modules[name]  # the next test imports them afresh, over its own records


def _value(vid: str, label: str, period: str, unit: str, number: float, **extra: Any) -> tuple[str, dict[str, Any]]:
    return vid, {"id": vid, "label": label, "period": period, "unit": unit, "value": number, **extra}


SERIES = {"F3": "gross_margin|FY2024", "F4": "gross_margin|FY2025", "D1": "ch:gross_margin|FY2025",
          "D2": "net_cash_to_revenue|FY2025", "D3": "peer_pctile:net_cash_to_revenue|FY2025",
          "D4": "peer_median:net_cash_to_revenue|FY2025", "D8": "cs:sga|FY2025"}
PACK: dict[str, Any] = {
    "split": "dev", "profile": "p", "window": "FY2024..FY2025", "snapshot_id": "s1",
    "values": dict([
        _value("F3", "Gross margin", "FY2024", "pct", 75.0),
        _value("F4", "Gross margin", "FY2025", "pct", 71.1),
        _value("D1", "Gross margin change", "FY2025", "pp", -3.9, inputs=["F4", "F3"]),
        _value("D2", "Net cash % of revenue", "FY2025", "pct", 2.0965),
        _value("D3", "Net cash % of revenue: percentile vs energy peers (n=6)", "FY2025", "pctile", 83.33, inputs=["D2"]),
        _value("D4", "Net cash % of revenue: energy peer median (n=6)", "FY2025", "pct", -7.71),
        _value("D8", "SG&A % of revenue", "FY2025", "pct", 30.3),
    ]),
    "series_keys": {key: vid for vid, key in SERIES.items()},
    "passages": [{"id": "P1", "text": "Pricing fell on new competition."}],
    "red_flags": [],
}
STEADY = [("arc", "fact", "Gross margin was 75.0% in FY2024 [F3]."), ("margins", "fact", "SG&A was 30.3% of revenue [D8]."),
          ("balance_sheet", "fact", "Net cash was 2.1% of revenue [D2].")]
WRONG = "Gross margin fell 3.9pp to 70.0% [D1]."  # 70.0% is in no cited value and no code can cite it
PASSED = "Gross margin was 71.1% in FY2025 [F4]."
RIGHT = "Gross margin fell 3.9pp to 71.1% [D1][F4]."
UNCITED = "That 2.1% net cash position ranks in the 83rd percentile of six energy peers, whose median is -7.7% [D3][D4]."
SO_CAUSE = "Gross margin fell 3.9pp [D1], so pricing power is weakening."


def _analysis(*placed: tuple[str, str, str]) -> dict[str, Any]:
    """All seven sections, holding ``(section, type, text)`` sentences in order."""
    from evals.trend_depth.generate import SECTION_KEYS

    return {"sections": [{"key": key, "sentences": [{"type": kind, "text": text} for section, kind, text in placed if section == key]}
                         for key in SECTION_KEYS]}


def _result(text: str, cost: float = 0.1) -> CallResult:
    return CallResult(text, 1000, 0, 100, 0, 1.0, cost, "openai_compat", "m", {"stop_reason": "end_turn"})


def _patch(original: str, **change: Any) -> str:
    return json.dumps({"patches": [{"section": "cash", "original": original, **change}]})


def _wire(harness: Any, monkeypatch: pytest.MonkeyPatch, replies: list) -> list:
    """Stub the pack and the prompt, and make each call take the next of ``replies`` (a result, a reply text, or an
    exception to raise). Returns the user messages the calls were sent."""
    generate = harness.generate
    monkeypatch.setattr(generate, "load_pack", lambda ticker, system="": PACK)
    monkeypatch.setattr(generate, "system_prompt", lambda arm_name: "the prompt")
    monkeypatch.setattr(generate, "user_message", lambda pack: "the pack")
    sent: list = []

    async def provider(arm: Any, system: str, user: str, **kwargs: Any) -> CallResult:
        sent.append(user)
        reply = replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        return _result(reply) if isinstance(reply, str) else reply

    monkeypatch.setattr(generate, "call", provider)
    return sent


def _generate(harness: Any, pipeline: str = "v2") -> dict[str, Any]:
    return asyncio.run(harness.generate.generate_proposed(ARM, TICKER, pipeline=pipeline))


def _sentences(output: dict[str, Any]) -> list[str]:
    return [json.dumps(s) for section in output["sections"] for s in section["sentences"]]


def test_a_first_pass_the_code_fixes_make_whole_is_never_repaired(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    first = _analysis(*STEADY, ("cash", "comparison", UNCITED), ("drivers", "cause", "The FY2025 gross-margin fall was 3.9pp [D1]."))
    sent = _wire(harness, monkeypatch, [json.dumps(first)])
    record = _generate(harness)
    assert len(sent) == 1 and record["pipeline"] == "v2"
    raw = record["raw_first_pass_gate"]  # the model's own output, before the code fixes, under the gate with backstops
    assert not raw["passed"] and "backstop_failures" in raw
    assert sorted(f["failure"] for f in raw["failures"]) == ["'2.1%' matches nothing the sentence cites", "cause sentence cites no filing passage"]
    assert record["autocite"] == {"added": [{"section": "cash", "sentence": UNCITED, "claim": "2.1%", "id": "D2"}], "rejected": 0}
    assert record["retyped"] == [{"section": "drivers", "sentence": "The FY2025 gross-margin fall was 3.9pp [D1].", "from": "cause", "to": "comparison"}]
    assert record["gate"]["passed"] and "backstop_failures" in record["gate"]
    assert not {"first_pass_gate", "first_pass_output", "repair_kind"} & set(record)
    assert UNCITED[:-1] + "[D2]." in json.dumps(record["output"])


def test_a_patch_changes_the_failed_sentence_and_nothing_else(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    first = _analysis(*STEADY, ("cash", "comparison", WRONG), ("cash", "fact", "Net cash was 2.1% of revenue [D2]."))
    sent = _wire(harness, monkeypatch, [json.dumps(first), _patch(WRONG, type="comparison", text=RIGHT)])
    record = _generate(harness)
    assert len(sent) == 2 and record["repair_kind"] == "patch" and record["gate"]["passed"]
    assert [a["attempt"] for a in record["attempts"]] == [0, "repair"] and record["cost_usd"] == pytest.approx(0.2)
    assert record["first_pass_gate"]["failures"][0]["sentence"] == WRONG and record["first_pass_output"] == first
    before, after = _sentences(first), _sentences(record["output"])
    changed = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
    assert len(before) == len(after) and [json.loads(after[i])["text"] for i in changed] == [RIGHT]
    message = sent[1]
    assert '"patches"' in message and "use the cited value exactly" not in message
    assert "[D1] Gross margin change, FY2025 = -3.9pp" in message
    assert "never replace it with a cited value of a different metric or year" in message


def test_a_patch_can_delete_the_failed_sentence(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    first = _analysis(*STEADY, ("cash", "comparison", WRONG))
    _wire(harness, monkeypatch, [json.dumps(first), _patch(WRONG, delete=True)])
    record = _generate(harness)
    assert record["repair_kind"] == "patch" and record["gate"]["passed"]
    assert _sentences(record["output"]) == [s for s in _sentences(first) if WRONG not in s]


@pytest.mark.parametrize("reply", [
    '{"sentences": []}',  # no patch list
    '{"patches": []}',  # nothing to apply
    _patch(PASSED, type="fact", text="Gross margin was 71.1% [F4]."),  # a sentence that did not fail
    _patch(WRONG, type="comparison", text="  "),  # no text
    _patch(WRONG, type="opinion", text=RIGHT),  # no valid type
    json.dumps({"patches": [{"section": "cash", "original": WRONG, "delete": True}] * 2}),  # one sentence twice
])
def test_an_unusable_patch_list_falls_back_to_the_full_repair(harness: Any, monkeypatch: pytest.MonkeyPatch, reply: str) -> None:
    first = _analysis(*STEADY, ("cash", "fact", PASSED), ("cash", "comparison", WRONG))
    whole = _analysis(*STEADY, ("cash", "fact", PASSED), ("cash", "comparison", RIGHT))
    sent = _wire(harness, monkeypatch, [json.dumps(first), reply, json.dumps(whole)])
    record = _generate(harness)
    assert len(sent) == 3 and record["repair_kind"] == "full" and record["output"] == whole and record["gate"]["passed"]
    assert [a["attempt"] for a in record["attempts"]] == [0, "repair", "repair"] and record["attempts"][1]["problems"]
    assert "Return the whole analysis again" in sent[2] and "use the cited value exactly" not in sent[2]


def test_the_paid_patch_is_on_disk_before_the_full_repair_is_sent(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    first = _analysis(*STEADY, ("cash", "comparison", WRONG))
    path = harness.generate.RUNS / LABEL / ARM / f"{TICKER}.json"

    class Killed(BaseException):
        pass

    sent = _wire(harness, monkeypatch, [json.dumps(first), '{"patches": []}', Killed()])
    with pytest.raises(Killed):
        asyncio.run(harness.generate.run(LABEL, [ARM], [TICKER], 1, "v2"))
    kept = json.loads(path.read_text())
    assert kept["repair_error"].startswith("interrupted: the full repair") and len(kept["attempts"]) == 2
    assert kept["cost_usd"] == pytest.approx(0.2) and kept["output"] == first
    sent.clear()
    _wire(harness, monkeypatch, [_patch(WRONG, type="comparison", text=RIGHT)])
    asyncio.run(harness.generate.run(LABEL, [ARM], [TICKER], 1, "v2"))
    settled = json.loads(path.read_text())  # only the repair was bought again, as a patch
    assert "repair_error" not in settled and settled["repair_kind"] == "patch" and len(settled["attempts"]) == 3


@pytest.mark.parametrize("kind, passes", [("fact", False), ("comparison", False), ("judgement", True)])
def test_a_retype_only_repair_that_keeps_its_explanation_still_fails(harness: Any, monkeypatch: pytest.MonkeyPatch,
                                                                     kind: str, passes: bool) -> None:
    first = _analysis(*STEADY, ("cash", "cause", SO_CAUSE))
    sent = _wire(harness, monkeypatch, [json.dumps(first), _patch(SO_CAUSE, type=kind, text=SO_CAUSE)])
    record = _generate(harness)
    assert record["retyped"] == [] and record["repair_kind"] == "patch"  # "so" kept it a cause: the repair decides
    assert "cite, in this sentence, the filing passage that states the cause" in sent[1]
    assert "retype it as judgement if it states no figure it does not cite" in sent[1] and "delete the causal clause" in sent[1]
    assert record["gate"]["passed"] is passes
    escapes = [f for f in record["gate"]["failures"] if "explanatory" in f["failure"]]
    assert escapes == ([] if passes else [{"section": "cash", "sentence": SO_CAUSE, "type": kind,
                                           "failure": "retyped from cause without a passage but keeps its explanatory 'so' clause"}])


def test_version_1_runs_as_eval_v1_did(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    first = _analysis(*STEADY, ("cash", "comparison", UNCITED))
    whole = _analysis(*STEADY, ("cash", "comparison", UNCITED[:-1] + "[D2]."))
    sent = _wire(harness, monkeypatch, [json.dumps(first), json.dumps(whole)])
    real, gated = harness.generate.factcheck.check, []
    monkeypatch.setattr(harness.generate.factcheck, "check", lambda sentences, pack, **kw: gated.append(kw) or real(sentences, pack, **kw))
    record = _generate(harness, pipeline="v1")
    assert len(sent) == 2 and gated == [{}, {}]  # no code fix: the repair is sent, and the gate has no backstops
    assert not {"pipeline", "raw_first_pass_gate", "autocite", "retyped", "repair_kind"} & set(record)
    assert sent[1] == harness.generate.repair_message("the pack", first, record["first_pass_gate"]["failures"])
    assert "use the cited value exactly" in sent[1] and record["output"] == whole and record["gate"]["passed"]


def _owed(harness: Any, **fields: Any) -> None:
    """A first pass on disk, owed its repair, from this prompt and pack."""
    first = _analysis(*STEADY, ("cash", "comparison", WRONG))
    gate = harness.generate.factcheck.check(harness.generate.sentences_of(first), PACK, backstops=True)
    record = {"ticker": TICKER, "arm": ARM, "generation_ok": True, "output": first, "gate": gate, "snapshot_id": "s1",
              "prompt_sha256": hashlib.sha256(b"the prompt").hexdigest(), "repair_error": "APIConnectionError",
              "attempts": [{"attempt": 0, "cost_usd": 0.2}], "usage": {"input_tokens": 1, "cached_input_tokens": 0,
              "output_tokens": 1, "reasoning_tokens": 0}, "latency_s": 1.0, "cost_usd": 0.2, **fields}
    path = harness.generate.RUNS / LABEL / ARM / f"{TICKER}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record))


@pytest.mark.parametrize("made_with, run_with, first_message", [
    ("v2", "v2", "patches"),  # the same pipeline: only the repair, as a patch
    ("v1", "v2", "the pack"),  # another pipeline: the first pass is made again
    ("v2", "v1", "the pack"),
])
def test_a_repair_is_retried_only_under_the_pipeline_of_its_first_pass(harness: Any, monkeypatch: pytest.MonkeyPatch,
                                                                       made_with: str, run_with: str, first_message: str) -> None:
    _owed(harness, **({"pipeline": "v2"} if made_with == "v2" else {}))
    whole = _analysis(*STEADY, ("cash", "comparison", RIGHT))
    sent = _wire(harness, monkeypatch, [_patch(WRONG, type="comparison", text=RIGHT) if first_message == "patches" else json.dumps(whole)])
    asyncio.run(harness.generate.run(LABEL, [ARM], [TICKER], 1, run_with))
    assert len(sent) == 1 and (first_message in sent[0] if first_message == "patches" else sent[0] == first_message)
    record = json.loads((harness.generate.RUNS / LABEL / ARM / f"{TICKER}.json").read_text())
    assert record.get("pipeline", "v1") == run_with and "repair_error" not in record


@pytest.mark.parametrize("made_with, copy_with", [("v1", "v2"), ("v2", "v1")])
def test_copying_checks_the_pipeline(harness: Any, monkeypatch: pytest.MonkeyPatch, made_with: str, copy_with: str) -> None:
    _wire(harness, monkeypatch, [])
    prompt = hashlib.sha256(b"the prompt").hexdigest()
    record = {"ticker": TICKER, "arm": ARM, "generation_ok": True, "prompt_sha256": prompt, "snapshot_id": "s1",
              **({"pipeline": "v2"} if made_with == "v2" else {})}
    source = harness.generate.RUNS / "source" / ARM / f"{TICKER}.json"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(json.dumps(record))
    with pytest.raises(SystemExit, match="pipeline"):
        harness.generate.copy_systems("source", LABEL, [ARM], [TICKER], copy_with)
    assert harness.generate.copy_systems("source", LABEL, [ARM], [TICKER], made_with) == 1


def test_these_tests_leave_the_real_bootstrap_unloaded() -> None:
    assert "evals.trend_depth.bootstrap" not in sys.modules
