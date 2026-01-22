"""
SEC Filing Parser Service

Uses sec-parser (AlphaSense) to parse SEC filings into semantic structures.
Handles 10-Q and 10-K filings with special attention to:
- Management's Discussion and Analysis (MD&A)
- Risk Factors
- Financial Statements
- Controls and Procedures
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Section patterns for fallback parsing (10-Q)
SECTION_PATTERNS_10Q = {
    "financial_statements": [
        r"item\s*1\.?\s*financial\s*statements",
        r"condensed\s*consolidated\s*financial\s*statements",
        r"financial\s*statements\s*and\s*supplementary\s*data",
    ],
    "mdna": [
        r"item\s*2\.?\s*management['']?s?\s*discussion",
        r"md&a",
        r"management['']?s?\s*discussion\s*and\s*analysis",
    ],
    "market_risk": [
        r"item\s*3\.?\s*quantitative\s*and\s*qualitative",
        r"market\s*risk\s*disclosure",
    ],
    "controls": [
        r"item\s*4\.?\s*controls\s*and\s*procedures",
        r"disclosure\s*controls",
    ],
    "legal_proceedings": [
        r"item\s*1\.?\s*legal\s*proceedings",
        r"part\s*ii.*item\s*1\.?\s*legal",
    ],
    "risk_factors": [
        r"item\s*1a\.?\s*risk\s*factors",
        r"risk\s*factors",
    ],
    "exhibits": [
        r"item\s*6\.?\s*exhibits",
        r"exhibit\s*index",
    ],
}

# Section patterns for 10-K filings
SECTION_PATTERNS_10K = {
    # Part I
    "business": [
        r"item\s*1\.?\s*business\b",
        r"part\s*i.*item\s*1\.?\s*business",
    ],
    "risk_factors": [
        r"item\s*1a\.?\s*risk\s*factors",
        r"risk\s*factors",
    ],
    "unresolved_comments": [
        r"item\s*1b\.?\s*unresolved\s*staff\s*comments",
    ],
    "properties": [
        r"item\s*2\.?\s*properties",
    ],
    "legal_proceedings": [
        r"item\s*3\.?\s*legal\s*proceedings",
    ],
    "mine_safety": [
        r"item\s*4\.?\s*mine\s*safety",
    ],
    # Part II
    "market_equity": [
        r"item\s*5\.?\s*market\s*for.*common\s*equity",
        r"item\s*5\.?\s*market\s*for.*registrant",
    ],
    "selected_financial": [
        r"item\s*6\.?\s*selected\s*financial\s*data",
        r"\[reserved\]",  # Item 6 often marked reserved for smaller companies
    ],
    "mdna": [
        r"item\s*7\.?\s*management['']?s?\s*discussion",
        r"md&a",
        r"management['']?s?\s*discussion\s*and\s*analysis",
    ],
    "market_risk": [
        r"item\s*7a\.?\s*quantitative\s*and\s*qualitative",
        r"market\s*risk\s*disclosure",
    ],
    "financial_statements": [
        r"item\s*8\.?\s*financial\s*statements",
        r"consolidated\s*financial\s*statements",
        r"financial\s*statements\s*and\s*supplementary\s*data",
    ],
    "accountant_changes": [
        r"item\s*9\.?\s*changes\s*in\s*and\s*disagreements",
    ],
    "controls": [
        r"item\s*9a\.?\s*controls\s*and\s*procedures",
        r"disclosure\s*controls",
    ],
    "other_info": [
        r"item\s*9b\.?\s*other\s*information",
    ],
    # Part III
    "directors": [
        r"item\s*10\.?\s*directors",
        r"executive\s*officers.*corporate\s*governance",
    ],
    "compensation": [
        r"item\s*11\.?\s*executive\s*compensation",
    ],
    "security_ownership": [
        r"item\s*12\.?\s*security\s*ownership",
    ],
    "relationships": [
        r"item\s*13\.?\s*certain\s*relationships",
    ],
    "accountant_fees": [
        r"item\s*14\.?\s*principal\s*account",
    ],
    # Part IV
    "exhibits": [
        r"item\s*15\.?\s*exhibits",
        r"exhibit\s*index",
        r"financial\s*statement\s*schedules",
    ],
}

# Combined patterns for backward compatibility
SECTION_PATTERNS = SECTION_PATTERNS_10Q


@dataclass
class ParsedSection:
    """A parsed section from an SEC filing"""
    section_type: str
    title: str
    content: str
    tables: List[Dict[str, Any]] = field(default_factory=list)
    subsections: List["ParsedSection"] = field(default_factory=list)
    source_index: int = 0


@dataclass
class ParsedFiling:
    """Complete parsed SEC filing"""
    filing_type: str
    sections: Dict[str, ParsedSection]
    raw_text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    parsing_method: str = "sec-parser"  # or "fallback"


class FilingParser:
    """
    Parse SEC filings into semantic structures.

    Uses sec-parser library for semantic parsing with fallback
    to regex-based extraction for edge cases.
    """

    def __init__(self):
        self._sec_parser_available = self._check_sec_parser()

    def _check_sec_parser(self) -> bool:
        """Check if sec-parser is available"""
        try:
            import sec_parser
            return True
        except ImportError:
            logger.warning(
                "sec-parser not installed. Using fallback parser. "
                "Install with: pip install sec-parser"
            )
            return False

    def parse(self, html: str, filing_type: str = "10-Q") -> ParsedFiling:
        """
        Parse SEC filing HTML into semantic structure.

        Args:
            html: Raw HTML content of the filing
            filing_type: Type of filing (10-Q, 10-K, etc.)

        Returns:
            ParsedFiling with extracted sections
        """
        if self._sec_parser_available:
            try:
                return self._parse_with_sec_parser(html, filing_type)
            except Exception as e:
                logger.warning(
                    f"sec-parser failed, falling back to regex parser: {e}"
                )
                return self._parse_with_fallback(html, filing_type)
        else:
            return self._parse_with_fallback(html, filing_type)

    def _parse_with_sec_parser(self, html: str, filing_type: str) -> ParsedFiling:
        """Parse using sec-parser library"""
        from sec_parser import Edgar10QParser, Edgar10KParser
        from sec_parser.semantic_elements import (
            TextElement,
            TitleElement,
            TableElement,
            TopSectionTitle,
        )

        # Use the appropriate parser based on filing type
        if filing_type.startswith("10-K"):
            parser = Edgar10KParser()
        else:
            parser = Edgar10QParser()
        elements = parser.parse(html)

        sections = {}
        current_section_type = None
        current_section_content = []
        current_section_title = ""
        current_tables = []

        for element in elements:
            # Check for section titles
            if isinstance(element, (TitleElement, TopSectionTitle)):
                # Save previous section if exists
                if current_section_type and current_section_content:
                    sections[current_section_type] = ParsedSection(
                        section_type=current_section_type,
                        title=current_section_title,
                        content="\n".join(current_section_content),
                        tables=current_tables,
                    )

                # Identify new section
                title_text = element.text if hasattr(element, 'text') else str(element)
                current_section_type = self._identify_section_type(title_text, filing_type)
                current_section_title = title_text
                current_section_content = []
                current_tables = []

            elif isinstance(element, TextElement):
                text = element.text if hasattr(element, 'text') else str(element)
                if text.strip():
                    current_section_content.append(text.strip())

            elif isinstance(element, TableElement):
                table_data = self._extract_table_data(element)
                if table_data:
                    current_tables.append(table_data)

        # Don't forget the last section
        if current_section_type and current_section_content:
            sections[current_section_type] = ParsedSection(
                section_type=current_section_type,
                title=current_section_title,
                content="\n".join(current_section_content),
                tables=current_tables,
            )

        # Extract raw text for summary purposes
        raw_text = self._extract_raw_text(html)

        return ParsedFiling(
            filing_type=filing_type,
            sections=sections,
            raw_text=raw_text,
            parsing_method="sec-parser",
        )

    def _parse_with_fallback(self, html: str, filing_type: str) -> ParsedFiling:
        """Fallback regex-based parser"""
        soup = BeautifulSoup(html, "html.parser")

        # Remove script and style elements
        for element in soup(["script", "style", "head"]):
            element.decompose()

        text = soup.get_text(separator="\n")
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        sections = {}
        current_section = None
        current_content = []
        current_title = ""

        for i, line in enumerate(lines):
            # Check if this line starts a new section
            section_type = self._identify_section_type(line, filing_type)
            if section_type:
                # Save previous section
                if current_section and current_content:
                    sections[current_section] = ParsedSection(
                        section_type=current_section,
                        title=current_title,
                        content="\n".join(current_content),
                        source_index=i,
                    )

                current_section = section_type
                current_title = line
                current_content = []
            elif current_section:
                current_content.append(line)

        # Save last section
        if current_section and current_content:
            sections[current_section] = ParsedSection(
                section_type=current_section,
                title=current_title,
                content="\n".join(current_content),
            )

        # Extract tables using BeautifulSoup
        for section_name, section in sections.items():
            section.tables = self._extract_tables_from_html(html, section.title)

        return ParsedFiling(
            filing_type=filing_type,
            sections=sections,
            raw_text="\n".join(lines),
            parsing_method="fallback",
        )

    def _identify_section_type(
        self, text: str, filing_type: str = "10-Q"
    ) -> Optional[str]:
        """Identify section type from title text"""
        text_lower = text.lower().strip()

        # Select patterns based on filing type
        if filing_type.startswith("10-K"):
            patterns_dict = SECTION_PATTERNS_10K
        else:
            patterns_dict = SECTION_PATTERNS_10Q

        for section_type, patterns in patterns_dict.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return section_type

        return None

    def _extract_table_data(self, table_element) -> Optional[Dict[str, Any]]:
        """Extract table data from sec-parser TableElement"""
        try:
            # sec-parser provides table data in various formats
            if hasattr(table_element, 'get_table_data'):
                return {
                    "type": "financial_table",
                    "data": table_element.get_table_data(),
                }
            elif hasattr(table_element, 'text'):
                return {
                    "type": "text_table",
                    "data": table_element.text,
                }
            return None
        except Exception as e:
            logger.debug(f"Failed to extract table data: {e}")
            return None

    def _extract_tables_from_html(
        self, html: str, section_title: str
    ) -> List[Dict[str, Any]]:
        """Extract tables from HTML near a section title"""
        tables = []
        soup = BeautifulSoup(html, "html.parser")

        for table in soup.find_all("table"):
            # Check if table is near section title
            table_data = self._parse_html_table(table)
            if table_data:
                tables.append(table_data)

        return tables[:5]  # Limit to first 5 tables per section

    def _parse_html_table(self, table) -> Optional[Dict[str, Any]]:
        """Parse HTML table into structured data"""
        try:
            rows = []
            for tr in table.find_all("tr"):
                row = []
                for cell in tr.find_all(["td", "th"]):
                    text = cell.get_text(strip=True)
                    row.append(text)
                if row:
                    rows.append(row)

            if rows:
                return {
                    "type": "html_table",
                    "headers": rows[0] if rows else [],
                    "rows": rows[1:] if len(rows) > 1 else [],
                }
            return None
        except Exception as e:
            logger.debug(f"Failed to parse HTML table: {e}")
            return None

    def _extract_raw_text(self, html: str) -> str:
        """Extract clean raw text from HTML"""
        soup = BeautifulSoup(html, "html.parser")

        # Remove non-content elements
        for element in soup(["script", "style", "head", "meta", "link"]):
            element.decompose()

        # Get text with newlines preserved
        text = soup.get_text(separator="\n")

        # Clean up excessive whitespace
        lines = [line.strip() for line in text.split("\n")]
        lines = [line for line in lines if line]

        # Remove duplicate blank lines
        cleaned_lines = []
        prev_blank = False
        for line in lines:
            if not line:
                if not prev_blank:
                    cleaned_lines.append(line)
                prev_blank = True
            else:
                cleaned_lines.append(line)
                prev_blank = False

        return "\n".join(cleaned_lines)

    def extract_sections(self, parsed: ParsedFiling) -> Dict[str, Optional[str]]:
        """
        Extract standardized sections from parsed filing.

        Returns a dict with keys for each expected section,
        value is the section content or None if not found.
        """
        return {
            "financial_statements": self._get_section_content(
                parsed, "financial_statements"
            ),
            "mdna": self._get_section_content(parsed, "mdna"),
            "market_risk": self._get_section_content(parsed, "market_risk"),
            "controls": self._get_section_content(parsed, "controls"),
            "legal_proceedings": self._get_section_content(
                parsed, "legal_proceedings"
            ),
            "risk_factors": self._get_section_content(parsed, "risk_factors"),
            "exhibits": self._get_section_content(parsed, "exhibits"),
        }

    def _get_section_content(
        self, parsed: ParsedFiling, section_type: str
    ) -> Optional[str]:
        """Get content for a specific section type"""
        section = parsed.sections.get(section_type)
        if section:
            return section.content
        return None


# Singleton instance
filing_parser = FilingParser()
