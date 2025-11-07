from typing import Dict, List, Optional
import httpx
import re
from bs4 import BeautifulSoup
from app.config import settings

class XBRLService:
    def __init__(self):
        self.base_url = settings.SEC_EDGAR_BASE_URL
        self.user_agent = "EarningsNerd (contact@earningsnerd.com)"

    async def get_xbrl_data(self, accession_number: str, cik: str) -> Optional[Dict]:
        """Extract XBRL data from SEC filing"""
        try:
            # SEC EDGAR XBRL data endpoint
            # Format: https://data.sec.gov/api/xbrl/companyfacts/CIK{number}.json
            # Or: https://www.sec.gov/cgi-bin/viewer?action=view&cik={cik}&accession_number={accession}
            
            # Try to get XBRL facts from companyfacts endpoint
            cik_padded = str(cik).zfill(10)
            facts_url = f"{self.base_url}/api/xbrl/companyfacts/CIK{cik_padded}.json"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    facts_url,
                    headers={"User-Agent": self.user_agent},
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return self._parse_xbrl_facts(data)
                else:
                    # Fallback: try to extract from filing HTML
                    return await self._extract_from_filing_html(accession_number, cik)
        except Exception as e:
            print(f"Error fetching XBRL data: {str(e)}")
            return None

    def _parse_xbrl_facts(self, facts_data: Dict) -> Dict:
        """Parse XBRL facts from SEC API response"""
        result = {
            "revenue": [],
            "net_income": [],
            "total_assets": [],
            "total_liabilities": [],
            "cash_and_equivalents": [],
            "earnings_per_share": [],
        }
        
        facts = facts_data.get("facts", {})
        
        # US GAAP facts
        us_gaap = facts.get("us-gaap", {})
        
        # Extract revenue
        if "Revenues" in us_gaap:
            revenue_data = us_gaap["Revenues"]["units"].get("USD", [])
            for item in revenue_data[:5]:  # Last 5 periods
                result["revenue"].append({
                    "period": item.get("end"),
                    "value": item.get("val"),
                    "form": item.get("form"),
                })
        
        # Extract net income
        if "NetIncomeLoss" in us_gaap:
            net_income_data = us_gaap["NetIncomeLoss"]["units"].get("USD", [])
            for item in net_income_data[:5]:
                result["net_income"].append({
                    "period": item.get("end"),
                    "value": item.get("val"),
                    "form": item.get("form"),
                })
        
        # Extract total assets
        if "Assets" in us_gaap:
            assets_data = us_gaap["Assets"]["units"].get("USD", [])
            for item in assets_data[:5]:
                result["total_assets"].append({
                    "period": item.get("end"),
                    "value": item.get("val"),
                    "form": item.get("form"),
                })
        
        # Extract EPS
        if "EarningsPerShareBasic" in us_gaap:
            eps_data = us_gaap["EarningsPerShareBasic"]["units"].get("USD/shares", [])
            for item in eps_data[:5]:
                result["earnings_per_share"].append({
                    "period": item.get("end"),
                    "value": item.get("val"),
                    "form": item.get("form"),
                })
        
        return result

    async def _extract_from_filing_html(self, accession_number: str, cik: str) -> Optional[Dict]:
        """Fallback: Extract financial data from filing HTML"""
        try:
            # Parse accession number (format: 0001234567-12-000001)
            accession_dashed = accession_number.replace("-", "")
            if len(accession_dashed) == 18:
                # Format: https://www.sec.gov/Archives/edgar/data/{cik}/{accession_dashed}/{accession_number}.txt
                filing_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_dashed}/{accession_number}.txt"
            else:
                return None
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    filing_url,
                    headers={"User-Agent": self.user_agent},
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    # Search for XBRL instance document
                    content = response.text
                    # Look for XBRL instance document link
                    xbrl_match = re.search(r'href="([^"]*\.xml)"', content)
                    if xbrl_match:
                        xbrl_url = xbrl_match.group(1)
                        if not xbrl_url.startswith("http"):
                            xbrl_url = f"https://www.sec.gov{xbrl_url}"
                        
                        # Parse XBRL XML
                        return await self._parse_xbrl_xml(xbrl_url)
            
            return None
        except Exception as e:
            print(f"Error extracting from HTML: {str(e)}")
            return None

    async def _parse_xbrl_xml(self, xbrl_url: str) -> Optional[Dict]:
        """Parse XBRL XML document"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    xbrl_url,
                    headers={"User-Agent": self.user_agent},
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    # Basic XML parsing to extract key financial facts
                    # This is a simplified parser - in production, use a proper XBRL library
                    soup = BeautifulSoup(response.text, 'xml')
                    
                    result = {
                        "revenue": [],
                        "net_income": [],
                        "total_assets": [],
                        "earnings_per_share": [],
                    }
                    
                    # Look for common XBRL tags
                    # This is a basic implementation - would need proper XBRL taxonomy handling
                    for tag in soup.find_all(['us-gaap:Revenues', 'us-gaap:NetIncomeLoss']):
                        context_ref = tag.get('contextRef', '')
                        value = tag.string
                        if value:
                            try:
                                numeric_value = float(value)
                                result["revenue"].append({
                                    "value": numeric_value,
                                    "context": context_ref,
                                })
                            except:
                                pass
                    
                    return result if any(result.values()) else None
            
            return None
        except Exception as e:
            print(f"Error parsing XBRL XML: {str(e)}")
            return None

    def extract_standardized_metrics(self, xbrl_data: Dict) -> Dict:
        """Extract standardized financial metrics from XBRL data"""

        def _normalise_series(entries: List[Dict]) -> List[Dict]:
            cleaned: List[Dict] = []
            seen_periods = set()
            # Sort descending by period (ISO dates sort lexicographically)
            sorted_entries = sorted(
                (entry for entry in entries if entry.get("period") and entry.get("value") is not None),
                key=lambda item: item.get("period"),
                reverse=True,
            )
            for entry in sorted_entries:
                period = entry.get("period")
                if period in seen_periods:
                    continue
                seen_periods.add(period)
                cleaned.append(
                    {
                        "period": period,
                        "value": entry.get("value"),
                        "form": entry.get("form"),
                    }
                )
            return cleaned

        def _build_metric_entry(series: List[Dict]) -> Dict:
            entry: Dict[str, Dict] = {}
            if series:
                entry["current"] = series[0]
            if len(series) > 1:
                entry["prior"] = series[1]
            if series:
                entry["series"] = series
            return entry

        metrics: Dict[str, Dict] = {}

        revenue_series = _normalise_series(xbrl_data.get("revenue", []))
        net_income_series = _normalise_series(xbrl_data.get("net_income", []))
        eps_series = _normalise_series(xbrl_data.get("earnings_per_share", []))

        if revenue_series:
            metrics["revenue"] = _build_metric_entry(revenue_series)

        if net_income_series:
            metrics["net_income"] = _build_metric_entry(net_income_series)

        if eps_series:
            metrics["earnings_per_share"] = _build_metric_entry(eps_series)

        # Build net margin series by aligning revenue and net income periods
        if revenue_series and net_income_series:
            income_by_period = {entry["period"]: entry for entry in net_income_series}
            margin_series: List[Dict] = []
            for revenue_entry in revenue_series:
                period = revenue_entry["period"]
                income_entry = income_by_period.get(period)
                revenue_value = revenue_entry.get("value")
                income_value = income_entry.get("value") if income_entry else None
                if (
                    revenue_value is not None
                    and income_value is not None
                    and revenue_value != 0
                ):
                    margin_series.append(
                        {
                            "period": period,
                            "value": (income_value / revenue_value) * 100,
                            "form": revenue_entry.get("form"),
                        }
                    )
            if margin_series:
                metrics["net_margin"] = _build_metric_entry(margin_series)

        return metrics

xbrl_service = XBRLService()

