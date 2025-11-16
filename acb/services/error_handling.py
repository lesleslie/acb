from typing import Any

"""Error Handling Service with Circuit Breaker Patterns.

Provides comprehensive error handling, circuit breaker patterns, and resilience
utilities for ACB applications.

Features:
- Circuit breaker implementation with state management
- Retry mechanisms with exponential backoff
- Error classification and recovery strategies
- Failure rate monitoring and alerting
- Bulkhead isolation patterns
- Graceful degradation support
"""

import time
from collections.abc import Awaitable, Callable
from enum import Enum
from functools import wraps
from statistics import mean

import asyncio
import typing as t
from contextlib import asynccontextmanager
from dataclasses import dataclass

from acb.services.discovery import (
    ServiceCapability,
    create_service_metadata_template,
)

# Service metadata
SERVICE_METADATA = create_service_metadata_template(
    name="Error Handling Service",
    category="error_handling",
    service_type="resilience",
    author="ACB Services Team",
    description="Comprehensive error handling with circuit breaker patterns for ACB applications",
    version="1.0.0",
    capabilities=[
        ServiceCapability.ASYNC_OPERATIONS,
        ServiceCapability.MONITORING,
        ServiceCapability.ERROR_HANDLING,
        ServiceCapability.RESILIENCE_PATTERNS,
    ],
    settings_class="ErrorHandlingServiceSettings",
)


class CircuitBreakerState(Enum):
    """Circuit breaker state enumeration."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, requests blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


class ErrorSeverity(Enum):
    """Error severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RecoveryStrategy(Enum):
    """Error recovery strategies."""

    FAIL_FAST = "fail_fast"
    RETRY = "retry"
    FALLBACK = "fallback"
    CIRCUIT_BREAKER = "circuit_breaker"
    BULKHEAD = "bulkhead"


@dataclass
class ErrorMetrics:
    """Error metrics for monitoring and analysis."""

    error_count: int = 0
    success_count: int = 0
    failure_rate: float = 0.0
    avg_response_time: float = 0.0
    last_error_time: float = 0.0
    recovery_time: float = 0.0

    @property
    def total_requests(self) -> int:
        """Total number of requests."""
        return self.error_count + self.success_count

    @property
    def success_rate(self) -> float:
        """Success rate percentage."""
        if self.total_requests == 0:
            return 100.0
        return (self.success_count / self.total_requests) * 100.0


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""

    failure_threshold: int = 5  # Failures before opening
    success_threshold: int = 3  # Successes to close from half-open
    timeout: float = 60.0  # Time to wait before half-open
    failure_rate_threshold: float = 50.0  # Failure rate % to trigger
    min_requests: int = 10  # Minimum requests before rate calculation
    max_failures: int = 100  # Maximum failures to track

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.failure_threshold <= 0:
            msg = "failure_threshold must be positive"
            raise ValueError(msg)
        if self.success_threshold <= 0:
            msg = "success_threshold must be positive"
            raise ValueError(msg)
        if self.timeout <= 0:
            msg = "timeout must be positive"
            raise ValueError(msg)


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""

    def __init__(
        self,
        message: str,
        state: CircuitBreakerState,
        metrics: ErrorMetrics,
    ) -> None:
        super().__init__(message)
        self.state = state
        self.metrics = metrics


