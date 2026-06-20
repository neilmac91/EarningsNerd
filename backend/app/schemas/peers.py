"""Response schemas for the cross-company peer comparison API (P3/F3)."""

from typing import List, Optional

from pydantic import BaseModel


class PeerEntry(BaseModel):
    ticker: str
    company_name: str
    value: Optional[float] = None
    period_end: Optional[str] = None
    fiscal_year: Optional[int] = None
    is_subject: bool
    rank: Optional[int] = None
    percentile: Optional[float] = None


class PeerComparisonResponse(BaseModel):
    ticker: str
    company_name: str
    sic: Optional[str] = None
    concept: str
    unit: Optional[str] = None
    peer_count: int
    subject: PeerEntry
    peers: List[PeerEntry]
