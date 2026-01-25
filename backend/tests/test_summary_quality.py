"""
Test suite for summary quality gates and content validation.

Per execution plan: These tests verify:
1. Subjective language detection (forbidden words)
2. Coverage quality gate (minimum 3/7 sections)
3. Full/partial result designation
4. Executive Summary completeness requirements
"""
import pytest
import re
from typing import Dict, Any, List

from app.services.summary_generation_service import (
    calculate_section_coverage,
    determine_result_type,
    generate_unavailable_sections_notes,
    MINIMUM_SECTIONS_FOR_FULL_RESULT,
    HIDEABLE_SECTIONS,
)


# Forbidden words list - must match the execution plan
FORBIDDEN_WORDS = [
    # Subjective adjectives
    "strong", "weak", "impressive", "disappointing", "concerning",
    "excellent", "poor", "significant", "major", "critical",
    "robust", "solid", "healthy", "troubled", "struggling",
    # Investment language
    "bullish", "bearish", "optimistic", "pessimistic",
    "buy", "sell", "hold", "recommend", "undervalued", "overvalued",
    # Predictive language
    "likely", "probably", "expected to", "poised to", "set to",
    "will likely", "should see", "on track to",
]


def check_for_subjective_language(text: str) -> List[str]:
    """Return list of forbidden words found in text (excluding attributed quotes).

    Per execution plan: Forbidden words are allowed when directly quoted
    from the company's filing with explicit attribution.
    """
    if not text:
        return []

    text_lower = text.lower()
    found = []

    for word in FORBIDDEN_WORDS:
        # Match whole words only (not parts of other words)
        pattern = rf'\b{re.escape(word)}\b'
        matches = list(re.finditer(pattern, text_lower))

        for match in matches:
            # Check if this is within an attributed quote
            # Look for patterns like: "Management described X as 'word'"
            # or "The company stated 'word'"
            start_pos = max(0, match.start() - 100)
            context = text_lower[start_pos:match.end()]

            # Check for attribution patterns
            attribution_patterns = [
                r'management\s+(described|characterized|stated|said)',
                r'the company\s+(described|characterized|stated|said)',
                r'per\s+(the|item|section)',
                r'according\s+to',
                r"['\"'].*?" + re.escape(word),  # Word inside quotes
            ]

            is_attributed = any(
                re.search(pattern, context)
                for pattern in attribution_patterns
            )

            if not is_attributed:
                found.append(word)
                break  # Only count each word once

    return list(set(found))


class TestForbiddenWordsDetection:
    """Test subjective language detection."""

    def test_detects_subjective_adjectives(self):
        """Should detect subjective adjectives."""
        text = "The company showed strong revenue growth this quarter."
        found = check_for_subjective_language(text)
        assert "strong" in found

    def test_detects_investment_language(self):
        """Should detect investment-related language."""
        text = "The outlook appears bullish for next quarter."
        found = check_for_subjective_language(text)
        assert "bullish" in found

    def test_detects_predictive_language(self):
        """Should detect predictive language."""
        text = "The company is likely to exceed expectations."
        found = check_for_subjective_language(text)
        assert "likely" in found

    def test_allows_attributed_quotes(self):
        """Should allow forbidden words when properly attributed."""
        text = "Management characterized Q4 performance as 'strong' in their MD&A discussion."
        found = check_for_subjective_language(text)
        # "strong" should NOT be flagged because it's attributed to management
        assert "strong" not in found

    def test_allows_company_quotes(self):
        """Should allow forbidden words when quoting company."""
        text = "The company stated that demand remained 'robust' according to Item 7."
        found = check_for_subjective_language(text)
        assert "robust" not in found

    def test_detects_unattributed_words(self):
        """Should detect forbidden words without attribution."""
        text = "Revenue growth was impressive and margins were solid."
        found = check_for_subjective_language(text)
        assert "impressive" in found
        assert "solid" in found

    def test_empty_text_returns_empty(self):
        """Empty text should return no forbidden words."""
        found = check_for_subjective_language("")
        assert found == []

    def test_neutral_text_returns_empty(self):
        """Neutral, objective text should return no forbidden words."""
        text = "Revenue increased 15% YoY to $94.3B. Net income was $20.1B."
        found = check_for_subjective_language(text)
        assert found == []

    def test_detects_multiple_violations(self):
        """Should detect multiple different forbidden words."""
        text = "Strong growth, impressive margins, and a bullish outlook."
        found = check_for_subjective_language(text)
        assert len(found) >= 3


