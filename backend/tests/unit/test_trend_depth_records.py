"""The depth harness's shared rules over run records (evals/trend_depth/records.py).

Pins when a generation is final enough to audit or judge, how an audit or a verdict is tied to the output it
read, and how the report prices a company's first analysis from the recorded calls.
"""
from __future__ import annotations

import json
import sys
from typing import Any

import pytest

from evals.trend_depth.providers import ARMS, list_cost
from evals.trend_depth import records
from evals.trend_depth.records import (
    api_cost, excerpt, first_request_cache, labelled, output_sha256, read_same_output, unsettled, write_json,
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


def test_an_audit_is_tied_to_the_output_it_read() -> None:
    record = {"output": {"sections": [{"sentences": [{"text": "a"}]}]}, "gate": {"passed": False}}
    sha = output_sha256(record)
    assert output_sha256({**record, "gate": {"passed": True}}) == sha  # only what a reader reads counts
    assert output_sha256({**record, "output": {"sections": []}}) != sha
    assert read_same_output({"output_sha256": sha}, "output_sha256", sha)
    assert not read_same_output({"output_sha256": "an earlier output"}, "output_sha256", sha)
    assert read_same_output({}, "output_sha256", sha)  # written before outputs were hashed (eval-v1)


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
    assert shared == 1920  # the least any first request read: the system prompt every company shares
    assert api_cost(records[0], shared) == pytest.approx(list_cost(flash, 40000, 1920, 2000) + list_cost(flash, 42000, 39000, 2500))


def test_claude_cli_calls_read_nothing_from_cache_and_api_calls_are_priced_as_billed() -> None:
    sonnet = ARMS["claude-sonnet-5-5"]
    cli = {"arm": "claude-sonnet-5-5", "attempts": [_attempt("repair", "claude_cli", 60000, 50000, 8000, write=10000)]}
    assert api_cost(cli, shared_cache=50000) == pytest.approx(list_cost(sonnet, 60000, 0, 8000))  # even a repair
    api = {"arm": "claude-sonnet-5-5", "attempts": [_attempt(0, "anthropic", 60000, 0, 8000, write=60000)]}
    assert api_cost(api) == pytest.approx(list_cost(sonnet, 60000, 0, 8000, 60000))
    assert first_request_cache([api]) == 0  # only an OpenAI-compatible first request sets the shared prefix


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
