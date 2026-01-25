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

    IMPORTANT: This function must NEVER return empty sections.
    Users must always see meaningful content, even if metrics are unavailable.
    """

    # Defaults
    business_overview = f"## Quick Summary for {company_name}\n\n"
    business_overview += "The full AI analysis is taking longer than expected. Here is a preliminary overview based on standardized financial data reported to the SEC.\n\n"

    # Extract metrics if available
    metrics_summary = []
    has_xbrl_data = False

    if xbrl_data:
        revenue = xbrl_data.get('revenue', {}).get('current', {})
        net_income = xbrl_data.get('net_income', {}).get('current', {})
        eps = xbrl_data.get('earnings_per_share', {}).get('current', {})

        if revenue.get('value'):
            metrics_summary.append(f"- **Revenue**: {format_currency(revenue['value'])} (Period: {revenue.get('period', 'N/A')})")
            has_xbrl_data = True

        if net_income.get('value'):
            metrics_summary.append(f"- **Net Income**: {format_currency(net_income['value'])} (Period: {net_income.get('period', 'N/A')})")
            has_xbrl_data = True

        if eps.get('value'):
            metrics_summary.append(f"- **EPS**: {eps['value']} (Period: {eps.get('period', 'N/A')})")
            has_xbrl_data = True

    # Build business overview text
    if metrics_summary:
        business_overview += "### Financial Snapshot (XBRL)\n" + "\n".join(metrics_summary) + "\n\n"
    else:
        business_overview += "Financial metrics are being processed. The full AI analysis will provide detailed insights.\n\n"

    business_overview += "> **Note:** This is a partial summary. You can retry generating the full analysis below."

    # ALWAYS provide financial_highlights with meaningful structure
    if has_xbrl_data and xbrl_data:
        revenue = xbrl_data.get('revenue', {}).get('current', {})
        net_income = xbrl_data.get('net_income', {}).get('current', {})
        financial_highlights = {
            "table": [
                {
                    "metric": "Revenue",
                    "current_period": format_currency(revenue.get('value')),
                    "prior_period": "Pending analysis",
                    "change": "Pending",
                    "commentary": "Full comparison available in detailed analysis."
                },
                {
                    "metric": "Net Income",
                    "current_period": format_currency(net_income.get('value')),
                    "prior_period": "Pending analysis",
                    "change": "Pending",
                    "commentary": "Full comparison available in detailed analysis."
                }
            ],
            "profitability": ["Profitability metrics available in full analysis."],
            "cash_flow": ["Cash flow analysis available in full analysis."],
            "balance_sheet": ["Balance sheet metrics available in full analysis."]
        }
    else:
        # Provide placeholder structure when no XBRL data
        financial_highlights = {
            "table": [
                {
                    "metric": "Revenue",
                    "current_period": "Loading...",
                    "prior_period": "Loading...",
                    "change": "Pending",
                    "commentary": "Financial metrics being processed. Retry for full analysis."
                },
                {
                    "metric": "Net Income",
                    "current_period": "Loading...",
                    "prior_period": "Loading...",
                    "change": "Pending",
                    "commentary": "Financial metrics being processed. Retry for full analysis."
                }
            ],
            "profitability": ["Processing... Retry for complete profitability analysis."],
            "cash_flow": ["Processing... Retry for complete cash flow analysis."],
            "balance_sheet": ["Processing... Retry for complete balance sheet analysis."]
        }

    # NEVER return empty risk_factors - always provide meaningful placeholder
    risk_factors = [
        {
            "summary": "Risk factors are being analyzed from the SEC filing.",
            "supporting_evidence": "Full risk analysis will be available when you retry the generation.",
            "materiality": "pending"
        }
    ]

    # NEVER return empty management_discussion
    management_discussion = (
        f"**{company_name}** management discussion analysis is being processed. "
        "The full AI analysis will provide detailed insights into management's perspective "
        "on business operations, financial condition, and future outlook. "
        "Please retry generation for complete MD&A coverage."
    )

    # NEVER return empty key_changes
    key_changes = (
        "Key changes and notable developments are being extracted from the filing. "
        "The full analysis will highlight significant operational, financial, or strategic "
        "changes compared to prior periods. Please retry for detailed change analysis."
    )

    return {
        "status": "partial",
        "message": "Full analysis timed out. Showing available financial data.",
        "business_overview": business_overview,
        "financial_highlights": financial_highlights,
        "risk_factors": risk_factors,
        "management_discussion": management_discussion,
        "key_changes": key_changes,
        "raw_summary": {
            "sections": {
                "executive_snapshot": {
                    "headline": f"{company_name} quarterly filing analysis in progress",
                    "key_points": [
                        "Full AI analysis is being processed",
                        "Financial metrics are being extracted",
                        "Risk factors are being identified",
                        "Retry generation for complete insights"
                    ],
                    "tone": "neutral"
                }
            }
        }
    }