class CircuitBreaker:
    """Circuit breaker implementation with state management."""

    def __init__(self, name: str, config: CircuitBreakerConfig | None = None) -> None:
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitBreakerState.CLOSED
        self._metrics = ErrorMetrics()
        self._last_failure_time = 0.0
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._response_times: list[float] = []
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitBreakerState:
        """Current circuit breaker state."""
        return self._state

    @property
    def metrics(self) -> ErrorMetrics:
        """Current error metrics."""
        return self._metrics

    async def call(
        self,
        func: Callable[..., Awaitable[t.Any]],
        *args: t.Any,
        **kwargs: t.Any,
    ) -> t.Any:
        """Execute a function through the circuit breaker."""
        async with self._lock:
            await self._check_state()

        start_time = time.perf_counter()

        try:
            result = await func(*args, **kwargs)
            execution_time = time.perf_counter() - start_time

            async with self._lock:
                await self._record_success(execution_time)
                # Check if we should close the circuit after recording success
                await self._check_state_after_success()

            return result

        except Exception:
            execution_time = time.perf_counter() - start_time

            async with self._lock:
                await self._record_failure(execution_time)
                # Check if we should open the circuit after recording failure
                await self._check_state_after_failure()

            raise

    async def _check_state(self) -> None:
        """Check and update circuit breaker state."""
        now = time.perf_counter()

        if self._state == CircuitBreakerState.OPEN:
            if now - self._last_failure_time >= self.config.timeout:
                self._state = CircuitBreakerState.HALF_OPEN
                self._consecutive_successes = 0

        elif self._state == CircuitBreakerState.HALF_OPEN:
            if self._consecutive_successes >= self.config.success_threshold:
                self._state = CircuitBreakerState.CLOSED
                self._consecutive_failures = 0

        # Check if we should open the circuit
        if self._state == CircuitBreakerState.CLOSED and (
            self._consecutive_failures >= self.config.failure_threshold
            or self._should_open_based_on_rate()
        ):
            self._state = CircuitBreakerState.OPEN
            self._last_failure_time = now

        # Block requests if circuit is open
        if self._state == CircuitBreakerState.OPEN:
            msg = f"Circuit breaker '{self.name}' is OPEN"
            raise CircuitBreakerError(
                msg,
                self._state,
                self._metrics,
            )

    def _should_open_based_on_rate(self) -> bool:
        """Check if circuit should open based on failure rate."""
        if self._metrics.total_requests < self.config.min_requests:
            return False

        return self._metrics.failure_rate >= self.config.failure_rate_threshold

    async def _record_success(self, execution_time: float) -> None:
        """Record a successful operation."""
        self._metrics.success_count += 1
        self._consecutive_successes += 1
        self._consecutive_failures = 0

        self._response_times.append(execution_time)
        if len(self._response_times) > 100:  # Keep last 100 response times
            self._response_times.pop(0)

        self._update_metrics()

    async def _record_failure(self, execution_time: float) -> None:
        """Record a failed operation."""
        self._metrics.error_count += 1
        self._metrics.last_error_time = time.perf_counter()
        self._consecutive_failures += 1
        self._consecutive_successes = 0

        self._response_times.append(execution_time)
        if len(self._response_times) > 100:
            self._response_times.pop(0)

        self._update_metrics()

    async def _check_state_after_failure(self) -> None:
        """Check if circuit should open after recording a failure."""
        if self._state == CircuitBreakerState.CLOSED:
            # Check if we should open the circuit based on failure count or rate
            if (
                self._consecutive_failures >= self.config.failure_threshold
                or self._should_open_based_on_rate()
            ):
                self._state = CircuitBreakerState.OPEN
                self._last_failure_time = time.perf_counter()

    async def _check_state_after_success(self) -> None:
        """Check if circuit should close after recording a success."""
        if self._state == CircuitBreakerState.HALF_OPEN:
            # Check if we should close the circuit based on success count
            if self._consecutive_successes >= self.config.success_threshold:
                self._state = CircuitBreakerState.CLOSED
                self._consecutive_failures = 0

    def _update_metrics(self) -> None:
        """Update calculated metrics."""
        total = self._metrics.total_requests
        if total > 0:
            self._metrics.failure_rate = (self._metrics.error_count / total) * 100.0

        if self._response_times:
            self._metrics.avg_response_time = mean(self._response_times)

    async def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        async with self._lock:
            self._state = CircuitBreakerState.CLOSED
            self._metrics = ErrorMetrics()
            self._consecutive_failures = 0
            self._consecutive_successes = 0
            self._response_times = []

    def get_state_info(self) -> dict[str, t.Any]:
        """Get detailed state information."""
        return {
            "name": self.name,
            "state": self._state.value,
            "metrics": {
                "error_count": self._metrics.error_count,
                "success_count": self._metrics.success_count,
                "total_requests": self._metrics.total_requests,
                "failure_rate": self._metrics.failure_rate,
                "success_rate": self._metrics.success_rate,
                "avg_response_time": self._metrics.avg_response_time,
                "last_error_time": self._metrics.last_error_time,
            },
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "success_threshold": self.config.success_threshold,
                "timeout": self.config.timeout,
                "failure_rate_threshold": self.config.failure_rate_threshold,
            },
            "internal_state": {
                "consecutive_failures": self._consecutive_failures,
                "consecutive_successes": self._consecutive_successes,
                "last_failure_time": self._last_failure_time,
            },
        }


