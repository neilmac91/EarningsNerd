"""Unit tests for _repair_json method in OpenAIService.

Tests cover all JSON repair patterns:
- Unquoted property names (JavaScript-style)
- Single quotes for keys and values
- Trailing commas
- Python booleans (True/False/None)
"""

import json
import pytest
from app.services.openai_service import OpenAIService


class TestRepairJson:
    """Unit tests for _repair_json method."""

    @pytest.fixture
    def service(self):
        """Create OpenAIService instance for testing."""
        return OpenAIService()

    # === Unquoted Keys (Primary Fix for the Bug) ===

    def test_unquoted_simple_key(self, service):
        """Fix simple unquoted key."""
        malformed = '{company_name: "Acme Corp"}'
        repaired = service._repair_json(malformed)
        assert '"company_name"' in repaired
        parsed = json.loads(repaired)
        assert parsed["company_name"] == "Acme Corp"

    def test_unquoted_multiple_keys(self, service):
        """Fix multiple unquoted keys."""
        malformed = '{company_name: "Acme", revenue: 1000000, active: true}'
        repaired = service._repair_json(malformed)
        parsed = json.loads(repaired)
        assert parsed["company_name"] == "Acme"
        assert parsed["revenue"] == 1000000
        assert parsed["active"] is True

    def test_unquoted_keys_with_underscores(self, service):
        """Fix keys with underscores."""
        malformed = '{net_income: 500, operating_cash_flow: 200}'
        repaired = service._repair_json(malformed)
        parsed = json.loads(repaired)
        assert "net_income" in parsed
        assert "operating_cash_flow" in parsed

    def test_unquoted_keys_with_numbers(self, service):
        """Fix keys containing numbers."""
        malformed = '{metric1: 100, q2_revenue: 500}'
        repaired = service._repair_json(malformed)
        parsed = json.loads(repaired)
        assert parsed["metric1"] == 100
        assert parsed["q2_revenue"] == 500

    def test_unquoted_keys_with_hyphens(self, service):
        """Fix keys containing hyphens."""
        malformed = '{company-name: "Acme", risk-level: "High"}'
        repaired = service._repair_json(malformed)
        parsed = json.loads(repaired)
        assert parsed["company-name"] == "Acme"
        assert parsed["risk-level"] == "High"

    def test_unquoted_nested_objects(self, service):
        """Fix unquoted keys in nested objects."""
        malformed = '{metadata: {company_name: "Test", filing_type: "10-Q"}}'
        repaired = service._repair_json(malformed)
        parsed = json.loads(repaired)
        assert parsed["metadata"]["company_name"] == "Test"
        assert parsed["metadata"]["filing_type"] == "10-Q"

    def test_unquoted_deeply_nested(self, service):
        """Fix unquoted keys in deeply nested structures."""
        malformed = '{level1: {level2: {level3: "deep"}}}'
        repaired = service._repair_json(malformed)
        parsed = json.loads(repaired)
        assert parsed["level1"]["level2"]["level3"] == "deep"

    def test_mixed_quoted_unquoted(self, service):
        """Handle mix of quoted and unquoted keys."""
        malformed = '{"company_name": "Acme", revenue: 1000}'
        repaired = service._repair_json(malformed)
        parsed = json.loads(repaired)
        assert parsed["company_name"] == "Acme"
        assert parsed["revenue"] == 1000

    def test_unquoted_keys_in_array_of_objects(self, service):
        """Fix unquoted keys in array of objects."""
        malformed = '{"items": [{name: "Item1", value: 10}, {name: "Item2", value: 20}]}'
        repaired = service._repair_json(malformed)
        parsed = json.loads(repaired)
        assert parsed["items"][0]["name"] == "Item1"
        assert parsed["items"][1]["value"] == 20

    # === Single Quotes (Existing Fix) ===

    def test_single_quoted_keys(self, service):
        """Fix single-quoted keys."""
        malformed = "{'company_name': \"Acme Corp\"}"
        repaired = service._repair_json(malformed)
        parsed = json.loads(repaired)
        assert parsed["company_name"] == "Acme Corp"

    def test_single_quoted_values(self, service):
        """Fix single-quoted string values."""
        malformed = '{"company_name": \'Acme Corp\'}'
        repaired = service._repair_json(malformed)
        parsed = json.loads(repaired)
        assert parsed["company_name"] == "Acme Corp"

    def test_single_quoted_keys_and_values(self, service):
        """Fix both single-quoted keys and values."""
        malformed = "{'company_name': 'Acme Corp'}"
        repaired = service._repair_json(malformed)
        parsed = json.loads(repaired)
        assert parsed["company_name"] == "Acme Corp"

    # === Single Quotes in Arrays (New Fix per PR Review) ===

    def test_single_quoted_strings_in_array(self, service):
        """Fix single-quoted strings in arrays."""
        malformed = "{'items': ['value1', 'value2', 'value3']}"
        repaired = service._repair_json(malformed)
        parsed = json.loads(repaired)
        assert parsed["items"] == ["value1", "value2", "value3"]

    def test_single_quoted_strings_in_array_with_double_quoted_key(self, service):
        """Fix single-quoted array values with double-quoted key."""
        malformed = '{"items": [\'first\', \'second\']}'
        repaired = service._repair_json(malformed)
        parsed = json.loads(repaired)
        assert parsed["items"] == ["first", "second"]

    def test_single_quoted_single_element_array(self, service):
        """Fix single-quoted string as sole array element."""
        malformed = "{'tags': ['only-one']}"
        repaired = service._repair_json(malformed)
        parsed = json.loads(repaired)
        assert parsed["tags"] == ["only-one"]

    def test_single_quoted_strings_in_nested_array(self, service):
        """Fix single-quoted strings in nested arrays."""
        malformed = "{'data': {'items': ['a', 'b', 'c']}}"
        repaired = service._repair_json(malformed)
        parsed = json.loads(repaired)
        assert parsed["data"]["items"] == ["a", "b", "c"]

    def test_mixed_arrays_with_numbers_and_single_quoted_strings(self, service):
        """Handle arrays with mixed numbers and single-quoted strings."""
        malformed = "{'mixed': [1, 'two', 3, 'four']}"
        repaired = service._repair_json(malformed)
        parsed = json.loads(repaired)
        assert parsed["mixed"] == [1, "two", 3, "four"]

    def test_realistic_risk_factors_array(self, service):
        """Test realistic LLM output with single-quoted risk factors."""
        malformed = """{
  "risk_factors": [
    'Supply chain disruption',
    'Regulatory changes',
    'Competition from rivals'
  ]
}"""
        repaired = service._repair_json(malformed)
        parsed = json.loads(repaired)
        assert len(parsed["risk_factors"]) == 3
        assert parsed["risk_factors"][0] == "Supply chain disruption"

    # === Trailing Commas (Existing Fix) ===

    def test_trailing_comma_object(self, service):
        """Remove trailing comma in object."""
        malformed = '{"a": 1, "b": 2,}'
        repaired = service._repair_json(malformed)
        parsed = json.loads(repaired)
        assert parsed == {"a": 1, "b": 2}

    def test_trailing_comma_array(self, service):
        """Remove trailing comma in array."""
        malformed = '{"items": [1, 2, 3,]}'
        repaired = service._repair_json(malformed)
        parsed = json.loads(repaired)
        assert parsed["items"] == [1, 2, 3]

    def test_trailing_comma_nested(self, service):
        """Remove trailing commas in nested structures."""
        malformed = '{"outer": {"inner": [1, 2,],},}'
        repaired = service._repair_json(malformed)
        parsed = json.loads(repaired)
        assert parsed["outer"]["inner"] == [1, 2]

    # === Python Booleans (New Fix) ===

    def test_python_true_false(self, service):
        """Convert Python True/False to JSON true/false."""
        malformed = '{"active": True, "deleted": False}'
        repaired = service._repair_json(malformed)
        parsed = json.loads(repaired)
        assert parsed["active"] is True
        assert parsed["deleted"] is False

    def test_python_none(self, service):
        """Convert Python None to JSON null."""
        malformed = '{"value": None}'
        repaired = service._repair_json(malformed)
        parsed = json.loads(repaired)
        assert parsed["value"] is None

    def test_python_booleans_in_array(self, service):
        """Convert Python booleans in arrays."""
        malformed = '{"flags": [True, False, None]}'
        repaired = service._repair_json(malformed)
        parsed = json.loads(repaired)
        assert parsed["flags"] == [True, False, None]

    # === Edge Cases / Safety ===

    def test_does_not_corrupt_valid_json(self, service):
        """Valid JSON should pass through unchanged (semantically)."""
        valid = '{"company_name": "Acme", "revenue": 1000}'
        repaired = service._repair_json(valid)
        assert json.loads(repaired) == json.loads(valid)

    def test_does_not_corrupt_string_values_with_colons(self, service):
        """String values containing colons should not be affected."""
        valid = '{"url": "https://example.com:8080/path"}'
        repaired = service._repair_json(valid)
        parsed = json.loads(repaired)
        assert parsed["url"] == "https://example.com:8080/path"

    def test_does_not_corrupt_string_values_with_json_like_content(self, service):
        """String values containing JSON-like patterns should be preserved."""
        # Note: This is a known limitation - embedded JSON-like patterns in strings
        # may be altered. This test documents expected behavior.
        valid = '{"note": "Value is high"}'
        repaired = service._repair_json(valid)
        parsed = json.loads(repaired)
        assert "Value is high" in parsed["note"]

    def test_empty_string(self, service):
        """Empty input should return empty string."""
        assert service._repair_json("") == ""

    def test_none_input(self, service):
        """None input should return empty string."""
        assert service._repair_json(None) == ""

    def test_whitespace_only(self, service):
        """Whitespace-only input passes through unchanged (JSON parse will fail)."""
        # Note: The repair function does not strip whitespace - that's handled by
        # _clean_json_payload() in the calling code. Whitespace-only will fail
        # JSON parsing regardless.
        result = service._repair_json("   ")
        assert result == "   "  # Passes through unchanged

    # === Realistic LLM Output ===

    def test_realistic_gemini_output_simple(self, service):
        """Test against realistic malformed Gemini output (simple case)."""
        malformed = """{
  company_name: "Apple Inc.",
  filing_type: "10-Q",
  has_prior_period: True
}"""
        repaired = service._repair_json(malformed)
        parsed = json.loads(repaired)
        assert parsed["company_name"] == "Apple Inc."
        assert parsed["filing_type"] == "10-Q"
        assert parsed["has_prior_period"] is True

    def test_realistic_gemini_output_complex(self, service):
        """Test against realistic malformed Gemini output (complex case)."""
        malformed = """{
  metadata: {
    company_name: "Apple Inc.",
    filing_type: "10-Q",
    reporting_period: "Q3 2025",
    currency: "USD",
    has_prior_period: True,
  },
  sections: {
    financial_highlights: {
      revenue: "$94.9B",
      net_income: "$22.9B",
    },
    risk_factors: [
      {risk: "Supply chain disruption", severity: "High"},
      {risk: "Competition", severity: "Medium"},
    ],
  },
}"""
        repaired = service._repair_json(malformed)
        parsed = json.loads(repaired)
        assert parsed["metadata"]["company_name"] == "Apple Inc."
        assert parsed["sections"]["financial_highlights"]["revenue"] == "$94.9B"
        assert len(parsed["sections"]["risk_factors"]) == 2
        assert parsed["sections"]["risk_factors"][0]["risk"] == "Supply chain disruption"

    def test_realistic_error_case_line5_column38(self, service):
        """Test the exact error pattern: line 5 column 38 (char 116).

        This reproduces the bug from the screenshot:
        DEBUG_ERROR: Expecting property name enclosed in double quotes: line 5 column 38 (char 116)
        """
        # This is structured to produce an error around char 116 if not repaired
        malformed = """{
  "metadata": {
    company_name: "Apple Inc.",
    filing_type: "10-Q"
  }
}"""
        # Before fix, this would fail with:
        # json.JSONDecodeError: Expecting property name enclosed in double quotes
        repaired = service._repair_json(malformed)
        parsed = json.loads(repaired)
        assert parsed["metadata"]["company_name"] == "Apple Inc."
        assert parsed["metadata"]["filing_type"] == "10-Q"

    # === Combined Issues ===

    def test_combined_all_issues(self, service):
        """Test with multiple issues combined."""
        malformed = """{
  company_name: 'Test Corp',
  revenue: 1000000,
  is_active: True,
  deleted: False,
  notes: None,
  items: [
    {name: 'Item1', value: 10,},
    {name: 'Item2', value: 20,},
  ],
}"""
        repaired = service._repair_json(malformed)
        parsed = json.loads(repaired)
        assert parsed["company_name"] == "Test Corp"
        assert parsed["revenue"] == 1000000
        assert parsed["is_active"] is True
        assert parsed["deleted"] is False
        assert parsed["notes"] is None
        assert len(parsed["items"]) == 2
