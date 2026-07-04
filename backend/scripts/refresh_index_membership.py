#!/usr/bin/env python3
"""Regenerate the committed index-membership list (S&P 500 ∪ Nasdaq 100).

This is the maintenance tool behind the earnings-calendar universe filter. The *served* universe
is the committed ``backend/app/data/index_membership.json`` — this script only regenerates that
file, and a human reviews the diff in a PR before it ships. That keeps the calendar's universe
auditable and impossible to corrupt from a bad/empty API response at runtime.

Source precedence:
  1. FMP  (``FMP_API_KEY`` set)  — /sp500_constituent + /nasdaq_constituent (clean JSON; prod path).
  2. Wikipedia (keyless fallback) — the "List of S&P 500 companies" and "Nasdaq-100" tables.

Safety: a fetch that yields fewer than ``SANITY_FLOOR`` unique tickers ABORTS without writing, so a
provider hiccup can never truncate the committed list.

Usage:
    python scripts/refresh_index_membership.py            # regenerate + write, print diff
    python scripts/refresh_index_membership.py --check     # dry-run: print diff, write nothing
    python scripts/refresh_index_membership.py --source wikipedia
"""
from __future__ import annotations

import argparse
import io
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import httpx

logger = logging.getLogger(__name__)

# ~525 unique across both indexes; abort below this so a failed parse never writes a stub list.
SANITY_FLOOR = 450

# Tickers Wikipedia pre-lists for announced-but-not-yet-trading spin-offs (e.g. FedEx Freight,
# Honeywell Aerospace). They can never match an Alpha Vantage earnings event because they don't
# trade, so they're harmless to the filter — but we drop them to keep the committed universe clean
# and auditable. Remove an entry here once it actually begins trading and is index-listed.
NONTRADING_ARTIFACTS = {"FDXF", "HONA"}

# Wikipedia 403s the default httpx UA; a descriptive UA per their bot policy gets a 200.
_WIKI_UA = "EarningsNerd/1.0 (https://earningsnerd.io; contact@earningsnerd.io) python-httpx"
_SP500_WIKI = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
_NASDAQ100_WIKI = "https://en.wikipedia.org/wiki/Nasdaq-100"
_FMP_BASE = "https://financialmodelingprep.com/api/v3"

_DATA_PATH = Path(__file__).resolve().parents[1] / "app" / "data" / "index_membership.json"


def normalize_ticker(raw: str) -> str:
    """Canonical form used on both sides of the membership comparison.

    Alpha Vantage (the calendar's ticker source) writes dual classes with a DOT — ``BRK.B``,
    ``BF.B`` — while FMP writes a DASH (``BRK-B``). Canonicalizing ``-`` → ``.`` makes the stored
    list source-agnostic and match AV's events. Upper + strip handles the rest.
    """
    return (raw or "").strip().upper().replace("-", ".")


# --------------------------------------------------------------------------- FMP source

def _fetch_fmp(path: str, api_key: str) -> List[dict]:
    url = f"{_FMP_BASE}/{path}"
    resp = httpx.get(url, params={"apikey": api_key}, timeout=20.0)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list):
        raise ValueError(f"FMP {path} returned {type(data).__name__}, expected list")
    return data


