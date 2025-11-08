from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

from .schema import FilingSummary, Financials, Liquidity, Metric, NumberUnit, Outlook, Risks


@dataclass
class _MetricConfig:
    label: str
    unit: NumberUnit
    concepts: Tuple[str, ...]


# Mapping of desired metrics to their XBRL concept names
FINANCIAL_METRICS: Dict[str, _MetricConfig] = {
    "revenue": _MetricConfig("Revenue", "USD", ("us-gaap:Revenues", "us-gaap:SalesRevenueNet")),
    "gross_profit": _MetricConfig("Gross Profit", "USD", ("us-gaap:GrossProfit",)),
    "operating_income": _MetricConfig("Operating Income", "USD", ("us-gaap:OperatingIncomeLoss",)),
    "net_income": _MetricConfig("Net Income", "USD", ("us-gaap:NetIncomeLoss",)),
    "eps_basic": _MetricConfig("EPS (Basic)", "EPS", ("us-gaap:EarningsPerShareBasic",)),
    "eps_diluted": _MetricConfig("EPS (Diluted)", "EPS", ("us-gaap:EarningsPerShareDiluted",)),
    "cfo": _MetricConfig("Operating Cash Flow", "USD", ("us-gaap:NetCashProvidedByUsedInOperatingActivities",)),
    "capex": _MetricConfig(
        "Capital Expenditures",
        "USD",
        (
            "us-gaap:PaymentsToAcquirePropertyPlantAndEquipment",
            "us-gaap:PaymentsToAcquirePropertyPlantAndEquipmentExcludingCapitalLeases",
        ),
    ),
}

LIQUIDITY_METRICS: Dict[str, _MetricConfig] = {
    "cash": _MetricConfig("Cash & Equivalents", "USD", ("us-gaap:CashAndCashEquivalentsAtCarryingValue",)),
    "debt_long": _MetricConfig("Long-Term Debt", "USD", ("us-gaap:LongTermDebtNoncurrent",)),
    "debt_current": _MetricConfig("Current Portion of Debt", "USD", ("us-gaap:LongTermDebtCurrent", "us-gaap:LongTermDebtAndCapitalLeaseObligationsCurrent")),
    "current_assets": _MetricConfig("Current Assets", "USD", ("us-gaap:AssetsCurrent",)),
    "current_liabilities": _MetricConfig("Current Liabilities", "USD", ("us-gaap:LiabilitiesCurrent",)),
}

NAMESPACES = {
    "ix": "http://www.xbrl.org/2013/inlineXBRL",
    "xbrli": "http://www.xbrl.org/2003/instance",
}

_VALUE_RE = re.compile(r"[^0-9.()-]")


def _parse_numeric(text: str) -> Optional[float]:
    if not text:
        return None
    cleaned = _VALUE_RE.sub("", text)
    if not cleaned:
        return None
    negative = False
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = cleaned[1:-1]
        negative = True
    if cleaned.startswith("-"):
        negative = True
    cleaned = cleaned.replace("(", "").replace(")", "")
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return -value if negative else value


def _apply_scale(value: float, tag) -> float:
    scale = tag.get("scale")
    if scale and scale.strip("-+").isdigit():
        value *= 10 ** int(scale)
        return value
    fmt = (tag.get("format") or "").lower()
    if "million" in fmt:
        value *= 1_000_000
    elif "billion" in fmt:
        value *= 1_000_000_000
    elif "thousand" in fmt:
        value *= 1_000
    return value


def _parse_tag_value(tag: ET.Element) -> Optional[float]:
    text = tag.text.strip() if tag.text else ""
    value = _parse_numeric(text)
    if value is None:
        return None
    if tag.get("sign") == "-":
        value = -value
    value = _apply_scale(value, tag)
    return value


def _parse_contexts(root: ET.Element) -> Dict[str, Dict[str, Optional[dt.date]]]:
    contexts: Dict[str, Dict[str, Optional[dt.date]]] = {}
    for context in root.findall(".//xbrli:context", NAMESPACES):
        context_id = context.get("id")
        if not context_id:
            continue
        period = context.find("xbrli:period", NAMESPACES)
        if not period:
            continue
        start_tag = period.find("xbrli:startDate", NAMESPACES)
        end_tag = period.find("xbrli:endDate", NAMESPACES)
        instant_tag = period.find("xbrli:instant", NAMESPACES)
        start: Optional[dt.date] = None
        end: Optional[dt.date] = None
        instant: Optional[dt.date] = None
        if start_tag and end_tag:
            try:
                start = dt.date.fromisoformat(start_tag.text.strip())
                end = dt.date.fromisoformat(end_tag.text.strip())
            except ValueError:
                start = end = None
        elif instant_tag:
            try:
                instant = dt.date.fromisoformat(instant_tag.text.strip())
            except ValueError:
                instant = None
        contexts[context_id] = {
            "start": start,
            "end": end,
            "instant": instant,
        }
    return contexts


