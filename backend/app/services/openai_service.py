from __future__ import annotations

import asyncio
import logging
from openai import AsyncOpenAI
from typing import Any, Dict, List, Optional, Tuple
from app.config import settings
from app.services.prompt_loader import get_prompt
import json
import re
from bs4 import BeautifulSoup

# Import json_repair for robust LLM JSON handling
try:
    from json_repair import repair_json as json_repair_lib
    HAS_JSON_REPAIR = True
except ImportError:
    HAS_JSON_REPAIR = False
    json_repair_lib = None

logger = logging.getLogger(__name__)

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

_TRACKED_STRUCTURED_SECTIONS = (
    "executive_snapshot",
    "financial_highlights",
    "risk_factors",
    "management_discussion_insights",
    "segment_performance",
    "liquidity_capital_structure",
    "guidance_outlook",
    "notable_footnotes",
    "three_year_trend",
)


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


def _section_has_content(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return False
        if stripped.lower() in _PLACEHOLDER_STRINGS:
            return False
        return True
    if isinstance(value, dict):
        return any(_section_has_content(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_section_has_content(item) for item in value)
    return True


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

        # If no evidence provided, use a default message instead of discarding the risk
        # This preserves legitimate risks that the AI extracted but didn't provide evidence for
        if not evidence:
            evidence = "See SEC filing for full details."

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
        # Use Google AI Studio base URL if configured
        base_url = settings.OPENAI_BASE_URL if hasattr(settings, 'OPENAI_BASE_URL') else None
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=base_url
        )
        # Model name constants for maintainability
        self._MODEL_GEMINI_3_PRO = "gemini-3-pro-preview"
        self._MODEL_GEMINI_2_5_PRO = "gemini-2.5-pro"
        self._MODEL_GEMINI_2_5_FLASH = "gemini-2.5-flash"

        # Google AI Studio model names
        # Updated to use Gemini Pro 3.0 for highest quality outputs
        self.model = self._MODEL_GEMINI_3_PRO  # Gemini Pro 3.0 (high-precision multimodal reasoning)
        # Fallback models in case primary is rate-limited
        self._fallback_models = [
            self._MODEL_GEMINI_3_PRO,
            self._MODEL_GEMINI_2_5_PRO,
            self._MODEL_GEMINI_2_5_FLASH
        ]
        # Dedicated writer preferences for editorial stage
        self._writer_models = [
            self._MODEL_GEMINI_3_PRO,  # Highest quality for writing
            self._MODEL_GEMINI_2_5_PRO,
            self._MODEL_GEMINI_2_5_FLASH,
        ]
        # Set optimized models for each filing type - all use Gemini Pro 3.0
        self._model_overrides = {
            "10-K": self._MODEL_GEMINI_3_PRO,  # Gemini Pro 3.0 for 10-K
            "10-Q": self._MODEL_GEMINI_3_PRO,  # Gemini Pro 3.0 for 10-Q
        }
        # Task-specific model selection for cost optimization
        # Uses cheaper/faster models for simpler tasks
        self._task_models = {
            "structured_extraction": self._MODEL_GEMINI_3_PRO,   # Needs high accuracy
            "section_recovery": self._MODEL_GEMINI_2_5_FLASH,    # Simpler task, lower cost
            "editorial_writer": self._MODEL_GEMINI_2_5_PRO,      # Creative but constrained
        }
        # Concurrency control for parallel section recovery
        # Limits concurrent API calls to prevent rate limiting
        # Configurable via RECOVERY_MAX_CONCURRENCY setting (default: 3)
        max_concurrency = getattr(settings, 'RECOVERY_MAX_CONCURRENCY', 3)
        self._recovery_semaphore = asyncio.Semaphore(max_concurrency)

    def get_model_for_filing(self, filing_type: Optional[str]) -> str:
        """Return the model to use for a given filing type.

        Using Gemini Pro 3.0 for highest quality outputs:
        - 10-Q: gemini-3-pro-preview (Gemini Pro 3.0)
        - 10-K: gemini-3-pro-preview (Gemini Pro 3.0)
        """
        if not filing_type:
            return self.model
        return self._model_overrides.get(filing_type.upper(), self.model)

    def get_model_for_task(self, task_type: str, filing_type: Optional[str] = None) -> str:
        """Return the appropriate model for a specific task type.

        Task types:
        - structured_extraction: Primary JSON extraction (needs highest accuracy)
        - section_recovery: Fill missing sections (simpler, use Flash for cost savings)
        - editorial_writer: Convert to markdown (creative, use Pro)

        Falls back to filing-type model if task not recognized.
        """
        if task_type in self._task_models:
            return self._task_models[task_type]
        return self.get_model_for_filing(filing_type)

    def _get_type_config(self, filing_type: str) -> Dict[str, Any]:
        # INCREASED LIMITS: Previous limits were too aggressive and caused "Not Disclosed"
        # responses because financial data was being truncated before reaching the AI
        base_config: Dict[str, Any] = {
            "sample_length": 80000,  # Increased from 25000 to capture more content
            "previous_section_limit": 30000,  # Increased from 15000
            "ai_timeout": 120.0,  # Increased for larger content processing
            "max_tokens": 2000,  # Increased for more comprehensive summaries
            "max_sections": 8,  # Increased from 6 to include all key sections
            "section_priority": [
                "financials",  # PRIORITY: Financial statements first
                "mda",         # MD&A has key context
                "risk_factors",
                "business",
                "liquidity",
                "segments",
                "guidance",
                "footnotes"
            ],
            "section_limits": {
                "financials": 40000,  # Increased from 12000 - CRITICAL for metrics
                "mda": 35000,         # Increased from 15000
                "risk_factors": 25000,  # Increased from 15000
                "business": 20000,    # Increased from 15000
                "liquidity": 20000,   # Increased from 12000
                "segments": 15000,    # Increased from 10000
                "guidance": 12000,    # Increased from 8000
                "footnotes": 15000    # Increased from 8000
            }
        }

        overrides = {
            "10-K": {
                "ai_timeout": 150.0,  # More time for larger 10-K filings
                "max_tokens": 2500,
                "sample_length": 100000,  # 10-K filings are larger
                "section_limits": {
                    "financials": 50000,  # 10-K has more detailed financials
                    "mda": 40000,
                    "risk_factors": 30000,
                    "business": 25000,
                    "liquidity": 25000,
                    "segments": 20000,
                    "guidance": 15000,
                    "footnotes": 20000
                }
            },
            "10-Q": {
                "sample_length": 70000,  # Increased from 22000
                "previous_section_limit": 25000,  # Increased from 15000
                "ai_timeout": 100.0,  # Increased from 75
                "max_tokens": 1800,
                "max_sections": 6,
                "section_limits": {
                    "financials": 35000,  # Increased from 10000 - CRITICAL
                    "mda": 30000,         # Increased from 10000
                    "risk_factors": 20000,  # Increased from 10000
                    "business": 15000,    # Increased from 10000
                    "liquidity": 15000,   # Increased from 8000
                    "segments": 12000,    # Increased from 8000
                    "guidance": 10000,    # Increased from 6000
                    "footnotes": 10000    # Increased from 6000
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
    
    def extract_critical_sections(self, filing_text: str, filing_type: str = "10-K", cleaned_text: Optional[str] = None) -> str:
        """Extract ALL critical sections for comprehensive summarization.

        For 10-K: Item 8 (Financial Statements), Item 7 (MD&A), Item 1A (Risk Factors)
        For 10-Q: Item 1 (Financial Statements), Item 2 (MD&A), Item 1A (Risk Factors)

        CRITICAL: Financial Statements MUST be included to extract revenue, net income,
        EPS, cash flow, and other key financial metrics.

        Returns: Concatenated text from critical sections
        """
        filing_type_key = (filing_type or "10-K").upper()

        # Remove HTML/XML tags for cleaner extraction
        # OPTIMIZATION: Use provided cleaned_text if available to avoid re-parsing
        if cleaned_text:
            filing_text_clean = cleaned_text
        else:
            try:
                soup = BeautifulSoup(filing_text, 'html.parser')
                # Preserve table structure by using separator that maintains spacing
                filing_text_clean = soup.get_text(separator='\n', strip=False)
            except Exception:
                filing_text_clean = filing_text

        critical_sections = []

        if filing_type_key == "10-K":
            # PRIORITY 1: Extract Item 8 - Financial Statements (MOST CRITICAL for metrics)
            # Using [\s\S]*? for consistent multiline matching (same as 10-Q patterns)
            financial_patterns = [
                r"ITEM\s*8\.?\s*[-–—]?\s*FINANCIAL\s+STATEMENTS[^\n]*\n([\s\S]*?)(?=\nITEM\s*9\.|\nPART\s*III|\nSIGNATURES|$)",
                r"ITEM\s*8\.?\s*FINANCIAL\s+STATEMENTS\s+AND\s+SUPPLEMENTARY\s+DATA[^\n]*\n([\s\S]*?)(?=\nITEM\s*9\.|\nPART\s*III|$)",
                r"CONSOLIDATED\s+STATEMENTS\s+OF\s+(?:OPERATIONS|INCOME|EARNINGS)[^\n]*\n([\s\S]*?)(?=\nITEM\s*9\.|\nPART\s*III|\nSIGNATURES|$)",
                r"(?:CONSOLIDATED\s+)?FINANCIAL\s+STATEMENTS[^\n]*\n([\s\S]*?)(?=\nNOTES\s+TO\s+CONSOLIDATED|\nITEM\s*9\.|$)",
            ]
            for pattern in financial_patterns:
                match = re.search(pattern, filing_text_clean, re.IGNORECASE | re.MULTILINE)
                if match:
                    financial_text = match.group(1).strip()
                    # Increased limit to 40000 chars to capture full financial statements
                    critical_sections.append(f"ITEM 8 - FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA:\n{financial_text[:40000]}")
                    break

            # PRIORITY 2: Extract Item 7 - MD&A (narrative context for financials)
            # Using [\s\S]*? for consistent multiline matching
            mda_patterns = [
                r"ITEM\s*7\.?\s*[-–—]?\s*MANAGEMENT['']?S?\s+DISCUSSION[^\n]*\n([\s\S]*?)(?=\nITEM\s*7A\.|\nITEM\s*8\.|\nQUANTITATIVE|$)",
                r"ITEM\s*7\.?\s*MANAGEMENT['']?S?\s+DISCUSSION\s+AND\s+ANALYSIS[^\n]*\n([\s\S]*?)(?=\nITEM\s*7A\.|\nITEM\s*8\.|$)",
                r"MANAGEMENT['']?S?\s+DISCUSSION\s+AND\s+ANALYSIS\s+OF\s+FINANCIAL[^\n]*\n([\s\S]*?)(?=\nITEM\s*7A\.|\nITEM\s*8\.|\nQUANTITATIVE|$)",
                r"MD&A[^\n]*\n([\s\S]*?)(?=\nITEM\s*8\.|\nQUANTITATIVE|$)",
            ]
            for pattern in mda_patterns:
                match = re.search(pattern, filing_text_clean, re.IGNORECASE | re.MULTILINE)
                if match:
                    mda_text = match.group(1).strip()
                    # Increased limit to 35000 chars to capture full MD&A
                    critical_sections.append(f"ITEM 7 - MANAGEMENT'S DISCUSSION AND ANALYSIS:\n{mda_text[:35000]}")
                    break

            # PRIORITY 3: Extract Item 1A - Risk Factors
            # Using [\s\S]*? for consistent multiline matching
            risk_patterns = [
                r"ITEM\s*1A\.?\s*[-–—]?\s*RISK\s+FACTORS[^\n]*\n([\s\S]*?)(?=\nITEM\s*1B\.|\nITEM\s*2\.|\nUNRESOLVED|\nPROPERTIES|$)",
                r"ITEM\s*1A\.?\s*RISK\s+FACTORS[^\n]*\n([\s\S]*?)(?=\nITEM\s*2\.|\nPART\s*II|$)",
                r"RISK\s+FACTORS[^\n]*\n([\s\S]*?)(?=\nITEM\s*2\.|\nITEM\s*1B\.|\nPROPERTIES|$)",
            ]
            for pattern in risk_patterns:
                match = re.search(pattern, filing_text_clean, re.IGNORECASE | re.MULTILINE)
                if match:
                    risk_text = match.group(1).strip()
                    # Increased limit to 25000 chars for comprehensive risk coverage
                    critical_sections.append(f"ITEM 1A - RISK FACTORS:\n{risk_text[:25000]}")
                    break

        elif filing_type_key == "10-Q":
            # PRIORITY 1: Extract Item 1 - Financial Statements (MOST CRITICAL for metrics)
            # This is where revenue, net income, EPS, and cash flow data lives!
            # FIXED: Use more specific lookaheads to avoid matching "MANAGEMENT" in content
            financial_patterns = [
                # Match Item 1 header, capture everything until Item 2 header
                r"ITEM\s*1\.?\s*[-–—]?\s*(?:CONDENSED\s+)?(?:CONSOLIDATED\s+)?FINANCIAL\s+STATEMENTS[^\n]*\n([\s\S]*?)(?=\nITEM\s*2\.?\s*[-–—]?\s*MANAGEMENT|\nITEM\s*2\.)",
                r"PART\s*I\s*[-–—]?\s*FINANCIAL\s+INFORMATION[^\n]*\n[\s\S]*?ITEM\s*1\.?[^\n]*\n([\s\S]*?)(?=\nITEM\s*2\.?\s*[-–—]?\s*MANAGEMENT|\nITEM\s*2\.)",
                r"CONDENSED\s+CONSOLIDATED\s+STATEMENTS\s+OF\s+(?:OPERATIONS|INCOME)[^\n]*\n([\s\S]*?)(?=\nITEM\s*2\.?\s*[-–—]?\s*MANAGEMENT|\nITEM\s*2\.)",
                r"(?:CONDENSED\s+)?CONSOLIDATED\s+BALANCE\s+SHEETS?[^\n]*\n([\s\S]*?)(?=\nITEM\s*2\.?\s*[-–—]?\s*MANAGEMENT|\nITEM\s*2\.)",
                r"FINANCIAL\s+STATEMENTS[^\n]*\n([\s\S]*?)(?=\nITEM\s*2\.?\s*[-–—]?\s*MANAGEMENT|\nITEM\s*2\.)",
            ]
            for pattern in financial_patterns:
                match = re.search(pattern, filing_text_clean, re.IGNORECASE | re.DOTALL | re.MULTILINE)
                if match:
                    financial_text = match.group(1).strip()
                    # 35000 chars to capture full condensed financial statements + notes
                    critical_sections.append(f"ITEM 1 - FINANCIAL STATEMENTS:\n{financial_text[:35000]}")
                    break

            # If no financial statements found via patterns, try to find the actual tables
            if not any("FINANCIAL STATEMENTS" in s for s in critical_sections):
                # Fallback: Look for key financial table headers
                table_patterns = [
                    r"((?:CONDENSED\s+)?CONSOLIDATED\s+STATEMENTS?\s+OF\s+OPERATIONS.*?)(?=CONDENSED\s+CONSOLIDATED\s+BALANCE|ITEM\s*2|$)",
                    r"((?:THREE|SIX|NINE)\s+MONTHS\s+ENDED.*?(?:Net\s+(?:income|loss)|Total\s+(?:revenue|net\s+sales)).*?)(?=ITEM\s*2|$)",
                    r"(Revenue[s]?\s*[\$\d,\.]+.*?(?:Net\s+income|Earnings\s+per\s+share).*?)(?=ITEM\s*2|$)",
                ]
                for pattern in table_patterns:
                    match = re.search(pattern, filing_text_clean, re.IGNORECASE | re.DOTALL | re.MULTILINE)
                    if match:
                        financial_text = match.group(1).strip()
                        critical_sections.append(f"FINANCIAL DATA:\n{financial_text[:35000]}")
                        break

            # PRIORITY 2: Extract Item 2 - MD&A (narrative context for financials)
            # FIXED: Use [\s\S]*? for multiline matching and more specific lookaheads
            mda_patterns = [
                r"ITEM\s*2\.?\s*[-–—]?\s*MANAGEMENT['']?S?\s+DISCUSSION[^\n]*\n([\s\S]*?)(?=\nITEM\s*3\.?\s*[-–—]?|\nITEM\s*4\.?\s*[-–—]?|\nQUANTITATIVE|\nCONTROLS|$)",
                r"ITEM\s*2\.?\s*MANAGEMENT['']?S?\s+DISCUSSION\s+AND\s+ANALYSIS[^\n]*\n([\s\S]*?)(?=\nITEM\s*3\.|\nITEM\s*4\.|$)",
                r"MANAGEMENT['']?S?\s+DISCUSSION\s+AND\s+ANALYSIS\s+OF\s+FINANCIAL[^\n]*\n([\s\S]*?)(?=\nITEM\s*3\.|\nQUANTITATIVE|\nCONTROLS|$)",
            ]
            for pattern in mda_patterns:
                match = re.search(pattern, filing_text_clean, re.IGNORECASE | re.MULTILINE)
                if match:
                    mda_text = match.group(1).strip()
                    # Increased to 30000 chars for comprehensive MD&A coverage
                    critical_sections.append(f"ITEM 2 - MANAGEMENT'S DISCUSSION AND ANALYSIS:\n{mda_text[:30000]}")
                    break

            # PRIORITY 3: Extract Item 1A - Risk Factors (if present - not always in 10-Q)
            # FIXED: Use [\s\S]*? for multiline matching
            risk_patterns = [
                r"ITEM\s*1A\.?\s*[-–—]?\s*RISK\s+FACTORS[^\n]*\n([\s\S]*?)(?=\nITEM\s*2\.|\nITEM\s*3\.|\nPART\s*II|$)",
                r"RISK\s+FACTORS[^\n]*\n([\s\S]*?)(?=\nITEM\s*2\.|\nLEGAL|\nPART\s*II|$)",
            ]
            for pattern in risk_patterns:
                match = re.search(pattern, filing_text_clean, re.IGNORECASE | re.MULTILINE)
                if match:
                    risk_text = match.group(1).strip()
                    # 15000 chars for 10-Q risk factors (usually shorter than 10-K)
                    critical_sections.append(f"ITEM 1A - RISK FACTORS:\n{risk_text[:15000]}")
                    break

        # Combine all critical sections
        if critical_sections:
            combined = "\n\n" + "="*50 + "\n\n".join(critical_sections)
            logger.info(f"Extracted {len(critical_sections)} critical sections, total {len(combined):,} chars")
            return combined
        else:
            # Enhanced fallback: Search for ANY financial data in the document
            logger.warning(f"No sections found via patterns, using enhanced fallback extraction")

            # Try to find financial tables anywhere in the document
            financial_keywords = [
                "total revenue", "net revenue", "net sales", "total net sales",
                "net income", "net earnings", "earnings per share", "diluted eps",
                "operating income", "gross profit", "cash flow", "total assets"
            ]

            # Find the section with the most financial keywords
            best_start = 0
            best_score = 0
            chunk_size = 50000

            for i in range(0, min(len(filing_text_clean), 200000), 10000):
                chunk = filing_text_clean[i:i+chunk_size].lower()
                score = sum(1 for kw in financial_keywords if kw in chunk)
                if score > best_score:
                    best_score = score
                    best_start = i

            if best_score > 2:
                logger.info(f"Fallback found {best_score} financial keywords at offset {best_start}")
                return filing_text_clean[best_start:best_start+chunk_size]

            # Last resort: return first 50000 chars
            logger.warning("Using last-resort fallback: first 50000 chars of document")
            return filing_text_clean[:50000]
    
    def extract_sections(self, filing_text: str, filing_type: str = "10-K") -> Dict[str, str]:
        """
        Extract key sections from filing text with improved patterns.
        
        This method gracefully handles missing or corrupted sections by:
        - Returning empty strings for sections that cannot be found
        - Continuing processing even if some sections are missing
        - Using multiple pattern variations to improve extraction success
        - Applying length limits to prevent processing issues
        
        If any section is missing or corrupted, it will be skipped gracefully
        and processing will continue with available sections.
        """
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

    def _repair_json(self, json_str: Optional[str]) -> str:
        """Attempt to repair common JSON syntax errors from LLMs.

        Uses a two-tier approach:
        1. Primary: json-repair library (handles ALL malformed JSON including
           unterminated strings, missing brackets, unescaped chars, etc.)
        2. Fallback: Regex-based repairs (if library unavailable)

        Args:
            json_str: The JSON string to repair, or None.

        Returns:
            Repaired JSON string, or empty string if input is None/empty.
        """
        if not json_str:
            return ""

        # TIER 1: Use json-repair library (handles ALL edge cases)
        if HAS_JSON_REPAIR and json_repair_lib is not None:
            try:
                # Pre-process: Convert Python booleans BEFORE json-repair
                # (json-repair would otherwise quote these as strings)
                preprocessed = re.sub(r'\bTrue\b', 'true', json_str)
                preprocessed = re.sub(r'\bFalse\b', 'false', preprocessed)
                preprocessed = re.sub(r'\bNone\b', 'null', preprocessed)

                # json_repair returns a valid JSON string
                repaired = json_repair_lib(preprocessed)
                if repaired:
                    logger.debug("JSON repair succeeded using json-repair library")
                    return repaired
            except Exception as e:
                logger.warning(f"json-repair library failed: {e}, falling back to regex")

        # TIER 2: Fallback to regex-based repairs
        return self._repair_json_regex(json_str)

    def _repair_json_regex(self, json_str: str) -> str:
        """Regex-based JSON repair for common LLM syntax errors.

        Handles:
        - Unquoted property names (JavaScript-style): {company_name: "val"}
        - Single quotes for keys: {'key': "val"}
        - Single quotes for string values: {"key": 'val'}
        - Single quotes in arrays: ['val1', 'val2']
        - Trailing commas: {"a": 1,}
        - Python booleans: True/False/None -> true/false/null
        """
        repaired = json_str

        # 1. Fix unquoted property names (JavaScript-style object literals)
        repaired = re.sub(
            r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_-]*)(\s*:)',
            r'\1"\2"\3',
            repaired
        )

        # 2. Fix single quotes used for keys
        repaired = re.sub(r"\'([^\']+)\'\s*:", r'"\1":', repaired)

        # 3. Fix single quotes used for string values (after colon)
        repaired = re.sub(r":\s*\'([^\']*)\'(\s*[,}\]])", r': "\1"\2', repaired)

        # 4. Fix single quotes in arrays
        repaired = re.sub(r"\[\s*\'([^\']*)\'", r'["\1"', repaired)
        for _ in range(10):
            new_repaired = re.sub(r",\s*\'([^\']*)\'", r', "\1"', repaired)
            if new_repaired == repaired:
                break
            repaired = new_repaired

        # 5. Fix trailing commas before closing braces/brackets
        repaired = re.sub(r",\s*([\]}])", r"\1", repaired)

        # 6. Fix Python-style booleans and None
        repaired = re.sub(r'\bTrue\b', 'true', repaired)
        repaired = re.sub(r'\bFalse\b', 'false', repaired)
        repaired = re.sub(r'\bNone\b', 'null', repaired)

        return repaired

    def _validate_editorial_markdown(self, markdown: str, filing_type: Optional[str] = None) -> None:
        """
        Validate editorial output for newsroom standards.

        For 10-Q filings, we expect a concise 1‑page, bullet-led structure with
        specific section headings. For other filing types we retain the longer,
        narrative format.
        """
        if not markdown or len(markdown.strip()) == 0:
            raise ValueError("Writer returned empty markdown output.")

        # Reject outputs containing raw JSON artefacts
        import re

        json_pattern = re.compile(r"\{[^{}]*\"[^{}]*:[^{}]*\}")
        if json_pattern.search(markdown):
            raise ValueError("Writer output contains raw JSON artefacts.")
        if "```json" in markdown.lower():
            raise ValueError("Writer output includes JSON code fences.")

        filing_type_key = (filing_type or "").upper()

        # 10-Q: tighter, 1‑page bulletin-style summary
        if filing_type_key == "10-Q":
            min_words, max_words = 120, 260
            required_sections = {
                "Quarter at a Glance",
                "Key Numbers",
                "Guidance & Outlook",
                "Key Risks",
                "Liquidity & Balance Sheet",
            }
        else:
            min_words, max_words = 200, 300
            required_sections = {
                "Executive Summary",
                "Financials",
                "Risks",
                "Management Commentary",
                "Outlook",
            }

        total_word_count = len(markdown.split())
        if total_word_count < min_words or total_word_count > max_words:
            raise ValueError(
                f"Editorial summary length must be {min_words}-{max_words} words "
                f"(current: {total_word_count})."
            )

        # Ensure sections exist and each stays within word budget
        sections: Dict[str, List[str]] = {}
        current_heading: Optional[str] = None
        for line in markdown.splitlines():
            if line.startswith("## "):
                current_heading = line[3:].strip()
                sections[current_heading] = []
            elif current_heading is not None:
                sections[current_heading].append(line)

        missing_sections = required_sections - set(sections.keys())
        if missing_sections:
            raise ValueError(
                f"Writer output missing required sections: {', '.join(sorted(missing_sections))}."
            )

        for heading, lines in sections.items():
            word_count = len(" ".join(lines).split())
            if word_count > 400:
                raise ValueError(f"Section '{heading}' exceeds 400-word limit ({word_count} words).")

        # Flag unformatted large numeric tokens (>=5 digits without separators or suffix)
        large_number_pattern = re.compile(r"\b\d{5,}\b")
        problematic_numbers = [
            token
            for token in large_number_pattern.findall(markdown)
            if not token.startswith(("20", "19"))  # allow years like 2023
        ]
        if problematic_numbers:
            raise ValueError(
                "Writer output includes potentially unformatted figures: "
                f"{', '.join(problematic_numbers[:5])}."
            )

    def _collect_structured_number_strings(self, structured_summary: Dict[str, Any]) -> List[str]:
        """
        Collect human-readable numeric strings from the structured payload.

        This is used as an allow-list when validating that the editorial writer
        is not introducing new, un-backed numeric claims.
        """
        texts: List[str] = []

        metadata = structured_summary.get("metadata") or {}
        for value in metadata.values():
            if isinstance(value, str):
                texts.append(value)

        sections = structured_summary.get("sections") or {}
        financial_section = sections.get("financial_highlights") or {}
        table = financial_section.get("table") or []
        if isinstance(table, list):
            for row in table:
                if not isinstance(row, dict):
                    continue
                for key in ("metric", "current_period", "prior_period", "change", "commentary"):
                    value = row.get(key)
                    if isinstance(value, str):
                        texts.append(value)

        # Also gather any string fields from guidance/liquidity sections where
        # numeric values may legitimately appear.
        guidance = sections.get("guidance_outlook") or {}
        if isinstance(guidance, dict):
            for value in guidance.values():
                if isinstance(value, str):
                    texts.append(value)
                elif isinstance(value, list):
                    texts.extend(str(v) for v in value if isinstance(v, (str, int, float)))

        liquidity = sections.get("liquidity_capital_structure") or {}
        if isinstance(liquidity, dict):
            for value in liquidity.values():
                if isinstance(value, str):
                    texts.append(value)
                elif isinstance(value, list):
                    texts.extend(str(v) for v in value if isinstance(v, (str, int, float)))

        return texts

    def _validate_editorial_numbers(self, markdown: str, structured_summary: Dict[str, Any]) -> None:
        """
        Best-effort check that numeric tokens in the editorial summary are backed
        by the structured data (or clearly represent benign items like years).

        This does *not* guarantee perfection, but it significantly reduces the
        risk of hallucinated figures by forcing the writer to stay within the
        numeric universe extracted in phase 1.
        """
        import re

        source_strings = self._collect_structured_number_strings(structured_summary)
        if not source_strings:
            # Nothing to validate against; skip numeric checks.
            return

        digit_only_source = [re.sub(r"[^\d]", "", s) for s in source_strings if isinstance(s, str)]

        token_pattern = re.compile(r"\$?\d[\d,]*(?:\.\d+)?%?")
        suspicious: List[str] = []

        for token in token_pattern.findall(markdown or ""):
            cleaned = token.strip()
            if not cleaned:
                continue

            digits = re.sub(r"[^\d]", "", cleaned)
            if not digits:
                continue

            # Allow common benign cases:
            # - four-digit years (e.g., 2024)
            # - very small integers (1–2 digits) which are often bullet counts
            if len(digits) == 4 and digits.startswith(("19", "20")):
                continue
            if len(digits) <= 2:
                continue

            # Accept if this numeric token (or its digit-only form) appears in any
            # of the structured strings.
            backed = False
            for src, src_digits in zip(source_strings, digit_only_source):
                if cleaned in src:
                    backed = True
                    break
                if digits and digits == src_digits:
                    backed = True
                    break

            if not backed:
                suspicious.append(cleaned)

        if suspicious:
            unique = sorted({s for s in suspicious})
            raise ValueError(
                "Editorial markdown references numeric values not present in structured data: "
                f"{', '.join(unique[:5])}."
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

    def _section_is_empty(self, value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return _normalize_simple_string(value) is None
        if isinstance(value, (int, float)):
            return False
        if isinstance(value, list):
            return all(self._section_is_empty(item) for item in value)
        if isinstance(value, dict):
            if not value:
                return True
            return all(self._section_is_empty(item) for item in value.values())
        return False

    def _find_empty_sections(self, sections: Dict[str, Any]) -> List[str]:
        ordered_keys = [
            "executive_snapshot",
            "financial_highlights",
            "risk_factors",
            "management_discussion_insights",
            "segment_performance",
            "liquidity_capital_structure",
            "guidance_outlook",
            "notable_footnotes",
            "three_year_trend",
        ]
        empty: List[str] = []
        for key in ordered_keys:
            if self._section_is_empty(sections.get(key)):
                empty.append(key)
        return empty

    def _build_section_context(
        self,
        section_key: str,
        extracted_sections: Dict[str, str],
        filing_sample: str,
    ) -> str:
        section_sources = {
            "executive_snapshot": ["mda", "business", "financials"],
            "financial_highlights": ["financials", "mda"],
            "risk_factors": ["risk_factors"],
            "management_discussion_insights": ["mda"],
            "segment_performance": ["segments", "mda"],
            "liquidity_capital_structure": ["liquidity", "financials"],
            "guidance_outlook": ["guidance", "mda"],
            "notable_footnotes": ["footnotes"],
            "three_year_trend": ["mda", "business"],
        }
        max_length = 6000
        parts: List[str] = []
        for source_key in section_sources.get(section_key, []):
            snippet = extracted_sections.get(source_key)
            if snippet:
                parts.append(snippet)
        if not parts and filing_sample:
            parts.append(filing_sample)
        combined = "\n\n".join(parts).strip()
        return combined[:max_length]

    def _get_section_schema_snippet(self, section_key: str) -> Optional[str]:
        schema_snippets = {
            "executive_snapshot": "{""executive_snapshot"": {""headline"": ""<string>"", ""key_points"": [""<string>""], ""tone"": ""<positive|neutral|cautious>""}}",
            "financial_highlights": "{""financial_highlights"": {""table"": [{""metric"": ""<string>"", ""current_period"": ""<string>"", ""prior_period"": ""<string>"", ""change"": ""<string>"", ""commentary"": ""<string>""}], ""profitability"": [""<string>""], ""cash_flow"": [""<string>""], ""balance_sheet"": [""<string>""]}}",
            "risk_factors": "{""risk_factors"": [{""summary"": ""<string>"", ""supporting_evidence"": ""<string>"", ""materiality"": ""<low|medium|high>""}]}",
            "management_discussion_insights": "{""management_discussion_insights"": {""themes"": [""<string>""], ""quotes"": [{""speaker"": ""<string>"", ""quote"": ""<string>"", ""context"": ""<string>""}], ""capital_allocation"": [""<string>""]}}",
            "segment_performance": "{""segment_performance"": [{""segment"": ""<string>"", ""revenue"": ""<string>"", ""change"": ""<string>"", ""commentary"": ""<string>""}]}",
            "liquidity_capital_structure": "{""liquidity_capital_structure"": {""leverage"": ""<string>"", ""liquidity"": ""<string>"", ""shareholder_returns"": [""<string>""]}}",
            "guidance_outlook": "{""guidance_outlook"": {""guidance"": ""<string>"", ""tone"": ""<positive|neutral|cautious>"", ""drivers"": [""<string>""], ""watch_items"": [""<string>""]}}",
            "notable_footnotes": "{""notable_footnotes"": [{""item"": ""<string>"", ""impact"": ""<string>""}]}",
            "three_year_trend": "{""three_year_trend"": {""trend_summary"": ""<string>"", ""inflections"": [""<string>""], ""compare_prior_period"": {""available"": <bool>, ""insights"": [""<string>""]}}}",
        }
        return schema_snippets.get(section_key)

    async def _run_secondary_completion(
        self,
        filing_type_key: str,
        prompt: str,
        *,
        timeout: float = 12.0,
        max_tokens: int = 350,
    ) -> Optional[str]:
        import asyncio
        import time
        import json

        # Use Flash model for section recovery (simpler task, lower cost)
        models_to_try = [self.get_model_for_task("section_recovery", filing_type_key)] + self._fallback_models
        models_to_try = list(dict.fromkeys(models_to_try))
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
                                    "You fill in missing sections of a structured SEC filing summary. "
                                    "Stay concise, rely only on provided excerpts, and return valid JSON."
                                ),
                            },
                            {"role": "user", "content": prompt},
                        ],
                        temperature=0.1,
                        max_tokens=max_tokens,
                    ),
                    timeout=timeout,
                )
                return response.choices[0].message.content if response.choices else None
            except Exception as model_error:
                error_msg = str(model_error)
                last_error = model_error
                if any(keyword in error_msg.lower() for keyword in ("rate limit", "429", "model", "unavailable")):
                    print(f"Secondary completion model {model_name} failed ({error_msg[:120]}). Trying next model...")
                    continue
                break
        if last_error:
            raise last_error
        return None

    async def _recover_single_section(
        self,
        section_key: str,
        filing_type_key: str,
        extracted_sections: Dict[str, str],
        filing_sample: str,
        metadata: Dict[str, Any],
    ) -> Tuple[str, Optional[Any]]:
        """Recover a single missing section. Returns (section_key, recovered_value or None).

        Uses semaphore to limit concurrent API calls and prevent rate limiting.
        """
        schema_snippet = self._get_section_schema_snippet(section_key)
        if not schema_snippet:
            return section_key, None

        context = self._build_section_context(section_key, extracted_sections, filing_sample)
        if not context:
            return section_key, None

        company_name = metadata.get("company_name", "The company")
        filing_type_label = metadata.get("filing_type", filing_type_key)
        reporting_period = metadata.get("reporting_period", "the reported period")

        prompt = f"""Company: {company_name}
Filing type: {filing_type_label}
Reporting period: {reporting_period}

Populate only the `{section_key}` portion of the structured summary schema shown below. Use concrete facts from the excerpt. If figures are missing, supply concise qualitative statements rather than placeholders.

SCHEMA:
{schema_snippet}

FILING EXCERPT:
{context}

Return JSON containing only the `{section_key}` key."""

        try:
            # Use semaphore to limit concurrent API calls
            async with self._recovery_semaphore:
                content = await self._run_secondary_completion(filing_type_key, prompt)
        except Exception as secondary_error:
            logger.warning(f"Secondary fill for {section_key} failed: {secondary_error}")
            return section_key, None

        if not content:
            return section_key, None

        cleaned = self._clean_json_payload(content)
        if not cleaned:
            return section_key, None

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            # Attempt repair before giving up
            try:
                repaired = self._repair_json(cleaned)
                parsed = json.loads(repaired)
                logger.info(f"JSON repair successful for secondary fill: {section_key}")
            except json.JSONDecodeError:
                logger.warning(f"Secondary fill for {section_key} returned unfixable JSON: {cleaned[:200]}")
                return section_key, None

        section_value = parsed.get(section_key)
        if section_value is not None and not self._section_is_empty(section_value):
            return section_key, section_value

        return section_key, None

    async def _recover_missing_sections(
        self,
        missing_sections: List[str],
        filing_type_key: str,
        extracted_sections: Dict[str, str],
        filing_sample: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Recover missing sections in parallel for improved latency.

        Uses asyncio.gather to run all section recovery tasks concurrently,
        with a semaphore limiting the number of simultaneous API calls.
        This reduces recovery time from 12s * N to approximately 12s total.
        """
        recovered: Dict[str, Any] = {}
        if not missing_sections:
            return recovered

        # Create tasks for all missing sections
        tasks = [
            self._recover_single_section(
                section_key,
                filing_type_key,
                extracted_sections,
                filing_sample,
                metadata,
            )
            for section_key in missing_sections
        ]

        # Execute all recovery tasks in parallel (with semaphore limiting concurrency)
        logger.info(f"Starting parallel recovery for {len(tasks)} sections")
        start_time = asyncio.get_running_loop().time()

        results = await asyncio.gather(*tasks, return_exceptions=True)

        elapsed = asyncio.get_running_loop().time() - start_time
        logger.info(f"Parallel recovery completed in {elapsed:.2f}s for {len(tasks)} sections")

        # Process results
        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Section recovery task failed: {result}")
                continue
            if isinstance(result, tuple) and len(result) == 2:
                section_key, section_value = result
                if section_value is not None:
                    recovered[section_key] = section_value

        return recovered

    def _apply_structured_fallbacks(
        self,
        sections: Dict[str, Any],
        metadata: Dict[str, Any],
        xbrl_metrics: Optional[Dict[str, Any]],
    ) -> None:
        def format_currency(value: Optional[float]) -> Optional[str]:
            if value is None:
                return None
            try:
                abs_value = abs(value)
                if abs_value >= 1_000_000_000:
                    return f"${value / 1_000_000_000:.1f}B"
                if abs_value >= 1_000_000:
                    return f"${value / 1_000_000:.1f}M"
                if abs_value >= 1_000:
                    return f"${value / 1_000:.1f}K"
                return f"${value:,.0f}"
            except Exception:
                return None

        def format_percent(value: Optional[float]) -> Optional[str]:
            if value is None:
                return None
            try:
                return f"{value:.1f}%"
            except Exception:
                return None

        def metric_entry(metric_key: str) -> Dict[str, Any]:
            metric = (xbrl_metrics or {}).get(metric_key) or {}
            current = metric.get("current") or {}
            prior = metric.get("prior") or {}
            formatted_current = format_currency(current.get("value")) if metric_key != "net_margin" else format_percent(current.get("value"))
            formatted_prior = format_currency(prior.get("value")) if metric_key != "net_margin" else format_percent(prior.get("value"))
            return {
                "current": formatted_current,
                "current_period": current.get("period"),
                "prior": formatted_prior,
                "prior_period": prior.get("period"),
            }

        metadata = metadata or {}
        company_name = metadata.get("company_name", "The company")
        reporting_period = metadata.get("reporting_period", "the reported period")

        revenue_info = metric_entry("revenue")
        income_info = metric_entry("net_income")
        margin_info = metric_entry("net_margin")

        if self._section_is_empty(sections.get("executive_snapshot")):
            headline_parts: List[str] = []
            if revenue_info["current"] and revenue_info["current_period"]:
                headline_parts.append(
                    f"Revenue at {revenue_info['current']} for {revenue_info['current_period']}"
                )
            if income_info["current"] and income_info["current_period"]:
                headline_parts.append(
                    f"Net income reported at {income_info['current']}"
                )
            headline = (
                f"{company_name} filing highlights standardized metrics" if headline_parts else f"{company_name} filing provided limited qualitative detail"
            )
            key_points: List[str] = []
            if headline_parts:
                key_points.extend(headline_parts)
            else:
                key_points.append("Core filing excerpts offered minimal narrative detail; review standardized data for context.")
            if margin_info["current"]:
                key_points.append(f"Net margin tracked at {margin_info['current']} based on available XBRL data.")
            sections["executive_snapshot"] = {
                "headline": headline,
                "key_points": key_points,
                "tone": "neutral",
            }

        if self._section_is_empty(sections.get("financial_highlights")):
            table: List[Dict[str, Any]] = []
            if revenue_info["current"]:
                table.append(
                    {
                        "metric": "Revenue",
                        "current_period": revenue_info["current"],
                        "prior_period": revenue_info["prior"] or "Not disclosed",
                        "change": "Not disclosed",
                        "commentary": f"Reported for {revenue_info['current_period'] or reporting_period}.",
                    }
                )
            if income_info["current"]:
                table.append(
                    {
                        "metric": "Net Income",
                        "current_period": income_info["current"],
                        "prior_period": income_info["prior"] or "Not disclosed",
                        "change": "Not disclosed",
                        "commentary": f"Latest standardized value for {income_info['current_period'] or reporting_period}.",
                    }
                )
            if margin_info["current"]:
                table.append(
                    {
                        "metric": "Net Margin",
                        "current_period": margin_info["current"],
                        "prior_period": margin_info["prior"] or "Not disclosed",
                        "change": "Not disclosed",
                        "commentary": "Derived from aligned revenue and income figures.",
                    }
                )
            if not table:
                table.append(
                    {
                        "metric": "Summary",
                        "current_period": "Not disclosed",
                        "prior_period": "Not disclosed",
                        "change": "Not disclosed",
                        "commentary": "Filing excerpts omitted detailed financial metrics; rely on management updates for figures.",
                    }
                )
            sections["financial_highlights"] = {
                "table": table,
                "profitability": [
                    margin_info["current"]
                    and f"Net margin approximately {margin_info['current']} based on standardized data."
                    or "Profitability commentary unavailable in provided excerpts."
                ],
                "cash_flow": [
                    "Cash flow details were not disclosed in the targeted excerpts; monitor future filings for updates."
                ],
                "balance_sheet": [
                    revenue_info["current"]
                    and f"Revenue scale of {revenue_info['current']} provides a proxy for balance sheet size."
                    or "Balance sheet specifics were absent from the extracted text."
                ],
            }

        if self._section_is_empty(sections.get("risk_factors")):
            sections["risk_factors"] = [
                {
                    "summary": "No incremental risks identified in extracted text; rely on full filing for detail.",
                    "supporting_evidence": "Targeted excerpts did not highlight new risk factor language.",
                    "materiality": "low",
                    "source_section_ref": "Item 1A. Risk Factors (not surfaced in sampled excerpts)",
                }
            ]

        if self._section_is_empty(sections.get("management_discussion_insights")):
            sections["management_discussion_insights"] = {
                "themes": [
                    "Management commentary was sparse in the sampled sections; watch for updates in subsequent communications."
                ],
                "quotes": [],
                "capital_allocation": [
                    "No explicit capital allocation remarks were captured in the excerpts."
                ],
                "source_section_ref": "Item 2. MD&A (not surfaced in sampled excerpts)",
            }

        if self._section_is_empty(sections.get("segment_performance")):
            sections["segment_performance"] = [
                {
                    "segment": "Company-wide",
                    "revenue": revenue_info["current"] or "Not disclosed",
                    "change": "Not disclosed",
                    "commentary": "Segment detail was not present; investors should review full filing tables.",
                    "source_section_ref": "Segment disclosures (not surfaced in sampled excerpts)",
                }
            ]

        if self._section_is_empty(sections.get("liquidity_capital_structure")):
            liquidity_line = (
                f"Liquidity not quantified in excerpts; standardized revenue indicates scale of {revenue_info['current']}."
                if revenue_info["current"]
                else "Liquidity metrics were omitted from extracted sections."
            )
            sections["liquidity_capital_structure"] = {
                "leverage": "Debt and leverage commentary not captured in sampled passages.",
                "liquidity": liquidity_line,
                "shareholder_returns": [
                    "No explicit reference to dividends or buybacks within the excerpted text."
                ],
                "source_section_ref": "Liquidity and capital resources (not surfaced in sampled excerpts)",
            }

        if self._section_is_empty(sections.get("guidance_outlook")):
            sections["guidance_outlook"] = {
                "guidance": "Guidance not disclosed in sampled sections.",
                "tone": "neutral",
                "drivers": [
                    revenue_info["current"]
                    and f"Standardized revenue of {revenue_info['current']} provides baseline demand context."
                    or "Key demand drivers were not described."
                ],
                "watch_items": [
                    "Monitor forthcoming management commentary for explicit outlook guidance."
                ],
                "source_section_ref": "Outlook / guidance (not surfaced in sampled excerpts)",
            }

        if self._section_is_empty(sections.get("notable_footnotes")):
            sections["notable_footnotes"] = [
                {
                    "item": "No specific footnotes surfaced in the extracted passages.",
                    "impact": "Review the full filing footnotes for accounting nuances or adjustments.",
                    "source_section_ref": "Footnotes (not surfaced in sampled excerpts)",
                }
            ]

        if self._section_is_empty(sections.get("three_year_trend")):
            trend_summary = (
                revenue_info["current"]
                and f"Latest standardized revenue of {revenue_info['current']} anchors the recent trajectory."
                or "Trend commentary unavailable from excerpts."
            )
            sections["three_year_trend"] = {
                "trend_summary": trend_summary,
                "inflections": [
                    margin_info["current"]
                    and f"Net margin currently at {margin_info['current']} per standardized data."
                    or "No clear inflection points identified from provided text."
                ],
                "compare_prior_period": {
                    "available": bool(revenue_info["prior"] or income_info["prior"]),
                    "insights": [
                        revenue_info["prior"]
                        and f"Prior revenue reference point: {revenue_info['prior']}"
                        or "Prior-period disclosures were not captured.",
                    ],
                },
                "source_section_ref": "Trend discussion (not surfaced in sampled excerpts)",
            }

    def _parse_and_clean_text(
        self,
        filing_text: str,
        filing_type_key: str,
        filing_excerpt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Helper method to run heavy parsing in a separate thread.
        This isolates CPU-intensive BeautifulSoup and regex operations from the main event loop.
        """
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(filing_text, 'html.parser')
            # Extract text
            filing_text_clean = soup.get_text(separator='\n', strip=False)
            
            # Explicitly clear the soup tree to free memory immediately
            # This is critical for 10-K filings which can parse into very large trees
            soup.decompose()  # Destroys the tree
            del soup
        except Exception:
            # Fallback if parsing fails
            filing_text_clean = filing_text

        # Use the provided excerpt or extract critical sections (regex intensive)
        # PASS cleaned_text to avoid double parsing!
        filing_sample = filing_excerpt or self.extract_critical_sections(
            filing_text, 
            filing_type_key, 
            cleaned_text=filing_text_clean
        )
        
        if not filing_sample:
            # Fallback to first 15k chars if extraction fails
            filing_sample = filing_text[:15000]
            
        # Extract financial data (regex/search intensive)
        financial_data = self.extract_financial_data(filing_sample[:25000])  # slightly larger window
        
        return {
            "filing_sample": filing_sample,
            "financial_data": financial_data,
            # We don't return filing_text_clean as it's not used in the downstream flow 
            # (or if it is, we should return it too, but looking at previous code it wasn't used)
        }

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
        from fastapi.concurrency import run_in_threadpool

        filing_type_key = (filing_type or "10-K").upper()
        
        # Offload heavy parsing/regex to thread pool to prevent blocking the event loop
        # This addresses the stall issue during summary generation
        parsing_result = await run_in_threadpool(
            self._parse_and_clean_text,
            filing_text,
            filing_type_key,
            filing_excerpt
        )
        
        filing_sample = parsing_result["filing_sample"]
        financial_data = parsing_result["financial_data"]
        
        # Explicit clean up
        del parsing_result

        config = self._get_type_config(filing_type_key)
        prompt_template = get_prompt(filing_type_key)

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
            "10-Q": [
                "- Highlight sequential and year-on-year momentum for this quarter.",
                "- Connect quarterly execution to full-year guidance and structural themes.",
                "- Call out liquidity, leverage, and any covenant or contingency disclosures that are material to near-term risk."
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
      "tone": "<positive|neutral|cautious>",
      "source_section_ref": "<e.g., 'Cover page' or 'Item 2. MD&A'>"
    },
    "financial_highlights": {
      "table": [
        {
          "metric": "<non-empty string>",
          "current_period": "<non-empty string>",
          "prior_period": "<non-empty string>",
          "change": "<non-empty string>",
          "commentary": "<non-empty string>"
        }
      ],
      "profitability": ["<non-empty bullet>"],
      "cash_flow": ["<non-empty bullet>"],
      "balance_sheet": ["<non-empty bullet>"],
      "source_section_ref": "<e.g., 'Item 1. Financial Statements'>"
    },
    "risk_factors": [
      {
        "summary": "<non-empty string>",
        "supporting_evidence": "<non-empty excerpt or citation>",
        "materiality": "<low|medium|high>",
        "source_section_ref": "<e.g., 'Item 1A. Risk Factors'>"
      }
    ],
    "management_discussion_insights": {
      "themes": ["<non-empty bullet>"],
      "quotes": [
        {
          "speaker": "<non-empty string>",
          "quote": "<non-empty string>",
          "context": "<non-empty string>"
        }
      ],
      "capital_allocation": ["<non-empty bullet>"],
      "source_section_ref": "<e.g., 'Item 2. MD&A'>"
    },
    "segment_performance": [
      {
        "segment": "<non-empty string>",
        "revenue": "<non-empty string>",
        "change": "<non-empty string>",
        "commentary": "<non-empty string>",
        "source_section_ref": "<e.g., 'Note 13 – Segment Information'>"
      }
    ],
    "liquidity_capital_structure": {
      "leverage": "<non-empty string>",
      "liquidity": "<non-empty string>",
      "shareholder_returns": ["<non-empty bullet>"],
      "source_section_ref": "<e.g., 'Liquidity and Capital Resources'>"
    },
    "covenants_contingencies": {
      "debt_covenants": ["<non-empty bullet>"],
      "contingent_liabilities": ["<non-empty bullet>"],
      "source_section_ref": "<e.g., 'Commitments and Contingencies'>"
    },
    "guidance_outlook": {
      "guidance": "<non-empty string>",
      "tone": "<positive|neutral|cautious>",
      "drivers": ["<non-empty bullet>"],
      "watch_items": ["<non-empty bullet>"],
      "source_section_ref": "<e.g., 'Outlook' or 'Guidance'>"
    },
    "notable_footnotes": [
      {
        "item": "<non-empty string>",
        "impact": "<non-empty string>",
        "source_section_ref": "<relevant note reference where possible>"
      }
    ],
    "three_year_trend": {
      "trend_summary": "<non-empty string>",
      "inflections": ["<non-empty bullet>"],
      "compare_prior_period": {
        "available": <bool>,
        "insights": ["<non-empty bullet>"]
      },
      "source_section_ref": "<e.g., 'Selected Financial Data' or MD&A trend discussion>"
    }
  }
}"""

        output_reference = ""
        if prompt_template.user:
            output_reference = (
                "\n\nOUTPUT REFERENCE (use for content coverage; respond in JSON schema below):\n"
                f"{prompt_template.user}\n"
            )

        prompt = f"""{prompt_template.system}

