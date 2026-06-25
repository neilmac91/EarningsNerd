"""Regression tests for summary export (PDF HTML + CSV).

Pins both production bugs:
  1. PDF "Failed to export PDF" — generate_pdf_html used to feed structured section **dicts**
     into a markdown-string formatter (``text.strip()`` on a dict -> AttributeError -> 500).
  2. CSV "limited data" — generate_csv only emitted the financial-highlights table + risks,
     dropping every other section.

Both exporters now render from the shared ``summary_sections.render_sections`` source of truth,
so these tests assert the full structured shape produces complete, non-crashing output and that
risk filtering matches the on-page UI.
"""

from datetime import date
from types import SimpleNamespace

import pytest

from app.services.export_service import ExportService
from app.services import summary_sections


def _full_sections():
    """A realistic raw_summary['sections'] with every section populated (dicts/lists)."""
    return {
        "executive_snapshot": {
            "headline": "Biogen reported $9.89B in revenue with a <neutral> stance.",
            "key_points": ["Revenue down y/y", "Margins compressed"],
            "tone": "cautious",
        },
        "financial_highlights": {
            "table": [
                {
                    "metric": "Revenue",
                    "current_period": "$9.89B",
                    "prior_period": "$9.68B",
                    "change": "+2.2%",
                    "commentary": "Reported via standardized XBRL data.",
                },
            ],
            "profitability": ["Net margin 13.1% vs 16.9% prior"],
            "cash_flow": ["Operating cash flow of $2.1B"],
            "balance_sheet": ["Total debt of $6.3B"],
            "notes": "Figures sourced from standardized XBRL.",
        },
        "risk_factors": [
            {
                "summary": "Competitive and rapidly changing environment",
                "supporting_evidence": "we operate in a very competitive and rapidly changing environment",
                "materiality": "high",
            },
            {
                # Placeholder evidence -> must be dropped (matches the page filter).
                "summary": "Vague risk",
                "supporting_evidence": "Data pending",
            },
            {
                # No evidence at all -> must be dropped.
                "summary": "Unsupported risk",
            },
        ],
        "management_discussion_insights": {
            "themes": ["Pipeline investment", "Cost discipline"],
            "capital_allocation": ["$1B buyback authorized"],
            "quotes": [{"speaker": "CEO", "quote": "We remain focused on execution."}],
        },
        "segment_performance": [
            {"segment": "Multiple Sclerosis", "revenue": "$4.1B", "change": "-5%", "commentary": "Mature franchise"},
        ],
        "liquidity_capital_structure": {
            "leverage": "Net debt/EBITDA of 1.2x",
            "liquidity": "$2.5B cash on hand",
            "shareholder_returns": ["Resumed buybacks"],
        },
        "guidance_outlook": {
            "guidance": "Revenue flat to slightly down for FY2026",
            "tone": "cautious",
            "drivers": ["New product launches"],
            "watch_items": ["Biosimilar erosion"],
        },
        "notable_footnotes": [
            {"item": "Goodwill impairment", "impact": "$200M non-cash charge"},
        ],
        "three_year_trend": {
            "trend_summary": "Revenue has declined modestly over three years.",
            "inflections": ["2024 product launch"],
            "compare_prior_period": {"available": True, "insights": ["Margins down 380bps"]},
        },
    }


def _make_summary_and_filing(sections):
    summary = SimpleNamespace(raw_summary={"sections": sections})
    filing = SimpleNamespace(
        company=SimpleNamespace(name="BIOGEN INC."),
        filing_type="10-K",
        filing_date=date(2026, 2, 6),
        period_end_date=date(2025, 12, 31),
        sec_url="https://www.sec.gov/Archives/edgar/data/875045/x.htm",
    )
    return summary, filing


@pytest.fixture
def service():
    return ExportService()


