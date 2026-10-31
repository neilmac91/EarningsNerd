"""The depth harness's shared rules over run records (evals/trend_depth/records.py).

Pins when a generation is final enough to audit or judge, and when one awaits only its repair (which the report counts
as not passing), the pipeline a record was made with (version 2 with auto-citation another build), the model's own
first output (a version-2 first pass carries the code's retyping), how an audit or a verdict is tied to the output it
read, when a first pass may be repaired or copied (only beside the prompt and the pack it read), and how the
report prices a company's first analysis from the recorded calls: a first request reads its model's and prompt's shared
prefix, what most first requests of that prompt read over every label, so neither a warm repeat nor a cold start moves it.
"""
from __future__ import annotations

import json
import sys
from typing import Any

import pytest

from evals.trend_depth.providers import ARMS, list_cost
from evals.trend_depth import records
from evals.trend_depth.records import (
    api_cost, excerpt, first_request_cache, labelled, output_sha256, pack_sha256, read_same_output, same_inputs, unsettled,
    write_json,
)


def _attempt(index: Any, backend: str, tokens: int, cached: int, output: int, write: int = 0) -> dict[str, Any]:
    return {"attempt": index, "backend": backend, "input_tokens": tokens, "cached_input_tokens": cached,
            "output_tokens": output, "cost_usd": 0.0, "meta": {"cache_creation_input_tokens": write}}


def test_a_record_waits_while_generate_still_owes_it_a_call() -> None:
    assert unsettled(None)
    assert unsettled({"generation_ok": False, "error": "RateLimitError"})
    assert unsettled({"generation_ok": True, "repair_error": "APIConnectionError"})
    assert unsettled({"generation_ok": True}) is None
    assert unsettled({"generation_ok": False}) is None  # the model's own failure is final: the judge records a forfeit


def test_a_record_awaiting_its_repair_is_one_whose_first_pass_stands() -> None:
    """Review 7 measures [1]: the report counts such a record as not passing, so only a repair still owed is one; a
    generation generate makes again after a provider error is not (it has no first pass yet)."""
    assert records.awaiting_repair({"generation_ok": True, "repair_error": "APIError: 503"})
    assert not records.awaiting_repair({"generation_ok": False, "error": "interrupted: the JSON retry had not returned",
                                        "repair_error": "a stale one"})
    assert not records.awaiting_repair({"generation_ok": True}) and not records.awaiting_repair(None)


def test_a_version_2_record_made_with_auto_citation_is_another_build() -> None:
    """Auto-citation (fix 1) was removed from version 2: a record made before carries ``autocite``, and a label, a copy
    and the report's builds must not take it for the version 2 of now."""
    assert records.pipeline_of({}) == "v1" and records.pipeline_of({"pipeline": "v2"}) == "v2"
    assert records.pipeline_of({"pipeline": "v2", "autocite": {"added": [], "rejected": 0}}) == "v2 with auto-citation"


def _analysis(text: str) -> dict[str, Any]:
    return {"sections": [{"key": "cash", "sentences": [{"type": "cause", "text": text}]}]}


def test_the_model_s_first_output_is_its_first_valid_reply_in_version_2() -> None:
    """Version 1 keeps the model's first pass as ``first_pass_output`` (its ``output`` when no repair ran). Version 2's
    ``first_pass_output`` and unrepaired ``output`` are the copy the code retyped, so the model's own first output is
    its last first-pass reply that parsed, never a repair's; none when no reply parses. The report's first-try
    measures, ``replay`` and ``retype``'s code-only replay read it here (review 9, repair-loop [0])."""
    own, retyped, repaired = _analysis("own"), _analysis("retyped"), _analysis("repaired")
    assert records.first_output({"output": own}) is own
    assert records.first_output({"output": repaired, "first_pass_output": own}) is own
    replies = [{"attempt": 0, "problems": ["not JSON"], "raw": "nonsense"}, {"attempt": 1, "problems": [], "raw": json.dumps(own)},
               {"attempt": "repair", "problems": [], "raw": json.dumps(repaired)}]
    v2 = {"pipeline": "v2", "output": repaired, "first_pass_output": retyped, "attempts": replies}
    assert records.first_output(v2) == own
    assert records.first_output({**v2, "attempts": replies[:1] + replies[2:]}) is None


def test_an_audit_is_tied_to_the_output_it_read() -> None:
    record = {"output": {"sections": [{"sentences": [{"text": "a"}]}]}, "gate": {"passed": False}}
    sha = output_sha256(record)
    assert output_sha256({**record, "gate": {"passed": True}}) == sha  # only what a reader reads counts
    assert output_sha256({**record, "output": {"sections": []}}) != sha
    assert read_same_output({"output_sha256": sha}, "output_sha256", sha)
    assert not read_same_output({"output_sha256": "an earlier output"}, "output_sha256", sha)
    assert read_same_output({}, "output_sha256", sha)  # written before outputs were hashed (eval-v1)


