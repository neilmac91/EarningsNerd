"""
Test suite for summary quality gates and content validation.

Per execution plan: These tests verify:
1. Subjective language detection (forbidden words)
2. Coverage quality gate (minimum 3/7 sections)
3. Full/partial result designation
4. Executive Summary completeness requirements
"""
import re
from typing import List

from app.services.summary_generation_service import (
    calculate_section_coverage,
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

        # Check for forbidden words
        all_text = " ".join([
            summary.get("business_overview", ""),
            summary.get("management_discussion", ""),
            summary.get("key_changes", ""),
        ])
        found = check_for_subjective_language(all_text)
        assert len(found) == 0, f"Found forbidden words: {found}"

    def test_subjective_summary_detected(self):
        """A summary with subjective language should be flagged."""
        text = "The company showed strong performance with impressive revenue growth."

        found = check_for_subjective_language(text)
        assert len(found) > 0
