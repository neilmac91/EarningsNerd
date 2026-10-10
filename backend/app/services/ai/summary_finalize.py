"""Ordered post-provider summary finalization; provider calls stay on OpenAIService."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.config import settings
from app.schemas.summary import attach_normalized_facts
from app.services.ai.acquisition_period import (
    CONTEXT_KEY as ACQUISITION_CONTEXT_KEY,
    CONTEXT_VERSION as ACQUISITION_CONTEXT_VERSION,
    bind_acquisition_period,
    clear_model_acquisition_context,
)
from app.services.ai.attribution_gate import apply_attributions, find_attributions
from app.services.ai.bank_guards import _sanitize_bank_financial_highlights
from app.services.ai.financing_comparison import CAPITAL_CONTEXT_KEY, CAPITAL_CONTEXT_VERSION, bind_capital_allocation
from app.services.ai.forward_quote_gate import gate_forward_quotes
from app.services.ai.issuer_cash_disclosure import (
    CONTEXT_KEY as ISSUER_CASH_CONTEXT_KEY,
    CONTEXT_VERSION as ISSUER_CASH_CONTEXT_VERSION,
    OWNED_FIELD as ISSUER_CASH_OWNED_FIELD,
    SOURCE_KEY as ISSUER_CASH_SOURCE_KEY,
    bind_issuer_cash_disclosure,
)
from app.services.ai.normalize import _normalize_risk_factors, _section_has_content
from app.services.ai.reconciliation_directions import (
    AUDIT_KEY as RECONCILIATION_AUDIT_KEY,
    strip_reconciliation_metadata,
    withhold_reconciliation_directions,
)
from app.services.ai.source_units import (
    attach_quote_unit_context,
    build_table_unit_index,
    capital_plan_proposition,
    restore_authored_plan_units,
    restore_table_cell_units,
)
from app.services.ai.statement_relationship import (
    CONTEXT_KEY as STATEMENT_CONTEXT_KEY,
    CONTEXT_VERSION as STATEMENT_CONTEXT_VERSION,
    OWNED_FIELD as STATEMENT_OWNED_FIELD,
    bind_statement_relationship,
    display_statement_paragraphs,
)
from app.services.ai.tax_rate_explanation import (
    AUDIT_KEY as TAX_EXPLANATION_AUDIT_KEY,
    strip_tax_explanation_metadata,
    withhold_tax_rate_explanation,
)
from app.services.metric_delta_service import (
    EXACT_CONTEXT_KEY as METRIC_DELTA_CONTEXT_KEY,
    EXACT_CONTEXT_VERSION as METRIC_DELTA_CONTEXT_VERSION,
    bind_exact_xbrl_deltas,
)
from app.services.provenance_service import (
    RISK_PROJECTION_KEY,
    RISK_SOURCE_CONTEXT_KEY,
    RISK_SOURCE_CONTEXT_VERSION,
    project_risk_list,
)
from app.services.summary_schema import (
    SOURCE_UNIT_CONTEXT_KEY,
    SOURCE_UNIT_CONTEXT_VERSION,
    TRACKED_SECTIONS_V2 as _TRACKED_STRUCTURED_SECTIONS,
)
from app.services.summary_sections import render_sections, sections_to_markdown
from app.services.summary_versioning import SUMMARY_SCHEMA_VERSION


@dataclass
class SummaryRun:
    """Per-call values shared by the ordered post-provider phases; no copies of section data."""
    structured_summary: Dict
    company_name: str
    filing_type_key: str
    filing_text: str
    xbrl_metrics: Optional[Dict]
    filing_excerpt: Optional[str]
    statement_source: Optional[Dict]
    sixk_class: Optional[str]
    sixk_class_audit: Optional[Dict]
    acquisition_owned: Any = field(init=False, repr=False)
    attribution_audit: Any = field(init=False, repr=False)
    attribution_candidates: Any = field(init=False, repr=False)
    attribution_checked: Any = field(init=False, repr=False)
    attribution_verdicts: Any = field(init=False, repr=False)
    coverage_snapshot: Any = field(init=False, repr=False)
    covered_sections: Any = field(init=False, repr=False)
    evidence_snap_audit: Any = field(init=False, repr=False)
    final_markdown: Any = field(init=False, repr=False)
    financial_section: Any = field(init=False, repr=False)
    forward_quote_audit: Any = field(init=False, repr=False)
    guidance_section: Any = field(init=False, repr=False)
    guidance_structured: Any = field(init=False, repr=False)
    insights: Any = field(init=False, repr=False)
    issuer_cash_owned: Any = field(init=False, repr=False)
    management_section: Any = field(init=False, repr=False)
    message: Any = field(init=False, repr=False)
    raw_summary_payload: Any = field(init=False, repr=False)
    reconciliation_audit: Any = field(init=False, repr=False)
    recovered_keys: Any = field(init=False, repr=False)
    risk_candidates: Any = field(init=False, repr=False)
    risk_section: Any = field(init=False, repr=False)
    risk_source: Any = field(init=False, repr=False)
    sections: Any = field(init=False, repr=False)
    sections_info: Any = field(init=False, repr=False)
    statement_owned: Any = field(init=False, repr=False)
    status: Any = field(init=False, repr=False)
    summary_title: Any = field(init=False, repr=False)
    table_cell_unit_audit: Any = field(init=False, repr=False)
    tax_explanation_audit: Any = field(init=False, repr=False)
    unit_index: Any = field(init=False, repr=False)
    verify_note: Any = field(init=False, repr=False)
    writer_error: Any = field(init=False, repr=False)
    writer_fallback_reason: Any = field(init=False, repr=False)
    writer_result: Any = field(init=False, repr=False)


def _segments_not_applicable(coverage_map: Dict[str, bool], xbrl_metrics: Optional[Dict]) -> List[str]:
    """T5.2b N/A marker (staff-review rider on #616): `segments` is machine-authored — code is its ONLY
    author — so an empty segments section post-fallback means the filing has no reportable segment table
    BY DESIGN (single-segment / undimensioned / bank), and the quality verdict may exclude it from the
    badge DENOMINATOR (a genuinely single-segment filer reads 8/8, not a misleading 8/9).

    Claimed ONLY when standardized XBRL actually arrived (staff review #617): `not covered` is also true
    when the XBRL fetch collapsed (the recurring EdgarTools-timeout mode) — a world where the filer may
    well HAVE reportable segments we simply could not author. Marking that N/A would UPGRADE a degraded
    run's badge to a clean 8/8 (the mirror image of the misleading-badge problem this fixes) and shrink
    the tail the P0-2 partial-verdict counter measures. No XBRL → no claim → total stays 9."""
    if xbrl_metrics and not coverage_map.get("segments"):
        return ["segments"]
    return []


def extraction_failure(extraction_error: Exception, company_name: str, filing_type_key: str, logger: Any) -> Dict:
    error_msg = str(extraction_error)
    logger.error(f"Structured extraction error: {error_msg}")
    return {
        "status": "error",
        "message": "We couldn't generate this summary just now. Please try again shortly.",
        "summary_title": f"{company_name} {filing_type_key} Filing Summary",
        "sections": [],
        "insights": {
            "sentiment": "Neutral",
            "growth_drivers": [],
            "risk_signals": []
        },
        # Legacy fields
        "business_overview": "Unable to retrieve this filing at the moment — please try again shortly.",
        "financial_highlights": {},
        "risk_factors": [],
        "management_discussion": "",
        "key_changes": "",
        "raw_summary": {"error": "structured_extraction_failed", "detail": error_msg[:500]},
    }


def prepare_sections(run: SummaryRun) -> None:
    strip_tax_explanation_metadata(run.structured_summary)
    strip_reconciliation_metadata(run.structured_summary)
    run.sections_info = run.structured_summary.get("sections", {}) or {}
    # Keep only the current taxonomy in the shared stored/rendered section object.
    if isinstance(run.sections_info, dict):
        run.sections_info = {
            key: value for key, value in run.sections_info.items()
            if key in _TRACKED_STRUCTURED_SECTIONS
        }
        run.structured_summary["sections"] = run.sections_info
    # v2 taxonomy (Tier-3.1): the P&L table lives in `results_that_matter`; risks in `risks`.
    run.financial_section = run.sections_info.get("results_that_matter")
    # Banks with no total revenue cannot publish a model-conflated total. Mutate the shared section.
    run.financial_section = _sanitize_bank_financial_highlights(run.financial_section, run.xbrl_metrics)
    run.financial_section = attach_normalized_facts(run.financial_section, run.xbrl_metrics)
    run.financial_section = bind_exact_xbrl_deltas(run.financial_section, run.xbrl_metrics)
    if isinstance(run.sections_info, dict):
        run.sections_info["results_that_matter"] = run.financial_section


def project_risks(run: SummaryRun) -> None:
    # Use the retained excerpt or the cleaned source the primary model actually saw.
    prepared_risk_source = run.structured_summary.pop("_risk_source_grounding", "")
    run.risk_source = (
        run.filing_excerpt
        if isinstance(run.filing_excerpt, str) and run.filing_excerpt.strip()
        else prepared_risk_source
    )
    raw_risk_section = run.sections_info.get("risks")
    if isinstance(raw_risk_section, str):
        raw_risk_section = [raw_risk_section]
    run.risk_candidates = _normalize_risk_factors(raw_risk_section)
    run.risk_section, risk_projection = project_risk_list(
        run.risk_candidates,
        sources=[run.risk_source] if isinstance(run.risk_source, str) and run.risk_source.strip() else [],
        base_url=None,
    )
    run.sections_info.pop("risk_factors", None)
    run.sections_info["risks"] = run.risk_section
    run.sections_info[RISK_PROJECTION_KEY] = risk_projection


def measure_forward_quotes(run: SummaryRun) -> None:
    # Measure before coverage/render; only the armed flag drops unverified quotes.
    # Ground solely in the supplied excerpt: raw HTML is not the cleaned source the model saw.
    # With no excerpt, measure and drop nothing.
    run.forward_quote_audit = gate_forward_quotes(
        run.sections_info, run.filing_excerpt or "", settings.AI_FORWARD_QUOTE_GATE
    )


def find_summary_attributions(run: SummaryRun) -> None:
    # Measure attribution against the excerpt; the service owns the one bounded verification call.
    # The lexical result alone must never delete text.
    run.attribution_checked, run.attribution_candidates = find_attributions(run.sections_info, run.filing_excerpt or "")


def apply_summary_attributions(run: SummaryRun) -> None:
    run.attribution_audit = apply_attributions(
        run.attribution_checked, run.attribution_candidates, run.attribution_verdicts,
        settings.AI_ATTRIBUTION_GATE,
    )
    if run.attribution_audit is not None and run.verify_note is not None:
        run.attribution_audit["verification"] = run.verify_note


async def snap_primary_evidence(run: SummaryRun, snap_evidence: Any) -> None:
    # Evidence snap is measured always, applied only when armed, before coverage/render.
    # Excerpt-only grounding; skip recovered sections whose selected source may differ.
    # The candidate scan runs off the event loop and the facade supplies the patchable callable.
    from app.services.request_work import run_owned_sync as run_in_threadpool

    run.recovered_keys = frozenset(run.structured_summary.pop("_recovered_sections", []) or [])
    # Bind original primary evidence before auto-snap can replace its bytes.
    clear_model_acquisition_context(run.structured_summary)
    run.acquisition_owned = bind_acquisition_period(
        run.sections_info, run.filing_excerpt or "", run.xbrl_metrics, filing_type=run.filing_type_key,
        recovered="notable_footnotes" in run.recovered_keys,
    )
    run.unit_index = build_table_unit_index(run.filing_text or "")
    # Inspect authored native-document evidence before fuzzy repair, including recovered notes.
    run.tax_explanation_audit = withhold_tax_rate_explanation(run.sections_info, run.unit_index)
    run.reconciliation_audit = withhold_reconciliation_directions(
        run.sections_info, run.unit_index, filing_type=run.filing_type_key,
        recovered="earnings_quality" in run.recovered_keys,
    )
    run.evidence_snap_audit = await run_in_threadpool(
        snap_evidence,
        run.sections_info,
        run.filing_excerpt or "",
        settings.EVIDENCE_SNAP_MIN_SCORE,
        settings.AI_EVIDENCE_SNAP,
        run.recovered_keys,
    )



def bind_final_sources(run: SummaryRun, layout: Any) -> None:
    # Certify final primary quotes against the supplied excerpt.
    attach_quote_unit_context(
        run.sections_info, run.filing_excerpt or "", layout,
        recovered="forward_signals" in run.recovered_keys,
    )

    if "forward_signals" not in run.recovered_keys:
        restore_authored_plan_units(
            run.sections_info, capital_plan_proposition(run.filing_excerpt or "", layout),
        )
    capital_source = run.structured_summary.pop("_capital_allocation_grounding", "")
    run.statement_owned = bind_statement_relationship(run.sections_info, run.statement_source)
    bind_capital_allocation(run.sections_info, run.xbrl_metrics, capital_source)
    run.issuer_cash_owned = bind_issuer_cash_disclosure(
        run.sections_info, run.structured_summary.pop(ISSUER_CASH_SOURCE_KEY, ""),
    )
    # Restore table-cell units after source binders, before coverage/render.
    # Verified source envelopes and recovered sections are outside these measured prose slots.
    run.table_cell_unit_audit = restore_table_cell_units(
        run.sections_info, run.unit_index,
        xbrl_metrics=run.xbrl_metrics, recovered=run.recovered_keys,
    )


def measure_coverage(run: SummaryRun, logger: Any) -> None:
    coverage_keys = set(_TRACKED_STRUCTURED_SECTIONS)
    # Private risk provenance must not inflate coverage.
    coverage_keys.update(
        key for key in run.sections_info.keys() if key != RISK_PROJECTION_KEY
    )
    coverage_map = {
        section: _section_has_content(run.sections_info.get(section))
        for section in sorted(coverage_keys)
    }
    total_sections = len(coverage_map)
    run.covered_sections = sum(1 for covered in coverage_map.values() if covered)
    missing_sections = [key for key, covered in coverage_map.items() if not covered]
    run.coverage_snapshot = {
        "per_section": coverage_map,
        "covered": [key for key, covered in coverage_map.items() if covered],
        "missing": missing_sections,
        "covered_count": run.covered_sections,
        "total_count": total_sections,
        "coverage_ratio": (run.covered_sections / total_sections) if total_sections else None,
        # The raw counts above stay raw (this snapshot records what exists; the verdict applies
        # the N/A semantics — see _segments_not_applicable).
        "not_applicable": _segments_not_applicable(coverage_map, run.xbrl_metrics),
    }

    logger.info(
        "Structured coverage for %s %s: %s/%s sections populated. Missing: %s",
        run.company_name,
        run.filing_type_key,
        run.covered_sections,
        total_sections,
        ", ".join(missing_sections) if missing_sections else "None",
    )


def build_compatibility_strings(run: SummaryRun) -> None:
    def _stringify(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, list):
            formatted_items = []
            for item in value:
                item_str = _stringify(item)
                if item_str:
                    formatted_items.append(f"- {item_str}")
            return "\n".join(formatted_items) if formatted_items else None
        if isinstance(value, dict):
            lines = []
            for key, content in value.items():
                content_str = _stringify(content)
                if content_str:
                    pretty_key = key.replace("_", " ").title()
                    lines.append(f"{pretty_key}: {content_str}")
            return "\n".join(lines) if lines else None
        return str(value)

    # v2 (Tier-3.1): MD&A dissolved into §1/§3/§5. The legacy `management_discussion` compat field
    # (and the eval's canonical management_discussion) maps to earnings_quality — the analytical
    # prose that absorbed the MD&A read; `key_changes`/outlook maps to forward_signals.
    management_section_structured = run.sections_info.get("earnings_quality")
    management_for_compat = management_section_structured
    if isinstance(management_section_structured, dict):
        management_for_compat = dict(management_section_structured)
        management_for_compat.pop(ISSUER_CASH_OWNED_FIELD, None)
        if run.statement_owned:
            owned_statement = management_for_compat.pop(STATEMENT_OWNED_FIELD, {})
            management_for_compat["operating_vs_one_time"] = "\n".join(display_statement_paragraphs(owned_statement))
    run.management_section = _stringify(management_for_compat)
    run.guidance_structured = run.sections_info.get("forward_signals")
    run.guidance_section = _stringify(run.guidance_structured)


def render_summary(run: SummaryRun, fallback_render: Any) -> None:
    # Render from structured data without a second provider call.
    run.writer_result = None
    run.writer_error: Optional[str] = None
    run.writer_fallback_reason: Optional[str] = None
    # Stamp the generation version and render the shared projection.
    # The bound legacy renderer is used only when no sections render.
    run.structured_summary["schema_version"] = SUMMARY_SCHEMA_VERSION
    # Only the final source-associated envelope can authorize code-owned units.
    run.structured_summary.pop(SOURCE_UNIT_CONTEXT_KEY, None)
    run.structured_summary.pop(CAPITAL_CONTEXT_KEY, None)
    run.structured_summary.pop(ISSUER_CASH_CONTEXT_KEY, None)
    run.structured_summary.pop(STATEMENT_CONTEXT_KEY, None)
    run.structured_summary.pop(ACQUISITION_CONTEXT_KEY, None)
    run.structured_summary.pop("primary_excerpt", None)
    run.structured_summary.pop(RISK_SOURCE_CONTEXT_KEY, None)
    run.structured_summary.pop("_risk_source_candidates", None)
    run.structured_summary.pop("_risk_source_candidate_count", None)
    render_envelope = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "sections": run.sections_info,
        SOURCE_UNIT_CONTEXT_KEY: SOURCE_UNIT_CONTEXT_VERSION,
        CAPITAL_CONTEXT_KEY: CAPITAL_CONTEXT_VERSION,
        METRIC_DELTA_CONTEXT_KEY: METRIC_DELTA_CONTEXT_VERSION,
        RISK_SOURCE_CONTEXT_KEY: RISK_SOURCE_CONTEXT_VERSION,
        **({ISSUER_CASH_CONTEXT_KEY: ISSUER_CASH_CONTEXT_VERSION} if run.issuer_cash_owned else {}),
        **({STATEMENT_CONTEXT_KEY: STATEMENT_CONTEXT_VERSION} if run.statement_owned else {}),
        **({ACQUISITION_CONTEXT_KEY: ACQUISITION_CONTEXT_VERSION} if run.acquisition_owned else {}),
    }
    rendered = render_sections(render_envelope)
    run.final_markdown = (
        sections_to_markdown(rendered) if rendered
        else fallback_render(run.structured_summary)
    )


def build_raw_payload(run: SummaryRun) -> None:
    run.raw_summary_payload = {
        **({ACQUISITION_CONTEXT_KEY: ACQUISITION_CONTEXT_VERSION} if run.acquisition_owned else {}),
        **({STATEMENT_CONTEXT_KEY: STATEMENT_CONTEXT_VERSION} if run.statement_owned else {}),
        SOURCE_UNIT_CONTEXT_KEY: SOURCE_UNIT_CONTEXT_VERSION,
        CAPITAL_CONTEXT_KEY: CAPITAL_CONTEXT_VERSION,
        METRIC_DELTA_CONTEXT_KEY: METRIC_DELTA_CONTEXT_VERSION,
        RISK_SOURCE_CONTEXT_KEY: RISK_SOURCE_CONTEXT_VERSION,
        **({ISSUER_CASH_CONTEXT_KEY: ISSUER_CASH_CONTEXT_VERSION} if run.issuer_cash_owned else {}),
        "structured": run.structured_summary,
        "sections": run.sections_info,
        "section_coverage": run.coverage_snapshot,
    }
    if run.forward_quote_audit:
        run.raw_summary_payload["forward_quote_audit"] = run.forward_quote_audit
    if run.attribution_audit:
        run.raw_summary_payload["attribution_audit"] = run.attribution_audit
    if run.evidence_snap_audit:
        run.raw_summary_payload["evidence_snap_audit"] = run.evidence_snap_audit
    if run.table_cell_unit_audit:
        run.raw_summary_payload["table_cell_unit_audit"] = run.table_cell_unit_audit
    if run.tax_explanation_audit:
        run.raw_summary_payload[TAX_EXPLANATION_AUDIT_KEY] = run.tax_explanation_audit
    if run.reconciliation_audit:
        run.raw_summary_payload[RECONCILIATION_AUDIT_KEY] = run.reconciliation_audit
    if run.writer_result:
        run.raw_summary_payload["writer"] = run.writer_result
    if run.writer_fallback_reason:
        run.raw_summary_payload["writer_fallback_reason"] = run.writer_fallback_reason
    if run.writer_error:
        run.raw_summary_payload["writer_error"] = run.writer_error[:500]
    if run.sixk_class:
        # W3-8b audit: which pre-classified 6-K variant produced this summary, and why.
        run.raw_summary_payload["sixk_class"] = run.sixk_class
        if run.sixk_class_audit:
            run.raw_summary_payload["sixk_class_audit"] = run.sixk_class_audit


def derive_title(run: SummaryRun) -> None:
    metadata = run.structured_summary.get("metadata", {})
    run.company_name = metadata.get("company_name", run.company_name)
    filing_type_label = metadata.get("filing_type", run.filing_type_key)
    reporting_period = metadata.get("reporting_period", "")
    filing_date = metadata.get("filing_date", "")

    # Generate summary title
    period_suffix = f" ({reporting_period})" if reporting_period else ""
    if filing_date:
        try:
            from datetime import datetime
            date_obj = datetime.fromisoformat(filing_date.replace("Z", "+00:00"))
            year = date_obj.year
            if run.filing_type_key in {"10-K", "20-F"}:
                # 20-F is a foreign annual report — label as a fiscal year like a 10-K.
                period_suffix = f" (FY{year})"
            elif run.filing_type_key == "10-Q":
                quarter = (date_obj.month - 1) // 3 + 1
                period_suffix = f" (Q{quarter} {year})"
        except (ValueError, TypeError):
            pass
    run.summary_title = f"{run.company_name} {filing_type_label} Filing Summary{period_suffix}"


def build_legacy_cards(run: SummaryRun) -> None:
    run.sections = []

    # Key Risks section
    if run.risk_section:
        risk_content_parts = []
        for risk in run.risk_section[:10]:  # Limit to top 10 risks
            if isinstance(risk, dict):
                summary = risk.get("summary", "")
                evidence = risk.get("supporting_evidence", "")
                if summary:
                    bullet = f"• {summary}"
                    if evidence:
                        bullet += f" (Evidence: {evidence[:200]})"
                    risk_content_parts.append(bullet)
        if risk_content_parts:
            run.sections.append({
                "title": "Key Risks",
                "content": "\n".join(risk_content_parts)
            })

    # Financial Overview section
    if run.financial_section:
        financial_content_parts = []
        table = run.financial_section.get("table", [])
        if table:
            for row in table[:10]:  # Limit to top 10 metrics
                if isinstance(row, dict):
                    metric = row.get("metric", "")
                    current = row.get("current_period", "")
                    prior = row.get("prior_period", "")
                    change = row.get("change", "")
                    commentary = row.get("commentary", "")
                    if metric:
                        line = f"• {metric}: {current}"
                        if prior and prior != "Not disclosed":
                            line += f" (vs. {prior})"
                        if change and change != "Not disclosed":
                            line += f" — {change}"
                        if commentary:
                            line += f" — {commentary[:150]}"
                        financial_content_parts.append(line)
        if financial_content_parts:
            run.sections.append({
                "title": "Financial Overview",
                "content": "\n".join(financial_content_parts)
            })

    # Management Commentary section
    if run.management_section:
        run.sections.append({
            "title": "Management Commentary",
            "content": run.management_section[:2000]  # Limit length
        })

    # Strategic Developments section (from guidance and management discussion)
    strategic_parts = []
    if run.guidance_section:
        strategic_parts.append(run.guidance_section[:1000])
    run.guidance_structured = run.sections_info.get("forward_signals", {})
    if isinstance(run.guidance_structured, dict):
        guidance_text = run.guidance_structured.get("guidance", "")
        drivers = run.guidance_structured.get("known_trends", [])
        if guidance_text and guidance_text != "Not disclosed":
            strategic_parts.append(f"Forward Guidance: {guidance_text}")
        if drivers:
            strategic_parts.append("Known trends: " + "; ".join(str(d) for d in drivers[:5]))
    if strategic_parts:
        run.sections.append({
            "title": "Strategic Developments",
            "content": "\n".join(strategic_parts)
        })


def build_insights(run: SummaryRun) -> None:
    run.insights = {
        "sentiment": "Neutral",
        "growth_drivers": [],
        "risk_signals": []
    }

    # Extract sentiment from the print (v2 §1; was executive_snapshot)
    exec_snapshot = run.sections_info.get("the_print", {})
    if isinstance(exec_snapshot, dict):
        tone = exec_snapshot.get("tone", "neutral")
        if tone:
            # Preserve compound sentiments such as "neutral to positive".
            if isinstance(tone, str):
                if " to " in tone.lower():
                    run.insights["sentiment"] = tone.title()
                else:
                    run.insights["sentiment"] = tone.capitalize()
            else:
                run.insights["sentiment"] = "Neutral"

    if run.guidance_structured and isinstance(run.guidance_structured, dict):
        guidance_tone = run.guidance_structured.get("tone", "")
        if guidance_tone and guidance_tone != run.insights["sentiment"].lower():
            # Combine sentiment if different (e.g., "Neutral to Positive")
            current_sentiment = run.insights["sentiment"].lower()
            if current_sentiment != guidance_tone:
                run.insights["sentiment"] = f"{run.insights['sentiment']} to {guidance_tone.capitalize()}"

    if run.guidance_structured and isinstance(run.guidance_structured, dict):
        drivers = run.guidance_structured.get("known_trends", [])
        if drivers:
            run.insights["growth_drivers"] = [str(d) for d in drivers[:5]]

    if run.risk_section:
        run.insights["risk_signals"] = [
            risk.get("summary", "")[:100]
            for risk in run.risk_section[:5]
            if isinstance(risk, dict) and risk.get("summary")
        ]


def determine_status(run: SummaryRun) -> None:
    run.status = "complete"
    run.message = None
    coverage_ratio = run.coverage_snapshot.get("coverage_ratio", 1.0)
    missing_sections_list = run.coverage_snapshot.get("missing", [])

    # If coverage is low or writer had issues, mark as partial
    if coverage_ratio < 0.5 or run.writer_error or run.writer_fallback_reason:
        run.status = "partial"
        run.message = "Some sections may not have loaded fully."
        if missing_sections_list:
            run.message += f" Missing sections: {', '.join(missing_sections_list[:3])}"

    # A source owner may withhold every presentation card from otherwise valid structured
    # output (for example, an ungrounded Risks item). Treat the response as unusable only when
    # the provider returned no covered structured section at all.
    if not run.sections and run.covered_sections == 0:
        run.status = "error"
        run.message = "Unable to retrieve this filing at the moment — please try again shortly."

    # If processing stopped mid-way but we have some sections, mark as partial
    if len(run.sections) > 0 and coverage_ratio < 0.7:
        run.status = "partial"
        if not run.message:
            run.message = "Some sections may not have loaded fully."

