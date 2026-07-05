"""LLM JSON repair for ``OpenAIService`` (roadmap S2 façade split).

``_JsonRepairMixin`` carries the two-tier repair (json-repair library → regex fallback) used to
salvage malformed model JSON. Provided as a mixin (not module functions) because the methods are
part of ``OpenAIService``'s tested surface and resolve through ``self``. Extracted verbatim.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

# Import json_repair for robust LLM JSON handling
try:
    from json_repair import repair_json as json_repair_lib
    HAS_JSON_REPAIR = True
except ImportError:
    HAS_JSON_REPAIR = False
    json_repair_lib = None

logger = logging.getLogger(__name__)


class _JsonRepairMixin:
    """JSON-payload cleaning + repair, mixed into ``OpenAIService``."""

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
