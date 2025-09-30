"""Tests for Error Handling Service."""

import asyncio
import pytest
import time
from unittest.mock import AsyncMock, MagicMock

from acb.services.error_handling import (
    ErrorHandlingService,
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerState,
    CircuitBreakerError,
    RetryConfig,
    RetryableError,
    ErrorSeverity,
    RecoveryStrategy,
    classify_error_severity,
    suggest_recovery_strategy,
    circuit_breaker,
    retry,
    fallback,
    bulkhead,
)


class TestCircuitBreakerConfig:
    """Test CircuitBreakerConfig class."""

    def test_init_valid_config(self):
        """Test circuit breaker config initialization with valid values."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout=30.0,
            failure_rate_threshold=75.0
        )

        assert config.failure_threshold == 3
        assert config.success_threshold == 2
        assert config.timeout == 30.0
        assert config.failure_rate_threshold == 75.0

    def test_init_invalid_config(self):
        """Test circuit breaker config validation."""
        with pytest.raises(ValueError, match="failure_threshold must be positive"):
            CircuitBreakerConfig(failure_threshold=0)

        with pytest.raises(ValueError, match="success_threshold must be positive"):
            CircuitBreakerConfig(success_threshold=0)

        with pytest.raises(ValueError, match="timeout must be positive"):
            CircuitBreakerConfig(timeout=0)


class TestCircuitBreaker:
    """Test CircuitBreaker class."""

    def test_init(self):
        """Test circuit breaker initialization."""
        cb = CircuitBreaker("test_circuit")

        assert cb.name == "test_circuit"
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.metrics.error_count == 0
        assert cb.metrics.success_count == 0

    @pytest.mark.asyncio
    async def test_successful_calls(self):
        """Test successful function calls through circuit breaker."""
        cb = CircuitBreaker("test_circuit")

        async def successful_func():
            return "success"

        result = await cb.call(successful_func)

        assert result == "success"
        assert cb.metrics.success_count == 1
        assert cb.metrics.error_count == 0
        assert cb.state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_failing_calls_open_circuit(self):
        """Test that failing calls eventually open the circuit."""
        config = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreaker("test_circuit", config)

        async def failing_func():
            raise ValueError("Test error")

        # Fail enough times to open circuit
        for _ in range(3):
            with pytest.raises(ValueError):
                await cb.call(failing_func)

        assert cb.state == CircuitBreakerState.OPEN
        assert cb.metrics.error_count == 3

        # Next call should raise CircuitBreakerError
        with pytest.raises(CircuitBreakerError):
            await cb.call(failing_func)

    @pytest.mark.asyncio
    async def test_half_open_state_recovery(self):
        """Test circuit breaker recovery through half-open state."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            success_threshold=2,
            timeout=0.1
        )
        cb = CircuitBreaker("test_circuit", config)

        async def failing_func():
            raise ValueError("Test error")

        async def successful_func():
            return "success"

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await cb.call(failing_func)

        assert cb.state == CircuitBreakerState.OPEN

        # Wait for timeout
        await asyncio.sleep(0.15)

        # Circuit should go to half-open on next call
        result = await cb.call(successful_func)
        assert result == "success"
        assert cb.state == CircuitBreakerState.HALF_OPEN

        # One more success should close it
        result = await cb.call(successful_func)
        assert result == "success"
        assert cb.state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_reset(self):
        """Test circuit breaker reset functionality."""
        cb = CircuitBreaker("test_circuit")

        async def failing_func():
            raise ValueError("Test error")

        # Generate some failures
        with pytest.raises(ValueError):
            await cb.call(failing_func)

        assert cb.metrics.error_count == 1

        # Reset
        await cb.reset()

        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.metrics.error_count == 0
        assert cb.metrics.success_count == 0

    def test_get_state_info(self):
        """Test getting circuit breaker state information."""
        cb = CircuitBreaker("test_circuit")
        info = cb.get_state_info()

        assert info["name"] == "test_circuit"
        assert info["state"] == "closed"
        assert "metrics" in info
        assert "config" in info
        assert "internal_state" in info


