"""XBRL "standardized financial data" grounding block for the summary prompt (roadmap 2.6 Phase B).

``build_xbrl_narrative_section`` is the single point that decides which SEC-verified figures the
summary *narrative* may cite. Pure, offline, no AI call — extracted verbatim from
``openai_service`` (roadmap S2 façade split) and re-exported there for existing callers.
"""
from __future__ import annotations

from typing import Optional

from app.services.ai.fi_signals import fi_components_present


# Standardized financial metrics surfaced in the prompt's grounding block, as
# (narrative label, metrics key, format kind). The model is told to quote these verbatim, so this
# whitelist is the single point that decides which SEC-verified figures the *narrative* may cite.
# Keys absent from `xbrl_metrics` are silently skipped, so listing a metric is inert until the
# extractor populates it — the roadmap-2.6 cash-flow/liquidity lines (investing/financing CF,
# current assets/liabilities, working capital, current ratio) only carry values when
# RICHER_FINANCIALS_ENABLED was on at extraction time, so the prompt is byte-for-byte unchanged
# otherwise. Order mirrors the financial statements (CF flows by operating CF; liquidity by assets).
_XBRL_NARRATIVE_SPEC: list[tuple[str, str, str]] = [
    ("Revenue", "revenue", "usd"),
    # Financial-institution revenue components/totals (self-gating — only present for banks/insurers/
    # BDCs). A bank shows Net Interest Income + Non-Interest Income and NO single "Revenue".
    ("Net Interest Income", "net_interest_income", "usd"),
    ("Non-Interest Income", "noninterest_income", "usd"),
    ("Premiums Earned (Net)", "premiums_earned", "usd"),
    ("Net Investment Income", "net_investment_income", "usd"),
    ("Gross Profit", "gross_profit", "usd"),
    ("Operating Income", "operating_income", "usd"), ("Net Income", "net_income", "usd"),
    ("EPS (Basic)", "earnings_per_share", "eps"), ("EPS (Diluted)", "eps_diluted", "eps"),
    ("Gross Margin", "gross_margin", "pct"),
    ("Operating Margin", "operating_margin", "pct"), ("Net Margin", "net_margin", "pct"),
    ("Return on Equity", "return_on_equity", "pct"), ("Return on Assets", "return_on_assets", "pct"),
    ("Operating Cash Flow", "operating_cash_flow", "usd"),
    ("Investing Cash Flow", "investing_cash_flow", "usd"),
    ("Financing Cash Flow", "financing_cash_flow", "usd"),
    ("Capital Expenditures", "capital_expenditures", "usd"),
    ("Free Cash Flow (OCF - CapEx)", "free_cash_flow", "usd"), ("Total Assets", "total_assets", "usd"),
    ("Current Assets", "current_assets", "usd"),
    ("Current Liabilities", "current_liabilities", "usd"),
    ("Working Capital", "working_capital", "usd"),
    ("Current Ratio", "current_ratio", "ratio"),
    ("Cash & Equivalents", "cash_and_equivalents", "usd"),
    ("Long-term Debt", "long_term_debt", "usd"),
    ("Shareholders' Equity", "shareholders_equity", "usd"),
]


def _format_xbrl_metric_value(value: Optional[float], kind: str) -> str:
    """Format a standardized metric for the narrative grounding block."""
    if value is None:
        return "Not disclosed"
    if kind == "pct":
        return f"{value:.1f}%"
    if kind == "ratio":
        return f"{value:.2f}x"  # dimensionless multiple (e.g. current ratio "2.50x") — never $/%
    if kind == "eps":
        return f"{value:,.2f}"
    return f"${value:,.0f}"


