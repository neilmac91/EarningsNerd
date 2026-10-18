"""Accession-aware XBRL instance parsing behind the service facade.

The service runs the whole synchronous chain in one executor call with one plain
timeout. Local parse cost is deliberately breaker-exempt, not a SEC-health signal.
"""

from typing import Any, Dict, List, Optional

from .ads_ratios import ads_ratio_for_cik
from .client import resolve_filing_by_accession
from .financing_source import financing_comparison_source
from .instance.concepts import (
    DURATION_CONCEPTS,
    INSTANT_CONCEPTS,
    RICHER_DURATION_CONCEPTS,
    RICHER_INSTANT_CONCEPTS,
)
from .instance.core import DURATION_WINDOWS, normalize_form
from .instance.debt import debt_component_observations
from .instance.financial_profiles import cash_financial_classification
from .instance.segments import segment_series_by_member
from .instance.series import (
    dividend_component_sum_series,
    duration_series_with_starts,
    instant_series_with_currency,
    instant_series_currency_concept,
)
from .instance.statements import extract_financial_statement_metrics
from .xbrl_cache import logger


def _extract_segments(
    xb: Any, base_form: str, period_of_report: str, consolidated_revenue: Optional[float]
) -> List[Dict[str, Any]]:
    """Assemble the reportable-segment table from the same ``xb`` instance (zero extra SEC traffic).

    Per-segment current+prior revenue and current operating income from the ASC-280
    ``StatementBusinessSegmentsAxis``, reusing the consolidated revenue / operating-income concept
    lists (their ordering encodes tag priority). Ordered by current revenue descending. Returns [] —
    degrading gracefully — for single-segment / undimensioned / financial-institution filers (which
    tag no generic segment revenue), when fewer than two reportable segments survive, or when the
    segment revenue sum is not the same order of magnitude as consolidated (a mis-tag / wrong-axis /
    unit guard, rule 9; intersegment eliminations legitimately push the sum modestly ABOVE
    consolidated, so the band is wide).
    """
    rev_by_member, rev_ccy = segment_series_by_member(
        xb, DURATION_CONCEPTS["revenue"], base_form, period_of_report
    )
    inc_by_member, inc_ccy = segment_series_by_member(
        xb, DURATION_CONCEPTS["operating_income"], base_form, period_of_report
    )
    if not rev_by_member and not inc_by_member:
        return []
    currency = rev_ccy or inc_ccy
    members = list(dict.fromkeys([*rev_by_member, *inc_by_member]))
    rows: List[Dict[str, Any]] = []
    for member in members:
        rev = rev_by_member.get(member, [])
        inc = inc_by_member.get(member, [])
        rows.append(
            {
                "name": member,
                "revenue": rev[0][1] if rev else None,
                "revenue_prior": rev[1][1] if len(rev) > 1 else None,
                "operating_income": inc[0][1] if inc else None,
                "period": (rev[0][0] if rev else inc[0][0] if inc else None),
                "currency": currency,
            }
        )
    # A single reportable segment == the consolidated total; only a multi-segment breakdown adds signal.
    if len(rows) < 2:
        return []
    revenue_sum = sum(r["revenue"] for r in rows if r["revenue"])
    if consolidated_revenue and revenue_sum:
        if not (0.5 <= revenue_sum / consolidated_revenue <= 2.0):
            logger.warning(
                f"Segment revenue sum {revenue_sum:.0f} not coherent with consolidated "
                f"{consolidated_revenue:.0f}; dropping segment table"
            )
            return []
    elif revenue_sum:
        # No consolidated revenue to validate against (the generic revenue path was suppressed/failed).
        # Surface the table rather than drop real segment data, but log so a coherence miss here is not
        # mistaken for a passed check.
        logger.info("Segment table surfaced without a consolidated-revenue coherence check")
    rows.sort(key=lambda r: (r["revenue"] is not None, r["revenue"] or 0.0), reverse=True)
    return rows


def _source_duration(start: Optional[str]) -> Dict[str, str]:
    """The source fact's own start, or nothing at all when it is unknown.

    Emitted as a key only when a real start exists, so an undated point keeps exactly the shape it
    has always had. Never synthesised: an instant fact, a computed aggregate, or a period whose
    equal-valued source facts disagreed on their start all stay absent, and every consumer treats
    absence as "duration unknown" rather than guessing one.
    """
    return {"period_start": start} if isinstance(start, str) and start else {}