You are a forensic financial analyst preparing structured briefing materials for newsroom editors.

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
{output_reference}

Return ONLY valid JSON (no markdown fences) that matches this schema (replace placeholders with actual values or meaningful nulls). Every string must contain substantive content—never emit blank strings or placeholder tokens. Arrays must never be empty; if no verifiable bullet exists, supply a single-element array with "Not disclosed—<concise reason>":
{schema_template}

Rules:
- Keep monetary values human-readable (e.g., "$17.7B", "$425M", "$912M").
- Express percentage changes with one decimal place where available (e.g., "up 8.3% YoY").
- For arrays, include 1-4 high-signal, evidence-backed bullets ordered by materiality. If nothing qualifies, return ["Not disclosed—<concise reason>"] instead of leaving the array empty.
- Empty sections are unacceptable. Do not fabricate data; explain the absence using the Not disclosed pattern when required.
- Provide supporting evidence excerpts for each risk factor (direct quote or XBRL tag reference), and when possible populate `source_section_ref` with the most relevant 10-Q section (for example: "Item 1A. Risk Factors", "Item 2. MD&A")."""

        import asyncio
        models_to_try = [self.get_model_for_filing(filing_type_key)] + self._fallback_models
        models_to_try = list(dict.fromkeys(models_to_try))

        response = None
        last_error: Optional[Exception] = None
        max_retries = 1  # Reduced from 3 to limit worst-case latency
        base_timeout = config.get("ai_timeout", 45.0)  # Reduced from 90s
        
        for model_name in models_to_try:
            # Try each model with limited retries (no exponential backoff)
            for attempt in range(max_retries):
                try:
                    # Fixed timeout (no exponential scaling) for predictable latency
                    timeout = base_timeout
                    response = await asyncio.wait_for(
                        self.client.chat.completions.create(
                            model=model_name,
                            messages=[
                                {
                                    "role": "system",
                                    "content": (
                                        "You are a structured data extraction engine for financial journalism. "
                                        "You never write narrative prose. You output STRICT RFC8259 COMPLIANT JSON. "
                                        "ALL keys and strings must use DOUBLE QUOTES. No trailing commas. "
                                        "Adhere strictly to the requested schema. "
                                        "Fill in 'Not disclosed' when data is missing. "
                                        "Never invent prior-period figures."
                                    ),
                                },
                                {"role": "user", "content": prompt},
                            ],
                            temperature=0.2,
                            max_tokens=config.get("max_tokens", 1500),
                        ),
                        timeout=timeout,
                    )
                    # Success - break out of retry loop
                    break
                except asyncio.TimeoutError as timeout_error:
                    last_error = timeout_error
                    logger.warning(f"AI request timed out after {timeout:.1f}s for {model_name}")
                    # No retry delay - move to next model immediately
                    break
                except Exception as model_error:
                    error_msg = str(model_error)
                    last_error = model_error
                    if any(keyword in error_msg.lower() for keyword in ("rate limit", "429", "model", "unavailable")):
                        logger.warning(f"Structured extraction model {model_name} failed ({error_msg[:120]}). Trying next model...")
                        break
                    raise
            
            # Validate response content before breaking
            if response is not None:
                # Safety check for malformed API response (missing choices)
                if not getattr(response, 'choices', None) or not response.choices:
                    logger.warning(f"Model {model_name} returned malformed response (no choices). Treating as failure and trying next model...")
                    last_error = ValueError("Malformed AI response: no choices returned")
                    continue
                content = response.choices[0].message.content
                # Check for empty content (blocked/filtered) or just whitespace
                if not content or not content.strip():
                    logger.warning(f"Model {model_name} returned empty payload. Treating as failure and trying next model...")
                    last_error = ValueError("Empty payload received from AI model")
                    continue
                
                # Valid response received
                break

        if response is None:
            raise last_error if last_error else RuntimeError("All extraction models failed.")

        content = response.choices[0].message.content
        payload = self._clean_json_payload(content or "")

        if not payload:
            raise ValueError("Extraction model returned empty payload.")

        # Always run repair first - json-repair library handles ALL edge cases
        # including unterminated strings, missing brackets, unescaped chars
        try:
            # First try direct parsing (fast path for valid JSON)
            summary_data = json.loads(payload)
        except json.JSONDecodeError as initial_error:
            # Apply robust repair using json-repair library
            logger.warning(f"JSON decode failed, attempting repair: {initial_error}")
            try:
                repaired_payload = self._repair_json(payload)
                summary_data = json.loads(repaired_payload)
                logger.info("JSON repair successful using json-repair library")
            except json.JSONDecodeError as repair_error:
                # Log details for debugging
                logger.error(f"JSON repair failed: {repair_error}")
                logger.error(f"Original error: {initial_error}")
                logger.error(f"Raw payload (first 500 chars): {payload[:500]}")
                # Re-raise with original error for clearer debugging
                raise initial_error

        sections_info = summary_data.get("sections") or {}
        missing_sections = self._find_empty_sections(sections_info)
        if missing_sections:
            detailed_sections = self.extract_sections(filing_text, filing_type_key)
            recovered = await self._recover_missing_sections(
                missing_sections,
                filing_type_key,
                detailed_sections,
                filing_sample,
                summary_data.get("metadata", {}),
            )
            if recovered:
                sections_info.update(recovered)

        self._apply_structured_fallbacks(
            sections_info,
            summary_data.get("metadata", {}),
            xbrl_metrics,
        )
        summary_data["sections"] = sections_info

        return summary_data

    async def generate_editorial_markdown(self, structured_summary: Dict[str, Any]) -> Dict[str, Any]:
        """Phase 2: Convert structured schema into polished newsroom-ready markdown."""
        import asyncio

        if not structured_summary:
            raise ValueError("Structured summary payload is empty.")

        metadata = structured_summary.get("metadata", {})
        company_name = metadata.get("company_name", "The company")
        filing_type = metadata.get("filing_type", "filing")
        filing_type_key = (str(filing_type) or "").upper()
        reporting_period = metadata.get("reporting_period", "the reported period")

        structured_payload = json.dumps(structured_summary, indent=2, ensure_ascii=False)

        if filing_type_key == "10-Q":
            # 10-Q: concise 1-page, bullet-led investor summary
            writer_prompt = f"""You are a senior financial journalist writing for a mixed audience of serious retail investors and professional investors.

