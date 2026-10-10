"""
EdgarTools XBRL Service

Provides XBRL financial data extraction using EdgarTools.
This service maintains API compatibility with the legacy xbrl_service.py
to enable gradual migration.

Caching Strategy (Two-Tier):
- L1: In-memory cache (fast, process-local, LRU eviction at 1000 entries)
- L2: Redis cache (persistent, shared across instances)

Usage:
    from app.services.edgar.xbrl_service import edgar_xbrl_service

    # Get XBRL data (compatible with legacy interface)
    data = await edgar_xbrl_service.get_xbrl_data(accession_number, cik)

    # Extract standardized metrics
    metrics = edgar_xbrl_service.extract_standardized_metrics(data)
"""

import asyncio
import logging  # noqa: F401 - preserve the facade import surface
from collections import OrderedDict  # noqa: F401 - preserve the facade import surface
from datetime import date, datetime, timedelta  # noqa: F401 - preserve the facade import surface
from typing import Any, Dict, List, Optional, Tuple  # noqa: F401 - preserve the facade import surface

from edgar import set_identity

# The XBRL primary-path calls use a plain timeout, NOT run_with_circuit_breaker: large filings
# legitimately parse for 20-40s (BAC/JPM/BABA 20-F), so their dominant failure mode is local parse
# cost, not SEC health. Feeding those timeouts to the shared edgar breaker would let a batch of big
# filings open the circuit and fail-fast unrelated endpoints while SEC is perfectly healthy — the
# detector reporting the opposite of the truth. The fetch-shaped calls in edgar/client.py +
# edgar/compat.py give the breaker its clean SEC-health signal (S4 review, finding #2).
from .async_executor import run_in_executor_with_timeout
from app.services.request_work import run_owned_sync
from .client import resolve_filing_by_accession
from app.services.sec_rate_limiter import sec_rate_limiter  # noqa: F401 - preserve the facade import surface
from app.utils.sec_urls import companyfacts_url  # noqa: F401 - preserve the facade import surface
from .config import EDGAR_IDENTITY, EDGAR_DEFAULT_TIMEOUT_SECONDS
from .ads_ratios import ads_ratio_for_cik, build_per_ads_eps  # noqa: F401 - preserve the facade import surface
from .instance_extractor import (
    DURATION_CONCEPTS,
    DURATION_WINDOWS,
    INSTANT_CONCEPTS,
    RICHER_DURATION_CONCEPTS,
    RICHER_INSTANT_CONCEPTS,
    cash_financial_classification,
    debt_component_observations,
    dividend_component_sum_series,
    duration_series_with_starts,
    extract_financial_statement_metrics,
    instant_series_with_currency,
    instant_series_currency_concept,
    normalize_form,
    segment_series_by_member,
)
from .financing_source import financing_comparison_source
from .models import MetricChange  # noqa: F401 - preserve the facade import surface

from . import xbrl_companyfacts as _companyfacts
from . import xbrl_standardized as _standardize
from .xbrl_companyfacts import CASH_TAG_CANDIDATES
from .xbrl_cache import (
    _XBRL_CACHE_VERSION,
    _cache_max_size,
    _cache_set_sync,
    _cache_ttl,
    _get_cache_lock,
    _xbrl_cache,
    async_clear_xbrl_cache,
    clear_xbrl_cache,
    get_xbrl_cache_stats,
    logger,
    record_hit,
    record_miss,
)

__all__ = [
    "CASH_TAG_CANDIDATES", "EdgarXBRLService", "_SECTION_MIN_CHARS",
    "_XBRL_CACHE_VERSION", "_cache_max_size", "_cache_set_sync", "_cache_ttl",
    "_extract_from_filing_instance_sync", "_extract_sections_sync", "_extract_segments",
    "_get_cache_lock", "_source_duration", "_xbrl_cache", "async_clear_xbrl_cache",
    "clear_xbrl_cache", "edgar_xbrl_service", "get_xbrl_cache_stats", "logger",
]