def _instance_concepts():
    # Roadmap 2.6 (Phase A): when enabled, also extract the full cash-flow statement (investing +
    # financing flows) and working-capital lines (current assets/liabilities). Flag-gated, so the
    # default concept set — and the eval baseline — stays byte-for-byte unchanged until flipped on.
    from app.config import settings

    duration_concepts = DURATION_CONCEPTS
    instant_concepts = INSTANT_CONCEPTS
    if settings.RICHER_FINANCIALS_ENABLED:
        duration_concepts = {**DURATION_CONCEPTS, **RICHER_DURATION_CONCEPTS}
        instant_concepts = {**INSTANT_CONCEPTS, **RICHER_INSTANT_CONCEPTS}
    return settings, duration_concepts, instant_concepts


def _statement_metrics(settings, company, xb, base_form, period_of_report, accession_number):
    # Financial institutions: "revenue" has no single generic tag (a bank's ASC-606 fee-income tag
    # is only a subset). Read the industry-correct revenue/component lines from the AS-REPORTED
    # income statement and suppress the generic keys they replace. Non-financial filers are
    # untouched, and any failure falls back to the generic fact-query path below.
    fin_suppress = set()
    fin_metrics = {}
    profile_key = None
    if settings.USE_STATEMENT_FINANCIALS:
        sic = getattr(company, "sic", None)
        try:
            fin = extract_financial_statement_metrics(xb, company, sic, base_form, period_of_report)
        except Exception as exc:  # noqa: BLE001 - never let the statement path break extraction
            logger.warning(f"Financial statement extraction failed for {accession_number}: {exc}")
            fin = None
        if fin is not None:
            profile_key, fin_metrics, suppress = fin
            fin_suppress = set(suppress)
            logger.info(
                f"Statement-based financial revenue for {accession_number} (profile={profile_key}, "
                f"metrics={sorted(fin_metrics)})"
            )
    return fin_suppress, fin_metrics, profile_key


def _duration_metrics(
    duration_concepts, fin_suppress, fin_metrics, xb, base_form, period_of_report,
    result, form, accession_number, filing, cik_padded, _record_currency,
):
    for metric, concepts in duration_concepts.items():
        if metric in fin_suppress or metric in fin_metrics:
            continue  # the as-reported statement supplies (or intentionally omits) this metric
        if metric == "revenue":
            # Record the winning concept as raw_tag so a revenue concept that FLIPS between filings
            # can be detected downstream (the −53.8% apples-to-oranges class of bug).
            series, currency, raw_tag = duration_series_with_starts(
                xb, concepts, base_form, period_of_report, qualified_concept=True
            )
            result[metric] = [
                {"period": end, "value": value, "form": form, "accn": accession_number,
                 "currency": currency, "raw_tag": raw_tag, **_source_duration(start)}
                for end, value, start in series
            ]
        elif metric in {"capital_expenditures", "net_income", "operating_cash_flow"}:
            # Preserve the winning basis for cash comparisons; selection and precedence stay fixed.
            series, currency, raw_tag = duration_series_with_starts(
                xb, concepts, base_form, period_of_report, qualified_concept=True
            )
            result[metric] = [
                {"period": end, "value": value, "form": form, "accn": accession_number,
                 "currency": currency, "raw_tag": raw_tag, **_source_duration(start)}
                for end, value, start in series
            ]
        else:
            financing_sources = [] if metric == "financing_cash_flow" else None
            series, currency, _concept = duration_series_with_starts(
                xb, concepts, base_form, period_of_report, selected_sources=financing_sources
            )
            if financing_sources:
                source = financing_comparison_source(
                    filing, financing_sources, accession=accession_number, form=form,
                    period_of_report=period_of_report, cik=cik_padded,
                )
                if source is not None:
                    result["financing_comparison_source"] = source
            result[metric] = [
                {"period": end, "value": value, "form": form, "accn": accession_number,
                 "currency": currency, **_source_duration(start)}
                for end, value, start in series
            ]
        # EPS is per-share (currency-per-share), so it shouldn't sway the headline reporting
        # currency vote; weight revenue/net_income (true monetary totals) instead.
        if metric not in ("earnings_per_share", "eps_diluted"):
            _record_currency(currency, len(series))


