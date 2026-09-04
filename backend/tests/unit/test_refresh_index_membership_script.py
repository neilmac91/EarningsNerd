"""The universe regeneration script must never write a partial (S&P-500-only) list.

Wikipedia's Nasdaq-100 article no longer carries a constituents table, so a keyless run can only
fetch the S&P 500 half. The script must exit 2 with an actionable message and leave the committed
file untouched — the calendar's universe is "S&P 500 ∪ Nasdaq 100" or nothing (fail-open at runtime
serves everything; a silently partial list would hide ~100 Nasdaq-only names instead).
"""
import json
from datetime import date
from pathlib import Path

import pytest

from scripts import refresh_index_membership as script

_SP500 = {f"T{i:03d}": f"Company {i}" for i in range(505)} | {"AAPL": "Apple", "MSFT": "Microsoft"}
_NASDAQ = {"AAPL": "Apple", "ASML": "ASML", "MELI": "MercadoLibre"}


def _fake_wiki_table(url: str, symbol_cols):
    if url == script._SP500_WIKI:
        return dict(_SP500)
    raise ValueError(f"no constituents table found at {url}")


def test_keyless_run_aborts_with_exit_2_and_writes_nothing(monkeypatch, tmp_path: Path, caplog):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    monkeypatch.setattr(script, "_read_wiki_table", _fake_wiki_table)
    target = tmp_path / "index_membership.json"

    rc = script.run("auto", check=False, path=target)

    assert rc == 2
    assert not target.exists(), "a partial universe must never be written"
    assert "FMP_API_KEY" in caplog.text and "Nasdaq-100" in caplog.text


def test_explicit_wikipedia_source_also_refuses_partial_list(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(script, "_read_wiki_table", _fake_wiki_table)
    target = tmp_path / "index_membership.json"
    assert script.run("wikipedia", check=False, path=target) == 2
    assert not target.exists()


def test_auto_prefers_fmp_when_key_is_set_and_stamps_generated_on(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("FMP_API_KEY", "test-key")
    monkeypatch.setattr(script, "fetch_fmp", lambda api_key: (dict(_SP500), dict(_NASDAQ)))
    monkeypatch.setattr(
        script, "_read_wiki_table",
        lambda *a, **k: pytest.fail("auto mode must not touch Wikipedia when FMP_API_KEY is set"),
    )
    target = tmp_path / "index_membership.json"

    assert script.run("auto", check=False, path=target) == 0

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["source"] == "fmp"
    assert date.fromisoformat(payload["generated_on"])  # ISO date the age gate can parse
    labels = {i for m in payload["members"] for i in m["indices"]}
    assert labels == {"sp500", "nasdaq100"}
    assert payload["count"] == len(payload["members"]) == len(set(_SP500) | set(_NASDAQ))
