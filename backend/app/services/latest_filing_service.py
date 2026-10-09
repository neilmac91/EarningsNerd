"""A company's latest filing, as its filings list would show it.

One definition of the forms a company's filings list serves (``company_list_forms``), shared by
``GET /api/filings/company/{ticker}`` and the company search, so the search can name the filing a
visitor lands on: the newest stored filing of those forms that still stands (not superseded by an
amendment), with whether its summary is ready. DB-only: it reads the rows the filings list already
serves and never calls SEC.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Filing, Summary
from app.services.filing_amendment_service import expand_amendment_forms
from app.services.summary_placeholders import is_summary_ready

DOMESTIC_FORMS = ["10-K", "10-Q"]
# Foreign private issuers: 20-F annual, 6-K interim, 40-F (tasks/fpi-support-roadmap.md).
FPI_FORMS = ["20-F", "6-K", "40-F"]


def company_list_forms() -> list[str]:
    """The forms a company's filings list serves by default, amendments included."""
    return expand_amendment_forms(DOMESTIC_FORMS + (FPI_FORMS if settings.ENABLE_FPI_FILINGS else []))


class LatestFilingRef(BaseModel):
    """The filing a search result leads to, in the filings list's own fields and serialization."""

    id: int
    filing_type: str
    filing_date: Optional[str]
    report_date: Optional[str]
    summary_ready: bool


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def latest_filings(db: Session, company_ids: list[int]) -> dict[int, LatestFilingRef]:
    """Each company's newest standing filing of the list's forms, keyed by company id.

    Companies with no such stored filing are absent. Ties on the filed date resolve to the highest
    row id, the rule the company page's selectRecommendedFiling applies too, so a result names the
    filing the page leads with. Three queries for the whole result set, never one per company.
    """
    if not company_ids:
        return {}
    forms = company_list_forms()
    standing = (
        Filing.company_id.in_(company_ids),
        Filing.filing_type.in_(forms),
        Filing.superseded_by_accession.is_(None),
    )
    newest = (
        db.query(Filing.company_id, func.max(Filing.filing_date).label("filed"))
        .filter(*standing)
        .group_by(Filing.company_id)
        .subquery()
    )
    rows = (
        db.query(Filing)
        .join(newest, (Filing.company_id == newest.c.company_id) & (Filing.filing_date == newest.c.filed))
        .filter(*standing)
        .order_by(Filing.id.desc())
        .all()
    )
    picked: dict[int, Filing] = {}
    for filing in rows:
        picked.setdefault(filing.company_id, filing)
    if not picked:
        return {}

    # Ready means the filing page will show the summary (is_summary_ready, the rule the company page's
    # lead mirrors): no in-progress marker, no failure filler, and no raw_summary.writer_error, which
    # that page shows as "Summary temporarily unavailable" whatever the body says. The flag is read in
    # the database, so the search never loads a raw_summary. (The page also fails a body left empty
    # once the legacy writer's notices are stripped; no renderer writes one.)
    writer_error = Summary.raw_summary["writer_error"].as_string()
    ready_ids = {
        filing_id
        for filing_id, overview, failed in db.query(Summary.filing_id, Summary.business_overview, writer_error)
        .filter(Summary.filing_id.in_([filing.id for filing in picked.values()]))
        .all()
        if is_summary_ready(overview, failed)
    }
    return {
        company_id: LatestFilingRef(
            id=filing.id,
            filing_type=filing.filing_type,
            filing_date=_iso(filing.filing_date),
            report_date=_iso(filing.period_end_date),
            summary_ready=filing.id in ready_ids,
        )
        for company_id, filing in picked.items()
    }
