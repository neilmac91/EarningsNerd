"""The depth harness's version-2 repair loop (evals/trend_depth/generate.py ``--pipeline v2``; DEEPSEEK-ERRORS.md
fixes 1, 2, 5 and 13), run over scripted provider replies and a synthetic pack, with the real gate.

Pins: the gate on the model's own output is kept before the code fixes, and a first pass the code fixes make whole
is never sent to a repair; each version-2 message opens with its analysis' nonce, which the repair and a retried
repair repeat; the repair message lists what each cited ID holds and never asks for "the cited value"; patches change
the failed sentences alone, byte for byte everywhere else; an unusable patch list (a section or original that is no
string included) falls back to the full repair, and a recoverable one (no type, the listing's prefix, a whole
analysis) needs no second call; every paid call is on the record before its reply is read, and the paid patch call
is on disk before the full repair is sent, on a retried repair too; a run resumed after an unusable patch (a kill, a
provider error, a full repair cut off at its token cap) sends only the full repair it owes, never a second patch, so
its record reads "full" with the patch's and the full repair's calls; a refused patch stands; the gate after a repair
applies the backstops; a retype-only repair that keeps an explanatory clause still fails, whatever else it edits;
a label refuses to mix an arm's pipelines, prompts or packs; and version 1 runs eval-v1's procedure under the current
gate. Also ``repair_replay`` (DEEPSEEK-ERRORS.md §3 step 1): it repairs exactly the recorded first passes version 2
would repair, through that same repair, and reports each repeat's calls, latency, tokens, cost (billed and warm, the
warm prefix capping what a repair's longer prompt reads from cache), gate and untouched sentences, keeping what was
paid for; its dry run prints the most a run can send and bill (two cold calls a repeat, each reply at max_tokens).
``generate`` is imported over a stub bootstrap whose records live in ``tmp_path`` (the fixture is
``test_trend_depth_stages.py``'s), so the real bootstrap never loads.
"""
from __future__ import annotations

import asyncio
import hashlib
import importlib
import json
import re
import sys
import types
from pathlib import Path
from typing import Any

import pytest

from evals.trend_depth.providers import CallResult, IncompleteReply

STAGES = ("generate", "repair_replay")
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
          "D4": "peer_median:net_cash_to_revenue|FY2025", "D8": "cs:sga|FY2025", "D9": "net_cash|FY2025"}
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
        _value("D9", "Net cash (cash and investments less debt)", "FY2025", "usd", -26.2e9),
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
UNCITED = "Net cash of 2.1% of revenue ranks in the 83rd percentile of six energy peers, whose median is -7.7% [D3][D4]."
SO_CAUSE = "Gross margin fell 3.9pp [D1], so pricing power is weakening."
SIGNED = "Net debt was -$26.2 billion in FY2025 [D9]."  # true by magnitude, but net cash's minus sign under "net debt"


def _analysis(*placed: tuple[str, str, str]) -> dict[str, Any]:
    """All seven sections, holding ``(section, type, text)`` sentences in order."""
    from evals.trend_depth.generate import SECTION_KEYS

    return {"sections": [{"key": key, "sentences": [{"type": kind, "text": text} for section, kind, text in placed if section == key]}
                         for key in SECTION_KEYS]}


def _result(text: str, cost: float = 0.1, stop: str = "end_turn") -> CallResult:
    return CallResult(text, 1000, 0, 100, 0, 1.0, cost, "openai_compat", "m", {"stop_reason": stop})


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


def _path(harness: Any, ticker: str = TICKER) -> Path:
    return harness.generate.RUNS / LABEL / ARM / f"{ticker}.json"


def _sentences(output: dict[str, Any]) -> list[str]:
    return [json.dumps(s) for section in output["sections"] for s in section["sentences"]]


def _opened(harness: Any, label: str = "") -> str:
    """The user message of a version-2 analysis under ``label``: the stub pack led by its nonce."""
    return harness.generate.opening("the pack", harness.generate.analysis_nonce(label, ARM, TICKER))


