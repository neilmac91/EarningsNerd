"""
Markdown Serializer Service

Converts parsed SEC filing sections into clean, semantic Markdown
optimized for LLM consumption.
"""

import logging
import re
from typing import Dict, List, Optional, Any
from .filing_parser import ParsedFiling, ParsedSection

logger = logging.getLogger(__name__)


class MarkdownSerializer:
    """
    Convert parsed SEC filings to clean, AI-ready Markdown.

    Produces structured Markdown with:
    - Clear section headers
    - Properly formatted tables
    - Clean prose extraction
    - Source citations
    """

    # Section display order and titles for 10-Q
    SECTION_ORDER_10Q = [
        ("financial_statements", "Item 1. Financial Statements"),
        ("mdna", "Item 2. Management's Discussion and Analysis"),
        ("market_risk", "Item 3. Quantitative and Qualitative Disclosures About Market Risk"),
        ("controls", "Item 4. Controls and Procedures"),
        ("legal_proceedings", "Item 1. Legal Proceedings"),
        ("risk_factors", "Item 1A. Risk Factors"),
        ("exhibits", "Item 6. Exhibits"),
    ]

    # Section display order and titles for 10-K
    SECTION_ORDER_10K = [
        # Part I
        ("business", "Item 1. Business"),
        ("risk_factors", "Item 1A. Risk Factors"),
        ("unresolved_comments", "Item 1B. Unresolved Staff Comments"),
        ("properties", "Item 2. Properties"),
        ("legal_proceedings", "Item 3. Legal Proceedings"),
        ("mine_safety", "Item 4. Mine Safety Disclosures"),
        # Part II
        ("market_equity", "Item 5. Market for Registrant's Common Equity"),
        ("selected_financial", "Item 6. Selected Financial Data"),
        ("mdna", "Item 7. Management's Discussion and Analysis"),
        ("market_risk", "Item 7A. Quantitative and Qualitative Disclosures About Market Risk"),
        ("financial_statements", "Item 8. Financial Statements and Supplementary Data"),
        ("accountant_changes", "Item 9. Changes in and Disagreements with Accountants"),
        ("controls", "Item 9A. Controls and Procedures"),
        ("other_info", "Item 9B. Other Information"),
        # Part III
        ("directors", "Item 10. Directors, Executive Officers and Corporate Governance"),
        ("compensation", "Item 11. Executive Compensation"),
        ("security_ownership", "Item 12. Security Ownership of Certain Beneficial Owners"),
        ("relationships", "Item 13. Certain Relationships and Related Transactions"),
        ("accountant_fees", "Item 14. Principal Accountant Fees and Services"),
        # Part IV
        ("exhibits", "Item 15. Exhibits and Financial Statement Schedules"),
    ]

    def __init__(self, max_section_length: int = 80000):
        """
        Initialize serializer.

        Args:
            max_section_length: Maximum characters per section (truncate beyond)
            Increased from 50000 to 80000 to capture more financial data.
        """
        self.max_section_length = max_section_length

    def serialize(
        self,
        parsed: ParsedFiling,
        metadata: Dict[str, Any],
    ) -> str:
        """
        Convert parsed filing to Markdown.

        Args:
            parsed: ParsedFiling from FilingParser
            metadata: Filing metadata (ticker, dates, etc.)

        Returns:
            Clean Markdown string
        """
        filing_type = metadata.get("filing_type", "10-Q")

        if filing_type.startswith("10-K"):
            return self._serialize_10k(parsed, metadata)
        else:
            return self._serialize_10q(parsed, metadata)

    def _serialize_10q(
        self,
        parsed: ParsedFiling,
        metadata: Dict[str, Any],
    ) -> str:
        """Serialize a 10-Q filing to Markdown."""
        parts = []

        # Header
        parts.append(self._render_header(metadata))

        # Filing info section
        parts.append(self._render_filing_info(metadata))

        # Part I - Financial Information
        part1_sections = ["financial_statements", "mdna", "market_risk", "controls"]
        part1_content = self._render_part(
            "Part I - Financial Information",
            parsed,
            part1_sections,
            self.SECTION_ORDER_10Q,
        )
        if part1_content:
            parts.append(part1_content)

        # Part II - Other Information
        part2_sections = ["legal_proceedings", "risk_factors", "exhibits"]
        part2_content = self._render_part(
            "Part II - Other Information",
            parsed,
            part2_sections,
            self.SECTION_ORDER_10Q,
        )
        if part2_content:
            parts.append(part2_content)

        # Footer with source
        parts.append(self._render_footer(metadata))

        return "\n\n".join(filter(None, parts))

    def _serialize_10k(
        self,
        parsed: ParsedFiling,
        metadata: Dict[str, Any],
    ) -> str:
        """Serialize a 10-K filing to Markdown."""
        parts = []

        # Header
        parts.append(self._render_header(metadata))

        # Filing info section
        parts.append(self._render_filing_info(metadata))

        # Part I - Business & Risk Information
        part1_sections = [
            "business", "risk_factors", "unresolved_comments",
            "properties", "legal_proceedings", "mine_safety"
        ]
        part1_content = self._render_part(
            "Part I",
            parsed,
            part1_sections,
            self.SECTION_ORDER_10K,
        )
        if part1_content:
            parts.append(part1_content)

        # Part II - Financial Information
        part2_sections = [
            "market_equity", "selected_financial", "mdna", "market_risk",
            "financial_statements", "accountant_changes", "controls", "other_info"
        ]
        part2_content = self._render_part(
            "Part II",
            parsed,
            part2_sections,
            self.SECTION_ORDER_10K,
        )
        if part2_content:
            parts.append(part2_content)

        # Part III - Governance Information
        part3_sections = [
            "directors", "compensation", "security_ownership",
            "relationships", "accountant_fees"
        ]
        part3_content = self._render_part(
            "Part III",
            parsed,
            part3_sections,
            self.SECTION_ORDER_10K,
        )
        if part3_content:
            parts.append(part3_content)

        # Part IV - Exhibits
        part4_sections = ["exhibits"]
        part4_content = self._render_part(
            "Part IV",
            parsed,
            part4_sections,
            self.SECTION_ORDER_10K,
        )
        if part4_content:
            parts.append(part4_content)

        # Footer with source
        parts.append(self._render_footer(metadata))

        return "\n\n".join(filter(None, parts))

    def _render_header(self, metadata: Dict[str, Any]) -> str:
        """Render document header"""
        company_name = metadata.get("company_name", "Company")
        filing_type = metadata.get("filing_type", "10-Q")
        fiscal_period = metadata.get("fiscal_period", "")

        if fiscal_period:
            return f"# {company_name} - {filing_type} ({fiscal_period})"
        return f"# {company_name} - {filing_type}"

    def _render_filing_info(self, metadata: Dict[str, Any]) -> str:
        """Render filing information section"""
        lines = ["## Filing Information"]

        if metadata.get("filing_date"):
            lines.append(f"- **Filed:** {metadata['filing_date']}")

        if metadata.get("period_end_date"):
            lines.append(f"- **Period Ending:** {metadata['period_end_date']}")

        if metadata.get("accession_number"):
            lines.append(f"- **Accession Number:** {metadata['accession_number']}")

        if metadata.get("ticker"):
            lines.append(f"- **Ticker:** {metadata['ticker']}")

        lines.append("")
        lines.append("---")

        return "\n".join(lines)

    def _render_part(
        self,
        part_title: str,
        parsed: ParsedFiling,
        section_keys: List[str],
        section_order: List[tuple],
    ) -> Optional[str]:
        """Render a filing part (Part I, II, III, or IV)"""
        sections_content = []

        for section_key, display_title in section_order:
            if section_key not in section_keys:
                continue

            section = parsed.sections.get(section_key)
            if section:
                section_md = self._render_section(section, display_title)
                if section_md:
                    sections_content.append(section_md)

        if not sections_content:
            return None

        return f"## {part_title}\n\n" + "\n\n".join(sections_content)

    def _render_section(
        self,
        section: ParsedSection,
        display_title: str,
    ) -> Optional[str]:
        """Render a single section to Markdown"""
        if not section.content and not section.tables:
            return None

        parts = [f"### {display_title}"]

        # Render content
        if section.content:
            cleaned_content = self._clean_text(section.content)
            if len(cleaned_content) > self.max_section_length:
                cleaned_content = cleaned_content[:self.max_section_length]
                cleaned_content += "\n\n*[Section truncated for length]*"
            parts.append(cleaned_content)

        # Render tables - increased limit to capture more financial data
        for i, table in enumerate(section.tables[:10]):  # Increased from 3 to 10 tables per section
            table_md = self._render_table(table)
            if table_md:
                parts.append(table_md)

        return "\n\n".join(parts)

    def _render_table(self, table: Dict[str, Any]) -> Optional[str]:
        """Render a table to Markdown format"""
        try:
            table_type = table.get("type", "")

            if table_type == "text_table":
                # Already text, just clean it up
                return self._clean_text(str(table.get("data", "")))

            if table_type in ("html_table", "financial_table"):
                headers = table.get("headers", [])
                rows = table.get("rows", [])

                if not headers and not rows:
                    return None

                # Determine column widths
                all_rows = [headers] + rows if headers else rows
                if not all_rows:
                    return None

                # Build Markdown table
                lines = []

                # Header row
                if headers:
                    header_line = "| " + " | ".join(str(h) for h in headers) + " |"
                    lines.append(header_line)

                    # Separator
                    sep_line = "| " + " | ".join("---" for _ in headers) + " |"
                    lines.append(sep_line)

                # Data rows
                for row in rows:
                    # Ensure row has same number of columns as header
                    while len(row) < len(headers):
                        row.append("")
                    row_line = "| " + " | ".join(str(cell) for cell in row[:len(headers)]) + " |"
                    lines.append(row_line)

                return "\n".join(lines)

            # Fallback for other table types
            data = table.get("data")
            if data:
                return f"```\n{data}\n```"

            return None

        except Exception as e:
            logger.debug(f"Failed to render table: {e}")
            return None

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text for Markdown"""
        if not text:
            return ""

        # Normalize whitespace
        text = re.sub(r'\r\n', '\n', text)
        text = re.sub(r'\r', '\n', text)

        # Remove excessive blank lines (more than 2)
        text = re.sub(r'\n{3,}', '\n\n', text)

        # Clean up spaces
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r' +\n', '\n', text)
        text = re.sub(r'\n +', '\n', text)

        # Remove common SEC HTML artifacts
        text = re.sub(r'&#\d+;', '', text)
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'&amp;', '&', text)
        text = re.sub(r'&lt;', '<', text)
        text = re.sub(r'&gt;', '>', text)
        text = re.sub(r'&quot;', '"', text)

        # Remove page numbers and headers/footers patterns
        text = re.sub(r'\n\d+\n', '\n', text)
        text = re.sub(r'Table of Contents', '', text, flags=re.IGNORECASE)

        # Clean up lines
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            # Skip very short lines that are likely artifacts
            if len(line) < 3 and not line.isdigit():
                if line and cleaned_lines and cleaned_lines[-1]:
                    cleaned_lines.append('')  # Keep paragraph break
                continue
            cleaned_lines.append(line)

        return '\n'.join(cleaned_lines).strip()

    def _render_footer(self, metadata: Dict[str, Any]) -> str:
        """Render document footer with source"""
        lines = ["---", ""]

        sec_url = metadata.get("sec_url")
        if sec_url:
            lines.append(f"*Source: [SEC EDGAR]({sec_url})*")
        else:
            lines.append("*Source: SEC EDGAR*")

        parsing_method = metadata.get("parsing_method", "")
        if parsing_method:
            lines.append(f"*Parsed using: {parsing_method}*")

        return "\n".join(lines)

    def serialize_minimal(
        self,
        parsed: ParsedFiling,
        metadata: Dict[str, Any],
        sections_to_include: List[str] = None,
    ) -> str:
        """
        Serialize only specific sections for focused analysis.

        Args:
            parsed: ParsedFiling from FilingParser
            metadata: Filing metadata
            sections_to_include: List of section keys to include

        Returns:
            Focused Markdown string
        """
        if sections_to_include is None:
            sections_to_include = ["mdna", "risk_factors"]

        filing_type = metadata.get("filing_type", "10-Q")
        section_order = (
            self.SECTION_ORDER_10K
            if filing_type.startswith("10-K")
            else self.SECTION_ORDER_10Q
        )

        parts = [self._render_header(metadata)]

        for section_key in sections_to_include:
            section = parsed.sections.get(section_key)
            if section:
                # Find display title
                display_title = section.title
                for key, title in section_order:
                    if key == section_key:
                        display_title = title
                        break

                section_md = self._render_section(section, display_title)
                if section_md:
                    parts.append(section_md)

        parts.append(self._render_footer(metadata))

        return "\n\n".join(filter(None, parts))


# Singleton instance
markdown_serializer = MarkdownSerializer()
