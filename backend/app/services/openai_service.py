from __future__ import annotations

import asyncio
import logging
from openai import AsyncOpenAI
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple
from app.config import settings
from app.services.prompt_loader import get_prompt, get_structured_prompt
import json
import re
from bs4 import BeautifulSoup

# Cohesive helpers/mixins extracted from this module (roadmap S2 façade split). Imported here so
# ``app.services.openai_service`` stays the single import surface for every existing caller; the
# re-exported public names are pinned in ``__all__`` at the bottom of this module.
from app.services.ai.bank_guards import _is_no_total_bank, _sanitize_bank_financial_highlights
from app.services.ai.model_flags import _thinking_disabled_model
from app.services.ai.normalize import (
    _normalize_risk_factors,
    _section_has_content,
    # Transitional: still referenced by _section_is_empty, which moves to the section-recovery
    # mixin in a later S2 step — this import goes with it at that point.
    _normalize_simple_string,
)
from app.services.ai.xbrl_narrative import (
    build_xbrl_narrative_section,
    _XBRL_NARRATIVE_SPEC,
    _format_xbrl_metric_value,
)
# Method-group mixins composed into OpenAIService (below). Each holds a cohesive slice of the
# service's methods; they resolve through ``self`` exactly as before the split.
from app.services.ai.json_repair import _JsonRepairMixin
from app.services.ai.markdown_render import _MarkdownRenderMixin

logger = logging.getLogger(__name__)


# Distinct failure signal for the transport-agnostic streaming wrappers (``stream_chat`` /
# ``stream_chat_with_tools``). On an upstream/model error they yield a single chunk prefixed with
# this sentinel instead of raising, so the SSE contract stays intact. The null-byte delimiters can
# never appear in normal model output, so a consumer can unambiguously distinguish a real failure
# from answer prose (a plain ``[Error: ...]`` string is indistinguishable from a model that happens
# to quote one, and would otherwise be streamed to the user as the answer body).
STREAM_ERROR_SENTINEL = "\x00\x00__OPENAI_STREAM_ERROR__\x00\x00"

# Tool-activity signal for ``stream_chat_with_tools``. Before and after running each tool call the
# wrapper yields a single chunk prefixed with this sentinel whose remainder is a JSON object
# ``{"name","args","phase":"start"|"done","ok"?}``. A consumer can surface a live "show the work"
# ticker ("Looking up revenue… ✓") while keeping the wrapper provider-generic — it emits the raw
# tool name/args and leaves human labelling to the caller. Null-byte delimiters can't appear in
# model output, so this is unambiguous vs. answer prose.
STREAM_ACTIVITY_SENTINEL = "\x00\x00__OPENAI_STREAM_ACTIVITY__\x00\x00"

# Hold back this many chars of a tool round's prose before deciding it is a real answer —
# inter-tool narration is short ("Let me compute the margins…"); real answers blow past it.
_TOOL_ROUND_HOLDBACK_CHARS = 240

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