def test_a_first_pass_is_repaired_or_copied_only_beside_the_prompt_and_pack_it_read() -> None:
    pack = {"snapshot_id": "s1", "values": {"D1": {"value": 1.0}}}
    record = {"prompt_sha256": "p", "snapshot_id": "s1", "pack_sha256": pack_sha256(pack)}
    assert same_inputs(record, "p", pack)
    assert not same_inputs(record, "another prompt", pack)
    assert not same_inputs(record, "p", {**pack, "snapshot_id": "s2"})
    rebuilt = {**pack, "values": {**pack["values"], "D2": {"value": 2.0}}}  # new IDs over the same dataset
    assert rebuilt["snapshot_id"] == pack["snapshot_id"] and not same_inputs(record, "p", rebuilt)
    assert same_inputs({"prompt_sha256": "p", "snapshot_id": "s1"}, "p", rebuilt)  # eval-v1: no pack hash, all on packs/
    assert pack_sha256(dict(reversed(pack.items()))) == pack_sha256(pack)  # the pack's content, not its key order


def test_a_long_reply_keeps_its_head_and_its_tail() -> None:
    kept = excerpt("a" * 5000 + "b" * 5000)
    assert kept.startswith("a" * 4000) and kept.endswith("b" * 4000) and len(kept) < 10000
    assert excerpt("short") == "short"


def test_a_first_request_reads_only_the_shared_prefix_and_a_repair_keeps_its_hits() -> None:
    flash = ARMS["deepseek-flash"]
    first, repair = _attempt(0, "openai_compat", 40000, 30000, 2000), _attempt("repair", "openai_compat", 42000, 39000, 2500)
    records = [{"arm": "deepseek-flash", "attempts": [first, repair]},
               {"arm": "deepseek-flash", "attempts": [_attempt(0, "openai_compat", 38000, 1920, 2000)]}]
    shared = first_request_cache(records)
    assert shared == 1920  # one read each: the smaller, the system prompt every company shares
    assert api_cost(records[0], shared) == pytest.approx(list_cost(flash, 40000, 1920, 2000) + list_cost(flash, 42000, 39000, 2500))


def _firsts(reads: list[int], prompt: str = "d558d371", arm: str = "deepseek-flash", model: str = "") -> list[dict[str, Any]]:
    return [{"arm": arm, "prompt_sha256": prompt, **({"model": model} if model else {}),
             "attempts": [_attempt(0, "openai_compat", 36000, read, 2000)]} for read in reads]


# Recorded first-attempt reads of the frozen prompt (d558d371): eval-v1's deepseek-flash, whose five development
# companies dev-v4 had just run read their whole prompt, and dev-v4's, whose first three ran before the whole prompt was
# cached.
EVAL_V1 = [1920] * 15 + [29312, 33280, 34048, 36608, 40192]
DEV_V4 = [1024, 1024, 1024, 1920, 1920]


def test_the_shared_prefix_is_what_most_first_requests_read_over_every_label() -> None:
    assert first_request_cache(_firsts(EVAL_V1)) == first_request_cache(_firsts(DEV_V4 + EVAL_V1)) == 1920
    warm_repeat = _firsts([35000 + 64 * n for n in range(10)])  # a label re-sent while every prompt is still cached
    assert first_request_cache(warm_repeat) == 35000  # alone, a warm label would price itself at its least read
    assert records.shared_prefixes([*_firsts(DEV_V4 + EVAL_V1), *warm_repeat]) == {"deepseek-flash d558d371": 1920}
    cold_start = _firsts([0, 0, 0] + [2048] * 7, prompt="candidate")  # a new prompt: its first requests find nothing cached
    assert records.shared_prefixes(cold_start) == {"deepseek-flash candidate": 2048}
    assert first_request_cache(_firsts([1920, 1024])) == 1024  # a tie: the smaller, never crediting a hit not read


def test_the_shared_prefix_is_kept_per_model_and_prompt() -> None:
    """K0 and P share the frozen prompt and the model, so their first requests share a cache; another model's (a Gemini
    arm on the frozen prompt) and a prompt without a hash (dev-v3) do not join it."""
    shared = records.shared_prefixes([*_firsts([1920] * 3), *_firsts([1920] * 2, arm="deepseek-flash-p"),
                                      *_firsts([0] * 9, arm="gemini-3.8-flash", model="gemini-3.8-flash"),
                                      {"arm": "deepseek-flash", "attempts": [_attempt(0, "openai_compat", 36000, 384, 2000)]}])
    assert shared == {"deepseek-flash d558d371": 1920, "gemini-3.8-flash d558d371": 0}


