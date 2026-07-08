"""Deterministic structured-summary rendering + fallbacks for OpenAIService (roadmap S2 façade split).

``_MarkdownRenderMixin`` holds the NON-LLM output path: render Markdown directly from structured
data (``_build_structured_markdown``), coerce a loose payload to a dict (``_coerce_summary_dict``),
and fill any sections the model left empty with deterministic, XBRL-grounded fallbacks
(``_apply_structured_fallbacks``). Mixed into ``OpenAIService``; methods resolve through ``self``.
Extracted verbatim.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.services.ai.normalize import _PLACEHOLDER_STRINGS


def _append_bullet_group(lines: List[str], label: str, items: Any) -> bool:
    """Emit ``- {label}:`` with one nested ``  - item`` bullet per non-empty item.

    Replaces the former ``"; ".join`` collapse (P0-2): "."-terminated model bullets joined with
    "; " rendered the ``.;`` artifact on every web summary, while the PDF serializer
    (``summary_sections``) already emits true bullets for the same fields. Returns True when
    anything was emitted."""
    if isinstance(items, str):  # schema-loose payloads: a bare string is ONE item, not chars
        items = [items]
    cleaned = [str(item).strip() for item in (items or []) if item and str(item).strip()]
    if not cleaned:
        return False
    lines.append(f"- {label}:")
    lines.extend(f"  - {c}" for c in cleaned)
    return True


class _MarkdownRenderMixin:
    """Deterministic structured→markdown rendering + section fallbacks, mixed into OpenAIService."""

    def _build_structured_markdown(
        self,
        structured_summary: Dict[str, Any],
        failure_reason: Optional[str] = None,
    ) -> str:
        """Render the web summary Markdown directly from structured data.

        This is the PRIMARY web serializer (called unconditionally since the editorial-writer LLM was
        removed), not a fallback — ``business_overview`` is this output, stored and rendered as-is.
        ``failure_reason`` is only set on the rare validation-failure path and prepends a notice.
        """
        metadata = structured_summary.get("metadata", {}) or {}
        sections = structured_summary.get("sections", {}) or {}

        company_name = metadata.get("company_name") or "The company"
        filing_type = metadata.get("filing_type") or "filing"
        reporting_period = metadata.get("reporting_period") or metadata.get("reportingPeriod") or "the reporting period"

        lines: list[str] = []
        if failure_reason:
            lines.append(f"*Auto-generated from structured data because the writer output failed validation ({failure_reason}).*")

        # Executive Summary
        # Guard: a malformed LLM payload can make a section a truthy non-dict (list/str), which
        # `or {}` would pass straight through to `.get()` and crash the fallback renderer. isinstance
        # is the stricter floor.
        exec_section = sections.get("executive_snapshot")
        if not isinstance(exec_section, dict):
            exec_section = {}
        headline = exec_section.get("headline")
        key_points = exec_section.get("key_points") or exec_section.get("keyPoints") or []
        tone = exec_section.get("tone")

        lines.append("## Executive Summary")
        summary_bits: list[str] = []
        if headline:
            summary_bits.append(headline.strip())
        else:
            summary_bits.append(f"{company_name} filed its {filing_type.upper()} covering {reporting_period}.")
        # Only surface tone when it carries signal — "neutral" is the uninformative default and
        # reads as filler, so it is omitted (report-quality Phase 0).
        if tone and str(tone).strip().lower() not in ("neutral", ""):
            summary_bits.append(f"Management's disclosed tone was {str(tone).strip().lower()}.")
        lines.append(" ".join(summary_bits).strip())
        # True bullets, not a "; "-joined prose run (P0-2) — parity with the PDF serializer.
        if isinstance(key_points, str):  # schema-loose payloads: ONE point, not characters
            key_points = [key_points]
        for point in key_points:
            cleaned_point = (str(point) if point else "").strip()
            if cleaned_point:
                lines.append(f"- {cleaned_point}")

        # Financials
        financials = sections.get("financial_highlights")
        if not isinstance(financials, dict):
            financials = {}
        table_rows = financials.get("table") or []
        profitability = financials.get("profitability") or []
        cash_flow = financials.get("cash_flow") or financials.get("cashFlow") or []
        balance_sheet = financials.get("balance_sheet") or financials.get("balanceSheet") or []

        lines.append("\n## Financials")
        financial_lines_added = False
        if table_rows:
            for row in table_rows:
                if not isinstance(row, dict):
                    continue
                metric = row.get("metric")
                if not metric:
                    continue
                current_period = row.get("current_period") or row.get("currentPeriod") or "Not disclosed"
                prior_period = row.get("prior_period") or row.get("priorPeriod")
                change = row.get("change")
                commentary = (row.get("commentary") or "").replace("\n", " ").strip()

                # Bold the metric label + current figure so a reader scanning the page lands on the
                # numbers (render-safe markdown; substring-matchable so eval numeric scorers are
                # unaffected). Only a real value is bolded — never a placeholder ("Not disclosed",
                # "N/A", "—", …), checked against the canonical _PLACEHOLDER_STRINGS set.
                current_disp = (
                    f"**{current_period}**"
                    if isinstance(current_period, str)
                    and current_period.strip().lower() not in _PLACEHOLDER_STRINGS
                    else current_period
                )
                bullet = f"- **{metric}:** {current_disp}"
                if prior_period and prior_period != "Not disclosed":
                    bullet += f" vs. {prior_period}"
                if change and change != "Not disclosed":
                    bullet += f" ({change})"
                if commentary:
                    bullet += f" – {commentary}"
                lines.append(bullet)
                financial_lines_added = True
        financial_lines_added = _append_bullet_group(lines, "Profitability", profitability) or financial_lines_added
        financial_lines_added = _append_bullet_group(lines, "Cash flow", cash_flow) or financial_lines_added
        financial_lines_added = _append_bullet_group(lines, "Balance sheet", balance_sheet) or financial_lines_added
        if not financial_lines_added:
            lines.append("- Key financial metrics were not disclosed in the structured extract.")

        # Risks
        lines.append("\n## Risks")
        risks = sections.get("risk_factors") or []
        if risks:
            for risk in risks:
                if not isinstance(risk, dict):
                    continue
                summary = (risk.get("summary") or risk.get("title") or "Risk factor not specified").strip()
                evidence = risk.get("supporting_evidence") or risk.get("supportingEvidence")
                lines.append(f"- {summary}")
                # Supporting evidence as a subordinate detail, not an inline "(Evidence: …)" scaffold
                # wrapper (T1.1). The text (and any figures in it) is preserved; T4 replaces this with
                # an anchored citation chip.
                evidence_text = str(evidence).strip() if evidence else ""
                if evidence_text:
                    lines.append(f"  - {evidence_text}")
        else:
            lines.append("- No material incremental risks were highlighted beyond routine disclosures.")

        # Management Commentary
        lines.append("\n## Management Commentary")
        mgmt = sections.get("management_discussion_insights")
        if not isinstance(mgmt, dict):
            mgmt = {}
        themes = mgmt.get("themes") or []
        capital_allocation = mgmt.get("capital_allocation") or mgmt.get("capitalAllocation") or []
        quotes = mgmt.get("quotes") or []
        mgmt_added = False
        mgmt_added = _append_bullet_group(lines, "Themes", themes) or mgmt_added
        mgmt_added = _append_bullet_group(lines, "Capital allocation", capital_allocation) or mgmt_added
        if quotes:
            for quote in quotes:
                if isinstance(quote, dict):
                    text = (quote.get("quote") or "").strip()
                    speaker = (quote.get("speaker") or "").strip()
                    if text:
                        mgmt_added = True
                        if speaker:
                            lines.append(f'> "{text}" – {speaker}')
                        else:
                            lines.append(f'> "{text}"')
        if not mgmt_added:
            lines.append("- Management commentary was limited in the structured extract.")

        # Outlook
        lines.append("\n## Outlook")
        outlook = sections.get("guidance_outlook")
        if not isinstance(outlook, dict):
            outlook = {}
        guidance = outlook.get("guidance")
        tone = outlook.get("tone")
        drivers = outlook.get("drivers") or []
        watch_items = outlook.get("watch_items") or outlook.get("watchItems") or []

        outlook_added = False
        # Render the guidance text as prose, not a "- Guidance:" field-name scaffold (T1.1).
        if guidance and guidance != "Not disclosed":
            lines.append(f"- {str(guidance).strip()}")
            outlook_added = True
        # Suppress the uninformative "neutral" tone (parity with the exec-snapshot rule at :72) and
        # render a real tone as prose rather than a "- Tone:" field label.
        if tone and str(tone).strip().lower() not in ("neutral", ""):
            lines.append(f"- Management's outlook tone was {str(tone).strip().lower()}.")
            outlook_added = True
        outlook_added = _append_bullet_group(lines, "Drivers", drivers) or outlook_added
        outlook_added = _append_bullet_group(lines, "Watch items", watch_items) or outlook_added

        if not outlook_added:
            lines.append("- Guidance was not disclosed; monitor subsequent updates for direction.")

        return "\n".join(lines).strip()

    @staticmethod
    def _coerce_summary_dict(data: Any) -> Dict[str, Any]:
        """Normalize parsed model JSON to the expected object shape.

        Some models (especially without a strict schema) return a top-level array, or a
        single-element array wrapping the object. Without this guard, ``data.get(...)`` raises
        ``'list' object has no attribute 'get'`` and the whole summary fails with the user-facing
        "Unable to retrieve this filing" error. Coercing here keeps the pipeline alive so the
        structured fallbacks can fill any gaps instead of crashing.
        """
        if isinstance(data, dict):
            return data
        if isinstance(data, list):
            for item in data:  # prefer an element that looks like the summary object
                if isinstance(item, dict) and ("sections" in item or "metadata" in item):
                    return item
            for item in data:
                if isinstance(item, dict):
                    return item
        return {}

    def _apply_structured_fallbacks(
        self,
        sections: Dict[str, Any],
        metadata: Dict[str, Any],
        xbrl_metrics: Optional[Dict[str, Any]],
    ) -> None:
        def format_currency(value: Optional[float]) -> Optional[str]:
            if value is None:
                return None
            try:
                abs_value = abs(value)
                if abs_value >= 1_000_000_000:
                    return f"${value / 1_000_000_000:.1f}B"
                if abs_value >= 1_000_000:
                    return f"${value / 1_000_000:.1f}M"
                if abs_value >= 1_000:
                    return f"${value / 1_000:.1f}K"
                return f"${value:,.0f}"
            except Exception:
                return None

        def format_percent(value: Optional[float]) -> Optional[str]:
            if value is None:
                return None
            try:
                return f"{value:.1f}%"
            except Exception:
                return None

        def metric_entry(metric_key: str) -> Dict[str, Any]:
            # Guard each level: a truthy non-dict metric/current/prior (malformed metrics payload)
            # would slip past `or {}` and crash `.get()`.
            metric = (xbrl_metrics or {}).get(metric_key)
            if not isinstance(metric, dict):
                metric = {}
            current = metric.get("current")
            if not isinstance(current, dict):
                current = {}
            prior = metric.get("prior")
            if not isinstance(prior, dict):
                prior = {}
            formatted_current = format_currency(current.get("value")) if metric_key != "net_margin" else format_percent(current.get("value"))
            formatted_prior = format_currency(prior.get("value")) if metric_key != "net_margin" else format_percent(prior.get("value"))
            return {
                "current": formatted_current,
                "current_period": current.get("period"),
                "prior": formatted_prior,
                "prior_period": prior.get("period"),
            }

        metadata = metadata or {}
        company_name = metadata.get("company_name", "The company")
        reporting_period = metadata.get("reporting_period", "the reported period")

        revenue_info = metric_entry("revenue")
        income_info = metric_entry("net_income")
        margin_info = metric_entry("net_margin")

        if self._section_is_empty(sections.get("executive_snapshot")):
            headline_parts: List[str] = []
            if revenue_info["current"] and revenue_info["current_period"]:
                headline_parts.append(
                    f"Revenue at {revenue_info['current']} for {revenue_info['current_period']}"
                )
            if income_info["current"] and income_info["current_period"]:
                headline_parts.append(
                    f"Net income reported at {income_info['current']}"
                )
            headline = (
                f"{company_name} filing highlights standardized metrics" if headline_parts else f"{company_name} filing provided limited qualitative detail"
            )
            key_points: List[str] = []
            if headline_parts:
                key_points.extend(headline_parts)
            else:
                key_points.append("Core filing excerpts offered minimal narrative detail; review standardized data for context.")
            if margin_info["current"]:
                key_points.append(f"Net margin {margin_info['current']} (from XBRL data).")
            sections["executive_snapshot"] = {
                "headline": headline,
                "key_points": key_points,
                "tone": "neutral",
            }

        if self._section_is_empty(sections.get("financial_highlights")):
            table: List[Dict[str, Any]] = []
            if revenue_info["current"]:
                table.append(
                    {
                        "metric": "Revenue",
                        "current_period": revenue_info["current"],
                        "prior_period": revenue_info["prior"] or "Not disclosed",
                        "change": "Not disclosed",
                        "commentary": f"Reported for {revenue_info['current_period'] or reporting_period}.",
                    }
                )
            if income_info["current"]:
                table.append(
                    {
                        "metric": "Net Income",
                        "current_period": income_info["current"],
                        "prior_period": income_info["prior"] or "Not disclosed",
                        "change": "Not disclosed",
                        "commentary": f"Latest standardized value for {income_info['current_period'] or reporting_period}.",
                    }
                )
            if margin_info["current"]:
                table.append(
                    {
                        "metric": "Net Margin",
                        "current_period": margin_info["current"],
                        "prior_period": margin_info["prior"] or "Not disclosed",
                        "change": "Not disclosed",
                        "commentary": "Derived from aligned revenue and income figures.",
                    }
                )
            if not table:
                table.append(
                    {
                        "metric": "Summary",
                        "current_period": "Not disclosed",
                        "prior_period": "Not disclosed",
                        "change": "Not disclosed",
                        "commentary": "Filing excerpts omitted detailed financial metrics; rely on management updates for figures.",
                    }
                )
            sections["financial_highlights"] = {
                "table": table,
                "profitability": [
                    margin_info["current"]
                    and f"Net margin approximately {margin_info['current']} based on standardized data."
                    or "Profitability commentary unavailable in provided excerpts."
                ],
                "cash_flow": [
                    "Cash flow figures were not captured from this filing's extracted text."
                ],
                "balance_sheet": [
                    "Balance sheet figures were not captured from this filing's extracted text."
                ],
            }

        if self._section_is_empty(sections.get("risk_factors")):
            # If no new risks extracted, provide more helpful context
            sections["risk_factors"] = [
                {
                    "summary": "Risk factors were not extracted from this filing.",
                    "supporting_evidence": "",
                    "materiality": "unknown",
                    "source_section_ref": "Item 1A. Risk Factors",
                }
            ]

        if self._section_is_empty(sections.get("management_discussion_insights")):
            # Provide more useful fallback that still offers value
            sections["management_discussion_insights"] = {
                "themes": [
                    "Management discussion was not extracted from this filing."
                ],
                "quotes": [],
                "capital_allocation": [
                    "Capital allocation detail was not extracted from this filing."
                ],
                "source_section_ref": "Item 2. MD&A",
            }

        if self._section_is_empty(sections.get("segment_performance")):
            sections["segment_performance"] = [
                {
                    "segment": "Company-wide",
                    "revenue": revenue_info["current"] or "Not disclosed",
                    "change": "Not disclosed",
                    "commentary": "Segment detail was not present; investors should review full filing tables.",
                    "source_section_ref": "Segment disclosures (not surfaced in sampled excerpts)",
                }
            ]

        if self._section_is_empty(sections.get("liquidity_capital_structure")):
            liquidity_line = "Liquidity figures were not captured from this filing's extracted text."
            sections["liquidity_capital_structure"] = {
                "leverage": "Debt and leverage commentary not captured in sampled passages.",
                "liquidity": liquidity_line,
                "shareholder_returns": [
                    "No explicit reference to dividends or buybacks within the excerpted text."
                ],
                "source_section_ref": "Liquidity and capital resources (not surfaced in sampled excerpts)",
            }

        if self._section_is_empty(sections.get("guidance_outlook")):
            sections["guidance_outlook"] = {
                "guidance": "Guidance was not extracted from this filing.",
                "tone": "neutral",
                "drivers": [
                    "Guidance drivers were not extracted from this filing."
                ],
                "watch_items": [
                    "Earnings call transcript may contain forward-looking commentary not included in SEC filings."
                ],
                "source_section_ref": "Forward-looking statements",
            }

        if self._section_is_empty(sections.get("notable_footnotes")):
            sections["notable_footnotes"] = [
                {
                    "item": "No specific footnotes surfaced in the extracted passages.",
                    "impact": "Review the full filing footnotes for accounting nuances or adjustments.",
                    "source_section_ref": "Footnotes (not surfaced in sampled excerpts)",
                }
            ]

        if self._section_is_empty(sections.get("three_year_trend")):
            trend_summary = (
                revenue_info["current"]
                and f"Latest standardized revenue of {revenue_info['current']} anchors the recent trajectory."
                or "Trend commentary unavailable from excerpts."
            )
            sections["three_year_trend"] = {
                "trend_summary": trend_summary,
                "inflections": [
                    margin_info["current"]
                    and f"Net margin currently at {margin_info['current']} per standardized data."
                    or "No clear inflection points identified from provided text."
                ],
                "compare_prior_period": {
                    "available": bool(revenue_info["prior"] or income_info["prior"]),
                    "insights": [
                        revenue_info["prior"]
                        and f"Prior revenue reference point: {revenue_info['prior']}"
                        or "Prior-period disclosures were not captured.",
                    ],
                },
                "source_section_ref": "Trend discussion (not surfaced in sampled excerpts)",
            }

