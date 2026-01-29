"""
Circuit Breaker Pattern for SEC EDGAR API

Implements the circuit breaker pattern to protect against cascading failures
when SEC EDGAR is experiencing issues. This prevents overwhelming an already
struggling external service and allows for graceful degradation.

States:
- CLOSED: Normal operation, requests flow through
- OPEN: Circuit is tripped, requests fail fast without calling the service
- HALF_OPEN: Testing if service has recovered, allowing limited requests

Usage:
    from app.services.edgar.circuit_breaker import edgar_circuit_breaker

    # Wrap calls to SEC EDGAR
    async with edgar_circuit_breaker:
        result = await some_edgar_operation()

    # Check state before making decisions
    if edgar_circuit_breaker.is_open:
        # Return cached data instead
        pass
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .exceptions import EdgarNetworkError, EdgarRateLimitError, EdgarTimeoutError

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""

    # Number of failures before opening the circuit
    failure_threshold: int = 5

    # Number of successes in half-open state to close the circuit
    success_threshold: int = 2

    # Time in seconds before transitioning from open to half-open
    recovery_timeout: float = 30.0

    # Maximum concurrent requests allowed in half-open state
    half_open_max_requests: int = 3

    # Exceptions that should trip the circuit
    # (business logic errors like NotFound should NOT trip the circuit)
    trip_exceptions: tuple = (
        EdgarNetworkError,
        EdgarTimeoutError,
        EdgarRateLimitError,
        ConnectionError,
        TimeoutError,
        asyncio.TimeoutError,
    )


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker monitoring."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rejected_requests: int = 0  # Requests rejected while circuit is open

    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    last_state_change_time: float = field(default_factory=time.time)

    # Consecutive counts for state transitions
    consecutive_failures: int = 0
    consecutive_successes: int = 0

    def record_success(self) -> None:
        """Record a successful request."""
        self.total_requests += 1
        self.successful_requests += 1
        self.last_success_time = time.time()
        self.consecutive_successes += 1
        self.consecutive_failures = 0

    def record_failure(self) -> None:
        """Record a failed request."""
        self.total_requests += 1
        self.failed_requests += 1
        self.last_failure_time = time.time()
        self.consecutive_failures += 1
        self.consecutive_successes = 0

    def record_rejection(self) -> None:
        """Record a rejected request (circuit open)."""
        self.total_requests += 1
        self.rejected_requests += 1

    def reset_consecutive(self) -> None:
        """Reset consecutive counters on state change."""
        self.consecutive_failures = 0
        self.consecutive_successes = 0

    @property
    def success_rate(self) -> float:
        """Calculate success rate as a percentage."""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests * 100

    def to_dict(self) -> dict:
        """Convert stats to dictionary for monitoring."""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "rejected_requests": self.rejected_requests,
            "success_rate": (
                self.successful_requests / self.total_requests * 100
                if self.total_requests > 0 else 0
            ),
            "last_failure_time": self.last_failure_time,
            "last_success_time": self.last_success_time,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
        }


class CircuitBreaker:
    """
    Async-safe circuit breaker for protecting external service calls.

    Example:
        circuit = CircuitBreaker("sec_edgar")

        async with circuit:
            result = await call_external_service()
    """

    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._stats = CircuitBreakerStats()
        self._lock = asyncio.Lock()
        self._half_open_semaphore = asyncio.Semaphore(
            self.config.half_open_max_requests
        )
        self._opened_at: Optional[float] = None

    @property
    def state(self) -> CircuitState:
        """Get current circuit state, checking for automatic transitions."""
        if self._state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if self._opened_at and (
                time.time() - self._opened_at >= self.config.recovery_timeout
            ):
                return CircuitState.HALF_OPEN
        return self._state

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (rejecting requests)."""
        return self.state == CircuitState.OPEN

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self.state == CircuitState.CLOSED

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing recovery)."""
        return self.state == CircuitState.HALF_OPEN

    @property
    def stats(self) -> CircuitBreakerStats:
        """Get circuit breaker statistics."""
        return self._stats

    def get_status(self) -> dict:
        """Get full status for monitoring endpoints."""
        return {
            "name": self.name,
            "state": self.state.value,
            "stats": self._stats.to_dict(),
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "success_threshold": self.config.success_threshold,
                "recovery_timeout": self.config.recovery_timeout,
            },
            "opened_at": self._opened_at,
            "time_until_half_open": (
                max(0, self.config.recovery_timeout - (time.time() - self._opened_at))
                if self._opened_at and self._state == CircuitState.OPEN
                else None
            ),
        }

    async def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new state with logging."""
        old_state = self._state
        self._state = new_state
        self._stats.last_state_change_time = time.time()
        self._stats.reset_consecutive()

        if new_state == CircuitState.OPEN:
            self._opened_at = time.time()
        elif new_state == CircuitState.CLOSED:
            self._opened_at = None

        logger.warning(
            f"Circuit breaker '{self.name}' transitioned: {old_state.value} -> {new_state.value}"
        )

    async def record_success(self) -> None:
        """Record a successful call and potentially close the circuit."""
        async with self._lock:
            self._stats.record_success()

            if self._state == CircuitState.HALF_OPEN:
                if self._stats.consecutive_successes >= self.config.success_threshold:
                    await self._transition_to(CircuitState.CLOSED)
                    logger.info(
                        f"Circuit breaker '{self.name}' closed after "
                        f"{self.config.success_threshold} successful requests"
                    )

    async def record_failure(self, exc: Exception) -> None:
        """Record a failed call and potentially open the circuit."""
        async with self._lock:
            self._stats.record_failure()

            # Only trip on specific exception types
            if not isinstance(exc, self.config.trip_exceptions):
                logger.debug(
                    f"Circuit breaker '{self.name}' ignoring non-tripping exception: "
                    f"{type(exc).__name__}"
                )
                return

            if self._state == CircuitState.CLOSED:
                if self._stats.consecutive_failures >= self.config.failure_threshold:
                    await self._transition_to(CircuitState.OPEN)
                    logger.error(
                        f"Circuit breaker '{self.name}' opened after "
                        f"{self.config.failure_threshold} consecutive failures"
                    )

            elif self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open state reopens the circuit
                await self._transition_to(CircuitState.OPEN)
                logger.warning(
                    f"Circuit breaker '{self.name}' reopened after failure in half-open state"
                )

    async def __aenter__(self) -> "CircuitBreaker":
        """Enter the circuit breaker context."""
        # Check for automatic transition from OPEN to HALF_OPEN
        if self._state == CircuitState.OPEN:
            if self._opened_at and (
                time.time() - self._opened_at >= self.config.recovery_timeout
            ):
                # Time to transition to half-open - update internal state
                async with self._lock:
                    if self._state == CircuitState.OPEN:  # Double-check after lock
                        self._state = CircuitState.HALF_OPEN
                        self._stats.last_state_change_time = time.time()
                        self._stats.reset_consecutive()
                        logger.info(
                            f"Circuit breaker '{self.name}' transitioned to half-open "
                            f"after {self.config.recovery_timeout}s recovery timeout"
                        )

        current_state = self._state

        if current_state == CircuitState.OPEN:
            self._stats.record_rejection()
            raise CircuitOpenError(
                self.name,
                time_until_recovery=max(
                    0,
                    self.config.recovery_timeout - (time.time() - (self._opened_at or 0))
                )
            )

        if current_state == CircuitState.HALF_OPEN:
            # Limit concurrent requests in half-open state
            # Use very small timeout to fail fast atomically
            # This prevents the TOCTOU race condition between locked() and acquire()
            try:
                await asyncio.wait_for(
                    self._half_open_semaphore.acquire(),
                    timeout=0.001  # 1ms timeout - enough for immediate acquire, fast fail if blocked
                )
            except asyncio.TimeoutError:
                self._stats.record_rejection()
                raise CircuitOpenError(
                    self.name,
                    message="Circuit in half-open state, max concurrent requests reached"
                )

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Exit the circuit breaker context."""
        current_state = self.state

        # Release semaphore if in half-open state
        if current_state == CircuitState.HALF_OPEN:
            self._half_open_semaphore.release()

        if exc_val is None:
            await self.record_success()
        else:
            await self.record_failure(exc_val)

        # Don't suppress exceptions
        return False

    def reset(self) -> None:
        """Manually reset the circuit breaker to closed state."""
        self._state = CircuitState.CLOSED
        self._opened_at = None
        self._stats.reset_consecutive()
        logger.info(f"Circuit breaker '{self.name}' manually reset to closed")


class CircuitOpenError(Exception):
    """Raised when the circuit breaker is open and rejecting requests."""

    def __init__(
        self,
        circuit_name: str,
        message: Optional[str] = None,
        time_until_recovery: Optional[float] = None,
    ):
        self.circuit_name = circuit_name
        self.time_until_recovery = time_until_recovery

        if message is None:
            message = f"Circuit breaker '{circuit_name}' is open"
            if time_until_recovery is not None:
                message += f" (recovery in {time_until_recovery:.1f}s)"

        super().__init__(message)


# Global circuit breaker instance for SEC EDGAR operations
edgar_circuit_breaker = CircuitBreaker(
    "sec_edgar",
    config=CircuitBreakerConfig(
        failure_threshold=5,
        success_threshold=2,
        recovery_timeout=30.0,
        half_open_max_requests=3,
    )
)
