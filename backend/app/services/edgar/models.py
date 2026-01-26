"""
EdgarTools Domain Models

Typed dataclasses representing SEC EDGAR entities.
These provide a clean, consistent interface regardless of
the underlying data source (EdgarTools, legacy services, etc.).

All models use dataclasses for:
- Immutability (frozen=True where appropriate)
- Type safety
- Easy serialization
- IDE autocompletion
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from .config import FilingType


@dataclass
class Company:
    """
    Represents a company registered with the SEC.

    Attributes:
        cik: Central Index Key (10-digit, zero-padded)
        ticker: Primary stock ticker symbol
        name: Company legal name
        sic_code: Standard Industrial Classification code
        sic_description: Human-readable industry description
        state_of_incorporation: State where incorporated
        fiscal_year_end: Month-day of fiscal year end (e.g., "12-31")
        exchange: Stock exchange (NYSE, NASDAQ, etc.)
    """
    cik: str
    ticker: str
    name: str
    sic_code: Optional[str] = None
    sic_description: Optional[str] = None
    state_of_incorporation: Optional[str] = None
    fiscal_year_end: Optional[str] = None
    exchange: Optional[str] = None

    def __post_init__(self):
        # Ensure CIK is zero-padded to 10 digits
        if self.cik and not self.cik.startswith("0"):
            object.__setattr__(self, "cik", self.cik.zfill(10))
        # Normalize ticker to uppercase
        if self.ticker:
            object.__setattr__(self, "ticker", self.ticker.upper())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "cik": self.cik,
            "ticker": self.ticker,
            "name": self.name,
            "sic_code": self.sic_code,
            "sic_description": self.sic_description,
            "state_of_incorporation": self.state_of_incorporation,
            "fiscal_year_end": self.fiscal_year_end,
            "exchange": self.exchange,
        }


@dataclass
class Filing:
    """
    Represents an SEC filing.

    Attributes:
        accession_number: Unique filing identifier (format: 0000000000-00-000000)
        filing_type: Type of filing (10-K, 10-Q, etc.)
        filing_date: Date the filing was submitted to SEC
        period_end_date: End of the reporting period
        ticker: Company ticker symbol
        cik: Company CIK
        company_name: Company name at time of filing
        document_url: URL to the primary filing document
        sec_url: URL to the SEC filing page
    """
    accession_number: str
    filing_type: FilingType
    filing_date: date
    ticker: str
    cik: str
    period_end_date: Optional[date] = None
    company_name: Optional[str] = None
    document_url: Optional[str] = None
    sec_url: Optional[str] = None

    @property
    def fiscal_period(self) -> str:
        """
        Determine the fiscal period label (Q1 2024, FY 2024, etc.).
        """
        if not self.period_end_date:
            return ""

        year = self.period_end_date.year
        month = self.period_end_date.month

        if self.filing_type.is_annual:
            return f"FY {year}"

        # Determine quarter based on month
        if month <= 3:
            return f"Q1 {year}"
        elif month <= 6:
            return f"Q2 {year}"
        elif month <= 9:
            return f"Q3 {year}"
        else:
            return f"Q4 {year}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "accession_number": self.accession_number,
            "filing_type": self.filing_type.value,
            "filing_date": self.filing_date.isoformat() if self.filing_date else None,
            "period_end_date": self.period_end_date.isoformat() if self.period_end_date else None,
            "report_date": self.period_end_date.isoformat() if self.period_end_date else None,  # Alias for compatibility
            "ticker": self.ticker,
            "cik": self.cik,
            "company_name": self.company_name,
            "document_url": self.document_url,
            "sec_url": self.sec_url,
            "fiscal_period": self.fiscal_period,
        }


@dataclass
class FinancialMetric:
    """
    Represents a single financial metric value.

    Attributes:
        name: Metric name (e.g., "Revenue", "NetIncome")
        value: Numeric value
        period_end: End date of the period
        period_type: "annual", "quarterly", or "TTM"
        unit: Unit of measurement (USD, shares, percent)
        form: Source form type (10-K, 10-Q)
        accession_number: Source filing accession number
    """
    name: str
    value: float
    period_end: date
    period_type: str = "quarterly"
    unit: str = "USD"
    form: Optional[str] = None
    accession_number: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "period": self.period_end.isoformat() if self.period_end else None,
            "value": self.value,
            "form": self.form,
            "accn": self.accession_number,
        }


@dataclass
class MetricChange:
    """
    Represents the change between two periods for a metric.

    This provides objective, factual change calculations
    with no interpretive language.
    """
    absolute: Optional[float] = None
    percentage: Optional[float] = None
    direction: Optional[str] = None  # "increase", "decrease", "unchanged"

    @staticmethod
    def compute(
        current_value: Optional[float],
        prior_value: Optional[float]
    ) -> "MetricChange":
        """
        Compute period-over-period change.

        Args:
            current_value: Current period value
            prior_value: Prior period value

        Returns:
            MetricChange with computed values
        """
        if current_value is None or prior_value is None:
            return MetricChange()

        if prior_value == 0:
            direction = "increase" if current_value > 0 else (
                "decrease" if current_value < 0 else "unchanged"
            )
            return MetricChange(
                absolute=round(current_value, 2),
                direction=direction,
            )

        absolute_change = current_value - prior_value
        percentage_change = (absolute_change / abs(prior_value)) * 100

        if absolute_change > 0:
            direction = "increase"
        elif absolute_change < 0:
            direction = "decrease"
        else:
            direction = "unchanged"

        return MetricChange(
            absolute=round(absolute_change, 2),
            percentage=round(percentage_change, 2),
            direction=direction,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "absolute": self.absolute,
            "percentage": self.percentage,
            "direction": self.direction,
        }


@dataclass
class MetricSeries:
    """
    Represents a time series of a financial metric.

    Includes current value, prior value, change calculation,
    and the full historical series.
    """
    metric_name: str
    current: Optional[FinancialMetric] = None
    prior: Optional[FinancialMetric] = None
    change: Optional[MetricChange] = None
    series: List[FinancialMetric] = field(default_factory=list)

    def __post_init__(self):
        # Auto-compute change if not provided
        if self.current and self.prior and not self.change:
            object.__setattr__(
                self,
                "change",
                MetricChange.compute(self.current.value, self.prior.value)
            )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        result = {}
        if self.current:
            result["current"] = self.current.to_dict()
        if self.prior:
            result["prior"] = self.prior.to_dict()
        if self.change:
            result["change"] = self.change.to_dict()
        if self.series:
            result["series"] = [m.to_dict() for m in self.series]
        return result


@dataclass
class XBRLData:
    """
    Represents XBRL financial data extracted from a filing.

    This is the primary structure returned by XBRL extraction,
    containing all key financial metrics organized by category.
    """
    revenue: List[FinancialMetric] = field(default_factory=list)
    net_income: List[FinancialMetric] = field(default_factory=list)
    total_assets: List[FinancialMetric] = field(default_factory=list)
    total_liabilities: List[FinancialMetric] = field(default_factory=list)
    cash_and_equivalents: List[FinancialMetric] = field(default_factory=list)
    earnings_per_share: List[FinancialMetric] = field(default_factory=list)

    def to_dict(self) -> Dict[str, List[Dict]]:
        """
        Convert to dictionary format compatible with existing API.

        Returns format:
        {
            "revenue": [{"period": "2024-03-31", "value": 123456, "form": "10-K", "accn": "..."}, ...],
            ...
        }
        """
        return {
            "revenue": [m.to_dict() for m in self.revenue],
            "net_income": [m.to_dict() for m in self.net_income],
            "total_assets": [m.to_dict() for m in self.total_assets],
            "total_liabilities": [m.to_dict() for m in self.total_liabilities],
            "cash_and_equivalents": [m.to_dict() for m in self.cash_and_equivalents],
            "earnings_per_share": [m.to_dict() for m in self.earnings_per_share],
        }

    def is_empty(self) -> bool:
        """Check if all metric lists are empty."""
        return not any([
            self.revenue,
            self.net_income,
            self.total_assets,
            self.total_liabilities,
            self.cash_and_equivalents,
            self.earnings_per_share,
        ])


@dataclass
class StandardizedMetrics:
    """
    Standardized financial metrics with current/prior/change computations.

    This is the final output format for financial analysis.
    """
    revenue: Optional[MetricSeries] = None
    net_income: Optional[MetricSeries] = None
    earnings_per_share: Optional[MetricSeries] = None
    net_margin: Optional[MetricSeries] = None

    def to_dict(self) -> Dict[str, Dict]:
        """Convert to dictionary for API responses."""
        result = {}
        if self.revenue:
            result["revenue"] = self.revenue.to_dict()
        if self.net_income:
            result["net_income"] = self.net_income.to_dict()
        if self.earnings_per_share:
            result["earnings_per_share"] = self.earnings_per_share.to_dict()
        if self.net_margin:
            result["net_margin"] = self.net_margin.to_dict()
        return result