@dataclass
class RetryConfig:
    """Retry mechanism configuration."""

    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    jitter: bool = True
    retry_exceptions: tuple[type[Exception], ...] = (Exception,)

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.max_attempts <= 0:
            msg = "max_attempts must be positive"
            raise ValueError(msg)
        if self.base_delay <= 0:
            msg = "base_delay must be positive"
            raise ValueError(msg)


class RetryableError(Exception):
    """Wrapper for retryable errors."""

    def __init__(
        self,
        original_error: Exception,
        attempt: int,
        max_attempts: int,
    ) -> None:
        super().__init__(f"Retry {attempt}/{max_attempts}: {original_error}")
        self.original_error = original_error
        self.attempt = attempt
        self.max_attempts = max_attempts


class ErrorHandlingService:
    """Service for comprehensive error handling and resilience patterns."""

    SERVICE_METADATA = SERVICE_METADATA

    def __init__(self) -> None:
        self._circuit_breakers: dict[str, CircuitBreaker] = {}
        self._error_handlers: dict[type[Exception], Callable[..., Any]] = {}
        self._fallback_handlers: dict[str, Callable[..., Any]] = {}
        self._global_metrics = ErrorMetrics()
        self._bulkheads: dict[str, asyncio.Semaphore] = {}

    def create_circuit_breaker(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
    ) -> CircuitBreaker:
        """Create or get a circuit breaker."""
        if name not in self._circuit_breakers:
            self._circuit_breakers[name] = CircuitBreaker(name, config)
        return self._circuit_breakers[name]

    def get_circuit_breaker(self, name: str) -> CircuitBreaker | None:
        """Get an existing circuit breaker."""
        return self._circuit_breakers.get(name)

    def list_circuit_breakers(self) -> list[str]:
        """List all circuit breaker names."""
        return list(self._circuit_breakers.keys())

    async def reset_circuit_breaker(self, name: str) -> bool:
        """Reset a circuit breaker."""
        if name in self._circuit_breakers:
            await self._circuit_breakers[name].reset()
            return True
        return False

    def register_error_handler(
        self,
        exception_type: type[Exception],
        handler: Callable[[Exception], t.Any],
    ) -> None:
        """Register a global error handler for specific exception types."""
        self._error_handlers[exception_type] = handler

    def register_fallback_handler(
        self,
        operation_name: str,
        handler: Callable[..., t.Any],
    ) -> None:
        """Register a fallback handler for operations."""
        self._fallback_handlers[operation_name] = handler

    def create_bulkhead(self, name: str, max_concurrent: int) -> asyncio.Semaphore:
        """Create a bulkhead for resource isolation."""
        semaphore = asyncio.Semaphore(max_concurrent)
        self._bulkheads[name] = semaphore
        return semaphore

    def get_bulkhead(self, name: str) -> asyncio.Semaphore | None:
        """Get an existing bulkhead."""
        return self._bulkheads.get(name)

    async def with_circuit_breaker(
        self,
        circuit_breaker_name: str,
        func: Callable[..., Awaitable[t.Any]],
        *args: t.Any,
        config: CircuitBreakerConfig | None = None,
        **kwargs: t.Any,
    ) -> t.Any:
        """Execute function with circuit breaker protection."""
        cb = self.create_circuit_breaker(circuit_breaker_name, config)
        return await cb.call(func, *args, **kwargs)

    async def with_retry(
        self,
        func: Callable[..., Awaitable[t.Any]],
        *args: t.Any,
        config: RetryConfig | None = None,
        **kwargs: t.Any,
    ) -> t.Any:
        """Execute function with retry logic."""
        retry_config = config or RetryConfig()
        last_exception = None

        for attempt in range(1, retry_config.max_attempts + 1):
            try:
                return await func(*args, **kwargs)
            except retry_config.retry_exceptions as e:
                last_exception = e

                if attempt == retry_config.max_attempts:
                    raise RetryableError(e, attempt, retry_config.max_attempts)

                # Calculate delay with exponential backoff
                delay = min(
                    retry_config.base_delay
                    * (retry_config.backoff_factor ** (attempt - 1)),
                    retry_config.max_delay,
                )

                # Add jitter to prevent thundering herd
                if retry_config.jitter:
                    import random

                    delay *= 0.5 + random.random() * 0.5

                await asyncio.sleep(delay)

        # This should never be reached, but just in case
        if last_exception:
            raise last_exception
        msg = "Retry failed without exception"
        raise RuntimeError(msg)

    async def with_fallback(
        self,
        operation_name: str,
        func: Callable[..., Awaitable[t.Any]],
        *args: t.Any,
        fallback_handler: Callable[..., t.Any] | None = None,
        **kwargs: t.Any,
    ) -> t.Any:
        """Execute function with fallback on failure."""
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            # Try registered fallback first
            handler = fallback_handler or self._fallback_handlers.get(operation_name)

            if handler:
                if asyncio.iscoroutinefunction(handler):
                    return await handler(e, *args, **kwargs)
                return handler(e, *args, **kwargs)

            # No fallback available, re-raise
            raise

    @asynccontextmanager
    async def with_bulkhead(
        self,
        bulkhead_name: str,
        max_concurrent: int | None = None,
    ) -> t.AsyncGenerator[None]:
        """Execute within a bulkhead for resource isolation."""
        if bulkhead_name not in self._bulkheads and max_concurrent:
            self.create_bulkhead(bulkhead_name, max_concurrent)

        bulkhead = self.get_bulkhead(bulkhead_name)
        if not bulkhead:
            msg = (
                f"Bulkhead '{bulkhead_name}' not found and max_concurrent not provided"
            )
            raise ValueError(msg)

        async with bulkhead:
            yield

    async def handle_error(
        self,
        error: Exception,
        context: dict[str, t.Any] | None = None,
    ) -> t.Any:
        """Handle an error using registered handlers."""
        # Update global metrics
        self._global_metrics.error_count += 1
        self._global_metrics.last_error_time = time.perf_counter()

        # Look for specific handler
        for exception_type, handler in self._error_handlers.items():
            if isinstance(error, exception_type):
                if asyncio.iscoroutinefunction(handler):
                    return await handler(error)
                return handler(error)

        # No specific handler found, re-raise
        raise error

    def get_circuit_breaker_status(self) -> dict[str, dict[str, t.Any]]:
        """Get status of all circuit breakers."""
        return {
            name: cb.get_state_info() for name, cb in self._circuit_breakers.items()
        }

    def get_global_metrics(self) -> dict[str, t.Any]:
        """Get global error handling metrics."""
        return {
            "total_errors": self._global_metrics.error_count,
            "last_error_time": self._global_metrics.last_error_time,
            "circuit_breakers": len(self._circuit_breakers),
            "error_handlers": len(self._error_handlers),
            "fallback_handlers": len(self._fallback_handlers),
            "bulkheads": len(self._bulkheads),
        }

    async def health_check(self) -> dict[str, t.Any]:
        """Perform health check of error handling service."""
        circuit_breaker_health = {}

        for name, cb in self._circuit_breakers.items():
            circuit_breaker_health[name] = {
                "state": cb.state.value,
                "healthy": cb.state != CircuitBreakerState.OPEN,
                "failure_rate": cb.metrics.failure_rate,
                "total_requests": cb.metrics.total_requests,
            }

        overall_healthy = all(
            info["healthy"] for info in circuit_breaker_health.values()
        )

        return {
            "service": "error_handling",
            "healthy": overall_healthy,
            "circuit_breakers": circuit_breaker_health,
            "global_metrics": self.get_global_metrics(),
            "timestamp": time.time(),
        }


