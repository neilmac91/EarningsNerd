"""
Tests for EdgarTools Integration

These tests verify that the new EdgarTools-based services work correctly
and maintain backward compatibility with the legacy interfaces.
"""

import pytest
from datetime import date
from unittest.mock import Mock, patch, AsyncMock

# Test the models
from app.services.edgar.models import (
    Company,
    Filing,
    FinancialMetric,
    MetricChange,
    XBRLData,
)
from app.services.edgar.config import FilingType
from app.services.edgar.exceptions import (
    EdgarError,
    CompanyNotFoundError,
    FilingNotFoundError,
    EdgarRateLimitError,
)


class TestFilingType:
    """Test the FilingType enum."""

    def test_basic_values(self):
        assert FilingType.FORM_10K.value == "10-K"
        assert FilingType.FORM_10Q.value == "10-Q"
        assert FilingType.FORM_8K.value == "8-K"

    def test_is_annual(self):
        assert FilingType.FORM_10K.is_annual is True
        assert FilingType.FORM_10K_AMENDED.is_annual is True
        assert FilingType.FORM_10Q.is_annual is False

    def test_is_quarterly(self):
        assert FilingType.FORM_10Q.is_quarterly is True
        assert FilingType.FORM_10K.is_quarterly is False

    def test_is_insider(self):
        assert FilingType.FORM_3.is_insider is True
        assert FilingType.FORM_4.is_insider is True
        assert FilingType.FORM_5.is_insider is True
        assert FilingType.FORM_10K.is_insider is False

    def test_is_amended(self):
        assert FilingType.FORM_10K_AMENDED.is_amended is True
        assert FilingType.FORM_10K.is_amended is False

    def test_from_string(self):
        assert FilingType.from_string("10-K") == FilingType.FORM_10K
        assert FilingType.from_string("10-Q") == FilingType.FORM_10Q
        assert FilingType.from_string("10K") == FilingType.FORM_10K
        assert FilingType.from_string("10k") == FilingType.FORM_10K

    def test_from_string_invalid(self):
        with pytest.raises(ValueError):
            FilingType.from_string("invalid")


class TestCompanyModel:
    """Test the Company domain model."""

    def test_creation(self):
        company = Company(
            cik="320193",
            ticker="aapl",
            name="Apple Inc.",
        )
        # CIK should be zero-padded
        assert company.cik == "0000320193"
        # Ticker should be uppercase
        assert company.ticker == "AAPL"
        assert company.name == "Apple Inc."

    def test_to_dict(self):
        company = Company(
            cik="0000320193",
            ticker="AAPL",
            name="Apple Inc.",
            sic_code="3571",
        )
        d = company.to_dict()
        assert d["cik"] == "0000320193"
        assert d["ticker"] == "AAPL"
        assert d["name"] == "Apple Inc."
        assert d["sic_code"] == "3571"


class TestFilingModel:
    """Test the Filing domain model."""

    def test_creation(self):
        filing = Filing(
            accession_number="0000320193-24-000123",
            filing_type=FilingType.FORM_10K,
            filing_date=date(2024, 1, 15),
            ticker="AAPL",
            cik="0000320193",
            period_end_date=date(2023, 12, 31),
        )
        assert filing.accession_number == "0000320193-24-000123"
        assert filing.filing_type == FilingType.FORM_10K
        assert filing.ticker == "AAPL"

    def test_fiscal_period_annual(self):
        filing = Filing(
            accession_number="0000320193-24-000123",
            filing_type=FilingType.FORM_10K,
            filing_date=date(2024, 1, 15),
            ticker="AAPL",
            cik="0000320193",
            period_end_date=date(2023, 12, 31),
        )
        assert filing.fiscal_period == "FY 2023"

    def test_fiscal_period_quarterly(self):
        filing = Filing(
            accession_number="0000320193-24-000123",
            filing_type=FilingType.FORM_10Q,
            filing_date=date(2024, 4, 15),
            ticker="AAPL",
            cik="0000320193",
            period_end_date=date(2024, 3, 31),
        )
        assert filing.fiscal_period == "Q1 2024"