def _dividend_fallback(result, xb, base_form, period_of_report, form, accession_number, _record_currency):
    # T5.3 review (WFC class): dividends component fallback. Filers with NO total dividends tag
    # emit common/preferred payments as separate components; first-candidate-wins over a component
    # would report the common-only subset as the unqualified total. Sum the explicitly-tagged
    # components per period instead. Crash-safe: a failure here never breaks the metrics path.
    if not result.get("dividends_paid"):
        try:
            div_series, div_currency = dividend_component_sum_series(xb, base_form, period_of_report)
            if div_series:
                result["dividends_paid"] = [
                    {"period": end, "value": value, "form": form, "accn": accession_number,
                     "currency": div_currency}
                    for end, value in div_series
                ]
                _record_currency(div_currency, len(div_series))
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Dividend component fallback failed: {exc}")


def _statement_and_instant_metrics(
    fin_metrics, instant_concepts, xb, period_of_report, result, form, accession_number,
    _record_currency, currency_votes,
):
    # Emit the statement-derived financial metrics (revenue and/or bank components), each carrying
    # its raw_tag. Values are in the filer's own reporting currency (domestic financials = USD).
    for key, (fin_series, raw_tag) in fin_metrics.items():
        result[key] = [
            {"period": end, "value": value, "form": form, "accn": accession_number,
             "currency": None, "raw_tag": raw_tag}
            for end, value in fin_series
        ]
    for metric, concepts in instant_concepts.items():
        provenance = {}
        if metric in ("cash_and_equivalents", "long_term_debt"):
            series, currency, raw_tag = instant_series_currency_concept(xb, concepts, period_of_report)
            provenance = {"raw_tag": raw_tag}
        else:
            series, currency = instant_series_with_currency(xb, concepts, period_of_report)
        result[metric] = [
            {"period": end, "value": value, "form": form, "accn": accession_number,
             "currency": currency, **provenance}
            for end, value in series
        ]
        _record_currency(currency, len(series))

    # Filing-level reporting currency = the currency carried by the most monetary facts.
    if currency_votes:
        result["reporting_currency"] = max(currency_votes.items(), key=lambda kv: kv[1])[0]


def _debt_and_ads(xb, period_of_report, result, accession_number, form, cik_padded):
    # Source-qualified DEBT observations from the SAME `xb` instance (no extra SEC round-trip;
    # rule 5 — these are in-memory queries over the already-parsed instance). Additive evidence
    # beside the `long_term_debt` series above, which stays exactly as selected: one
    # first-candidate-wins value cannot say WHICH obligations it covers, so a scope claim needs
    # each admissible concept retained separately with its own concept/instant/currency/context/
    # entity identity. Filtered to the reporting currency resolved just above, so a foreign
    # issuer's USD convenience translation is not mistaken for a conflicting balance. Absent for a
    # filer tagging none of the admissible concepts — which downstream reads as "not separately
    # reported", never as zero. Best-effort: this must never break the metrics path.
    try:
        debt_observations = debt_component_observations(
            xb, period_of_report,
            reporting_currency=result.get("reporting_currency"),
            accession_number=accession_number, form=form,
        )
    except Exception as exc:  # noqa: BLE001 - debt evidence must never break metric extraction
        logger.warning(f"Debt observation extraction failed for {accession_number}: {exc}")
        debt_observations = []
    if debt_observations:
        result["debt_observations"] = debt_observations

    # Item A: attach the issuer's locked ADS ratio (ratio != 1 ADRs only) so the standardized
    # metrics can surface a per-ADS EPS alongside the as-filed per-ordinary-share figure. Absent
    # for 1:1 ADRs and domestic filers, in which case no per-ADS normalization is applied.
    ads_ratio = ads_ratio_for_cik(cik_padded)
    if ads_ratio is not None:
        result["ads_ratio"] = ads_ratio.as_dict()


def _segment_metrics(result, xb, base_form, period_of_report, accession_number):
    # Reportable-segment disaggregation (T5.2) — per-segment revenue + operating income from the SAME
    # `xb` instance (no extra SEC round-trip; rule 5). Best-effort: never let it break the metrics path.
    # Empty for single-segment / undimensioned / financial-institution filers (degrade gracefully).
    revenue_series = result.get("revenue") or []
    consolidated_revenue = revenue_series[0].get("value") if revenue_series else None
    try:
        segments = _extract_segments(xb, base_form, period_of_report, consolidated_revenue)
    except Exception as exc:  # noqa: BLE001 - segment extraction must never break metric extraction
        logger.warning(f"Segment extraction failed for {accession_number}: {exc}")
        segments = []
    if segments:
        result["segments"] = segments