class OpenAIService(_JsonRepairMixin, _MarkdownRenderMixin):
    def __init__(self):
        # Use Google AI Studio base URL if configured
        base_url = settings.OPENAI_BASE_URL if hasattr(settings, 'OPENAI_BASE_URL') else None
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=base_url
        )
        # Model name constants for maintainability
        # Primary model sourced from settings for single source of truth
        self._MODEL_GEMINI_3_PRO = settings.AI_DEFAULT_MODEL  # From config.py
        self._MODEL_GEMINI_2_5_PRO = "gemini-2.5-pro"
        self._MODEL_GEMINI_2_5_FLASH = "gemini-2.5-flash"

        # Google AI Studio model names
        # Updated to use Gemini Pro 3.0 for highest quality outputs
        self.model = self._MODEL_GEMINI_3_PRO  # Sourced from settings.AI_DEFAULT_MODEL
        # Fallback models in case primary is rate-limited
        self._fallback_models = [
            self._MODEL_GEMINI_3_PRO,
            self._MODEL_GEMINI_2_5_PRO,
            self._MODEL_GEMINI_2_5_FLASH
        ]
        # Set optimized models for each filing type - all use Gemini Pro 3.0
        self._model_overrides = {
            "10-K": self._MODEL_GEMINI_3_PRO,  # Gemini Pro 3.0 for 10-K
            "10-Q": self._MODEL_GEMINI_3_PRO,  # Gemini Pro 3.0 for 10-Q
        }
        # Task-specific model selection - all use Gemini 3 Pro for maximum quality
        # Per-task model routing. Extraction and editorial stay on the Pro model (quality bar).
        # Section recovery may opt into a cheaper model (A11) — defaults to Pro until an operator
        # sets AI_SECTION_RECOVERY_MODEL or AI_FAST_MODEL, so behavior is unchanged out of the box.
        _section_recovery_model = (
            settings.AI_SECTION_RECOVERY_MODEL.strip()
            or settings.AI_FAST_MODEL.strip()
            or self._MODEL_GEMINI_3_PRO
        )
        self._task_models = {
            "structured_extraction": self._MODEL_GEMINI_3_PRO,   # Needs high accuracy
            "section_recovery": _section_recovery_model,         # Cheaper-model candidate (A11)
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
        - section_recovery: Fill missing sections (simpler; opt-in cheaper model via config — A11)

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
            "max_tokens": 8000,  # Large enough for the full multi-section JSON schema (avoids truncation)
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
                "max_tokens": 12000,  # 10-K schema is largest; prevents mid-JSON truncation
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
                "max_tokens": 8000,  # Prevents mid-JSON truncation on the multi-section schema
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
            },
            # 20-F annual reports are as large and detailed as a 10-K — give them the same
            # generous budget so financials/MD&A/risk aren't truncated before reaching the model.
            "20-F": {
                "ai_timeout": 150.0,
                "max_tokens": 12000,
                "sample_length": 100000,
                "section_limits": {
                    "financials": 50000,
                    "mda": 40000,
                    "risk_factors": 30000,
                    "business": 25000,
                    "liquidity": 25000,
                    "segments": 20000,
                    "guidance": 15000,
                    "footnotes": 20000
                }
            },
            # A 6-K (FPI interim furnished report) is a short earnings release / notice, not a full
            # report — a modest budget and faster timeout avoid over-spending on small filings. Its
            # grounding text is supplied as a pre-extracted exhibit excerpt (no section sampling).
            "6-K": {
                "ai_timeout": 90.0,
                "max_tokens": 5000,
                "sample_length": 60000,
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
    
    @staticmethod
    def _looks_like_toc(text: str) -> bool:
        """Heuristic: does this captured span look like a table-of-contents entry rather than
        real section content? TOC spans are short and/or dense with dotted leaders
        ("Item 8 ....... 45"). Used to reject TOC slivers during section extraction (roadmap S2)."""
        sample = text[:2000].lower()
        if "table of contents" in sample:
            return True
        leaders = len(re.findall(r"\.{4,}", text[:5000]))
        if leaders >= 5 and len(text) < 3000:
            return True
        return False

    @classmethod
    def _accept_section(cls, text: str, min_chars: int) -> bool:
        """A captured section is real content only if it clears a length floor and isn't TOC-like.
        The 10-K extraction path previously had no such guard, so an Item-8 regex that hit the
        table of contents fed the model a sliver of real content (roadmap S2)."""
        return len(text) >= min_chars and not cls._looks_like_toc(text)

    @staticmethod
    def _dense_window(text: str, keywords: List[str], window: int = 130000, step: int = 20000) -> str:
        """Return the `window`-char slice of `text` densest in `keywords`, scanning the whole document.

        P1.2 robustness: targeted Item regex is fragile on 10-Qs and complex (e.g. bank) filings and
        can return a few-thousand-char sliver. Rather than feed the model that sliver, hand it the
        most relevant large slab of the actual document — the cheap, large-context model uses it.
        Returns "" only for empty input; the whole text when it is already within `window`."""
        if not text:
            return ""
        if len(text) <= window:
            return text
        # Lowercase once up front, not per overlapping chunk — on a multi-MB filing the sliding
        # window re-lowercases the same characters dozens of times otherwise.
        text_lower = text.lower()
        best_start, best_score = 0, -1
        last = len(text) - window
        i = 0
        while True:
            i = min(i, last)
            chunk = text_lower[i:i + window]
            score = sum(chunk.count(kw) for kw in keywords)
            if score > best_score:
                best_score, best_start = score, i
            if i >= last:
                break
            i += step
        return text[best_start:best_start + window]

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
                    # S2: reject TOC-like/short matches and try the next pattern instead of
                    # feeding the model a sliver captured from the table of contents.
                    if not self._accept_section(financial_text, 500):
                        logger.debug(f"10-K Item 8: skipping TOC-like/short match ({len(financial_text)} chars)")
                        continue
                    # Increased limit to 40000 chars to capture full financial statements
                    critical_sections.append(f"ITEM 8 - FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA:\n{financial_text[:70000]}")
                    logger.info(f"10-K Item 8 extraction: captured {len(financial_text):,} chars")
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
                    if not self._accept_section(mda_text, 500):
                        logger.debug(f"10-K Item 7: skipping TOC-like/short match ({len(mda_text)} chars)")
                        continue
                    # Increased limit to 35000 chars to capture full MD&A
                    critical_sections.append(f"ITEM 7 - MANAGEMENT'S DISCUSSION AND ANALYSIS:\n{mda_text[:55000]}")
                    logger.info(f"10-K Item 7 extraction: captured {len(mda_text):,} chars")
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
                    if not self._accept_section(risk_text, 200):
                        logger.debug(f"10-K Item 1A: skipping TOC-like/short match ({len(risk_text)} chars)")
                        continue
                    # Increased limit to 25000 chars for comprehensive risk coverage
                    critical_sections.append(f"ITEM 1A - RISK FACTORS:\n{risk_text[:45000]}")
                    logger.info(f"10-K Item 1A extraction: captured {len(risk_text):,} chars")
                    break

        elif filing_type_key == "10-Q":
            # PRIORITY 1: Extract Item 1 - Financial Statements (MOST CRITICAL for metrics)
            # This is where revenue, net income, EPS, and cash flow data lives!
            # CRITICAL FIX: Avoid matching Table of Contents entries
            # TOC entries have short text; actual sections have substantial content
            financial_patterns = [
                # Match Item 1 header with multiple spaces (actual section, not TOC)
                # PR FEEDBACK FIX: Require \s{2,} in all lookaheads to avoid matching TOC entries
                r"ITEM\s*1\.?\s{2,}(?:CONDENSED\s+)?(?:CONSOLIDATED\s+)?FINANCIAL\s+STATEMENTS[^\n]*\n([\s\S]*?)(?=\nITEM\s*2\.?\s{2,})",
                # PART I FINANCIAL INFORMATION header
                r"PART\s*I\s*[-–—]?\s*FINANCIAL\s+INFORMATION[^\n]*\n([\s\S]*?)(?=\nITEM\s*2\.?\s{2,})",
                # Direct financial statement headers (these appear in actual content, not TOC)
                r"CONDENSED\s+CONSOLIDATED\s+STATEMENTS\s+OF\s+OPERATIONS\s+\(Unaudited\)[^\n]*\n([\s\S]*?)(?=\nITEM\s*2\.\s{2,}|\nManagement['']?s\s+Discussion)",
                r"(?:CONDENSED\s+)?CONSOLIDATED\s+BALANCE\s+SHEETS?\s+\(Unaudited\)[^\n]*\n([\s\S]*?)(?=\nITEM\s*2\.\s{2,}|\nManagement['']?s\s+Discussion)",
                # Fallback: Any Financial Statements header with substantial content
                r"FINANCIAL\s+STATEMENTS[^\n]*\n([\s\S]{1000,}?)(?=\nITEM\s*2\.\s{2,}|\nManagement['']?s\s+Discussion|$)",
            ]
            for pattern in financial_patterns:
                match = re.search(pattern, filing_text_clean, re.IGNORECASE | re.DOTALL | re.MULTILINE)
                if match:
                    financial_text = match.group(1).strip()
                    # Verify this isn't a TOC entry (actual financial statements are long)
                    if len(financial_text) > 500:
                        # 35000 chars to capture full condensed financial statements + notes
                        critical_sections.append(f"ITEM 1 - FINANCIAL STATEMENTS:\n{financial_text[:50000]}")
                        logger.info(f"10-Q Financial Statements extraction: captured {len(financial_text):,} chars")
                        break
                    else:
                        logger.debug(f"10-Q Financial: skipping short match ({len(financial_text)} chars) - likely TOC entry")

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
                        critical_sections.append(f"FINANCIAL DATA:\n{financial_text[:50000]}")
                        break

            # PRIORITY 2: Extract Item 2 - MD&A (narrative context for financials)
            # CRITICAL FIX: Patterns must avoid matching Table of Contents entries
            # TOC format: "Item 2.\nManagement's Discussion...\n12" (with line breaks)
            # Actual format: "Item 2.    Management's Discussion..." (on same line, with spaces/tabs)
            # Use [^\n]+ after Item header to ensure we match actual section, not TOC
            mda_patterns = [
                # Primary: Match "Item 2.    Management's Discussion" with spaces (not newlines) between
                r"ITEM\s*2\.?\s{2,}MANAGEMENT['']?S?\s+DISCUSSION[^\n]*\n([\s\S]*?)(?=\nITEM\s*3\.?\s{2,}|\nITEM\s*4\.?\s{2,}|\nQUANTITATIVE|\nCONTROLS|\nPART\s*II|$)",
                # Secondary: Match with any whitespace but require substantial content after header
                # PR FEEDBACK FIX: Require \s{2,} after item numbers in lookaheads
                r"ITEM\s*2\.?[^\n]*MANAGEMENT['']?S?\s+DISCUSSION\s+AND\s+ANALYSIS[^\n]*\n([\s\S]{500,}?)(?=\nITEM\s*3\.\s{2,}|\nITEM\s*4\.\s{2,}|\nPART\s*II|$)",
                # Tertiary: Direct MD&A header (no Item number prefix)
                r"MANAGEMENT['']?S?\s+DISCUSSION\s+AND\s+ANALYSIS\s+OF\s+FINANCIAL\s+CONDITION[^\n]*\n([\s\S]{500,}?)(?=\nITEM\s*3\.\s{2,}|\nQUANTITATIVE|\nCONTROLS|\nPART\s*II|$)",
                # Fallback: More lenient but still require content
                r"ITEM\s*2\.[^\n]*DISCUSSION[^\n]*\n([\s\S]{500,}?)(?=\nITEM\s*[34]\.\s{2,}|\nPART\s*II|$)",
            ]
            for pattern in mda_patterns:
                match = re.search(pattern, filing_text_clean, re.IGNORECASE | re.MULTILINE)
                if match:
                    mda_text = match.group(1).strip()
                    # Verify this isn't a TOC entry (TOC entries are short, actual content is long)
                    if len(mda_text) > 200:
                        # Increased to 30000 chars for comprehensive MD&A coverage
                        critical_sections.append(f"ITEM 2 - MANAGEMENT'S DISCUSSION AND ANALYSIS:\n{mda_text[:45000]}")
                        logger.info(f"10-Q MD&A extraction: captured {len(mda_text):,} chars")
                        break
                    else:
                        logger.debug(f"10-Q MD&A: skipping short match ({len(mda_text)} chars) - likely TOC entry")

            # PRIORITY 3: Extract Item 1A - Risk Factors (if present - not always in 10-Q)
            # CRITICAL FIX: Avoid matching TOC entries (short text with page numbers)
            # In 10-Q, Risk Factors are often in PART II, not PART I
            risk_patterns = [
                # PART II Risk Factors (common in 10-Q)
                # PR FEEDBACK FIX: Require \s{2,} after item numbers in lookaheads
                r"PART\s*II[^\n]*\n[\s\S]*?ITEM\s*1A\.?\s{2,}RISK\s+FACTORS[^\n]*\n([\s\S]*?)(?=\nITEM\s*2\.\s{2,}|\nITEM\s*3\.\s{2,}|\nITEM\s*[456]\.\s{2,}|\nSIGNATURE|$)",
                # Standard Item 1A with spacing (actual section, not TOC)
                r"ITEM\s*1A\.?\s{2,}RISK\s+FACTORS[^\n]*\n([\s\S]{200,}?)(?=\nITEM\s*2\.\s{2,}|\nITEM\s*3\.\s{2,}|\nPART\s*II|$)",
                # Fallback with content length requirement
                r"ITEM\s*1A\.[^\n]*RISK\s+FACTORS[^\n]*\n([\s\S]{200,}?)(?=\nITEM\s*[23]\.\s{2,}|\nPART\s*II|$)",
                # Direct "Risk Factors" header with substantial content
                r"\nRISK\s+FACTORS\n([\s\S]{200,}?)(?=\nITEM\s*2\.\s{2,}|\nLEGAL|\nPART\s*II|\nSIGNATURE|$)",
            ]
            for pattern in risk_patterns:
                match = re.search(pattern, filing_text_clean, re.IGNORECASE | re.MULTILINE)
                if match:
                    risk_text = match.group(1).strip()
                    # Verify this isn't a TOC entry
                    if len(risk_text) > 100:
                        # 15000 chars for 10-Q risk factors (usually shorter than 10-K)
                        critical_sections.append(f"ITEM 1A - RISK FACTORS:\n{risk_text[:25000]}")
                        logger.info(f"10-Q Risk Factors extraction: captured {len(risk_text):,} chars")
                        break
                    else:
                        logger.debug(f"10-Q Risk Factors: skipping short match ({len(risk_text)} chars) - likely TOC entry")

        # P1.2: targeted regex extraction is high-precision when it lands, but fragile on 10-Qs and
        # complex (e.g. bank) filings where it can return a few-thousand-char sliver. When the
        # captured text is thin, augment it with large, keyword-anchored slices of the actual document
        # so the model sees the real Risk Factors and MD&A narrative. XBRL already supplies the
        # verified financials (P1.1), so this targets narrative depth.
        combined = ("\n\n" + "=" * 50 + "\n\n".join(critical_sections)) if critical_sections else ""
        RICH_MIN = 60000
        if len(combined) >= RICH_MIN:
            logger.info(
                f"{filing_type_key} extraction: {len(critical_sections)}/3 sections, "
                f"{len(combined):,} chars (targeted)"
            )
            return combined

        risk_kw = ["risk factors", "could adversely", "material adverse", "adversely affect",
                   "we may", "uncertaint", "regulatory", "litigation", "competition", "cybersecurity"]
        fin_kw = ["operating activities", "cash flow", "consolidated statements", "balance sheet",
                  "net income", "total revenue", "net sales", "gross", "operating income", "liquidity"]
        risk_slice = self._dense_window(filing_text_clean, risk_kw)
        fin_slice = self._dense_window(filing_text_clean, fin_kw)
        parts: List[str] = []
        if combined:
            parts.append(combined)
        if risk_slice:
            parts.append("RISK & NARRATIVE CONTEXT (recovered from filing):\n" + risk_slice)
        if fin_slice and fin_slice != risk_slice:
            parts.append("FINANCIAL & MD&A CONTEXT (recovered from filing):\n" + fin_slice)
        recovered = ("\n\n" + "=" * 50 + "\n\n").join(p for p in parts if p)
        logger.info(
            f"{filing_type_key} extraction: thin targeted ({len(combined):,} chars) — augmented "
            f"with recovered windows to {len(recovered):,} chars"
        )
        return recovered[:320000] or filing_text_clean[:120000]

    # Per-form display labels + length caps for sections parsed by edgartools
    # (xbrl_service.get_filing_sections). Mirrors the labels/caps the regex path emits so the
    # downstream prompt is byte-for-byte compatible regardless of which extractor produced it.
    _SECTION_LAYOUT = {
        "10-K": [
            ("financials", "ITEM 8 - FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA", 70000),
            ("mda", "ITEM 7 - MANAGEMENT'S DISCUSSION AND ANALYSIS", 55000),
            ("risk", "ITEM 1A - RISK FACTORS", 45000),
        ],
        "10-Q": [
            ("financials", "ITEM 1 - FINANCIAL STATEMENTS", 50000),
            ("mda", "ITEM 2 - MANAGEMENT'S DISCUSSION AND ANALYSIS", 45000),
            ("risk", "ITEM 1A - RISK FACTORS", 25000),
        ],
        # 20-F (foreign annual report): Item 18 carries the audited statements, Item 5 is the
        # MD&A equivalent (Operating & Financial Review), Item 3 holds the Risk Factors.
        "20-F": [
            ("financials", "ITEM 18 - FINANCIAL STATEMENTS", 70000),
            ("mda", "ITEM 5 - OPERATING AND FINANCIAL REVIEW AND PROSPECTS", 55000),
            ("risk", "ITEM 3.D - RISK FACTORS", 45000),
        ],
    }

    # Financial keyword set for the dense-window backfill (mirrors the regex path's fin_kw).
    _FIN_KW = ["operating activities", "cash flow", "consolidated statements", "balance sheet",
               "net income", "total revenue", "net sales", "gross", "operating income", "liquidity"]
    # Below this many chars, a parsed Item 8 (10-K) / Item 1 (10-Q) is treated as a stub — some
    # filers incorporate the financial statements by reference, leaving only a short pointer.
    _FINANCIALS_MIN_CHARS = 5000
    # MD&A keyword set for the dense-window backfill (mirrors the regex path's narrative recovery).
    _MDA_KW = ["results of operations", "liquidity and capital resources", "management's discussion",
               "critical accounting", "compared to", "non-interest income", "net interest income",
               "operating segment", "contractual obligations", "off-balance sheet"]
    # Below this, a parsed Item 7 (10-K) / Item 2 (10-Q) MD&A is treated as a stub — big financial
    # filers (e.g. JPM) routinely parse only a thin Item 7 pointer even when the full narrative is
    # present in the document, so backfill it the same way the financial statements are.
    _MDA_MIN_CHARS = 3000

    def assemble_excerpt_from_sections(
        self,
        sections: Optional[Dict[str, str]],
        filing_type: str = "10-K",
        filing_text: Optional[str] = None,
    ) -> str:
        """Build the critical-sections excerpt from edgartools-parsed section text.

        ``sections`` is keyed by canonical name ("financials" / "mda" / "risk") as returned by
        ``xbrl_service.get_filing_sections``. When the financial-statements section is thin/absent
        (e.g. incorporated by reference) and ``filing_text`` is supplied, a dense financial window
        of the document is appended so statement-level depth isn't lost — XBRL still supplies the
        verified headline numbers separately. Returns "" when nothing usable is present so the
        caller can fall back to the legacy regex extractor.
        """
        if not sections:
            return ""
        filing_type_key = (filing_type or "10-K").upper()
        layout = self._SECTION_LAYOUT.get(filing_type_key, self._SECTION_LAYOUT["10-K"])

        parts: List[str] = []
        financials_len = 0
        for canonical, label, cap in layout:
            text = (sections.get(canonical) or "").strip()
            if len(text) < 200:
                continue
            parts.append(f"{label}:\n{text[:cap]}")
            if canonical == "financials":
                financials_len = len(text)
            logger.info(f"{filing_type_key} {label.split(' - ')[0]} (edgartools): captured {len(text):,} chars")

        if not parts:
            return ""

        # Backfill thin/absent narrative sections with dense, keyword-anchored windows of the raw
        # document so depth isn't lost. Financials are often incorporated by reference (a short
        # pointer); big financial filers (e.g. JPM) likewise parse only a stub Item 7 MD&A even when
        # the full narrative is present. XBRL still supplies the verified headline numbers (P1.1).
        financials_thin = financials_len < self._FINANCIALS_MIN_CHARS
        mda_len = len((sections.get("mda") or "").strip())
        mda_thin = mda_len < self._MDA_MIN_CHARS
        if (financials_thin or mda_thin) and filing_text:
            try:
                clean = BeautifulSoup(filing_text, "html.parser").get_text(separator="\n", strip=False)
            except Exception:  # noqa: BLE001
                clean = filing_text
            fin_slice = self._dense_window(clean, self._FIN_KW) if financials_thin else ""
            if fin_slice:
                parts.append("FINANCIAL STATEMENTS CONTEXT (recovered from filing):\n" + fin_slice)
                logger.info(
                    f"{filing_type_key} financials thin ({financials_len:,} chars) — "
                    f"backfilled dense window ({len(fin_slice):,} chars)"
                )
            if mda_thin:
                mda_slice = self._dense_window(clean, self._MDA_KW)
                # Skip when it substantially overlaps the financials window: financial and MD&A
                # keywords cluster in the same region (Item 7/Item 8 are adjacent), so the two dense
                # windows are often near-duplicates and a second copy just wastes model context. A
                # mid-window probe catches that cheaply (vs an exact compare that misses partial overlap).
                probe = mda_slice[len(mda_slice) // 2: len(mda_slice) // 2 + 1000]
                overlaps_financials = bool(fin_slice) and bool(probe) and probe in fin_slice
                if mda_slice and not overlaps_financials:
                    parts.append("MD&A CONTEXT (recovered from filing):\n" + mda_slice)
                    logger.info(
                        f"{filing_type_key} MD&A thin ({mda_len:,} chars) — "
                        f"backfilled dense window ({len(mda_slice):,} chars)"
                    )

        excerpt = ("\n\n" + "=" * 50 + "\n\n").join(parts)
        logger.info(
            f"{filing_type_key} extraction: {len(parts)} sections via edgartools, "
            f"{len(excerpt):,} chars (precise)"
        )
        return excerpt[:320000]

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

        # Section recovery uses the configured recovery model (Pro by default; can opt into a
        # cheaper model via AI_SECTION_RECOVERY_MODEL / AI_FAST_MODEL — see config.py / A11).
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
                    logger.warning(f"Secondary completion model {model_name} failed ({error_msg[:120]}). Trying next model...")
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
        stream_cb: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Phase 1: Extract structured financial schema from the filing.

        When ``stream_cb`` is provided (A5 progressive reveal), the primary model is streamed and
        ``stream_cb(partial_markdown)`` is awaited with throttled preview renders as the JSON fills
        in; the COMPLETE content is then assembled through the same path as the non-streaming branch,
        so the final result is identical. ``stream_cb`` errors / streaming failures propagate to the
        caller (``summarize_filing``), which falls back to non-streaming — streaming never degrades
        the output, it only adds the preview."""
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

        # Roadmap 2.6 Phase B: the grounding block is built by the module-level
        # `build_xbrl_narrative_section` (testable, behavior-preserving). It now also surfaces the
        # full cash-flow statement (investing/financing) + working-capital lines when present.
        xbrl_section = build_xbrl_narrative_section(xbrl_metrics)

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
                # Prefer an edgartools-parsed excerpt built upstream; fall back to the legacy
                # regex extractor, then to a raw slice.
                prev_sample = (
                    prev_filing.get("excerpt")
                    or self.extract_critical_sections(prev_text, "10-K")
                    or prev_text[:12000]
                )
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

        # Roadmap S1 (flagged): in structured-output mode use the schema-first prompt (which
        # omits the narrative "produce a cohesive markdown summary / 600-1000 words" block that
        # contradicts the JSON demand). Off → current behavior, unchanged.
        structured_mode = settings.USE_STRUCTURED_OUTPUT
        analyst_preamble = (
            get_structured_prompt(filing_type_key) if structured_mode else prompt_template.system
        )

        prompt = f"""{analyst_preamble}

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
- OBJECTIVITY: Use neutral, factual language. Do NOT use promotional or subjective adjectives (e.g. strong, robust, solid, healthy, surged, soared, plunged, record, exceptional, impressive, fortress); state magnitude and direction with figures instead (e.g. "increased 14% YoY"). Such words are permitted ONLY inside a direct, attributed management quote.
- Keep monetary values human-readable (e.g., "$17.7B", "$425M", "$912M").
- Express percentage changes with one decimal place where available (e.g., "up 8.3% YoY").
- For arrays, include 1-4 high-signal, evidence-backed bullets ordered by materiality. If nothing qualifies, return ["Not disclosed—<concise reason>"] instead of leaving the array empty.
- Empty sections are unacceptable. Do not fabricate data; explain the absence using the Not disclosed pattern when required.
- Provide supporting evidence excerpts for each risk factor (direct quote or XBRL tag reference), and when possible populate `source_section_ref` with the most relevant 10-Q section (for example: "Item 1A. Risk Factors", "Item 2. MD&A")."""

        import asyncio
        models_to_try = [self.get_model_for_filing(filing_type_key)] + self._fallback_models
        models_to_try = list(dict.fromkeys(models_to_try))

        if stream_cb is not None:
            # A5: best-effort progressive reveal. Stream the primary model once, emitting throttled
            # partial-markdown previews as the JSON fills in, then assemble the COMPLETE content
            # through the SAME path as the non-streaming branch (identical final output). Any error
            # propagates so summarize_filing can fall back to non-streaming generation.
            stream_model = models_to_try[0]
            stream_timeout = config.get("ai_timeout", 45.0)
            stream_kwargs: Dict[str, Any] = dict(
                model=stream_model,
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
                temperature=0.1 if structured_mode else 0.2,
                max_tokens=config.get("max_tokens", 1500),
                stream=True,
                response_format={"type": "json_object"},
            )
            if _thinking_disabled_model(stream_model, getattr(settings, "OPENAI_BASE_URL", None)):
                stream_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
            else:
                stream_kwargs["max_tokens"] = min(stream_kwargs["max_tokens"], 8192)
            streamed_content = await asyncio.wait_for(
                self._stream_collect(stream_kwargs, stream_cb, filing_type_key, xbrl_metrics),
                timeout=stream_timeout,
            )
            return await self._assemble_structured_summary(
                streamed_content, filing_text, filing_type_key, filing_sample, xbrl_metrics
            )

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
                    create_kwargs: Dict[str, Any] = dict(
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
                        # Roadmap S1: pin extraction temperature low (0.1) in structured mode for
                        # determinism; otherwise keep the prior 0.2.
                        temperature=0.1 if structured_mode else 0.2,
                        max_tokens=config.get("max_tokens", 1500),
                    )
                    # Always enforce JSON at the API layer (provider-agnostic) so validity never
                    # depends on the model resolving a prompt-vs-schema conflict. Critical for
                    # reliable extraction across Gemini/DeepSeek and for avoiding non-object output.
                    create_kwargs["response_format"] = {"type": "json_object"}
                    # Reasoning models (DeepSeek V4, Zhipu GLM via z.ai) default to "thinking" mode;
                    # disable it for this deterministic extraction task and keep full max_tokens
                    # headroom (prevents mid-JSON truncation). For everything else (e.g. Gemini),
                    # cap max_tokens to the provider's ~8192 output ceiling.
                    if _thinking_disabled_model(model_name, getattr(settings, "OPENAI_BASE_URL", None)):
                        create_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
                    else:
                        create_kwargs["max_tokens"] = min(create_kwargs["max_tokens"], 8192)
                    response = await asyncio.wait_for(
                        self.client.chat.completions.create(**create_kwargs),
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
        return await self._assemble_structured_summary(
            content, filing_text, filing_type_key, filing_sample, xbrl_metrics
        )

    async def _assemble_structured_summary(
        self,
        content: Optional[str],
        filing_text: str,
        filing_type_key: str,
        filing_sample: str,
        xbrl_metrics: Optional[Dict],
    ) -> Dict[str, Any]:
        """Parse the model's JSON response → recover empty sections → apply fallbacks → return the
        structured summary dict. Shared by the non-streaming path and the streaming (progressive
        reveal) path, so the FINAL output is identical regardless of how the content was produced —
        this is the invariant that makes streaming a zero-quality-risk change."""
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

        # R1 guard: coerce non-object JSON (bare array / wrapped object) so .get() never crashes.
        summary_data = self._coerce_summary_dict(summary_data)
        sections_info = summary_data.get("sections")
        if not isinstance(sections_info, dict):
            sections_info = {}
        metadata = summary_data.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        missing_sections = self._find_empty_sections(sections_info)
        if missing_sections:
            detailed_sections = self.extract_sections(filing_text, filing_type_key)
            recovered = await self._recover_missing_sections(
                missing_sections,
                filing_type_key,
                detailed_sections,
                filing_sample,
                metadata,
            )
            if recovered:
                sections_info.update(recovered)

        self._apply_structured_fallbacks(
            sections_info,
            metadata,
            xbrl_metrics,
        )
        summary_data["sections"] = sections_info
        summary_data["metadata"] = metadata

        return summary_data

    async def _stream_collect(
        self,
        create_kwargs: Dict[str, Any],
        stream_cb: Any,
        filing_type_key: str,
        xbrl_metrics: Optional[Dict],
    ) -> str:
        """Stream a structured-extraction call, awaiting ``stream_cb(partial_markdown)`` with throttled
        preview renders as the JSON fills in, and return the COMPLETE accumulated content. Preview
        rendering and ``stream_cb`` are best-effort — they never affect the returned content."""
        parts: List[str] = []
        emitted_at = 0
        stream = await self.client.chat.completions.create(**create_kwargs)
        async for chunk in stream:
            choices = getattr(chunk, "choices", None)
            if not choices:
                continue
            delta = getattr(choices[0], "delta", None)
            piece = getattr(delta, "content", None) if delta is not None else None
            if not piece:
                continue
            parts.append(piece)
            total = sum(len(p) for p in parts)
            # Re-render a preview every ~1500 new chars to keep preview frames modest.
            if total - emitted_at >= 1500:
                emitted_at = total
                preview = self._partial_markdown_preview("".join(parts), xbrl_metrics)
                if preview:
                    try:
                        await stream_cb(preview)
                    except Exception:  # noqa: BLE001 — a consumer error must never abort generation
                        pass
        return "".join(parts)

    def _partial_markdown_preview(self, partial_content: str, xbrl_metrics: Optional[Dict]) -> Optional[str]:
        """Best-effort partial render: repair-parse the in-progress JSON and build a partial markdown
        preview with the SAME builder as the final output. Returns None on any failure (preview frames
        are optional and are always superseded by the authoritative final render)."""
        try:
            repaired = self._repair_json(self._clean_json_payload(partial_content or ""))
            data = self._coerce_summary_dict(json.loads(repaired))
            if not isinstance(data.get("sections"), dict):
                return None
            return self._build_structured_markdown(data) or None
        except Exception:  # noqa: BLE001 — partial JSON frequently won't parse cleanly; skip this frame
            return None

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        *,
        model: Optional[str] = None,
        max_tokens: int = 1200,
        temperature: float = 0.2,
    ) -> AsyncGenerator[str, None]:
        """Stream raw assistant delta content for an arbitrary chat completion.

        A thin, transport-agnostic wrapper used by the "Ask this Filing" Copilot (A2). It does not
        own any prompt/JSON contract — callers pass the full ``messages`` and parse the streamed
        text themselves. Yields only ``delta.content`` strings in order.

        ``model`` defaults to ``self.model``. DeepSeek's reasoning ("thinking") mode is disabled so
        the stream is the answer text, not chain-of-thought. Tolerant try/except mirrors the existing
        streaming method: on failure it yields a single chunk prefixed with ``STREAM_ERROR_SENTINEL``
        (so a consumer can surface a real error rather than stream it as the answer) rather than
        raising, so the generator never breaks the SSE contract.
        """
        model_name = model or self.model
        try:
            create_kwargs: Dict[str, Any] = {
                "model": model_name,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
            }
            if _thinking_disabled_model(model_name, getattr(settings, "OPENAI_BASE_URL", None)):
                create_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
            stream = await self.client.chat.completions.create(**create_kwargs)
            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        yield delta.content
        except Exception as e:  # noqa: BLE001 — tolerant: never raise out of the stream
            error_msg = str(e)
            logger.warning(f"stream_chat failed for {model_name}: {error_msg[:200]}")
            yield f"{STREAM_ERROR_SENTINEL}{error_msg[:200]}"

    async def stream_chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        run_tool: Any,
        *,
        model: Optional[str] = None,
        max_tokens: int = 1200,
        temperature: float = 0.2,
        max_rounds: int = 4,
        usage_sink: Optional[Dict[str, int]] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream a chat completion that may call tools, executing them server-side between rounds.

        A function-calling sibling of :meth:`stream_chat` used by the "Ask this Filing" Copilot's
        numeric path (P5). The model is offered ``tools`` with ``tool_choice="auto"``; when it asks
        for one, this method runs it via ``run_tool(name, args)`` and feeds the result back, then lets
        the model continue. Plain answer text is yielded live (token-by-token) exactly like
        ``stream_chat``, so the caller's sentinel-split prose handling is unchanged.

        The tricky part is **stream-assembling tool calls**: a single tool call's
        ``function.arguments`` arrives as a sequence of string fragments across many chunks, keyed by
        ``tc.index``. We accumulate ``id``/``name`` and concatenate the argument fragments per index,
        then at the round's end append the assistant ``tool_calls`` message + one ``tool`` result
        message per call and loop again (the next round streams the answer). Rounds that only call
        tools normally carry empty ``content``, so yielding their content live is harmless.

        Args:
            messages: The conversation so far (mutated in place across rounds with tool turns).
            tools: OpenAI-format tool schemas to offer the model.
            run_tool: ``Callable[[str, dict], dict]`` executing a tool by name + decoded args.
            model: Model id (defaults to ``self.model``).
            max_tokens: Max completion tokens per round.
            temperature: Sampling temperature.
            max_rounds: Hard cap on tool-call rounds to bound latency/loops.

        Yields:
            Assistant answer ``delta.content`` strings in order. On any failure yields a single chunk
            prefixed with ``STREAM_ERROR_SENTINEL`` (so the consumer can surface a real error instead
            of streaming it as the answer) rather than raising, so the SSE contract is never broken.
        """
        model_name = model or self.model
        disable_thinking = _thinking_disabled_model(model_name, getattr(settings, "OPENAI_BASE_URL", None))
        try:
            for _ in range(max_rounds):
                create_kwargs: Dict[str, Any] = {
                    "model": model_name,
                    "messages": messages,
                    "tools": tools,
                    "tool_choice": "auto",
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": True,
                }
                if disable_thinking:
                    create_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
                # Ask for token usage on the final (choices-empty) chunk when the caller wants to
                # meter cost. Opt-in, so the default streaming contract is otherwise unchanged.
                if usage_sink is not None:
                    create_kwargs["stream_options"] = {"include_usage": True}

                stream = await self.client.chat.completions.create(**create_kwargs)

                # Assemble tool calls across chunks, keyed by their delta index. Each entry holds the
                # call id, function name, and the concatenated arguments-string fragments. Whether any
                # tool calls were assembled (not finish_reason) drives the round's branch below.
                tool_calls: Dict[int, Dict[str, str]] = {}
                content_parts: List[str] = []
                # Models narrate between tool rounds ("Let me gather the figures…") — chatter the
                # user must never see (field report: it streamed as the answer's opening lines).
                # A round's content is HELD BACK until the round's nature is known: the first
                # tool-call delta marks a tool round and its held content is dropped from the
                # stream (it still rides the assistant message below, so the model keeps its own
                # context); content that outgrows the hold-back cap is a real answer — flush and
                # stream live from there. A short final answer that never hits the cap flushes
                # when the round ends without tool calls.
                held: List[str] = []
                held_len = 0
                streaming_live = False

                async for chunk in stream:
                    if not chunk.choices:
                        # The include_usage final chunk has empty choices + a `usage` payload;
                        # accumulate it across tool rounds (best-effort, only when requested). Some
                        # OpenAI-compatible gateways return usage as a dict rather than an object, so
                        # handle both — getattr on a dict would silently zero the token counts.
                        if usage_sink is not None:
                            u = getattr(chunk, "usage", None)
                            if u is not None:
                                is_dict = isinstance(u, dict)
                                p_tok = (u.get("prompt_tokens") if is_dict else getattr(u, "prompt_tokens", 0)) or 0
                                c_tok = (u.get("completion_tokens") if is_dict else getattr(u, "completion_tokens", 0)) or 0
                                t_tok = (u.get("total_tokens") if is_dict else getattr(u, "total_tokens", 0)) or 0
                                # DeepSeek-specific: input tokens served from the context cache (HIT)
                                # vs not (MISS), priced ~120x apart. Absent on providers that don't
                                # cache → 0, and the cost estimate then treats all input as a miss.
                                hit_tok = (u.get("prompt_cache_hit_tokens") if is_dict else getattr(u, "prompt_cache_hit_tokens", 0)) or 0
                                miss_tok = (u.get("prompt_cache_miss_tokens") if is_dict else getattr(u, "prompt_cache_miss_tokens", 0)) or 0
                                usage_sink["prompt_tokens"] = usage_sink.get("prompt_tokens", 0) + p_tok
                                usage_sink["completion_tokens"] = usage_sink.get("completion_tokens", 0) + c_tok
                                usage_sink["total_tokens"] = usage_sink.get("total_tokens", 0) + t_tok
                                usage_sink["cache_hit_tokens"] = usage_sink.get("cache_hit_tokens", 0) + hit_tok
                                usage_sink["cache_miss_tokens"] = usage_sink.get("cache_miss_tokens", 0) + miss_tok
                        continue
                    choice = chunk.choices[0]
                    delta = choice.delta
                    if delta is None:
                        continue
                    if delta.content:
                        content_parts.append(delta.content)
                        if streaming_live:
                            yield delta.content
                        elif not tool_calls:
                            held.append(delta.content)
                            held_len += len(delta.content)
                            if held_len >= _TOOL_ROUND_HOLDBACK_CHARS:
                                streaming_live = True
                                yield "".join(held)
                                held = []
                        # else: a tool round's narration — dropped from the stream.
                    for tc in (delta.tool_calls or []):
                        slot = tool_calls.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
                        if tc.id:
                            slot["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                slot["name"] = tc.function.name
                            if tc.function.arguments:
                                slot["arguments"] += tc.function.arguments

                # No tool calls → this round's content was the final answer; flush anything the
                # hold-back was still sitting on (a short answer that never crossed the cap).
                if not tool_calls:
                    if held:
                        yield "".join(held)
                    return

                # Append the assistant tool-call turn, then run each call and append its result, so
                # the next round can stream the grounded answer.
                assembled = [tool_calls[idx] for idx in sorted(tool_calls)]
                messages.append({
                    "role": "assistant",
                    "content": "".join(content_parts),
                    "tool_calls": [
                        {
                            "id": call["id"],
                            "type": "function",
                            "function": {"name": call["name"], "arguments": call["arguments"]},
                        }
                        for call in assembled
                    ],
                })
                for call in assembled:
                    try:
                        parsed_args = json.loads(call["arguments"] or "{}")
                    except (ValueError, TypeError):
                        parsed_args = {}
                    # Live "show the work" signal: announce the tool call, run it, then report the
                    # outcome. Labelling is left to the (copilot-specific) consumer.
                    yield STREAM_ACTIVITY_SENTINEL + json.dumps(
                        {"name": call["name"], "args": parsed_args, "phase": "start"}
                    )
                    result = run_tool(call["name"], parsed_args)
                    ok = not (isinstance(result, dict) and "error" in result)
                    yield STREAM_ACTIVITY_SENTINEL + json.dumps(
                        {"name": call["name"], "args": parsed_args, "phase": "done", "ok": ok}
                    )
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": json.dumps(result, default=str),
                    })
                # Loop continues for the next round (which should stream the answer).
        except Exception as e:  # noqa: BLE001 — tolerant: never raise out of the stream
            error_msg = str(e)
            logger.warning(f"stream_chat_with_tools failed for {model_name}: {error_msg[:200]}")
            yield f"{STREAM_ERROR_SENTINEL}{error_msg[:200]}"

    async def summarize_filing(
        self,
        filing_text: str,
        company_name: str,
        filing_type: str,
        previous_filings: Optional[list] = None,
        xbrl_metrics: Optional[Dict] = None,
        filing_excerpt: Optional[str] = None,
        stream_cb: Optional[Any] = None,
    ) -> Dict:
        """Generate newsroom-ready summary using structured extraction + editorial writer phases.

        ``stream_cb`` (A5) opts into progressive reveal: the extraction is streamed and
        ``stream_cb(partial_markdown)`` is awaited as sections fill in. If streaming fails for any
        non-timeout reason it falls back to non-streaming generation, so the result is never
        degraded — the final assembled summary is identical either way."""
        import asyncio

        filing_type_key = (filing_type or "10-K").upper()
        try:
            try:
                structured_summary = await self.generate_structured_summary(
                    filing_text,
                    company_name,
                    filing_type,
                    previous_filings=previous_filings,
                    xbrl_metrics=xbrl_metrics,
                    filing_excerpt=filing_excerpt,
                    stream_cb=stream_cb,
                )
            except asyncio.TimeoutError:
                raise
            except Exception as stream_error:
                if stream_cb is None:
                    raise
                logger.warning(
                    f"Streaming extraction failed ({str(stream_error)[:160]}); "
                    "falling back to non-streaming generation"
                )
                structured_summary = await self.generate_structured_summary(
                    filing_text,
                    company_name,
                    filing_type,
                    previous_filings=previous_filings,
                    xbrl_metrics=xbrl_metrics,
                    filing_excerpt=filing_excerpt,
                    stream_cb=None,
                )

        except asyncio.TimeoutError:
            timeout_seconds = self._get_type_config(filing_type_key).get("ai_timeout", 30.0)
            logger.warning(f"Structured extraction timed out after {timeout_seconds}s for {filing_type_key}")
            return {
                "status": "error",
                "message": "Unable to complete summary due to parsing timeout. Suggest retrying later.",
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
            logger.error(f"Structured extraction error: {error_msg}")
            return {
                "status": "error",
                "message": "We couldn't generate this summary just now. Please try again shortly.",
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
        # Deterministic guard: for a bank that reports no single revenue line, drop any LLM-authored
        # conflated "Revenue" row so it can never ship in the table, prose, or stored payload.
        # `sections_info` is the same object every downstream consumer reads, so reassigning it here
        # covers the markdown, "Financial Overview", raw payload, and the response column at once.
        financial_section = _sanitize_bank_financial_highlights(financial_section, xbrl_metrics)
        if isinstance(sections_info, dict):
            sections_info["financial_highlights"] = financial_section

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

        # P1.4: render markdown deterministically from the structured data — no second editorial-
        # writer LLM call. The structured render is rich and objective; the separate writer added
        # cost, latency and a recurring failure mode (it kept failing the length gate) plus a
        # journalistic voice at odds with the objective-summary goal (approved decision 3a).
        writer_result = None
        writer_error: Optional[str] = None
        writer_fallback_reason: Optional[str] = None
        final_markdown = self._build_structured_markdown(structured_summary)

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
                if filing_type_key in {"10-K", "20-F"}:
                    # 20-F is a foreign annual report — label as a fiscal year like a 10-K.
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


# Public import surface of this façade. Callers import these from ``app.services.openai_service``;
# the definitions live in the ``app.services.ai`` package (roadmap S2 split). Listed here so the
# split stays caller-transparent and so ruff treats the re-exported imports as used (no F401).
__all__ = [
    "openai_service",
    "OpenAIService",
    "build_xbrl_narrative_section",
    "_XBRL_NARRATIVE_SPEC",
    "_format_xbrl_metric_value",
    "_is_no_total_bank",
    "_sanitize_bank_financial_highlights",
]