def _select_period(entries: List[Tuple[float, str, str]], contexts: Dict[str, Dict[str, Optional[dt.date]]]) -> Tuple[Optional[float], Optional[float], List[str]]:
    if not entries:
        return None, None, []
    scored: List[Tuple[dt.date, float, str, str]] = []
    for value, context_id, anchor in entries:
        context = contexts.get(context_id, {})
        end = context.get("end") or context.get("instant")
        if end is None:
            continue
        scored.append((end, value, context_id, anchor))
    if not scored:
        # fall back to order of appearance
        ordered = entries[:2]
        anchors = [anchor for _, _, anchor in ordered if anchor]
        current = ordered[0][0] if ordered else None
        prior = ordered[1][0] if len(ordered) > 1 else None
        return current, prior, anchors
    scored.sort(key=lambda item: item[0], reverse=True)
    current = scored[0][1]
    prior = scored[1][1] if len(scored) > 1 else None
    anchors = [anchor for _, _, _, anchor in scored[:2] if anchor]
    return current, prior, anchors


def _collect_values(root: ET.Element, config: _MetricConfig, contexts: Dict[str, Dict[str, Optional[dt.date]]]) -> Tuple[Optional[float], Optional[float], List[str]]:
    entries: List[Tuple[float, str, str]] = []
    for concept in config.concepts:
        for tag in root.findall(f".//ix:nonFraction[@name='{concept}']", NAMESPACES):
            value = _parse_tag_value(tag)
            if value is None:
                continue
            context_ref = tag.get("contextRef")
            if not context_ref:
                continue
            anchor = tag.get("id") or concept
            entries.append((value, context_ref, anchor))
        for tag in root.findall(f".//ix:nonNumeric[@name='{concept}']", NAMESPACES):
            value = _parse_tag_value(tag)
            if value is None:
                continue
            context_ref = tag.get("contextRef")
            if not context_ref:
                continue
            anchor = tag.get("id") or concept
            entries.append((value, context_ref, anchor))
    return _select_period(entries, contexts)


