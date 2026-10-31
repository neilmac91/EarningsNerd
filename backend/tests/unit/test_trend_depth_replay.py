"""The depth harness's gate replay (evals/trend_depth/replay.py) over run records.

Pins that every recorded output is re-checked against the pack its system reads (``packs-v2/`` for the ``-p`` and
``-c`` arms, which cite IDs only version 2 has), and that a version-2 record's first pass is the model's own first
reply, before the code's retyping (and the auto-citation of a record made before it was removed). replay is imported over a stub bootstrap whose records live in
``tmp_path`` (the stage tests' pattern), so the real bootstrap never loads and git is never read.
"""
from __future__ import annotations

import importlib
import json
import sys
import types
from pathlib import Path
from typing import Any

import pytest

from evals.trend_depth.providers import packs_dir

LABEL, TICKER = "test", "T"
MODULES = ("generate", "judge", "causes", "semantics", "report", "gold", "replay")


@pytest.fixture
def replay(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    stub = types.ModuleType("evals.trend_depth.bootstrap")
    stub.RECORDS = tmp_path
    stub.BACKEND = Path(__file__).resolve().parents[2]
    stub.REPO = stub.BACKEND.parent
    stub.PRODUCTION_MODEL = "stub"
    monkeypatch.setitem(sys.modules, "evals.trend_depth.bootstrap", stub)
    for name in MODULES:
        monkeypatch.delitem(sys.modules, f"evals.trend_depth.{name}", raising=False)
    yield importlib.import_module("evals.trend_depth.replay")
    for name in [n for n in sys.modules if n.split(".")[-1] in MODULES and n.startswith("evals.trend_depth.")]:
        del sys.modules[name]  # the next test imports them afresh, over its own records


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def _output(text: str) -> dict[str, Any]:
    return {"sections": [{"key": "arc", "sentences": [{"text": text, "type": "fact"}]}]}


def test_every_system_is_replayed_against_its_own_pack_and_first_reply(replay: Any, tmp_path: Path) -> None:
    for system in ("deepseek-flash", "deepseek-flash-c"):  # packs/ and packs-v2/, each naming its directory
        folder = packs_dir(system, tmp_path)
        _write(folder / f"{TICKER}.json", {"dir": folder.name, "values": {}, "passages": [], "red_flags": []})
    own = _output("Revenue was $1.0 billion [F1].")
    fixed = _output("Revenue was $1.0 billion [F1][D9].")  # what the code step made of it (auto-citation, before its removal)
    runs = tmp_path / "runs" / LABEL
    _write(runs / "deepseek-flash" / f"{TICKER}.json", {"ticker": TICKER, "output": own})
    _write(runs / "deepseek-flash-c" / f"{TICKER}.json", {
        "ticker": TICKER, "pipeline": "v2", "output": fixed, "first_pass_output": fixed,
        "attempts": [{"attempt": 0, "raw": json.dumps(own), "problems": []}]})
    replayed = {system: (pack["dir"], final, first) for _, system, _, pack, final, first in replay.records([LABEL])}
    assert replayed["deepseek-flash"] == ("packs", replay.sentences_of(own), None)
    assert replayed["deepseek-flash-c"] == ("packs-v2", replay.sentences_of(fixed), replay.sentences_of(own))
