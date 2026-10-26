"""Process bootstrap for the depth harness: environment, the harness's own facts store, SEC inputs.

Import this module BEFORE anything under ``app`` (``Settings`` reads the environment at import).

- The facts store is a private SQLite database built with the production schema and filled through
  the production companyfacts ingest (``normalize_companyfacts`` -> ``upsert_facts_bulk``), so the
  datasets the harness reads are the ones production would build from the same SEC payload.
- Every SEC request goes through the application's own transports (CLAUDE.md rule 5): companyfacts
  through ``facts.transport``, filing indexes and documents through ``edgar.compat``, XBRL instances
  through ``edgar.client``, full-text search through ``integrations.sec_api``. Raw responses are cached
  under ``TREND_DEPTH_CACHE`` (default ``~/.cache/earningsnerd-trend-depth``) so a re-run reads the same
  bytes; delete the cache to refetch.
- Provider keys are read by explicit name (``DEEPSEEK_API_KEY``, ``GEMINI_API_KEY``,
  ``ANTHROPIC_API_KEY``). The application's own ``OPENAI_*`` variables are pointed at DeepSeek with
  the production model so the census exercises the production call path; a Gemini key found in
  ``OPENAI_API_KEY`` with a Google base URL (the cloud container's layout) is moved to
  ``GEMINI_API_KEY`` first.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

BACKEND = Path(__file__).resolve().parents[2]
REPO = BACKEND.parent
RECORDS = REPO / "tasks" / "analysis-depth-2026-10"
CACHE = Path(os.environ.get("TREND_DEPTH_CACHE") or Path.home() / ".cache" / "earningsnerd-trend-depth")
CACHE.mkdir(parents=True, exist_ok=True)
STORE = Path(os.environ.get("TREND_DEPTH_STORE") or CACHE / "facts-store.sqlite")

PRODUCTION_BASE_URL = "https://api.deepseek.com/v1"
PRODUCTION_MODEL = "deepseek-flash"


def _configure_environment() -> None:
    base = os.environ.get("OPENAI_BASE_URL", "")
    if not os.environ.get("GEMINI_API_KEY") and "generativelanguage" in base and os.environ.get("OPENAI_API_KEY"):
        os.environ["GEMINI_API_KEY"] = os.environ["OPENAI_API_KEY"]
    os.environ["OPENAI_BASE_URL"] = PRODUCTION_BASE_URL
    os.environ["OPENAI_API_KEY"] = os.environ.get("DEEPSEEK_API_KEY") or "sk-unused"
    os.environ["AI_DEFAULT_MODEL"] = PRODUCTION_MODEL
    os.environ["DATABASE_URL"] = "sqlite:///" + str(STORE)
    os.environ.setdefault("SECRET_KEY", "trend-depth-harness-secret-key-not-a-real-secret-0001")
    os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_unused")
    os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_unused")
    os.environ["SKIP_REDIS_INIT"] = "true"
    os.environ["PWNED_PASSWORD_CHECK_ENABLED"] = "false"
    os.environ.setdefault("SEC_USER_AGENT", "EarningsNerd research harness support@earningsnerd.io")
    for key in ("SENTRY_DSN", "POSTHOG_API_KEY", "RESEND_API_KEY", "ALPHA_VANTAGE_API_KEY", "TURNSTILE_SECRET_KEY"):
        os.environ[key] = ""
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))


_configure_environment()

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import Company  # noqa: E402

Base.metadata.create_all(engine)


def _cache_json(name: str) -> Path:
    path = CACHE / name
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def read_cached(name: str) -> Optional[Any]:
    path = CACHE / name
    if path.exists():
        return json.loads(path.read_text())
    return None


def write_cached(name: str, payload: Any) -> None:
    _cache_json(name).write_text(json.dumps(payload))


async def resolve_identity(ticker: str) -> dict[str, Any]:
    """CIK, name and SIC for a ticker, through the application's ticker map and SIC lookup."""
    cached = read_cached(f"identity/{ticker}.json")
    if cached:
        return cached
    from app.services.edgar.company_sic import fetch_company_sic
    from app.services.edgar.compat import sec_edgar_service

    hit = await sec_edgar_service.resolve_ticker(ticker)
    if not hit:
        raise LookupError(f"ticker not found in the SEC ticker map: {ticker}")
    cik = str(hit["cik"]).lstrip("0")
    sic_pair = await fetch_company_sic(cik.zfill(10))
    identity = {
        "ticker": ticker,
        "cik": cik,
        "name": hit.get("name") or hit.get("title") or ticker,
        "sic": sic_pair[0] if sic_pair else None,
        "industry": sic_pair[1] if sic_pair else None,
    }
    write_cached(f"identity/{ticker}.json", identity)
    return identity


async def companyfacts(cik: str) -> dict[str, Any]:
    cached = read_cached(f"companyfacts/CIK{cik.zfill(10)}.json")
    if cached:
        return cached
    from app.services.facts.transport import _fetch_companyfacts_async

    payload = await _fetch_companyfacts_async(cik.zfill(10))
    if not payload:
        raise RuntimeError(f"companyfacts fetch failed for CIK {cik}")
    write_cached(f"companyfacts/CIK{cik.zfill(10)}.json", payload)
    return payload


async def ingest(ticker: str) -> int:
    """Ensure the ticker's facts are in the harness store; returns the Company id."""
    from app.services import facts_service
    from app.services.facts.concepts import _is_financial_sic
    from app.utils.datetimes import utcnow

    identity = await resolve_identity(ticker)
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.ticker == ticker).first()
        if company is not None and company.facts_synced_at is not None:
            return company.id
        payload = await companyfacts(identity["cik"])
        if company is None:
            company = Company(
                ticker=ticker, cik=identity["cik"], name=identity["name"], exchange="", sic=identity["sic"],
            )
            db.add(company)
            db.commit()
        facts, _meta = facts_service.normalize_companyfacts(
            company.id, payload, financial_sic=_is_financial_sic(identity["sic"]),
        )
        facts_service.upsert_facts_bulk(db, facts, commit=False)
        company.facts_synced_at = utcnow()
        db.commit()
        return company.id
    finally:
        db.close()


def latest_annual_window(company_id: int, years: int = 10) -> tuple[str, str]:
    """The UI's "Last 10" annual window (``PeriodPicker.latestRange``): the newest ``years`` fiscal years
    ending at the latest year with core data, where years without core data count toward the cap and
    the window starts at the first year with core data inside it."""
    from app.services.trend_analysis.periods import available_periods

    db = SessionLocal()
    try:
        options = available_periods(db, company_id)["annual"]
    finally:
        db.close()
    enabled = [index for index, option in enumerate(options) if option["has_core"]]
    if len(enabled) < 2:
        raise ValueError("fewer than two fiscal years with core data")
    end = enabled[-1]
    start = next(index for index in enabled if index >= max(0, end - years + 1))
    return options[start]["key"], options[end]["key"]