def test_a_warm_first_attempt_is_counted_and_priced_as_the_prefix() -> None:
    flash = ARMS["deepseek-flash"]
    firsts = _firsts(EVAL_V1)
    assert records.warm_first_attempts(firsts, lambda record: 1920) == (5, 20)
    assert api_cost(firsts[-1], 1920) == pytest.approx(list_cost(flash, 36000, 1920, 2000))


def test_claude_cli_calls_read_nothing_from_cache_and_api_calls_are_priced_as_billed() -> None:
    sonnet = ARMS["claude-sonnet-5-5"]
    cli = {"arm": "claude-sonnet-5-5", "attempts": [_attempt("repair", "claude_cli", 60000, 50000, 8000, write=10000)]}
    assert api_cost(cli, shared_cache=50000) == pytest.approx(list_cost(sonnet, 60000, 0, 8000))  # even a repair
    api = {"arm": "claude-sonnet-5-5", "attempts": [_attempt(0, "anthropic", 60000, 0, 8000, write=60000)]}
    assert api_cost(api) == pytest.approx(list_cost(sonnet, 60000, 0, 8000, 60000))
    assert first_request_cache([api]) == 0  # only an OpenAI-compatible first request sets the shared prefix


def test_a_claude_api_call_adds_the_attempts_cut_before_it_once() -> None:
    """providers records a cut attempt's worst case as ``cut_cost_usd`` beside the reply's own tokens, or with none
    when the call then failed: the tokens are repriced and the cut is added, so neither is counted twice."""
    sonnet = ARMS["claude-sonnet-5-5"]
    reply = {**_attempt(0, "anthropic", 1000, 0, 10), "meta": {"cache_creation_input_tokens": 0, "cut_cost_usd": 0.162}}
    failed = {**_attempt("repair", "anthropic", 0, 0, 0), "meta": {"stop_reason": "cut short", "cut_cost_usd": 0.324}}
    assert api_cost({"arm": "claude-sonnet-5-5", "attempts": [reply]}) == pytest.approx(list_cost(sonnet, 1000, 0, 10) + 0.162)
    assert api_cost({"arm": "claude-sonnet-5-5", "attempts": [reply, failed]}) == pytest.approx(0.1641 + 0.324)


def test_a_failed_generation_a_record_replaced_still_counts() -> None:
    sonnet = ARMS["claude-sonnet-5-5"]
    record = {"arm": "claude-sonnet-5-5", "prior_attempts": [_attempt(0, "anthropic", 60000, 0, 64000)],
              "attempts": [_attempt(0, "anthropic", 60000, 0, 8000)]}
    assert api_cost(record) == pytest.approx(list_cost(sonnet, 60000, 0, 64000) + list_cost(sonnet, 60000, 0, 8000))
    assert api_cost({"arm": "current", "cost_usd": 0.0002}) == 0.0002  # production records carry their own cost


def test_only_a_label_for_an_item_asked_about_counts() -> None:
    assert labelled([{"n": 1, "verdict": "supported"}], 1) == {}  # a wrong field name labels nothing
    assert labelled([{"n": 0, "label": "supported"}, {"n": 2, "label": "partial"}], 1) == {}  # numbered from 0
    assert labelled([{"n": 1, "label": " "}, {"n": "2.", "label": "partial"}], 2) == {2: {"n": "2.", "label": "partial"}}
    # Numbered from 0 for three items: accepting n=1 and n=2 would put each label on the wrong item.
    assert labelled([{"n": 0, "label": "supported"}, {"n": 1, "label": "unsupported"}, {"n": 2, "label": "partial"}], 3) == {}
    assert labelled([{"n": 1, "label": "supported"}, {"n": 4, "label": "partial"}], 3) == {}  # an item never asked about


def test_a_record_is_written_whole_or_not_at_all(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    path = tmp_path / "runs" / "T.json"
    write_json(path, {"cost_usd": 0.1})
    assert json.loads(path.read_text()) == {"cost_usd": 0.1}

    def killed(source: str, target: str) -> None:
        raise KeyboardInterrupt  # the process stops between writing and renaming

    monkeypatch.setattr(records.os, "replace", killed)
    with pytest.raises(KeyboardInterrupt):
        write_json(path, {"cost_usd": 0.2})
    assert json.loads(path.read_text()) == {"cost_usd": 0.1}  # the earlier record, whole
    assert [p.name for p in path.parent.iterdir()] == ["T.json"]  # and no temporary file left behind


def test_these_tests_never_load_the_harness_bootstrap() -> None:
    # bootstrap rewrites DATABASE_URL and the AI settings for the process; it must stay out of the test session.
    assert "evals.trend_depth.bootstrap" not in sys.modules
