from typing import Optional, Dict, Any, List
import re
import logging

logger = logging.getLogger(__name__)


def has_valid_xbrl_data(xbrl_data: Optional[Dict[str, Any]]) -> bool:
    """Check if XBRL data contains actual metric values.

    An empty dict `{}` is falsy in Python, so `if xbrl_data:` fails.
    This function checks for actual data in the expected metric keys.

    Note: Uses explicit `is not None` checks to allow zero as a valid value
    (e.g., zero net income is a legitimate financial figure).
    """
    if not xbrl_data:
        return False
    if not isinstance(xbrl_data, dict):
        return False
    # Check if any metric has actual data
    for key in ['revenue', 'net_income', 'earnings_per_share']:
        metric = xbrl_data.get(key, {})
        # Use 'is not None' to allow zero values (valid financial data)
        if isinstance(metric, dict) and metric.get('current', {}).get('value') is not None:
            return True
        # Also check if it's a list with items (raw XBRL format)
        if isinstance(metric, list) and len(metric) > 0:
            if any(item.get('value') is not None for item in metric if isinstance(item, dict)):
                return True
    return False


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
    except Exception as e:
        logger.warning(f"Error formatting currency value {value}: {e}")
        return "Not disclosed"


def _extract_section_text(text: str, section_patterns: List[str], max_chars: int = 2000) -> Optional[str]:
    """Extract a section from filing text using regex patterns."""
    if not text:
        return None

    for pattern in section_patterns:
        try:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                content = match.group(1) if match.groups() else match.group(0)
                # Clean and truncate
                content = re.sub(r'\s+', ' ', content).strip()
                if len(content) > max_chars:
                    content = content[:max_chars] + "..."
                return content
        except Exception as e:
            logger.warning(f"Error processing regex pattern in _extract_section_text: {e}")
            continue
    return None


def _extract_risk_factors(filing_text: str, filing_type: str = "10-Q") -> List[Dict[str, Any]]:
    """Extract risk factors from filing text."""
    if not filing_text:
        return []

    # Patterns to find Risk Factors section
    patterns = [
        r"Item\s*1A[\.\s\-:]*Risk\s*Factors(.*?)(?=Item\s*\d|PART\s*II|$)",
        r"RISK\s*FACTORS(.*?)(?=Item\s*\d|PART\s*II|$)",
        r"Factors\s*That\s*May\s*Affect(.*?)(?=Item\s*\d|$)",
    ]

    section_text = _extract_section_text(filing_text, patterns, max_chars=5000)

    if not section_text or len(section_text) < 100:
        return []

    # Try to extract individual risk items
    risks = []

    # Look for bullet points or numbered risks
    risk_patterns = [
        r"[•\-\*]\s*([A-Z][^•\-\*\n]{50,300})",  # Bullet points
        r"(?:^|\n)\s*(\d+[\.\)]\s*[A-Z][^\n]{50,300})",  # Numbered items
    ]

    for pattern in risk_patterns:
        matches = re.findall(pattern, section_text)
        for match in matches[:5]:  # Limit to 5 risks
            clean_text = re.sub(r'\s+', ' ', match).strip()
            if len(clean_text) > 50:
                risks.append({
                    "summary": clean_text[:200] + ("..." if len(clean_text) > 200 else ""),
                    "supporting_evidence": "Extracted from SEC filing Item 1A",
                    "materiality": "medium"
                })

    # If no structured risks found, extract first few sentences as summary
    if not risks and len(section_text) > 100:
        sentences = re.split(r'[.!?]+', section_text)
        summary_sentences = [s.strip() for s in sentences[:3] if len(s.strip()) > 30]
        if summary_sentences:
            risks.append({
                "summary": ". ".join(summary_sentences)[:300],
                "supporting_evidence": "Extracted from SEC filing Risk Factors section",
                "materiality": "medium"
            })

    return risks


