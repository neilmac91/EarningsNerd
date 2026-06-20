"""Response schemas for the fundamentals time-series API (P3/F5)."""

from typing import List, Optional

from pydantic import BaseModel


class FundamentalPoint(BaseModel):
    period_end: Optional[str] = None
    fiscal_year: Optional[int] = None
    fiscal_period: Optional[str] = None
    value: Optional[float] = None
    unit: str
    form: Optional[str] = None
    accession: str


class FundamentalSeries(BaseModel):
    concept: str
    unit: str
    points: List[FundamentalPoint]


class FundamentalsResponse(BaseModel):
    ticker: str
    company_name: str
    concepts: List[FundamentalSeries]