def test_a_first_pass_the_code_fixes_make_whole_is_never_repaired(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    first = _analysis(*STEADY, ("cash", "comparison", UNCITED), ("drivers", "cause", "The FY2025 gross-margin fall was 3.9pp [D1]."))
    sent = _wire(harness, monkeypatch, [json.dumps(first)])
    record = _generate(harness)
    assert sent == [_opened(harness)] and record["pipeline"] == "v2"
    raw = record["raw_first_pass_gate"]  # the model's own output, before the code fixes, under the gate with backstops
    assert not raw["passed"] and "backstop_failures" in raw
    assert sorted(f["failure"] for f in raw["failures"]) == ["'2.1%' matches nothing the sentence cites", "cause sentence cites no filing passage"]
    assert record["autocite"] == {"added": [{"section": "cash", "sentence": UNCITED, "claim": "2.1%", "id": "D2"}], "rejected": 0}
    assert record["retyped"] == [{"section": "drivers", "sentence": "The FY2025 gross-margin fall was 3.9pp [D1].", "from": "cause", "to": "comparison"}]
    assert record["gate"]["passed"] and "backstop_failures" in record["gate"]
    assert not {"first_pass_gate", "first_pass_output", "repair_kind"} & set(record)
    assert UNCITED[:-1] + "[D2]." in json.dumps(record["output"])


def test_version_2_opens_every_message_with_its_analysis_nonce(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    first = _analysis(*STEADY, ("cash", "comparison", WRONG))
    sent = _wire(harness, monkeypatch, [json.dumps(first), '{"patches": []}', json.dumps(_analysis(*STEADY, ("cash", "comparison", RIGHT)))])
    asyncio.run(harness.generate.run(LABEL, [ARM], [TICKER], 1, "v2"))
    record = json.loads(_path(harness).read_text())
    nonce = harness.generate.analysis_nonce(LABEL, ARM, TICKER)
    assert record["nonce"] == nonce and re.fullmatch(r"[0-9a-f]{12}", nonce)
    assert len(sent) == 3 and all(message.startswith(f"Request {nonce}.\n\nthe pack") for message in sent)  # first, patch, full
    others = {harness.generate.analysis_nonce(*key) for key in (("other", ARM, TICKER), (LABEL, "deepseek-flash-c", TICKER),
                                                                (LABEL, ARM, "U"))}
    assert nonce not in others and len(others) == 3  # every other label, arm and company opens differently


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
    json.dumps({"patches": [{"section": ["cash"], "original": WRONG, "type": "comparison", "text": RIGHT}]}),  # no string section
    json.dumps({"patches": [{"section": "cash", "original": [WRONG], "type": "comparison", "text": RIGHT}]}),  # no string original
])
def test_an_unusable_patch_list_falls_back_to_the_full_repair(harness: Any, monkeypatch: pytest.MonkeyPatch, reply: str) -> None:
    first = _analysis(*STEADY, ("cash", "fact", PASSED), ("cash", "comparison", WRONG))
    whole = _analysis(*STEADY, ("cash", "fact", PASSED), ("cash", "comparison", RIGHT))
    sent = _wire(harness, monkeypatch, [json.dumps(first), reply, json.dumps(whole)])
    record = _generate(harness)
    assert len(sent) == 3 and record["repair_kind"] == "full" and record["output"] == whole and record["gate"]["passed"]
    assert [a["attempt"] for a in record["attempts"]] == [0, "repair", "repair"] and record["attempts"][1]["problems"]
    assert "Return the whole analysis again" in sent[2] and "use the cited value exactly" not in sent[2]


