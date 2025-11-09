#!/usr/bin/env python3
"""
Verification script for XBRL fallback parser.
Tests that the parser correctly maps GAAP tags to metric buckets.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock httpx BEFORE importing the service
import httpx

class MockResponse:
    status_code = 200
    def __init__(self, text):
        self.text = text

class MockClient:
    def __init__(self, *args, **kwargs):
        pass
    async def __aenter__(self):
        return self
    async def __aexit__(self, *args):
        pass
    async def get(self, *args, **kwargs):
        return MockResponse(self._sample_xbrl)

# Store sample XML in the mock class
MockClient._sample_xbrl = None

# Replace httpx.AsyncClient before importing the service
original_async_client = httpx.AsyncClient
httpx.AsyncClient = MockClient

from app.services.xbrl_service import XBRLService


def test_xbrl_parsing():
    """Test XBRL XML parsing with sample data"""
    sample_xbrl = """<?xml version='1.0' encoding='UTF-8'?>
    <xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
                xmlns:us-gaap="http://fasb.org/us-gaap/2020-01-31">
      <xbrli:context id="ctx1">
        <xbrli:period>
          <xbrli:endDate>2024-12-31</xbrli:endDate>
        </xbrli:period>
      </xbrli:context>
      <us-gaap:Revenues contextRef="ctx1">1,200,000</us-gaap:Revenues>
      <us-gaap:NetIncomeLoss contextRef="ctx1">(250,000)</us-gaap:NetIncomeLoss>
      <us-gaap:Assets contextRef="ctx1">5,000,000</us-gaap:Assets>
      <us-gaap:Liabilities contextRef="ctx1">2,500,000</us-gaap:Liabilities>
      <us-gaap:CashAndCashEquivalentsAtCarryingValue contextRef="ctx1">500,000</us-gaap:CashAndCashEquivalentsAtCarryingValue>
      <us-gaap:EarningsPerShareBasic contextRef="ctx1">2.50</us-gaap:EarningsPerShareBasic>
    </xbrli:xbrl>
    """
    
    # Set the sample XML in the mock
    MockClient._sample_xbrl = sample_xbrl
    
    try:
        service = XBRLService()
        import asyncio
        
        # Add exception handling to see what's happening
        try:
            parsed = asyncio.run(service._parse_xbrl_xml("https://example.com/xbrl.xml"))
        except Exception as parse_error:
            print(f"❌ Parser raised exception: {parse_error}")
            import traceback
            traceback.print_exc()
            return False
        
        if not parsed:
            print("❌ Parser returned None")
            print("This usually means no metrics were extracted. Checking parser logic...")
            # Let's test the parsing directly with BeautifulSoup
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(sample_xbrl, 'xml')
            revenues = soup.find_all('us-gaap:Revenues')
            print(f"Found {len(revenues)} revenue tags in XML")
            if revenues:
                print(f"First revenue tag: {revenues[0]}")
                print(f"Revenue value: {revenues[0].string}")
            return False
        
        # Verify revenue
        revenue = parsed.get("revenue", [])
        if not revenue or revenue[0]["value"] != 1_200_000.0:
            print(f"❌ Revenue parsing failed: {revenue}")
            return False
        print(f"✓ Revenue: {revenue[0]['value']:,.0f}")
        
        # Verify net income (should be negative)
        net_income = parsed.get("net_income", [])
        if not net_income or net_income[0]["value"] != -250_000.0:
            print(f"❌ Net income parsing failed: {net_income}")
            return False
        print(f"✓ Net Income: {net_income[0]['value']:,.0f}")
        
        # Verify assets
        assets = parsed.get("total_assets", [])
        if not assets or assets[0]["value"] != 5_000_000.0:
            print(f"❌ Assets parsing failed: {assets}")
            return False
        print(f"✓ Assets: {assets[0]['value']:,.0f}")
        
        # Verify liabilities (new metric)
        liabilities = parsed.get("total_liabilities", [])
        if not liabilities or liabilities[0]["value"] != 2_500_000.0:
            print(f"❌ Liabilities parsing failed: {liabilities}")
            return False
        print(f"✓ Liabilities: {liabilities[0]['value']:,.0f}")
        
        # Verify cash (new metric)
        cash = parsed.get("cash_and_equivalents", [])
        if not cash or cash[0]["value"] != 500_000.0:
            print(f"❌ Cash parsing failed: {cash}")
            return False
        print(f"✓ Cash & Equivalents: {cash[0]['value']:,.0f}")
        
        # Verify EPS
        eps = parsed.get("earnings_per_share", [])
        if not eps or eps[0]["value"] != 2.50:
            print(f"❌ EPS parsing failed: {eps}")
            return False
        print(f"✓ EPS: {eps[0]['value']:.2f}")
        
        # Verify periods are extracted
        if revenue[0]["period"] != "2024-12-31":
            print(f"❌ Period extraction failed: {revenue[0]['period']}")
            return False
        print(f"✓ Period extraction: {revenue[0]['period']}")
        
        print("\n✅ All XBRL fallback parser tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Error during parsing: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Restore original client
        httpx.AsyncClient = original_async_client


if __name__ == "__main__":
    success = test_xbrl_parsing()
    sys.exit(0 if success else 1)

