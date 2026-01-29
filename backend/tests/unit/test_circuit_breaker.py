"""
Circuit Breaker Tests

Tests for the circuit breaker pattern implementation for SEC EDGAR API.
"""

import asyncio
import pytest

from app.services.edgar.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    CircuitOpenError,
)
from app.services.edgar.exceptions import EdgarTimeoutError, EdgarNetworkError


class TestCircuitBreakerBasic:
    """Tests for basic circuit breaker functionality."""

    @pytest.fixture
    def circuit(self):
        """Create a circuit breaker with fast timeouts for testing."""
        return CircuitBreaker(
            "test_circuit",
            config=CircuitBreakerConfig(
                failure_threshold=3,
                success_threshold=2,
                recovery_timeout=0.1,  # 100ms for fast tests
                half_open_max_requests=2,
            )
        )

    def test_initial_state_is_closed(self, circuit):
        """Circuit breaker starts in closed state."""
        assert circuit.state == CircuitState.CLOSED
        assert circuit.is_closed
        assert not circuit.is_open

    @pytest.mark.asyncio
    async def test_successful_request_keeps_circuit_closed(self, circuit):
        """Successful requests don't affect closed state."""
        async with circuit:
            pass  # Successful request

        assert circuit.is_closed
        assert circuit.stats.successful_requests == 1
        assert circuit.stats.consecutive_successes == 1

    @pytest.mark.asyncio
    async def test_failures_below_threshold_keep_circuit_closed(self, circuit):
        """Failures below threshold don't open the circuit."""
        # Fail twice (threshold is 3)
        for _ in range(2):
            try:
                async with circuit:
                    raise EdgarTimeoutError("test timeout")
            except EdgarTimeoutError:
                pass

        assert circuit.is_closed
        assert circuit.stats.consecutive_failures == 2

    @pytest.mark.asyncio
    async def test_failures_at_threshold_open_circuit(self, circuit):
        """Circuit opens after threshold failures."""
        for _ in range(3):
            try:
                async with circuit:
                    raise EdgarTimeoutError("test timeout")
            except EdgarTimeoutError:
                pass

        assert circuit.is_open
        assert circuit.stats.failed_requests == 3

    @pytest.mark.asyncio
    async def test_open_circuit_rejects_requests(self, circuit):
        """Open circuit rejects requests immediately."""
        # Open the circuit
        for _ in range(3):
            try:
                async with circuit:
                    raise EdgarTimeoutError("test timeout")
            except EdgarTimeoutError:
                pass

        # Try to make a request - should be rejected
        with pytest.raises(CircuitOpenError) as exc_info:
            async with circuit:
                pass

        assert "test_circuit" in str(exc_info.value)
        assert circuit.stats.rejected_requests == 1

    @pytest.mark.asyncio
    async def test_circuit_transitions_to_half_open_after_timeout(self, circuit):
        """Circuit transitions to half-open after recovery timeout."""
        # Open the circuit
        for _ in range(3):
            try:
                async with circuit:
                    raise EdgarTimeoutError("test timeout")
            except EdgarTimeoutError:
                pass

        assert circuit.is_open

        # Wait for recovery timeout
        await asyncio.sleep(0.15)  # 150ms > 100ms recovery timeout

        # State should now be half-open
        assert circuit.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_successful_requests_in_half_open_close_circuit(self, circuit):
        """Successful requests in half-open state close the circuit."""
        # Open the circuit
        for _ in range(3):
            try:
                async with circuit:
                    raise EdgarTimeoutError("test timeout")
            except EdgarTimeoutError:
                pass

        # Wait for half-open
        await asyncio.sleep(0.15)
        assert circuit.state == CircuitState.HALF_OPEN

        # Make successful requests (threshold is 2)
        for _ in range(2):
            async with circuit:
                pass  # Success

        assert circuit.is_closed

    @pytest.mark.asyncio
    async def test_failure_in_half_open_reopens_circuit(self, circuit):
        """A failure in half-open state reopens the circuit."""
        # Open the circuit
        for _ in range(3):
            try:
                async with circuit:
                    raise EdgarTimeoutError("test timeout")
            except EdgarTimeoutError:
                pass

        # Wait for half-open
        await asyncio.sleep(0.15)
        assert circuit.state == CircuitState.HALF_OPEN

        # Fail in half-open state
        try:
            async with circuit:
                raise EdgarNetworkError("test network error")
        except EdgarNetworkError:
            pass

        assert circuit.is_open

    @pytest.mark.asyncio
    async def test_non_trip_exceptions_dont_affect_circuit(self, circuit):
        """Exceptions not in trip_exceptions don't trip the circuit."""
        # ValueError is not in trip_exceptions
        for _ in range(5):
            try:
                async with circuit:
                    raise ValueError("business logic error")
            except ValueError:
                pass

        # Circuit should still be closed
        assert circuit.is_closed
        assert circuit.stats.failed_requests == 5

    def test_manual_reset_closes_circuit(self, circuit):
        """Manual reset closes the circuit."""
        # Simulate open state
        circuit._state = CircuitState.OPEN
        circuit._opened_at = 1.0

        circuit.reset()

        assert circuit.is_closed
        assert circuit._opened_at is None


class TestCircuitBreakerStats:
    """Tests for circuit breaker statistics."""

    @pytest.fixture
    def circuit(self):
        return CircuitBreaker("test_stats")

    @pytest.mark.asyncio
    async def test_stats_track_requests(self, circuit):
        """Stats correctly track request counts."""
        # Make some successful requests
        for _ in range(3):
            async with circuit:
                pass

        assert circuit.stats.total_requests == 3
        assert circuit.stats.successful_requests == 3
        assert circuit.stats.failed_requests == 0

    def test_get_status_returns_complete_info(self, circuit):
        """get_status returns complete circuit breaker info."""
        status = circuit.get_status()

        assert status["name"] == "test_stats"
        assert status["state"] == "closed"
        assert "stats" in status
        assert "config" in status
        assert status["config"]["failure_threshold"] == 5  # default

    @pytest.mark.asyncio
    async def test_success_rate_calculation(self, circuit):
        """Success rate is calculated correctly."""
        # 3 successes, 2 failures = 60% success rate
        for _ in range(3):
            async with circuit:
                pass

        for _ in range(2):
            try:
                async with circuit:
                    raise ValueError("test")  # Non-tripping exception
            except ValueError:
                pass

        assert circuit.stats.success_rate == pytest.approx(60.0, rel=0.1)


class TestCircuitBreakerConcurrency:
    """Tests for circuit breaker concurrency handling."""

    @pytest.mark.asyncio
    async def test_half_open_limits_concurrent_requests(self):
        """Half-open state limits concurrent requests."""
        circuit = CircuitBreaker(
            "test_concurrency",
            config=CircuitBreakerConfig(
                failure_threshold=1,
                recovery_timeout=0.05,
                half_open_max_requests=1,
            )
        )

        # Open the circuit
        try:
            async with circuit:
                raise EdgarTimeoutError("test")
        except EdgarTimeoutError:
            pass

        # Wait for half-open
        await asyncio.sleep(0.1)
        assert circuit.state == CircuitState.HALF_OPEN

        # First request should go through
        async def request1():
            async with circuit:
                await asyncio.sleep(0.1)  # Hold the semaphore

        task1 = asyncio.create_task(request1())
        await asyncio.sleep(0.01)  # Let task1 acquire semaphore

        # Second request should be rejected (semaphore full)
        with pytest.raises(CircuitOpenError):
            async with circuit:
                pass

        await task1