def _extract_mda(filing_text: str, filing_type: str = "10-Q") -> str:
    """Extract Management Discussion & Analysis from filing text."""
    if not filing_text:
        return ""

    # Different patterns for 10-K vs 10-Q
    if filing_type == "10-K":
        patterns = [
            r"Item\s*7[\.\s\-:]*Management['']?s?\s*Discussion(.*?)(?=Item\s*7A|Item\s*8|$)",
            r"MANAGEMENT['']?S?\s*DISCUSSION\s*AND\s*ANALYSIS(.*?)(?=Item\s*\d|$)",
        ]
    else:  # 10-Q
        patterns = [
            r"Item\s*2[\.\s\-:]*Management['']?s?\s*Discussion(.*?)(?=Item\s*3|Item\s*4|$)",
            r"MANAGEMENT['']?S?\s*DISCUSSION\s*AND\s*ANALYSIS(.*?)(?=Item\s*\d|$)",
        ]

    section_text = _extract_section_text(filing_text, patterns, max_chars=3000)

    if section_text and len(section_text) > 100:
        # Clean up and format
        return f"**From the SEC Filing MD&A:**\n\n{section_text}"

    return ""


def generate_xbrl_summary(
    xbrl_data: Optional[Dict[str, Any]],
    company_name: str,
    filing_date: str = "Unknown Date",
    filing_text: Optional[str] = None,
    filing_type: Optional[str] = None,
    filing_excerpt: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate a fallback summary when AI analysis times out.

    This function extracts REAL content from the filing text when available,
    rather than just showing placeholder text. This ensures users always
    receive valuable information even when the full AI analysis fails.

    Args:
        xbrl_data: Standardized XBRL metrics (may be None)
        company_name: Company name for display
        filing_date: Filing date string
        filing_text: Full filing text for content extraction
        filing_type: Type of filing (10-K, 10-Q, etc.)
        filing_excerpt: Pre-extracted critical sections (Risk Factors + MD&A)

    IMPORTANT: This function must NEVER return empty sections.
    Users must always see meaningful content, even if all extractions fail.
    """
    filing_type = (filing_type or "10-Q").upper()

    # Defaults
    business_overview = f"## Quick Summary for {company_name}\n\n"
    business_overview += "The full AI analysis is taking longer than expected. Here is a preliminary overview based on available filing data.\n\n"

    # Extract metrics if available
    metrics_summary = []
    # Use has_valid_xbrl_data() to properly check for data
    # An empty dict {} is falsy, so `if xbrl_data:` would skip valid responses
    has_xbrl_data = has_valid_xbrl_data(xbrl_data)

    if has_xbrl_data:
        # Note: xbrl_data is guaranteed truthy by has_valid_xbrl_data()
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
        business_overview += "Financial metrics are being processed.\n\n"

    business_overview += "> **Note:** This is a partial summary. You can retry generating the full analysis below."

    # ALWAYS provide financial_highlights with meaningful structure
    if has_xbrl_data:
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
        # Show clear "Not available" messaging instead of misleading "Loading..."
        # The user should understand this data isn't coming - they need to retry
        financial_highlights = {
            "table": [
                {
                    "metric": "Revenue",
                    "current_period": "Not available",
                    "prior_period": "Not available",
                    "change": "—",
                    "commentary": "XBRL data unavailable. Retry for full financial analysis."
                },
                {
                    "metric": "Net Income",
                    "current_period": "Not available",
                    "prior_period": "Not available",
                    "change": "—",
                    "commentary": "XBRL data unavailable. Retry for full financial analysis."
                }
            ],
            "profitability": ["Financial metrics not available in this partial summary. Retry for complete analysis."],
            "cash_flow": ["Financial metrics not available in this partial summary. Retry for complete analysis."],
            "balance_sheet": ["Financial metrics not available in this partial summary. Retry for complete analysis."]
        }

    # EXTRACT REAL RISK FACTORS from filing text
    # Priority: filing_excerpt > filing_text > placeholder
    risk_factors = []

    text_source = filing_excerpt or filing_text
    if text_source:
        try:
            extracted_risks = _extract_risk_factors(text_source, filing_type)
            if extracted_risks:
                risk_factors = extracted_risks
                logger.info(f"Extracted {len(risk_factors)} risk factors from filing text")
        except Exception as e:
            logger.warning(f"Failed to extract risk factors: {e}")

    # Fallback if extraction failed
    if not risk_factors:
        risk_factors = [
            {
                "summary": f"Risk factors for {company_name} are available in the full SEC filing.",
                "supporting_evidence": "Retry generation for AI-powered risk analysis.",
                "materiality": "pending"
            }
        ]

    # EXTRACT REAL MD&A from filing text
    management_discussion = ""

    if text_source:
        try:
            extracted_mda = _extract_mda(text_source, filing_type)
            if extracted_mda and len(extracted_mda) > 100:
                management_discussion = extracted_mda
                logger.info("Extracted MD&A from filing text")
        except Exception as e:
            logger.warning(f"Failed to extract MD&A: {e}")

    # Fallback if extraction failed
    if not management_discussion:
        management_discussion = (
            f"**{company_name}** management discussion is available in the full SEC filing. "
            "Retry generation for AI-powered MD&A analysis covering business operations, "
            "financial condition, and management's perspective on future outlook."
        )

    # Key changes - always placeholder since this requires AI analysis
    key_changes = (
        "Key changes and notable developments require AI analysis to identify. "
        "Retry generation for detailed change analysis comparing to prior periods."
    )

    # Build the raw_summary.sections structure that frontend expects
    # Frontend reads from raw_summary.sections for ALL tabs
    sections_for_frontend = {
        "executive_snapshot": {
            "headline": f"{company_name} {filing_type or 'SEC'} Filing - Partial Analysis",
            "key_points": [
                "Financial metrics extracted from XBRL data" if has_xbrl_data else "XBRL metrics unavailable for this filing",
                f"{len(risk_factors)} risk factors identified from filing" if risk_factors else "Risk factors require full AI analysis",
                "MD&A excerpt extracted from filing" if management_discussion and "From the SEC Filing" in management_discussion else "MD&A requires full AI analysis",
                "Click 'Retry Full Analysis' for complete AI-powered insights"
            ],
            "tone": "neutral"
        },
        # Financial highlights - frontend expects this in sections
        "financial_highlights": financial_highlights,
        # Risk factors - already in correct format
        "risk_factors": risk_factors,
        # MD&A - frontend expects 'management_discussion_insights' with specific structure
        "management_discussion_insights": {
            "themes": [management_discussion] if management_discussion else ["Management discussion requires full AI analysis. Please retry."],
            "quotes": [],
            "capital_allocation": []
        },
        # Guidance - frontend expects 'guidance_outlook'
        "guidance_outlook": {
            "outlook": key_changes,
            "targets": [],
            "assumptions": []
        },
        # Liquidity - placeholder for frontend
        "liquidity_capital_structure": {
            "summary": "Liquidity analysis requires full AI processing. Please retry for detailed capital structure insights.",
            "metrics": [],
            "concerns": []
        },
        # Trends - placeholder for frontend
        "three_year_trend": {
            "summary": "Trend analysis requires full AI processing. Please retry for multi-period comparison.",
            "metrics": []
        }
    }

    # Calculate coverage dynamically based on actual section content
    # This provides accurate feedback to the frontend about what data is available
    total_sections = 7  # exec_snapshot, financials, risks, mda, guidance, liquidity, trends

    covered_sections = 1  # executive_snapshot is always populated

    # Check if financial_highlights has real data (not just placeholders)
    if has_xbrl_data and financial_highlights.get("table"):
        table_has_data = any(
            row.get("current_period") not in (None, "Not available", "Loading...")
            for row in financial_highlights.get("table", [])
        )
        if table_has_data:
            covered_sections += 1

    # Check if risk_factors has real extracted content
    if risk_factors and len(risk_factors) > 0:
        # Check it's not just placeholder content
        first_risk = risk_factors[0] if risk_factors else {}
        if not first_risk.get("summary", "").startswith("Risk factors for"):
            covered_sections += 1

    # Check if management_discussion has real extracted content
    if management_discussion and "From the SEC Filing" in management_discussion:
        covered_sections += 1

    # guidance_outlook, liquidity_capital_structure, three_year_trend are always placeholders (0)

    coverage_ratio = round(covered_sections / total_sections, 2)

    return {
        "status": "partial",
        "message": "Full analysis timed out. Showing extracted filing data.",
        "business_overview": business_overview,
        "financial_highlights": financial_highlights,
        "risk_factors": risk_factors,
        "management_discussion": management_discussion,
        "key_changes": key_changes,
        "raw_summary": {
            "sections": sections_for_frontend,
            "section_coverage": {
                "covered_count": covered_sections,
                "total_count": total_sections,
                "coverage_ratio": coverage_ratio
            }
        }
    }
