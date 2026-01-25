from typing import Optional, Dict, Any, List

def format_currency(value: Optional[float]) -> str:
    if value is None:
        return "Not disclosed"
    try:
        abs_val = abs(value)
        if abs_val >= 1_000_000_000:
            return f"${value / 1_000_000_000:.1f}B"
        if abs_val >= 1_000_000:
            return f"${value / 1_000_000:.1f}M"
        return f"${value:,.0f}"
    except:
        return "Not disclosed"

def generate_xbrl_summary(
    xbrl_data: Optional[Dict[str, Any]], 
    company_name: str,
    filing_date: str = "Unknown Date"
) -> Dict[str, Any]:
    """
    Generate a fallback summary using only XBRL data and metadata.
    This is used when the full AI analysis times out.
    """
    
    # Defaults
    business_overview = f"## Quick Summary for {company_name}\n\n"
    business_overview += "The full AI analysis is taking longer than expected. Here is a preliminary overview based on standardized financial data reported to the SEC.\n\n"
    
    financial_highlights = None
    
    # Extract metrics if available
    metrics_summary = []
    
    if xbrl_data:
        # Expected structure: xbrl_data should be normalized metrics map
        # But xbrl_service usually returns raw data which is then normalized
        # If we pass raw xbrl_data, we might need to extract.
        # Assuming xbrl_data passed here is the cleaned metrics dict (e.g. from xbrl_service.extract_standardized_metrics)
        # Check structure
        
        # If it's the raw list of facts, we can't easily use it without the service helper.
        # Ideally, caller passes normalized metrics.
        # Let's assume input is normalized metrics dict as seen in summaries.py (xbrl_metrics variable)
        
        # metric format: {'value': 123, 'period': '2023', 'unit': 'USD'}
        
        revenue = xbrl_data.get('revenue', {}).get('current', {})
        net_income = xbrl_data.get('net_income', {}).get('current', {})
        eps = xbrl_data.get('earnings_per_share', {}).get('current', {})
        
        if revenue.get('value'):
            metrics_summary.append(f"- **Revenue**: {format_currency(revenue['value'])} (Period: {revenue.get('period', 'N/A')})")
        
        if net_income.get('value'):
            metrics_summary.append(f"- **Net Income**: {format_currency(net_income['value'])} (Period: {net_income.get('period', 'N/A')})")
            
        if eps.get('value'):
            metrics_summary.append(f"- **EPS**: {eps['value']} (Period: {eps.get('period', 'N/A')})")
            
        # Construct financial_highlights structured data for frontend
        financial_highlights = {
            "table": [
                {
                    "metric": "Revenue",
                    "current_period": format_currency(revenue.get('value')),
                    "prior_period": "Not loaded",
                    "change": "N/A",
                    "commentary": "Derived from XBRL data."
                },
                {
                    "metric": "Net Income",
                    "current_period": format_currency(net_income.get('value')),
                    "prior_period": "Not loaded",
                    "change": "N/A",
                    "commentary": "Derived from XBRL data."
                }
            ],
            "profitability": ["Profitability analysis pending full report."],
            "cash_flow": ["Cash flow analysis pending full report."],
            "balance_sheet": ["Balance sheet analysis pending full report."]
        }
    
    if metrics_summary:
        business_overview += "### Financial Snapshot (XBRL)\n" + "\n".join(metrics_summary) + "\n\n"
    else:
        business_overview += "No standardized financial metrics resulted from the XBRL parse.\n"
        
    business_overview += "> **Note:** This is a partial summary. You can retry generating the full analysis below."

    return {
        "status": "partial",
        "message": "Full analysis timed out. Showing available financial data.",
        "business_overview": business_overview,
        "financial_highlights": financial_highlights,
        "risk_factors": [],
        "management_discussion": "Analysis pending...",
        "key_changes": "Analysis pending...",
        "raw_summary": {} 
    }
