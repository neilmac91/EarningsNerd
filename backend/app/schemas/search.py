"""Pydantic schemas for the EDGAR full-text search API."""

from typing import List, Optional

from pydantic import BaseModel


class FullTextSearchHit(BaseModel):
    """A single filing matched by EDGAR full-text search."""

    accession_no: str
    form: Optional[str] = None
    filed_date: Optional[str] = None
    period_ending: Optional[str] = None
    cik: Optional[str] = None
    company: Optional[str] = None
    ticker: Optional[str] = None
    document: Optional[str] = None
    sec_url: Optional[str] = None
    document_url: Optional[str] = None


class FullTextSearchResponse(BaseModel):
    """Response for ``GET /api/search/full-text``."""

    query: str
    total: int  # total filings matching upstream (EDGAR caps deep pagination near 10,000)
    count: int  # number of hits in this page
    hits: List[FullTextSearchHit]
