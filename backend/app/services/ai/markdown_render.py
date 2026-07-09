"""Deterministic structured-summary rendering + fallbacks for OpenAIService (roadmap S2 façade split).

``_MarkdownRenderMixin`` holds the NON-LLM output path: render Markdown directly from structured
data (``_build_structured_markdown``), coerce a loose payload to a dict (``_coerce_summary_dict``),
and fill any sections the model left empty with deterministic, XBRL-grounded fallbacks
(``_apply_structured_fallbacks``). Mixed into ``OpenAIService``; methods resolve through ``self``.
Extracted verbatim.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.services.ai.fi_signals import fi_components_present
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
        """Backfill v2 sections from standardized XBRL: the anchor sections when empty, plus the
        cash-flow bridge and working-capital position.

        Tier-3.1: this used to fill all nine v1 sections; under the v2 taxonomy the model reliably
        populates the nine v2 sections (and a downstream guard filters to them), so the anchors need
        only a minimal floor — a lead (``the_print``) and a P&L table (``results_that_matter``) so a
        degraded summary still grounds in the standardized figures and clears the coverage bar.
        ``balance_sheet_liquidity`` is the exception: v1 surfaced the operating/investing/financing
        cash flows and current assets/liabilities deterministically (via
        ``financial_highlights.cash_flow[]`` / ``balance_sheet[]``); the v2 taxonomy routes them into
        prose the model tends to write WITHOUT figures, so those numbers are injected here too
        (numbers from code) to hold the numeric-recall floor. Tier-5.1 adds ``earnings_quality.
        cash_conversion`` (the NI-vs-CFO accrual read + free cash flow) on the same principle. The
        remaining analytical feeds (red-flag scan, ROIC) land later.
        """
        # Currency-aware money formatter: bare "$" for USD/domestic filers, ISO-prefixed for foreign
        # issuers (e.g. "EUR 30.6B", "CNY 30.6B"). Standardized XBRL values are in the filer's
        # reporting currency, so the deterministic figures below must never mislabel a non-USD filer
        # as dollars — a ~7x distortion the numeric scorers can't catch, and a currency-consistency hit.
        reporting_currency = (xbrl_metrics or {}).get("reporting_currency")
        money_prefix = (
            "$" if str(reporting_currency or "USD").upper() == "USD"
            else f"{str(reporting_currency).upper()} "
        )

        def format_currency(value: Optional[float]) -> Optional[str]:
            if value is None:
                return None
            try:
                abs_value = abs(value)
                if abs_value >= 1_000_000_000:
                    return f"{money_prefix}{value / 1_000_000_000:.1f}B"
                if abs_value >= 1_000_000:
                    return f"{money_prefix}{value / 1_000_000:.1f}M"
                if abs_value >= 1_000:
                    return f"{money_prefix}{value / 1_000:.1f}K"
                return f"{money_prefix}{value:,.0f}"
            except Exception:
                return None

        def metric_entry(metric_key: str) -> Dict[str, Optional[str]]:
            metric = (xbrl_metrics or {}).get(metric_key)
            if not isinstance(metric, dict):
                metric = {}
            current = metric.get("current") if isinstance(metric.get("current"), dict) else {}
            prior = metric.get("prior") if isinstance(metric.get("prior"), dict) else {}
            return {
                "current": format_currency(current.get("value")),
                "current_period": current.get("period"),
                "prior": format_currency(prior.get("value")),
            }

        def raw_period(metric_key: str, period: str) -> Optional[float]:
            """Raw float for a standardized metric's ``current``/``prior`` period (ratio math + checks)."""
            metric = (xbrl_metrics or {}).get(metric_key)
            block = metric.get(period) if isinstance(metric, dict) else None
            value = block.get("value") if isinstance(block, dict) else None
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return None
            return float(value)

        def raw_current(metric_key: str) -> Optional[float]:
            return raw_period(metric_key, "current")

        def raw_prior(metric_key: str) -> Optional[float]:
            return raw_period(metric_key, "prior")

        metadata = metadata or {}
        company_name = metadata.get("company_name", "The company")
        reporting_period = metadata.get("reporting_period", "the reported period")
        revenue_info = metric_entry("revenue")
        income_info = metric_entry("net_income")

        if self._section_is_empty(sections.get("the_print")):
            takeaways = [p for p in (
                (f"Revenue of {revenue_info['current']} for {revenue_info['current_period']}"
                 if revenue_info["current"] and revenue_info["current_period"] else None),
                (f"Net income of {income_info['current']}" if income_info["current"] else None),
            ) if p]
            sections["the_print"] = {
                "headline": (f"{company_name} reported standardized results for {reporting_period}."
                             if takeaways else
                             f"{company_name} filing provided limited standardized detail."),
                "key_takeaways": takeaways or ["Not disclosed—standardized metrics were not extracted."],
                "what_changed": "",
                "tone": "neutral",
                "source_section_ref": "Standardized XBRL financial data",
            }

        if self._section_is_empty(sections.get("results_that_matter")):
            table = [
                {"metric": label, "current_period": info["current"],
                 "prior_period": info["prior"] or "", "change": "", "commentary": ""}
                for label, info in (("Revenue", revenue_info), ("Net income", income_info))
                if info["current"]
            ]
            if table:
                sections["results_that_matter"] = {
                    "table": table,
                    "source_section_ref": "Standardized XBRL financial data",
                }

        # balance_sheet_liquidity: author the cash-flow statement bridge + working-capital position
        # from standardized XBRL whenever the figures exist. These two fields ARE their figures, so
        # code owns them (numbers from code) — the model keeps `leverage` + `liquidity` for qualitative
        # colour. A presence check on the field is unreliable: the model often writes an UNRELATED "$"
        # figure (a cash balance, total debt) there, which would falsely suppress the specific facts.
        # Holds the numeric-recall floor the v2 cutover dropped (investing/financing cash flow, current
        # assets/liabilities — measured recall 0.84 -> 0.74 before this).
        bsl = sections.get("balance_sheet_liquidity")
        if not isinstance(bsl, dict):
            bsl = {}
        current_assets = format_currency(raw_current("current_assets"))
        current_liabilities = format_currency(raw_current("current_liabilities"))
        if current_assets or current_liabilities:
            ca_v, cl_v = raw_current("current_assets"), raw_current("current_liabilities")
            # Denominator must be a non-zero number (guards div-by-zero); the numerator may legitimately
            # be zero, so gate it on presence (is not None), not truthiness.
            ratio = f" (current ratio {ca_v / cl_v:.2f}x)" if (ca_v is not None and cl_v) else ""
            wc = (
                f"Current assets {current_assets or 'Not disclosed'} vs. current liabilities "
                f"{current_liabilities or 'Not disclosed'}{ratio}."
            )
            # Restore the schema's YoY-direction promise (and surface the prior-period facts) when the
            # standardized metrics carry a prior period — the current-only line otherwise drops it.
            prior_ca = format_currency(raw_prior("current_assets"))
            prior_cl = format_currency(raw_prior("current_liabilities"))
            if prior_ca and prior_cl:
                pca_v, pcl_v = raw_prior("current_assets"), raw_prior("current_liabilities")
                prior_ratio = f" ({pca_v / pcl_v:.2f}x)" if (pca_v is not None and pcl_v) else ""
                wc += f" A year earlier: {prior_ca} vs. {prior_cl}{prior_ratio}."
            bsl["working_capital"] = wc
        cash_legs = [
            (label, format_currency(raw_current(key)))
            for label, key in (
                ("operating", "operating_cash_flow"),
                ("investing", "investing_cash_flow"),
                ("financing", "financing_cash_flow"),
            )
        ]
        if any(val for _, val in cash_legs):
            bsl["cash_flow"] = "Cash flow — " + ", ".join(
                f"{label} {val}" for label, val in cash_legs if val
            ) + "."
        if bsl:
            sections["balance_sheet_liquidity"] = bsl

        # earnings_quality.cash_conversion: author the NI-vs-CFO accrual read + free cash flow from
        # standardized XBRL (numbers from code). The cash-conversion RATIO (operating cash flow / net
        # income) is a derived relationship present in no single XBRL magnitude, and the model tends to
        # write this field WITHOUT the figures — so code owns it, mirroring the cash_flow bridge above.
        # ONE-HOME: state the RATIO (or, on a loss, the cash-vs-loss read) + FCF here, never re-quote the
        # OCF/NI dollar levels (their homes are §8 cash_flow / §2 results). Suppressed for financial
        # institutions — NI-vs-CFO and a capex-based
        # FCF are meaningless there (unclassified balance sheet, lending/deposit-driven cash flow) — gated
        # on the SAME predicate as the bank grounding NOTE (xbrl_narrative) so instruction and output stay
        # aligned. The model keeps operating_vs_one_time + red_flags (qualitative, no standardized feed).
        if not fi_components_present(xbrl_metrics):
            ni_v = raw_current("net_income")
            ocf_v = raw_current("operating_cash_flow")
            fcf = format_currency(raw_current("free_cash_flow"))
            parts: List[str] = []
            if ni_v is not None and ocf_v is not None and ni_v > 0:
                # Positive net income: the conversion multiple IS the accrual read. A negative OCF
                # against a positive NI stays (a negative multiple — itself a real accrual red flag).
                parts.append(f"operating cash flow was {ocf_v / ni_v:.1f}x net income (cash conversion)")
            elif ni_v is not None and ni_v < 0 and ocf_v is not None and ocf_v > 0:
                # A net LOSS alongside positive operating cash flow — §3's highest-value accrual signal:
                # the business generated cash despite a GAAP loss (non-cash charges/impairments). Stated
                # qualitatively; a "conversion" multiple against a negative denominator is meaningless.
                parts.append("operating cash flow was positive despite a net loss")
            if fcf:
                parts.append(f"free cash flow of {fcf}")
            if parts:
                eq = sections.get("earnings_quality")
                if not isinstance(eq, dict):
                    eq = {}
                line = "; ".join(parts)
                eq["cash_conversion"] = line[0].upper() + line[1:] + "."
                sections["earnings_quality"] = eq