# Decorators for easy integration


def circuit_breaker(
    name: str,
    config: CircuitBreakerConfig | None = None,
    service: ErrorHandlingService | None = None,
) -> Callable[[Callable[..., Awaitable[t.Any]]], Callable[..., Awaitable[t.Any]]]:
    """Decorator to add circuit breaker protection to functions."""

    def decorator(
        func: Callable[..., Awaitable[t.Any]],
    ) -> Callable[..., Awaitable[t.Any]]:
        @wraps(func)
        async def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
            error_service = service or ErrorHandlingService()
            return await error_service.with_circuit_breaker(
                name,
                func,
                *args,
                config=config,
                **kwargs,
            )

        return wrapper

    return decorator


def retry(
    config: RetryConfig | None = None,
    service: ErrorHandlingService | None = None,
) -> Callable[[Callable[..., Awaitable[t.Any]]], Callable[..., Awaitable[t.Any]]]:
    """Decorator to add retry logic to functions."""

    def decorator(
        func: Callable[..., Awaitable[t.Any]],
    ) -> Callable[..., Awaitable[t.Any]]:
        @wraps(func)
        async def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
            error_service = service or ErrorHandlingService()
            return await error_service.with_retry(func, *args, config=config, **kwargs)

        return wrapper

    return decorator


