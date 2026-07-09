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
import logging
from collections import OrderedDict
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from edgar import Company as EdgarCompany, set_identity

# The XBRL primary-path calls use a plain timeout, NOT run_with_circuit_breaker: large filings
# legitimately parse for 20-40s (BAC/JPM/BABA 20-F), so their dominant failure mode is local parse
# cost, not SEC health. Feeding those timeouts to the shared edgar breaker would let a batch of big
# filings open the circuit and fail-fast unrelated endpoints while SEC is perfectly healthy — the
# detector reporting the opposite of the truth. The fetch-shaped calls in edgar/client.py +
# edgar/compat.py give the breaker its clean SEC-health signal (S4 review, finding #2).
from .async_executor import run_in_executor_with_timeout
from .client import resolve_filing_by_accession
from app.services.sec_rate_limiter import sec_rate_limiter
from .config import EDGAR_IDENTITY, EDGAR_DEFAULT_TIMEOUT_SECONDS
from .ads_ratios import ads_ratio_for_cik, build_per_ads_eps
from .instance_extractor import (
    DURATION_CONCEPTS,
    DURATION_WINDOWS,
    INSTANT_CONCEPTS,
    RICHER_DURATION_CONCEPTS,
    RICHER_INSTANT_CONCEPTS,
    duration_series_currency_concept,
    duration_series_with_currency,
    extract_financial_statement_metrics,
    instant_series_with_currency,
    normalize_form,
    segment_series_by_member,
)
from .models import MetricChange
from .statement_parser import extract_metric_values, statement_dataframe

logger = logging.getLogger(__name__)

# Cash concept candidates for the single-filing statement path, in priority order. The
# ASU 2016-18 restricted-cash total sits LAST (lowest priority): it only resolves when no
# unrestricted-cash tag is present — the JPM-class bank case whose only cash line is the
# migrated tag (data-quality plan P0-3). test_cash_registry_consistency.py pins this ordering
# across all three cash registries.
CASH_TAG_CANDIDATES: List[str] = [
    "CashAndCashEquivalentsAtCarryingValue",
    "Cash",
    "CashAndCashEquivalents",
    "CashCashEquivalentsAndShortTermInvestments",
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
]

# Ensure identity is set
set_identity(EDGAR_IDENTITY)

# Cache key version — bump whenever extraction semantics change so stale
# entries written by the previous logic cannot be served under the same key.
# v2: accession-aware primary path (issue #240); v1 entries could hold the
# latest 10-K's figures for any accession and must age out unread.
# v3: financial-institution revenue via the as-reported income statement (filing 528 / MCB fix) —
# v2 entries can hold a bank's fee-income-only "revenue" subset and must age out unread.
_XBRL_CACHE_VERSION = "v3"

# Module-level cache for XBRL data (L1 - in-memory with LRU eviction)
# Key: "{cik}:{accession_number}"
# Value: (cached_datetime, data_dict)
# Using OrderedDict for LRU eviction - most recently accessed items at end
_xbrl_cache: OrderedDict[str, Tuple[datetime, Optional[Dict]]] = OrderedDict()
_cache_ttl = timedelta(hours=24)
_cache_max_size = 1000  # Maximum entries before LRU eviction

# Cache operation counters for structured logging and metrics
_cache_hits = 0
_cache_misses = 0
_cache_evictions = 0

# Async lock to protect cache operations from concurrent coroutine access.
# WHY lazy initialization: asyncio.Lock must be created within an event loop context.
# If created at module import time (outside of async context), it binds to no loop
# or the wrong loop, causing "attached to a different loop" errors.
# By creating it lazily on first use, we ensure it binds to the correct running loop.
_cache_lock: asyncio.Lock | None = None


def _get_cache_lock() -> asyncio.Lock:
    """
    Get or create the cache lock (lazy initialization for event loop safety).

    This pattern ensures the asyncio.Lock is created within the context of the
    event loop that will actually use it, avoiding "attached to a different loop" errors.
    """
    global _cache_lock
    if _cache_lock is None:
        _cache_lock = asyncio.Lock()
    return _cache_lock


