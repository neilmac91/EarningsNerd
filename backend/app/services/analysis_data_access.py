"""Analysis database reads and short-session units; HTTP policy stays in the router."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from logging import Logger
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from app.models import Company

if TYPE_CHECKING:
    from app.models import TrendAnalysis


def find_company(db: Session, ticker: str) -> Company | None:
    return db.query(Company).filter(Company.ticker == ticker.upper()).first()


def release_coverage_read(db: Session) -> None:
    db.close()


def facts_synced_at(db: Session, company_id: int) -> datetime | None:
    return db.query(Company.facts_synced_at).filter(Company.id == company_id).scalar()


def find_analysis(db: Session, analysis_id: int) -> TrendAnalysis | None:
    from app.models import TrendAnalysis

    return db.get(TrendAnalysis, analysis_id)


def find_company_by_id(db: Session, company_id: int) -> Company | None:
    return db.get(Company, company_id)


async def ingest_with_own_session(
    company_id: int,
    *,
    ingest_companyfacts_by_id: Callable[..., Awaitable[dict]],
) -> dict:
    """Run companyfacts ingest in short DB units so it can safely outlive the request."""
    from app.database import SessionLocal

    return await ingest_companyfacts_by_id(
        company_id, session_factory=SessionLocal
    )


def meter_analysis_best_effort(
    user_id: int,
    token: str | None = None,
    *,
    convert_reservation: Callable[[str | None, Session], str | None],
    get_current_month: Callable[[], str],
    increment_user_analysis: Callable[[int, str, Session], None],
    logger: Logger,
) -> bool:
    """Meter one FRESH analysis generation in a fresh DB session (best-effort — a metering failure
    must never break the stream the user already received). Converts the admission lease
    (``token``) in the same commit; returns whether it did, so the caller can release otherwise."""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        month = convert_reservation(token, db) or get_current_month()
        increment_user_analysis(user_id, month, db)
        return True
    except Exception:  # noqa: BLE001 - metering must not break the stream
        logger.warning("Failed to meter analysis for user %s", user_id, exc_info=True)
        return False
    finally:
        db.close()


def release_reservation_best_effort(
    token: str | None,
    *,
    release_reservation: Callable[[str | None, Session], None],
    logger: Logger,
) -> None:
    """Give an admission lease back (fresh session; the lease expires on its own if this fails)."""
    if not token:
        return
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        release_reservation(token, db)
    except Exception:  # noqa: BLE001 - never mask the stream outcome
        logger.warning("Could not release an analysis admission reservation", exc_info=True)
    finally:
        db.close()
