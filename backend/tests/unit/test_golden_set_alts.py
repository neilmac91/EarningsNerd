"""Offline tests for the FPI/multi-basis ground-truth alternates.

`_distinct_alts` is pure; the data-integrity checks assert the committed golden set carries the
per-ADS EPS and multi-basis net-income alternates that close the FPI recall residual (BABA/TSM)."""
import json
from pathlib import Path

from evals.build_golden_set import _distinct_alts, _per_ads_eps_alts

GOLDEN = Path(__file__).resolve().parents[2] / "evals" / "golden_set.json"


def _entry(ticker: str, form: str) -> dict:
    data = json.loads(GOLDEN.read_text())
    return next(e for e in data["filings"] if e["ticker"] == ticker and e["filing_type"] == form)


def _fact(entry: dict, metric: str) -> dict:
    return next(f for f in entry["ground_truth"] if f["metric"] == metric)


def test_distinct_alts_dedups_and_excludes_primary():
    assert _distinct_alts([5.5, 5.7, 5.5, 44.0], 5.7) == [5.5, 44.0]
    assert _distinct_alts([100.0, 100.0], 100.0) == []      # all equal the primary
    assert _distinct_alts([None, 3.0], 2.0) == [3.0]         # None dropped


def test_per_ads_eps_alts_guard_short_circuits_no_op_and_invalid_ratios():
    # A no-op (1:1) or invalid ratio returns [] WITHOUT touching the XBRL instance (xb=None is safe).
    for ratio in (None, 0, -1, 1, 1.0, "not-a-number"):
        assert _per_ads_eps_alts(None, "2026-03-31", "20-F", ratio) == []


def test_baba_carries_per_ads_eps_and_multibasis_net_income():
    baba = _entry("BABA", "20-F")
    assert baba.get("ads_ratio") == 8
    eps = _fact(baba, "eps")
    # diluted per ADS = 5.5 × 8 = 44.0 (the figure the 20-F headlines: "earnings per ADS RMB44.00")
    assert any(abs(a - 44.0) < 1e-6 for a in eps.get("alt_values", []))
    ni = _fact(baba, "net_income")
    # consolidated (ProfitLoss) RMB102,127M accepted alongside the GT (attributable) figure
    assert any(abs(a - 102_127_000_000.0) < 1.0 for a in ni.get("alt_values", []))


def test_tsm_carries_attributable_net_income_alt():
    tsm = _entry("TSM", "20-F")
    assert tsm.get("ads_ratio") == 5
    ni = _fact(tsm, "net_income")
    # attributable-to-owners NT$1,697,604M (what TSM's summary quotes) vs GT consolidated ProfitLoss
    assert any(abs(a - 1_697_604_000_000.0) < 1.0 for a in ni.get("alt_values", []))