# Ensure identity is set
set_identity(EDGAR_IDENTITY)

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

    # Roadmap 2.6 (Phase A): when enabled, also extract the full cash-flow statement (investing +
    # financing flows) and working-capital lines (current assets/liabilities). Flag-gated, so the
    # default concept set — and the eval baseline — stays byte-for-byte unchanged until flipped on.
    from app.config import settings

    duration_concepts = DURATION_CONCEPTS
    instant_concepts = INSTANT_CONCEPTS
    if settings.RICHER_FINANCIALS_ENABLED:
        duration_concepts = {**DURATION_CONCEPTS, **RICHER_DURATION_CONCEPTS}
        instant_concepts = {**INSTANT_CONCEPTS, **RICHER_INSTANT_CONCEPTS}

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

    # Anchor requirement: at least one income-statement metric for the
    # filing's own period — otherwise this instance is unusable and the
    # accession-aware companyfacts fallback should take over. Banks report no single "revenue"
    # (it is suppressed), so their net-interest/non-interest income components anchor instead.
    anchor_keys = ("revenue", "net_income", "earnings_per_share",
                   "net_interest_income", "noninterest_income")
    if not any(result.get(key) for key in anchor_keys):
        logger.info(f"No usable consolidated facts in instance for {accession_number}")
        return None
    if base_form == "10-Q":
        from .fiscal_periods import fiscal_label
        entity = getattr(xb, "entity_info", None)
        if isinstance(entity, dict):
            for values in result.values():
                if isinstance(values, list):
                    for point in values:
                        if isinstance(point, dict) and point.get("period"):
                            point.update(fiscal_label(
                                point["period"], period_of_report,
                                entity.get("fiscal_year"), entity.get("fiscal_period"),
                            ))
    result["financial_classification"] = cash_financial_classification(
        company, getattr(company, "sic", None), profile_key
    )
    return result


# Minimum length (chars) for an edgartools-parsed section to count as real content
# rather than an empty/placeholder stub.
_SECTION_MIN_CHARS = 200


def _extract_sections_sync(
    cik_padded: str,
    accession_number: str,
    base_form: str,
) -> Optional[Dict[str, str]]:
    """Pull the critical narrative/financial sections via edgartools' own document parser.

    edgartools (``filing.obj()``) resolves real section boundaries from the filing's
    structure/inline-XBRL, which is robust to the element-fragmented HTML that defeats the
    legacy regex extractor in ``openai_service.extract_critical_sections``.

    Synchronous on purpose: the whole chain (company lookup -> filing resolution -> document
    parse) runs as ONE executor call, sharing a single timeout budget and thread-pool slot,
    mirroring ``_extract_from_filing_instance_sync``.

    Returns a dict keyed by canonical section ("financials" / "mda" / "risk") mapped to clean
    text, or None when the filing can't be resolved or yields no usable sections (callers then
    fall back to the legacy regex extractor).
    """
    _, filings = resolve_filing_by_accession(cik_padded, accession_number)
    if not filings:
        logger.info(f"Filing {accession_number} not found by accession for CIK {cik_padded}")
        return None

    obj = filings[0].obj()
    if obj is None:
        logger.info(f"Filing {accession_number} has no parsable document object")
        return None

    out: Dict[str, str] = {}
    if base_form == "10-K":
        # 10-K items are unique across parts, so label lookup via __getitem__ is unambiguous
        # and returns clean section text (verified: AAPL Item 1A/7/8 -> 68k/18k/61k chars).
        for canonical, label in (("risk", "Item 1A"), ("mda", "Item 7"), ("financials", "Item 8")):
            try:
                text = obj[label]
            except Exception:  # noqa: BLE001 — a single missing/odd section must not abort the rest
                text = None
            if text and len(text.strip()) >= _SECTION_MIN_CHARS:
                out[canonical] = text.strip()
    elif base_form == "10-Q":
        # 10-Q items repeat across parts (e.g. Item 2 is MD&A in Part I but Unregistered Sales
        # in Part II), so __getitem__ by label is ambiguous — obj['Item 2'] returns the WRONG
        # Part II section. Use the new parser's part-prefixed section keys to disambiguate.
        sections = getattr(obj, "sections", None) or {}
        for canonical, skey in (
            ("financials", "part_i_item_1"),
            ("mda", "part_i_item_2"),
            ("risk", "part_ii_item_1a"),
        ):
            # edgartools' Sections is dict-like (.get); Section.text is a method in 5.36.0, but
            # guard against it being a plain str/property in other versions.
            section = sections.get(skey) if hasattr(sections, "get") else None
            text_attr = getattr(section, "text", None) if section is not None else None
            text = text_attr() if callable(text_attr) else text_attr
            if text and len(text.strip()) >= _SECTION_MIN_CHARS:
                out[canonical] = text.strip()
    elif base_form == "20-F":
        # 20-F (foreign private issuer annual report) uses Part/Item numbering distinct from a
        # 10-K: Item 3 (Key Information) carries the Risk Factors, Item 5 (Operating & Financial
        # Review and Prospects) is the MD&A equivalent, and the audited statements live under
        # Item 18 (or the older Item 17). Items repeat across parts, so use the part-prefixed
        # section keys like the 10-Q path. Each canonical maps to ordered candidate keys —
        # first one that yields real content wins (handles the Item 18-vs-17 filer choice).
        sections = getattr(obj, "sections", None) or {}
        for canonical, candidate_keys in (
            ("risk", ("part_i_item_3",)),
            ("mda", ("part_i_item_5",)),
            ("financials", ("part_iii_item_18", "part_iii_item_17", "part_i_item_8")),
        ):
            for skey in candidate_keys:
                section = sections.get(skey) if hasattr(sections, "get") else None
                text_attr = getattr(section, "text", None) if section is not None else None
                text = text_attr() if callable(text_attr) else text_attr
                if text and len(text.strip()) >= _SECTION_MIN_CHARS:
                    out[canonical] = text.strip()
                    break

    return out or None


