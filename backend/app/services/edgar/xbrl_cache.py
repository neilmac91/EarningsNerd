"""XBRL L1 cache state, eviction and counters shared by the service facade."""

import asyncio
import logging
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

# Preserve the logger name used before this module was extracted.
logger = logging.getLogger("app.services.edgar.xbrl_service")

# Cache key version — bump whenever extraction semantics change so stale
# entries written by the previous logic cannot be served under the same key.
# v2: accession-aware primary path (issue #240); v1 entries could hold the
# latest 10-K's figures for any accession and must age out unread.
# v3: financial-institution revenue via the as-reported income statement (filing 528 / MCB fix) —
# v2 entries can hold a bank's fee-income-only "revenue" subset and must age out unread.
# v4: T5.3 shareholder-returns concepts (dividends_paid, share_repurchases) — v3 entries lack the
# new keys and must age out so the §4 deterministic feed sees them without a manual refresh.
# v5: retain fiscal-quarter metadata in newly extracted snapshots.
# v6: fallback facts must originate in the selected accession; no latest-filing surrogate.
_XBRL_CACHE_VERSION = "v6"

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


def record_hit() -> None:
    """Record an L1 hit while the caller holds the cache lock."""
    global _cache_hits
    _cache_hits += 1


def record_miss() -> None:
    """Record an L1 miss while the caller holds the cache lock."""
    global _cache_misses
    _cache_misses += 1
