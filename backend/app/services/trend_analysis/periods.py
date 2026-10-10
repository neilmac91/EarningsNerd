"""Period keys, concept labels and available-period coverage."""
from __future__ import annotations

import re
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import FinancialFact


MODES = ("annual", "quarterly")


_QUARTERS = ("Q1", "Q2", "Q3", "Q4")


# Display order for the dataset grid (missing concepts are simply omitted).
DATASET_CONCEPT_ORDER: tuple[str, ...] = (
    "revenue",
    "net_interest_income", "noninterest_income", "premiums_earned", "net_investment_income",
    "gross_profit", "gross_margin",
    "operating_income", "operating_margin",
    "net_income", "net_margin",
    "earnings_per_share", "eps_diluted",
    "operating_cash_flow", "capital_expenditures", "free_cash_flow",
    "investing_cash_flow", "financing_cash_flow",
    "total_assets", "cash_and_equivalents",
    "current_assets", "current_liabilities", "working_capital", "current_ratio",
    "long_term_debt", "shareholders_equity",
)


_CONCEPT_LABELS: dict[str, str] = {
    "revenue": "Revenue",
    "net_interest_income": "Net interest income",
    "noninterest_income": "Noninterest income",
    "premiums_earned": "Premiums earned",
    "net_investment_income": "Net investment income",
    "gross_profit": "Gross profit",
    "gross_margin": "Gross margin",
    "operating_income": "Operating income",
    "operating_margin": "Operating margin",
    "net_income": "Net income",
    "net_margin": "Net margin",
    "earnings_per_share": "EPS (basic)",
    "eps_diluted": "EPS (diluted)",
    "operating_cash_flow": "Operating cash flow",
    "capital_expenditures": "Capital expenditures",
    "free_cash_flow": "Free cash flow",
    "investing_cash_flow": "Investing cash flow",
    "financing_cash_flow": "Financing cash flow",
    "total_assets": "Total assets",
    "cash_and_equivalents": "Cash & equivalents",
    "current_assets": "Current assets",
    "current_liabilities": "Current liabilities",
    "working_capital": "Working capital",
    "current_ratio": "Current ratio",
    "long_term_debt": "Long-term debt",
    "shareholders_equity": "Shareholders' equity",
}


def concept_label(concept: str) -> str:
    return _CONCEPT_LABELS.get(concept, concept.replace("_", " ").title())


# --- period keys -------------------------------------------------------------------------------

_ANNUAL_KEY_RE = re.compile(r"^FY(\d{4})$")


_QUARTER_KEY_RE = re.compile(r"^(\d{4})(Q[1-4])$")


def parse_period_key(mode: str, key: str) -> tuple[int, Optional[str]]:
    """"FY2024" -> (2024, None); "2024Q2" -> (2024, "Q2"). Raises ValueError on a bad key."""
    if mode == "annual":
        match = _ANNUAL_KEY_RE.match(key or "")
        if not match:
            raise ValueError(f"Invalid annual period key: {key!r} (expected e.g. 'FY2024')")
        return int(match.group(1)), None
    match = _QUARTER_KEY_RE.match(key or "")
    if not match:
        raise ValueError(f"Invalid quarterly period key: {key!r} (expected e.g. '2024Q2')")
    return int(match.group(1)), match.group(2)


def _period_sort_key(bucket: dict[str, Any]) -> tuple:
    return (bucket["period_end"], bucket["fiscal_period"] or "")


# --- coverage ----------------------------------------------------------------------------------

_CORE_REVENUE_CONCEPTS = ("revenue", "net_interest_income")  # generic top line OR the FI one


def available_periods(db: Session, company_id: int) -> dict[str, Any]:
    """Selectable periods per mode, oldest → newest (one indexed read on the series index)."""
    rows = (
        db.query(
            FinancialFact.concept,
            FinancialFact.fiscal_year,
            FinancialFact.fiscal_period,
            FinancialFact.period_end,
            FinancialFact.source,
        )
        .filter(
            FinancialFact.company_id == company_id,
            FinancialFact.is_latest.is_(True),
            FinancialFact.fiscal_period.isnot(None),
        )
        .all()
    )

    annual: dict[int, dict[str, Any]] = {}
    quarterly: dict[tuple[int, str], dict[str, Any]] = {}
    for concept, fiscal_year, fiscal_period, period_end, source in rows:
        if fiscal_year is None or period_end is None:
            continue
        if fiscal_period == "FY":
            entry = annual.setdefault(
                fiscal_year,
                {"fiscal_year": fiscal_year, "period_end": period_end, "concepts": set()},
            )
            entry["period_end"] = max(entry["period_end"], period_end)
            entry["concepts"].add(concept)
        elif fiscal_period in _QUARTERS:
            entry = quarterly.setdefault(
                (fiscal_year, fiscal_period),
                {
                    "fiscal_year": fiscal_year,
                    "fiscal_period": fiscal_period,
                    "period_end": period_end,
                    "derived": True,
                },
            )
            entry["period_end"] = max(entry["period_end"], period_end)
            # A quarter column is "derived" only if EVERY row in it came from the Q4 derivation.
            if source != "derived":
                entry["derived"] = False

    annual_out = [
        {
            "key": f"FY{entry['fiscal_year']}",
            "fiscal_year": entry["fiscal_year"],
            "period_end": entry["period_end"].isoformat(),
            "has_core": (
                any(c in entry["concepts"] for c in _CORE_REVENUE_CONCEPTS)
                and "net_income" in entry["concepts"]
            ),
        }
        for entry in sorted(annual.values(), key=lambda e: e["period_end"])
    ]
    quarterly_out = [
        {
            "key": f"{entry['fiscal_year']}{entry['fiscal_period']}",
            "fiscal_year": entry["fiscal_year"],
            "fiscal_period": entry["fiscal_period"],
            "period_end": entry["period_end"].isoformat(),
            "derived": entry["derived"],
        }
        for entry in sorted(quarterly.values(), key=lambda e: e["period_end"])
    ]
    return {"annual": annual_out, "quarterly": quarterly_out}
