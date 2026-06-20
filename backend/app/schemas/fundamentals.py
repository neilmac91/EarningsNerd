"""Pydantic schemas for the multi-year fundamentals timeline API."""

from typing import List, Optional

from pydantic import BaseModel


class FundamentalPoint(BaseModel):
    fiscal_year: int
    period_end: str
    value: float


class MetricSeries(BaseModel):
    metric: str
    label: str
    unit: str  # "USD" | "USD/share" | "percent"
    points: List[FundamentalPoint]


class FundamentalsTimelineResponse(BaseModel):
    """Response for ``GET /api/companies/{ticker}/fundamentals``."""

    ticker: str
    cik: str
    company_name: Optional[str] = None
    metrics: List[MetricSeries]