def _working_capital_fallback(xbrl_metrics: dict, which: str) -> Optional[dict]:
    """Derive a working-capital {value, period} for period `which` ('current'|'prior') from Current
    Assets - Current Liabilities. Working capital is frequently untagged in XBRL; this fallback keeps
    the liquidity figure available to the summary. Returns None if either side is missing."""
    ca = xbrl_metrics.get("current_assets")
    cl = xbrl_metrics.get("current_liabilities")
    if not isinstance(ca, dict) or not isinstance(cl, dict):
        return None
    ca_p, cl_p = ca.get(which), cl.get(which)
    if not isinstance(ca_p, dict) or not isinstance(cl_p, dict):
        return None
    ca_v, cl_v = ca_p.get("value"), cl_p.get("value")
    # bool is an int subclass — exclude it so a stray True/False can't slip into the arithmetic.
    if (isinstance(ca_v, bool) or isinstance(cl_v, bool)
            or not isinstance(ca_v, (int, float)) or not isinstance(cl_v, (int, float))):
        return None
    return {"value": ca_v - cl_v, "period": ca_p.get("period") or "N/A"}


def build_xbrl_narrative_section(xbrl_metrics: Optional[dict]) -> str:
    """Build the "XBRL STANDARDIZED FINANCIAL DATA" grounding block from standardized metrics.

    Emits one line per `_XBRL_NARRATIVE_SPEC` entry that has a current value; whitelisted-but-absent
    metrics are skipped. Returns "" when there is nothing to surface, so the prompt is byte-for-byte
    unchanged for filings without metrics. The prior period is shown when present, and working
    capital is derived from Current Assets - Current Liabilities when untagged.
    """
    if not isinstance(xbrl_metrics, dict):
        return ""
    rows: list[str] = []
    for label, key, kind in _XBRL_NARRATIVE_SPEC:
        # Defensive: the metrics dict is produced by extract_standardized_metrics (always dict-shaped),
        # but this is a reusable helper in the summary hot path — a non-dict entry/current/prior (a
        # future upstream change or a corrupted cache) must skip, not raise an AttributeError.
        entry = xbrl_metrics.get(key)
        current = entry.get("current") if isinstance(entry, dict) else None
        prior = entry.get("prior") if isinstance(entry, dict) else None

        # Working-capital fallback: XBRL often doesn't tag working capital directly. When it's absent
        # but current assets/liabilities are present, derive it (CA - CL) per period and name the
        # derivation in the label so the model doesn't over-claim it as a reported line item.
        if key == "working_capital" and (not isinstance(current, dict) or current.get("value") is None):
            derived_current = _working_capital_fallback(xbrl_metrics, "current")
            if derived_current is not None:
                current, prior = derived_current, _working_capital_fallback(xbrl_metrics, "prior")
                label = "Working Capital (Current Assets - Current Liabilities)"

        if not isinstance(current, dict) or current.get("value") is None:
            continue
        line = f"- {label}: {_format_xbrl_metric_value(current.get('value'), kind)} (period: {current.get('period') or 'N/A'})"
        if isinstance(prior, dict) and prior.get("value") is not None:
            line += f"; prior: {_format_xbrl_metric_value(prior.get('value'), kind)} ({prior.get('period') or 'N/A'})"
        rows.append(line)
    if not rows:
        return ""
    header = "XBRL STANDARDIZED FINANCIAL DATA (SEC-verified; quote these figures verbatim):"
    body = header + "\n" + "\n".join(rows)
    # Financial-institution guard: a bank has no single "revenue" line (its generic revenue tag is
    # only fee income), so the model must report the components separately instead of inventing a
    # conflated composite — the root of the cross-section revenue mismatch this addresses.
    # Shares fi_components_present with bank_guards and assess_quality (P0-2): the instruction
    # and the checks that judge its output are driven by the same predicate.
    if fi_components_present(xbrl_metrics):
        body += (
            "\nNOTE — financial institution: there is NO single revenue line here. Report Net "
            "Interest Income and Non-Interest Income as the SEPARATE figures given above; do NOT sum "
            'them into, or invent, a single "Revenue" number.'
        )
        # Industrial checklist → bank fabrication: the analyst prompt's working-capital / current-ratio
        # / capex-driven-FCF items have no meaning for a bank (unclassified balance sheet; cash flow is
        # lending/deposit/trading-driven), and the model was observed inventing a "FCF negative due to
        # high capex and working-capital changes" cause on JPM. Swap the checklist here, at the point of
        # grounding, gated on the SAME predicate as the NOTE above so instruction and output-checks stay
        # aligned. No literal "$" — the non-USD relabel below rewrites "$" and must not touch this text.
        body += (
            "\nFINANCIAL-INSTITUTION COVERAGE — this issuer is a bank/financial institution: its "
            "balance sheet is UNCLASSIFIED (no current-asset/current-liability split) and its cash "
            "flows are lending-, deposit-, and trading-driven, not industrial capex. Do NOT compute or "
            "cite working capital, a current ratio, or a capex-based free-cash-flow figure, and NEVER "
            "attribute a cash-flow swing to capex or working capital. Cover instead, ONLY as the filing "
            "discloses them: net interest income and net interest margin; noninterest income and the "
            "noninterest expense / efficiency ratio; provision for credit losses and the "
            "allowance/reserve trend; regulatory capital ratios (e.g. CET1); and deposit and loan growth."
        )
    # Reportable-segment labels (T5.2b): the segment TABLE (revenue / operating income / mix) is
    # machine-authored from XBRL, so the model never writes segment figures — but the qualitative
    # driver behind each segment's move is the model's job. List ONLY the label names (no figures, no
    # derived % — the arch-no-precomputed-deltas-in-grounding lesson) so the model can key its
    # commentary to the code's own row names; the filler merges by exact label and drops anything else.
    seg_rows = xbrl_metrics.get("segments")
    segment_labels = [
        str(r.get("name")).strip() for r in seg_rows
        if isinstance(r, dict) and str(r.get("name") or "").strip()
    ] if isinstance(seg_rows, list) else []
    if len(segment_labels) >= 2:
        body += (
            "\nREPORTABLE SEGMENTS (XBRL; revenue order): " + "; ".join(segment_labels) + ". The "
            "per-segment figure table is filled deterministically from XBRL — in `segments`, provide "
            "ONLY a one-line driver per listed segment as management states it (copy each name EXACTLY "
            "as listed; never restate the segment's own revenue, operating income, or YoY change — the "
            "table carries them; finer-grained product/sub-segment facts are welcome as the filing "
            "discloses them; NEVER add a segment that is not listed here)."
        )
    # Foreign (non-USD) filers: name the reporting currency emphatically, right next to the figures.
    # The generic "don't render non-USD as $" rule in the analyst system prompt is intermittently
    # ignored for less-common currencies (observed ~1/3 on DKK/Novo Nordisk — figures rendered as
    # "$309B" instead of "DKK 309B", a ~7x distortion the currency-agnostic numeric scorers can't
    # catch). A per-figure, currency-NAMED directive at the point of grounding cuts that slip.
    cur = str(xbrl_metrics.get("reporting_currency") or "").strip().upper()
    if cur and cur != "USD":
        # The metric formatter labels every monetary value "$" (it assumes USD), but for a non-USD
        # filer these extracted values are ALREADY in the reporting currency — so the "$" is a
        # mislabel that contradicts the directive below. Relabel the figures with the currency code
        # (only the "usd"-kind rows carry "$"; eps/pct/ratio don't), then prepend the directive
        # (whose own literal "$" is added AFTER the replace, so it's preserved).
        body = body.replace("$", f"{cur} ")
        return (
            f'CURRENCY — this issuer reports in {cur}: render EVERY monetary figure (below and in '
            f'your summary) as "{cur} <amount>" (e.g. "{cur} 941.2B"), NEVER as a bare "$". Use '
            f'"US$" ONLY for a convenience translation the filing itself provides.\n' + body
        )
    return body
