"""
Stocktwits and FMP Integration Tests

Tests for the Stocktwits and Financial Modeling Prep (FMP) API integrations
used by the Market Movers feature.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.integrations.stocktwits import (
    StocktwitsClient,
    StocktwitsSymbol,
    stocktwits_client,
)
from app.integrations.fmp import (
    FMPClient,
    FMPProfile,
    FMPEtf,
    fmp_client,
)


class TestStocktwitsClient:
    """Tests for StocktwitsClient."""

    @pytest.fixture
    def client(self):
        """Create a Stocktwits client for testing."""
        return StocktwitsClient(timeout_seconds=5.0)

    def test_pre_filter_removes_crypto(self, client):
        """Pre-filter should remove crypto symbols (.X suffix)."""
        symbols = [
            StocktwitsSymbol(symbol="BTC.X", title="Bitcoin", watchlist_count=1000, raw={}),
            StocktwitsSymbol(symbol="ETH.X", title="Ethereum", watchlist_count=800, raw={}),
            StocktwitsSymbol(symbol="AAPL", title="Apple Inc.", watchlist_count=500, raw={}),
        ]

        filtered = client.pre_filter_symbols(symbols)

        assert len(filtered) == 1
        assert filtered[0].symbol == "AAPL"

    def test_pre_filter_removes_forex(self, client):
        """Pre-filter should remove forex pairs (contain /)."""
        symbols = [
            StocktwitsSymbol(symbol="EUR/USD", title="Euro/Dollar", watchlist_count=100, raw={}),
            StocktwitsSymbol(symbol="MSFT", title="Microsoft", watchlist_count=500, raw={}),
        ]

        filtered = client.pre_filter_symbols(symbols)

        assert len(filtered) == 1
        assert filtered[0].symbol == "MSFT"

    def test_pre_filter_removes_warrants(self, client):
        """Pre-filter should remove warrants and units."""
        symbols = [
            StocktwitsSymbol(symbol="SPAC.WS", title="SPAC Warrants", watchlist_count=50, raw={}),
            StocktwitsSymbol(symbol="SPAC.WT", title="SPAC Warrants", watchlist_count=50, raw={}),
            StocktwitsSymbol(symbol="SPAC-WT", title="SPAC Warrants", watchlist_count=50, raw={}),
            StocktwitsSymbol(symbol="NVDA", title="NVIDIA", watchlist_count=1000, raw={}),
        ]

        filtered = client.pre_filter_symbols(symbols)

        assert len(filtered) == 1
        assert filtered[0].symbol == "NVDA"

    def test_pre_filter_removes_long_symbols(self, client):
        """Pre-filter should remove symbols longer than 6 characters."""
        symbols = [
            StocktwitsSymbol(symbol="TOOLONGSYM", title="Too Long", watchlist_count=50, raw={}),
            StocktwitsSymbol(symbol="GOOGL", title="Alphabet", watchlist_count=500, raw={}),
        ]

        filtered = client.pre_filter_symbols(symbols)

        assert len(filtered) == 1
        assert filtered[0].symbol == "GOOGL"

    def test_pre_filter_removes_single_char(self, client):
        """Pre-filter should remove single-character symbols."""
        symbols = [
            StocktwitsSymbol(symbol="A", title="Agilent", watchlist_count=50, raw={}),
            StocktwitsSymbol(symbol="F", title="Ford", watchlist_count=50, raw={}),
            StocktwitsSymbol(symbol="TSLA", title="Tesla", watchlist_count=1000, raw={}),
        ]

        filtered = client.pre_filter_symbols(symbols)

        assert len(filtered) == 1
        assert filtered[0].symbol == "TSLA"

    def test_pre_filter_keeps_valid_lowercase(self, client):
        """Pre-filter should keep valid symbols (case preserved for later normalization)."""
        symbols = [
            StocktwitsSymbol(symbol="aapl", title="Apple", watchlist_count=500, raw={}),
        ]

        filtered = client.pre_filter_symbols(symbols)

        # Pre-filter keeps valid symbols; case normalization happens in service layer
        assert len(filtered) == 1
        assert filtered[0].symbol.upper() == "AAPL"

    def test_parse_response_valid_data(self, client):
        """Parse response should handle valid Stocktwits data."""
        data = {
            "symbols": [
                {"symbol": "AAPL", "title": "Apple Inc.", "watchlist_count": 12490},
                {"symbol": "NVDA", "title": "NVIDIA", "watchlist_count": 8500},
            ]
        }

        result = client._parse_response(data)

        assert len(result) == 2
        assert result[0].symbol == "AAPL"
        assert result[0].title == "Apple Inc."
        assert result[0].watchlist_count == 12490

    def test_parse_response_empty_data(self, client):
        """Parse response should handle empty data gracefully."""
        result = client._parse_response({})
        assert result == []

        result = client._parse_response({"symbols": []})
        assert result == []

    def test_parse_response_invalid_data(self, client):
        """Parse response should handle invalid data gracefully."""
        result = client._parse_response(None)
        assert result == []

        result = client._parse_response({"symbols": "not a list"})
        assert result == []


class TestFMPClient:
    """Tests for FMPClient."""

    @pytest.fixture
    def client(self):
        """Create an FMP client for testing."""
        return FMPClient(
            api_key="test_key",
            timeout_seconds=5.0,
            max_concurrency=2,
        )

    @pytest.fixture
    def unconfigured_client(self):
        """Create an FMP client without API key."""
        return FMPClient(api_key="", timeout_seconds=5.0)

    def test_is_configured_with_key(self, client):
        """Client should report configured when API key is set."""
        assert client.is_configured is True

    def test_is_configured_without_key(self, unconfigured_client):
        """Client should report not configured without API key."""
        assert unconfigured_client.is_configured is False

    def test_parse_profiles_valid_data(self, client):
        """Parse profiles should handle valid FMP data."""
        data = [
            {
                "symbol": "AAPL",
                "companyName": "Apple Inc.",
                "exchangeShortName": "NASDAQ",
                "isEtf": False,
                "isFund": False,
                "isActivelyTrading": True,
                "price": 185.50,
                "changes": 2.30,
                "changesPercentage": 1.25,
                "mktCap": 2900000000000,
            },
            {
                "symbol": "SPY",
                "companyName": "SPDR S&P 500 ETF",
                "exchangeShortName": "NYSEArca",
                "isEtf": True,
                "isFund": False,
                "isActivelyTrading": True,
                "price": 450.00,
            },
        ]

        result = client._parse_profiles(data)

        assert "AAPL" in result
        assert "SPY" in result

        aapl = result["AAPL"]
        assert aapl.company_name == "Apple Inc."
        assert aapl.exchange == "NASDAQ"
        assert aapl.is_etf is False
        assert aapl.is_valid_stock is True
        assert aapl.price == 185.50
        assert aapl.changes == 2.30

        spy = result["SPY"]
        assert spy.is_etf is True
        assert spy.is_valid_stock is False  # ETF should not be valid stock

    def test_fmp_profile_is_valid_stock_checks(self, client):
        """FMPProfile.is_valid_stock should correctly identify stocks."""
        # Valid stock
        valid = FMPProfile(
            symbol="AAPL",
            company_name="Apple",
            exchange="NASDAQ",
            is_etf=False,
            is_fund=False,
            is_actively_trading=True,
            price=185.0,
            changes=2.0,
            changes_percentage=1.1,
            market_cap=2900000000000,
            raw={},
        )
        assert valid.is_valid_stock is True

        # ETF should be invalid
        etf = FMPProfile(
            symbol="SPY",
            company_name="SPDR S&P 500",
            exchange="NYSEArca",
            is_etf=True,
            is_fund=False,
            is_actively_trading=True,
            price=450.0,
            changes=None,
            changes_percentage=None,
            market_cap=None,
            raw={},
        )
        assert etf.is_valid_stock is False

        # Fund should be invalid
        fund = FMPProfile(
            symbol="VFINX",
            company_name="Vanguard 500",
            exchange="NYSE",
            is_etf=False,
            is_fund=True,
            is_actively_trading=True,
            price=350.0,
            changes=None,
            changes_percentage=None,
            market_cap=None,
            raw={},
        )
        assert fund.is_valid_stock is False

        # Crypto exchange should be invalid
        crypto = FMPProfile(
            symbol="BTC",
            company_name="Bitcoin",
            exchange="CRYPTO",
            is_etf=False,
            is_fund=False,
            is_actively_trading=True,
            price=50000.0,
            changes=None,
            changes_percentage=None,
            market_cap=None,
            raw={},
        )
        assert crypto.is_valid_stock is False

        # Not actively trading should be invalid
        delisted = FMPProfile(
            symbol="OLD",
            company_name="Old Company",
            exchange="NASDAQ",
            is_etf=False,
            is_fund=False,
            is_actively_trading=False,
            price=0.0,
            changes=None,
            changes_percentage=None,
            market_cap=None,
            raw={},
        )
        assert delisted.is_valid_stock is False

    def test_parse_profiles_empty_data(self, client):
        """Parse profiles should handle empty data gracefully."""
        result = client._parse_profiles([])
        assert result == {}

        result = client._parse_profiles(None)
        assert result == {}

    @pytest.mark.asyncio
    async def test_get_profiles_not_configured(self, unconfigured_client):
        """Get profiles should return empty dict when not configured."""
        result = await unconfigured_client.get_profiles(["AAPL", "MSFT"])
        assert result == {}

    @pytest.mark.asyncio
    async def test_get_etf_list_not_configured(self, unconfigured_client):
        """Get ETF list should return empty list when not configured."""
        result = await unconfigured_client.get_etf_list()
        assert result == []

    @pytest.mark.asyncio
    async def test_get_quotes_not_configured(self, unconfigured_client):
        """Get quotes should return empty dict when not configured."""
        result = await unconfigured_client.get_quotes(["AAPL", "MSFT"])
        assert result == {}

    def test_coerce_float_valid_values(self):
        """Coerce float should handle valid values."""
        from app.integrations.fmp import _coerce_float
        assert _coerce_float(123.45) == 123.45
        assert _coerce_float("123.45") == 123.45
        assert _coerce_float(100) == 100.0

    def test_coerce_float_invalid_values(self):
        """Coerce float should return None for invalid values."""
        from app.integrations.fmp import _coerce_float
        assert _coerce_float(None) is None
        assert _coerce_float("") is None
        assert _coerce_float("not a number") is None


class TestTrendingServiceIntegration:
    """Integration tests for trending service with Stocktwits + FMP."""

    @pytest.mark.asyncio
    async def test_service_returns_fallback_when_unconfigured(self):
        """Service should return fallback tickers when FMP is not configured."""
        from app.services.trending_service import TrendingTickerService

        # Mock Stocktwits to return symbols
        mock_stocktwits = MagicMock()
        mock_stocktwits.fetch_trending = AsyncMock(return_value=[
            StocktwitsSymbol(symbol="AAPL", title="Apple", watchlist_count=1000, raw={}),
            StocktwitsSymbol(symbol="MSFT", title="Microsoft", watchlist_count=800, raw={}),
        ])
        mock_stocktwits.pre_filter_symbols = StocktwitsClient.pre_filter_symbols

        # Mock FMP as unconfigured
        mock_fmp = MagicMock()
        mock_fmp.is_configured = False

        service = TrendingTickerService(stocktwits=mock_stocktwits, fmp=mock_fmp)
        result = await service.get_trending_tickers()

        # Should return data (with or without FMP validation)
        assert "tickers" in result
        assert "source" in result

    @pytest.mark.asyncio
    async def test_service_filters_crypto(self):
        """Service should filter out crypto from Stocktwits."""
        from app.services.trending_service import TrendingTickerService

        mock_stocktwits = MagicMock()
        mock_stocktwits.fetch_trending = AsyncMock(return_value=[
            StocktwitsSymbol(symbol="BTC.X", title="Bitcoin", watchlist_count=5000, raw={}),
            StocktwitsSymbol(symbol="ETH.X", title="Ethereum", watchlist_count=3000, raw={}),
            StocktwitsSymbol(symbol="AAPL", title="Apple", watchlist_count=1000, raw={}),
        ])
        mock_stocktwits.pre_filter_symbols = StocktwitsClient.pre_filter_symbols

        mock_fmp = MagicMock()
        mock_fmp.is_configured = False

        service = TrendingTickerService(stocktwits=mock_stocktwits, fmp=mock_fmp)
        result = await service._fetch_from_stocktwits_fmp()

        # Only AAPL should remain after filtering
        assert result is not None
        tickers = result.get("tickers", [])
        symbols = [t["symbol"] for t in tickers]
        assert "BTC.X" not in symbols
        assert "ETH.X" not in symbols
        assert "AAPL" in symbols


class TestPreFilterHeuristics:
    """Tests for pre-filter heuristics that save API calls."""

    @pytest.fixture
    def client(self):
        return StocktwitsClient()

    def test_mixed_asset_filtering(self, client):
        """Test filtering a mix of assets like real Stocktwits data."""
        # Simulated real-world Stocktwits trending data
        symbols = [
            StocktwitsSymbol(symbol="NVDA", title="NVIDIA", watchlist_count=15000, raw={}),
            StocktwitsSymbol(symbol="BTC.X", title="Bitcoin", watchlist_count=12000, raw={}),
            StocktwitsSymbol(symbol="TSLA", title="Tesla", watchlist_count=11000, raw={}),
            StocktwitsSymbol(symbol="ETH.X", title="Ethereum", watchlist_count=8000, raw={}),
            StocktwitsSymbol(symbol="AAPL", title="Apple", watchlist_count=7000, raw={}),
            StocktwitsSymbol(symbol="SOL.X", title="Solana", watchlist_count=5000, raw={}),
            StocktwitsSymbol(symbol="EUR/USD", title="Euro/Dollar", watchlist_count=3000, raw={}),
            StocktwitsSymbol(symbol="MSFT", title="Microsoft", watchlist_count=6000, raw={}),
            StocktwitsSymbol(symbol="SPCE.WS", title="SPCE Warrants", watchlist_count=1000, raw={}),
            StocktwitsSymbol(symbol="AMZN", title="Amazon", watchlist_count=5500, raw={}),
        ]

        filtered = client.pre_filter_symbols(symbols)
        filtered_symbols = [s.symbol for s in filtered]

        # Should keep only stocks
        assert set(filtered_symbols) == {"NVDA", "TSLA", "AAPL", "MSFT", "AMZN"}

        # Should have filtered 5 items
        assert len(symbols) - len(filtered) == 5
