from __future__ import annotations

import asyncio
import logging
import sys
from openai import AsyncOpenAI
from typing import Any, Dict, List, Optional
from app.config import settings
from app.schemas.summary import attach_normalized_facts
from app.services.prompt_loader import get_prompt, get_structured_prompt  # noqa: F401 - live prompt seams
import json

# Cohesive helpers/mixins extracted from this module (roadmap S2 façade split). Imported here so
# ``app.services.openai_service`` stays the single import surface for every existing caller; the
# re-exported public names are pinned in ``__all__`` at the bottom of this module.
from app.services.ai.bank_guards import _is_no_total_bank, _sanitize_bank_financial_highlights
from app.services.ai.provider_requests import (
    _ProviderRequestsMixin, bounded_summary, close_stream, fallback_client,
)
from app.services.ai.recovery_context import RecoveryBlock, clean_filing_source, recovery_blocks
from app.services.ai.normalize import _normalize_risk_factors, _section_has_content  # noqa: F401 - retained facade imports
from app.services.ai.xbrl_narrative import (
    build_xbrl_narrative_section,
    _XBRL_NARRATIVE_SPEC,
    _format_xbrl_metric_value,
)
# Method-group mixins composed into OpenAIService (below). Each holds a cohesive slice of the
# service's methods; they resolve through ``self`` exactly as before the split.
from app.services.ai.copilot_chat import (
    _CopilotChatMixin,
    STREAM_ACTIVITY_SENTINEL,
    STREAM_ERROR_SENTINEL,
)
from app.services.ai.extraction import _ExtractionMixin
from app.services.ai.evidence_snap import snap_evidence
from app.services.ai.acquisition_period import (
    CONTEXT_KEY as ACQUISITION_CONTEXT_KEY, CONTEXT_VERSION as ACQUISITION_CONTEXT_VERSION,
    bind_acquisition_period, clear_model_acquisition_context,
)
from app.services.ai.attribution_gate import apply_attributions, find_attributions  # noqa: F401 - retained facade imports
from app.services.ai import attribution_verify, summary_finalize, summary_prompt
from app.services.ai.summary_finalize import _segments_not_applicable as _segments_not_applicable
from app.services.ai.forward_quote_gate import gate_forward_quotes  # noqa: F401 - retained facade imports
from app.services.ai.statement_relationship import (  # noqa: F401 - retained facade imports
    CONTEXT_KEY as STATEMENT_CONTEXT_KEY, CONTEXT_VERSION as STATEMENT_CONTEXT_VERSION,
    OWNED_FIELD as STATEMENT_OWNED_FIELD, bind_statement_relationship, display_statement_paragraphs,
)
from app.services.ai.issuer_cash_disclosure import (  # noqa: F401 - retained facade imports
    CONTEXT_KEY as ISSUER_CASH_CONTEXT_KEY, CONTEXT_VERSION as ISSUER_CASH_CONTEXT_VERSION,
    SOURCE_KEY as ISSUER_CASH_SOURCE_KEY, OWNED_FIELD as ISSUER_CASH_OWNED_FIELD, bind_issuer_cash_disclosure,
)
from app.services.ai.financing_comparison import (
    CAPITAL_CONTEXT_KEY, CAPITAL_CONTEXT_VERSION, bind_capital_allocation,
)
from app.services.ai.source_units import (
    attach_quote_unit_context, build_table_unit_index, capital_plan_proposition,
    restore_authored_plan_units, restore_table_cell_units,
)
from app.services.ai.reconciliation_directions import (  # noqa: F401 - retained facade imports
    AUDIT_KEY as RECONCILIATION_AUDIT_KEY, strip_reconciliation_metadata, withhold_reconciliation_directions,
)
from app.services.ai.tax_rate_explanation import (  # noqa: F401 - retained facade imports
    AUDIT_KEY as TAX_EXPLANATION_AUDIT_KEY, strip_tax_explanation_metadata, withhold_tax_rate_explanation,
)
from app.services.ai.json_repair import _JsonRepairMixin
from app.services.ai.markdown_render import _MarkdownRenderMixin
from app.services.ai.section_recovery import _SectionRecoveryMixin
from app.services.metric_delta_service import (
    EXACT_CONTEXT_KEY as METRIC_DELTA_CONTEXT_KEY,
    EXACT_CONTEXT_VERSION as METRIC_DELTA_CONTEXT_VERSION,
    bind_exact_xbrl_deltas,
)
from app.services.summary_sections import render_sections, sections_to_markdown
from app.services.provenance_service import (  # noqa: F401 - retained facade imports
    RISK_PROJECTION_KEY,
    RISK_SOURCE_CONTEXT_KEY,
    RISK_SOURCE_CONTEXT_VERSION,
    project_risk_list,
)
# The generation-side taxonomy: the section keys the current schema_template emits — v2 as of the
# Tier-3.1 cutover. summarize_filing builds the per_section coverage snapshot from it below. This is
# DISTINCT from the quality badge's frozen per-version tuples (summary_schema.TRACKED_SECTIONS_V1 /
# V2): the badge counts a stored row against ITS OWN schema_version, so this generation-side constant
# moving to v2 must not retroactively change how a legacy v1 row is scored. Single source of truth
# for the v2 names lives in summary_schema.
from app.services.summary_schema import (  # noqa: F401 - retained facade imports
    EARNINGS_RECONCILIATION, FINANCIAL_DRIVER, FINANCIAL_EXPLANATION_SUPPORT, REPORTED_METRIC_LABEL,
    SOURCE_UNIT_CONTEXT_KEY, SOURCE_UNIT_CONTEXT_VERSION,
)
from app.services.summary_schema import TRACKED_SECTIONS_V2 as _TRACKED_STRUCTURED_SECTIONS
from app.services.summary_versioning import SUMMARY_SCHEMA_VERSION