Write a concise, 1-page summary of this Form 10-Q based on the structured financial data provided below.

Structured data (JSON):
{structured_payload}

Style:
- Bullet-first and highly scannable; avoid long paragraphs.
- Focus on what changed this quarter and why it matters to investors.
- Tie every number you cite directly to the structured data; never introduce new figures.
- Use very short sentences and limit jargon.
- Length: 120–260 words total across all sections.

Output Markdown using ONLY the following second-level headings (in this order), each followed by 3–6 high-signal bullets:
## Quarter at a Glance
## Key Numbers
## Guidance & Outlook
## Key Risks
## Liquidity & Balance Sheet
## Operational Highlights

Guidance for sections:
- Quarter at a Glance: 3–4 bullets summarizing the overall narrative for the quarter.
- Key Numbers: revenue, EPS, margins, cash flow and any key segment/KPI metrics, always with direction vs prior period when available.
- Guidance & Outlook: changes to guidance, tone, and the main drivers; if no guidance, say it was not disclosed.
- Key Risks: 3–7 bullets summarizing the most material risks or watchpoints, referencing the risk_factors data.
- Liquidity & Balance Sheet: cash, debt, leverage, liquidity and covenants/contingencies where disclosed.
- Operational Highlights: segment performance, product/geography highlights, or execution themes; omit bullets if there is no real data.

