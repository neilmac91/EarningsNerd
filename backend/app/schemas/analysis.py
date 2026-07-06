"""Request/response schemas for Multi-Period Analysis (`/api/analysis`).

The dataset itself is returned as the service's dict (its deep shape feeds the frontend grid,
the charts AND the AI prompt — a single source of truth documented in
``trend_analysis_service.build_dataset``); coverage and requests are typed here.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class AnnualCoveragePeriod(BaseModel):
    key: str  # "FY2024"
    fiscal_year: int
    period_end: str
    # True when the year has a top line (revenue OR net interest income) AND net income —
    # the minimum for a meaningful analysis; the picker greys out years without it.
    has_core: bool


class QuarterlyCoveragePeriod(BaseModel):
    key: str  # "2024Q2"
    fiscal_year: int
    fiscal_period: str
    period_end: str
    # True when EVERY value in the column is Q4-derived (from the annual report: FY − YTD9 or
    # FY − ΣQ1–3; EPS shares-based) — badged in the picker.
    derived: bool


class CoverageLimits(BaseModel):
    annual: int
    quarterly: int


class CoverageResponse(BaseModel):
    ticker: str
    company_name: str
    # False → nothing to analyze: reason is "ifrs_filer" (foreign IFRS filer, v1-unsupported) or
    # "no_facts" (no US-GAAP history found).
    supported: bool
    reason: Optional[str] = None
    # True → the first-touch companyfacts sync exceeded the request budget and continues in the
    # background; the client should retry shortly.
    syncing: bool = False
    synced_at: Optional[str] = None
    annual: List[AnnualCoveragePeriod] = Field(default_factory=list)
    quarterly: List[QuarterlyCoveragePeriod] = Field(default_factory=list)
    limits: CoverageLimits


class DatasetRequest(BaseModel):
    mode: Literal["annual", "quarterly"]
    start_period: str = Field(min_length=4, max_length=8)  # "FY2016" | "2023Q2"
    end_period: str = Field(min_length=4, max_length=8)


class StreamRequest(DatasetRequest):
    # Regenerate even when a cached narrative matches (metered; the "Refresh analysis" button).
    force: bool = False