logger = logging.getLogger(__name__)


class OpenAIService(
    _ProviderRequestsMixin,
    _ExtractionMixin,
    _JsonRepairMixin,
    _MarkdownRenderMixin,
    _SectionRecoveryMixin,
    _CopilotChatMixin,
):
    def __init__(self):
        # Application requests own retry/deadline policy; SDK retries must not multiply it.
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY,
                                  base_url=settings.OPENAI_BASE_URL, max_retries=0)
        self.fallback_client = fallback_client()
        self.model = settings.AI_DEFAULT_MODEL
        self._model_overrides = {"10-K": self.model, "10-Q": self.model}
        self._task_models = {
            "structured_extraction": self.model,
            "section_recovery": (settings.AI_SECTION_RECOVERY_MODEL.strip()
                                 or settings.AI_FAST_MODEL.strip() or self.model),
            # Attribution verification is a short yes/no read of supplied passages, so it takes the
            # same cheap model section recovery uses; no new provider and no new credential.
            "attribution_verify": (settings.AI_SECTION_RECOVERY_MODEL.strip()
                                   or settings.AI_FAST_MODEL.strip() or self.model),
        }
        # Concurrency control for parallel section recovery
        # Limits concurrent API calls to prevent rate limiting
        # Configurable via RECOVERY_MAX_CONCURRENCY setting (default: 3)
        max_concurrency = getattr(settings, 'RECOVERY_MAX_CONCURRENCY', 3)
        self._recovery_semaphore = asyncio.Semaphore(max_concurrency)

    def get_model_for_filing(self, filing_type: Optional[str]) -> str:
        """Return the configured primary model for this filing type."""
        if not filing_type:
            return self.model
        return self._model_overrides.get(filing_type.upper(), self.model)

    def get_model_for_task(self, task_type: str, filing_type: Optional[str] = None) -> str:
        """Return the appropriate model for a specific task type.

        Task types:
        - structured_extraction: Primary JSON extraction (needs highest accuracy)
        - section_recovery: Fill missing sections (simpler; opt-in cheaper model via config — A11)

        Falls back to filing-type model if task not recognized.
        """
        if task_type in self._task_models:
            return self._task_models[task_type]
        return self.get_model_for_filing(filing_type)

    async def _verify_attributions(
        self, candidates: list, filing_type_key: str,
    ) -> tuple[Optional[Dict[int, str]], Optional[Dict[str, Any]]]:
        """One bounded model verdict on the clauses the attribution gate flagged.

        Returns ``(verdicts, note)``. ``verdicts`` is None whenever no verdict was obtained — the
        flag is off, nothing was flagged, or the call failed — and a None verdict map is what stops
        ``apply_attributions`` from removing anything. Every failure mode lands here: a provider
        error, a timeout, an exhausted request budget or unparseable JSON all leave the summary
        exactly as the model wrote it, with the reason recorded in the audit.
        """
        if not settings.AI_ATTRIBUTION_VERIFY or not candidates:
            return None, None
        judged = attribution_verify.verifiable(candidates)
        if not judged:
            return None, attribution_verify.audit_note(candidates, judged, {}, "no source passages")
        try:
            raw = await self._request_content(
                {"model": self.get_model_for_task("attribution_verify", filing_type_key),
                 "messages": [{"role": "system", "content": attribution_verify.VERIFY_SYSTEM_MESSAGE},
                              {"role": "user", "content": attribution_verify.build_prompt(judged)}],
                 "temperature": 0.0, "max_tokens": 700},
                operation="attribution_verify", timeout=15.0,
            )
        except Exception as exc:  # noqa: BLE001 — never let verification fail a generation
            logger.warning("attribution_verify_failed error=%s", type(exc).__name__)
            return None, attribution_verify.audit_note(candidates, judged, {}, type(exc).__name__)
        verdicts = attribution_verify.parse_verdicts(raw, judged)
        if not verdicts:
            return None, attribution_verify.audit_note(candidates, judged, {}, "no usable verdicts")
        # Indices are positions in `judged`, which is a prefix-filtered view of `candidates`; map
        # them back so a drop can never act on a clause the verifier was not shown.
        position = {id(c): i for i, c in enumerate(candidates)}
        mapped = {position[id(judged[i])]: verdict for i, verdict in verdicts.items()}
        return mapped, attribution_verify.audit_note(candidates, judged, verdicts, None)

    def _parse_and_clean_text(
        self,
        filing_text: str,
        filing_type_key: str,
        filing_excerpt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Helper method to run heavy parsing in a separate thread.
        This isolates CPU-intensive BeautifulSoup and regex operations from the main event loop.
        """
        if filing_excerpt and filing_excerpt.strip():
            filing_sample = clean_filing_source(filing_excerpt)
        else:
            clean = clean_filing_source(filing_text)
            filing_sample = self.extract_critical_sections(
                filing_text, filing_type_key, cleaned_text=clean
            ) if clean.strip() else ""
            if not filing_sample:
                filing_sample = clean[:15000]

        layout = self._SECTION_LAYOUT.get(filing_type_key.removesuffix("/A"), self._SECTION_LAYOUT["10-K"])
        return {
            "filing_sample": filing_sample,
            "financial_data": self.extract_financial_data(filing_sample[:25000]),
            "recovery_sources": recovery_blocks(filing_sample, layout),
        }

    @bounded_summary()
    async def generate_structured_summary(
        self,
        filing_text: str,
        company_name: str,
        filing_type: str,
        xbrl_metrics: Optional[Dict] = None,
        filing_excerpt: Optional[str] = None,
        stream_cb: Optional[Any] = None,
        statement_source: Optional[Dict] = None,
        sixk_class: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Phase 1: Extract structured financial schema from the filing.

        When ``stream_cb`` is provided (A5 progressive reveal), the primary model is streamed and
        ``stream_cb(partial_markdown)`` is awaited with throttled preview renders as the JSON fills
        in; the COMPLETE content is then assembled through the same path as the non-streaming branch,
        so both use the same assembly. Transient streaming failures discard buffered content and
        retry non-streaming within the shared deadline; callback errors remain best-effort."""
        from app.services.request_work import run_owned_sync as run_in_threadpool

        filing_type_key = (filing_type or "10-K").upper()
        
        # Offload heavy parsing/regex to thread pool to prevent blocking the event loop
        # This addresses the stall issue during summary generation
        parsing_result = await run_in_threadpool(
            self._parse_and_clean_text,
            filing_text,
            filing_type_key,
            filing_excerpt
        )
        
        filing_sample = parsing_result["filing_sample"]
        financial_data = parsing_result["financial_data"]
        recovery_sources = parsing_result["recovery_sources"]
        
        # Explicit clean up
        del parsing_result

        create_kwargs: Dict[str, Any] = summary_prompt.build_primary_request(
            self, sys.modules[__name__], filing_type_key, sixk_class, xbrl_metrics,
            financial_data, company_name, filing_type, filing_sample,
        )
        # Only the supplied excerpt owns this correction on both preview and final paths.
        layout = self._SECTION_LAYOUT.get(filing_type_key.removesuffix("/A"), self._SECTION_LAYOUT["10-K"])
        plan = capital_plan_proposition(filing_excerpt or "", layout)
        # Declared table-cell scales: the filing's own source document (inline-XBRL facts and
        # <table> cells) owns previews and the final render; a cached-excerpt generation has none.
        unit_index = build_table_unit_index(filing_text or "")
        content = await self._request_content(
            create_kwargs, stream_cb=stream_cb, filing_type_key=filing_type_key,
            xbrl_metrics=xbrl_metrics, **({"capital_plan": plan} if plan else {}),
            **({"statement_source": statement_source} if statement_source else {}),
            **({"unit_index": unit_index} if unit_index else {}),
            **({"primary_excerpt": filing_excerpt} if filing_excerpt else {}),
        )
        return await self._assemble_structured_summary(
            content, filing_type_key, filing_sample, xbrl_metrics, recovery_sources
        )

    async def _assemble_structured_summary(
        self,
        content: Optional[str],
        filing_type_key: str,
        filing_sample: str,
        xbrl_metrics: Optional[Dict],
        recovery_sources: tuple[RecoveryBlock, ...],
    ) -> Dict[str, Any]:
        """Parse the model's JSON response → recover empty sections → apply fallbacks → return the
        structured summary dict. Shared by the non-streaming path and the streaming (progressive
        reveal) path, so the FINAL output is identical regardless of how the content was produced —
        this is the invariant that makes streaming a zero-quality-risk change."""
        payload = self._clean_json_payload(content or "")

        if not payload:
            raise ValueError("Extraction model returned empty payload.")

        # Always run repair first - json-repair library handles ALL edge cases
        # including unterminated strings, missing brackets, unescaped chars
        try:
            # First try direct parsing (fast path for valid JSON)
            summary_data = json.loads(payload)
        except json.JSONDecodeError as initial_error:
            # Apply robust repair using json-repair library
            logger.warning(f"JSON decode failed, attempting repair: {initial_error}")
            try:
                repaired_payload = self._repair_json(payload)
                summary_data = json.loads(repaired_payload)
                logger.info("JSON repair successful using json-repair library")
            except json.JSONDecodeError as repair_error:
                # Log details for debugging
                logger.error(f"JSON repair failed: {repair_error}")
                logger.error(f"Original error: {initial_error}")
                logger.error(f"Raw payload (first 500 chars): {payload[:500]}")
                # Re-raise with original error for clearer debugging
                raise initial_error

        # R1 guard: coerce non-object JSON (bare array / wrapped object) so .get() never crashes.
        summary_data = self._coerce_summary_dict(summary_data)
        sections_info = summary_data.get("sections")
        if not isinstance(sections_info, dict):
            sections_info = {}
        metadata = summary_data.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        # The model cannot choose its own evidence source. Overwrite its private key.
        summary_data["_capital_allocation_grounding"] = filing_sample
        summary_data[ISSUER_CASH_SOURCE_KEY] = filing_sample
        # Same rule for source-first Risks: this value is application-built after JSON parsing,
        # from the exact bounded text placed in the primary prompt.  A model-supplied copy cannot
        # select its own source.  ``summarize_filing`` removes it before building the stored payload.
        summary_data["_risk_source_grounding"] = filing_sample
        missing_sections = self._find_empty_sections(sections_info)
        if missing_sections:
            recovered = await self._recover_missing_sections(
                missing_sections,
                filing_type_key,
                recovery_sources,
                filing_sample,
                metadata,
            )
            if recovered:
                sections_info.update(recovered)
                if "earnings_quality" in recovered:
                    summary_data[ISSUER_CASH_SOURCE_KEY] = self._build_section_context(
                        "earnings_quality", recovery_sources, filing_sample,
                    )
                if "value_drivers" in recovered:
                    summary_data["_capital_allocation_grounding"] = self._build_section_context(
                        "value_drivers", recovery_sources, filing_sample,
                    )
                # Evidence auto-snap (skeptic F3): recovery re-asks generate from
                # separately selected context, which may differ from the exact primary excerpt; its verbatim-TRUE
                # evidence can fail the excerpt exact-check — the snap must not touch it.
                # summarize_filing pops this private key before assembling the stored payload.
                summary_data["_recovered_sections"] = sorted(recovered.keys())

        self._apply_structured_fallbacks(
            sections_info,
            metadata,
            xbrl_metrics,
        )
        summary_data["sections"] = sections_info
        summary_data["metadata"] = metadata

        return summary_data

    async def _stream_collect(
        self,
        create_kwargs: Dict[str, Any],
        stream_cb: Any,
        filing_type_key: str,
        xbrl_metrics: Optional[Dict],
        *, _client=None, _observation=None, capital_plan: tuple[str, str] | None = None,
        statement_source: Optional[Dict] = None, unit_index: Any = None, primary_excerpt: str = "",
    ) -> str:
        """Stream a structured-extraction call, awaiting ``stream_cb(partial_markdown)`` with throttled
        preview renders as the JSON fills in, and return the COMPLETE accumulated content. Preview
        rendering and ``stream_cb`` are best-effort — they never affect the returned content."""
        parts: List[str] = []
        emitted_at = 0
        started = asyncio.get_running_loop().time()
        stream = await (_client or self.client).chat.completions.create(**create_kwargs)
        try:
            async for chunk in stream:
                if _observation is not None:
                    if getattr(chunk, "model", None):
                        _observation["model"] = chunk.model
                    if getattr(chunk, "system_fingerprint", None):
                        _observation["fingerprint"] = chunk.system_fingerprint
                    if getattr(chunk, "usage", None) is not None:
                        _observation["usage"] = chunk.usage
                choices = getattr(chunk, "choices", None)
                if not choices:
                    continue
                delta = getattr(choices[0], "delta", None)
                piece = getattr(delta, "content", None) if delta is not None else None
                if not piece:
                    continue
                if _observation is not None and _observation.get("first_token_ms") is None:
                    _observation["first_token_ms"] = (asyncio.get_running_loop().time() - started) * 1000
                parts.append(piece)
                total = sum(len(p) for p in parts)
                # Re-render a preview every ~1500 new chars to keep preview frames modest.
                if total - emitted_at >= 1500:
                    emitted_at = total
                    preview = self._partial_markdown_preview(
                        "".join(parts), xbrl_metrics,
                        **({"filing_type_key": filing_type_key} if unit_index is not None or primary_excerpt else {}),
                        **({"capital_plan": capital_plan} if capital_plan else {}),
                        **({"statement_source": statement_source} if statement_source else {}),
                        **({"unit_index": unit_index} if unit_index else {}),
                        **({"primary_excerpt": primary_excerpt} if primary_excerpt else {}),
                    )
                    if preview:
                        try:
                            await stream_cb(preview)
                        except Exception:  # noqa: BLE001 — a consumer error must never abort generation
                            pass
        finally:
            await close_stream(stream)
        return "".join(parts)

    def _partial_markdown_preview(
        self, partial_content: str, xbrl_metrics: Optional[Dict], *, filing_type_key: str = "",
        capital_plan: tuple[str, str] | None = None,
        statement_source: Optional[Dict] = None, unit_index: Any = None, primary_excerpt: str = "",
    ) -> Optional[str]:
        """Render only originally complete sections with the current summary projection.

        In-flight values are never repaired into claims. Missing sections remain pending;
        previews are optional and the authoritative final render supersedes them.
        """
        try:
            sections = self._complete_preview_sections(partial_content or "")
            clear_model_acquisition_context(sections)
            # Preview may own a capital-plan proposition, but never a quote-unit badge.
            attach_quote_unit_context(sections)
            restore_authored_plan_units(sections, capital_plan)
            completed_keys = tuple(
                key for key in sections
                if key != "the_print" or not self._section_is_empty(sections[key])
            )
            # Parsed sections are a fresh local copy. Reuse final numeric ownership, then
            # keep unreceived sections pending instead of revealing synthesized fallbacks.
            # An empty lead also stays pending, without the final degraded-detail notice.
            self._apply_structured_fallbacks(sections, {}, xbrl_metrics)
            sections = {key: sections[key] for key in completed_keys if key in sections}
            if "results_that_matter" in sections:
                sections["results_that_matter"] = _sanitize_bank_financial_highlights(
                    sections["results_that_matter"], xbrl_metrics,
                )
                sections["results_that_matter"] = attach_normalized_facts(
                    sections["results_that_matter"], xbrl_metrics,
                )
                sections["results_that_matter"] = bind_exact_xbrl_deltas(
                    sections["results_that_matter"], xbrl_metrics,
                )
            # This callback has no excerpt to verify against. When verification is required,
            # attributed quotes wait for the authoritative final gate (other prose can show).
            forward = sections.get("forward_signals")
            if settings.AI_FORWARD_QUOTE_GATE and isinstance(forward, dict):
                forward.pop("quotes", None)
            # A partial provider response has no source text at this callback boundary. Risks wait
            # for the final same-filing source projection rather than streaming model-authored text.
            sections.pop("risks", None)
            acquisition_owned = bind_acquisition_period(sections, primary_excerpt, xbrl_metrics, filing_type=filing_type_key)
            statement_owned = bind_statement_relationship(sections, statement_source)
            bind_capital_allocation(sections, xbrl_metrics)
            bind_issuer_cash_disclosure(sections)
            withhold_tax_rate_explanation(sections, unit_index)
            withhold_reconciliation_directions(sections, unit_index, filing_type=filing_type_key)
            # Same table-cell owner as the final render, over the same source document, after the
            # same binders, so preview and final restore the same surviving prose.
            restore_table_cell_units(sections, unit_index, xbrl_metrics=xbrl_metrics)
            rendered = render_sections({
                "schema_version": SUMMARY_SCHEMA_VERSION, "sections": sections,
                CAPITAL_CONTEXT_KEY: CAPITAL_CONTEXT_VERSION,
                METRIC_DELTA_CONTEXT_KEY: METRIC_DELTA_CONTEXT_VERSION,
                **({ACQUISITION_CONTEXT_KEY: ACQUISITION_CONTEXT_VERSION} if acquisition_owned else {}),
                **({STATEMENT_CONTEXT_KEY: STATEMENT_CONTEXT_VERSION} if statement_owned else {}),
            })
            return sections_to_markdown(rendered) or None
        except Exception:  # noqa: BLE001 — optional malformed previews must not abort generation
            return None

    @bounded_summary(report=True)
    async def summarize_filing(
        self,
        filing_text: str,
        company_name: str,
        filing_type: str,
        xbrl_metrics: Optional[Dict] = None,
        filing_excerpt: Optional[str] = None,
        stream_cb: Optional[Any] = None,
        statement_source: Optional[Dict] = None,
        sixk_class: Optional[str] = None,
        sixk_class_audit: Optional[Dict] = None,
    ) -> Dict:
        """Generate a newsroom-ready summary: one structured extraction, rendered without a second provider call.

        ``stream_cb`` opts into progressive previews. The provider request policy owns bounded
        transient retries; exhausted/authentication failures retain the existing error contract.
        The metering signal (``provider_requests.provider_start_signal``) travels in the task
        context, not as a parameter."""
        import asyncio

        filing_type_key = (filing_type or "10-K").upper()
        try:
            structured_summary = await self.generate_structured_summary(
                filing_text, company_name, filing_type,
                xbrl_metrics=xbrl_metrics, filing_excerpt=filing_excerpt, stream_cb=stream_cb,
                **({"statement_source": statement_source} if statement_source else {}),
                **({"sixk_class": sixk_class} if sixk_class else {}),
            )
        except asyncio.TimeoutError:
            # The single orchestrator owns deterministic partial fallback on deadline exhaustion.
            raise
        except Exception as extraction_error:
            return summary_finalize.extraction_failure(extraction_error, company_name, filing_type_key, logger)

        run = summary_finalize.SummaryRun(
            structured_summary=structured_summary, company_name=company_name,
            filing_type_key=filing_type_key, filing_text=filing_text,
            xbrl_metrics=xbrl_metrics, filing_excerpt=filing_excerpt,
            statement_source=statement_source, sixk_class=sixk_class, sixk_class_audit=sixk_class_audit,
        )
        summary_finalize.prepare_sections(run)
        summary_finalize.project_risks(run)
        summary_finalize.measure_forward_quotes(run)
        summary_finalize.find_summary_attributions(run)
        run.attribution_verdicts, run.verify_note = await self._verify_attributions(
            run.attribution_candidates, filing_type_key,
        )
        summary_finalize.apply_summary_attributions(run)
        await summary_finalize.snap_primary_evidence(run, snap_evidence)
        summary_finalize.bind_final_sources(
            run, self._SECTION_LAYOUT.get(filing_type_key.removesuffix("/A"), self._SECTION_LAYOUT["10-K"]),
        )
        summary_finalize.measure_coverage(run, logger)
        summary_finalize.build_compatibility_strings(run)
        summary_finalize.render_summary(run, self._build_structured_markdown)
        summary_finalize.build_raw_payload(run)
        summary_finalize.derive_title(run)
        summary_finalize.build_legacy_cards(run)
        summary_finalize.build_insights(run)
        summary_finalize.determine_status(run)

        response = {
            "summary_title": run.summary_title, "sections": run.sections,
            "insights": run.insights, "status": run.status,
            # Keep legacy fields for backward compatibility
            "business_overview": run.final_markdown,
            "financial_highlights": run.financial_section,
            "risk_factors": run.risk_section,
            "management_discussion": run.management_section,
            "key_changes": run.guidance_section,
            "raw_summary": run.raw_summary_payload,
            # Private source candidates/grounding survive to the shared pipeline finalizer.
            "_risk_source_candidates": run.risk_candidates,
            "_risk_source_grounding": run.risk_source,
        }

        if run.message:
            response["message"] = run.message

        return response

openai_service = OpenAIService()


# Public import surface of this façade. Callers import these from ``app.services.openai_service``;
# the definitions live in the ``app.services.ai`` package (roadmap S2 split). Listed here so the
# split stays caller-transparent and so ruff treats the re-exported imports as used (no F401).
__all__ = [
    "openai_service",
    "OpenAIService",
    "STREAM_ERROR_SENTINEL",
    "STREAM_ACTIVITY_SENTINEL",
    "_TRACKED_STRUCTURED_SECTIONS",
    "build_xbrl_narrative_section",
    "_XBRL_NARRATIVE_SPEC",
    "_format_xbrl_metric_value",
    "_is_no_total_bank",
    "_sanitize_bank_financial_highlights",
]
