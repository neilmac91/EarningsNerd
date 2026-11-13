"""
Circuit Breaker Tests

Tests for the circuit breaker pattern implementation for SEC EDGAR API.
"""

import asyncio
import logging
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
                await asyncio.sleep(0.1)  # Hold the slot

        task1 = asyncio.create_task(request1())
        await asyncio.sleep(0.01)  # Let task1 take the slot

        # Second request should be rejected (no slot free)
        with pytest.raises(CircuitOpenError):
            async with circuit:
                pass

        await task1

    @staticmethod
    def _half_open_circuit(max_requests: int) -> CircuitBreaker:
        return CircuitBreaker(
            "test_probe_slots",
            config=CircuitBreakerConfig(
                failure_threshold=1,
                success_threshold=2,
                recovery_timeout=0.05,
                half_open_max_requests=max_requests,
            )
        )

    @staticmethod
    async def _trip(circuit: CircuitBreaker) -> None:
        with pytest.raises(EdgarTimeoutError):
            async with circuit:
                raise EdgarTimeoutError("test")
        await asyncio.sleep(0.1)
        assert circuit.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_a_probe_that_ends_after_the_circuit_reopened_gives_its_slot_back(self):
        """Probes that end after another probe's failure reopened the circuit used to keep their
        slots; once every slot was gone, each half-open window rejected every probe for good."""
        circuit = self._half_open_circuit(3)
        await self._trip(circuit)

        for _ in range(4):  # more rounds than there are slots
            first_failed = asyncio.Event()

            async def failing_probe():
                async with circuit:
                    raise EdgarTimeoutError("still down")

            async def slow_probe():
                async with circuit:
                    await first_failed.wait()  # ends only after the circuit has reopened

            slow = [asyncio.create_task(slow_probe()) for _ in range(2)]
            await asyncio.sleep(0)  # both slow probes are admitted
            with pytest.raises(EdgarTimeoutError):
                await failing_probe()
            assert circuit._state == CircuitState.OPEN
            first_failed.set()
            await asyncio.gather(*slow)
            await asyncio.sleep(0.1)
            assert circuit.state == CircuitState.HALF_OPEN

        # The service is back: two probes pass and the circuit closes.
        async with circuit:
            pass
        async with circuit:
            pass
        assert circuit.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_a_call_admitted_while_closed_frees_no_probe_slot(self):
        """A call admitted while the circuit was closed took no slot, so ending while the circuit is
        half-open must not add one: the limit on concurrent probes would grow by one each time."""
        circuit = self._half_open_circuit(1)
        release = asyncio.Event()

        async def long_call():
            async with circuit:
                await release.wait()

        admitted_closed = asyncio.create_task(long_call())
        await asyncio.sleep(0)
        await self._trip(circuit)

        probe_release = asyncio.Event()

        async def probe():
            async with circuit:
                await probe_release.wait()

        only_probe = asyncio.create_task(probe())
        await asyncio.sleep(0)  # the one slot is taken
        release.set()
        await admitted_closed  # ends while half-open, having taken no slot

        with pytest.raises(CircuitOpenError):
            async with circuit:
                pass

        probe_release.set()
        await only_probe

    @pytest.mark.asyncio
    async def test_a_manual_reset_frees_every_probe_slot(self):
        circuit = self._half_open_circuit(1)
        await self._trip(circuit)
        release = asyncio.Event()

        async def probe():
            async with circuit:
                await release.wait()

        held = asyncio.create_task(probe())
        await asyncio.sleep(0)
        circuit.reset()
        assert circuit._half_open_in_flight == 0  # the reset itself frees the slot, before any new window
        await self._trip(circuit)
        async with circuit:  # the new window has its slot, though the old probe never ended
            pass
        release.set()
        await held

    @pytest.mark.asyncio
    async def test_a_probe_left_from_an_earlier_window_neither_holds_nor_frees_a_slot_of_the_next(self):
        """A new half-open window starts with every slot free, and a probe still running from an
        earlier window gives nothing back to it when it ends: the limit holds across windows."""
        circuit = self._half_open_circuit(2)
        await self._trip(circuit)
        release_old = asyncio.Event()
        release_new = asyncio.Event()

        async def held(release):
            async with circuit:
                await release.wait()

        old = asyncio.create_task(held(release_old))  # the first window: one of its two slots
        await asyncio.sleep(0.01)
        with pytest.raises(EdgarTimeoutError):  # a second probe fails and reopens the circuit
            async with circuit:
                raise EdgarTimeoutError("still down")
        await asyncio.sleep(0.1)
        assert circuit.state == CircuitState.HALF_OPEN

        # The second window has both its slots, though the old probe never ended.
        new = [asyncio.create_task(held(release_new)) for _ in range(2)]
        await asyncio.sleep(0.01)
        assert [task.done() for task in new] == [False, False]

        release_old.set()
        await old  # the old probe ends inside the second window
        with pytest.raises(CircuitOpenError):  # which is still full
            async with circuit:
                pass

        release_new.set()
        await asyncio.gather(*new)

    @pytest.mark.asyncio
    async def test_an_exit_outside_its_entrys_context_says_so_and_leaves_the_count_alone(self, caplog):
        circuit = self._half_open_circuit(1)
        await self._trip(circuit)
        # Entered in a task of its own, so the entry is recorded in that task's context, not this one's.
        await asyncio.create_task(circuit.__aenter__())
        with caplog.at_level(logging.WARNING):
            await circuit.__aexit__(None, None, None)
        assert "found no entry of its own" in caplog.text
        with pytest.raises(CircuitOpenError):  # the slot is still counted in this window
            async with circuit:
                pass


class TestRunWithCircuitBreaker:
    """The `run_with_circuit_breaker` wrapper is what S4 routes the primary edgartools calls
    (edgar client/xbrl/sixk) through. An OPEN breaker must short-circuit the wrapper BEFORE it
    dispatches `func` to the thread pool — that's the resilience guarantee those sites now inherit."""

    @pytest.mark.asyncio
    async def test_open_breaker_short_circuits_without_running_func(self, monkeypatch):
        from app.services.edgar import async_executor

        breaker = CircuitBreaker(
            "test_wrapper",
            config=CircuitBreakerConfig(failure_threshold=1, recovery_timeout=60.0),
        )
        # Trip it open (one tripping failure at threshold=1).
        with pytest.raises(EdgarTimeoutError):
            async with breaker:
                raise EdgarTimeoutError("boom")
        assert breaker.is_open
        # run_with_circuit_breaker reads the module-level singleton; point it at our open breaker.
        monkeypatch.setattr(async_executor, "edgar_circuit_breaker", breaker)

        ran = False

        def _func():
            nonlocal ran
            ran = True
            return "should not run"

        with pytest.raises(CircuitOpenError):
            await async_executor.run_with_circuit_breaker(_func, timeout=5.0)
        assert ran is False  # short-circuited before touching the thread pool
