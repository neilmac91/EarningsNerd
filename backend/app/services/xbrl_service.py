from typing import Dict, List, Optional
import httpx
import re
import logging
from bs4 import BeautifulSoup
from app.config import settings

logger = logging.getLogger(__name__)

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
            logger.error(f"Error fetching XBRL data: {str(e)}", exc_info=True)
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
        
        try:
            facts = facts_data.get("facts", {})
            
            # US GAAP facts
            us_gaap = facts.get("us-gaap", {})
            if not isinstance(us_gaap, dict):
                return result
            
            # Extract revenue
            if "Revenues" in us_gaap:
                revenues_fact = us_gaap["Revenues"]
                if isinstance(revenues_fact, dict) and "units" in revenues_fact:
                    revenue_data = revenues_fact["units"].get("USD", [])
                    if isinstance(revenue_data, list):
                        for item in revenue_data[:5]:  # Last 5 periods
                            if isinstance(item, dict):
                                result["revenue"].append({
                                    "period": item.get("end"),
                                    "value": item.get("val"),
                                    "form": item.get("form"),
                                })
            
            # Extract net income
            if "NetIncomeLoss" in us_gaap:
                net_income_fact = us_gaap["NetIncomeLoss"]
                if isinstance(net_income_fact, dict) and "units" in net_income_fact:
                    net_income_data = net_income_fact["units"].get("USD", [])
                    if isinstance(net_income_data, list):
                        for item in net_income_data[:5]:
                            if isinstance(item, dict):
                                result["net_income"].append({
                                    "period": item.get("end"),
                                    "value": item.get("val"),
                                    "form": item.get("form"),
                                })
            
            # Extract total assets
            if "Assets" in us_gaap:
                assets_fact = us_gaap["Assets"]
                if isinstance(assets_fact, dict) and "units" in assets_fact:
                    assets_data = assets_fact["units"].get("USD", [])
                    if isinstance(assets_data, list):
                        for item in assets_data[:5]:
                            if isinstance(item, dict):
                                result["total_assets"].append({
                                    "period": item.get("end"),
                                    "value": item.get("val"),
                                    "form": item.get("form"),
                                })
            
            # Extract EPS - try multiple unit formats
            if "EarningsPerShareBasic" in us_gaap:
                eps_fact = us_gaap["EarningsPerShareBasic"]
                if isinstance(eps_fact, dict) and "units" in eps_fact:
                    units = eps_fact["units"]
                    # Try different unit formats
                    eps_data = None
                    for unit_key in ["USD/shares", "shares", "pure"]:
                        if unit_key in units:
                            eps_data = units[unit_key]
                            break
                    
                    if eps_data and isinstance(eps_data, list):
                        for item in eps_data[:5]:
                            if isinstance(item, dict):
                                result["earnings_per_share"].append({
                                    "period": item.get("end"),
                                    "value": item.get("val"),
                                    "form": item.get("form"),
                                })
        except Exception as e:
            logger.warning(f"Error parsing XBRL facts: {str(e)}", exc_info=True)
        
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
            logger.error(f"Error extracting from HTML: {str(e)}", exc_info=True)
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
                        "total_liabilities": [],
                        "cash_and_equivalents": [],
                        "earnings_per_share": [],
                    }
                    
                    # Build context lookup to map context IDs to reporting periods
                    context_periods: Dict[str, Optional[str]] = {}
                    for context in soup.find_all('context'):
                        context_id = context.get('id')
                        if not context_id:
                            continue

                        period_value: Optional[str] = None
                        period_tag = context.find('period')
                        if period_tag:
                            instant = period_tag.find('instant')
                            if instant and instant.string:
                                period_value = instant.string.strip()
                            else:
                                end_date = period_tag.find('endDate')
                                if end_date and end_date.string:
                                    period_value = end_date.string.strip()
                        if period_value:
                            context_periods[context_id] = period_value

                    raw_tag_mappings = {
                        'us-gaap:Revenues': 'revenue',
                        'us-gaap:SalesRevenueNet': 'revenue',
                        'us-gaap:NetIncomeLoss': 'net_income',
                        'us-gaap:ProfitLoss': 'net_income',
                        'us-gaap:Assets': 'total_assets',
                        'us-gaap:Liabilities': 'total_liabilities',
                        'us-gaap:LiabilitiesAndStockholdersEquity': 'total_liabilities',
                        'us-gaap:CashAndCashEquivalentsAtCarryingValue': 'cash_and_equivalents',
                        'us-gaap:CashAndCashEquivalentsPeriodIncreaseDecrease': 'cash_and_equivalents',
                        'us-gaap:EarningsPerShareBasic': 'earnings_per_share',
                        'us-gaap:EarningsPerShareDiluted': 'earnings_per_share',
                        'us-gaap:EarningsPerShareBasicAndDiluted': 'earnings_per_share',
                    }

                    tag_mappings: Dict[str, str] = {}
                    for tag_name, mapped_key in raw_tag_mappings.items():
                        tag_mappings[tag_name.lower()] = mapped_key
                        if ":" in tag_name:
                            local_name = tag_name.split(":", 1)[1]
                            tag_mappings[local_name.lower()] = mapped_key

                    def _parse_numeric_value(raw: Optional[str]) -> Optional[float]:
                        if raw is None:
                            return None
                        text = raw.strip()
                        if not text:
                            return None
                        negative = text.startswith('(') and text.endswith(')')
                        if negative:
                            text = text[1:-1]
                        text = text.replace(',', '')
                        try:
                            value = float(text)
                        except ValueError:
                            return None
                        return -value if negative else value

                    # BeautifulSoup find_all() doesn't accept a list directly
                    # We need to search for each tag name individually or use a lambda
                    def _is_target_tag(tag):
                        """Check if tag matches any of our lookup tags"""
                        tag_name_lower = tag.name.lower() if tag.name else ""
                        return tag_name_lower in tag_mappings
                    
                    for tag in soup.find_all(_is_target_tag):
                        mapped_key = tag_mappings.get(tag.name.lower())
                        if not mapped_key:
                            continue

                        numeric_value = _parse_numeric_value(tag.string)
                        if numeric_value is None:
                            continue

                        context_ref = tag.get('contextRef', '').strip()
                        result.setdefault(mapped_key, []).append(
                            {
                                "period": context_periods.get(context_ref),
                                "value": numeric_value,
                                "form": tag.get('form'),
                            }
                        )
                    
                    return result if any(result.values()) else None
            
            return None
        except Exception as e:
            logger.error(f"Error parsing XBRL XML: {str(e)}", exc_info=True)
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

