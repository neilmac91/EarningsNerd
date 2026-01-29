"""
Two-Tier Caching Tests

Tests for the L1 (in-memory) + L2 (Redis) caching implementation.
Covers stress testing, concurrent access, and LRU eviction.
"""

import asyncio
import pytest
from collections import OrderedDict
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

# Import cache components
from app.services.edgar.xbrl_service import (
    _xbrl_cache,
    _cache_max_size,
    _cache_ttl,
    _cache_set_sync,
    _get_cache_lock,
    get_xbrl_cache_stats,
    clear_xbrl_cache,
    async_clear_xbrl_cache,
    EdgarXBRLService,
)


class TestLRUCacheEviction:
    """Tests for LRU eviction behavior in L1 cache."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_xbrl_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_xbrl_cache()

    def test_cache_set_sync_adds_entry(self):
        """_cache_set_sync should add entries to the cache."""
        _cache_set_sync("test:key1", (datetime.now(), {"data": "value1"}))

        assert "test:key1" in _xbrl_cache
        assert _xbrl_cache["test:key1"][1] == {"data": "value1"}

    def test_cache_set_sync_updates_existing_entry(self):
        """_cache_set_sync should update existing entries and move to end."""
        _cache_set_sync("test:key1", (datetime.now(), {"data": "old"}))
        _cache_set_sync("test:key2", (datetime.now(), {"data": "newer"}))
        _cache_set_sync("test:key1", (datetime.now(), {"data": "updated"}))

        # key1 should be at the end (most recently used)
        keys = list(_xbrl_cache.keys())
        assert keys[-1] == "test:key1"
        assert _xbrl_cache["test:key1"][1] == {"data": "updated"}

    def test_lru_eviction_when_over_max_size(self):
        """Cache should evict oldest entries when exceeding max size."""
        # Temporarily reduce max size for testing
        original_max = _cache_max_size

        # We need to patch the module-level constant
        import app.services.edgar.xbrl_service as xbrl_module
        xbrl_module._cache_max_size = 5

        try:
            # Add 7 entries (should evict 2 oldest)
            for i in range(7):
                _cache_set_sync(f"test:key{i}", (datetime.now(), {"index": i}))

            # Should have only 5 entries
            assert len(_xbrl_cache) == 5

            # Oldest keys (0, 1) should be evicted
            assert "test:key0" not in _xbrl_cache
            assert "test:key1" not in _xbrl_cache

            # Newer keys should remain
            assert "test:key2" in _xbrl_cache
            assert "test:key6" in _xbrl_cache
        finally:
            xbrl_module._cache_max_size = original_max

    def test_access_updates_lru_order(self):
        """Accessing an entry should move it to end of LRU queue."""
        _cache_set_sync("test:key1", (datetime.now(), {"data": 1}))
        _cache_set_sync("test:key2", (datetime.now(), {"data": 2}))
        _cache_set_sync("test:key3", (datetime.now(), {"data": 3}))

        # Access key1 (oldest) - should move it to end
        _cache_set_sync("test:key1", (datetime.now(), {"data": 1}))

        keys = list(_xbrl_cache.keys())
        assert keys == ["test:key2", "test:key3", "test:key1"]


class TestCacheStats:
    """Tests for cache statistics reporting."""

    def setup_method(self):
        clear_xbrl_cache()

    def teardown_method(self):
        clear_xbrl_cache()

    def test_cache_stats_returns_expected_keys(self):
        """get_xbrl_cache_stats should return both new and legacy keys."""
        stats = get_xbrl_cache_stats()

        # New L1-prefixed keys
        assert "l1_total_entries" in stats
        assert "l1_valid_entries" in stats
        assert "l1_expired_entries" in stats
        assert "l1_max_size" in stats
        assert "l1_utilization_percent" in stats
        assert "cache_ttl_hours" in stats

        # Backward compatibility keys
        assert "total_entries" in stats
        assert "valid_entries" in stats
        assert "expired_entries" in stats

    def test_cache_stats_counts_entries(self):
        """Cache stats should accurately count entries."""
        _cache_set_sync("test:key1", (datetime.now(), {"data": 1}))
        _cache_set_sync("test:key2", (datetime.now(), {"data": 2}))

        stats = get_xbrl_cache_stats()

        assert stats["l1_total_entries"] == 2
        assert stats["total_entries"] == 2  # Legacy alias

    def test_cache_stats_identifies_expired_entries(self):
        """Cache stats should correctly identify expired entries."""
        # Add a fresh entry
        _cache_set_sync("test:fresh", (datetime.now(), {"data": "fresh"}))

        # Add an expired entry (25 hours ago)
        expired_time = datetime.now() - timedelta(hours=25)
        _cache_set_sync("test:expired", (expired_time, {"data": "expired"}))

        stats = get_xbrl_cache_stats()

        assert stats["l1_total_entries"] == 2
        assert stats["l1_valid_entries"] == 1
        assert stats["l1_expired_entries"] == 1

    def test_cache_utilization_percent(self):
        """Cache stats should calculate utilization percentage."""
        import app.services.edgar.xbrl_service as xbrl_module
        original_max = xbrl_module._cache_max_size
        xbrl_module._cache_max_size = 100

        try:
            for i in range(25):
                _cache_set_sync(f"test:key{i}", (datetime.now(), {"data": i}))

            stats = get_xbrl_cache_stats()
            assert stats["l1_utilization_percent"] == 25.0
        finally:
            xbrl_module._cache_max_size = original_max


class TestAsyncCacheLock:
    """Tests for asyncio.Lock protection of cache operations."""

    def setup_method(self):
        clear_xbrl_cache()

    def teardown_method(self):
        clear_xbrl_cache()

    @pytest.mark.asyncio
    async def test_get_cache_lock_returns_lock(self):
        """_get_cache_lock should return an asyncio.Lock."""
        lock = _get_cache_lock()
        assert isinstance(lock, asyncio.Lock)

    @pytest.mark.asyncio
    async def test_get_cache_lock_returns_same_lock(self):
        """_get_cache_lock should return the same lock instance."""
        lock1 = _get_cache_lock()
        lock2 = _get_cache_lock()
        assert lock1 is lock2

    @pytest.mark.asyncio
    async def test_async_clear_acquires_lock(self):
        """async_clear_xbrl_cache should acquire the cache lock."""
        _cache_set_sync("test:key1", (datetime.now(), {"data": 1}))

        # Clear should work and acquire the lock
        count = await async_clear_xbrl_cache()

        assert count == 1
        assert len(_xbrl_cache) == 0

    @pytest.mark.asyncio
    async def test_concurrent_cache_operations_are_safe(self):
        """Concurrent cache operations should not corrupt the cache."""
        import app.services.edgar.xbrl_service as xbrl_module

        # Mock Redis to avoid actual network calls
        with patch.object(EdgarXBRLService, '_get_from_redis', new_callable=AsyncMock) as mock_redis_get, \
             patch.object(EdgarXBRLService, '_set_to_redis', new_callable=AsyncMock) as mock_redis_set, \
             patch.object(EdgarXBRLService, '_fetch_xbrl_data', new_callable=AsyncMock) as mock_fetch:

            mock_redis_get.return_value = None  # L2 cache miss
            mock_redis_set.return_value = True
            mock_fetch.return_value = {"revenue": [{"period": "2024-01-01", "value": 1000}]}

            service = EdgarXBRLService()

            # Run multiple concurrent cache operations
            tasks = []
            for i in range(10):
                tasks.append(service.get_xbrl_data(f"acc-{i}", f"cik-{i}"))

            results = await asyncio.gather(*tasks)

            # All results should be valid
            assert len(results) == 10
            assert all(r is not None for r in results)

            # Cache should have entries (may be less than 10 due to concurrent access)
            assert len(_xbrl_cache) > 0


class TestConcurrentAccess:
    """Tests for concurrent access patterns."""

    def setup_method(self):
        clear_xbrl_cache()

    def teardown_method(self):
        clear_xbrl_cache()

    @pytest.mark.asyncio
    async def test_concurrent_reads_same_key(self):
        """Multiple concurrent reads of the same key should be safe."""
        # Pre-populate cache
        _cache_set_sync("test:shared", (datetime.now(), {"data": "shared_value"}))

        lock = _get_cache_lock()
        results = []

        async def read_cache():
            async with lock:
                if "test:shared" in _xbrl_cache:
                    _xbrl_cache.move_to_end("test:shared")
                    return _xbrl_cache["test:shared"][1]
            return None

        # Run 50 concurrent reads
        tasks = [read_cache() for _ in range(50)]
        results = await asyncio.gather(*tasks)

        # All reads should return the same value
        assert all(r == {"data": "shared_value"} for r in results)

    @pytest.mark.asyncio
    async def test_concurrent_writes_different_keys(self):
        """Concurrent writes to different keys should all succeed."""
        lock = _get_cache_lock()

        async def write_cache(key: str, value: dict):
            async with lock:
                _cache_set_sync(key, (datetime.now(), value))

        # Run 20 concurrent writes to different keys
        tasks = [write_cache(f"test:key{i}", {"index": i}) for i in range(20)]
        await asyncio.gather(*tasks)

        # All entries should be present
        assert len(_xbrl_cache) == 20
        for i in range(20):
            assert f"test:key{i}" in _xbrl_cache

    @pytest.mark.asyncio
    async def test_mixed_read_write_operations(self):
        """Mixed concurrent reads and writes should be safe."""
        lock = _get_cache_lock()

        # Pre-populate some entries
        for i in range(5):
            _cache_set_sync(f"test:existing{i}", (datetime.now(), {"index": i}))

        read_results = []

        async def read_op(key: str):
            async with lock:
                if key in _xbrl_cache:
                    _xbrl_cache.move_to_end(key)
                    return _xbrl_cache[key][1]
            return None

        async def write_op(key: str, value: dict):
            async with lock:
                _cache_set_sync(key, (datetime.now(), value))

        # Mix reads and writes
        tasks = []
        for i in range(10):
            if i % 2 == 0:
                tasks.append(read_op(f"test:existing{i % 5}"))
            else:
                tasks.append(write_op(f"test:new{i}", {"new": i}))

        await asyncio.gather(*tasks)

        # Original entries should still exist
        for i in range(5):
            assert f"test:existing{i}" in _xbrl_cache


class TestStressConditions:
    """Stress tests for cache under high load."""

    def setup_method(self):
        clear_xbrl_cache()

    def teardown_method(self):
        clear_xbrl_cache()

    @pytest.mark.asyncio
    async def test_rapid_cache_operations(self):
        """Cache should handle rapid sequential operations."""
        lock = _get_cache_lock()

        async def rapid_ops():
            for i in range(100):
                async with lock:
                    _cache_set_sync(f"test:rapid{i}", (datetime.now(), {"i": i}))
                    if f"test:rapid{i}" in _xbrl_cache:
                        _ = _xbrl_cache[f"test:rapid{i}"]

        await rapid_ops()

        # Should have entries (limited by max size)
        assert len(_xbrl_cache) > 0
        assert len(_xbrl_cache) <= _cache_max_size

    @pytest.mark.asyncio
    async def test_cache_under_memory_pressure(self):
        """Cache should correctly evict under memory pressure."""
        import app.services.edgar.xbrl_service as xbrl_module
        original_max = xbrl_module._cache_max_size
        xbrl_module._cache_max_size = 50

        try:
            lock = _get_cache_lock()

            # Add 100 entries (should evict 50)
            for i in range(100):
                async with lock:
                    _cache_set_sync(f"test:pressure{i}", (datetime.now(), {"i": i}))

            # Should have exactly max_size entries
            assert len(_xbrl_cache) == 50

            # Oldest entries should be evicted
            assert "test:pressure0" not in _xbrl_cache
            assert "test:pressure49" not in _xbrl_cache

            # Newest entries should remain
            assert "test:pressure50" in _xbrl_cache
            assert "test:pressure99" in _xbrl_cache
        finally:
            xbrl_module._cache_max_size = original_max

    @pytest.mark.asyncio
    async def test_cache_clear_under_load(self):
        """Clearing cache during concurrent operations should be safe."""
        lock = _get_cache_lock()
        clear_count = 0

        async def add_entries():
            for i in range(20):
                async with lock:
                    _cache_set_sync(f"test:load{i}", (datetime.now(), {"i": i}))
                await asyncio.sleep(0.001)

        async def clear_periodically():
            nonlocal clear_count
            for _ in range(3):
                await asyncio.sleep(0.01)
                count = await async_clear_xbrl_cache()
                clear_count += count

        # Run both concurrently
        await asyncio.gather(add_entries(), clear_periodically())

        # Cache operations should complete without error
        # Final state may have some entries or be empty


# Marker for unit tests
pytestmark = pytest.mark.unit