def fetch_fmp(api_key: str) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Return ({sp500 ticker->name}, {nasdaq100 ticker->name}) from FMP."""
    def to_map(rows: List[dict]) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for r in rows:
            sym = normalize_ticker(str(r.get("symbol", "")))
            if sym:
                out[sym] = str(r.get("name") or r.get("companyName") or "").strip()
        return out

    sp = to_map(_fetch_fmp("sp500_constituent", api_key))
    nd = to_map(_fetch_fmp("nasdaq_constituent", api_key))
    return sp, nd


# --------------------------------------------------------------------------- Wikipedia source

def _read_wiki_table(url: str, symbol_cols: Tuple[str, ...]) -> Dict[str, str]:
    """Fetch a Wikipedia page and return {ticker -> name} from its constituents table.

    Picks the first table that has a symbol/ticker column and a plausible row count (>50), so a
    layout change that reorders tables doesn't silently grab the wrong one.
    """
    import pandas as pd

    html = httpx.get(url, headers={"User-Agent": _WIKI_UA}, timeout=25.0, follow_redirects=True)
    html.raise_for_status()
    tables = pd.read_html(io.StringIO(html.text))
    for table in tables:
        cols = {str(c).strip().lower(): c for c in table.columns}
        sym_col = next((cols[s.lower()] for s in symbol_cols if s.lower() in cols), None)
        if sym_col is None or len(table) <= 50:
            continue
        name_col = next(
            (cols[n] for n in ("security", "company", "company name") if n in cols), None
        )
        out: Dict[str, str] = {}
        for _, r in table.iterrows():
            sym = normalize_ticker(str(r[sym_col]))
            if sym and sym.lower() != "nan":
                out[sym] = str(r[name_col]).strip() if name_col is not None else ""
        if out:
            return out
    raise ValueError(f"no constituents table found at {url}")


def fetch_wikipedia() -> Tuple[Dict[str, str], Dict[str, str]]:
    sp = _read_wiki_table(_SP500_WIKI, ("Symbol", "Ticker"))
    nd = _read_wiki_table(_NASDAQ100_WIKI, ("Ticker", "Symbol"))
    return sp, nd


# --------------------------------------------------------------------------- build + write

def build_entries(sp500: Dict[str, str], nasdaq100: Dict[str, str]) -> List[dict]:
    """Merge the two maps into sorted entries with an ``indices`` list per ticker."""
    entries: Dict[str, dict] = {}
    for tickers, label in ((sp500, "sp500"), (nasdaq100, "nasdaq100")):
        for sym, name in tickers.items():
            if sym in NONTRADING_ARTIFACTS:
                continue
            e = entries.setdefault(sym, {"ticker": sym, "name": name, "indices": []})
            if name and not e["name"]:
                e["name"] = name
            if label not in e["indices"]:
                e["indices"].append(label)
    for e in entries.values():
        e["indices"].sort()
    return [entries[k] for k in sorted(entries)]


def _load_existing(path: Path) -> List[dict]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text()).get("members", [])
    except Exception:
        return []


def _print_diff(old: List[dict], new: List[dict]) -> None:
    old_t = {e["ticker"] for e in old}
    new_t = {e["ticker"] for e in new}
    added = sorted(new_t - old_t)
    removed = sorted(old_t - new_t)
    logger.info("current committed: %d  regenerated: %d", len(old_t), len(new_t))
    logger.info("added (%d): %s", len(added), ", ".join(added) or "-")
    logger.info("removed (%d): %s", len(removed), ", ".join(removed) or "-")


def run(source: str, *, check: bool, path: Path = _DATA_PATH) -> int:
    api_key = os.environ.get("FMP_API_KEY", "") or ""
    use_fmp = source == "fmp" or (source == "auto" and api_key)
    if use_fmp and not api_key:
        logger.error("source=fmp but FMP_API_KEY is unset")
        return 2
    try:
        sp500, nasdaq100 = fetch_fmp(api_key) if use_fmp else fetch_wikipedia()
    except Exception as exc:  # noqa: BLE001 - degrade with a clear message, never half-write
        logger.error("fetch failed (%s): %s", "fmp" if use_fmp else "wikipedia", exc)
        return 2

    entries = build_entries(sp500, nasdaq100)
    logger.info(
        "fetched via %s: sp500=%d nasdaq100=%d union=%d",
        "fmp" if use_fmp else "wikipedia", len(sp500), len(nasdaq100), len(entries),
    )
    if len(entries) < SANITY_FLOOR:
        logger.error(
            "ABORT: %d unique tickers < sanity floor %d — refusing to write a truncated list",
            len(entries), SANITY_FLOOR,
        )
        return 1

    _print_diff(_load_existing(path), entries)
    if check:
        logger.info("--check: no file written")
        return 0

    payload = {
        "_comment": "Generated by scripts/refresh_index_membership.py. S&P 500 ∪ Nasdaq 100. "
                    "Review diffs in PRs; do not hand-edit casually. Tickers are AV/dot format.",
        "source": "fmp" if use_fmp else "wikipedia",
        "count": len(entries),
        "members": entries,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    logger.info("wrote %d members -> %s", len(entries), path)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate the committed index-membership list.")
    parser.add_argument("--source", choices=("auto", "fmp", "wikipedia"), default="auto")
    parser.add_argument("--check", action="store_true", help="dry-run: print diff, write nothing")
    args = parser.parse_args()
    return run(args.source, check=args.check)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    sys.exit(main())
