"""Populate golden_set.json from live EDGAR + each filing's own XBRL (network required).

For each entry, resolves the latest filing of the requested type (accession_number +
document_url), then loads THAT filing's XBRL instance and extracts ground-truth facts
(revenue, net_income, eps) for the filing's own reporting period — the full-year
duration for a 10-K, the quarter duration for a 10-Q, always undimensioned
(consolidated) facts ending on the filing's period_of_report.

Ground truth therefore means "what the filed document reports", independent of the
product's extraction pipeline, so the eval can catch extraction errors as well as
summarization errors.

An entry is marked verified=true only when ALL hard invariants pass:
  - revenue, net_income and eps facts found for the filing's own period
  - revenue > 0
  - sign(eps) == sign(net_income) (when both are nonzero)
  - fact duration matches the form (~12 months for 10-K, ~3 months for 10-Q)
Failures leave verified=false with the reasons recorded in `verification_problems`.

    cd backend && python -m evals.build_golden_set            # update in place
    cd backend && python -m evals.build_golden_set --dry-run  # print, don't write

Run in an environment with SEC EDGAR network access (and the app's env vars).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

GOLDEN_PATH = Path(__file__).with_name("golden_set.json")

# Concept candidates per metric, most-specific/most-current tags first.
METRIC_CONCEPTS: Dict[str, Tuple[str, List[str]]] = {
    # `Revenues` first: within a single filing's XBRL there is no stale-tag risk
    # (unlike the companyfacts API), and when both are tagged `Revenues` is the
    # income statement's total top line (e.g. WMT/XOM include membership/other
    # income there) — the figure a summary will quote.
    # NOTE: these concept lists must stay identical to the product's DURATION_CONCEPTS in
    # app.services.edgar.instance_extractor (enforced by test_golden_set_concepts_match_product_
    # extraction). The trailing entries are the IFRS (ifrs-full) candidates for foreign filers.
    "revenue": ("USD", [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
        "NetSales",
        "Revenue",
        "RevenueFromContractsWithCustomers",
    ]),
    "net_income": ("USD", [
        "NetIncomeLoss",
        "ProfitLoss",
        "NetIncomeLossAvailableToCommonStockholdersBasic",
        "ProfitLossAttributableToOwnersOfParent",
    ]),
    "eps": ("USD_per_share", [
        "EarningsPerShareBasic",
        "EarningsPerShareDiluted",
        "EarningsPerShareBasicAndDiluted",
        "BasicEarningsLossPerShare",
        "DilutedEarningsLossPerShare",
    ]),
}

def _unit_with_currency(default_unit: str, currency: Optional[str]) -> str:
    """Stamp the as-filed reporting currency onto the ground-truth unit (USD defaults otherwise).

    A foreign filer's value is recorded in its native currency so the golden set isn't implied-USD:
    monetary "USD" -> "CNY", per-share "USD_per_share" -> "CNY_per_share". The scorer reads the
    "_per_share" suffix (not the currency) to pick full-precision vs scaled rendering.
    """
    if not currency:
        return default_unit
    return f"{currency}_per_share" if default_unit.endswith("_per_share") else currency


def _duration_ok(start: Optional[str], end: Optional[str], filing_type: str) -> bool:
    # Shared with the product's accession-aware extraction (issue #240): the
    # duration windows live in app.services.edgar.instance_extractor so the
    # eval harness and the product ground on the same period semantics.
    # Imported lazily — app imports may need env vars that __main__ sets first.
    from app.services.edgar.instance_extractor import duration_in_window
    return duration_in_window(start, end, filing_type)


def _fact_for_metric(
    xb, metric: str, period_of_report: str, filing_type: str
) -> Tuple[Optional[float], Optional[str], Optional[str]]:
    """Extract one consolidated fact (+ its reporting currency) for the filing's own period.

    Delegates to the product's currency-aware series selection so the eval ground truth and the
    product ground on identical period + currency semantics: facts are filtered to the issuer's
    reporting currency, so a foreign filer that also tags a USD convenience translation (e.g.
    Alibaba) yields its native value — not an "ambiguous" drop. Returns (value, currency, problem).
    """
    from app.services.edgar.instance_extractor import duration_series_with_currency

    _, concepts = METRIC_CONCEPTS[metric]
    series, currency = duration_series_with_currency(xb, concepts, filing_type, period_of_report)
    if series and series[0][0] == period_of_report:
        return series[0][1], currency, None
    return None, None, f"{metric}: no consolidated fact for period {period_of_report}"


# Diluted EPS, captured as an accepted ALTERNATE to the (basic-first) `eps` ground truth: a summary
# that quotes diluted EPS — the headline figure investors use — is correct, not a miss.
def _diluted_eps(xb, period_of_report: str, filing_type: str) -> Optional[float]:
    """Diluted EPS for the filing's own period, or None if not separately tagged.

    Reuses the product's `DURATION_CONCEPTS["eps_diluted"]` so the harness and the product can't
    drift on which diluted-EPS tags count.
    """
    from app.services.edgar.instance_extractor import DURATION_CONCEPTS, duration_series_with_currency

    series, _ = duration_series_with_currency(
        xb, DURATION_CONCEPTS["eps_diluted"], filing_type, period_of_report
    )
    if series and series[0][0] == period_of_report:
        return series[0][1]
    return None


def _distinct_alts(values: List[float], primary: float) -> List[float]:
    """De-dup candidate alt values against the primary and each other (float-tolerant)."""
    out: List[float] = []
    for v in values:
        if v is None or abs(v - primary) <= 1e-6:
            continue
        if all(abs(v - o) > 1e-6 for o in out):
            out.append(v)
    return out


# A multi-entity filer tags several legitimate net-income figures: consolidated (incl. NCI),
# attributable to the parent, and available-to-common (after preferred / mezzanine adjustments).
# A summary that quotes ANY of them is correct, not a miss — so the non-primary ones are accepted
# as alternates. Single-concept (most domestic) filers yield none.
_NET_INCOME_ALT_CONCEPTS = (
    "NetIncomeLoss", "ProfitLoss",
    "NetIncomeLossAvailableToCommonStockholdersBasic",
    "NetIncomeLossAvailableToCommonStockholdersDiluted",
    "ProfitLossAttributableToOwnersOfParent",
)


def _net_income_alts(xb, period_of_report: str, filing_type: str, primary: float) -> List[float]:
    """Distinct other-basis net-income values for the period (excludes the primary)."""
    from app.services.edgar.instance_extractor import duration_series_with_currency

    found: List[float] = []
    for concept in _NET_INCOME_ALT_CONCEPTS:
        series, _ = duration_series_with_currency(xb, [concept], filing_type, period_of_report)
        if series and series[0][0] == period_of_report:
            found.append(series[0][1])
    return _distinct_alts(found, primary)


def _per_ads_eps_alts(xb, period_of_report: str, filing_type: str, ads_ratio: Optional[float]) -> List[float]:
    """Per-ADS EPS renderings (= per-ordinary-share × ratio) for ADR filers.

    A 20-F headlines 'earnings per ADS' while the XBRL tags per-ordinary-share, so a correct
    per-ADS figure (e.g. Alibaba's RMB44.00 = RMB5.50 × 8) would otherwise score as a miss."""
    if not ads_ratio or ads_ratio <= 1:
        return []
    from app.services.edgar.instance_extractor import DURATION_CONCEPTS, duration_series_with_currency

    out: List[float] = []
    for concepts in (METRIC_CONCEPTS["eps"][1], DURATION_CONCEPTS["eps_diluted"]):
        series, _ = duration_series_with_currency(xb, concepts, filing_type, period_of_report)
        if series and series[0][0] == period_of_report:
            out.append(round(series[0][1] * ads_ratio, 2))
    return out


def _extract_ground_truth(
    cik: str, accession_number: str, filing_type: str, ads_ratio: Optional[float] = None
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Load the specific filing's XBRL and return (facts, problems). Sync — run in a thread."""
    from edgar import Company

    company = Company(cik)
    filings = list(company.get_filings(accession_number=accession_number))
    if not filings:
        return [], [f"filing {accession_number} not found by accession"]
    filing = filings[0]

    period_of_report = str(filing.period_of_report or "")
    if not period_of_report:
        return [], ["filing has no period_of_report"]
    if filing.form != filing_type:
        return [], [f"resolved form {filing.form!r} != requested {filing_type!r}"]

    xb = filing.xbrl()
    if xb is None:
        return [], ["filing has no XBRL instance"]

    facts: List[Dict[str, Any]] = []
    problems: List[str] = []
    by_metric: Dict[str, float] = {}
    for metric, (default_unit, _) in METRIC_CONCEPTS.items():
        value, currency, problem = _fact_for_metric(xb, metric, period_of_report, filing_type)
        if problem:
            problems.append(problem)
            continue
        by_metric[metric] = value
        facts.append({"metric": metric, "value": value, "unit": _unit_with_currency(default_unit, currency)})

    # EPS alternates: diluted (vs basic primary) + per-ADS renderings for ADR filers.
    eps_fact = next((f for f in facts if f["metric"] == "eps"), None)
    if eps_fact is not None:
        candidates = [_diluted_eps(xb, period_of_report, filing_type)]
        candidates += _per_ads_eps_alts(xb, period_of_report, filing_type, ads_ratio)
        alts = _distinct_alts([c for c in candidates if c is not None], eps_fact["value"])
        if alts:
            eps_fact["alt_values"] = alts

    # Net income alternates: other legitimately-tagged bases (consolidated / attributable / common).
    ni_fact = next((f for f in facts if f["metric"] == "net_income"), None)
    if ni_fact is not None:
        ni_alts = _net_income_alts(xb, period_of_report, filing_type, ni_fact["value"])
        if ni_alts:
            ni_fact["alt_values"] = ni_alts

    # Hard invariants — corrupt ground truth poisons every bake-off run.
    if "revenue" in by_metric and by_metric["revenue"] <= 0:
        problems.append(f"revenue not positive: {by_metric['revenue']}")
    if by_metric.get("net_income") and by_metric.get("eps"):
        if (by_metric["net_income"] > 0) != (by_metric["eps"] > 0):
            problems.append(
                f"sign mismatch: net_income={by_metric['net_income']} vs eps={by_metric['eps']}"
            )

    return facts, problems


async def _resolve_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    from app.services.edgar.compat import sec_edgar_service

    cik, ftype = str(entry["cik"]), entry["filing_type"]
    filings = await sec_edgar_service.get_filings(cik, filing_types=[ftype], limit=1)
    if not filings:
        print(f"  ! {entry['ticker']}: no {ftype} filings found")
        entry["verified"] = False
        return entry
    latest = filings[0]
    entry["accession_number"] = latest.get("accession_number", "")
    entry["document_url"] = latest.get("document_url", "")

    try:
        facts, problems = await asyncio.to_thread(
            _extract_ground_truth, cik, entry["accession_number"], ftype, entry.get("ads_ratio")
        )
    except Exception as exc:  # noqa: BLE001
        facts, problems = [], [f"XBRL extraction failed: {exc}"]

    entry["ground_truth"] = facts
    entry["verified"] = bool(
        entry["accession_number"] and entry["document_url"]
        and len(facts) == len(METRIC_CONCEPTS) and not problems
    )
    if problems:
        entry["verification_problems"] = problems
        print(f"  ! {entry['ticker']} {ftype}: {'; '.join(problems)}")
    else:
        entry.pop("verification_problems", None)
    status = "ok" if entry["verified"] else "UNVERIFIED"
    print(f"  - {entry['ticker']} {ftype}: {len(facts)} facts, {status}")
    return entry


async def main(dry_run: bool) -> None:
    data = json.loads(GOLDEN_PATH.read_text())
    print(f"Resolving {len(data['filings'])} golden filings against EDGAR...")
    data["filings"] = [await _resolve_entry(e) for e in data["filings"]]
    if dry_run:
        print(json.dumps(data, indent=2))
        return
    GOLDEN_PATH.write_text(json.dumps(data, indent=2) + "\n")
    verified = sum(1 for e in data["filings"] if e["verified"])
    print(f"Wrote {GOLDEN_PATH} ({verified}/{len(data['filings'])} verified).")


if __name__ == "__main__":
    os.environ.setdefault("SKIP_REDIS_INIT", "true")
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    asyncio.run(main(parser.parse_args().dry_run))
