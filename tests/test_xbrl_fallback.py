import sys
from pathlib import Path

# Add backend directory to Python path to ensure correct imports
# Must be first to avoid conflicts with root-level app.py and pydantic directories
backend_path = Path(__file__).parent.parent / "backend"
backend_path_str = str(backend_path.resolve())
if backend_path_str not in sys.path:
    # Remove root directory from path if present to avoid conflicts
    root_path = str(Path(__file__).parent.parent.resolve())
    if root_path in sys.path:
        sys.path.remove(root_path)
    sys.path.insert(0, backend_path_str)

import pytest

from app.services.xbrl_service import XBRLService


class _DummyResponse:
    status_code = 200

    def __init__(self, text: str) -> None:
        self.text = text


class _DummyAsyncClient:
    def __init__(self, *args, **kwargs) -> None:  # pragma: no cover - signature match
        self._response: _DummyResponse | None = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False

    async def get(self, url, headers=None, timeout=None):  # pragma: no cover - keep signature
        if self._response is None:
            raise RuntimeError("Dummy response was not initialised")
        return self._response


@pytest.mark.asyncio
async def test_parse_xbrl_xml_maps_metrics(monkeypatch):
    """Ensure fallback XML parsing maps GAAP tags to the correct metric buckets."""

    sample_xbrl = """<?xml version='1.0' encoding='UTF-8'?>
    <xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
                xmlns:us-gaap="http://fasb.org/us-gaap/2020-01-31">
      <xbrli:context id="ctx1">
        <xbrli:period>
          <xbrli:endDate>2024-12-31</xbrli:endDate>
        </xbrli:period>
      </xbrli:context>
      <xbrli:context id="ctx2">
        <xbrli:period>
          <xbrli:instant>2023-12-31</xbrli:instant>
        </xbrli:period>
      </xbrli:context>
      <us-gaap:Revenues contextRef="ctx1">1,200,000</us-gaap:Revenues>
      <us-gaap:SalesRevenueNet contextRef="ctx2">1,000,000</us-gaap:SalesRevenueNet>
      <us-gaap:NetIncomeLoss contextRef="ctx1">(250,000)</us-gaap:NetIncomeLoss>
      <us-gaap:ProfitLoss contextRef="ctx2">150,000</us-gaap:ProfitLoss>
      <us-gaap:Assets contextRef="ctx1">5,000,000</us-gaap:Assets>
      <us-gaap:Liabilities contextRef="ctx1">2,500,000</us-gaap:Liabilities>
      <us-gaap:CashAndCashEquivalentsAtCarryingValue contextRef="ctx1">500,000</us-gaap:CashAndCashEquivalentsAtCarryingValue>
      <us-gaap:EarningsPerShareBasic contextRef="ctx1">2.50</us-gaap:EarningsPerShareBasic>
      <us-gaap:EarningsPerShareDiluted contextRef="ctx1">2.45</us-gaap:EarningsPerShareDiluted>
    </xbrli:xbrl>
    """

    dummy_client = _DummyAsyncClient()
    dummy_client._response = _DummyResponse(sample_xbrl)

    def _factory(*args, **kwargs):  # pragma: no cover - factory shim
        return dummy_client

    monkeypatch.setattr("app.services.xbrl_service.httpx.AsyncClient", _factory)

    service = XBRLService()
    parsed = await service._parse_xbrl_xml("https://example.com/xbrl.xml")

    assert parsed is not None

    # Test revenue mapping (both Revenues and SalesRevenueNet should map to revenue)
    revenue_entries = parsed["revenue"]
    assert len(revenue_entries) == 2
    assert revenue_entries[0]["value"] == pytest.approx(1_200_000.0)
    assert revenue_entries[0]["period"] == "2024-12-31"
    assert revenue_entries[1]["value"] == pytest.approx(1_000_000.0)
    assert revenue_entries[1]["period"] == "2023-12-31"

    # Test net income mapping (both NetIncomeLoss and ProfitLoss should map to net_income)
    net_income_entries = parsed["net_income"]
    assert len(net_income_entries) == 2
    assert net_income_entries[0]["value"] == pytest.approx(-250_000.0)
    assert net_income_entries[0]["period"] == "2024-12-31"
    assert net_income_entries[1]["value"] == pytest.approx(150_000.0)
    assert net_income_entries[1]["period"] == "2023-12-31"

    # Test assets
    assets_entries = parsed["total_assets"]
    assert len(assets_entries) == 1
    assert assets_entries[0]["value"] == pytest.approx(5_000_000.0)
    assert assets_entries[0]["period"] == "2024-12-31"

    # Test liabilities (new metric)
    liabilities_entries = parsed["total_liabilities"]
    assert len(liabilities_entries) == 1
    assert liabilities_entries[0]["value"] == pytest.approx(2_500_000.0)
    assert liabilities_entries[0]["period"] == "2024-12-31"

    # Test cash and equivalents (new metric)
    cash_entries = parsed["cash_and_equivalents"]
    assert len(cash_entries) == 1
    assert cash_entries[0]["value"] == pytest.approx(500_000.0)
    assert cash_entries[0]["period"] == "2024-12-31"

    # Test EPS (both Basic and Diluted should map to earnings_per_share)
    eps_entries = parsed["earnings_per_share"]
    assert len(eps_entries) == 2
    assert eps_entries[0]["value"] == pytest.approx(2.50)
    assert eps_entries[0]["period"] == "2024-12-31"
    assert eps_entries[1]["value"] == pytest.approx(2.45)
    assert eps_entries[1]["period"] == "2024-12-31"


