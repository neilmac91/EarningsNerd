from __future__ import annotations

from openai import AsyncOpenAI
from typing import Any, Dict, Optional
from app.config import settings
import json
import re
from bs4 import BeautifulSoup

_PLACEHOLDER_STRINGS = {
    "",
    "n/a",
    "na",
    "none",
    "not available",
    "not disclosed",
    "not provided",
    "-",
    "--",
    "—",
    "n.a.",
}

_BOILERPLATE_RISK_PHRASES = {
    "cash flow and debt levels are concerning",
}


def _normalize_simple_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (list, tuple, set)):
        joined = " ".join(str(v).strip() for v in value if v)
        value = joined
    text = str(value).strip()
    if not text:
        return None
    lowered = text.lower()
    if lowered in _PLACEHOLDER_STRINGS:
        return None
    return text


def _normalize_evidence(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, dict):
        parts: list[str] = []
        for key in ("excerpt", "text", "quote", "support", "source", "reference", "tag", "xbrl_tag", "citation"):
            if key in value:
                part = _normalize_evidence(value.get(key))
                if part:
                    parts.append(part)
        combined = " | ".join(parts)
        return _normalize_simple_string(combined) if combined else None
    if isinstance(value, (list, tuple, set)):
        parts = [ev for item in value if (ev := _normalize_evidence(item))]
        combined = "; ".join(parts)
        return _normalize_simple_string(combined) if combined else None
    return _normalize_simple_string(value)


def _normalize_risk_factors(raw_risks: Any) -> list[dict[str, str]]:
    if raw_risks is None:
        return []

    raw_items: list[Any] = []
    if isinstance(raw_risks, list):
        raw_items = raw_risks
    elif isinstance(raw_risks, dict):
        # Accept either explicit list container or dict keyed by identifiers
        for value in raw_risks.values():
            if isinstance(value, list):
                raw_items.extend(value)
            else:
                raw_items.append(value)
    else:
        raw_items = [raw_risks]

    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for entry in raw_items:
        summary: Optional[str] = None
        description: Optional[str] = None
        title: Optional[str] = None
        evidence: Optional[str] = None

        if isinstance(entry, dict):
            summary = (
                _normalize_simple_string(entry.get("summary"))
                or _normalize_simple_string(entry.get("description"))
                or _normalize_simple_string(entry.get("detail"))
                or _normalize_simple_string(entry.get("text"))
                or _normalize_simple_string(entry.get("title"))
            )
            title = _normalize_simple_string(entry.get("title"))
            description = _normalize_simple_string(entry.get("description"))
            evidence = (
                _normalize_evidence(entry.get("supporting_evidence"))
                or _normalize_evidence(entry.get("supportingEvidence"))
                or _normalize_evidence(entry.get("evidence"))
                or _normalize_evidence(entry.get("source"))
            )
        else:
            summary = _normalize_simple_string(entry)
            evidence = None

        if not summary:
            continue

        normalized_key = summary.lower()
        if normalized_key in _BOILERPLATE_RISK_PHRASES and not evidence:
            continue

        if not evidence:
            # Require supporting evidence for each bullet
            continue

        dedupe_key = (normalized_key, evidence.lower())
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        normalized_entry: dict[str, str] = {
            "summary": summary,
            "supporting_evidence": evidence,
        }
        if title:
            normalized_entry["title"] = title
        if description and description != summary:
            normalized_entry["description"] = description

        normalized.append(normalized_entry)

    return normalized

