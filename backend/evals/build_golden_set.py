"""Populate golden_set.json from live EDGAR + XBRL (network required).

For each entry, resolves the latest filing of the requested type (accession_number +
document_url) and auto-fills ground_truth financial facts (revenue, net_income, eps) from
standardized XBRL — the same XBRL the product grounds on, so "ground truth" means "what the
pipeline should have surfaced." Sets verified=true on success.

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
from typing import Any, Dict, List, Optional

GOLDEN_PATH = Path(__file__).with_name("golden_set.json")


def _coerce_number(node: Any) -> Optional[float]:
    """Pull a single current numeric value out of whatever shape XBRL extraction returns."""
    if node is None:
        return None
    if isinstance(node, (int, float)):
        return float(node)
    if isinstance(node, dict):
        for key in ("current", "value", "latest", "amount"):
            if key in node:
                return _coerce_number(node[key])
        return None
    if isinstance(node, list) and node:
        return _coerce_number(node[0])
    return None


def _facts_from_metrics(metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
    facts: List[Dict[str, Any]] = []
    mapping = {
        "revenue": ("revenue", "USD"),
        "net_income": ("net_income", "USD"),
        "earnings_per_share": ("eps", "USD_per_share"),
        "eps": ("eps", "USD_per_share"),
    }
    for src_key, (metric, unit) in mapping.items():
        if src_key in metrics:
            val = _coerce_number(metrics[src_key])
            if val is not None and not any(f["metric"] == metric for f in facts):
                facts.append({"metric": metric, "value": val, "unit": unit})
    return facts


async def _resolve_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    from app.services.edgar.compat import sec_edgar_service, xbrl_service

    cik, ftype = str(entry["cik"]), entry["filing_type"]
    filings = await sec_edgar_service.get_filings(cik, filing_types=[ftype], limit=1)
    if not filings:
        print(f"  ! {entry['ticker']}: no {ftype} filings found")
        return entry
    latest = filings[0]
    entry["accession_number"] = latest.get("accession_number", "")
    entry["document_url"] = latest.get("document_url", "")

    try:
        xbrl = await xbrl_service.get_xbrl_data(entry["accession_number"], cik)
        metrics = xbrl_service.extract_standardized_metrics(xbrl) if xbrl else {}
        facts = _facts_from_metrics(metrics or {})
    except Exception as exc:  # noqa: BLE001
        print(f"  ! {entry['ticker']}: XBRL fetch failed: {exc}")
        facts = []

    entry["ground_truth"] = facts
    entry["verified"] = bool(entry["accession_number"] and entry["document_url"] and facts)
    status = "ok" if entry["verified"] else "incomplete (fill ground_truth manually)"
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
