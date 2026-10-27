"""Standardized XBRL metrics, in the service's original calculation and insertion order."""

from typing import Any, Dict, List, Optional, Tuple

from .ads_ratios import build_per_ads_eps
from .models import MetricChange


def normalise_series(entries: List[Dict]) -> List[Dict]:
    cleaned = []
    seen_periods = set()
    sorted_entries = sorted(
        (e for e in entries if e.get("period") and e.get("value") is not None),
        key=lambda x: x.get("period"),
        reverse=True,
    )
    for entry in sorted_entries:
        period = entry.get("period")
        if period in seen_periods:
            continue
        seen_periods.add(period)
        cleaned.append({
            "period": period,
            "value": entry.get("value"),
            "form": entry.get("form"),
            "currency": entry.get("currency"),
            # ``accn``, the filing a companyfacts fact came from, rides through where it was recorded, so a
            # comparison can refuse another filing's fact (E184); the filing's own instance records none.
            **{key: entry[key] for key in ("fiscal_year", "fiscal_period", "period_start", "accn")
               if entry.get(key) is not None},
            # raw_tag rides through so financial_fact records which XBRL concept a value came
            # from (audit trail) and the change report can detect a concept that flips
            # between filings. None for legacy/pre-fix series.
            "raw_tag": entry.get("raw_tag"),
        })
    return cleaned


def build_metric_entry(series: List[Dict]) -> Dict:
    entry = {}
    if series:
        entry["current"] = series[0]
    if len(series) > 1:
        entry["prior"] = series[1]
        current_val = series[0].get("value")
        prior_val = series[1].get("value")
        entry["change"] = MetricChange.compute(current_val, prior_val).to_dict()
    if series:
        entry["series"] = series
    return entry


def _headline_metrics(xbrl_data: Dict, metrics: Dict) -> Tuple[List[Dict], List[Dict]]:
    revenue_series = normalise_series(xbrl_data.get("revenue", []))
    net_income_series = normalise_series(xbrl_data.get("net_income", []))
    eps_series = normalise_series(xbrl_data.get("earnings_per_share", []))

    if revenue_series:
        metrics["revenue"] = build_metric_entry(revenue_series)

    if net_income_series:
        metrics["net_income"] = build_metric_entry(net_income_series)

    if eps_series:
        metrics["earnings_per_share"] = build_metric_entry(eps_series)

    # Calculate net margin
    if revenue_series and net_income_series:
        income_by_period = {e["period"]: e for e in net_income_series}
        margin_series = []
        for rev_entry in revenue_series:
            period = rev_entry["period"]
            inc_entry = income_by_period.get(period)
            rev_value = rev_entry.get("value")
            inc_value = inc_entry.get("value") if inc_entry else None
            if rev_value and inc_value and rev_value != 0:
                margin_series.append({
                    "period": period,
                    "value": (inc_value / rev_value) * 100,
                    "form": rev_entry.get("form"),
                })
        if margin_series:
            metrics["net_margin"] = build_metric_entry(margin_series)
    return revenue_series, net_income_series


def _statement_metrics(xbrl_data: Dict, metrics: Dict) -> None:
    # P1.1 depth + roadmap 2.6: surface cash-flow + balance-sheet metrics the pipeline collects.
    # The 2.6 keys (investing/financing CF, current assets/liabilities) only carry a series when
    # RICHER_FINANCIALS_ENABLED was on at extraction, so listing them here is inert until then.
    for key in ("eps_diluted", "operating_cash_flow", "capital_expenditures", "gross_profit",
                "operating_income", "total_assets", "total_liabilities", "cash_and_equivalents",
                "shareholders_equity", "long_term_debt",
                "investing_cash_flow", "financing_cash_flow",
                "current_assets", "current_liabilities",
                # Financial-institution revenue components/totals (filing 528 / MCB fix). Only
                # present for banks/insurers/BDCs; inert (empty series → skipped) otherwise.
                "net_interest_income", "noninterest_income",
                "premiums_earned", "net_investment_income",
                # T5.3 shareholder returns (cash paid, as-tagged positive magnitudes).
                "dividends_paid", "share_repurchases"):
        series = normalise_series(xbrl_data.get(key, []))
        if series:
            metrics[key] = build_metric_entry(series)


