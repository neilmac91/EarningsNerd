"""The universe regeneration script must never write a partial (S&P-500-only) list.

Automatic refresh uses the two public constituent lists even when an FMP key is present.
An unavailable or truncated half must leave the committed file untouched; runtime fail-open
behavior cannot compensate for a plausible but partial list that hides Nasdaq-only names.
"""
import json
from datetime import date
from html import escape
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


def test_public_fetch_failure_preserves_existing_file(monkeypatch, tmp_path: Path, caplog):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    monkeypatch.setattr(script, "_read_wiki_table", _fake_wiki_table)
    target = tmp_path / "index_membership.json"
    target.write_bytes(b"existing reviewed file")

    rc = script.run("auto", check=False, path=target)

    assert rc == 2
    assert target.read_bytes() == b"existing reviewed file", "a failed refresh must preserve prior bytes"
    assert script._NASDAQ100_WIKI in caplog.text and "Nasdaq-100" in caplog.text


def test_explicit_wikipedia_source_also_refuses_partial_list(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(script, "_read_wiki_table", _fake_wiki_table)
    target = tmp_path / "index_membership.json"
    assert script.run("wikipedia", check=False, path=target) == 2
    assert not target.exists()


def test_fmp_uses_stable_endpoints_and_parses_row_shape(monkeypatch, tmp_path: Path):
    """Explicit FMP compatibility still uses stable routes and the documented row shape."""
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
    missing/short half on the explicit FMP path too."""
    monkeypatch.setenv("FMP_API_KEY", "test-key")
    monkeypatch.setattr(script, "fetch_fmp", lambda api_key: (dict(sp500), dict(nasdaq)))
    target = tmp_path / "index_membership.json"

    assert script.run("fmp", check=False, path=target) == 2
    assert not target.exists()


def test_wikipedia_path_refuses_short_nasdaq_table(monkeypatch, tmp_path: Path):
    """A Nasdaq-100 table that parses but is implausibly small (layout change) is also partial."""
    def short_nasdaq(url, symbol_cols):
        return dict(_SP500) if url == script._SP500_WIKI else {"AAPL": "Apple", "MSFT": "Microsoft"}

    monkeypatch.setattr(script, "_read_wiki_table", short_nasdaq)
    target = tmp_path / "index_membership.json"
    assert script.run("wikipedia", check=False, path=target) == 2
    assert not target.exists()


def test_auto_parses_both_public_lists_without_using_fmp_credentials(monkeypatch, tmp_path: Path):
    """Exercise real HTML parsing/normalization and check mode across absent and present keys."""
    sp500 = {**_SP500, "BRK-B": "Berkshire Hathaway", "BF.B": "Brown–Forman",
             "FDXF": "FedEx Freight", "HONA": "Honeywell Aerospace"}

    def table(symbol_header, name_header, members):
        # Observed dedicated-list schemas: Symbol/Security and Ticker/Company. Navigation
        # tables can precede the constituents, and cell markup must survive real parsing.
        rows = "".join(
            f"<tr><td><a>{escape(ticker)}</a></td><td>{escape(name)}</td></tr>"
            for ticker, name in members.items()
        )
        return (
            "<table><tr><th>Navigation</th></tr><tr><td>Index</td></tr></table>"
            f"<table><tr><th>{symbol_header}</th><th>{name_header}</th></tr>{rows}</table>"
        )

    urls = {
        "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies": table("Symbol", "Security", sp500),
        "https://en.wikipedia.org/wiki/List_of_NASDAQ-100_companies": table("Ticker", "Company", _NASDAQ),
    }
    calls = []

    def fake_get(url, *, headers, timeout, follow_redirects):
        calls.append(url)
        assert "apikey" not in url and "Authorization" not in headers
        response = _FakeResponse(None)
        response.text = urls[url]
        return response

    monkeypatch.setattr(script.httpx, "get", fake_get)
    for api_key in (None, "unused-test-key"):
        if api_key is None:
            monkeypatch.delenv("FMP_API_KEY", raising=False)
        else:
            monkeypatch.setenv("FMP_API_KEY", api_key)
        target = tmp_path / f"index-membership-{api_key is not None}.json"
        assert script.run("auto", check=False, path=target) == 0
        payload = json.loads(target.read_text(encoding="utf-8"))
        assert payload["source"] == "wikipedia"
        assert payload["source_urls"] == dict(zip(("sp500", "nasdaq100"), urls))
        assert date.fromisoformat(payload["generated_on"])
        by_ticker = {m["ticker"]: m for m in payload["members"]}
        assert by_ticker["BRK.B"]["name"] == "Berkshire Hathaway"
        assert by_ticker["BF.B"]["name"] == "Brown–Forman"
        assert by_ticker["AAPL"]["indices"] == ["nasdaq100", "sp500"]
        assert by_ticker["MELI"]["indices"] == ["nasdaq100"]
        assert {"FDXF", "HONA"} <= by_ticker.keys()
        assert payload["count"] == len(by_ticker) == len(set(sp500) | set(_NASDAQ))
        target.write_bytes(b"existing reviewed file")
        assert script.run("auto", check=True, path=target) == 0
        assert target.read_bytes() == b"existing reviewed file"
    assert calls == list(urls) * 4
