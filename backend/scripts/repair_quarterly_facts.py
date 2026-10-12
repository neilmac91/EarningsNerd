#!/usr/bin/env python3
"""Preview/apply/rollback a bounded quarterly correction; JSON output and durable apply journal.

Defaults to a read-only preview. Explicit tickers are mandatory; --apply is required for writes.
External SEC reads use the existing companyfacts/filing transport. Inputs are fetched before the
per-company write transaction; no AI calls, subscriptions, or production flags are involved.
"""
import argparse
import asyncio
from datetime import date
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAX_BATCH = 50
MAX_INPUT_BYTES = 32 * 1024 * 1024


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tickers", required=True, help="Explicit comma-separated cohort; max 50.")
    parser.add_argument("--limit", type=int, default=10, help="Batch bound, 1..50 (default 10).")
    parser.add_argument("--apply", action="store_true", help="Commit changes and their audit journal.")
    parser.add_argument("--rollback-run", help="Preview/rollback this prior apply run; no SEC fetch.")
    parser.add_argument("--companyfacts-dir", type=Path, help="Offline CIK##########.json directory.")
    parser.add_argument("--eps-manifest", type=Path, help="Explicit local reported-EPS source manifest.")
    parser.add_argument("--output", type=Path, help="Also save complete machine-readable JSON report.")
    return parser


def _read_json(path: Path):
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError(f"Input exceeds {MAX_INPUT_BYTES} bytes: {path.name}")
    return json.loads(path.read_text())


def _manifest(path: Path | None, tickers: list[str]) -> list[dict]:
    entries = _read_json(path) if path else []
    required = {
        "ticker", "cik", "accession", "filename", "period_end", "fiscal_period",
        "fiscal_year", "currency", "filed_at",
    }
    if not isinstance(entries, list) or len(entries) > 200:
        raise ValueError("EPS manifest must be an array of at most 200 source entries")
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != required:
            raise ValueError("EPS manifest entry has missing or unsupported fields")
        if entry["ticker"] not in tickers or entry["fiscal_period"] not in {"Q1", "Q2", "Q3", "Q4"}:
            raise ValueError("EPS manifest contains an unselected ticker or invalid quarter")
        if not isinstance(entry["fiscal_year"], int) or entry["currency"] != "USD":
            raise ValueError("EPS manifest requires integer fiscal year and USD currency")
        date.fromisoformat(entry["period_end"])
        date.fromisoformat(entry["filed_at"])
    return entries


async def _reported_eps(company: dict, entries: list[dict], supported_units: set[str]) -> list[dict]:
    from app.services.edgar.reported_quarterly_eps import fetch_reported_quarterly_eps
    from app.services.fact_provenance import reported_provenance

    facts = []
    for entry in entries:
        if entry["ticker"] != company["ticker"]:
            continue
        if int(entry["cik"]) != int(company["cik"]) or "USD/shares" not in supported_units:
            raise ValueError("EPS source CIK/currency is not supported by this company's stored EPS")
        source = await fetch_reported_quarterly_eps(
            cik=company["cik"], accession=entry["accession"], filename=entry["filename"],
            period_end=entry["period_end"], currency=entry["currency"],
        )
        if source is None:
            raise ValueError("Explicit reported EPS source could not be validated")
        for concept, value in source["values"].items():
            fact = {
                "company_id": company["id"], "filing_id": None,
                "concept": "earnings_per_share" if concept == "eps_basic" else concept,
                "raw_tag": None, "unit": source["unit"], "period_start": date.fromisoformat(source["period_start"]),
                "period_end": date.fromisoformat(source["period_end"]), "fiscal_period": entry["fiscal_period"],
                "fiscal_year": entry["fiscal_year"], "form": source["form"],
                "accession": entry["accession"], "source": "reported_eps", "reconciled": True,
                "value": value,
            }
            provenance = reported_provenance(fact, filed_at=entry["filed_at"])
            provenance.update({
                "source_url": source["source_url"], "source_sha256": source["source_sha256"],
                "source_evidence": source["source_evidence"],
            })
            fact["provenance"] = provenance
            facts.append(fact)
    return facts


def run(args: argparse.Namespace) -> dict:
    tickers = list(dict.fromkeys(t.strip().upper() for t in args.tickers.split(",") if t.strip()))
    if not 1 <= args.limit <= MAX_BATCH or not tickers or len(tickers) > args.limit:
        raise ValueError("Select 1..limit explicit tickers with limit between 1 and 50")
    if any(not t.replace(".", "").replace("-", "").isalnum() or len(t) > 12 for t in tickers):
        raise ValueError("Invalid ticker in cohort")
    if args.rollback_run and (args.eps_manifest or args.companyfacts_dir):
        raise ValueError("Rollback does not accept source inputs")
    entries = _manifest(args.eps_manifest, tickers)
    from app.database import SessionLocal
    from app.models import Company, FinancialFact
    from app.services import facts_service
    from app.services.quarterly_fact_repair import repair_company, rollback_company

    # This short read session closes before network I/O. No caller/business transaction is ended.
    with SessionLocal() as db:
        rows = db.query(Company).filter(Company.ticker.in_(tickers)).order_by(Company.id).all()
        companies = [{"id": c.id, "ticker": c.ticker, "cik": c.cik} for c in rows]
        if {c["ticker"] for c in companies} != set(tickers):
            raise ValueError("One or more selected tickers are unknown; no companies processed")
        units = {c["id"]: {unit for (unit,) in db.query(FinancialFact.unit).filter(
            FinancialFact.company_id == c["id"],
            FinancialFact.concept.in_(["earnings_per_share", "eps_diluted"]),
            FinancialFact.source.in_(["companyfacts", "edgar_xbrl", "reported_eps"]),
            FinancialFact.reconciled.is_(True), FinancialFact.is_latest.is_(True),
        ).distinct()} for c in companies}
    report = {"run_id": str(uuid4()), "dry_run": not args.apply, "companies": [], "failed": 0}
    for company in companies:
        try:
            if args.rollback_run:
                payload, eps = None, []
            else:
                payload = (_read_json(args.companyfacts_dir / f"CIK{int(company['cik']):010d}.json")
                           if args.companyfacts_dir else
                           facts_service._fetch_companyfacts_sync(company["cik"]))
                if payload is None:
                    raise ValueError("Companyfacts fetch failed; company unchanged")
                eps = asyncio.run(_reported_eps(company, entries, units[company["id"]])) if entries else []
            with SessionLocal() as db:
                with db.begin():
                    if args.rollback_run:
                        result = rollback_company(
                            db, company["id"], args.rollback_run,
                            dry_run=not args.apply, run_id=report["run_id"],
                        )
                    else:
                        result = repair_company(
                            db, company["id"], payload, dry_run=not args.apply,
                            run_id=report["run_id"], reported_eps=eps,
                        )
                report["companies"].append(result)
        except Exception as exc:  # Per-company failure is visible and sets a failing CLI exit code.
            report["failed"] += 1
            report["companies"].append({"ticker": company["ticker"], "error": str(exc)})
    return report


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = run(args)
    except (ValueError, OSError) as exc:
        print(json.dumps({"failed": 1, "error": str(exc)}))
        return 1
    encoded = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(encoded + "\n")
    print(encoded)
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    os.environ.setdefault("SKIP_REDIS_INIT", "true")
    raise SystemExit(main())