def clear_xbrl_cache() -> int:
    """
    Clear the XBRL cache. Returns number of entries cleared.

    Note: For async contexts, prefer async_clear_xbrl_cache() for thread safety.
    """
    global _xbrl_cache
    count = len(_xbrl_cache)
    _xbrl_cache.clear()
    logger.info(f"Cleared {count} XBRL cache entries")
    return count


async def async_clear_xbrl_cache() -> int:
    """Clear the XBRL cache (async-safe). Returns number of entries cleared."""
    global _xbrl_cache
    async with _get_cache_lock():
        count = len(_xbrl_cache)
        _xbrl_cache.clear()
        logger.info(f"Cleared {count} XBRL cache entries")
        return count


def _cache_set_sync(key: str, value: Tuple[datetime, Optional[Dict]]) -> None:
    """
    Set a value in L1 cache with LRU eviction (sync version, call within lock).

    If cache exceeds max size, evicts oldest entries (least recently used).
    Tracks eviction count for metrics and uses structured logging.
    """
    global _xbrl_cache, _cache_evictions

    # If key exists, move to end (most recently used)
    if key in _xbrl_cache:
        _xbrl_cache.move_to_end(key)
        _xbrl_cache[key] = value
        return

    # Add new entry
    _xbrl_cache[key] = value

    # Evict oldest entries if over max size
    evicted_this_call = 0
    while len(_xbrl_cache) > _cache_max_size:
        oldest_key, (cached_time, _) = _xbrl_cache.popitem(last=False)
        _cache_evictions += 1
        evicted_this_call += 1
        # Structured log with key details for debugging cache pressure
        logger.info(
            "XBRL L1 cache eviction",
            extra={
                "event": "cache_eviction",
                "cache_type": "xbrl_l1",
                "evicted_key": oldest_key,
                "entry_age_hours": round((datetime.now() - cached_time).total_seconds() / 3600, 2),
                "cache_size": len(_xbrl_cache),
                "total_evictions": _cache_evictions,
            }
        )

    # Log batch eviction summary if multiple entries evicted
    if evicted_this_call > 1:
        logger.warning(
            f"XBRL L1 cache batch eviction: {evicted_this_call} entries",
            extra={
                "event": "cache_batch_eviction",
                "cache_type": "xbrl_l1",
                "evicted_count": evicted_this_call,
                "new_key": key,
                "cache_size": len(_xbrl_cache),
            }
        )


