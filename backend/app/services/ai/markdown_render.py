"""Deterministic structured-summary rendering + fallbacks for OpenAIService (roadmap S2 façade split).

``_MarkdownRenderMixin`` holds the NON-LLM output path: render Markdown directly from structured
data (``_build_structured_markdown``), coerce a loose payload to a dict (``_coerce_summary_dict``),
and fill any sections the model left empty with deterministic, XBRL-grounded fallbacks
(``_apply_structured_fallbacks``). Mixed into ``OpenAIService``; methods resolve through ``self``.
Extracted verbatim.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, List, Optional

from app.services.ai.fi_signals import fi_components_present
from app.services.ai.bank_guards import ground_bank_component_rows
from app.services.ai.normalize import _PLACEHOLDER_STRINGS
from app.services.ai.debt_scope import (
    build_debt_scope_view,
    leverage_statement,
    model_leverage_is_admissible,
)
from app.services.ai.xbrl_narrative import cash_flow_basis, return_ratio_basis, returns_ratio_in_band


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

        Legacy v1 renderer and degraded-summary fallback. Current-schema summaries and
        complete-section previews use summary_sections' shared projection.
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
        remaining analytical feed (the red-flag scan) lands later; ROIC was assessed and rejected as underivable (see the value_drivers block).
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

        # The model can populate a total-only table while omitting bank components. Own those
        # figures even in a nonempty table, just as we own the cash-flow bridge below.
        if fi_components_present(xbrl_metrics):
            sections["results_that_matter"] = ground_bank_component_rows(
                sections.get("results_that_matter"), xbrl_metrics
            )

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
            # Instant comparatives are often the preceding year-end, not a year earlier.
            # Date the paired prior balances only when both carry the same usable date.
            prior_ca = format_currency(raw_prior("current_assets"))
            prior_cl = format_currency(raw_prior("current_liabilities"))
            if prior_ca and prior_cl:
                pca_v, pcl_v = raw_prior("current_assets"), raw_prior("current_liabilities")
                ca_metric = (xbrl_metrics or {}).get("current_assets")
                cl_metric = (xbrl_metrics or {}).get("current_liabilities")
                ca_prior = ca_metric.get("prior") if isinstance(ca_metric, dict) else None
                cl_prior = cl_metric.get("prior") if isinstance(cl_metric, dict) else None
                ca_date = ca_prior.get("period") if isinstance(ca_prior, dict) else None
                cl_date = cl_prior.get("period") if isinstance(cl_prior, dict) else None
                prior_label = "Prior reported balance sheet"
                if isinstance(ca_date, str) and ca_date == cl_date:
                    try:
                        prior_label += f" as of {date.fromisoformat(ca_date).isoformat()}"
                    except ValueError:
                        pass  # Legacy labels (e.g. FY25) do not establish an actual balance date.
                # Do not combine explicitly different balance dates into one prior current ratio.
                same_or_unknown_date = not (ca_date and cl_date) or ca_date == cl_date
                prior_ratio = (
                    f" ({pca_v / pcl_v:.2f}x)"
                    if pca_v is not None and pcl_v and same_or_unknown_date else ""
                )
                wc += f" {prior_label}: {prior_ca} vs. {prior_cl}{prior_ratio}."
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
        # balance_sheet_liquidity.leverage: CODE-OWNED, from source-qualified debt evidence.
        #
        # This field's own schema description is "<total debt vs cash / equity; net position>" — it
        # is a numeric scope claim end to end, and the retained outcomes show the model cannot make
        # it safely: "Total debt was $38.2B" against a filing whose only verifiable balance is
        # $34,624M of NONCURRENT debt (short-term borrowings still missing), "cash ... exceed total
        # debt" on a scope short two components, a current-plus-noncurrent concept relabelled
        # "long-term debt" with a separate current figure added beside it, and a "cash net of debt"
        # read mixing a finance subsidiary with the consolidated entity. A correct block beside that
        # prose is not a fix, so ownership is an invariant here exactly as it is for
        # `cash_conversion`: the field is machine-authored or absent, never model-authored.
        #
        # Model prose is not discarded wholesale, though. Leverage text that makes NO debt or
        # leverage claim (an equity / asset / cash read the source statement does not cover) is
        # genuine analysis and is kept verbatim after the source statement; `debt_scope` judges the
        # whole field, so no sentence is rewritten and no clause is relabelled. And the replacement
        # is never silent: the statement names the scope the filing DOES establish and the bands it
        # does not, so missing debt reads as unknown rather than zero or net cash.
        #
        # A section is not CREATED merely to say debt is unverifiable: with no debt evidence and an
        # otherwise empty §8 there is nothing to qualify, and authoring anyway would flip an empty
        # section to "covered" on that sentence alone.
        debt_view = build_debt_scope_view(xbrl_metrics)
        if debt_view.has_evidence or bsl:
            model_leverage = bsl.get("leverage")
            bsl["leverage"] = leverage_statement(
                debt_view,
                format_currency,
                model_leverage if model_leverage_is_admissible(model_leverage) else None,
            )

        if bsl:
            sections["balance_sheet_liquidity"] = bsl

        # earnings_quality.cash_conversion: author the NI-vs-CFO accrual read + free cash flow from
        # standardized XBRL (numbers from code). The cash-conversion RATIO (operating cash flow / net
        # income) is a derived relationship present in no single XBRL magnitude, and the model tends to
        # write this field WITHOUT the figures — so code owns it, mirroring the cash_flow bridge above.
        # ONE-HOME: state the RATIO (or, on a loss, the cash-vs-loss read) + FCF here, never re-quote the
        # OCF/NI dollar levels (their homes are §8 cash_flow / §2 results). Suppressed for financial
        # institutions — NI-vs-CFO and a capex-based FCF are meaningless there (unclassified balance sheet,
        # lending/deposit-driven cash flow) — gated on the SAME predicate as the bank grounding NOTE
        # (xbrl_narrative) so instruction and output stay aligned. The model keeps operating_vs_one_time +
        # red_flags (qualitative, no standardized feed).
        #
        # Field OWNERSHIP is an invariant, not a tendency: strip any stray model-provided cash_conversion
        # FIRST, on every path. The empty-section filter is section-level (T3.1 decision #1 — the model
        # emits extra keys no matter the prompt), so a stray cash_conversion would otherwise survive AND —
        # since it's now excluded from the figure_trace gate — render UNPOLICED. That bites hardest on the
        # two paths where the filler does not author: banks (always suppressed — where the T3.2 readout
        # showed model figure behaviour is worst) and thin-XBRL filers (nothing computable). So the field
        # is always machine-authored OR absent, never model-authored.
        eq = sections.get("earnings_quality")
        if isinstance(eq, dict):
            eq.pop("cash_conversion", None)
        if not fi_components_present(xbrl_metrics):
            ni_v = raw_current("net_income")
            ocf_v = raw_current("operating_cash_flow")
            fcf = format_currency(raw_current("free_cash_flow"))
            parts: List[str] = []
            if ni_v is not None and ocf_v is not None and ni_v > 0:
                ratio = ocf_v / ni_v
                if -10.0 <= ratio <= 10.0:
                    # Positive net income in a meaningful band: the multiple IS the accrual read. A
                    # negative OCF against a positive NI stays (a negative multiple — a real red flag).
                    parts.append(f"operating cash flow was {ratio:.1f}x net income (cash conversion)")
                elif ratio > 10.0:
                    # Near-breakeven NI: the tiny denominator dominates, so the multiple (e.g. 250x) is
                    # analytically noise. Keep the signal (cash far exceeding income) qualitatively.
                    parts.append("operating cash flow far exceeded net income")
                else:  # ratio < -10.0: a large operating cash OUTFLOW against a small positive income
                    parts.append("operating cash flow was negative despite positive net income")
            elif ni_v is not None and ni_v < 0 and ocf_v is not None and ocf_v > 0:
                # A net LOSS alongside positive operating cash flow — §3's highest-value accrual signal:
                # the business generated cash despite a GAAP loss (non-cash charges/impairments). Stated
                # qualitatively; a "conversion" multiple against a negative denominator is meaningless.
                parts.append("operating cash flow was positive despite a net loss")
            if fcf:
                parts.append(f"free cash flow of {fcf} ({cash_flow_basis('free_cash_flow')})")
            if parts:
                if not isinstance(eq, dict):
                    eq = {}
                line = "; ".join(parts)
                eq["cash_conversion"] = line[0].upper() + line[1:] + "."
                sections["earnings_quality"] = eq

        # value_drivers (§4, T5.3): two machine-authored fields — numbers from code, the value VERDICT
        # stays the model's (`capital_allocation` prose + `highlights`).
        #
        # `shareholder_returns` (filler sole author; never in the schema): the §4-homed capital-
        # allocation dollars — dividends paid, share repurchases, capex — current vs prior,
        # currency-aware, cash-paid magnitudes as tagged. ONE-HOME: never FCF (§3's home) nor the
        # financing/investing cash-flow TOTALS (§8's home; these are components, a different figure).
        # Zero-valued current clauses are omitted (a "TWD 0" repurchase line is noise, not signal).
        #
        # `returns_on_capital` (T5.1 code-owns): ROE/ROA level + prior — the honest filing-derivable
        # returns read. The prompt previously asked for ROIC, which is never a filing line item and
        # absent from the grounding (a standing fabrication invitation, and full ROIC founders on
        # short-term debt being a multi-concept sum — understating invested capital OVERSTATES it).
        # Deliberately NOT gated on fi_components_present: ROE/ROA is explicitly the FI-appropriate
        # read, so this authors for banks too. Ownership invariant on both fields: pop the model's
        # value FIRST on every path — always machine-authored or absent, never model-authored.
        vd = sections.get("value_drivers")
        if not isinstance(vd, dict):
            vd = {}
        vd.pop("shareholder_returns", None)
        vd.pop("returns_on_capital", None)

        def _flow_clause(label: str, key: str) -> Optional[str]:
            # abs(): these are cash-PAID magnitudes; a filer that tags the outflow as negative (the
            # documented population the FCF derivation abs()es) must not render "capital expenditures
            # $-1.2B" — a tagging artifact presented as if the sign were semantic, and internally
            # inconsistent with §3's abs()-based FCF in the same summary.
            current = raw_current(key)
            if not current:  # None or 0.0 → omit (zero cash paid is noise in a returns line)
                return None
            clause = f"{label} {format_currency(abs(current))}"
            prior = raw_prior(key)
            if prior:
                clause += f" (prior {format_currency(abs(prior))})"
            return clause

        returned = [c for c in (_flow_clause("dividends paid", "dividends_paid"),
                                _flow_clause("share repurchases", "share_repurchases")) if c]
        capex_clause = _flow_clause("capital expenditures", "capital_expenditures")
        if capex_clause:
            capex_clause += f" ({cash_flow_basis('capital_expenditures')})"
        if returned:
            line = "Capital returned — " + ", ".join(returned)
            if capex_clause:
                line += f"; {capex_clause}"
            vd["shareholder_returns"] = line + "."
        elif capex_clause:
            # No shareholder returns this period (or none tagged): the capex line still grounds §4.
            vd["shareholder_returns"] = capex_clause[0].upper() + capex_clause[1:] + "."

        roe = (xbrl_metrics or {}).get("return_on_equity")
        roa = (xbrl_metrics or {}).get("return_on_assets")

        def _ratio_clause(key: str, label: str, metric: Any) -> Optional[str]:
            # Band guard (the cash_conversion ±10x precedent): a |ratio| beyond the shared
            # RETURNS_RATIO_BAND_PCT almost always means a near-zero denominator (HD's ~$1B equity
            # → "1644.4%") — arithmetically true, analytically noise. Honest negatives inside the
            # band (a loss against positive equity, e.g. -12.3%) stay; the sign-flip class is
            # already killed at the derivation (equity > 0). `returns_ratio_in_band` is the SAME
            # predicate that bands these two metrics out of the grounding narrative (#621 staff
            # review) — one constant, two surfaces, no drift.
            if not isinstance(metric, dict):
                return None
            current = metric.get("current") if isinstance(metric.get("current"), dict) else {}
            value = current.get("value")
            if not returns_ratio_in_band(value):
                return None
            clause = f"{label} {value:.1f}%"
            prior = metric.get("prior") if isinstance(metric.get("prior"), dict) else {}
            prior_value = prior.get("value")
            if returns_ratio_in_band(prior_value):
                clause += f" (prior {prior_value:.1f}%)"
            return f"{clause} ({return_ratio_basis(key)})"

        ratio_clauses = [c for c in (_ratio_clause("return_on_equity", "return on equity was", roe),
                                     _ratio_clause("return_on_assets", "return on assets", roa)) if c]
        if ratio_clauses:
            line = "; ".join(ratio_clauses)
            vd["returns_on_capital"] = line[0].upper() + line[1:] + "."
        if vd:
            sections["value_drivers"] = vd

        # segments (§7): author the reportable-segment table from standardized XBRL (T5.2). Code owns the
        # FIGURES — per-segment revenue, operating income, YoY revenue change — plus a same-row
        # operating margin; code owns every segment FIGURE and the
        # section key. Ownership invariant (mirrors cash_conversion): pop any model segments FIRST so a
        # model row can never render — but HARVEST its commentary before discarding (T5.2b hybrid: the
        # model contributes ONLY a qualitative driver per row, keyed by the code's own labels via the
        # REPORTABLE SEGMENTS grounding list; unmatched labels are dropped, and the model can never
        # create a row or the section key). Empty for single-segment / undimensioned / bank filers.
        model_segments = sections.pop("segments", None)
        model_notes: Dict[str, str] = {}
        if isinstance(model_segments, list):
            for row in model_segments:
                if not isinstance(row, dict):
                    continue
                # Strings only — a schema-loose dict/list here would str() into a Python repr in the
                # user-facing cell (every other render field drops non-strings the same way).
                raw_label = row.get("segment") or row.get("name")
                raw_note = row.get("commentary")
                if not isinstance(raw_label, str) or not isinstance(raw_note, str):
                    continue
                label = raw_label.strip()
                # Strip a dangling separator prefix (em/en dash, or a "- " bullet) WITHOUT eating a
                # legitimate leading minus sign — "-3% FX headwind" must keep its sign.
                note = re.sub(r"^[\s—–]+", "", raw_note.strip())
                note = re.sub(r"^-\s+", "", note).strip()
                low = note.lower()
                if not label or not note or low in _PLACEHOLDER_STRINGS \
                        or low.startswith(("not disclosed", "not applicable", "n/a")) \
                        or re.match(r"none\b", low):
                    continue
                # Duplicate labels: last write wins (the model's final row for a name supersedes).
                model_notes[label.casefold()] = note
        seg_rows = (xbrl_metrics or {}).get("segments")

        def _seg_num(value: Any) -> Optional[float]:
            return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None

        named = (
            [r for r in seg_rows if isinstance(r, dict) and str(r.get("name") or "").strip()]
            if isinstance(seg_rows, list) else []
        )
        if named:
            # Flat members may include both a parent and its children (e.g. Intel Products and
            # CCG/DCAI). Without hierarchy, their sum is not a valid revenue-mix denominator.
            authored: List[Dict[str, Any]] = []
            for r in named:
                name = str(r.get("name")).strip()
                rev = _seg_num(r.get("revenue"))
                prior = _seg_num(r.get("revenue_prior"))
                opinc = _seg_num(r.get("operating_income"))
                change = f"{(rev - prior) / abs(prior) * 100.0:+.1f}%" if rev is not None and prior else ""
                # Same-row margin first, model driver appended; hierarchy is not needed to divide
                # a row's operating income by its own revenue. Preserve commentary-only rows too.
                det = f"{opinc / rev * 100.0:.0f}% operating margin" if rev and opinc is not None else ""
                note = model_notes.get(name.casefold(), "")
                commentary = f"{det} — {note}" if det and note else (det or note)
                authored.append({
                    "segment": name,
                    "revenue": format_currency(rev) or "",
                    "operating_income": format_currency(opinc) or "",
                    "change": change,
                    "commentary": commentary,
                    "source_section_ref": "Segment information (XBRL)",
                })
            if authored:
                sections["segments"] = authored