class TestRetryConfig:
    """Test RetryConfig class."""

    def test_init_valid_config(self):
        """Test retry config initialization with valid values."""
        config = RetryConfig(
            max_attempts=5,
            base_delay=0.5,
            max_delay=30.0,
            backoff_factor=1.5
        )

        assert config.max_attempts == 5
        assert config.base_delay == 0.5
        assert config.max_delay == 30.0
        assert config.backoff_factor == 1.5

    def test_init_invalid_config(self):
        """Test retry config validation."""
        with pytest.raises(ValueError, match="max_attempts must be positive"):
            RetryConfig(max_attempts=0)

        with pytest.raises(ValueError, match="base_delay must be positive"):
            RetryConfig(base_delay=0)


class TestErrorHandlingService:
    """Test ErrorHandlingService class."""

    def test_init(self):
        """Test error handling service initialization."""
        service = ErrorHandlingService()

        assert len(service._circuit_breakers) == 0
        assert len(service._error_handlers) == 0
        assert len(service._fallback_handlers) == 0

    def test_create_circuit_breaker(self):
        """Test creating circuit breakers."""
        service = ErrorHandlingService()

        cb = service.create_circuit_breaker("test_cb")
        assert cb.name == "test_cb"
        assert "test_cb" in service._circuit_breakers

        # Getting the same one should return existing
        cb2 = service.create_circuit_breaker("test_cb")
        assert cb is cb2

    def test_get_circuit_breaker(self):
        """Test getting circuit breakers."""
        service = ErrorHandlingService()

        # Non-existent circuit breaker
        assert service.get_circuit_breaker("missing") is None

        # Create and get
        cb = service.create_circuit_breaker("test_cb")
        retrieved = service.get_circuit_breaker("test_cb")
        assert retrieved is cb

    def test_list_circuit_breakers(self):
        """Test listing circuit breakers."""
        service = ErrorHandlingService()

        assert service.list_circuit_breakers() == []

        service.create_circuit_breaker("cb1")
        service.create_circuit_breaker("cb2")

        names = service.list_circuit_breakers()
        assert set(names) == {"cb1", "cb2"}

    @pytest.mark.asyncio
    async def test_reset_circuit_breaker(self):
        """Test resetting circuit breakers."""
        service = ErrorHandlingService()

        # Non-existent circuit breaker
        assert await service.reset_circuit_breaker("missing") is False

        # Existing circuit breaker
        cb = service.create_circuit_breaker("test_cb")
        cb._metrics.error_count = 5  # Simulate some errors

        assert await service.reset_circuit_breaker("test_cb") is True
        assert cb.metrics.error_count == 0

    def test_register_error_handler(self):
        """Test registering error handlers."""
        service = ErrorHandlingService()

        def handle_value_error(error):
            return "handled"

        service.register_error_handler(ValueError, handle_value_error)

        assert ValueError in service._error_handlers
        assert service._error_handlers[ValueError] is handle_value_error

    def test_register_fallback_handler(self):
        """Test registering fallback handlers."""
        service = ErrorHandlingService()

        def fallback_handler():
            return "fallback"

        service.register_fallback_handler("test_op", fallback_handler)

        assert "test_op" in service._fallback_handlers
        assert service._fallback_handlers["test_op"] is fallback_handler

    def test_create_bulkhead(self):
        """Test creating bulkheads."""
        service = ErrorHandlingService()

        bulkhead = service.create_bulkhead("test_bulkhead", 5)

        assert "test_bulkhead" in service._bulkheads
        assert isinstance(bulkhead, asyncio.Semaphore)

    def test_get_bulkhead(self):
        """Test getting bulkheads."""
        service = ErrorHandlingService()

        # Non-existent bulkhead
        assert service.get_bulkhead("missing") is None

        # Create and get
        bulkhead = service.create_bulkhead("test_bulkhead", 5)
        retrieved = service.get_bulkhead("test_bulkhead")
        assert retrieved is bulkhead

    @pytest.mark.asyncio
    async def test_with_circuit_breaker(self):
        """Test executing function with circuit breaker."""
        service = ErrorHandlingService()

        async def test_func():
            return "success"

        result = await service.with_circuit_breaker("test_cb", test_func)

        assert result == "success"
        assert "test_cb" in service._circuit_breakers

    @pytest.mark.asyncio
    async def test_with_retry_success(self):
        """Test retry with eventual success."""
        service = ErrorHandlingService()
        call_count = 0

        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary failure")
            return "success"

        config = RetryConfig(max_attempts=5, base_delay=0.01)
        result = await service.with_retry(flaky_func, config=config)

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_with_retry_exhausted(self):
        """Test retry with all attempts exhausted."""
        service = ErrorHandlingService()

        async def always_failing_func():
            raise ValueError("Always fails")

        config = RetryConfig(max_attempts=3, base_delay=0.01)

        with pytest.raises(RetryableError) as exc_info:
            await service.with_retry(always_failing_func, config=config)

        assert exc_info.value.attempt == 3
        assert exc_info.value.max_attempts == 3

    @pytest.mark.asyncio
    async def test_with_fallback_success(self):
        """Test fallback when primary function succeeds."""
        service = ErrorHandlingService()

        async def primary_func():
            return "primary"

        async def fallback_func(*args, **kwargs):
            return "fallback"

        result = await service.with_fallback(
            "test_op", primary_func, fallback_handler=fallback_func
        )

        assert result == "primary"

    @pytest.mark.asyncio
    async def test_with_fallback_failure(self):
        """Test fallback when primary function fails."""
        service = ErrorHandlingService()

        async def primary_func():
            raise ValueError("Primary failed")

        async def fallback_func(error, *args, **kwargs):
            return f"fallback: {error}"

        result = await service.with_fallback(
            "test_op", primary_func, fallback_handler=fallback_func
        )

        assert "fallback: Primary failed" in result

    @pytest.mark.asyncio
    async def test_with_fallback_registered_handler(self):
        """Test fallback with registered handler."""
        service = ErrorHandlingService()

        async def primary_func():
            raise ValueError("Primary failed")

        async def fallback_func(error, *args, **kwargs):
            return "registered fallback"

        service.register_fallback_handler("test_op", fallback_func)

        result = await service.with_fallback("test_op", primary_func)
        assert result == "registered fallback"

    @pytest.mark.asyncio
    async def test_with_bulkhead(self):
        """Test bulkhead execution."""
        service = ErrorHandlingService()

        async with service.with_bulkhead("test_bulkhead", 2):
            assert "test_bulkhead" in service._bulkheads

    @pytest.mark.asyncio
    async def test_with_bulkhead_existing(self):
        """Test bulkhead with existing semaphore."""
        service = ErrorHandlingService()
        service.create_bulkhead("test_bulkhead", 3)

        async with service.with_bulkhead("test_bulkhead"):
            pass  # Should work with existing bulkhead

    @pytest.mark.asyncio
    async def test_with_bulkhead_missing(self):
        """Test bulkhead with missing semaphore and no max_concurrent."""
        service = ErrorHandlingService()

        with pytest.raises(ValueError, match="Bulkhead .* not found"):
            async with service.with_bulkhead("missing_bulkhead"):
                pass

    @pytest.mark.asyncio
    async def test_handle_error_with_handler(self):
        """Test error handling with registered handler."""
        service = ErrorHandlingService()

        async def handle_value_error(error):
            return f"handled: {error}"

        service.register_error_handler(ValueError, handle_value_error)

        error = ValueError("test error")
        result = await service.handle_error(error)

        assert result == "handled: test error"

    @pytest.mark.asyncio
    async def test_handle_error_no_handler(self):
        """Test error handling without registered handler."""
        service = ErrorHandlingService()

        error = ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            await service.handle_error(error)

    def test_get_circuit_breaker_status(self):
        """Test getting circuit breaker status."""
        service = ErrorHandlingService()

        cb1 = service.create_circuit_breaker("cb1")
        cb2 = service.create_circuit_breaker("cb2")

        status = service.get_circuit_breaker_status()

        assert "cb1" in status
        assert "cb2" in status
        assert status["cb1"]["name"] == "cb1"
        assert status["cb2"]["name"] == "cb2"

    def test_get_global_metrics(self):
        """Test getting global metrics."""
        service = ErrorHandlingService()

        service.create_circuit_breaker("cb1")
        service.register_error_handler(ValueError, lambda e: None)
        service.register_fallback_handler("op1", lambda: None)
        service.create_bulkhead("bulk1", 5)

        metrics = service.get_global_metrics()

        assert metrics["circuit_breakers"] == 1
        assert metrics["error_handlers"] == 1
        assert metrics["fallback_handlers"] == 1
        assert metrics["bulkheads"] == 1

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test service health check."""
        service = ErrorHandlingService()

        # Create some circuit breakers
        cb1 = service.create_circuit_breaker("cb1")
        cb2 = service.create_circuit_breaker("cb2")

        health = await service.health_check()

        assert health["service"] == "error_handling"
        assert health["healthy"] is True
        assert "cb1" in health["circuit_breakers"]
        assert "cb2" in health["circuit_breakers"]
        assert "global_metrics" in health
        assert "timestamp" in health


class TestDecorators:
    """Test decorator functions."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_decorator(self):
        """Test circuit breaker decorator."""

        @circuit_breaker("test_decorator")
        async def test_func():
            return "success"

        result = await test_func()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_retry_decorator(self):
        """Test retry decorator."""
        call_count = 0

        @retry(RetryConfig(max_attempts=3, base_delay=0.01))
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Temporary failure")
            return "success"

        result = await flaky_func()
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_fallback_decorator(self):
        """Test fallback decorator."""

        async def fallback_handler(error, *args, **kwargs):
            return "fallback result"

        @fallback("test_op", fallback_handler=fallback_handler)
        async def failing_func():
            raise ValueError("Always fails")

        result = await failing_func()
        assert result == "fallback result"

    @pytest.mark.asyncio
    async def test_bulkhead_decorator(self):
        """Test bulkhead decorator."""

        @bulkhead("test_bulkhead", 2)
        async def test_func():
            return "success"

        result = await test_func()
        assert result == "success"