def _liquidity_metrics(xbrl_data: Dict, metrics: Dict) -> None:
    # Roadmap 2.6 derived liquidity (per period): working capital = current assets − current
    # liabilities; current ratio = current assets ÷ current liabilities. Self-gating — both
    # require the 2.6 balance-sheet lines, which only exist when the flag is on.
    ca_series = normalise_series(xbrl_data.get("current_assets", []))
    cl_series = normalise_series(xbrl_data.get("current_liabilities", []))
    if ca_series and cl_series:
        cl_by_period = {e["period"]: e for e in cl_series}
        wc_series, cr_series = [], []
        for ca in ca_series:
            cl = cl_by_period.get(ca["period"])
            ca_v = ca.get("value")
            cl_v = cl.get("value") if cl else None
            # Guard on non-negative components: a negative current-assets/liabilities total is a
            # parse error (the base fact is hard-rejected by the reconciliation gate). The derived
            # metrics aren't in NON_NEGATIVE_CONCEPTS (working_capital CAN be negative), so without
            # this guard a corrupt component would persist an invalid working_capital / negative
            # current_ratio. Only derive from clean inputs.
            if ca_v is not None and cl_v is not None and ca_v >= 0 and cl_v >= 0:
                wc_series.append({"period": ca["period"], "value": ca_v - cl_v, "form": ca.get("form")})
                if cl_v > 0:
                    cr_series.append({"period": ca["period"], "value": ca_v / cl_v, "form": ca.get("form")})
        if wc_series:
            metrics["working_capital"] = build_metric_entry(wc_series)
        if cr_series:
            metrics["current_ratio"] = build_metric_entry(cr_series)


def _free_cash_flow(xbrl_data: Dict, metrics: Dict) -> None:
    # Derived: free cash flow = operating cash flow - capital expenditures (per period).
    # abs(capex) handles filers that tag the outflow as negative.
    ocf_series = normalise_series(xbrl_data.get("operating_cash_flow", []))
    capex_series = normalise_series(xbrl_data.get("capital_expenditures", []))
    if ocf_series and capex_series:
        capex_by_period = {e["period"]: e for e in capex_series}
        fcf_series = []
        for ocf in ocf_series:
            capex = capex_by_period.get(ocf["period"])
            ocf_v = ocf.get("value")
            capex_v = capex.get("value") if capex else None
            if ocf_v is not None and capex_v is not None:
                fcf_series.append({"period": ocf["period"],
                                   "value": ocf_v - abs(capex_v), "form": ocf.get("form")})
        if fcf_series:
            metrics["free_cash_flow"] = build_metric_entry(fcf_series)


def _margin_metrics(xbrl_data: Dict, metrics: Dict, revenue_series: List[Dict]) -> None:
    # Derived margins (gross/operating). Same issuer-type caveat as net_margin (hardened in P1.3).
    for margin_key, numerator_key in (("gross_margin", "gross_profit"),
                                      ("operating_margin", "operating_income")):
        num_series = normalise_series(xbrl_data.get(numerator_key, []))
        if revenue_series and num_series:
            num_by_period = {e["period"]: e for e in num_series}
            m_series = []
            for rev in revenue_series:
                num = num_by_period.get(rev["period"])
                rev_v = rev.get("value")
                num_v = num.get("value") if num else None
                if rev_v and num_v is not None and rev_v != 0:
                    m_series.append({"period": rev["period"],
                                     "value": (num_v / rev_v) * 100, "form": rev.get("form")})
            if m_series:
                metrics[margin_key] = build_metric_entry(m_series)


def _return_metrics(xbrl_data: Dict, metrics: Dict, net_income_series: List[Dict]) -> None:
    # P1.3 issuer-relevant returns: ROE and ROA — the right profitability read where gross
    # margin doesn't apply (banks, insurers, REITs). Net income (period) over equity / assets.
    # Denominator must be POSITIVE, not merely non-zero ("only derive from clean inputs", the
    # working-capital precedent above): a NEGATIVE-equity filer (buyback-driven deficits — SBUX,
    # MCD, BA) sign-flips the ratio, rendering a profitable company deeply negative and a
    # loss-maker confidently positive — a machine-authored wrong statement on both the grounding
    # and the T5.3 §4 surface. Skip those periods; ROA is unaffected in practice (total_assets
    # is hard-rejected when negative).
    equity_series = normalise_series(xbrl_data.get("shareholders_equity", []))
    assets_series = normalise_series(xbrl_data.get("total_assets", []))
    for ratio_key, denom_series in (("return_on_equity", equity_series),
                                    ("return_on_assets", assets_series)):
        if net_income_series and denom_series:
            denom_by_period = {e["period"]: e for e in denom_series}
            r_series = []
            for ni in net_income_series:
                denom = denom_by_period.get(ni["period"])
                ni_v = ni.get("value")
                denom_v = denom.get("value") if denom else None
                if ni_v is not None and denom_v is not None and denom_v > 0:
                    r_series.append({
                        "period": ni["period"],
                        "value": (ni_v / denom_v) * 100,
                        "form": ni.get("form"),
                        # Bind the formula to these selected operands. The ratio's prior
                        # may differ from the standalone NI prior when an instant is absent.
                        "numerator": dict(ni),
                        "denominator": dict(denom),
                    })
            if r_series:
                metrics[ratio_key] = build_metric_entry(r_series)


