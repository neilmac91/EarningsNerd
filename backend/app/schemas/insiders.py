"""Response schemas for the insider-activity API (P4, Form 4)."""

from typing import List, Optional

from pydantic import BaseModel


class InsiderTransaction(BaseModel):
    """A single open-market insider trade parsed from a Form 4 filing."""

    insider_name: Optional[str] = None
    insider_title: Optional[str] = None
    is_director: Optional[bool] = None
    is_officer: Optional[bool] = None
    is_ten_pct_owner: Optional[bool] = None
    ticker: Optional[str] = None
    transaction_date: Optional[str] = None
    transaction_code: Optional[str] = None
    transaction_label: Optional[str] = None
    shares: Optional[float] = None
    price: Optional[float] = None
    value: Optional[float] = None
    acquired_disposed: Optional[str] = None
    is_10b5_1: Optional[bool] = None
    accession: Optional[str] = None
    filed_date: Optional[str] = None


class InsiderActivitySummary(BaseModel):
    """Aggregated buy/sell signal over a trailing window, with a 10b5-1 split."""

    window_days: int
    buy_count: int
    sell_count: int
    buy_shares: float
    sell_shares: float
    buy_value: Optional[float] = None
    sell_value: Optional[float] = None
    net_shares: float
    net_value: Optional[float] = None
    discretionary_net_shares: float
    plan_10b5_1_sell_shares: float
    last_transaction_date: Optional[str] = None


class InsiderActivityResponse(BaseModel):
    ticker: str
    company_name: Optional[str] = None
    cik: Optional[str] = None
    window_days: int
    summary: InsiderActivitySummary
    transactions: List[InsiderTransaction]
    total_transactions: int