Rules:
- Use ONLY information available in the structured JSON; do not invent metrics, dates, guidance, or qualitative claims.
- Every numeric value you mention must come from the structured data.
- If data is missing, say it was not disclosed instead of guessing.
- Use currency suffixes (e.g., "$17.7B", "$482M") and percentage formatting (e.g., "29%") when citing numbers.
- Keep tone neutral-to-confident and investor-focused.
- Return Markdown only — no JSON, code fences, or additional commentary."""
        else:
            # Default writer for other filing types
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
- Return Markdown only — no JSON, code fences, or additional commentary."""

        system_message = (
            "You are an award-winning financial journalist for a Tier 1 financial publication. "
            "Write with authority, clarity, and precision. Style references: Bloomberg, The Economist, Financial Times. "
            "You deliver narrative cohesion, emphasize materiality, and integrate numbers seamlessly."
        )

        response = None
        last_error: Optional[Exception] = None
        validation_error: Optional[Exception] = None
        max_retries = 2

        # Use Pro model for editorial writing (creative but constrained)
        writer_model = self.get_model_for_task("editorial_writer", filing_type_key)
        writer_models = [writer_model] + [m for m in self._writer_models if m != writer_model]

        for attempt in range(max_retries):
            for model_name in writer_models:
                try:
                    # Enhance prompt on retry with more explicit instructions
                    enhanced_prompt = writer_prompt
                    if attempt > 0:
                        if filing_type_key == "10-Q":
                            enhanced_prompt += (
                                "\n\nIMPORTANT: Previous attempt failed validation. Ensure you include ALL required "
                                "sections with the correct headings and keep total length within 120–260 words. "
                                "Each bullet must be grounded in the structured data; do not introduce new figures."
                            )
                        else:
                            enhanced_prompt += (
                                "\n\nIMPORTANT: Previous attempt failed validation. Ensure you include ALL required "
                                "sections: Executive Summary, Financials, Risks, Management Commentary, Outlook. "
                                "Each section must have substantive content (not just 'Not disclosed'). Total word "
                                "count must be 200-300 words."
                            )
                        if validation_error:
                            enhanced_prompt += f"\n\nPrevious error: {str(validation_error)[:200]}"
                    
                    response = await asyncio.wait_for(
                        self.client.chat.completions.create(
                            model=model_name,
                            messages=[
                                {"role": "system", "content": system_message},
                                {"role": "user", "content": enhanced_prompt},
                            ],
                            temperature=0.4 if attempt == 0 else 0.3,  # Lower temperature on retry for more consistent output
                            max_tokens=900,
                        ),
                        timeout=18.0,
                    )
                    
                    content = response.choices[0].message.content or ""
                    markdown = content.strip()
                    model_used = response.model if hasattr(response, "model") else None
                    
                    # Validate the output
                    try:
                        # First validate structure/length/sections, then validate numeric consistency
                        self._validate_editorial_markdown(markdown, filing_type=filing_type)
                        self._validate_editorial_numbers(markdown, structured_summary)
                        word_count = len(markdown.split())
                        return {
                            "markdown": markdown,
                            "word_count": word_count,
                            "model_used": model_used,
                        }
                    except Exception as ve:
                        validation_error = ve
                        logger.warning(
                            f"Writer validation failed (attempt {attempt + 1}/{max_retries}): {str(ve)[:200]}"
                        )
                        if attempt < max_retries - 1:
                            # Try again with next model or retry
                            continue
                        # Last attempt failed, will fall back below
                        break
                        
                except Exception as model_error:
                    error_msg = str(model_error)
                    last_error = model_error
                    if any(keyword in error_msg.lower() for keyword in ("rate limit", "429", "model", "unavailable")):
                        logger.warning(f"Writer model {model_name} failed ({error_msg[:120]}). Trying next model...")
                        continue
                    raise
            
            # If we got here and have a response but validation failed, break retry loop
            if response and validation_error:
                break
        
        # Fall back to structured markdown if all attempts failed
        if validation_error or response is None:
            fallback_reason = str(validation_error) if validation_error else (str(last_error) if last_error else "All writer models failed")
            logger.warning(f"Writer generation failed after {max_retries} attempts. Using structured fallback. Reason: {fallback_reason[:200]}")
            fallback_markdown = self._build_structured_markdown(structured_summary, fallback_reason)
            word_count = len(fallback_markdown.split())
            model_used = response.model if response and hasattr(response, "model") else None
            return {
                "markdown": fallback_markdown,
                "word_count": word_count,
                "model_used": model_used,
                "fallback_used": True,
                "fallback_reason": fallback_reason,
            }
        
        # Should not reach here, but handle gracefully
        raise RuntimeError("Unexpected error in writer generation")

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
        from fastapi.concurrency import run_in_threadpool
        
        filing_type_key = (filing_type or "10-K").upper()
        config = self._get_type_config(filing_type_key)
        prompt_template = get_prompt(filing_type_key)

        # Offload heavy parsing/regex to thread pool
        parsing_result = await run_in_threadpool(
            self._parse_and_clean_text,
            filing_text,
            filing_type_key,
            filing_excerpt
        )
        
        filing_sample = parsing_result["filing_sample"]
        financial_data = parsing_result["financial_data"]
        
        # Explicit clean up
        del parsing_result

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
        
        output_reference = ""
        if prompt_template.user:
            output_reference = (
                "\n\nOUTPUT REFERENCE (use to shape the markdown in the JSON response):\n"
                f"{prompt_template.user}\n"
            )

        prompt = f"""{prompt_template.system}

You are a top-tier financial advisor and public market investor with over 30 years of experience analyzing companies at the highest level. You've advised institutional investors, managed billions in assets, and have a track record of identifying winners and avoiding losers. Your analysis is trusted by the most sophisticated investors in the market.

Your task: Analyze {company_name}'s {filing_type} filing and provide key takeaways from a professional investor's perspective. Think like a portfolio manager making a multimillion-dollar investment decision.

IMPORTANT: The text below contains ONLY the most critical sections extracted from the filing:
- For 10-K: Item 1A (Risk Factors) and Item 7 (Management's Discussion and Analysis)
- For 10-Q: Item 1A (Risk Factors) and Item 2 (Management's Discussion and Analysis)

This focused extraction allows for faster, more targeted analysis while maintaining the essential information needed for investment decisions.

{data_summary}

CRITICAL SECTIONS FROM FILING:
{filing_sample}
{previous_filings_context}
{output_reference}

ANALYSIS FRAMEWORK:
{analysis_focus_block}
1. Use the EXTRACTED FINANCIAL DATA above - cite specific numbers, percentages, and dollar amounts
2. Focus on what matters to professional investors: cash flow, margins, debt, competitive position, management quality
3. Identify the KEY investment thesis drivers - what makes this company investable or problematic?
4. Be direct and decisive - no hedging or generic statements
5. Highlight what institutional investors would focus on: execution quality, market position, financial health, strategic clarity
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
            system_prompt = "\n\n".join(
                part
                for part in [
                    prompt_template.system,
                    "Always return valid JSON with the exact structure requested. Use specific financial data provided and support all analysis with actual numbers. Be direct, decisive, and investment-focused.",
                ]
                if part
            )
            # Try models in order, starting with primary model, then fallbacks
            models_to_try = [self.get_model_for_filing(filing_type_key)] + self._fallback_models
            models_to_try = list(dict.fromkeys(models_to_try))
            
            for model_name in models_to_try:
                try:
                    stream = await self.client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": system_prompt},
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
                "status": "error",
                "message": f"Unable to complete summary due to parsing timeout. Suggest retrying later.",
                "summary_title": f"{company_name} {filing_type_key} Filing Summary",
                "sections": [],
                "insights": {
                    "sentiment": "Neutral",
                    "growth_drivers": [],
                    "risk_signals": []
                },
                # Legacy fields
                "business_overview": "Unable to complete summary due to parsing timeout. Suggest retrying later.",
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
                "status": "error",
                "message": f"DEBUG_ERROR: {str(extraction_error)}",
                "summary_title": f"{company_name} {filing_type_key} Filing Summary",
                "sections": [],
                "insights": {
                    "sentiment": "Neutral",
                    "growth_drivers": [],
                    "risk_signals": []
                },
                # Legacy fields
                "business_overview": "Unable to retrieve this filing at the moment — please try again shortly.",
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

        coverage_keys = set(_TRACKED_STRUCTURED_SECTIONS)
        coverage_keys.update(sections_info.keys())
        coverage_map = {
            section: _section_has_content(sections_info.get(section))
            for section in sorted(coverage_keys)
        }
        total_sections = len(coverage_map)
        covered_sections = sum(1 for covered in coverage_map.values() if covered)
        missing_sections = [key for key, covered in coverage_map.items() if not covered]
        coverage_snapshot = {
            "per_section": coverage_map,
            "covered": [key for key, covered in coverage_map.items() if covered],
            "missing": missing_sections,
            "covered_count": covered_sections,
            "total_count": total_sections,
            "coverage_ratio": (covered_sections / total_sections) if total_sections else None,
        }

        logger.info(
            "Structured coverage for %s %s: %s/%s sections populated. Missing: %s",
            company_name,
            filing_type_key,
            covered_sections,
            total_sections,
            ", ".join(missing_sections) if missing_sections else "None",
        )

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
            # Generate fallback markdown from structured data
            final_markdown = self._build_structured_markdown(structured_summary, f"Writer failed: {writer_error[:100]}")

        raw_summary_payload = {
            "structured": structured_summary,
            "sections": sections_info,
            "section_coverage": coverage_snapshot,
        }
        if writer_result:
            raw_summary_payload["writer"] = writer_result
        if writer_fallback_reason:
            raw_summary_payload["writer_fallback_reason"] = writer_fallback_reason
        if writer_error:
            raw_summary_payload["writer_error"] = writer_error[:500]

        # Build new format response
        metadata = structured_summary.get("metadata", {})
        company_name = metadata.get("company_name", company_name)
        filing_type_label = metadata.get("filing_type", filing_type_key)
        reporting_period = metadata.get("reporting_period", "")
        filing_date = metadata.get("filing_date", "")
        
        # Generate summary title
        period_suffix = f" ({reporting_period})" if reporting_period else ""
        if filing_date:
            try:
                from datetime import datetime
                date_obj = datetime.fromisoformat(filing_date.replace("Z", "+00:00"))
                year = date_obj.year
                if filing_type_key == "10-K":
                    period_suffix = f" (FY{year})"
                elif filing_type_key == "10-Q":
                    quarter = (date_obj.month - 1) // 3 + 1
                    period_suffix = f" (Q{quarter} {year})"
            except (ValueError, TypeError):
                pass
        summary_title = f"{company_name} {filing_type_label} Filing Summary{period_suffix}"
        
        # Build sections array
        sections = []
        
        # Key Risks section
        if risk_section:
            risk_content_parts = []
            for risk in risk_section[:10]:  # Limit to top 10 risks
                if isinstance(risk, dict):
                    summary = risk.get("summary", "")
                    evidence = risk.get("supporting_evidence", "")
                    if summary:
                        bullet = f"• {summary}"
                        if evidence:
                            bullet += f" (Evidence: {evidence[:200]})"
                        risk_content_parts.append(bullet)
            if risk_content_parts:
                sections.append({
                    "title": "Key Risks",
                    "content": "\n".join(risk_content_parts)
                })
        
        # Financial Overview section
        if financial_section:
            financial_content_parts = []
            table = financial_section.get("table", [])
            if table:
                for row in table[:10]:  # Limit to top 10 metrics
                    if isinstance(row, dict):
                        metric = row.get("metric", "")
                        current = row.get("current_period", "")
                        prior = row.get("prior_period", "")
                        change = row.get("change", "")
                        commentary = row.get("commentary", "")
                        if metric:
                            line = f"• {metric}: {current}"
                            if prior and prior != "Not disclosed":
                                line += f" (vs. {prior})"
                            if change and change != "Not disclosed":
                                line += f" — {change}"
                            if commentary:
                                line += f" — {commentary[:150]}"
                            financial_content_parts.append(line)
            if financial_content_parts:
                sections.append({
                    "title": "Financial Overview",
                    "content": "\n".join(financial_content_parts)
                })
        
        # Management Commentary section
        if management_section:
            sections.append({
                "title": "Management Commentary",
                "content": management_section[:2000]  # Limit length
            })
        
        # Strategic Developments section (from guidance and management discussion)
        strategic_parts = []
        if guidance_section:
            strategic_parts.append(guidance_section[:1000])
        guidance_structured = sections_info.get("guidance_outlook", {})
        if isinstance(guidance_structured, dict):
            guidance_text = guidance_structured.get("guidance", "")
            drivers = guidance_structured.get("drivers", [])
            if guidance_text and guidance_text != "Not disclosed":
                strategic_parts.append(f"Forward Guidance: {guidance_text}")
            if drivers:
                strategic_parts.append("Key Drivers: " + "; ".join(str(d) for d in drivers[:5]))
        if strategic_parts:
            sections.append({
                "title": "Strategic Developments",
                "content": "\n".join(strategic_parts)
            })
        
        # Build insights object
        insights = {
            "sentiment": "Neutral",
            "growth_drivers": [],
            "risk_signals": []
        }
        
        # Extract sentiment from executive snapshot
        exec_snapshot = sections_info.get("executive_snapshot", {})
        if isinstance(exec_snapshot, dict):
            tone = exec_snapshot.get("tone", "neutral")
            if tone:
                # Format sentiment based on tone (e.g., "positive" -> "Positive", "neutral" -> "Neutral", "cautious" -> "Cautious")
                # Support compound sentiments like "neutral to positive"
                if isinstance(tone, str):
                    if " to " in tone.lower():
                        # Already a compound sentiment
                        insights["sentiment"] = tone.title()
                    else:
                        insights["sentiment"] = tone.capitalize()
                else:
                    insights["sentiment"] = "Neutral"
        
        # Enhance sentiment with guidance tone if available
        if guidance_structured and isinstance(guidance_structured, dict):
            guidance_tone = guidance_structured.get("tone", "")
            if guidance_tone and guidance_tone != insights["sentiment"].lower():
                # Combine sentiment if different (e.g., "Neutral to Positive")
                current_sentiment = insights["sentiment"].lower()
                if current_sentiment != guidance_tone:
                    insights["sentiment"] = f"{insights['sentiment']} to {guidance_tone.capitalize()}"
        
        # Extract growth drivers from guidance and management discussion
        if guidance_structured and isinstance(guidance_structured, dict):
            drivers = guidance_structured.get("drivers", [])
            if drivers:
                insights["growth_drivers"] = [str(d) for d in drivers[:5]]
        
        # Extract risk signals from risk factors
        if risk_section:
            insights["risk_signals"] = [
                risk.get("summary", "")[:100] 
                for risk in risk_section[:5] 
                if isinstance(risk, dict) and risk.get("summary")
            ]
        
        # Determine status and message
        # Step 6: Graceful Failure Handling
        status = "complete"
        message = None
        coverage_ratio = coverage_snapshot.get("coverage_ratio", 1.0)
        missing_sections_list = coverage_snapshot.get("missing", [])
        
        # If coverage is low or writer had issues, mark as partial
        if coverage_ratio < 0.5 or writer_error or writer_fallback_reason:
            status = "partial"
            message = "Some sections may not have loaded fully."
            if missing_sections_list:
                message += f" Missing sections: {', '.join(missing_sections_list[:3])}"
        
        # If we have no sections at all, it's an error
        if not sections:
            status = "error"
            message = "Unable to retrieve this filing at the moment — please try again shortly."
        
        # If processing stopped mid-way but we have some sections, mark as partial
        if len(sections) > 0 and coverage_ratio < 0.7:
            status = "partial"
            if not message:
                message = "Some sections may not have loaded fully."
        
        # Build response
        response = {
            "summary_title": summary_title,
            "sections": sections,
            "insights": insights,
            "status": status,
            # Keep legacy fields for backward compatibility
            "business_overview": final_markdown,
            "financial_highlights": financial_section,
            "risk_factors": risk_section,
            "management_discussion": management_section,
            "key_changes": guidance_section,
            "raw_summary": raw_summary_payload,
        }
        
        # Add message if status is error or partial
        if message:
            response["message"] = message
        
        return response

openai_service = OpenAIService()