def extract_ixbrl_metrics(
    html: str,
    *,
    cik: str,
    symbol: str,
    company_name: str,
    filing_type: str,
    filing_date: str,
    period_end: Optional[str] = None,
) -> FilingSummary:
    """Parse inline XBRL HTML and extract normalized metrics."""

    root = ET.fromstring(html)
    contexts = _parse_contexts(root)

    financials = Financials()

    revenue_current, revenue_prior, revenue_anchors = _collect_values(root, FINANCIAL_METRICS["revenue"], contexts)
    gross_current, gross_prior, gross_anchors = _collect_values(root, FINANCIAL_METRICS["gross_profit"], contexts)
    operating_current, operating_prior, operating_anchors = _collect_values(root, FINANCIAL_METRICS["operating_income"], contexts)
    net_current, net_prior, net_anchors = _collect_values(root, FINANCIAL_METRICS["net_income"], contexts)
    eps_basic_current, eps_basic_prior, eps_basic_anchors = _collect_values(root, FINANCIAL_METRICS["eps_basic"], contexts)
    eps_diluted_current, eps_diluted_prior, eps_diluted_anchors = _collect_values(root, FINANCIAL_METRICS["eps_diluted"], contexts)
    cfo_current, cfo_prior, cfo_anchors = _collect_values(root, FINANCIAL_METRICS["cfo"], contexts)
    capex_current, capex_prior, capex_anchors = _collect_values(root, FINANCIAL_METRICS["capex"], contexts)

    def build_metric(label: str, unit: NumberUnit, current: Optional[float], prior: Optional[float], anchors: List[str]) -> Optional[Metric]:
        if current is None and prior is None:
            return None
        return Metric(label=label, unit=unit, current=current, prior=prior, source_anchors=anchors)

    financials.revenue = build_metric("Revenue", "USD", revenue_current, revenue_prior, revenue_anchors)
    gross_margin_metric: Optional[Metric] = None
    if revenue_current and gross_current:
        gross_margin_metric = Metric(
            label="Gross Margin",
            unit="PCT",
            current=gross_current / revenue_current if revenue_current else None,
            prior=gross_prior / revenue_prior if revenue_prior else None,
            source_anchors=gross_anchors or revenue_anchors,
        )
    elif gross_current or gross_prior:
        # fall back to gross profit absolute metric
        gross_margin_metric = Metric(
            label="Gross Profit",
            unit="USD",
            current=gross_current,
            prior=gross_prior,
            source_anchors=gross_anchors,
        )
    financials.gross_margin = gross_margin_metric
    financials.operating_income = build_metric("Operating Income", "USD", operating_current, operating_prior, operating_anchors)
    financials.net_income = build_metric("Net Income", "USD", net_current, net_prior, net_anchors)
    financials.eps_basic = build_metric("EPS (Basic)", "EPS", eps_basic_current, eps_basic_prior, eps_basic_anchors)
    financials.eps_diluted = build_metric("EPS (Diluted)", "EPS", eps_diluted_current, eps_diluted_prior, eps_diluted_anchors)

    free_cash_flow_metric: Optional[Metric] = None
    if cfo_current is not None:
        fcf_current = cfo_current - (capex_current or 0)
        fcf_prior: Optional[float] = None
        if cfo_prior is not None and capex_prior is not None:
            fcf_prior = cfo_prior - capex_prior
        elif cfo_prior is not None:
            fcf_prior = None
        free_cash_flow_metric = Metric(
            label="Free Cash Flow",
            unit="USD",
            current=fcf_current,
            prior=fcf_prior,
            source_anchors=(cfo_anchors or []) + (capex_anchors or []),
        )
    financials.free_cash_flow = free_cash_flow_metric

    liquidity_metrics: Dict[str, Optional[Metric]] = {}
    liquidity_source = Liquidity()
    cash_current, cash_prior, cash_anchors = _collect_values(root, LIQUIDITY_METRICS["cash"], contexts)
    if cash_current is not None or cash_prior is not None:
        liquidity_source.cash = Metric(label="Cash & Equivalents", unit="USD", current=cash_current, prior=cash_prior, source_anchors=cash_anchors)

    debt_long_current, debt_long_prior, debt_long_anchors = _collect_values(root, LIQUIDITY_METRICS["debt_long"], contexts)
    debt_current_current, debt_current_prior, debt_current_anchors = _collect_values(root, LIQUIDITY_METRICS["debt_current"], contexts)
    total_debt_current = None
    total_debt_prior = None
    if debt_long_current is not None or debt_current_current is not None:
        total_debt_current = (debt_long_current or 0) + (debt_current_current or 0)
    if debt_long_prior is not None or debt_current_prior is not None:
        total_debt_prior = None
        if debt_long_prior is not None and debt_current_prior is not None:
            total_debt_prior = debt_long_prior + debt_current_prior
        elif debt_long_prior is not None:
            total_debt_prior = debt_long_prior
        elif debt_current_prior is not None:
            total_debt_prior = debt_current_prior
    debt_anchors = (debt_long_anchors or []) + (debt_current_anchors or [])
    if total_debt_current is not None or total_debt_prior is not None:
        liquidity_source.debt = Metric(
            label="Total Debt",
            unit="USD",
            current=total_debt_current,
            prior=total_debt_prior,
            source_anchors=debt_anchors,
        )

    current_assets_current, current_assets_prior, ca_anchors = _collect_values(root, LIQUIDITY_METRICS["current_assets"], contexts)
    current_liabilities_current, current_liabilities_prior, cl_anchors = _collect_values(root, LIQUIDITY_METRICS["current_liabilities"], contexts)
    if current_assets_current is not None and current_liabilities_current:
        current_ratio_current = current_assets_current / current_liabilities_current if current_liabilities_current else None
    else:
        current_ratio_current = None
    current_ratio_prior: Optional[float] = None
    if current_assets_prior is not None and current_liabilities_prior:
        current_ratio_prior = current_assets_prior / current_liabilities_prior if current_liabilities_prior else None
    anchors = (ca_anchors or []) + (cl_anchors or [])
    if current_ratio_current is not None or current_ratio_prior is not None:
        liquidity_source.current_ratio = Metric(
            label="Current Ratio",
            unit="PCT",
            current=current_ratio_current,
            prior=current_ratio_prior,
            source_anchors=anchors,
        )

    risks = Risks(items=[], citations=[])
    outlook = Outlook(guidance_summary=None, catalysts=[])

    summary = FilingSummary(
        cik=cik,
        symbol=symbol,
        company_name=company_name,
        filing_type=filing_type,
        filing_date=filing_date,
        period_end=period_end,
        financials=financials,
        liquidity=liquidity_source,
        risks=risks,
        outlook=outlook,
        sources=[],
    )
    return summary
