"""
Event Loop Safety Tests

Tests for event loop change detection and connection reset in Redis service.
Ensures Redis connections handle event loop changes gracefully.
"""

import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

# Import Redis service components
from app.services.redis_service import (
    _reset_on_loop_change,
    _get_init_lock,
    get_redis_pool,
    get_redis_client,
    close_redis,
    CACHE_OPERATION_TIMEOUT,
    cache_get,
    cache_set,
)


class TestEventLoopDetection:
    """Tests for event loop change detection."""

    def setup_method(self):
        """Reset module state before each test."""
        import app.services.redis_service as redis_module
        redis_module._pool = None
        redis_module._client = None
        redis_module._init_lock = None
        redis_module._init_lock_loop = None

    @pytest.mark.asyncio
    async def test_reset_on_loop_change_returns_false_when_no_previous_loop(self):
        """_reset_on_loop_change should return False if no previous loop tracked."""
        import app.services.redis_service as redis_module

        # Ensure no previous loop is tracked
        redis_module._init_lock_loop = None

        result = _reset_on_loop_change()
        assert result is False

    @pytest.mark.asyncio
    async def test_reset_on_loop_change_returns_false_when_same_loop(self):
        """_reset_on_loop_change should return False if same loop."""
        import app.services.redis_service as redis_module

        current_loop = asyncio.get_running_loop()
        redis_module._init_lock_loop = current_loop

        result = _reset_on_loop_change()
        assert result is False

    @pytest.mark.asyncio
    async def test_reset_on_loop_change_returns_true_when_different_loop(self):
        """_reset_on_loop_change should return True and reset state when loop changes."""
        import app.services.redis_service as redis_module

        # Simulate a previous loop (different from current)
        mock_old_loop = MagicMock()
        redis_module._init_lock_loop = mock_old_loop
        redis_module._pool = MagicMock()
        redis_module._client = MagicMock()
        redis_module._init_lock = MagicMock()

        result = _reset_on_loop_change()

        assert result is True
        assert redis_module._pool is None
        assert redis_module._client is None
        assert redis_module._init_lock is None
        assert redis_module._init_lock_loop is None

    def test_reset_on_loop_change_handles_no_running_loop(self):
        """_reset_on_loop_change should return False when no running loop."""
        # Called outside of async context
        result = _reset_on_loop_change()
        assert result is False


class TestInitLockManagement:
    """Tests for initialization lock management."""

    def setup_method(self):
        import app.services.redis_service as redis_module
        redis_module._init_lock = None
        redis_module._init_lock_loop = None

    @pytest.mark.asyncio
    async def test_get_init_lock_creates_lock(self):
        """_get_init_lock should create a new lock if none exists."""
        lock = await _get_init_lock()

        assert lock is not None
        assert isinstance(lock, asyncio.Lock)

    @pytest.mark.asyncio
    async def test_get_init_lock_returns_same_lock_in_same_loop(self):
        """_get_init_lock should return the same lock within the same event loop."""
        lock1 = await _get_init_lock()
        lock2 = await _get_init_lock()

        assert lock1 is lock2

    @pytest.mark.asyncio
    async def test_get_init_lock_tracks_loop(self):
        """_get_init_lock should track which loop the lock was created in."""
        import app.services.redis_service as redis_module

        await _get_init_lock()

        current_loop = asyncio.get_running_loop()
        assert redis_module._init_lock_loop is current_loop


class TestRedisPoolLoopSafety:
    """Tests for Redis pool event loop safety."""

    def setup_method(self):
        import app.services.redis_service as redis_module
        redis_module._pool = None
        redis_module._client = None
        redis_module._init_lock = None
        redis_module._init_lock_loop = None

    @pytest.mark.asyncio
    async def test_get_redis_pool_calls_reset_on_loop_change(self):
        """get_redis_pool should check for event loop changes."""
        with patch('app.services.redis_service._reset_on_loop_change') as mock_reset:
            mock_reset.return_value = False

            with patch('app.services.redis_service.ConnectionPool') as mock_pool:
                mock_pool.from_url.return_value = MagicMock()

                await get_redis_pool()

                mock_reset.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_redis_client_calls_reset_on_loop_change(self):
        """get_redis_client should check for event loop changes."""
        with patch('app.services.redis_service._reset_on_loop_change') as mock_reset:
            mock_reset.return_value = False

            with patch('app.services.redis_service.get_redis_pool', new_callable=AsyncMock) as mock_pool:
                mock_pool.return_value = MagicMock()

                await get_redis_client()

                mock_reset.assert_called()


