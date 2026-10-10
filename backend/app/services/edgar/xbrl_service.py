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
from .instance.concepts import (  # noqa: F401 - preserve the facade import surface
    DURATION_CONCEPTS,
    INSTANT_CONCEPTS,
    RICHER_DURATION_CONCEPTS,
    RICHER_INSTANT_CONCEPTS,
)
from .instance.core import DURATION_WINDOWS, normalize_form  # noqa: F401 - preserve the facade import surface
from .instance.debt import debt_component_observations  # noqa: F401 - preserve the facade import surface
from .instance.financial_profiles import cash_financial_classification  # noqa: F401 - preserve the facade import surface
from .instance.segments import segment_series_by_member  # noqa: F401 - preserve the facade import surface
from .instance.series import (  # noqa: F401 - preserve the facade import surface
    dividend_component_sum_series,
    duration_series_with_starts,
    instant_series_with_currency,
    instant_series_currency_concept,
)
from .instance.statements import extract_financial_statement_metrics  # noqa: F401 - preserve the facade import surface
from .financing_source import financing_comparison_source  # noqa: F401 - preserve the facade import surface
from .models import MetricChange  # noqa: F401 - preserve the facade import surface

from . import xbrl_companyfacts as _companyfacts
from . import xbrl_standardized as _standardize
from .xbrl_companyfacts import CASH_TAG_CANDIDATES
from .xbrl_instance import _extract_from_filing_instance_sync, _extract_segments, _source_duration
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
