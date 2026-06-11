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
    "revenue": ("USD", [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
        "NetSales",
    ]),
    "net_income": ("USD", [
        "NetIncomeLoss",
        "ProfitLoss",
        "NetIncomeLossAvailableToCommonStockholdersBasic",
    ]),
    "eps": ("USD_per_share", [
        "EarningsPerShareBasic",
        "EarningsPerShareDiluted",
        "EarningsPerShareBasicAndDiluted",
    ]),
}

# Acceptable duration windows in days. 52/53-week fiscal years run 364-371 days;
# fiscal quarters run 84-98. Anything outside is the wrong period slice (Q4 vs FY,
# quarter vs YTD) and must not become ground truth.
DURATION_WINDOWS = {"10-K": (320, 390), "10-Q": (75, 105)}


def _duration_ok(start: Optional[str], end: Optional[str], filing_type: str) -> bool:
    from datetime import date
    if not start or not end:
        return False
    try:
        days = (date.fromisoformat(str(end)) - date.fromisoformat(str(start))).days
    except (ValueError, TypeError):
        return False
    low, high = DURATION_WINDOWS[filing_type]
    return low <= days <= high


def _fact_for_metric(xb, metric: str, period_of_report: str, filing_type: str) -> Tuple[Optional[float], Optional[str]]:
    """Extract one consolidated fact for the filing's own reporting period."""
    _, concepts = METRIC_CONCEPTS[metric]
    for concept in concepts:
        df = xb.facts.query().by_concept(f"us-gaap:{concept}", exact=True).to_dataframe()
        if df.empty:
            continue
        rows = df[
            (df["is_dimensioned"] == False)  # noqa: E712 (pandas mask)
            & (df["period_end"] == period_of_report)
        ]
        if rows.empty:
            continue
        # An empty boolean list would select columns, not rows — guard above matters.
        rows = rows[[
            _duration_ok(s, e, filing_type)
            for s, e in zip(rows["period_start"], rows["period_end"])
        ]]
        if rows.empty:
            continue
        values = sorted({round(float(v), 4) for v in rows["numeric_value"] if v == v})
        if not values:
            continue
        if len(values) > 1:
            return None, f"{metric}: ambiguous values {values} for {concept}"
        return values[0], None
    return None, f"{metric}: no consolidated fact for period {period_of_report}"


def _extract_ground_truth(cik: str, accession_number: str, filing_type: str) -> Tuple[List[Dict[str, Any]], List[str]]:
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
    for metric, (unit, _) in METRIC_CONCEPTS.items():
        value, problem = _fact_for_metric(xb, metric, period_of_report, filing_type)
        if problem:
            problems.append(problem)
            continue
        by_metric[metric] = value
        facts.append({"metric": metric, "value": value, "unit": unit})

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
            _extract_ground_truth, cik, entry["accession_number"], ftype
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