class TestCacheOperationTimeouts:
    """Tests for cache operation timeout behavior."""

    def setup_method(self):
        import app.services.redis_service as redis_module
        redis_module._pool = None
        redis_module._client = None
        redis_module._init_lock = None
        redis_module._init_lock_loop = None

    def test_cache_operation_timeout_is_configured(self):
        """CACHE_OPERATION_TIMEOUT should be set to 2 seconds."""
        assert CACHE_OPERATION_TIMEOUT == 2.0

    @pytest.mark.asyncio
    async def test_cache_get_handles_client_timeout(self):
        """cache_get should handle timeout when getting Redis client."""
        with patch('app.services.redis_service.get_redis_client', new_callable=AsyncMock) as mock_client:
            # Simulate a timeout by making get_redis_client hang
            async def slow_client():
                await asyncio.sleep(10)  # Longer than timeout
                return MagicMock()

            mock_client.side_effect = asyncio.TimeoutError()

            result = await cache_get("test:key")

            assert result is None

    @pytest.mark.asyncio
    async def test_cache_get_handles_get_timeout(self):
        """cache_get should handle timeout when getting value."""
        mock_client = AsyncMock()

        async def slow_get(key):
            await asyncio.sleep(10)
            return "value"

        mock_client.get = slow_get

        with patch('app.services.redis_service.get_redis_client', new_callable=AsyncMock) as mock_get_client:
            mock_get_client.return_value = mock_client

            # Should timeout and return None
            result = await asyncio.wait_for(cache_get("test:key"), timeout=3.0)
            assert result is None

    @pytest.mark.asyncio
    async def test_cache_set_handles_timeout(self):
        """cache_set should handle timeout when setting value."""
        with patch('app.services.redis_service.get_redis_client', new_callable=AsyncMock) as mock_client:
            mock_client.side_effect = asyncio.TimeoutError()

            result = await cache_set("test:key", "value")

            assert result is False


class TestRedisConnectionResetScenarios:
    """Tests for various connection reset scenarios."""

    def setup_method(self):
        import app.services.redis_service as redis_module
        redis_module._pool = None
        redis_module._client = None
        redis_module._init_lock = None
        redis_module._init_lock_loop = None

    @pytest.mark.asyncio
    async def test_stale_pool_is_reset_on_loop_change(self):
        """Stale pool should be reset when event loop changes."""
        import app.services.redis_service as redis_module

        # Simulate stale state from previous loop
        mock_old_loop = MagicMock()
        stale_pool = MagicMock()
        stale_client = MagicMock()

        redis_module._pool = stale_pool
        redis_module._client = stale_client
        redis_module._init_lock = MagicMock()
        redis_module._init_lock_loop = mock_old_loop

        # Reset should detect loop change and clear state
        reset_occurred = _reset_on_loop_change()

        assert reset_occurred is True
        assert redis_module._pool is None
        assert redis_module._client is None

    @pytest.mark.asyncio
    async def test_close_redis_clears_all_state(self):
        """close_redis should clear pool, client, and lock state."""
        import app.services.redis_service as redis_module

        # Setup mock state
        mock_client = AsyncMock()
        mock_pool = AsyncMock()

        redis_module._client = mock_client
        redis_module._pool = mock_pool
        redis_module._init_lock = asyncio.Lock()
        redis_module._init_lock_loop = asyncio.get_running_loop()

        await close_redis()

        assert redis_module._pool is None
        assert redis_module._client is None
        mock_client.close.assert_called_once()
        mock_pool.disconnect.assert_called_once()


class TestConcurrentInitialization:
    """Tests for concurrent initialization safety."""

    def setup_method(self):
        import app.services.redis_service as redis_module
        redis_module._pool = None
        redis_module._client = None
        redis_module._init_lock = None
        redis_module._init_lock_loop = None

    @pytest.mark.asyncio
    async def test_concurrent_pool_initialization_uses_lock(self):
        """Concurrent get_redis_pool calls should be serialized by lock."""
        import app.services.redis_service as redis_module

        init_count = 0
        original_from_url = None

        with patch('app.services.redis_service.ConnectionPool') as mock_pool_class:
            mock_pool = MagicMock()

            def track_init(*args, **kwargs):
                nonlocal init_count
                init_count += 1
                return mock_pool

            mock_pool_class.from_url = track_init

            # Run multiple concurrent initializations
            tasks = [get_redis_pool() for _ in range(5)]
            results = await asyncio.gather(*tasks)

            # Pool should only be created once (double-check pattern)
            assert init_count == 1

            # All calls should return the same pool
            assert all(r is mock_pool for r in results)

    @pytest.mark.asyncio
    async def test_concurrent_client_initialization_uses_lock(self):
        """Concurrent get_redis_client calls should be serialized by lock."""
        import app.services.redis_service as redis_module

        mock_pool = MagicMock()
        client_init_count = 0

        with patch('app.services.redis_service.get_redis_pool', new_callable=AsyncMock) as mock_get_pool:
            mock_get_pool.return_value = mock_pool

            with patch('app.services.redis_service.aioredis.Redis') as mock_redis_class:
                mock_client = MagicMock()

                def track_client_init(*args, **kwargs):
                    nonlocal client_init_count
                    client_init_count += 1
                    return mock_client

                mock_redis_class.side_effect = track_client_init

                # Run multiple concurrent client requests
                tasks = [get_redis_client() for _ in range(5)]
                results = await asyncio.gather(*tasks)

                # Client should only be created once
                assert client_init_count == 1

                # All calls should return the same client
                assert all(r is mock_client for r in results)


# Marker for unit tests
pytestmark = pytest.mark.unit