class TestCoverageQualityGate:
    """Test section coverage calculation and quality gate."""

    def test_full_coverage(self):
        """All sections populated should return full coverage."""
        summary_data = {
            "business_overview": "Apple Inc. designs and manufactures...",
            "financial_highlights": {"revenue": 94000000000},
            "risk_factors": [{"title": "Competition", "summary": "..."}],
            "management_discussion": "Management's discussion...",
            "key_changes": "Year-over-year changes...",
            "forward_guidance": "Management expects...",
            "additional_disclosures": "Other disclosures...",
        }

        covered, total, covered_sections, missing = calculate_section_coverage(summary_data)
        assert covered == 7
        assert total == 7
        assert len(missing) == 0

    def test_minimum_coverage_met(self):
        """Minimum coverage (3/7) should be detected."""
        summary_data = {
            "business_overview": "Company overview...",
            "financial_highlights": {"revenue": 94000000000},
            "risk_factors": [{"title": "Risk 1"}],
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
        summary_data = {
            "business_overview": "Overview...",
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
        summary_data = {
            "business_overview": "Overview...",
            "financial_highlights": {"data": "exists"},
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


class TestResultTypeDesignation:
    """Test full/partial result designation."""

    def test_full_result_with_good_coverage(self):
        """Should return 'full' for adequate coverage without errors."""
        summary_data = {
            "business_overview": "Overview...",
            "financial_highlights": {"revenue": 100},
            "risk_factors": [{"risk": "data"}],
            "management_discussion": "MD&A...",
            "key_changes": None,
            "forward_guidance": None,
            "additional_disclosures": None,
        }

        result_type, reason = determine_result_type(summary_data, had_errors=False)
        assert result_type == "full"
        assert reason is None

    def test_partial_result_insufficient_coverage(self):
        """Should return 'partial' for insufficient coverage."""
        summary_data = {
            "business_overview": "Overview...",
            "financial_highlights": None,
            "risk_factors": None,
            "management_discussion": None,
            "key_changes": None,
            "forward_guidance": None,
            "additional_disclosures": None,
        }

        result_type, reason = determine_result_type(summary_data, had_errors=False)
        assert result_type == "partial"
        assert "insufficient_coverage" in reason

    def test_partial_result_with_errors(self):
        """Should return 'partial' when errors occurred."""
        summary_data = {
            "business_overview": "Overview...",
            "financial_highlights": {"revenue": 100},
            "risk_factors": [{"risk": "data"}],
            "management_discussion": "MD&A...",
            "key_changes": "Changes...",
            "forward_guidance": "Guidance...",
            "additional_disclosures": "Disclosures...",
        }

        result_type, reason = determine_result_type(summary_data, had_errors=True)
        assert result_type == "partial"
        assert reason == "api_error"

    def test_partial_result_with_timeout(self):
        """Should return 'partial' when timeout occurred."""
        summary_data = {
            "business_overview": "Overview...",
            "financial_highlights": {"revenue": 100},
            "risk_factors": [{"risk": "data"}],
            "management_discussion": None,
            "key_changes": None,
            "forward_guidance": None,
            "additional_disclosures": None,
        }

        result_type, reason = determine_result_type(summary_data, had_timeout=True)
        assert result_type == "partial"
        assert reason == "timeout"


class TestUnavailableSectionsNotes:
    """Test generation of unavailable sections notes."""

    def test_generates_notes_for_missing_sections(self):
        """Should generate appropriate notes for missing sections."""
        missing = ["forward_guidance", "key_changes"]

        notes = generate_unavailable_sections_notes(missing)

        assert len(notes) == 2
        assert any(n["section"] == "forward_guidance" for n in notes)
        assert any(n["section"] == "key_changes" for n in notes)

    def test_notes_have_correct_structure(self):
        """Notes should have section and note fields."""
        missing = ["risk_factors"]

        notes = generate_unavailable_sections_notes(missing)

        assert len(notes) == 1
        assert "section" in notes[0]
        assert "note" in notes[0]
        assert notes[0]["section"] == "risk_factors"
        assert "Risk factors" in notes[0]["note"]

    def test_empty_missing_returns_empty(self):
        """Empty missing list should return empty notes."""
        notes = generate_unavailable_sections_notes([])
        assert notes == []

    def test_all_sections_have_notes(self):
        """All hideable sections should have predefined notes."""
        notes = generate_unavailable_sections_notes(HIDEABLE_SECTIONS)

        assert len(notes) == len(HIDEABLE_SECTIONS)
        for note in notes:
            assert note["note"]  # Should have non-empty note


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

        # Check result type
        result_type, _ = determine_result_type(summary)
        assert result_type == "full"

        # Check for forbidden words
        all_text = " ".join([
            summary.get("business_overview", ""),
            summary.get("management_discussion", ""),
            summary.get("key_changes", ""),
        ])
        found = check_for_subjective_language(all_text)
        assert len(found) == 0, f"Found forbidden words: {found}"

    def test_low_quality_summary_detected(self):
        """A low-quality summary should be flagged as partial."""
        summary = {
            "business_overview": None,
            "financial_highlights": None,
            "risk_factors": None,
            "management_discussion": "Some text.",
            "key_changes": None,
            "forward_guidance": None,
            "additional_disclosures": None,
        }

        result_type, reason = determine_result_type(summary)
        assert result_type == "partial"

    def test_subjective_summary_detected(self):
        """A summary with subjective language should be flagged."""
        text = "The company showed strong performance with impressive revenue growth."

        found = check_for_subjective_language(text)
        assert len(found) > 0