def test_a_patch_to_a_failed_sentence_that_stands_twice_in_its_section_falls_back(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    first = _analysis(*STEADY, ("cash", "comparison", WRONG), ("cash", "comparison", WRONG))
    whole = _analysis(*STEADY, ("cash", "comparison", RIGHT))
    sent = _wire(harness, monkeypatch, [json.dumps(first), _patch(WRONG, type="comparison", text=RIGHT), json.dumps(whole)])
    record = _generate(harness)
    assert len(sent) == 3 and record["repair_kind"] == "full" and record["output"] == whole
    assert record["attempts"][1]["problems"] == ["patch 1 does not quote one failed sentence of its section"]


@pytest.mark.parametrize("name, kind", [("no type", "patch"), ("listing prefix", "patch"), ("bulleted prefix", "patch"),
                                        ("whole analysis", "full")])
def test_a_recoverable_patch_reply_needs_no_second_call(harness: Any, monkeypatch: pytest.MonkeyPatch, name: str, kind: str) -> None:
    first = _analysis(*STEADY, ("cash", "comparison", WRONG))
    whole = _analysis(*STEADY, ("cash", "comparison", RIGHT))
    reply = {"no type": _patch(WRONG, text=RIGHT),  # the sentence keeps its own type
             "listing prefix": _patch(f"[cash] {WRONG}", type="comparison", text=RIGHT),  # copied as the listing prints it
             "bulleted prefix": _patch(f"- [cash] {WRONG}", type="comparison", text=RIGHT),
             "whole analysis": json.dumps(whole)}[name]  # the full repair, unasked
    sent = _wire(harness, monkeypatch, [json.dumps(first), reply])
    record = _generate(harness)
    assert len(sent) == 2 and record["repair_kind"] == kind and record["output"] == whole and record["gate"]["passed"]
    assert [a["attempt"] for a in record["attempts"]] == [0, "repair"] and record["attempts"][1]["problems"] == []


def test_a_patch_reply_is_on_the_record_before_it_is_read(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    first = _analysis(*STEADY, ("cash", "comparison", WRONG))
    _wire(harness, monkeypatch, [json.dumps(first), _patch(WRONG, type="comparison", text=RIGHT)])

    def unreadable(*args: Any) -> None:
        raise TypeError("unhashable type: 'list'")

    monkeypatch.setattr(harness.generate, "read_patch_reply", unreadable)
    record = _generate(harness)  # the paid patch call counts though its reply could not be read
    assert record["repair_error"].startswith("TypeError") and [a["attempt"] for a in record["attempts"]] == [0, "repair"]
    assert record["cost_usd"] == pytest.approx(0.2) and record["usage"]["output_tokens"] == 200


def test_a_full_repair_whose_reply_cannot_be_read_is_still_owed(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    first = _analysis(*STEADY, ("cash", "comparison", WRONG))
    sent = _wire(harness, monkeypatch, [json.dumps(first), '{"patches": []}', json.dumps(first)])
    real = harness.generate.parse_json_object

    def unreadable(text: str) -> Any:
        if text == json.dumps(first) and len(sent) == 3:  # the full repair's reply, not the first pass's
            raise TypeError("unreadable")
        return real(text)

    monkeypatch.setattr(harness.generate, "parse_json_object", unreadable)
    record = _generate(harness)  # paid, on the record, and the full repair still owed: a resumed run sends it again
    assert record["repair_error"].startswith("TypeError") and record["repair_owed"] == "full" and len(record["attempts"]) == 3


def test_a_refused_patch_stands(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    first = _analysis(*STEADY, ("cash", "comparison", WRONG))
    sent = _wire(harness, monkeypatch, [json.dumps(first), _result("", stop="refusal")])
    record = _generate(harness)
    assert len(sent) == 2 and record["repair_kind"] == "patch" and record["repair_failed"] == ["the model refused (stop_reason refusal)"]
    assert record["output"] == first and not record["gate"]["passed"] and len(record["attempts"]) == 2


class Killed(BaseException):
    """A kill or Ctrl-C mid-call: no ``except Exception`` catches it."""


@pytest.mark.parametrize("stop, calls", [
    (Killed(), 3),  # the kill leaves the checkpoint: first pass, patch, then the full repair the resumed run sends
    (RuntimeError("503 Service Unavailable"), 3),  # a provider error outlasting the retries: nothing was billed
    # The full repair cut off at its token cap was paid for, so it stays on the record beside the one resent.
    (IncompleteReply("the reply stopped at max_tokens", _result("{", stop="max_tokens")), 4),
])
def test_a_run_resumed_after_an_unusable_patch_sends_only_the_full_repair(harness: Any, monkeypatch: pytest.MonkeyPatch,
                                                                           stop: BaseException, calls: int) -> None:
    # Review 7, repair loop finding 2: the resume used to send a second patch, so the record read "patch" and its
    # latency summed two patch calls, a sequence the pipeline never runs.
    first = _analysis(*STEADY, ("cash", "comparison", WRONG))
    whole = _analysis(*STEADY, ("cash", "comparison", RIGHT))
    _wire(harness, monkeypatch, [json.dumps(first), '{"patches": []}', stop])
    if isinstance(stop, Killed):
        with pytest.raises(Killed):
            asyncio.run(harness.generate.run(LABEL, [ARM], [TICKER], 1, "v2"))
    else:
        asyncio.run(harness.generate.run(LABEL, [ARM], [TICKER], 1, "v2"))
    kept = json.loads(_path(harness).read_text())  # the paid patch call is on disk, the full repair owed
    assert kept["repair_owed"] == "full" and kept["repair_kind"] == "full" and kept["output"] == first and kept["repair_error"]
    assert [a["attempt"] for a in kept["attempts"]][:2] == [0, "repair"] and kept["attempts"][1]["problems"]
    sent = _wire(harness, monkeypatch, [json.dumps(whole)])
    asyncio.run(harness.generate.run(LABEL, [ARM], [TICKER], 1, "v2"))
    settled = json.loads(_path(harness).read_text())
    assert len(sent) == 1 and "Return the whole analysis again" in sent[0] and '"patches"' not in sent[0]
    assert not {"repair_error", "repair_owed"} & set(settled) and settled["repair_kind"] == "full"
    assert settled["output"] == whole and settled["gate"]["passed"] and len(settled["attempts"]) == calls
    assert settled["latency_s"] == pytest.approx(calls * 1.0) and settled["cost_usd"] == pytest.approx(calls * 0.1)


@pytest.mark.parametrize("path", ["patch", "full"])
def test_the_gate_after_a_repair_applies_the_backstops(harness: Any, monkeypatch: pytest.MonkeyPatch, path: str) -> None:
    first = _analysis(*STEADY, ("cash", "comparison", WRONG))
    signed = _analysis(*STEADY, ("cash", "comparison", SIGNED))
    repairs = [_patch(WRONG, type="comparison", text=SIGNED)] if path == "patch" else ['{"patches": []}', json.dumps(signed)]
    _wire(harness, monkeypatch, [json.dumps(first), *repairs])
    record = _generate(harness)
    assert record["repair_kind"] == path and record["output"] == signed and record["gate"]["passed"] is False
    assert [f["failure"][:13] for f in record["gate"]["failures"]] == ["backstop R2a:"] and record["gate"]["backstop_failures"] == 1


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


EDITED = ["Gross margin fell 3.9pp [D1][F4], so pricing power is weakening.",  # an ID added
          "Gross margin fell 3.9pp [D1], so pricing power is eroding."]  # a word changed


@pytest.mark.parametrize("text", EDITED)
@pytest.mark.parametrize("path", ["patch", "full"])
def test_a_retype_escape_fails_whatever_else_the_repair_edits(harness: Any, monkeypatch: pytest.MonkeyPatch, text: str, path: str) -> None:
    first = _analysis(*STEADY, ("cash", "cause", SO_CAUSE), ("cash", "fact", PASSED))
    retyped = _analysis(*STEADY, ("cash", "fact", text), ("cash", "fact", PASSED))
    repairs = [_patch(SO_CAUSE, type="fact", text=text)] if path == "patch" else ['{"patches": []}', json.dumps(retyped)]
    _wire(harness, monkeypatch, [json.dumps(first), *repairs])
    record = _generate(harness)
    assert record["repair_kind"] == path and record["output"] == retyped and not record["gate"]["passed"]
    assert record["gate"]["failures"] == [{"section": "cash", "sentence": text, "type": "fact",
                                           "failure": "retyped from cause without a passage but keeps its explanatory 'so' clause"}]


@pytest.mark.parametrize("kept", [[("cash", "fact", "Gross margin fell 3.9pp [D1][P1], so pricing power is weakening.")], []])
def test_a_full_repair_that_cites_the_causes_passage_or_deletes_it_passes(harness: Any, monkeypatch: pytest.MonkeyPatch,
                                                                         kept: list) -> None:
    first = _analysis(*STEADY, ("cash", "cause", SO_CAUSE), ("cash", "fact", PASSED))
    whole = _analysis(*STEADY, *kept, ("cash", "fact", PASSED))
    _wire(harness, monkeypatch, [json.dumps(first), '{"patches": []}', json.dumps(whole)])
    assert _generate(harness)["gate"]["passed"]


def test_version_1_runs_eval_v1s_procedure_under_the_current_gate(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    first = _analysis(*STEADY, ("cash", "comparison", UNCITED))
    whole = _analysis(*STEADY, ("cash", "comparison", UNCITED[:-1] + "[D2]."))
    sent = _wire(harness, monkeypatch, [json.dumps(first), json.dumps(whole)])
    real, gated = harness.generate.factcheck.check, []
    monkeypatch.setattr(harness.generate.factcheck, "check", lambda sentences, pack, **kw: gated.append(kw) or real(sentences, pack, **kw))
    record = _generate(harness, pipeline="v1")
    assert len(sent) == 2 and gated == [{}, {}]  # no code fix: the repair is sent, and the gate has no backstops
    assert sent[0] == "the pack"  # no nonce
    assert not {"pipeline", "nonce", "raw_first_pass_gate", "autocite", "retyped", "repair_kind"} & set(record)
    assert sent[1] == harness.generate.repair_message("the pack", first, record["first_pass_gate"]["failures"])
    assert "use the cited value exactly" in sent[1] and record["output"] == whole and record["gate"]["passed"]


def _owed(harness: Any, ticker: str = TICKER, **fields: Any) -> Path:
    """A first pass on disk, owed its repair, from this prompt and pack."""
    first = _analysis(*STEADY, ("cash", "comparison", WRONG))
    gate = harness.generate.factcheck.check(harness.generate.sentences_of(first), PACK, backstops=True)
    record = {"ticker": ticker, "arm": ARM, "generation_ok": True, "output": first, "gate": gate, "snapshot_id": "s1",
              "prompt_sha256": hashlib.sha256(b"the prompt").hexdigest(), "repair_error": "APIConnectionError",
              "attempts": [{"attempt": 0, "cost_usd": 0.2}], "usage": {"input_tokens": 1, "cached_input_tokens": 0,
              "output_tokens": 1, "reasoning_tokens": 0}, "latency_s": 1.0, "cost_usd": 0.2, **fields}
    path = _path(harness, ticker)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({k: v for k, v in record.items() if v is not None}))
    return path


def test_a_retried_repair_repeats_its_analysis_nonce(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    _owed(harness, pipeline="v2", nonce="0123456789ab")
    sent = _wire(harness, monkeypatch, [_patch(WRONG, type="comparison", text=RIGHT)])
    asyncio.run(harness.generate.run(LABEL, [ARM], [TICKER], 1, "v2"))
    record = json.loads(_path(harness).read_text())
    assert len(sent) == 1 and sent[0].startswith("Request 0123456789ab.\n\nthe pack") and '"patches"' in sent[0]
    assert "repair_error" not in record and record["repair_kind"] == "patch" and record["gate"]["passed"]


def test_a_retried_repair_puts_its_paid_patch_on_disk_before_the_full_repair(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _owed(harness, pipeline="v2", nonce="0123456789ab")
    _wire(harness, monkeypatch, ['{"patches": []}', Killed()])
    with pytest.raises(Killed):
        asyncio.run(harness.generate.run(LABEL, [ARM], [TICKER], 1, "v2"))
    kept = json.loads(path.read_text())
    assert kept["repair_error"].startswith("interrupted: the full repair") and [a["attempt"] for a in kept["attempts"]] == [0, "repair"]
    assert kept["cost_usd"] == pytest.approx(0.3)


@pytest.mark.parametrize("held, named", [
    ({"pipeline": None}, "test/deepseek-flash/U was made with pipeline v1, not v2"),
    ({"prompt_sha256": "0" * 64}, "test/deepseek-flash/U was made with prompt sha256 000000000000, not "),
    ({"pack_sha256": "f" * 64}, "test/deepseek-flash/U was made from evidence pack sha256 ffffffffffff of snapshot s1, not "),
    ({"snapshot_id": "s0"}, "of snapshot s0, not "),
])
def test_a_label_refuses_an_arm_made_another_way(harness: Any, monkeypatch: pytest.MonkeyPatch, held: dict[str, Any],
                                                 named: str) -> None:
    # Another company's record under the label, settled, of this arm: a retry of T must not add a second build.
    other = _owed(harness, "U", **{"pipeline": "v2", "nonce": "x", **held, "repair_error": None})
    owed = _owed(harness, pipeline="v2", nonce="0123456789ab")
    before = (other.read_text(), owed.read_text())
    sent = _wire(harness, monkeypatch, [])
    with pytest.raises(SystemExit, match=re.escape(named)):
        asyncio.run(harness.generate.run(LABEL, [ARM], [TICKER], 1, "v2"))
    assert sent == [] and (other.read_text(), owed.read_text()) == before


def test_a_failed_generation_does_not_hold_a_label_to_its_build(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    _owed(harness, generation_ok=False, error="RateLimitError", repair_error=None)  # made again, under this run's build
    sent = _wire(harness, monkeypatch, [json.dumps(_analysis(*STEADY))])
    asyncio.run(harness.generate.run(LABEL, [ARM], [TICKER], 1, "v2"))
    record = json.loads(_path(harness).read_text())
    assert len(sent) == 1 and record["pipeline"] == "v2" and record["gate"]["passed"] and record["prior_cost_usd"] == 0.2


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


FIRST_ATTEMPT = {"attempt": 0, "input_tokens": 30000, "cached_input_tokens": 0, "output_tokens": 1800, "cost_usd": 0.006}


def _recorded(harness: Any, source: str, ticker: str, first: dict[str, Any], **fields: Any) -> None:
    """A deepseek-flash record under ``runs/<source>/`` whose first pass is ``first``, made on the stub prompt."""
    path = harness.generate.RUNS / source / ARM / f"{ticker}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"ticker": ticker, "arm": ARM, "generation_ok": True, "output": first,
                                "prompt_sha256": hashlib.sha256(b"the prompt").hexdigest(), "attempts": [FIRST_ATTEMPT],
                                **fields}))


def _sources(harness: Any) -> dict[str, Any]:
    """eval-v1 holds a first pass that fails (A), one the code fixes make whole (B), one that passes as written (C) and
    a failed generation (D); dev-v3 a repaired record on an earlier prompt, whose first pass failed (E)."""
    failing = _analysis(*STEADY, ("cash", "comparison", WRONG), ("cash", "fact", PASSED))
    _recorded(harness, "eval-v1", "A", failing)
    _recorded(harness, "eval-v1", "B", _analysis(*STEADY, ("cash", "comparison", UNCITED)))
    _recorded(harness, "eval-v1", "C", _analysis(*STEADY))
    _recorded(harness, "eval-v1", "D", None, generation_ok=False)
    _recorded(harness, "dev-v3", "E", _analysis(*STEADY), first_pass_output=failing, prompt_sha256=None)
    return failing


def test_the_replay_takes_the_first_passes_version_2_would_repair(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    failing = _sources(harness)
    _wire(harness, monkeypatch, [])
    found, notes = harness.repair_replay.cases(["eval-v1", "dev-v3"])
    assert [case["name"] for case in found] == ["eval-v1__A", "dev-v3__E"]  # E's own first pass, not its repaired output
    assert notes == ["eval-v1/B: passes after the code fixes", "eval-v1/C: passes the gate as written"]
    record = found[1]["record"]
    assert record["output"] == failing and record["source"] == "dev-v3/deepseek-flash/E" and record["pipeline"] == "v2"
    assert record["first_pass_prompt_sha256"] is None and record["attempts"] == [] and record["cost_usd"] == 0
    assert [f["sentence"] for f in record["gate"]["failures"]] == [WRONG]
    assert [case["warm_prefix"] for case in found] == [30000, None]  # E's ticker has no first attempt on this prompt
    assert [case["name"] for case in harness.repair_replay.cases(["eval-v1", "dev-v3"], {"E"})[0]] == ["dev-v3__E"]


def test_the_replay_repairs_each_case_through_version_2s_repair(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    failing = _sources(harness)
    whole = _analysis(*STEADY, ("cash", "comparison", RIGHT), ("cash", "fact", "Gross margin was 71.1% [F4]."))
    # A repair's prompt is the first pass's (30,000 tokens, its first attempt's: the warm prefix) plus the failure
    # listing and the analysis, so it is longer than the prefix: 40,000 tokens here.
    replies = [_patch(WRONG, type="comparison", text=RIGHT), '{"patches": []}', json.dumps(whole)]
    sent = _wire(harness, monkeypatch, [CallResult(text, 40000, 0, 100, 0, 1.0, 0.1, "openai_compat", "m", {}) for text in replies])
    replay = harness.repair_replay
    found = [case for case in replay.cases(["eval-v1"])[0]]
    rows = asyncio.run(replay.replay("step1", found, 2, 1))
    assert len(sent) == 3 and all(m.startswith("the pack\n\nYour analysis was checked") for m in sent)  # no nonce
    patched, full = rows
    assert (patched["repair_kind"], patched["calls"], patched["gate_passed"], patched["untouched_kept"]) == ("patch", 1, True, [4, 4])
    assert (full["repair_kind"], full["calls"], full["gate_passed"], full["untouched_kept"]) == ("full", 2, True, [3, 4])
    assert full["latency_s"] == 2.0 and full["output_tokens"] == 200 and full["cost_usd"] == pytest.approx(0.2)
    # Warm, a call reads only the 30,000-token prefix from cache and pays full price for the other 10,000:
    # (10,000 x $0.15 + 30,000 x $0.003 + 100 x $0.60) per million = $0.00165 a call.
    assert patched["cost_warm_usd"] == pytest.approx(0.00165) and full["cost_warm_usd"] == pytest.approx(2 * 0.00165)
    written = harness.generate.RUNS / "step1" / "repair-replay" / "repeats"
    assert sorted(p.name for p in written.iterdir()) == ["eval-v1__A__1.json", "eval-v1__A__2.json"]
    assert json.loads((written / "eval-v1__A__1.json").read_text())["first_pass_output"] == failing
    # Latency on the report's basis (records.quantile, linear between the two nearest ranks, as §3's baselines): the
    # median of 1.0 s and 2.0 s is 1.5 s and the p90 1.9 s; a nearest rank read 1.0 s and 2.0 s.
    assert replay.summary(rows) == {"repeats": 2, "provider_errors": 0, "gate_passed": 2, "repair_failed": 0, "full_repairs": 1,
                                    "untouched_all_kept": 1, "latency_p50_s": 1.5, "latency_p90_s": 1.9,
                                    "cost_mean_usd": pytest.approx(0.15), "cost_warm_mean_usd": pytest.approx(1.5 * 0.00165)}


def test_the_replay_keeps_what_was_paid_for_and_retries_only_a_provider_error(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    failing = _sources(harness)
    _wire(harness, monkeypatch, ['{"patches": []}', Killed()])
    replay = harness.repair_replay
    found = replay.cases(["eval-v1"])[0]
    with pytest.raises(Killed):
        asyncio.run(replay.replay("step1", found, 1, 1))
    path = harness.generate.RUNS / "step1" / "repair-replay" / "repeats" / "eval-v1__A__1.json"
    kept = json.loads(path.read_text())  # the paid patch call is on disk before the full repair was sent
    assert kept["repair_error"].startswith("interrupted: the full repair") and [a["attempt"] for a in kept["attempts"]] == ["repair"]
    assert kept["repair_owed"] == "full"
    whole = json.loads(json.dumps(failing).replace(WRONG, RIGHT))
    sent = _wire(harness, monkeypatch, [json.dumps(whole)])
    rows = asyncio.run(replay.replay("step1", found, 1, 1))
    # The resumed repeat is bought only its owed full repair: it reads as the fallback it was, on the patch-then-full
    # basis of an uninterrupted one (two calls, both latencies), never as a patch.
    assert len(sent) == 1 and "Return the whole analysis again" in sent[0] and rows[0]["gate_passed"]
    assert (rows[0]["repair_kind"], rows[0]["calls"], rows[0]["latency_s"]) == ("full", 2, 2.0)
    assert rows[0]["cost_usd"] == pytest.approx(0.2) and replay.summary(rows)["full_repairs"] == 1
    sent = _wire(harness, monkeypatch, [])
    assert asyncio.run(replay.replay("step1", found, 1, 1)) == rows and sent == []  # a settled repeat is kept


def test_a_dry_run_sends_nothing(harness: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    _sources(harness)
    sent = _wire(harness, monkeypatch, [])
    harness.repair_replay.main(["--label", "step1", "--sources", "eval-v1,dev-v3", "--dry-run"])
    out = capsys.readouterr().out
    assert sent == [] and "2 cases, 4 repairs, at most 8 calls and USD " in out and "case eval-v1__A: 1 failure(s)" in out
    assert not (harness.generate.RUNS / "step1").exists()


def test_the_ceiling_is_two_cold_calls_a_repeat_each_at_max_tokens(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    _sources(harness)
    _wire(harness, monkeypatch, [])
    monkeypatch.setattr(harness.generate, "repair_message_v2",
                        lambda user, parsed, failures, pack, patch=True: "x" * (1000 if patch else 3000))
    found = harness.repair_replay.cases(["eval-v1"])[0]
    monkeypatch.setattr(harness.generate, "system_prompt", lambda arm_name: "s" * 20000)
    # One case. Per repeat: the patch request, 21,000 tokens in (the 20,000-byte system prompt and its 1,000-byte
    # message), and the full repair, 23,000; each reply 16,000 tokens (deepseek-flash's max_tokens), all cold at the
    # off-peak list price ($0.15 in and $0.60 out per million tokens): $0.0258 a repeat.
    assert harness.repair_replay.ceiling(found, 2) == (4, pytest.approx(2 * ((21000 + 23000) * 0.15 + 2 * 16000 * 0.60) / 1e6))


def test_these_tests_leave_the_real_bootstrap_unloaded() -> None:
    assert "evals.trend_depth.bootstrap" not in sys.modules
