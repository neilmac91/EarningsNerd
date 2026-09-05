"""Prepare source-only Copilot evidence in a NEW disposable SQLite database.

Run in a fresh process: python -m evals.copilot_bootstrap --database /scratch/new.db
--output /scratch/evidence. This module imports no application code until the target
is checked and environment configured. It never reads questions or expected answers.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import re
import sys
from types import SimpleNamespace
from typing import Any

SOURCE_MANIFEST = Path(__file__).with_name("copilot_sources.json")
IDENTITY_KEYS = {"ticker", "cik", "accession_number", "filing_type", "document_url"}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_sources(path: Path = SOURCE_MANIFEST) -> tuple[list[dict], str]:
    raw = path.read_bytes()
    manifest = json.loads(raw)
    if set(manifest) != {"schema_version", "sources"} or manifest["schema_version"] != 1:
        raise ValueError("invalid_source_manifest")
    sources = manifest["sources"]
    if not isinstance(sources, list) or not sources:
        raise ValueError("empty_source_manifest")
    identities = set()
    for source in sources:
        if not isinstance(source, dict) or set(source) != IDENTITY_KEYS:
            raise ValueError("source_identity_fields_only")
        if not all(isinstance(value, str) and value for value in source.values()):
            raise ValueError("invalid_source_identity")
        accession = source["accession_number"]
        if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession) or accession in identities:
            raise ValueError("invalid_or_duplicate_accession")
        if not source["cik"].isdigit() or int(source["cik"]) <= 0:
            raise ValueError("invalid_cik")
        if source["filing_type"] not in {"10-K", "10-Q", "20-F", "40-F"}:
            raise ValueError("unsupported_form")
        # Identity-only validation. Production canonical URL construction remains in sec_urls.
        from urllib.parse import urlsplit
        url = urlsplit(source["document_url"])
        expected = f"/Archives/edgar/data/{int(source['cik'])}/{accession.replace('-', '')}/"
        if url.scheme != "https" or url.netloc != "www.sec.gov" or not url.path.startswith(expected) or url.query or url.fragment:
            raise ValueError("source_url_identity_mismatch")
        identities.add(accession)
    return sources, _sha(raw)


def validate_database(value: str) -> Path:
    path = Path(value)
    if ":" in value or not path.is_absolute() or path.suffix != ".db":
        raise ValueError("new_absolute_db_path_required")
    if path.is_symlink() or path.exists():
        raise ValueError("database_already_exists")
    resolved = path.resolve()
    if not resolved.parent.is_dir():
        raise ValueError("database_parent_missing")
    return resolved


def configure_environment(database: Path, output: Path) -> None:
    if any(name == "app" or name.startswith("app.") for name in sys.modules):
        raise ValueError("application_already_imported_use_fresh_process")
    os.environ.update({
        "DATABASE_URL": "sqlite:///" + str(database), "ENVIRONMENT": "test",
        "SECRET_KEY": "source-bootstrap-disposable-test-key-not-for-authentication",
        "SKIP_REDIS_INIT": "true", "ENABLE_HISTORY_BACKFILL_ON_VISIT": "false",
        "EDGAR_LOCAL_DATA_DIR": str(output / "edgar-cache"),
        "USE_STATEMENT_FINANCIALS": "true", "USE_EDGARTOOLS_SECTIONS": "true",
        "ENABLE_FPI_FILINGS": "true", "AI_FALLBACK_BASE_URL": "", "AI_FALLBACK_MODEL": "",
        # Extraction helpers construct a client on import, but this process never generates.
        "OPENAI_API_KEY": "source-bootstrap-placeholder-never-used-for-generation",
        "OPENAI_BASE_URL": "http://127.0.0.1:9/v1", "AI_FALLBACK_API_KEY": "",
    })


def verify_engine(engine: Any, database: Path) -> None:
    url = engine.url
    if url.drivername != "sqlite" or url.host or url.query or not url.database or Path(url.database).resolve() != database:
        raise ValueError("resolved_engine_target_mismatch")


def _load_runtime() -> SimpleNamespace:
    from app.config import settings
    from app.database import Base, SessionLocal, engine
    from app.models import Company, Filing
    from app.models.financial_fact import FinancialFact
    from app.services.edgar.compat import sec_edgar_service, xbrl_service
    from app.services.facts_service import process_filing_facts
    from app.services.summary_generation_service import get_or_cache_excerpt
    return SimpleNamespace(
        settings=settings, Base=Base, session=SessionLocal, engine=engine,
        Company=Company, Filing=Filing, FinancialFact=FinancialFact,
        sec=sec_edgar_service, xbrl=xbrl_service,
        excerpt=get_or_cache_excerpt, facts=process_filing_facts,
    )


def _artifact(output: Path, name: str, value: Any) -> dict:
    data = (value if isinstance(value, str) else json.dumps(value, sort_keys=True, default=str)).encode()
    path = output / name
    path.write_bytes(data)
    return {"path": str(path), "sha256": _sha(data), "bytes": len(data)}


def _date(value: str) -> datetime:
    return datetime.fromisoformat(value[:10]).replace(tzinfo=timezone.utc)


async def prepare_source(source: dict, runtime: Any, output: Path) -> dict:
    result = {**source, "status": "unavailable", "artifacts": {},
              "retrieved_at": datetime.now(timezone.utc).isoformat()}
    stage = "metadata"
    try:
        filings = await runtime.sec.get_filings(source["cik"], [source["filing_type"]], limit=40)
        matches = [f for f in filings if f.get("accession_number") == source["accession_number"]]
        if len(matches) != 1:
            raise ValueError("exact_source_metadata_unavailable")
        metadata = matches[0]
        if (str(int(metadata["cik"])) != str(int(source["cik"]))
                or metadata["filing_type"] != source["filing_type"]
                or metadata["document_url"] != source["document_url"]):
            raise ValueError("returned_metadata_identity_mismatch")
        filed, period = _date(metadata["filing_date"]), _date(metadata["report_date"])
        result["metadata"] = {key: metadata.get(key) for key in (
            "filing_date", "report_date", "document_url", "sec_url", "company_name",
        )}
        folder = output / source["accession_number"]
        folder.mkdir()
        stage = "document"
        html = await runtime.sec.get_filing_document(source["document_url"])
        result["artifacts"]["html"] = _artifact(folder, "filing.html", html)
        if not isinstance(html, str) or not html.strip():
            raise ValueError("document_unavailable")
        stage = "xbrl"
        xbrl = await runtime.xbrl.get_xbrl_data(source["accession_number"], source["cik"])
        result["artifacts"]["xbrl"] = _artifact(folder, "xbrl.json", xbrl)
        if not isinstance(xbrl, dict) or not xbrl:
            raise ValueError("xbrl_unavailable")
        stage = "sections"
        sections = await runtime.xbrl.get_filing_sections(source["accession_number"], source["cik"], source["filing_type"])
        result["artifacts"]["sections"] = _artifact(folder, "sections.json", sections)
        # Native parser unavailability is recorded; the production excerpt helper owns fallback.
        stage = "persist"
        with runtime.session() as db:
            company = db.query(runtime.Company).filter(runtime.Company.cik == str(int(source["cik"]))).first()
            if company is None:
                company = runtime.Company(cik=str(int(source["cik"])), ticker=source["ticker"],
                                          name=metadata.get("company_name") or source["ticker"])
                db.add(company)
                db.flush()
            filing = runtime.Filing(company=company, accession_number=source["accession_number"],
                filing_type=source["filing_type"], filing_date=filed, period_end_date=period,
                document_url=metadata["document_url"], sec_url=metadata.get("sec_url"), xbrl_data=xbrl)
            db.add(filing)
            db.commit()
            excerpt = runtime.excerpt(db, filing, html, sections=sections)
            result["artifacts"]["excerpt"] = _artifact(folder, "excerpt.txt", excerpt or "")
            if not excerpt or not excerpt.strip():
                raise ValueError("excerpt_unavailable")
            runtime.facts(db, filing)
            count = db.query(runtime.FinancialFact).filter(
                runtime.FinancialFact.company_id == company.id,
                runtime.FinancialFact.accession == source["accession_number"],
            ).count()
            result["fact_count"] = count
            result["reporting_currency"] = xbrl.get("reporting_currency")
            if not count:
                raise ValueError("facts_unavailable")
        result["status"] = "complete"
    except Exception as exc:  # noqa: BLE001 — retain partial evidence without leaking network/DB details
        result["error"] = {"stage": stage, "error_type": type(exc).__name__}
        if isinstance(exc, ValueError) and re.fullmatch(r"[a-z_]+", str(exc)):
            result["error"]["reason"] = str(exc)
    return result


async def bootstrap(database_value: str, output_value: str) -> dict:
    output = Path(output_value).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / "preparation.json").exists():
        raise ValueError("preparation_artifact_already_exists")
    report = {"schema_version": 1, "status": "unavailable", "sources": [], "errors": [],
              "planned_accessions": [], "prepared_at": datetime.now(timezone.utc).isoformat()}
    runtime = None
    stage = "target_guard"
    try:
        database = validate_database(database_value)
        report["database_path"] = str(database)
        sources, digest = load_sources()
        report.update(source_manifest_sha256=digest, planned_accessions=[s["accession_number"] for s in sources])
        configure_environment(database, output)
        stage = "runtime_guard"
        runtime = _load_runtime()
        verify_engine(runtime.engine, database)
        # Exclusive creation closes the check/create race; never adopt an existing file.
        descriptor = os.open(database, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
        runtime.Base.metadata.create_all(runtime.engine)
        report["runtime"] = {"flags": {key: getattr(runtime.settings, key) for key in (
            "USE_STATEMENT_FINANCIALS", "USE_EDGARTOOLS_SECTIONS", "ENABLE_FPI_FILINGS",
            "ENABLE_HISTORY_BACKFILL_ON_VISIT",
        )}, "versions": {name: version(name) for name in ("edgartools", "sqlalchemy", "openai")}}
        stage = "source_preparation"
        for source in sources:
            report["sources"].append(await prepare_source(source, runtime, output))
        if all(s["status"] == "complete" for s in report["sources"]):
            report["status"] = "complete"
    except Exception as exc:  # noqa: BLE001 — failed preparations are artifacts, never green gates
        error = {"stage": stage, "error_type": type(exc).__name__}
        if isinstance(exc, ValueError) and re.fullmatch(r"[a-z_]+", str(exc)):
            error["reason"] = str(exc)
        report["errors"].append(error)
    finally:
        if runtime is not None:
            runtime.engine.dispose()
        (output / "preparation.json").write_text(json.dumps(report, indent=2, sort_keys=True))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = asyncio.run(bootstrap(args.database, args.output))
    print(json.dumps({"status": report["status"], "prepared": len(report["sources"])}))
    return 0 if report["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