def _currency_and_ads(xbrl_data: Dict, metrics: Dict, revenue_series: List[Dict]) -> None:
    # Surface the filing's reporting currency (e.g. "CNY") so the UI can label monetary values
    # in the as-filed currency instead of implying USD. Derived in the instance extractor;
    # falls back to the currency carried on the revenue series when only that is available.
    reporting_currency = xbrl_data.get("reporting_currency")
    if not reporting_currency and revenue_series:
        reporting_currency = revenue_series[0].get("currency")
    if reporting_currency:
        metrics["reporting_currency"] = reporting_currency

    # Item A: additive per-ADS EPS for ADRs with a locked ratio (ratio != 1). The as-filed
    # per-ordinary-share EPS is left untouched; this only ADDS a `per_ads` block (value +
    # ratio + auditable arithmetic) so the ADR investor sees the figure they actually trade on.
    ads_info = xbrl_data.get("ads_ratio")
    if ads_info:
        for eps_key in ("earnings_per_share", "eps_diluted"):
            entry = metrics.get(eps_key)
            if entry:  # explicit: only annotate an EPS metric that was actually built
                per_ads = build_per_ads_eps(
                    entry.get("current", {}).get("value"), ads_info, reporting_currency
                )
                if per_ads:
                    entry["per_ads"] = per_ads


def _evidence_annotations(xbrl_data: Dict, metrics: Dict) -> None:
    # Reportable-segment table (T5.2): pass the raw per-segment rows through unchanged (like
    # reporting_currency — an annotation, not a standardized metric). The summary filler formats
    # them into the §7 table; absent for single-segment / undimensioned / bank filers.
    segments = xbrl_data.get("segments")
    if isinstance(segments, list) and segments:
        metrics["segments"] = segments

    # Source-qualified debt observations (debt-scope slice): passed through unchanged, like
    # `segments` — an evidence annotation, not a standardized metric, so it deliberately does
    # NOT get a current/prior/series entry. The shared debt-scope owner (`ai/debt_scope.py`)
    # turns these into the grounding label and the visible leverage statement. Absent on rows
    # extracted before this slice; that absence is unknown scope, never zero debt.
    debt_observations = xbrl_data.get("debt_observations")
    if isinstance(debt_observations, list) and debt_observations:
        metrics["debt_observations"] = debt_observations


def _inherit_labels_and_classification(xbrl_data: Dict, metrics: Dict) -> None:
    # Same-period derived ratios/flows inherit the fiscal label of their source values.
    labels = {}
    for entry in metrics.values():
        if isinstance(entry, dict):
            for point in entry.get("series", []):
                if point.get("fiscal_period"):
                    labels[point["period"]] = {k: point[k] for k in ("fiscal_year", "fiscal_period")}
    for entry in metrics.values():
        if isinstance(entry, dict):
            for point in entry.get("series", []):
                if point["period"] in labels and not point.get("fiscal_period"):
                    point.update(labels[point["period"]])
    source = xbrl_data.get("financing_comparison_source")
    if isinstance(source, dict):
        metrics["financing_comparison_source"] = source
    classification = xbrl_data.get("financial_classification")
    if isinstance(classification, dict):
        metrics["financial_classification"] = classification


def extract_standardized_metrics(xbrl_data: Optional[Dict]) -> Dict[str, Any]:
    """Build the same ordered metrics through the original calculation phases."""
    # Handle None or empty input
    if not xbrl_data:
        return {}

    metrics = {}
    revenue_series, net_income_series = _headline_metrics(xbrl_data, metrics)
    _statement_metrics(xbrl_data, metrics)
    _liquidity_metrics(xbrl_data, metrics)
    _free_cash_flow(xbrl_data, metrics)
    _margin_metrics(xbrl_data, metrics, revenue_series)
    _return_metrics(xbrl_data, metrics, net_income_series)
    _currency_and_ads(xbrl_data, metrics, revenue_series)
    _evidence_annotations(xbrl_data, metrics)
    _inherit_labels_and_classification(xbrl_data, metrics)
    return metrics