class TestMetricChange:
    """Test the MetricChange computation."""

    def test_compute_increase(self):
        change = MetricChange.compute(150.0, 100.0)
        assert change.absolute == 50.0
        assert change.percentage == 50.0
        assert change.direction == "increase"

    def test_compute_decrease(self):
        change = MetricChange.compute(80.0, 100.0)
        assert change.absolute == -20.0
        assert change.percentage == -20.0
        assert change.direction == "decrease"

    def test_compute_unchanged(self):
        change = MetricChange.compute(100.0, 100.0)
        assert change.absolute == 0.0
        assert change.percentage == 0.0
        assert change.direction == "unchanged"

    def test_compute_with_none_values(self):
        change = MetricChange.compute(None, 100.0)
        assert change.absolute is None
        assert change.percentage is None
        assert change.direction is None

    def test_compute_with_zero_prior(self):
        change = MetricChange.compute(100.0, 0.0)
        assert change.absolute == 100.0
        assert change.percentage is None
        assert change.direction == "increase"


class TestExceptions:
    """Test the exception hierarchy."""

    def test_edgar_error_base(self):
        error = EdgarError("Test error", code="TEST_ERROR")
        assert str(error) == "Test error"
        assert error.code == "TEST_ERROR"
        assert error.timestamp is not None

    def test_company_not_found(self):
        error = CompanyNotFoundError("INVALID")
        assert "INVALID" in str(error)
        assert error.code == "COMPANY_NOT_FOUND"
        assert error.ticker == "INVALID"

    def test_filing_not_found(self):
        error = FilingNotFoundError("AAPL", "10-K")
        assert "AAPL" in str(error)
        assert "10-K" in str(error)
        assert error.code == "FILING_NOT_FOUND"

    def test_rate_limit_error(self):
        error = EdgarRateLimitError(retry_after=120)
        assert error.retry_after == 120
        assert error.code == "EDGAR_RATE_LIMITED"

    def test_exception_to_dict(self):
        error = EdgarError("Test", context={"key": "value"})
        d = error.to_dict()
        assert d["message"] == "Test"
        assert d["context"]["key"] == "value"
        assert "timestamp" in d


class TestXBRLData:
    """Test the XBRLData model."""

    def test_empty_check(self):
        xbrl = XBRLData()
        assert xbrl.is_empty() is True

    def test_not_empty(self):
        xbrl = XBRLData(
            revenue=[
                FinancialMetric(
                    name="Revenue",
                    value=100000.0,
                    period_end=date(2024, 3, 31),
                )
            ]
        )
        assert xbrl.is_empty() is False

    def test_to_dict(self):
        xbrl = XBRLData(
            revenue=[
                FinancialMetric(
                    name="Revenue",
                    value=100000.0,
                    period_end=date(2024, 3, 31),
                    accession_number="0000320193-24-000123",
                )
            ]
        )
        d = xbrl.to_dict()
        assert "revenue" in d
        assert len(d["revenue"]) == 1
        assert d["revenue"][0]["value"] == 100000.0


class TestBackwardCompatibility:
    """Test backward compatibility with legacy interfaces."""

    def test_xbrl_cache_functions(self):
        """Test that cache functions are exported correctly."""
        from app.services.edgar import clear_xbrl_cache, get_xbrl_cache_stats

        # Should not raise
        stats = get_xbrl_cache_stats()
        assert "total_entries" in stats
        assert "valid_entries" in stats

    def test_compat_imports(self):
        """Test that compat module provides expected interfaces."""
        from app.services.edgar.compat import (
            sec_edgar_service,
            xbrl_service,
        )

        # Should have expected methods
        assert hasattr(sec_edgar_service, "search_company")
        assert hasattr(sec_edgar_service, "get_filings")
        assert hasattr(xbrl_service, "get_xbrl_data")
        assert hasattr(xbrl_service, "extract_standardized_metrics")
