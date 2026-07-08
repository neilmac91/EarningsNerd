"""Empty-section detection + LLM recovery for OpenAIService (roadmap S2 façade split).

``_SectionRecoveryMixin`` is the LLM re-ask path: find sections the primary completion left empty
(``_section_is_empty`` / ``_find_empty_sections``), build a focused context + schema snippet for
each (``_build_section_context`` / ``_get_section_schema_snippet``), and re-request just those
sections with a bounded secondary completion (``_run_secondary_completion`` /
``_recover_single_section`` / ``_recover_missing_sections``). The model client is reached through
``self`` (instance attribute), so no settings/prompt-loader imports are needed here. Mixed into
``OpenAIService``; methods resolve through ``self``. Extracted verbatim.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from app.services.ai.normalize import _normalize_simple_string

logger = logging.getLogger(__name__)


class _SectionRecoveryMixin:
    """Empty-section detection + bounded LLM recovery, mixed into OpenAIService."""

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

        Note — the ONE HOME PER NUMBER rule (the main ``generate_structured_summary`` Rules block)
        intentionally does NOT reach this path. Recovery is section-scoped: the prompt below sees
        only the target section's schema and its own excerpt, with no view of what the other
        sections already state, so it structurally cannot enforce a cross-section de-duplication
        rule. This is a documented decision, not an oversight — recovery fires only for sections
        the primary completion left empty, and the pinned eval baseline was measured end-to-end
        with this path live, so any residual restatement it produces is already inside the
        measured redundancy floor.
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