def get_xbrl_cache_stats() -> Dict[str, Any]:
    """
    Get cache statistics for monitoring (L1 in-memory cache).

    Returns dict with both new (l1_*) and legacy (total_entries, valid_entries)
    keys for backward compatibility.
    """
    now = datetime.now()
    total = len(_xbrl_cache)
    valid_count = sum(
        1 for cached_time, _ in _xbrl_cache.values()
        if now - cached_time < _cache_ttl
    )
    expired_count = total - valid_count

    # Calculate hit rate
    total_ops = _cache_hits + _cache_misses
    hit_rate = round(_cache_hits / total_ops * 100, 2) if total_ops > 0 else 0.0

    return {
        # New L1-prefixed keys for two-tier caching clarity
        "l1_total_entries": total,
        "l1_valid_entries": valid_count,
        "l1_expired_entries": expired_count,
        "l1_max_size": _cache_max_size,
        "l1_utilization_percent": round(total / _cache_max_size * 100, 1) if _cache_max_size > 0 else 0,
        "l1_hits": _cache_hits,
        "l1_misses": _cache_misses,
        "l1_hit_rate": hit_rate,
        "l1_evictions": _cache_evictions,
        "cache_ttl_hours": _cache_ttl.total_seconds() / 3600,
        # Backward compatibility aliases (deprecated)
        "total_entries": total,
        "valid_entries": valid_count,
        "expired_entries": expired_count,
    }


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
            series, currency, concept = duration_series_currency_concept(
                xb, concepts, base_form, period_of_report
            )
            raw_tag = f"us-gaap:{concept}" if concept else None
            result[metric] = [
                {"period": end, "value": value, "form": form, "accn": accession_number,
                 "currency": currency, "raw_tag": raw_tag}
                for end, value in series
            ]
        else:
            series, currency = duration_series_with_currency(xb, concepts, base_form, period_of_report)
            result[metric] = [
                {"period": end, "value": value, "form": form, "accn": accession_number, "currency": currency}
                for end, value in series
            ]
        # EPS is per-share (currency-per-share), so it shouldn't sway the headline reporting
        # currency vote; weight revenue/net_income (true monetary totals) instead.
        if metric not in ("earnings_per_share", "eps_diluted"):
            _record_currency(currency, len(series))

    # Emit the statement-derived financial metrics (revenue and/or bank components), each carrying
    # its raw_tag. Values are in the filer's own reporting currency (domestic financials = USD).
    for key, (fin_series, raw_tag) in fin_metrics.items():
        result[key] = [
            {"period": end, "value": value, "form": form, "accn": accession_number,
             "currency": None, "raw_tag": raw_tag}
            for end, value in fin_series
        ]
    for metric, concepts in instant_concepts.items():
        series, currency = instant_series_with_currency(xb, concepts, period_of_report)
        result[metric] = [
            {"period": end, "value": value, "form": form, "accn": accession_number, "currency": currency}
            for end, value in series
        ]
        _record_currency(currency, len(series))

    # Filing-level reporting currency = the currency carried by the most monetary facts.
    if currency_votes:
        result["reporting_currency"] = max(currency_votes.items(), key=lambda kv: kv[1])[0]

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

        Uses two-tier caching:
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
        global _xbrl_cache, _cache_hits, _cache_misses

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
                    _cache_hits += 1
                    logger.debug(f"XBRL L1 cache hit for {memory_key}")
                    return cached_data
                else:
                    logger.debug(f"XBRL L1 cache expired for {memory_key}")
                    del _xbrl_cache[memory_key]
                    # L1 cache miss (expired) - track inside lock for thread safety
                    _cache_misses += 1
            else:
                # L1 cache miss (not found) - track inside lock for thread safety
                _cache_misses += 1

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
        2. The companyfacts API — accession-aware since PR #239 (prefers facts
           the target filing reported, dedupes by standard duration).
        3. Company.get_financials() — built from the company's LATEST 10-K,
           so for any other filing it can return another filing's numbers;
           last resort only.
        """
        cik_padded = cik.zfill(10)

        result = await self._fetch_from_filing_instance(cik_padded, accession_number)
        if result is not None:
            logger.debug(f"XBRL extracted from filing instance for {accession_number}")
            return result

        result = await self._fallback_to_company_facts(cik_padded, accession_number)
        if result is not None and any(result.values()):
            return result

        return await self._fetch_from_latest_financials(cik_padded, accession_number)

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

    async def _fetch_from_latest_financials(
        self,
        cik_padded: str,
        accession_number: str,
    ) -> Optional[Dict[str, Any]]:
        """LAST RESORT: Company.get_financials() builds from the company's
        latest 10-K, so for any other filing these can be a different filing's
        numbers (issue #240). Reached only when the filing's own instance and
        the companyfacts API both produced nothing.
        """
        try:
            # Get company via EdgarTools
            edgar_company = await run_in_executor_with_timeout(
                lambda: EdgarCompany(cik_padded),
                timeout=self.timeout,
            )

            # Get financials. EdgarTools 5.x exposes Company.get_financials()
            # (there is no `financials` property; attribute access raises and
            # silently forced every request onto the company-facts fallback).
            financials = await run_in_executor_with_timeout(
                edgar_company.get_financials,
                timeout=self.timeout,
            )

            if not financials:
                logger.warning(f"No financials available for CIK {cik_padded}")
                return None

            # Extract data from financials
            result = {
                "revenue": [],
                "net_income": [],
                "total_assets": [],
                "total_liabilities": [],
                "cash_and_equivalents": [],
                "earnings_per_share": [],
                "eps_diluted": [],
                # P1.1 depth additions
                "gross_profit": [],
                "operating_income": [],
                "operating_cash_flow": [],
                "capital_expenditures": [],
                "shareholders_equity": [],
                "long_term_debt": [],
            }

            # Try to get income statement
            try:
                df = await run_in_executor_with_timeout(lambda: statement_dataframe(financials, "income_statement"), timeout=self.timeout)
                if df is not None and not df.empty:
                    result["revenue"] = self._extract_from_dataframe(
                        df,
                        ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues",
                         "Revenue", "TotalRevenue", "TotalRevenues", "NetSales", "SalesRevenueNet"],
                        accession_number
                    )
                    result["net_income"] = self._extract_from_dataframe(
                        df,
                        ["NetIncomeLoss", "ProfitLoss", "NetIncome",
                         "NetIncomeLossAvailableToCommonStockholdersBasic"],
                        accession_number
                    )
                    result["earnings_per_share"] = self._extract_from_dataframe(
                        df,
                        ["EarningsPerShareBasic", "EarningsPerShareDiluted",
                         "BasicEarningsPerShare", "EarningsPerShareBasicAndDiluted"],
                        accession_number
                    )
                    result["eps_diluted"] = self._extract_from_dataframe(
                        df, ["EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted"], accession_number
                    )
                    result["gross_profit"] = self._extract_from_dataframe(
                        df, ["GrossProfit"], accession_number
                    )
                    result["operating_income"] = self._extract_from_dataframe(
                        df, ["OperatingIncomeLoss"], accession_number
                    )
            except Exception as e:
                logger.warning(f"Error extracting income statement: {e}")

            # Try to get balance sheet
            try:
                df = await run_in_executor_with_timeout(lambda: statement_dataframe(financials, "balance_sheet"), timeout=self.timeout)
                if df is not None and not df.empty:
                    result["total_assets"] = self._extract_from_dataframe(
                        df,
                        ["Assets", "TotalAssets"],
                        accession_number
                    )
                    result["total_liabilities"] = self._extract_from_dataframe(
                        df,
                        ["Liabilities", "TotalLiabilities", "LiabilitiesAndStockholdersEquity"],
                        accession_number
                    )
                    result["cash_and_equivalents"] = self._extract_from_dataframe(
                        df,
                        CASH_TAG_CANDIDATES,
                        accession_number
                    )
                    result["shareholders_equity"] = self._extract_from_dataframe(
                        df,
                        ["StockholdersEquity",
                         "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
                        accession_number
                    )
                    result["long_term_debt"] = self._extract_from_dataframe(
                        df, ["LongTermDebtNoncurrent", "LongTermDebt"], accession_number
                    )
            except Exception as e:
                logger.warning(f"Error extracting balance sheet: {e}")

            # Try to get cash-flow statement (P1.1 depth: operating CF + capex -> free cash flow)
            try:
                df = await run_in_executor_with_timeout(lambda: statement_dataframe(financials, "cash_flow_statement"), timeout=self.timeout)
                if df is not None and not df.empty:
                    result["operating_cash_flow"] = self._extract_from_dataframe(
                        df,
                        ["NetCashProvidedByUsedInOperatingActivities",
                         "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
                        accession_number
                    )
                    result["capital_expenditures"] = self._extract_from_dataframe(
                        df,
                        ["PaymentsToAcquirePropertyPlantAndEquipment",
                         "PaymentsToAcquireProductiveAssets"],
                        accession_number
                    )
            except Exception as e:
                logger.warning(f"Error extracting cash-flow statement: {e}")

            # If we got any data, return it (companyfacts already ran earlier
            # in the chain — see _fetch_xbrl_data — so there is nothing left
            # to fall back to from here).
            if any(result.values()):
                return result
            return None

        except Exception as e:
            logger.error(f"Error fetching XBRL data: {e}", exc_info=True)
            return None

    def _extract_from_dataframe(
        self,
        df,
        candidates: List[str],
        accession_number: str,
    ) -> List[Dict[str, Any]]:
        """Extract metric values from an EdgarTools statement DataFrame."""
        _, values = extract_metric_values(df, candidates)
        return [
            {
                "period": period,
                "value": value,
                "form": None,
                "accn": accession_number,
            }
            for period, value in values[:5]
        ]

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
        import httpx

        logger.info(f"Falling back to SEC company facts API for CIK {cik}")

        try:
            facts_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

            # Route through the SEC rate limiter with a SINGLE token wait (execute, NOT
            # execute_with_backoff): this fallback runs inside user-facing summary generation, so it
            # fail-fasts rather than sleeping through the full backoff ladder (S4 review #3).
            # raise_for_status turns a non-200 into an exception, preserving "non-200 -> None" via the
            # outer except.
            async with httpx.AsyncClient() as client:
                async def _do_request() -> httpx.Response:
                    resp = await client.get(
                        facts_url,
                        headers={"User-Agent": EDGAR_IDENTITY},
                        timeout=30.0,
                    )
                    resp.raise_for_status()
                    return resp

                response = await sec_rate_limiter.execute(_do_request)
                data = response.json()
                return self._parse_company_facts(data, accession_number)

        except Exception as e:
            logger.error(f"Error in company facts fallback: {e}")
            return None

    def _parse_company_facts(
        self,
        facts_data: Dict,
        target_accession: str,
    ) -> Dict[str, List[Dict]]:
        """Parse SEC company facts API response."""
        result = {
            "revenue": [],
            "net_income": [],
            "total_assets": [],
            "total_liabilities": [],
            "cash_and_equivalents": [],
            "earnings_per_share": [],
        }

        normalized_accession = target_accession.replace("-", "") if target_accession else None

        def _is_target(item: Dict) -> bool:
            return bool(
                normalized_accession
                and item.get("accn", "").replace("-", "") == normalized_accession
            )

        def _duration_penalty(item: Dict) -> int:
            """Distance from the standard duration for the item's form.

            Companyfacts reports several durations sharing one period end
            (Q4 + FY both end on the fiscal year end; Q3 + 9-month YTD both
            end on the quarter end). The standard statement value is the
            12-month figure for a 10-K and the 3-month figure for a 10-Q.
            Instant facts (no start) have a single duration; penalty 0.
            """
            start, end = item.get("start"), item.get("end")
            if not start:
                return 0
            try:
                days = (date.fromisoformat(end) - date.fromisoformat(start)).days
            except (ValueError, TypeError):
                return 0
            target_days = 365 if (item.get("form") or "").startswith("10-K") else 91
            return abs(days - target_days)

        def filter_and_sort(data_list: list, max_items: int = 5) -> list:
            if not isinstance(data_list, list):
                return []

            valid_items = [
                item for item in data_list
                if isinstance(item, dict) and item.get("end")
            ]

            # When the target filing reported this concept, use its facts only
            # (current value + the comparatives restated in that same filing).
            matching = [item for item in valid_items if _is_target(item)]
            if matching:
                valid_items = matching

            # Dedupe by period end: prefer the standard duration for the form,
            # then the most recently filed restatement.
            best_by_end: Dict[str, Dict] = {}
            for item in valid_items:
                incumbent = best_by_end.get(item["end"])
                if incumbent is None:
                    best_by_end[item["end"]] = item
                    continue
                key = (_duration_penalty(item), item.get("filed") or "")
                incumbent_key = (_duration_penalty(incumbent), incumbent.get("filed") or "")
                # Lower penalty wins; on a tie, later filed date wins.
                if key[0] < incumbent_key[0] or (key[0] == incumbent_key[0] and key[1] > incumbent_key[1]):
                    best_by_end[item["end"]] = item

            sorted_items = sorted(
                best_by_end.values(),
                key=lambda x: x.get("end", ""),
                reverse=True
            )
            return sorted_items[:max_items]

        def select_fact_data(fields: List[str], unit_keys: Tuple[str, ...] = ("USD",)) -> list:
            """Pick the candidate concept actually used by recent filings.

            Taking the first concept present is wrong: issuers retire tags over
            time (e.g. AAPL last reported `Revenues` in FY2018 and has used
            `RevenueFromContractWithCustomerExcludingAssessedTax` since), so a
            stale concept would shadow the live one and surface years-old
            values as "current". Prefer a concept with facts from the target
            filing; otherwise the one with the most recent period end.
            """
            best_key: Optional[Tuple[int, str]] = None
            best_data: list = []
            for field in fields:
                fact = us_gaap.get(field)
                if not (isinstance(fact, dict) and isinstance(fact.get("units"), dict)):
                    continue
                for unit_key in unit_keys:
                    data = fact["units"].get(unit_key) or []
                    valid = [i for i in data if isinstance(i, dict) and i.get("end")]
                    if not valid:
                        continue
                    has_target = any(_is_target(i) for i in valid)
                    latest_end = max(i["end"] for i in valid)
                    key = (0 if has_target else 1, latest_end)
                    if (
                        best_key is None
                        or key[0] < best_key[0]
                        or (key[0] == best_key[0] and key[1] > best_key[1])
                    ):
                        best_key, best_data = key, valid
                    break  # first unit key with data for this concept
            return best_data

        def append_items(metric: str, data: list) -> None:
            for item in filter_and_sort(data):
                result[metric].append({
                    "period": item.get("end"),
                    "value": item.get("val"),
                    "form": item.get("form"),
                    "accn": item.get("accn"),
                })

        try:
            facts = facts_data.get("facts", {})
            us_gaap = facts.get("us-gaap", {})

            if not isinstance(us_gaap, dict):
                return result

            append_items("revenue", select_fact_data(
                ["Revenues", "Revenue", "RevenueFromContractWithCustomerExcludingAssessedTax",
                 "SalesRevenueNet", "NetSales", "TotalRevenue"]))
            append_items("net_income", select_fact_data(
                ["NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"]))
            append_items("total_assets", select_fact_data(["Assets"]))
            append_items("earnings_per_share", select_fact_data(
                ["EarningsPerShareBasic", "EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted"],
                unit_keys=("USD/shares", "USD", "pure")))

        except Exception as e:
            logger.warning(f"Error parsing company facts: {e}")

        return result

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
        # Handle None or empty input
        if not xbrl_data:
            return {}

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

        metrics = {}

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

        # P1.1 depth + roadmap 2.6: surface cash-flow + balance-sheet metrics the pipeline collects.
        # The 2.6 keys (investing/financing CF, current assets/liabilities) only carry a series when
        # RICHER_FINANCIALS_ENABLED was on at extraction, so listing them here is inert until then.
        for key in ("eps_diluted", "operating_cash_flow", "capital_expenditures", "gross_profit",
                    "operating_income", "total_assets", "cash_and_equivalents",
                    "shareholders_equity", "long_term_debt",
                    "investing_cash_flow", "financing_cash_flow",
                    "current_assets", "current_liabilities",
                    # Financial-institution revenue components/totals (filing 528 / MCB fix). Only
                    # present for banks/insurers/BDCs; inert (empty series → skipped) otherwise.
                    "net_interest_income", "noninterest_income",
                    "premiums_earned", "net_investment_income"):
            series = normalise_series(xbrl_data.get(key, []))
            if series:
                metrics[key] = build_metric_entry(series)

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

        # P1.3 issuer-relevant returns: ROE and ROA — the right profitability read where gross
        # margin doesn't apply (banks, insurers, REITs). Net income (period) over equity / assets.
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
                    if ni_v is not None and denom_v and denom_v != 0:
                        r_series.append({"period": ni["period"],
                                         "value": (ni_v / denom_v) * 100, "form": ni.get("form")})
                if r_series:
                    metrics[ratio_key] = build_metric_entry(r_series)

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

        # Reportable-segment table (T5.2): pass the raw per-segment rows through unchanged (like
        # reporting_currency — an annotation, not a standardized metric). The summary filler formats
        # them into the §7 table; absent for single-segment / undimensioned / bank filers.
        segments = xbrl_data.get("segments")
        if isinstance(segments, list) and segments:
            metrics["segments"] = segments

        return metrics


# Singleton instance for backward compatibility
edgar_xbrl_service = EdgarXBRLService()