@pytest.mark.asyncio
async def test_parse_xbrl_xml_handles_negative_values(monkeypatch):
    """Ensure negative values in parentheses are parsed correctly."""
    sample_xbrl = """<?xml version='1.0' encoding='UTF-8'?>
    <xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
                xmlns:us-gaap="http://fasb.org/us-gaap/2020-01-31">
      <xbrli:context id="ctx1">
        <xbrli:period>
          <xbrli:endDate>2024-12-31</xbrli:endDate>
        </xbrli:period>
      </xbrli:context>
      <us-gaap:NetIncomeLoss contextRef="ctx1">(1,500,000)</us-gaap:NetIncomeLoss>
    </xbrli:xbrl>
    """

    dummy_client = _DummyAsyncClient()
    dummy_client._response = _DummyResponse(sample_xbrl)

    def _factory(*args, **kwargs):
        return dummy_client

    monkeypatch.setattr("app.services.xbrl_service.httpx.AsyncClient", _factory)

    service = XBRLService()
    parsed = await service._parse_xbrl_xml("https://example.com/xbrl.xml")

    assert parsed is not None
    net_income_entries = parsed["net_income"]
    assert len(net_income_entries) == 1
    assert net_income_entries[0]["value"] == pytest.approx(-1_500_000.0)


@pytest.mark.asyncio
async def test_parse_xbrl_xml_handles_missing_context(monkeypatch):
    """Ensure parsing works even when contextRef doesn't match any context."""
    sample_xbrl = """<?xml version='1.0' encoding='UTF-8'?>
    <xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
                xmlns:us-gaap="http://fasb.org/us-gaap/2020-01-31">
      <us-gaap:Revenues contextRef="missing_ctx">1,200,000</us-gaap:Revenues>
    </xbrli:xbrl>
    """

    dummy_client = _DummyAsyncClient()
    dummy_client._response = _DummyResponse(sample_xbrl)

    def _factory(*args, **kwargs):
        return dummy_client

    monkeypatch.setattr("app.services.xbrl_service.httpx.AsyncClient", _factory)

    service = XBRLService()
    parsed = await service._parse_xbrl_xml("https://example.com/xbrl.xml")

    assert parsed is not None
    revenue_entries = parsed["revenue"]
    assert len(revenue_entries) == 1
    assert revenue_entries[0]["value"] == pytest.approx(1_200_000.0)
    assert revenue_entries[0]["period"] is None  # Period should be None when context is missing


@pytest.mark.asyncio
async def test_parse_xbrl_xml_ignores_invalid_tags(monkeypatch):
    """Ensure unknown tags are ignored without causing errors."""
    sample_xbrl = """<?xml version='1.0' encoding='UTF-8'?>
    <xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
                xmlns:us-gaap="http://fasb.org/us-gaap/2020-01-31">
      <xbrli:context id="ctx1">
        <xbrli:period>
          <xbrli:endDate>2024-12-31</xbrli:endDate>
        </xbrli:period>
      </xbrli:context>
      <us-gaap:Revenues contextRef="ctx1">1,200,000</us-gaap:Revenues>
      <us-gaap:UnknownTag contextRef="ctx1">999,999</us-gaap:UnknownTag>
    </xbrli:xbrl>
    """

    dummy_client = _DummyAsyncClient()
    dummy_client._response = _DummyResponse(sample_xbrl)

    def _factory(*args, **kwargs):
        return dummy_client

    monkeypatch.setattr("app.services.xbrl_service.httpx.AsyncClient", _factory)

    service = XBRLService()
    parsed = await service._parse_xbrl_xml("https://example.com/xbrl.xml")

    assert parsed is not None
    # Only revenue should be present, unknown tag should be ignored
    assert len(parsed["revenue"]) == 1
    assert len(parsed["net_income"]) == 0