class TestUtilityFunctions:
    """Test utility functions."""

    def test_classify_error_severity(self):
        """Test error severity classification."""
        assert classify_error_severity(SystemExit()) == ErrorSeverity.CRITICAL
        assert classify_error_severity(KeyboardInterrupt()) == ErrorSeverity.CRITICAL
        assert classify_error_severity(MemoryError()) == ErrorSeverity.HIGH
        assert classify_error_severity(OSError()) == ErrorSeverity.HIGH
        assert classify_error_severity(ValueError()) == ErrorSeverity.MEDIUM
        assert classify_error_severity(TypeError()) == ErrorSeverity.MEDIUM
        assert classify_error_severity(AttributeError()) == ErrorSeverity.MEDIUM
        assert classify_error_severity(RuntimeError()) == ErrorSeverity.LOW

    def test_suggest_recovery_strategy(self):
        """Test recovery strategy suggestions."""
        assert suggest_recovery_strategy(ConnectionError()) == RecoveryStrategy.RETRY
        assert suggest_recovery_strategy(TimeoutError()) == RecoveryStrategy.RETRY
        assert suggest_recovery_strategy(PermissionError()) == RecoveryStrategy.FAIL_FAST
        assert suggest_recovery_strategy(MemoryError()) == RecoveryStrategy.CIRCUIT_BREAKER
        assert suggest_recovery_strategy(OSError()) == RecoveryStrategy.CIRCUIT_BREAKER
        assert suggest_recovery_strategy(ValueError()) == RecoveryStrategy.FALLBACK
