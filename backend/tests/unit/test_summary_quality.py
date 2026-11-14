"""
Test suite for the summary section-coverage quality gate (minimum 3/7 sections) and its constants.
"""
from app.services.summary_generation_service import (
    calculate_section_coverage,
    MINIMUM_SECTIONS_FOR_FULL_RESULT,
    HIDEABLE_SECTIONS,
)


class TestCoverageQualityGate:
    """Test section coverage calculation and quality gate."""

    def test_full_coverage(self):
        """All sections populated should return full coverage."""
        # NOTE: Content must be >20 chars and not contain placeholder patterns
        summary_data = {
            "business_overview": "Apple Inc. designs, manufactures, and markets smartphones, personal computers, tablets, and accessories worldwide.",
            "financial_highlights": {"revenue": 94000000000, "notes": "Revenue increased 15% YoY driven by strong Services growth."},
            "risk_factors": [{"title": "Competition", "summary": "The markets for the Company products are highly competitive with many well-established players."}],
            "management_discussion": "Management's discussion and analysis of financial condition and results of operations for Q4 2024.",
            "key_changes": "Year-over-year changes include higher R&D investment and expanded manufacturing capacity in Asia.",
            "forward_guidance": "Management expects revenue growth of 10-15% in the next fiscal year based on current demand trends.",
            "additional_disclosures": "Other disclosures include related party transactions and subsequent events affecting the financial statements.",
        }

        covered, total, covered_sections, missing = calculate_section_coverage(summary_data)
        assert covered == 7
        assert total == 7
        assert len(missing) == 0

    def test_minimum_coverage_met(self):
        """Minimum coverage (3/7) should be detected."""
        # NOTE: Content must be >20 chars and not contain placeholder patterns
        summary_data = {
            "business_overview": "Company overview for fiscal year 2024 including detailed analysis of market position and competitive landscape.",
            "financial_highlights": {"revenue": 94000000000, "notes": "Revenue growth accelerated in Q4."},
            "risk_factors": [{"title": "Risk 1", "summary": "Supply chain constraints may impact production capacity in upcoming quarters."}],
            "management_discussion": None,
            "key_changes": None,
            "forward_guidance": None,
            "additional_disclosures": None,
        }

        covered, total, _, _ = calculate_section_coverage(summary_data)
        assert covered == 3
        assert covered >= MINIMUM_SECTIONS_FOR_FULL_RESULT

    def test_below_minimum_coverage(self):
        """Below minimum coverage should be detected."""
        # NOTE: Content must be >20 chars and not contain placeholder patterns
        summary_data = {
            "business_overview": "Apple Inc. is a technology company that designs and manufactures consumer electronics and software.",
            "financial_highlights": None,
            "risk_factors": None,
            "management_discussion": None,
            "key_changes": None,
            "forward_guidance": None,
            "additional_disclosures": None,
        }

        covered, total, _, _ = calculate_section_coverage(summary_data)
        assert covered == 1
        assert covered < MINIMUM_SECTIONS_FOR_FULL_RESULT

    def test_empty_string_not_counted(self):
        """Empty strings should not count as coverage."""
        summary_data = {
            "business_overview": "",
            "financial_highlights": {},
            "risk_factors": [],
            "management_discussion": "   ",  # Whitespace only
            "key_changes": None,
            "forward_guidance": None,
            "additional_disclosures": None,
        }

        covered, total, _, _ = calculate_section_coverage(summary_data)
        assert covered == 0

    def test_missing_sections_identified(self):
        """Missing sections should be correctly identified."""
        # NOTE: Content must be >20 chars and not contain placeholder patterns
        summary_data = {
            "business_overview": "Apple Inc. is a technology company that designs, manufactures, and markets consumer electronics worldwide.",
            "financial_highlights": {"data": "exists", "notes": "Financial data for the fiscal year ending September 2024."},
            "risk_factors": None,
            "management_discussion": None,
            "key_changes": None,
            "forward_guidance": None,
            "additional_disclosures": None,
        }

        _, _, _, missing = calculate_section_coverage(summary_data)
        assert "risk_factors" in missing
        assert "management_discussion" in missing
        assert "business_overview" not in missing


class TestMinimumSectionsConstant:
    """Test the minimum sections constant."""

    def test_minimum_is_three(self):
        """Per execution plan, minimum is 3/7 sections."""
        assert MINIMUM_SECTIONS_FOR_FULL_RESULT == 3

    def test_hideable_sections_count(self):
        """Should have 7 hideable sections."""
        assert len(HIDEABLE_SECTIONS) == 7


class TestSummaryQualityIntegration:
    """Integration tests for summary quality validation."""

    def test_full_quality_summary(self):
        """A high-quality summary should pass all checks."""
        summary = {
            "business_overview": "Apple Inc. designs, manufactures, and markets smartphones, personal computers, tablets, wearables, and accessories worldwide.",
            "financial_highlights": {
                "revenue": {"current": {"value": 94000000000}},
                "net_income": {"current": {"value": 20000000000}},
            },
            "risk_factors": [
                {
                    "title": "Competition",
                    "summary": "The markets for the Company's products are competitive.",
                }
            ],
            "management_discussion": "Revenue increased 12% compared to the prior year.",
            "key_changes": "Operating expenses increased $2.1B.",
            "forward_guidance": None,  # Acceptable to be missing
            "additional_disclosures": None,  # Acceptable to be missing
        }

        # Check coverage
        covered, total, _, _ = calculate_section_coverage(summary)
        assert covered >= 3