def _finish_instance(result, accession_number, base_form, xb, period_of_report, company, profile_key):
    # Anchor requirement: at least one income-statement metric for the
    # filing's own period — otherwise this instance is unusable and the
    # accession-aware companyfacts fallback should take over. Banks report no single "revenue"
    # (it is suppressed), so their net-interest/non-interest income components anchor instead.
    anchor_keys = ("revenue", "net_income", "earnings_per_share",
                   "net_interest_income", "noninterest_income")
    if not any(result.get(key) for key in anchor_keys):
        logger.info(f"No usable consolidated facts in instance for {accession_number}")
        return None
    from .fiscal_periods import filing_point_label
    entity = getattr(xb, "entity_info", None)
    if isinstance(entity, dict):
        for values in result.values():
            if isinstance(values, list):
                for point in values:
                    if isinstance(point, dict) and point.get("period"):
                        point.update(filing_point_label(
                            base_form, point["period"], period_of_report,
                            entity.get("fiscal_year"), entity.get("fiscal_period"),
                        ))
    result["financial_classification"] = cash_financial_classification(
        company, getattr(company, "sic", None), profile_key
    )
    return result


def _extract_from_filing_instance_sync(
    cik_padded: str,
    accession_number: str,
) -> Optional[Dict[str, Any]]:
    """Extract metrics from the requested filing's OWN XBRL instance.

    Synchronous on purpose: the whole chain (company lookup -> filing
    resolution -> instance parse) runs as ONE executor call, sharing a single
    timeout budget and occupying a single thread-pool slot.

    Returns the legacy result-dict shape, or None when the filing cannot be
    resolved or has no usable instance (callers then fall back).
    """
    company, filings = resolve_filing_by_accession(cik_padded, accession_number)
    if not filings:
        logger.info(f"Filing {accession_number} not found by accession for CIK {cik_padded}")
        return None
    filing = filings[0]

    form = str(filing.form or "")
    base_form = normalize_form(form)
    if base_form not in DURATION_WINDOWS:
        logger.info(f"Form {form!r} has no standard duration window; skipping instance extraction")
        return None

    period_of_report = str(filing.period_of_report or "")
    if not period_of_report:
        logger.info(f"Filing {accession_number} has no period_of_report")
        return None

    xb = filing.xbrl()
    if xb is None:
        logger.info(f"Filing {accession_number} has no XBRL instance")
        return None

    result: Dict[str, Any] = {
        "revenue": [],
        "net_income": [],
        "total_assets": [],
        "total_liabilities": [],
        "cash_and_equivalents": [],
        "earnings_per_share": [],
    }
    # Track the currency of monetary metrics so the filing's reporting currency (e.g. CNY for a
    # 20-F that also tags a USD convenience translation) can be surfaced and never rendered as USD.
    currency_votes: Dict[str, int] = {}

    def _record_currency(currency: Optional[str], weight: int) -> None:
        if currency:
            currency_votes[currency] = currency_votes.get(currency, 0) + weight

    settings, duration_concepts, instant_concepts = _instance_concepts()
    fin_suppress, fin_metrics, profile_key = _statement_metrics(
        settings, company, xb, base_form, period_of_report, accession_number,
    )
    _duration_metrics(
        duration_concepts, fin_suppress, fin_metrics, xb, base_form, period_of_report,
        result, form, accession_number, filing, cik_padded, _record_currency,
    )
    _dividend_fallback(result, xb, base_form, period_of_report, form, accession_number, _record_currency)
    _statement_and_instant_metrics(
        fin_metrics, instant_concepts, xb, period_of_report, result, form, accession_number,
        _record_currency, currency_votes,
    )
    _debt_and_ads(xb, period_of_report, result, accession_number, form, cik_padded)
    _segment_metrics(result, xb, base_form, period_of_report, accession_number)
    return _finish_instance(result, accession_number, base_form, xb, period_of_report, company, profile_key)
