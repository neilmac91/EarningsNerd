"""The primary document of each filing a dataset's facts cite, read from the company's own filing rows."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Filing
from app.services.fact_provenance import source_accessions
from app.utils.sec_urls import normalize_accession


def filing_documents(db: Session, company_id: int, facts: Iterable[Any]) -> dict[str, str]:
    """Map each accession these facts and their operands cite, dashless, to its filing's document.

    One ORM read of the company's filings, with the accession compared dashless on both sides, so
    a dashed and a dashless spelling of one filing meet. An accession with no row here is left
    out, and ``fact_provenance`` keeps its accession folder. ``document_url`` is used as stored: the
    filings table's listeners checked it where it entered. Database rows only, no SEC request.
    """
    keys = source_accessions(facts)
    if not keys:
        return {}
    rows = (
        db.query(Filing.accession_number, Filing.document_url)
        .filter(Filing.company_id == company_id, func.replace(Filing.accession_number, "-", "").in_(sorted(keys)))
        .order_by(Filing.id)  # Two spellings of one accession then resolve alike on every read.
        .all()
    )
    return {normalize_accession(accession): document_url for accession, document_url in rows}