class OpenAIService:
    def __init__(self):
        # Use OpenRouter base URL if configured
        base_url = settings.OPENAI_BASE_URL if hasattr(settings, 'OPENAI_BASE_URL') else None
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=base_url
        )
        # OpenRouter compatible model names
        # Optimized for speed and cost-effectiveness
        self.model = "google/gemini-flash-1.5"  # Fast, cost-effective default
        # Fallback models in case primary is rate-limited (prioritize free/low-cost)
        self._fallback_models = [
            "google/gemini-flash-1.5",
            "meta-llama/llama-3.2-3b-instruct:free",
            "meta-llama/llama-3.1-8b-instruct"
        ]
        # Dedicated writer preferences for editorial stage
        self._writer_models = [
            "openai/gpt-4.1-mini",
            "meta-llama/llama-3.1-70b-instruct",
            "meta-llama/llama-3.1-8b-instruct",
            "google/gemini-flash-1.5",
        ]
        # Set optimized models for each filing type (ensure consistent quality)
        self._model_overrides = {
            "10-K": "meta-llama/llama-3.1-8b-instruct",  # Better quality for longer docs
            "10-Q": "meta-llama/llama-3.1-8b-instruct",  # Align quality with 10-K summaries
            "8-K": "meta-llama/llama-3.1-8b-instruct"  # Align quality with 10-K summaries
        }

    def get_model_for_filing(self, filing_type: Optional[str]) -> str:
        """Return the model to use for a given filing type.

        Optimized for speed and cost:
        - 8-K: meta-llama/llama-3.1-8b-instruct (consistent with 10-K)
        - 10-Q: meta-llama/llama-3.1-8b-instruct (consistent with 10-K)
        - 10-K: meta-llama/llama-3.1-8b-instruct (better quality for longer docs)
        """
        if not filing_type:
            return self.model
        return self._model_overrides.get(filing_type.upper(), self.model)
    
    def _get_type_config(self, filing_type: str) -> Dict[str, Any]:
        base_config: Dict[str, Any] = {
            "sample_length": 25000,
            "previous_section_limit": 15000,
            "ai_timeout": 40.0,  # Optimized for 10-K
            "max_tokens": 1500,  # Optimized for quality
            "max_sections": 6,
            "section_priority": [
                "business",
                "mda",
                "financials",
                "risk_factors",
                "liquidity",
                "segments",
                "guidance",
                "footnotes"
            ],
            "section_limits": {
                "business": 15000,
                "risk_factors": 15000,
                "financials": 12000,
                "mda": 15000,
                "liquidity": 12000,
                "segments": 10000,
                "guidance": 8000,
                "footnotes": 8000
            }
        }

        overrides = {
            "10-K": {
                "ai_timeout": 40.0,  # Leaves 20s buffer for processing
                "max_tokens": 1500
            },
            "10-Q": {
                "sample_length": 22000,
                "previous_section_limit": 15000,
                "ai_timeout": 35.0,  # Allow longer extraction for dense 10-Qs
                "max_tokens": 1400,  # Slightly higher to cover expanded context
                "max_sections": 4,
                "section_limits": {
                    "business": 10000,
                    "risk_factors": 10000,
                    "financials": 10000,
                    "mda": 10000,
                    "liquidity": 8000,
                    "segments": 8000,
                    "guidance": 6000,
                    "footnotes": 6000
                }
            },
            "8-K": {
                "sample_length": 8000,
                "previous_section_limit": 6000,
                "ai_timeout": 8.0,  # Leaves 7s buffer for processing
                "max_tokens": 1000,  # Reduced for faster responses
                "max_sections": 2,
                "section_limits": {
                    "business": 5000,
                    "risk_factors": 4000,
                    "financials": 4000,
                    "mda": 4000,
                    "liquidity": 3000,
                    "segments": 3000,
                    "guidance": 3000,
                    "footnotes": 3000
                }
            }
        }

        key = filing_type.upper() if filing_type else ""
        config = base_config.copy()
        if key in overrides:
            override = overrides[key]
            for k, v in override.items():
                if k == "section_limits":
                    # Merge limits to avoid mutating base dict for other types
                    merged_limits = config["section_limits"].copy()
                    merged_limits.update(v)
                    config["section_limits"] = merged_limits
                else:
                    config[k] = v
        return config

    def _build_section_sample(self, sections: Dict[str, str], config: Dict[str, Any], max_length: Optional[int] = None) -> str:
        priority_order = config.get("section_priority", [])
        parts = []
        for key in priority_order:
            content = sections.get(key)
            if content:
                header = key.replace("_", " ").title()
                parts.append(f"{header}:\n{content}")
        combined = "\n\n".join(parts).strip()
        limit = max_length or config.get("sample_length", 25000)
        if combined:
            return combined[:limit]
        return ""
    
    def extract_critical_sections(self, filing_text: str, filing_type: str = "10-K") -> str:
        """Extract ONLY the most critical sections for fast summarization.
        
        For 10-K: Item 1A (Risk Factors) and Item 7 (MD&A)
        For 10-Q: Item 1A (Risk Factors) and Item 2 (MD&A)
        For 8-K: Extract the main content sections
        
        Returns: Concatenated text from critical sections only
        """
        filing_type_key = (filing_type or "10-K").upper()
        
        # Remove HTML/XML tags for cleaner extraction
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(filing_text, 'html.parser')
            filing_text_clean = soup.get_text(separator='\n', strip=False)
        except:
            filing_text_clean = filing_text
        
        critical_sections = []
        
        if filing_type_key == "10-K":
            # Extract Item 1A - Risk Factors
            risk_patterns = [
                r"ITEM\s+1A\.\s*RISK\s+FACTORS[^\n]*\n(.*?)(?=ITEM\s+2|ITEM\s+7|PART\s+II|$)",
                r"PART\s+I[^\n]*\n.*?ITEM\s+1A\.\s*RISK\s+FACTORS[^\n]*\n(.*?)(?=ITEM\s+2|ITEM\s+7|PART\s+II|$)",
                r"Risk\s+Factors[^\n]*\n(.*?)(?=ITEM\s+2|ITEM\s+7|PART\s+II|$)"
            ]
            for pattern in risk_patterns:
                match = re.search(pattern, filing_text_clean, re.IGNORECASE | re.DOTALL | re.MULTILINE)
                if match:
                    risk_text = match.group(1).strip()
                    # Limit to 15000 chars for 10-K (optimized for speed)
                    critical_sections.append(f"ITEM 1A - RISK FACTORS:\n{risk_text[:15000]}")
                    break
            
            # Extract Item 7 - MD&A
            mda_patterns = [
                r"PART\s+II[^\n]*\n.*?ITEM\s+7\.\s*MANAGEMENT['\']?S\s+DISCUSSION[^\n]*\n(.*?)(?=ITEM\s+7A|ITEM\s+8|ITEM\s+9|$)",
                r"ITEM\s+7\.\s*MANAGEMENT['\']?S\s+DISCUSSION[^\n]*\n(.*?)(?=ITEM\s+7A|ITEM\s+8|ITEM\s+9|$)",
                r"Management['\']?s\s+Discussion\s+and\s+Analysis[^\n]*\n(.*?)(?=ITEM\s+8|Financial|$)"
            ]
            for pattern in mda_patterns:
                match = re.search(pattern, filing_text_clean, re.IGNORECASE | re.DOTALL | re.MULTILINE)
                if match:
                    mda_text = match.group(1).strip()
                    # Limit to 20000 chars for 10-K (optimized for speed)
                    critical_sections.append(f"ITEM 7 - MANAGEMENT'S DISCUSSION AND ANALYSIS:\n{mda_text[:20000]}")
                    break
        
        elif filing_type_key == "10-Q":
            # Extract Item 1A - Risk Factors
            risk_patterns = [
                r"ITEM\s+1A\.\s*RISK\s+FACTORS[^\n]*\n(.*?)(?=ITEM\s+2|ITEM\s+7|PART\s+II|$)",
                r"Risk\s+Factors[^\n]*\n(.*?)(?=ITEM\s+2|ITEM\s+7|PART\s+II|$)"
            ]
            for pattern in risk_patterns:
                match = re.search(pattern, filing_text_clean, re.IGNORECASE | re.DOTALL | re.MULTILINE)
                if match:
                    risk_text = match.group(1).strip()
                    # Limit to 8000 chars for 10-Q (optimized for speed)
                    critical_sections.append(f"ITEM 1A - RISK FACTORS:\n{risk_text[:8000]}")
                    break
            
            # Extract Item 2 - MD&A (for 10-Q)
            mda_patterns = [
                r"ITEM\s+2\.\s*MANAGEMENT['\']?S\s+DISCUSSION[^\n]*\n(.*?)(?=ITEM\s+3|ITEM\s+4|ITEM\s+5|$)",
                r"Management['\']?s\s+Discussion\s+and\s+Analysis[^\n]*\n(.*?)(?=ITEM\s+3|Financial|$)"
            ]
            for pattern in mda_patterns:
                match = re.search(pattern, filing_text_clean, re.IGNORECASE | re.DOTALL | re.MULTILINE)
                if match:
                    mda_text = match.group(1).strip()
                    # Limit to 12000 chars for 10-Q (optimized for speed)
                    critical_sections.append(f"ITEM 2 - MANAGEMENT'S DISCUSSION AND ANALYSIS:\n{mda_text[:12000]}")
                    break
        
        elif filing_type_key == "8-K":
            # For 8-K, extract the main content sections (usually shorter)
            # Try to find the main body content
            content_patterns = [
                r"ITEM\s+[0-9]\.\s+[^\n]*\n(.*?)(?=ITEM\s+[0-9]|SIGNATURE|$)",
            ]
            for pattern in content_patterns:
                matches = re.finditer(pattern, filing_text_clean, re.IGNORECASE | re.DOTALL | re.MULTILINE)
                for match in list(matches)[:3]:  # Get first 3 items
                    content = match.group(0).strip()
                    if len(content) > 500:  # Only include substantial content
                        # Limit to 10000 chars for 8-K (already optimized)
                        critical_sections.append(content[:10000])
        
        # Combine all critical sections
        if critical_sections:
            return "\n\n".join(critical_sections)
        else:
            # Fallback: return first 15000 chars if no sections found
            return filing_text_clean[:15000]
    
    def extract_sections(self, filing_text: str, filing_type: str = "10-K") -> Dict[str, str]:
        """Extract key sections from filing text with improved patterns"""
        sections = {
            "business": "",
            "risk_factors": "",
            "financials": "",
            "mda": "",
            "liquidity": "",
            "segments": "",
            "guidance": "",
            "footnotes": ""
        }
        
        # Remove HTML/XML tags for cleaner extraction
        filing_text_clean = filing_text
        
        config = self._get_type_config(filing_type)
        section_limits = config.get("section_limits", {})

        # Business section - Item 1
        business_patterns = [
            r"ITEM\s+1\.\s*BUSINESS[^\n]*\n(.*?)(?=ITEM\s+1A|ITEM\s+2|PART\s+II|$)",
            r"PART\s+I[^\n]*\n.*?ITEM\s+1\.\s*BUSINESS[^\n]*\n(.*?)(?=ITEM\s+1A|ITEM\s+2|PART\s+II|$)",
            r"Description\s+of\s+Business[^\n]*\n(.*?)(?=Risk\s+Factors|ITEM\s+1A|ITEM\s+2|$)"
        ]
        for pattern in business_patterns:
            match = re.search(pattern, filing_text_clean, re.IGNORECASE | re.DOTALL | re.MULTILINE)
            if match:
                limit = section_limits.get("business", 15000)
                sections["business"] = match.group(1)[:limit].strip()
                break
        
        # Risk Factors - Item 1A
        risk_patterns = [
            r"ITEM\s+1A\.\s*RISK\s+FACTORS[^\n]*\n(.*?)(?=ITEM\s+2|ITEM\s+7|PART\s+II|$)",
            r"PART\s+I[^\n]*\n.*?ITEM\s+1A\.\s*RISK\s+FACTORS[^\n]*\n(.*?)(?=ITEM\s+2|ITEM\s+7|PART\s+II|$)",
            r"Risk\s+Factors[^\n]*\n(.*?)(?=ITEM\s+2|ITEM\s+7|PART\s+II|$)"
        ]
        for pattern in risk_patterns:
            match = re.search(pattern, filing_text_clean, re.IGNORECASE | re.DOTALL | re.MULTILINE)
            if match:
                extracted = match.group(1).strip()
                limit = section_limits.get("risk_factors", 15000)
                sections["risk_factors"] = re.sub(r'\s+', ' ', extracted)[:limit].strip()
                break
        
        # MD&A - Item 7 (Part II)
        mda_patterns = [
            r"PART\s+II[^\n]*\n.*?ITEM\s+7\.\s*MANAGEMENT['\']?S\s+DISCUSSION[^\n]*\n(.*?)(?=ITEM\s+7A|ITEM\s+8|ITEM\s+9|$)",
            r"ITEM\s+7\.\s*MANAGEMENT['\']?S\s+DISCUSSION[^\n]*\n(.*?)(?=ITEM\s+7A|ITEM\s+8|ITEM\s+9|$)",
            r"Management['\']?s\s+Discussion\s+and\s+Analysis[^\n]*\n(.*?)(?=ITEM\s+8|Financial|$)"
        ]
        for pattern in mda_patterns:
            match = re.search(pattern, filing_text_clean, re.IGNORECASE | re.DOTALL | re.MULTILINE)
            if match:
                extracted = match.group(1).strip()
                limit = section_limits.get("mda", 15000)
                sections["mda"] = re.sub(r'\s+', ' ', extracted)[:limit].strip()
                break
        
        # Financials - Item 8 (Part II)
        financial_patterns = [
            r"PART\s+II[^\n]*\n.*?ITEM\s+8\.\s*FINANCIAL[^\n]*\n(.*?)(?=ITEM\s+9|ITEM\s+15|$)",
            r"ITEM\s+8\.\s*FINANCIAL[^\n]*\n(.*?)(?=ITEM\s+9|ITEM\s+15|$)",
            r"Consolidated\s+Statements\s+of\s+Operations[^\n]*\n(.*?)(?=ITEM\s+9|NOTE|$)"
        ]
        for pattern in financial_patterns:
            match = re.search(pattern, filing_text_clean, re.IGNORECASE | re.DOTALL | re.MULTILINE)
            if match:
                extracted = match.group(1).strip()
                limit = section_limits.get("financials", 12000)
                sections["financials"] = re.sub(r'\s+', ' ', extracted)[:limit].strip()
                break
        
        # Liquidity and capital resources (often in MD&A or separate section)
        liquidity_patterns = [
            r"LIQUIDITY\s+AND\s+CAPITAL\s+RESOURCES[^\n]*\n(.*?)(?=ITEM\s+8|ITEM\s+9|CAPITAL|$)",
            r"Liquidity\s+and\s+Capital\s+Resources[^\n]*\n(.*?)(?=ITEM\s+8|ITEM\s+9|CAPITAL|$)",
            r"Cash\s+Flows[^\n]*\n(.*?)(?=ITEM\s+8|ITEM\s+9|$)"
        ]
        for pattern in liquidity_patterns:
            match = re.search(pattern, filing_text_clean, re.IGNORECASE | re.DOTALL | re.MULTILINE)
            if match:
                extracted = match.group(1).strip()
                limit = section_limits.get("liquidity", 12000)
                sections["liquidity"] = re.sub(r'\s+', ' ', extracted)[:limit].strip()
                break

        # Segment performance
        segment_patterns = [
            r"SEGMENT\s+INFORMATION[^\n]*\n(.*?)(?=ITEM\s+8|ITEM\s+9|NOTE|$)",
            r"SEGMENT\s+RESULTS[^\n]*\n(.*?)(?=ITEM\s+8|ITEM\s+9|NOTE|$)",
            r"RESULTS\s+BY\s+SEGMENT[^\n]*\n(.*?)(?=ITEM\s+8|ITEM\s+9|NOTE|$)",
            r"Our\s+Services\s+segment[^\n]*\n(.*?)(?=ITEM\s+8|ITEM\s+9|NOTE|$)"
        ]
        for pattern in segment_patterns:
            match = re.search(pattern, filing_text_clean, re.IGNORECASE | re.DOTALL | re.MULTILINE)
            if match:
                extracted = match.group(1).strip()
                limit = section_limits.get("segments", 10000)
                sections["segments"] = re.sub(r'\s+', ' ', extracted)[:limit].strip()
                break

        # Guidance / outlook (often in MD&A)
        guidance_patterns = [
            r"OUTLOOK[^\n]*\n(.*?)(?=ITEM\s+8|ITEM\s+9|NOTE|$)",
            r"GUIDANCE[^\n]*\n(.*?)(?=ITEM\s+8|ITEM\s+9|NOTE|$)",
            r"Future\s+Outlook[^\n]*\n(.*?)(?=ITEM\s+8|ITEM\s+9|NOTE|$)",
            r"Looking\s+Forward[^\n]*\n(.*?)(?=ITEM\s+8|ITEM\s+9|NOTE|$)"
        ]
        for pattern in guidance_patterns:
            match = re.search(pattern, filing_text_clean, re.IGNORECASE | re.DOTALL | re.MULTILINE)
            if match:
                extracted = match.group(1).strip()
                limit = section_limits.get("guidance", 8000)
                sections["guidance"] = re.sub(r'\s+', ' ', extracted)[:limit].strip()
                break

        # Footnotes / other notes (capture first few Note sections)
        footnote_matches = list(re.finditer(r"NOTE\s+\d+[^\n]*\n(.*?)(?=NOTE\s+\d+|ITEM|$)", filing_text_clean, re.IGNORECASE | re.DOTALL))
        if footnote_matches:
            # Combine first 3 notes
            footnote_text = ""
            for match in footnote_matches[:3]:
                note_text = match.group(0).strip()
                limit = section_limits.get("footnotes", 8000)
                footnote_text += re.sub(r'\s+', ' ', note_text)[:limit] + "\n\n"
            sections["footnotes"] = footnote_text[:section_limits.get("footnotes", 8000)].strip()

        max_sections = config.get("max_sections")
        if max_sections:
            kept = 0
            for key in config.get("section_priority", []):
                content = sections.get(key)
                if content:
                    kept += 1
                    if kept > max_sections:
                        sections[key] = ""
        
        return sections
    
    def extract_financial_data(self, text_content: str) -> Dict[str, list]:
        """Extract specific financial figures from filing text"""
        data = {
            'revenue': [],
            'net_income': [],
            'cash_flow': [],
            'segments': [],
            'guidance': [],
            'risks': []
        }

        # Revenue patterns
        revenue_patterns = [
            r'revenue[s]?\s+(?:of\s+)?[\$]?(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[MBK]?',
            r'net\s+sales?\s+(?:of\s+)?[\$]?(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[MBK]?',
            r'total\s+revenue[s]?\s+[\$]?(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[MBK]?',
        ]
        for pattern in revenue_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            data['revenue'].extend(matches)

        # Net income patterns
        income_patterns = [
            r'net\s+income\s+(?:of\s+)?[\$]?(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[MBK]?',
            r'net\s+earnings\s+(?:of\s+)?[\$]?(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[MBK]?',
            r'profit\s+(?:of\s+)?[\$]?(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[MBK]?',
        ]
        for pattern in income_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            data['net_income'].extend(matches)

        # Cash flow patterns
        cash_patterns = [
            r'cash\s+flow\s+(?:from\s+operations?\s+)?[\$]?(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[MBK]?',
            r'free\s+cash\s+flow\s+[\$]?(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[MBK]?',
            r'operating\s+cash\s+flow\s+[\$]?(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[MBK]?',
        ]
        for pattern in cash_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            data['cash_flow'].extend(matches)

        # Segment data (company-specific)
        segment_patterns = [
            r'(iPhone|Mac|iPad|Services|Wearables|Home)\s+(?:net\s+)?sales?\s+[\$]?(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[MBK]?',
            r'(Americas|Europe|Greater\s+China|Japan|Rest\s+of\s+Asia\s+Pacific)\s+(?:net\s+)?sales?\s+[\$]?(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[MBK]?',
        ]
        for pattern in segment_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            data['segments'].extend(matches)

        # Guidance patterns
        guidance_patterns = [
            r'guidance\s+(?:of\s+|for\s+)?[\$]?(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[MBK]?',
            r'expect.*?(?:revenue|sales)\s+(?:of\s+|to\s+be\s+)?[\$]?(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[MBK]?',
        ]
        for pattern in guidance_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            data['guidance'].extend(matches)

        # Clean and deduplicate
        for key in data:
            data[key] = list(set(data[key]))  # Remove duplicates
            data[key] = sorted(data[key], key=lambda x: float(x.replace(',', '')), reverse=True)[:5]  # Top 5 by value

        return data

    def _clean_json_payload(self, content: str) -> str:
        """Strip markdown fences and surrounding whitespace from LLM JSON payloads."""
        if not content:
            return ""
        cleaned = content.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        return cleaned.strip()

    def _validate_editorial_markdown(self, markdown: str) -> None:
        """Validate editorial output for newsroom standards."""
        if not markdown or len(markdown.strip()) == 0:
            raise ValueError("Writer returned empty markdown output.")

        # Reject outputs containing raw JSON artefacts
        import re
        json_pattern = re.compile(r"\{[^{}]*\"[^{}]*:[^{}]*\}")
        if json_pattern.search(markdown):
            raise ValueError("Writer output contains raw JSON artefacts.")
        if "```json" in markdown.lower():
            raise ValueError("Writer output includes JSON code fences.")

        total_word_count = len(markdown.split())
        if total_word_count < 200 or total_word_count > 300:
            raise ValueError(f"Editorial summary length must be 200-300 words (current: {total_word_count}).")

        # Ensure sections exist and each stays within word budget
        sections = {}
        current_heading = None
        for line in markdown.splitlines():
            if line.startswith("## "):
                current_heading = line[3:].strip()
                sections[current_heading] = []
            elif current_heading is not None:
                sections[current_heading].append(line)

        required_sections = {
            "Executive Summary",
            "Financials",
            "Risks",
            "Management Commentary",
            "Outlook",
        }

        missing_sections = required_sections - set(sections.keys())
        if missing_sections:
            raise ValueError(f"Writer output missing required sections: {', '.join(sorted(missing_sections))}.")

        for heading, lines in sections.items():
            word_count = len(" ".join(lines).split())
            if word_count > 400:
                raise ValueError(f"Section '{heading}' exceeds 400-word limit ({word_count} words).")

        # Flag unformatted large numeric tokens (>=5 digits without separators or suffix)
        large_number_pattern = re.compile(r"\b\d{5,}\b")
        problematic_numbers = [
            token for token in large_number_pattern.findall(markdown)
            if not token.startswith(("20", "19"))  # allow years like 2023
        ]
        if problematic_numbers:
            raise ValueError(
                f"Writer output includes potentially unformatted figures: {', '.join(problematic_numbers[:5])}."
            )

    def _build_structured_markdown(
        self,
        structured_summary: Dict[str, Any],
        failure_reason: Optional[str] = None,
    ) -> str:
        """Fallback: render Markdown directly from structured data when the writer LLM output fails validation."""
        metadata = structured_summary.get("metadata", {}) or {}
        sections = structured_summary.get("sections", {}) or {}

        company_name = metadata.get("company_name") or "The company"
        filing_type = metadata.get("filing_type") or "filing"
        reporting_period = metadata.get("reporting_period") or metadata.get("reportingPeriod") or "the reporting period"

        lines: list[str] = []
        if failure_reason:
            lines.append(f"*Auto-generated from structured data because the writer output failed validation ({failure_reason}).*")

        # Executive Summary
        exec_section = sections.get("executive_snapshot") or {}
        headline = exec_section.get("headline")
        key_points = exec_section.get("key_points") or exec_section.get("keyPoints") or []
        tone = exec_section.get("tone")

        lines.append("## Executive Summary")
        summary_bits: list[str] = []
        if headline:
            summary_bits.append(headline.strip())
        else:
            summary_bits.append(f"{company_name} filed its {filing_type.upper()} covering {reporting_period}.")
        if tone:
            summary_bits.append(f"Management adopted a {tone} tone.")
        if key_points:
            cleaned_points = "; ".join(point.strip() for point in key_points if point)
            if cleaned_points:
                summary_bits.append(cleaned_points)
        lines.append(" ".join(summary_bits).strip())

        # Financials
        financials = sections.get("financial_highlights") or {}
        table_rows = financials.get("table") or []
        profitability = financials.get("profitability") or []
        cash_flow = financials.get("cash_flow") or financials.get("cashFlow") or []
        balance_sheet = financials.get("balance_sheet") or financials.get("balanceSheet") or []

        lines.append("\n## Financials")
        financial_lines_added = False
        if table_rows:
            for row in table_rows:
                if not isinstance(row, dict):
                    continue
                metric = row.get("metric")
                if not metric:
                    continue
                current_period = row.get("current_period") or row.get("currentPeriod") or "Not disclosed"
                prior_period = row.get("prior_period") or row.get("priorPeriod")
                change = row.get("change")
                commentary = (row.get("commentary") or "").replace("\n", " ").strip()

                bullet = f"- {metric}: {current_period}"
                if prior_period and prior_period != "Not disclosed":
                    bullet += f" vs. {prior_period}"
                if change and change != "Not disclosed":
                    bullet += f" ({change})"
                if commentary:
                    bullet += f" – {commentary}"
                lines.append(bullet)
                financial_lines_added = True
        if profitability:
            lines.append("- Profitability: " + "; ".join(item.strip() for item in profitability if item))
            financial_lines_added = True
        if cash_flow:
            lines.append("- Cash flow: " + "; ".join(item.strip() for item in cash_flow if item))
            financial_lines_added = True
        if balance_sheet:
            lines.append("- Balance sheet: " + "; ".join(item.strip() for item in balance_sheet if item))
            financial_lines_added = True
        if not financial_lines_added:
            lines.append("- Key financial metrics were not disclosed in the structured extract.")

        # Risks
        lines.append("\n## Risks")
        risks = sections.get("risk_factors") or []
        if risks:
            for risk in risks:
                if not isinstance(risk, dict):
                    continue
                summary = (risk.get("summary") or risk.get("title") or "Risk factor not specified").strip()
                evidence = risk.get("supporting_evidence") or risk.get("supportingEvidence")
                bullet = f"- {summary}"
                if evidence:
                    bullet += f" (Evidence: {evidence})"
                lines.append(bullet)
        else:
            lines.append("- No material incremental risks were highlighted beyond routine disclosures.")

        # Management Commentary
        lines.append("\n## Management Commentary")
        mgmt = sections.get("management_discussion_insights") or {}
        themes = mgmt.get("themes") or []
        capital_allocation = mgmt.get("capital_allocation") or mgmt.get("capitalAllocation") or []
        quotes = mgmt.get("quotes") or []
        mgmt_added = False
        if themes:
            lines.append("- Themes: " + "; ".join(item.strip() for item in themes if item))
            mgmt_added = True
        if capital_allocation:
            lines.append("- Capital allocation: " + "; ".join(item.strip() for item in capital_allocation if item))
            mgmt_added = True
        if quotes:
            for quote in quotes:
                if isinstance(quote, dict):
                    text = (quote.get("quote") or "").strip()
                    speaker = (quote.get("speaker") or "").strip()
                    if text:
                        mgmt_added = True
                        if speaker:
                            lines.append(f'> "{text}" – {speaker}')
                        else:
                            lines.append(f'> "{text}"')
        if not mgmt_added:
            lines.append("- Management commentary was limited in the structured extract.")

        # Outlook
        lines.append("\n## Outlook")
        outlook = sections.get("guidance_outlook") or {}
        guidance = outlook.get("guidance")
        tone = outlook.get("tone")
        drivers = outlook.get("drivers") or []
        watch_items = outlook.get("watch_items") or outlook.get("watchItems") or []

        outlook_points: list[str] = []
        if guidance and guidance != "Not disclosed":
            outlook_points.append(f"Guidance: {guidance}")
        if tone:
            outlook_points.append(f"Tone: {tone}")
        if drivers:
            outlook_points.append("Drivers: " + "; ".join(item.strip() for item in drivers if item))
        if watch_items:
            outlook_points.append("Watch items: " + "; ".join(item.strip() for item in watch_items if item))

        if outlook_points:
            for point in outlook_points:
                lines.append(f"- {point}")
        else:
            lines.append("- Guidance was not disclosed; monitor subsequent updates for direction.")

        return "\n".join(lines).strip()

    async def generate_structured_summary(
        self,
        filing_text: str,
        company_name: str,
        filing_type: str,
        previous_filings: Optional[list] = None,
        xbrl_metrics: Optional[Dict] = None,
        filing_excerpt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Phase 1: Extract structured financial schema from the filing."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(filing_text, 'html.parser')
            filing_text_clean = soup.get_text(separator='\n', strip=False)
        except Exception:
            filing_text_clean = filing_text

        filing_type_key = (filing_type or "10-K").upper()
        config = self._get_type_config(filing_type_key)

        filing_sample = filing_excerpt or self.extract_critical_sections(filing_text, filing_type_key)
        if not filing_sample:
            filing_sample = filing_text[:15000]
        financial_data = self.extract_financial_data(filing_sample[:15000])

        xbrl_section = ""
        if xbrl_metrics:
            revenue_info = (xbrl_metrics.get('revenue') or {}).get('current', {})
            income_info = (xbrl_metrics.get('net_income') or {}).get('current', {})
            eps_info = (xbrl_metrics.get('earnings_per_share') or {}).get('current', {})
            margin_info = (xbrl_metrics.get('net_margin') or {}).get('current', {})

            def _format_currency(value: Optional[float]) -> str:
                return f"${value:,.0f}" if value is not None else "Not disclosed"

            def _format_percent(value: Optional[float]) -> str:
                return f"{value:.1f}%" if value is not None else "Not disclosed"

            xbrl_section = f"""
XBRL STANDARDIZED FINANCIAL DATA (SEC-verified):
- Revenue: {_format_currency(revenue_info.get('value'))} (period: {revenue_info.get('period', 'N/A')})
- Net Income: {_format_currency(income_info.get('value'))} (period: {income_info.get('period', 'N/A')})
- EPS: {eps_info.get('value') if eps_info.get('value') is not None else 'Not disclosed'} (period: {eps_info.get('period', 'N/A')})
- Net Margin: {_format_percent(margin_info.get('value'))} (period: {margin_info.get('period', 'N/A')})
""".strip()

        data_summary = f"""
EXTRACTED FINANCIAL SIGNALS:
- Revenue figures: {', '.join(financial_data['revenue'][:3]) if financial_data['revenue'] else 'Not observed'}
- Net income figures: {', '.join(financial_data['net_income'][:3]) if financial_data['net_income'] else 'Not observed'}
- Cash flow figures: {', '.join(financial_data['cash_flow'][:3]) if financial_data['cash_flow'] else 'Not observed'}
- Key segments: {', '.join([f"{seg[0]}: {seg[1]}" for seg in financial_data['segments'][:3]]) if financial_data['segments'] else 'Not observed'}
- Guidance references: {', '.join(financial_data['guidance'][:2]) if financial_data['guidance'] else 'Not observed'}
{xbrl_section if xbrl_section else ''}
""".strip()

        previous_filings_context = ""
        if filing_type_key == "10-K" and previous_filings:
            previous_filings_context = "\n\n## PREVIOUS 10-K EXCERPTS FOR CONTEXT:\n"
            for i, prev_filing in enumerate(previous_filings[:1], 1):
                prev_filing_date = prev_filing.get("filing_date", "Unknown date")
                prev_text = prev_filing.get("text", "")
                prev_sample = self.extract_critical_sections(prev_text, "10-K") or prev_text[:12000]
                previous_filings_context += f"\n### Prior 10-K {i} ({prev_filing_date}):\n{prev_sample}\n"

        focus_guidance = {
            "8-K": [
                "- Capture discrete events and quantify immediate financial or strategic impact.",
                "- Identify any material non-recurring adjustments or regulatory issues."
            ],
            "10-Q": [
                "- Highlight sequential and year-on-year momentum for this quarter.",
                "- Connect quarterly execution to full-year guidance and structural themes."
            ],
            "10-K": [
                "- Evaluate year-long shifts in growth, profitability, cash generation, and capital allocation."
            ]
        }
        analysis_focus_lines = focus_guidance.get(filing_type_key, focus_guidance["10-K"])

        schema_template = """{
  "metadata": {
    "company_name": "<non-empty string>",
    "filing_type": "<non-empty string>",
    "reporting_period": "<non-empty string>",
    "filing_date": "<non-empty string>",
    "currency": "<non-empty string>",
    "has_prior_period": <bool>
  },
  "sections": {
    "executive_snapshot": {
      "headline": "<non-empty string>",
      "key_points": [
        "<non-empty bullet>",
        "... (use ['Not disclosed—explain why'] if no validated bullets)"
      ],
      "tone": "<positive|neutral|cautious>"
    },
    "financial_highlights": {
      "table": [
        {"metric": "<non-empty string>", "current_period": "<non-empty string>", "prior_period": "<non-empty string>", "change": "<non-empty string>", "commentary": "<non-empty string>"}
      ],
      "profitability": ["<non-empty bullet>"],
      "cash_flow": ["<non-empty bullet>"],
      "balance_sheet": ["<non-empty bullet>"]
    },
    "risk_factors": [
      {"summary": "<non-empty string>", "supporting_evidence": "<non-empty excerpt or citation>", "materiality": "<low|medium|high>"}
    ],
    "management_discussion_insights": {
      "themes": ["<non-empty bullet>"],
      "quotes": [{"speaker": "<non-empty string>", "quote": "<non-empty string>", "context": "<non-empty string>"}],
      "capital_allocation": ["<non-empty bullet>"]
    },
    "segment_performance": [
      {"segment": "<non-empty string>", "revenue": "<non-empty string>", "change": "<non-empty string>", "commentary": "<non-empty string>"}
    ],
    "liquidity_capital_structure": {
      "leverage": "<non-empty string>",
      "liquidity": "<non-empty string>",
      "shareholder_returns": ["<non-empty bullet>"]
    },
    "guidance_outlook": {
      "guidance": "<non-empty string>",
      "tone": "<positive|neutral|cautious>",
      "drivers": ["<non-empty bullet>"],
      "watch_items": ["<non-empty bullet>"]
    },
    "notable_footnotes": [
      {"item": "<non-empty string>", "impact": "<non-empty string>"}
    ],
    "three_year_trend": {
      "trend_summary": "<non-empty string>",
      "inflections": ["<non-empty bullet>"],
      "compare_prior_period": {
        "available": <bool>,
        "insights": ["<non-empty bullet>"]
      }
    }
  }
}"""

        prompt = f"""You are a forensic financial analyst preparing structured briefing materials for newsroom editors.

Company: {company_name}
Filing type: {filing_type}

Use the extracted context below to populate quantitative and qualitative data. Focus on concrete, verifiable metrics and management disclosures. Avoid prose paragraphs; capture facts in concise data fields.

Guidance for emphasis:
- {" ".join(analysis_focus_lines)}
- Only cite figures present in the excerpts or XBRL data.
- If prior-period data is unavailable, set related fields to "Not disclosed" and mark "has_prior_period": false.

{data_summary}

CRITICAL FILING EXCERPTS:
{filing_sample}
{previous_filings_context}

Return ONLY valid JSON (no markdown fences) that matches this schema (replace placeholders with actual values or meaningful nulls). Every string must contain substantive content—never emit blank strings or placeholder tokens. Arrays must never be empty; if no verifiable bullet exists, supply a single-element array with "Not disclosed—<concise reason>":
{schema_template}

Rules:
- Keep monetary values human-readable (e.g., "$17.7B", "$425M", "$912M").
- Express percentage changes with one decimal place where available (e.g., "up 8.3% YoY").
- For arrays, include 1-4 high-signal, evidence-backed bullets ordered by materiality. If nothing qualifies, return ["Not disclosed—<concise reason>"] instead of leaving the array empty.
- Empty sections are unacceptable. Do not fabricate data; explain the absence using the Not disclosed pattern when required.
- Provide supporting evidence excerpts for each risk factor (direct quote or XBRL tag reference)."""

        import asyncio
        models_to_try = [self.get_model_for_filing(filing_type_key)] + self._fallback_models
        models_to_try = list(dict.fromkeys(models_to_try))

        response = None
        last_error: Optional[Exception] = None
        for model_name in models_to_try:
            try:
                response = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {
                                "role": "system",
                                "content": (
                                    "You are a structured data extraction engine for financial journalism. "
                                    "You never write narrative prose. You output clean JSON that adheres strictly "
                                    "to the requested schema, filling in 'Not disclosed' when data is missing. "
                                    "Never invent prior-period figures."
                                ),
                            },
                            {"role": "user", "content": prompt},
                        ],
                        temperature=0.2,
                        max_tokens=config.get("max_tokens", 1500),
                    ),
                    timeout=config.get("ai_timeout", 25.0),
                )
                break
            except Exception as model_error:
                error_msg = str(model_error)
                last_error = model_error
                if any(keyword in error_msg.lower() for keyword in ("rate limit", "429", "model", "unavailable")):
                    print(f"Structured extraction model {model_name} failed ({error_msg[:120]}). Trying next model...")
                    continue
                raise

        if response is None:
            raise last_error if last_error else RuntimeError("All extraction models failed.")

        content = response.choices[0].message.content
        payload = self._clean_json_payload(content or "")

        if not payload:
            raise ValueError("Extraction model returned empty payload.")

        try:
            summary_data = json.loads(payload)
        except json.JSONDecodeError as json_error:
            print(f"Structured summary JSON error: {json_error}")
            print(f"Raw payload (first 500 chars): {payload[:500]}")
            raise

        return summary_data

    async def generate_editorial_markdown(self, structured_summary: Dict[str, Any]) -> Dict[str, Any]:
        """Phase 2: Convert structured schema into polished newsroom-ready markdown."""
        import asyncio

        if not structured_summary:
            raise ValueError("Structured summary payload is empty.")

        metadata = structured_summary.get("metadata", {})
        company_name = metadata.get("company_name", "The company")
        filing_type = metadata.get("filing_type", "filing")
        reporting_period = metadata.get("reporting_period", "the reported period")

        structured_payload = json.dumps(structured_summary, indent=2, ensure_ascii=False)

        writer_prompt = f"""You are a senior financial journalist writing for an audience of professional investors.

Write a summary of an SEC filing based on the structured financial data provided below.

Structured data (JSON):
{structured_payload}

Style:
- Professional, analytical, and concise — similar to Bloomberg or The Economist.
- Begin with 1–2 sentences capturing the headline narrative.
- Integrate key figures naturally within sentences (e.g., "Net income climbed to $17.7 billion, up 8% year-on-year").
- Avoid repeating numbers in isolation or labeling them as "current period".
- Omit comparative commentary if prior-period data is missing.
- Use natural transitions ("Meanwhile", "In contrast", "However").
- Summaries should interpret data — highlight trends, risks, or strategic signals.
- Length: 200–300 words total across all sections.

Output Markdown with headings: Executive Summary, Financials, Risks, Management Commentary, Outlook.

Rules:
- Do not invent figures beyond the structured data. If data is missing, state that it was not disclosed.
- Use currency suffixes (e.g., "$17.7B", "$482M") and percentage formatting (e.g., "29%") when citing numbers.
- Keep tone neutral-to-confident, informative, and newsroom-ready.
- Return Markdown only — no JSON, code fences, or additional commentary.
"""

        system_message = (
            "You are an award-winning financial journalist for a Tier 1 financial publication. "
            "Write with authority, clarity, and precision. Style references: Bloomberg, The Economist, Financial Times. "
            "You deliver narrative cohesion, emphasize materiality, and integrate numbers seamlessly."
        )

        response = None
        last_error: Optional[Exception] = None
        for model_name in self._writer_models:
            try:
                response = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": system_message},
                            {"role": "user", "content": writer_prompt},
                        ],
                        temperature=0.4,
                        max_tokens=900,
                    ),
                    timeout=18.0,
                )
                break
            except Exception as model_error:
                error_msg = str(model_error)
                last_error = model_error
                if any(keyword in error_msg.lower() for keyword in ("rate limit", "429", "model", "unavailable")):
                    print(f"Writer model {model_name} failed ({error_msg[:120]}). Trying next model...")
                    continue
                raise

        if response is None:
            raise last_error if last_error else RuntimeError("All writer models failed.")

        content = response.choices[0].message.content or ""
        markdown = content.strip()
        model_used = response.model if hasattr(response, "model") else None

        try:
            self._validate_editorial_markdown(markdown)
            word_count = len(markdown.split())
            return {
                "markdown": markdown,
                "word_count": word_count,
                "model_used": model_used,
            }
        except Exception as validation_error:
            fallback_markdown = self._build_structured_markdown(structured_summary, str(validation_error))
            word_count = len(fallback_markdown.split())
            return {
                "markdown": fallback_markdown,
                "word_count": word_count,
                "model_used": model_used,
                "fallback_used": True,
                "fallback_reason": str(validation_error),
            }

    async def summarize_filing_stream(
        self,
        filing_text: str,
        company_name: str,
        filing_type: str,
        previous_filings: Optional[list] = None,
        xbrl_metrics: Optional[Dict] = None,
        filing_excerpt: Optional[str] = None,
    ):
        """Generate AI summary of filing with streaming response"""
        # Parse HTML and extract text
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(filing_text, 'html.parser')
            filing_text_clean = soup.get_text(separator='\n', strip=False)
        except:
            filing_text_clean = filing_text

        filing_type_key = (filing_type or "10-K").upper()
        config = self._get_type_config(filing_type_key)

        # OPTIMIZED: Extract ONLY critical sections (Item 1A and Item 7 for 10-K)
        filing_sample = filing_excerpt or self.extract_critical_sections(filing_text, filing_type_key)
        if not filing_sample:
            filing_sample = filing_text[:15000]
        
        # Extract financial data from the critical sections for context
        financial_data = self.extract_financial_data(filing_sample[:15000])

        # Build enhanced prompt with specific financial data
        xbrl_section = ""
        if xbrl_metrics:
            revenue_info = (xbrl_metrics.get('revenue') or {}).get('current', {})
            income_info = (xbrl_metrics.get('net_income') or {}).get('current', {})
            eps_info = (xbrl_metrics.get('earnings_per_share') or {}).get('current', {})
            margin_info = (xbrl_metrics.get('net_margin') or {}).get('current', {})
            
            revenue_value = revenue_info.get('value')
            income_value = income_info.get('value')
            eps_value = eps_info.get('value')
            margin_value = margin_info.get('value')
            
            revenue_str = f"${revenue_value:,.0f}" if revenue_value is not None else "N/A"
            income_str = f"${income_value:,.0f}" if income_value is not None else "N/A"
            eps_str = f"${eps_value:,.2f}" if eps_value is not None else "N/A"
            margin_str = f"{margin_value:.2f}%" if margin_value is not None else "N/A"
            
            xbrl_section = f"""
XBRL STANDARDIZED FINANCIAL DATA (SEC-Verified):
- Revenue: {revenue_str} (period: {revenue_info.get('period', 'N/A')})
- Net Income: {income_str} (period: {income_info.get('period', 'N/A')})
- EPS: {eps_str} (period: {eps_info.get('period', 'N/A')})
- Net Margin: {margin_str} (period: {margin_info.get('period', 'N/A')})
"""
        
        data_summary = f"""
EXTRACTED FINANCIAL DATA FROM FILING:
- Revenue figures: {', '.join(financial_data['revenue'][:3]) if financial_data['revenue'] else 'Not found'}
- Net income figures: {', '.join(financial_data['net_income'][:3]) if financial_data['net_income'] else 'Not found'}
- Cash flow figures: {', '.join(financial_data['cash_flow'][:3]) if financial_data['cash_flow'] else 'Not found'}
- Key segments: {', '.join([f"{seg[0]}: {seg[1]}" for seg in financial_data['segments'][:3]]) if financial_data['segments'] else 'Not found'}
- Guidance figures: {', '.join(financial_data['guidance'][:2]) if financial_data['guidance'] else 'Not found'}
{xbrl_section}
"""

        # Build previous filings context if available and applicable
        previous_filings_context = ""
        if filing_type_key == "10-K" and previous_filings:
            previous_filings_context = "\n\n## PREVIOUS 10-K FILINGS FOR TREND ANALYSIS:\n"
            for i, prev_filing in enumerate(previous_filings[:1], 1):
                prev_filing_date = prev_filing.get("filing_date", "Unknown date")
                prev_text = prev_filing.get("text", "")
                prev_sample = self.extract_critical_sections(prev_text, "10-K")
                if not prev_sample:
                    prev_sample = prev_text[:15000]
                previous_filings_context += f"\n### Previous 10-K {i} ({prev_filing_date}):\n{prev_sample}\n"

        focus_guidance = {
            "8-K": [
                "- Prioritize the discrete events and triggers disclosed in this 8-K.",
                "- Quantify immediate financial or strategic impact and required investor actions."
            ],
            "10-Q": [
                "- Emphasize sequential and year-over-year trends for this quarter.",
                "- Connect quarterly execution to full-year guidance and strategic priorities."
            ],
            "10-K": [
                "- Evaluate long-term competitiveness, structural shifts, and capital allocation over the full year."
            ]
        }
        analysis_focus_lines = focus_guidance.get(filing_type_key, focus_guidance["10-K"])
        analysis_focus_block = "\n".join(analysis_focus_lines)

        if filing_type_key == "10-K" and previous_filings_context:
            trend_section_instruction = """## 3-Year Investment Perspective
- Tie the past three annual filings together to explain how the investment case is evolving.
- Highlight structural improvements or deterioration in growth, margins, cash flow, and balance sheet quality.
- Explicitly state what the three-year trajectory implies for valuation and forward positioning.
"""
        elif filing_type_key == "10-Q":
            trend_section_instruction = """## Trend Perspective (Populate `three_year_trend`)
- Summarize momentum across the last six to eight quarters so investors see the trajectory.
- Call out inflections in revenue mix, margins, liquidity, or guidance that change the thesis.
"""
        else:
            trend_section_instruction = """## Context & Recent History (Populate `three_year_trend`)
- Provide concise context from the most recent annual or quarterly filings so investors understand the baseline.
- If limited data is available, explain why and outline what to monitor next.
"""
        
        prompt = f"""You are a top-tier financial advisor and public market investor with over 30 years of experience analyzing companies at the highest level. You've advised institutional investors, managed billions in assets, and have a track record of identifying winners and avoiding losers. Your analysis is trusted by the most sophisticated investors in the market.

Your task: Analyze {company_name}'s {filing_type} filing and provide key takeaways from a professional investor's perspective. Think like a portfolio manager making a multimillion-dollar investment decision.

IMPORTANT: The text below contains ONLY the most critical sections extracted from the filing:
- For 10-K: Item 1A (Risk Factors) and Item 7 (Management's Discussion and Analysis)
- For 10-Q: Item 1A (Risk Factors) and Item 2 (Management's Discussion and Analysis)
- For 8-K: Key disclosure items

This focused extraction allows for faster, more targeted analysis while maintaining the essential information needed for investment decisions.

{data_summary}

CRITICAL SECTIONS FROM FILING:
{filing_sample}
{previous_filings_context}

ANALYSIS FRAMEWORK:
{analysis_focus_block}
1. Use the EXTRACTED FINANCIAL DATA above - cite specific numbers, percentages, and dollar amounts
2. Focus on what matters to professional investors: cash flow, margins, debt, competitive position, management quality
3. Identify the KEY investment thesis drivers - what makes this company investable or problematic?
4. Be direct and decisive - no hedging or generic statements
5. Highlight what institutional investors would focus on: execution quality, market position, financial health, strategic clarity
6. Only include bullets you can prove. Every risk or notable item must cite specific supporting evidence (exact filing excerpt or XBRL tag) in the `supporting_evidence` field.
6. Only include bullets you can prove. Every risk or notable item must cite specific supporting evidence (exact filing excerpt or XBRL tag) in the `supporting_evidence` field.

Create a professional investment analysis UNDER 800 words with the following sections:

## Executive Assessment
- Lead with the bottom line: What does this filing tell us about the company's investment case?
- What are the 2-3 most critical developments that an experienced investor needs to know?
- Frame it as a portfolio manager would: "This company shows X because of Y, which suggests Z for investors."

## Financial Performance Analysis
| Metric | Current Period | Prior Period | Investor Takeaway |
| --- | --- | --- | --- |
- Use actual figures from the filing. For each metric, explain what it means for the investment case.
- Focus on quality of earnings: Are they sustainable? Are margins improving or deteriorating?
- Cash flow analysis: Can the company fund growth and return capital?

## Management Strategy & Execution
- Assess management's strategic vision and execution quality
- What are their priorities? Are they focused on the right things?
- Quote specific management commentary that reveals their thinking
- Evaluate: Is this a management team you'd trust with capital?

## Investment Risks & Concerns
- Prioritize risks that could materially impact the investment thesis
- Distinguish between normal business risks and red flags
- What keeps experienced investors up at night about this company?
- Are risks increasing, decreasing, or stable?

## Business Segment Analysis
- Use actual segment data. Which businesses are growing/declining and why?
- What does segment performance tell us about competitive position?
- Are there structural shifts in the business model investors should understand?

## Financial Health & Capital Allocation
- Assess balance sheet strength: Can they weather a downturn?
- Cash flow quality: Are earnings converting to cash?
- Capital allocation: How are they deploying capital? Is it creating value?
- Debt levels: Sustainable or concerning?

## Forward Outlook & Investment Implications
- What does management's guidance imply for the investment case?
- What are the key assumptions underlying the outlook?
- What would need to happen for this to be a winning investment?
- What could go wrong?

## Notable Items Requiring Attention
- Accounting changes, litigation, or regulatory matters that could impact valuation
- Hidden liabilities or off-balance-sheet items
- One-time items vs. recurring trends

{trend_section_instruction}

WRITING STYLE:
- Write as a seasoned financial advisor would to a sophisticated client
- Use professional investment terminology
- Be direct and decisive - no waffling
- Focus on what matters for investment decisions
- Assume your reader is making a significant investment decision
- Use specific numbers and percentages to support your analysis
- Keep total length under 800 words

Return ONLY valid JSON (no Markdown code fences) with this structure:
{{
  "markdown": "<full markdown summary>",
  "sections": {{
    "executive_snapshot": "...",
    "financial_highlights": {{
      "table": [
        {{"metric": "...", "current_period": "...", "prior_period": "...", "commentary": "..."}}
      ],
      "notes": "..."
    }},
    "management_discussion_insights": "...",
    "risk_factors": [
      {{"summary": "...", "supporting_evidence": "..."}}
    ],
    "segment_performance": "...",
    "liquidity_capital_structure": "...",
    "guidance_outlook": "...",
    "notable_footnotes": "...",
    "three_year_trend": "..."
  }}
}}

Do not include any additional keys or text outside the JSON object."""

        try:
            import asyncio
            # Try models in order, starting with primary model, then fallbacks
            models_to_try = [self.get_model_for_filing(filing_type_key)] + self._fallback_models
            models_to_try = list(dict.fromkeys(models_to_try))
            
            for model_name in models_to_try:
                try:
                    stream = await self.client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": "You are a top-tier financial advisor and public market investor with over 30 years of experience. You analyze companies from a professional investor's perspective, focusing on what matters for investment decisions. You write with the authority and insight of someone who has advised institutional investors and managed billions in assets. Always return valid JSON with the exact structure requested. Use specific financial data provided and support all analysis with actual numbers. Be direct, decisive, and investment-focused."},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.3,
                        max_tokens=config.get("max_tokens", 1500),
                        stream=True  # Enable streaming
                    )
                    print(f"Successfully using streaming model: {model_name}")
                    async for chunk in stream:
                        if chunk.choices and len(chunk.choices) > 0:
                            delta = chunk.choices[0].delta
                            if delta and delta.content:
                                yield delta.content
                    break  # Success, exit loop
                except Exception as model_error:
                    error_msg = str(model_error)
                    # If rate-limited or model not found, try next model
                    if "rate limit" in error_msg.lower() or "429" in error_msg or "not found" in error_msg.lower() or "model" in error_msg.lower():
                        print(f"Model {model_name} failed ({error_msg[:100]}), trying next model...")
                        continue
                    else:
                        raise
        except Exception as e:
            error_msg = str(e)
            yield f"\n\n[Error: {error_msg[:200]}]"

    async def summarize_filing(
        self,
        filing_text: str,
        company_name: str,
        filing_type: str,
        previous_filings: Optional[list] = None,
        xbrl_metrics: Optional[Dict] = None,
        filing_excerpt: Optional[str] = None,
    ) -> Dict:
        """Generate newsroom-ready summary using structured extraction + editorial writer phases."""
        import asyncio

        filing_type_key = (filing_type or "10-K").upper()
        try:
            structured_summary = await self.generate_structured_summary(
                filing_text,
                company_name,
                filing_type,
                previous_filings=previous_filings,
                xbrl_metrics=xbrl_metrics,
                filing_excerpt=filing_excerpt,
            )
        except asyncio.TimeoutError:
            timeout_seconds = self._get_type_config(filing_type_key).get("ai_timeout", 30.0)
            print(f"Structured extraction timed out after {timeout_seconds}s for {filing_type_key}")
            return {
                "business_overview": "Summary temporarily unavailable — please retry.",
                "financial_highlights": {},
                "risk_factors": [],
                "management_discussion": "",
                "key_changes": "",
                "raw_summary": {"error": "structured_extraction_timeout", "timeout_seconds": timeout_seconds},
            }
        except Exception as extraction_error:
            error_msg = str(extraction_error)
            print(f"Structured extraction error: {error_msg}")
            return {
                "business_overview": "Summary temporarily unavailable — please retry.",
                "financial_highlights": {},
                "risk_factors": [],
                "management_discussion": "",
                "key_changes": "",
                "raw_summary": {"error": "structured_extraction_failed", "detail": error_msg[:500]},
            }

        sections_info = structured_summary.get("sections", {}) or {}
        financial_section = sections_info.get("financial_highlights")

        raw_risk_section = sections_info.get("risk_factors")
        if isinstance(raw_risk_section, str):
            raw_risk_section = [raw_risk_section]
        risk_section = _normalize_risk_factors(raw_risk_section)
        sections_info["risk_factors"] = risk_section

        def _stringify(value: Any) -> Optional[str]:
            if value is None:
                return None
            if isinstance(value, str):
                return value.strip()
            if isinstance(value, list):
                formatted_items = []
                for item in value:
                    item_str = _stringify(item)
                    if item_str:
                        formatted_items.append(f"- {item_str}")
                return "\n".join(formatted_items) if formatted_items else None
            if isinstance(value, dict):
                lines = []
                for key, content in value.items():
                    content_str = _stringify(content)
                    if content_str:
                        pretty_key = key.replace("_", " ").title()
                        lines.append(f"{pretty_key}: {content_str}")
                return "\n".join(lines) if lines else None
            return str(value)

        management_section_structured = sections_info.get("management_discussion_insights")
        management_section = _stringify(management_section_structured)
        guidance_structured = sections_info.get("guidance_outlook")
        guidance_section = _stringify(guidance_structured)

        writer_result = None
        writer_error: Optional[str] = None
        writer_fallback_reason: Optional[str] = None
        try:
            writer_result = await self.generate_editorial_markdown(structured_summary)
            final_markdown = writer_result.get("markdown", "").strip()
            if writer_result.get("fallback_used"):
                fallback_reason = writer_result.get("fallback_reason") or "Writer output failed validation; structured fallback applied."
                writer_fallback_reason = fallback_reason
        except Exception as writer_exc:
            writer_error = str(writer_exc)
            print(f"Writer stage failed: {writer_error}")
            final_markdown = "Summary temporarily unavailable — please retry."

        raw_summary_payload = {
            "structured": structured_summary,
            "sections": sections_info,
        }
        if writer_result:
            raw_summary_payload["writer"] = writer_result
        if writer_fallback_reason:
            raw_summary_payload["writer_fallback_reason"] = writer_fallback_reason
        if writer_error:
            raw_summary_payload["writer_error"] = writer_error[:500]

        return {
            "business_overview": final_markdown,
            "financial_highlights": financial_section,
            "risk_factors": risk_section,
            "management_discussion": management_section,
            "key_changes": guidance_section,
            "raw_summary": raw_summary_payload,
        }

openai_service = OpenAIService()

