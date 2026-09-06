#!/usr/bin/env python3
"""Regenerate the committed index-membership list (S&P 500 ∪ Nasdaq 100).

This is the maintenance tool behind the earnings-calendar universe filter. The *served* universe
is the committed ``backend/app/data/index_membership.json`` — this script only regenerates that
file, and a human reviews the diff in a PR before it ships. That keeps the calendar's universe
auditable and impossible to corrupt from a bad/empty API response at runtime.

Sources:
  - ``--source auto`` (the workflow default) and ``--source wikipedia`` use the public
    "List of S&P 500 companies" and "List of NASDAQ-100 companies" tables without credentials.
    The dedicated Nasdaq list is separate from the general "Nasdaq-100" article.
  - ``--source fmp`` explicitly selects the stable-API /sp500-constituent + /nasdaq-constituent
    routes and requires ``FMP_API_KEY``. A supplied key never changes the automatic source.

Safety: EVERY source must deliver both halves at plausible size (S&P 500 >= ``SP500_FLOOR``,
Nasdaq-100 >= ``NASDAQ100_FLOOR``) and the union must clear ``SANITY_FLOOR``, else the run ABORTS
without writing — a provider hiccup or an empty index response can never truncate the committed
list or drop one index. The written file carries ``generated_on`` (UTC date), stamped on every run
so the monthly workflow PR doubles as a heartbeat; ``tests/unit/test_index_membership_service.py``
fails once that date is >100 days old.

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
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import httpx

logger = logging.getLogger(__name__)

# ~525 unique across both indexes; abort below this so a failed parse never writes a stub list.
SANITY_FLOOR = 450
# Per-index floors: the union floor alone is satisfied by the S&P 500 by itself, so an empty or
# truncated Nasdaq-100 response would otherwise pass and silently ship an S&P-only universe.
# S&P 500 holds ~503 tickers (dual classes); the Nasdaq-100 ~101.
SP500_FLOOR = 480
NASDAQ100_FLOOR = 90

# Wikipedia 403s the default httpx UA; a descriptive UA per their bot policy gets a 200.
_WIKI_UA = "EarningsNerd/1.0 (https://earningsnerd.io; contact@earningsnerd.io) python-httpx"
_SP500_WIKI = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
_NASDAQ100_WIKI = "https://en.wikipedia.org/wiki/List_of_NASDAQ-100_companies"
# FMP "stable" API. The legacy /api/v3 (sp500_constituent, nasdaq_constituent) was cut off on
# 2026-07-03 — see tests/unit/test_dead_integrations_allowlist.py — and 403s even with a valid key.
_FMP_BASE = "https://financialmodelingprep.com/stable"
_FMP_SP500_PATH = "sp500-constituent"
_FMP_NASDAQ100_PATH = "nasdaq-constituent"

_DATA_PATH = Path(__file__).resolve().parents[1] / "app" / "data" / "index_membership.json"


class PartialUniverseError(RuntimeError):
    """One index half was fetched but the other is unavailable — refuse to write a partial list."""


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

    sp = to_map(_fetch_fmp(_FMP_SP500_PATH, api_key))
    nd = to_map(_fetch_fmp(_FMP_NASDAQ100_PATH, api_key))
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
    """Fetch both dedicated public lists; report a failed Nasdaq half without writing."""
    sp = _read_wiki_table(_SP500_WIKI, ("Symbol", "Ticker"))
    try:
        nd = _read_wiki_table(_NASDAQ100_WIKI, ("Ticker", "Symbol"))
    except Exception as exc:  # noqa: BLE001 - re-raised with an actionable message
        raise PartialUniverseError(
            f"S&P 500 fetched from Wikipedia ({len(sp)} tickers) but the Nasdaq-100 half is "
            f"unavailable ({exc}). Check the public constituents table at {_NASDAQ100_WIKI} "
            "and retry after retrieval or parsing is repaired. Nothing written."
        ) from exc
    return sp, nd


# --------------------------------------------------------------------------- build + write

def require_both_halves(sp500: Dict[str, str], nasdaq100: Dict[str, str], source: str) -> None:
    """Source-agnostic guard: both indices present at plausible size, else ``PartialUniverseError``.

    Applies to FMP too — an empty ``nasdaq-constituent`` response (plan change, outage, endpoint
    move) would otherwise clear the union floor on the S&P 500 alone and write a partial file.
    """
    if len(sp500) < SP500_FLOOR or len(nasdaq100) < NASDAQ100_FLOOR:
        raise PartialUniverseError(
            f"{source} returned sp500={len(sp500)} (floor {SP500_FLOOR}) and "
            f"nasdaq100={len(nasdaq100)} (floor {NASDAQ100_FLOOR}); one index half is missing or "
            "truncated, so the S&P 500 ∪ Nasdaq 100 universe cannot be rebuilt. Nothing written."
        )


def build_entries(sp500: Dict[str, str], nasdaq100: Dict[str, str]) -> List[dict]:
    """Merge the two maps into sorted entries with an ``indices`` list per ticker."""
    entries: Dict[str, dict] = {}
    for tickers, label in ((sp500, "sp500"), (nasdaq100, "nasdaq100")):
        for sym, name in tickers.items():
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
        return json.loads(path.read_text(encoding="utf-8")).get("members", [])
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
    use_fmp = source == "fmp"
    api_key = (os.environ.get("FMP_API_KEY", "") or "") if use_fmp else ""
    if use_fmp and not api_key:
        logger.error("source=fmp but FMP_API_KEY is unset")
        return 2
    label = "fmp" if use_fmp else "wikipedia"
    try:
        sp500, nasdaq100 = fetch_fmp(api_key) if use_fmp else fetch_wikipedia()
        require_both_halves(sp500, nasdaq100, label)
    except PartialUniverseError as exc:
        logger.error("ABORT (partial universe, nothing written): %s", exc)
        return 2
    except Exception as exc:  # noqa: BLE001 - degrade with a clear message, never half-write
        logger.error("fetch failed (%s): %s", label, exc)
        return 2

    entries = build_entries(sp500, nasdaq100)
    logger.info(
        "fetched via %s: sp500=%d nasdaq100=%d union=%d", label, len(sp500), len(nasdaq100), len(entries),
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
        "source": label,
        "source_urls": {
            "sp500": f"{_FMP_BASE}/{_FMP_SP500_PATH}" if use_fmp else _SP500_WIKI,
            "nasdaq100": f"{_FMP_BASE}/{_FMP_NASDAQ100_PATH}" if use_fmp else _NASDAQ100_WIKI,
        },
        # Stamped on every run (the monthly workflow PR is then a heartbeat, and the 100-day test gate
        # stays honest). Stdlib rather than app.utils.datetimes.utcnow(): this script runs in the
        # workflow's bare venv (httpx + pandas only) and must not import the app package.
        "generated_on": datetime.now(timezone.utc).date().isoformat(),
        "count": len(entries),
        "members": entries,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
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
