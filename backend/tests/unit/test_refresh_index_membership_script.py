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
_NASDAQ = {f"N{i:03d}": f"Nasdaq Co {i}" for i in range(98)} | {"AAPL": "Apple", "ASML": "ASML", "MELI": "MercadoLibre"}


def _stable_rows(tickers: dict) -> list[dict]:
    """Row shape of FMP's stable ``/sp500-constituent`` and ``/nasdaq-constituent`` responses."""
    return [
        {"symbol": t, "name": n, "sector": "Technology", "subSector": "Semis", "headQuarter": "X",
         "dateFirstAdded": "2020-01-01", "cik": "0000000001", "founded": "1990"}
        for t, n in tickers.items()
    ]


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


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


def test_fmp_uses_stable_endpoints_and_parses_row_shape(monkeypatch, tmp_path: Path):
    """The legacy /api/v3 sp500_constituent endpoints were cut off 2026-07-03; the script must call
    the stable API and read its row shape. Live verification = the founder's first keyed run."""
    calls: list[tuple[str, dict]] = []
    payloads = {
        f"{script._FMP_BASE}/sp500-constituent": _stable_rows({"AAPL": "Apple Inc.", "BRK-B": "Berkshire", **_SP500}),
        f"{script._FMP_BASE}/nasdaq-constituent": _stable_rows(_NASDAQ),
    }

    def fake_get(url, params=None, timeout=None):
        calls.append((url, params or {}))
        return _FakeResponse(payloads[url])

    monkeypatch.setattr(script.httpx, "get", fake_get)
    monkeypatch.setenv("FMP_API_KEY", "test-key")
    target = tmp_path / "index_membership.json"

    assert script.run("fmp", check=False, path=target) == 0

    assert [u for u, _ in calls] == [
        "https://financialmodelingprep.com/stable/sp500-constituent",
        "https://financialmodelingprep.com/stable/nasdaq-constituent",
    ]
    assert all(p == {"apikey": "test-key"} for _, p in calls)
    by_ticker = {m["ticker"]: m for m in json.loads(target.read_text(encoding="utf-8"))["members"]}
    assert by_ticker["BRK.B"]["name"] == "Berkshire"  # dash -> dot normalization survives
    assert by_ticker["AAPL"]["indices"] == ["nasdaq100", "sp500"]


@pytest.mark.parametrize(
    ("sp500", "nasdaq"),
    [
        (_SP500, {}),                                   # empty Nasdaq-100 response
        (_SP500, dict(list(_NASDAQ.items())[:40])),     # truncated Nasdaq-100
        (dict(list(_SP500.items())[:300]), _NASDAQ),    # truncated S&P 500
    ],
)
def test_fmp_path_refuses_partial_universe(monkeypatch, tmp_path: Path, sp500, nasdaq):
    """The union floor is satisfied by the S&P 500 alone, so the per-index floors must catch a
    missing/short half on the FMP path too — not just Wikipedia's dead Nasdaq-100 table."""
    monkeypatch.setenv("FMP_API_KEY", "test-key")
    monkeypatch.setattr(script, "fetch_fmp", lambda api_key: (dict(sp500), dict(nasdaq)))
    target = tmp_path / "index_membership.json"

    assert script.run("auto", check=False, path=target) == 2
    assert not target.exists()


def test_wikipedia_path_refuses_short_nasdaq_table(monkeypatch, tmp_path: Path):
    """A Nasdaq-100 table that parses but is implausibly small (layout change) is also partial."""
    def short_nasdaq(url, symbol_cols):
        return dict(_SP500) if url == script._SP500_WIKI else {"AAPL": "Apple", "MSFT": "Microsoft"}

    monkeypatch.setattr(script, "_read_wiki_table", short_nasdaq)
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
