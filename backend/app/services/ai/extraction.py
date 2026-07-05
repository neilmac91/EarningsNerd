"""SEC filing section extraction for OpenAIService (roadmap S2 façade split).

``_ExtractionMixin`` holds the pure text-processing path that turns raw/HTML filing text into the
bounded, section-labelled excerpt the summary prompt is grounded on: per-form config, the regex +
edgartools section extractors, table-of-contents/stub detection, dense-window backfill, and the
excerpt assembler. No AI call, no DB, no settings — regex + BeautifulSoup only. The per-form
display-label/length-cap constants (``_SECTION_LAYOUT`` et al.) travel with it as class attributes.
Mixed into ``OpenAIService``; methods resolve through ``self``. Extracted verbatim.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class _ExtractionMixin:
    """Filing section extraction + excerpt assembly, mixed into OpenAIService."""

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

        # Clean and deduplicate, then keep the top 5 by numeric value per key.
        # `segments` entries are (name, value) TUPLES — their patterns carry two capture groups —
        # while every other key holds bare value-strings. The sort key must read the numeric value
        # from BOTH shapes: the previous `x.replace(',', '')` raised AttributeError on a tuple, so a
        # single matched segment (e.g. an Apple 10-K's "iPhone net sales $…") crashed extraction and
        # degraded the whole summary to the fallback path. Unparseable values sort last (0.0).
        def _numeric_sort_value(item: Any) -> float:
            raw = item[1] if isinstance(item, tuple) else item
            try:
                return float(str(raw).replace(',', ''))
            except (ValueError, TypeError):
                return 0.0

        for key in data:
            data[key] = list(set(data[key]))  # Remove duplicates
            data[key] = sorted(data[key], key=_numeric_sort_value, reverse=True)[:5]  # Top 5 by value

        return data

