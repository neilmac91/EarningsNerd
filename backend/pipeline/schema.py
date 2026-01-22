from __future__ import annotations

from pydantic import BaseModel
from typing import Optional, List, Literal

NumberUnit = Literal["USD", "PCT", "EPS", "COUNT"]


class Metric(BaseModel):
    label: str
    unit: NumberUnit
    current: Optional[float] = None
    prior: Optional[float] = None
    delta_abs: Optional[float] = None
    delta_pct: Optional[float] = None
    material: bool = False
    source_anchors: List[str] = []  # e.g., ["10-Q p.17 Results of Operations"]


class Financials(BaseModel):
    revenue: Optional[Metric] = None
    gross_margin: Optional[Metric] = None
    operating_income: Optional[Metric] = None
    net_income: Optional[Metric] = None
    eps_basic: Optional[Metric] = None
    eps_diluted: Optional[Metric] = None
    free_cash_flow: Optional[Metric] = None
    has_prior: bool = False


class Liquidity(BaseModel):
    cash: Optional[Metric] = None
    debt: Optional[Metric] = None
    current_ratio: Optional[Metric] = None


class Risks(BaseModel):
    items: List[str] = []
    citations: List[str] = []


class Outlook(BaseModel):
    guidance_summary: Optional[str] = None
    catalysts: List[str] = []


class FilingSummary(BaseModel):
    cik: str
    symbol: str
    company_name: str
    filing_type: Literal["10-Q", "10-K"]
    filing_date: str
    period_end: Optional[str] = None
    financials: Financials
    liquidity: Optional[Liquidity] = None
    risks: Risks
    outlook: Outlook
    sources: List[str] = []
