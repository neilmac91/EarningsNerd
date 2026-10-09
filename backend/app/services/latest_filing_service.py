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
from app.services.summary_placeholders import is_summary_placeholder

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

    ready_ids = {
        filing_id
        for filing_id, overview in db.query(Summary.filing_id, Summary.business_overview)
        .filter(Summary.filing_id.in_([filing.id for filing in picked.values()]))
        .all()
        if overview and overview.strip() and not is_summary_placeholder(overview)
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