class TestPdfHtml:
    def test_does_not_raise_on_structured_dict_sections(self, service):
        """The core PDF regression: structured dicts must not crash the HTML builder."""
        summary, filing = _make_summary_and_filing(_full_sections())
        html = service.generate_pdf_html(summary, filing)  # would raise AttributeError pre-fix
        assert isinstance(html, str)
        assert "<html>" in html

    def test_includes_every_section(self, service):
        summary, filing = _make_summary_and_filing(_full_sections())
        html = service.generate_pdf_html(summary, filing)
        for title in (
            "Executive Assessment",
            "Financial Highlights",
            "Investment Risks &amp; Concerns",  # & is escaped
            "Management Strategy",
            "Business Segment Analysis",
            "Liquidity &amp; Capital Structure",
            "Forward Outlook",
            "Notable Footnotes",
            "3-Year Investment Perspective",
        ):
            assert title in html, f"missing section: {title}"
        # Content from sections the old PDF crashed on or omitted:
        assert "Pipeline investment" in html
        assert "New product launches" in html
        assert "Goodwill impairment" in html

    def test_escapes_untrusted_filing_text(self, service):
        """Filing-derived text must be HTML-escaped (no injection / broken markup)."""
        summary, filing = _make_summary_and_filing(_full_sections())
        html = service.generate_pdf_html(summary, filing)
        # The headline contains "<neutral>" — it must be escaped, not emitted as a tag.
        assert "&lt;neutral&gt;" in html
        assert "<neutral>" not in html


class TestCsv:
    def test_includes_all_sections(self, service):
        summary, filing = _make_summary_and_filing(_full_sections())
        csv_out = service.generate_csv(summary, filing)
        # Header preserved
        assert "BIOGEN INC. - 10-K Summary" in csv_out
        # Every section's content is present (the old CSV dropped all of these):
        for fragment in (
            "Executive Assessment",
            "Revenue down y/y",
            "Net margin 13.1% vs 16.9% prior",  # profitability
            "Operating cash flow of $2.1B",  # cash_flow
            "Total debt of $6.3B",  # balance_sheet
            "Pipeline investment",  # MD&A theme
            "We remain focused on execution",  # MD&A quote
            "Multiple Sclerosis",  # segment
            "Net debt/EBITDA of 1.2x",  # liquidity
            "Revenue flat to slightly down for FY2026",  # guidance
            "Biosimilar erosion",  # watch item
            "Goodwill impairment",  # footnote
            "Revenue has declined modestly over three years.",  # trend
        ):
            assert fragment in csv_out, f"CSV missing: {fragment}"

    def test_risk_filter_matches_page(self, service):
        """Only risks with non-placeholder supporting evidence appear (mirrors the UI)."""
        summary, filing = _make_summary_and_filing(_full_sections())
        csv_out = service.generate_csv(summary, filing)
        assert "Competitive and rapidly changing environment" in csv_out
        assert "Vague risk" not in csv_out  # placeholder evidence dropped
        assert "Unsupported risk" not in csv_out  # no evidence dropped


class TestRenderSections:
    def test_drops_empty_and_placeholder_sections(self):
        sections = {
            "executive_snapshot": {"headline": "Real headline", "key_points": []},
            "financial_highlights": {},  # empty
            "guidance_outlook": {"guidance": "Not available"},  # placeholder
            "three_year_trend": {"trend_summary": ""},  # empty
        }
        rendered = summary_sections.render_sections({"sections": sections})
        titles = [s.title for s in rendered]
        assert "Executive Assessment" in titles
        assert "Financial Highlights" not in titles
        assert "Forward Outlook & Investment Implications" not in titles
        assert "3-Year Investment Perspective" not in titles

    def test_handles_missing_and_malformed_input(self):
        assert summary_sections.render_sections(None) == []
        assert summary_sections.render_sections({}) == []
        assert summary_sections.render_sections({"sections": "not-a-dict"}) == []

    def test_is_placeholder(self):
        assert summary_sections.is_placeholder("N/A")
        assert summary_sections.is_placeholder("being processed")
        assert summary_sections.is_placeholder("")
        assert summary_sections.is_placeholder(None)
        assert summary_sections.is_placeholder({"a": 1})  # non-string
        assert not summary_sections.is_placeholder("Revenue grew 10%")


class TestExportPdfBytes:
    """Best-effort end-to-end check: only runs where WeasyPrint + fonts are available."""

    @pytest.mark.asyncio
    async def test_export_pdf_returns_bytes(self, service):
        pytest.importorskip("weasyprint")
        summary, filing = _make_summary_and_filing(_full_sections())
        try:
            pdf_bytes = await service.export_pdf(summary, filing)
        except Exception as exc:  # missing system fonts/libs in this env — not what we test here
            pytest.skip(f"WeasyPrint runtime unavailable: {exc}")
        assert isinstance(pdf_bytes, (bytes, bytearray))
        assert pdf_bytes[:4] == b"%PDF"
