"""
Unit tests for SEC 10-K Pipeline

Tests cover:
- sec_client.py: 10-K specific methods
- filing_parser.py: 10-K section detection
- markdown_serializer.py: 10-K markdown generation
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# Import modules under test
from app.services.sec_client import SECClient, FilingNotFoundError
from app.services.filing_parser import (
    FilingParser,
    SECTION_PATTERNS_10K,
    SECTION_PATTERNS_10Q,
)
from app.services.markdown_serializer import MarkdownSerializer


class TestFilingParser:
    """Tests for FilingParser 10-K section detection"""

    def setup_method(self):
        self.parser = FilingParser()

    def test_identify_10k_business_section(self):
        """Should identify Item 1. Business section"""
        assert self.parser._identify_section_type(
            "Item 1. Business", "10-K"
        ) == "business"
        assert self.parser._identify_section_type(
            "ITEM 1 BUSINESS", "10-K"
        ) == "business"

    def test_identify_10k_risk_factors_section(self):
        """Should identify Item 1A. Risk Factors section"""
        assert self.parser._identify_section_type(
            "Item 1A. Risk Factors", "10-K"
        ) == "risk_factors"
        assert self.parser._identify_section_type(
            "ITEM 1A RISK FACTORS", "10-K"
        ) == "risk_factors"

    def test_identify_10k_mdna_section(self):
        """Should identify Item 7. MD&A section"""
        assert self.parser._identify_section_type(
            "Item 7. Management's Discussion and Analysis", "10-K"
        ) == "mdna"
        assert self.parser._identify_section_type(
            "MD&A", "10-K"
        ) == "mdna"

    def test_identify_10k_financial_statements(self):
        """Should identify Item 8. Financial Statements section"""
        assert self.parser._identify_section_type(
            "Item 8. Financial Statements and Supplementary Data", "10-K"
        ) == "financial_statements"

    def test_identify_10k_controls(self):
        """Should identify Item 9A. Controls section"""
        assert self.parser._identify_section_type(
            "Item 9A. Controls and Procedures", "10-K"
        ) == "controls"

    def test_identify_10k_exhibits(self):
        """Should identify Item 15. Exhibits section"""
        assert self.parser._identify_section_type(
            "Item 15. Exhibits and Financial Statement Schedules", "10-K"
        ) == "exhibits"

    def test_10q_vs_10k_section_patterns_are_different(self):
        """10-Q and 10-K should have different section patterns"""
        # 10-Q: Item 2 is MD&A
        assert self.parser._identify_section_type(
            "Item 2. Management's Discussion", "10-Q"
        ) == "mdna"

        # 10-K: Item 7 is MD&A
        assert self.parser._identify_section_type(
            "Item 7. Management's Discussion", "10-K"
        ) == "mdna"

    def test_section_patterns_10k_has_business_section(self):
        """10-K patterns should include business section"""
        assert "business" in SECTION_PATTERNS_10K
        assert "business" not in SECTION_PATTERNS_10Q


class TestMarkdownSerializer:
    """Tests for MarkdownSerializer 10-K support"""

    def setup_method(self):
        self.serializer = MarkdownSerializer()

    def test_section_order_10k_exists(self):
        """Should have 10-K section ordering"""
        assert hasattr(self.serializer, "SECTION_ORDER_10K")
        assert len(self.serializer.SECTION_ORDER_10K) > 0

    def test_section_order_10k_has_all_parts(self):
        """10-K section order should cover all parts"""
        section_keys = [k for k, _ in self.serializer.SECTION_ORDER_10K]

        # Part I sections
        assert "business" in section_keys
        assert "risk_factors" in section_keys
        assert "properties" in section_keys
        assert "legal_proceedings" in section_keys

        # Part II sections
        assert "mdna" in section_keys
        assert "market_risk" in section_keys
        assert "financial_statements" in section_keys
        assert "controls" in section_keys

        # Part III sections
        assert "directors" in section_keys
        assert "compensation" in section_keys

        # Part IV sections
        assert "exhibits" in section_keys

    def test_10k_header_includes_fy(self):
        """10-K header should show FY (fiscal year) instead of quarter"""
        metadata = {
            "company_name": "Apple Inc",
            "filing_type": "10-K",
            "fiscal_period": "FY 2023",
        }
        header = self.serializer._render_header(metadata)
        assert "FY 2023" in header
        assert "10-K" in header

    def test_serialize_dispatches_to_10k_method(self):
        """serialize() should call _serialize_10k for 10-K filings"""
        from app.services.filing_parser import ParsedFiling

        parsed = ParsedFiling(
            filing_type="10-K",
            sections={},
            raw_text="",
            metadata={},
            parsing_method="test",
        )
        metadata = {"filing_type": "10-K"}

        with patch.object(
            self.serializer, "_serialize_10k", return_value="10-K content"
        ) as mock_10k:
            result = self.serializer.serialize(parsed, metadata)
            mock_10k.assert_called_once()
            assert result == "10-K content"

    def test_serialize_dispatches_to_10q_method(self):
        """serialize() should call _serialize_10q for 10-Q filings"""
        from app.services.filing_parser import ParsedFiling

        parsed = ParsedFiling(
            filing_type="10-Q",
            sections={},
            raw_text="",
            metadata={},
            parsing_method="test",
        )
        metadata = {"filing_type": "10-Q"}

        with patch.object(
            self.serializer, "_serialize_10q", return_value="10-Q content"
        ) as mock_10q:
            result = self.serializer.serialize(parsed, metadata)
            mock_10q.assert_called_once()
            assert result == "10-Q content"


class TestSECClient:
    """Tests for SECClient 10-K methods"""

    def setup_method(self):
        self.client = SECClient()

    def test_determine_fiscal_period_10k(self):
        """Should return FY for 10-K filings"""
        filing = {
            "report_date": "2023-09-30",
            "filing_type": "10-K",
        }
        assert self.client._determine_fiscal_period(filing) == "FY 2023"

    def test_determine_fiscal_period_10q(self):
        """Should return quarter for 10-Q filings"""
        filing = {
            "report_date": "2023-09-30",
            "filing_type": "10-Q",
        }
        assert self.client._determine_fiscal_period(filing) == "Q3 2023"

    def test_determine_fiscal_period_empty(self):
        """Should return empty string if no report_date"""
        filing = {"filing_type": "10-K"}
        assert self.client._determine_fiscal_period(filing) == ""

    @pytest.mark.asyncio
    async def test_get_latest_10k_returns_filing(self):
        """get_latest_10k should return filing metadata"""
        mock_filings = [
            {
                "accession_number": "0000320193-23-000106",
                "filing_date": "2023-11-03",
                "filing_type": "10-K",
            }
        ]

        with patch.object(
            self.client, "get_cik", new_callable=AsyncMock
        ) as mock_cik, patch.object(
            self.client._rate_limiter, "execute_with_backoff", new_callable=AsyncMock
        ) as mock_rate_limit:
            mock_cik.return_value = "0000320193"
            mock_rate_limit.return_value = mock_filings

            result = await self.client.get_latest_10k("AAPL")

            assert result["accession_number"] == "0000320193-23-000106"
            assert result["filing_type"] == "10-K"

    @pytest.mark.asyncio
    async def test_get_latest_10k_raises_not_found(self):
        """get_latest_10k should raise FilingNotFoundError if no filings"""
        with patch.object(
            self.client, "get_cik", new_callable=AsyncMock
        ) as mock_cik, patch.object(
            self.client._rate_limiter, "execute_with_backoff", new_callable=AsyncMock
        ) as mock_rate_limit:
            mock_cik.return_value = "0000320193"
            mock_rate_limit.return_value = []

            with pytest.raises(FilingNotFoundError):
                await self.client.get_latest_10k("AAPL")

    @pytest.mark.asyncio
    async def test_get_10k_filings_list(self):
        """get_10k_filings should return list of filings"""
        mock_filings = [
            {"accession_number": "1", "filing_type": "10-K"},
            {"accession_number": "2", "filing_type": "10-K"},
        ]

        with patch.object(
            self.client, "get_cik", new_callable=AsyncMock
        ) as mock_cik, patch.object(
            self.client._rate_limiter, "execute_with_backoff", new_callable=AsyncMock
        ) as mock_rate_limit:
            mock_cik.return_value = "0000320193"
            mock_rate_limit.return_value = mock_filings

            result = await self.client.get_10k_filings("AAPL", limit=5)

            assert len(result) == 2
            assert result[0]["filing_type"] == "10-K"


# Note: _determine_fiscal_period tests are now in TestSECClient
# since the function was consolidated into sec_client.py