class EdgarXBRLService:
    """
    XBRL data extraction service using EdgarTools.

    This service provides the same interface as the legacy XBRLService
    but uses EdgarTools for data extraction, eliminating the need for
    100+ hardcoded XBRL field names.
    """

    def __init__(self, timeout: float = EDGAR_DEFAULT_TIMEOUT_SECONDS):
        self.timeout = timeout

    async def get_xbrl_data(
        self,
        accession_number: str,
        cik: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Extract XBRL data from SEC filing.

        This method maintains backward compatibility with the legacy
        xbrl_service.get_xbrl_data() interface.

        Reads the persisted filing snapshot first, then uses two-tier caching:
        - L1: In-memory cache (fast, process-local)
        - L2: Redis cache (persistent, shared across instances)

        Args:
            accession_number: Filing accession number
            cik: Company CIK (Central Index Key)

        Returns:
            Dictionary with XBRL data in legacy format:
            {
                "revenue": [{"period": "2024-03-31", "value": 123, "form": "10-K", "accn": "..."}],
                "net_income": [...],
                "total_assets": [...],
                "total_liabilities": [...],
                "cash_and_equivalents": [...],
                "earnings_per_share": [...],
            }
        """
        # Persisted data is accession-specific and survives process/cache eviction. Release the
        # short read session before touching Redis or SEC; parsing/generation never holds it open.
        persisted = await run_owned_sync(self._persisted_xbrl, accession_number, cik)
        if persisted is not None:
            return persisted

        # Build cache keys (versioned — see _XBRL_CACHE_VERSION)
        memory_key = f"{_XBRL_CACHE_VERSION}:{cik}:{accession_number}"
        redis_key = f"xbrl:{_XBRL_CACHE_VERSION}:{cik}:{accession_number}"

        # L1: Check in-memory cache first (fastest) - protected by async lock
        async with _get_cache_lock():
            if memory_key in _xbrl_cache:
                cached_time, cached_data = _xbrl_cache[memory_key]
                if datetime.now() - cached_time < _cache_ttl:
                    # Move to end for LRU ordering (most recently used)
                    _xbrl_cache.move_to_end(memory_key)
                    record_hit()
                    logger.debug(f"XBRL L1 cache hit for {memory_key}")
                    return cached_data
                else:
                    logger.debug(f"XBRL L1 cache expired for {memory_key}")
                    del _xbrl_cache[memory_key]
                    # L1 cache miss (expired) - track inside lock for thread safety
                    record_miss()
            else:
                # L1 cache miss (not found) - track inside lock for thread safety
                record_miss()

        # L2: Check Redis cache (persistent, shared)
        redis_data = await self._get_from_redis(redis_key)
        if redis_data is not None:
            logger.debug(f"XBRL L2 cache hit for {redis_key}")
            # Populate L1 cache from L2 with LRU eviction
            async with _get_cache_lock():
                _cache_set_sync(memory_key, (datetime.now(), redis_data))
            return redis_data

        # Cache miss - fetch from EdgarTools
        result = await self._fetch_xbrl_data(cik, accession_number)

        # Cache successful results in both tiers
        if result is not None:
            async with _get_cache_lock():
                _cache_set_sync(memory_key, (datetime.now(), result))
            await self._set_to_redis(redis_key, result)
            logger.debug(f"XBRL cached (L1+L2) for {memory_key}")
        else:
            logger.debug(f"XBRL NOT cached for {memory_key} (no data)")

        return result

    @staticmethod
    def _persisted_xbrl(accession_number: str, cik: str) -> Optional[Dict[str, Any]]:
        from app.database import SessionLocal
        from app.models import Company, Filing

        normalized_cik = str(cik).strip().lstrip("0") or "0"
        try:
            with SessionLocal() as db:
                payload = (
                    db.query(Filing.xbrl_data)
                    .join(Company, Filing.company_id == Company.id)
                    .filter(
                        Filing.accession_number == accession_number,
                        Company.cik.in_((normalized_cik, normalized_cik.zfill(10))),
                    ).scalar()
                )
                # Empty/legacy malformed snapshots must not suppress a real extraction.
                return payload if isinstance(payload, dict) and any(
                    isinstance(payload.get(key), list) and payload[key]
                    for key in ("revenue", "net_income", "earnings_per_share", "total_assets",
                                "total_liabilities", "cash_and_equivalents", "net_interest_income",
                                "noninterest_income")
                ) else None
        except Exception as exc:
            logger.warning("Persisted XBRL read failed for %s: %s", accession_number, type(exc).__name__)
            return None

    async def _get_from_redis(self, key: str) -> Optional[Dict[str, Any]]:
        """Get XBRL data from Redis cache (L2)."""
        try:
            from app.services.redis_service import cache_get
            return await cache_get(key)
        except Exception as e:
            logger.debug(f"Redis L2 cache get failed for {key}: {e}")
            return None

    async def _set_to_redis(self, key: str, data: Dict[str, Any]) -> bool:
        """Set XBRL data in Redis cache (L2)."""
        try:
            from app.services.redis_service import cache_set, CacheTTL
            return await cache_set(key, data, CacheTTL.XBRL_DATA)
        except Exception as e:
            logger.debug(f"Redis L2 cache set failed for {key}: {e}")
            return False

    async def _fetch_xbrl_data(
        self,
        cik: str,
        accession_number: str,
    ) -> Optional[Dict[str, Any]]:
        """Fetch XBRL data using EdgarTools.

        Order matters (issue #240):
        1. The requested filing's own XBRL instance — the only source whose
           periods and durations are guaranteed to belong to this accession.
        2. The companyfacts API, restricted to facts the target accession reported,
           including its own comparative periods. If neither source is usable,
           return no data; the company's latest filing is not a substitute.
        """
        cik_padded = cik.zfill(10)

        result = await self._fetch_from_filing_instance(cik_padded, accession_number)
        if result is not None:
            logger.debug(f"XBRL extracted from filing instance for {accession_number}")
            return result

        result = await self._fallback_to_company_facts(cik_padded, accession_number)
        if result is not None and any(result.values()):
            return result

        return None

    async def _fetch_from_filing_instance(
        self,
        cik_padded: str,
        accession_number: str,
    ) -> Optional[Dict[str, Any]]:
        """Accession-aware primary path: the requested filing's own XBRL instance."""
        try:
            return await run_in_executor_with_timeout(
                lambda: _extract_from_filing_instance_sync(cik_padded, accession_number),
                timeout=self.timeout,
            )
        except Exception as e:
            logger.warning(f"Accession-aware XBRL extraction failed for {accession_number}: {e}")
            return None

    async def get_filing_sections(
        self,
        accession_number: str,
        cik: str,
        filing_type: str,
    ) -> Optional[Dict[str, str]]:
        """Extract critical sections via edgartools' native document parser.

        Returns {"financials": str, "mda": str, "risk": str} (only the sections that
        parsed to real content), or None when the form is unsupported, parsing fails, or
        the timeout is hit — callers fall back to the legacy regex extractor in that case.
        """
        base_form = normalize_form(filing_type)
        if base_form not in {"10-K", "10-Q", "20-F"}:
            return None
        cik_padded = str(cik).zfill(10)
        # The section parse runs CONCURRENT with the document fetch, so extra headroom is largely
        # hidden. Big financial 10-Ks need it: measured BAC ~21s, GS ~20s, JPM ~26s — all over the
        # 15s default, so they were timing out into the lower-precision regex excerpt. 20-F annual
        # reports are larger still (a BABA 20-F parses Item 3/5/18 in ~17.5s). (B3)
        section_timeout = max(self.timeout, 40.0) if base_form == "20-F" else max(self.timeout, 30.0)
        try:
            return await run_in_executor_with_timeout(
                lambda: _extract_sections_sync(cik_padded, accession_number, base_form),
                timeout=section_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(f"Section extraction timed out for {accession_number}")
            return None
        except Exception as e:  # noqa: BLE001 — never let section parsing break generation
            logger.warning(f"Section extraction failed for {accession_number}: {e}")
            return None

    async def _fallback_to_company_facts(
        self,
        cik: str,
        accession_number: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Fallback to SEC company facts API if EdgarTools financials not available.

        This replicates the logic from the legacy xbrl_service.py for cases
        where EdgarTools doesn't have the data.
        """
        return await _companyfacts.fallback_to_company_facts(self, cik, accession_number)

    def _parse_company_facts(
        self,
        facts_data: Dict,
        target_accession: str,
    ) -> Dict[str, List[Dict]]:
        """Parse SEC company facts API response."""
        return _companyfacts.parse_company_facts(facts_data, target_accession)


    def extract_standardized_metrics(self, xbrl_data: Optional[Dict]) -> Dict[str, Any]:
        """
        Extract standardized financial metrics from XBRL data.

        This method maintains backward compatibility with the legacy interface.

        Args:
            xbrl_data: Raw XBRL data dictionary (can be None)

        Returns:
            Dictionary with standardized metrics including current, prior,
            change calculations, and series data. Returns empty dict if
            xbrl_data is None or empty.
        """
        return _standardize.extract_standardized_metrics(xbrl_data)


# Singleton instance for backward compatibility
edgar_xbrl_service = EdgarXBRLService()