def fallback(
    operation_name: str,
    fallback_handler: Callable[..., t.Any] | None = None,
    service: ErrorHandlingService | None = None,
) -> Callable[[Callable[..., Awaitable[t.Any]]], Callable[..., Awaitable[t.Any]]]:
    """Decorator to add fallback handling to functions."""

    def decorator(
        func: Callable[..., Awaitable[t.Any]],
    ) -> Callable[..., Awaitable[t.Any]]:
        @wraps(func)
        async def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
            error_service = service or ErrorHandlingService()
            return await error_service.with_fallback(
                operation_name,
                func,
                *args,
                fallback_handler=fallback_handler,
                **kwargs,
            )

        return wrapper

    return decorator


def bulkhead(
    name: str,
    max_concurrent: int,
    service: ErrorHandlingService | None = None,
) -> Callable[[Callable[..., Awaitable[t.Any]]], Callable[..., Awaitable[t.Any]]]:
    """Decorator to add bulkhead isolation to functions."""

    def decorator(
        func: Callable[..., Awaitable[t.Any]],
    ) -> Callable[..., Awaitable[t.Any]]:
        @wraps(func)
        async def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
            error_service = service or ErrorHandlingService()
            async with error_service.with_bulkhead(name, max_concurrent):
                return await func(*args, **kwargs)

        return wrapper

    return decorator


# Utility functions for error classification


def classify_error_severity(error: Exception) -> ErrorSeverity:
    """Classify error severity based on exception type."""
    if isinstance(error, SystemExit | KeyboardInterrupt):
        return ErrorSeverity.CRITICAL
    if isinstance(error, MemoryError | OSError):
        return ErrorSeverity.HIGH
    if isinstance(error, ValueError | TypeError | AttributeError):
        return ErrorSeverity.MEDIUM
    return ErrorSeverity.LOW


def suggest_recovery_strategy(error: Exception) -> RecoveryStrategy:
    """Suggest recovery strategy based on error type."""
    if isinstance(error, ConnectionError | TimeoutError):
        return RecoveryStrategy.RETRY
    if isinstance(error, PermissionError | AuthenticationError):
        return RecoveryStrategy.FAIL_FAST
    if isinstance(error, MemoryError | OSError):
        return RecoveryStrategy.CIRCUIT_BREAKER
    return RecoveryStrategy.FALLBACK


# Custom exceptions for the error handling service


class AuthenticationError(Exception):
    """Authentication related errors."""


class BulkheadFullError(Exception):
    """Raised when bulkhead capacity is exceeded."""

    def __init__(self, bulkhead_name: str, max_concurrent: int) -> None:
        super().__init__(f"Bulkhead '{bulkhead_name}' is full (max: {max_concurrent})")
        self.bulkhead_name = bulkhead_name
        self.max_concurrent = max_concurrent


class RetryExhaustedError(Exception):
    """Raised when all retry attempts are exhausted."""

    def __init__(self, original_error: Exception, attempts: int) -> None:
        super().__init__(f"Retry exhausted after {attempts} attempts: {original_error}")
        self.original_error = original_error
        self.attempts = attempts
