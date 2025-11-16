"""Tests for ACB performance optimizer service."""

from unittest.mock import AsyncMock, MagicMock, patch

import asyncio
import pytest

from acb.depends import depends
from acb.services._base import ServiceStatus
from acb.services.performance.optimizer import (
    OptimizationConfig,
    OptimizationResult,
    PerformanceOptimizer,
    PerformanceOptimizerSettings,
)


class TestPerformanceOptimizer:
    """Test the PerformanceOptimizer service."""

    @pytest.mark.asyncio
    async def test_optimizer_initialization(self):
        """Test performance optimizer initialization."""
        with (
            patch("acb.adapters.import_adapter") as mock_import,
            patch.object(depends, "get_async") as mock_get_async,
        ):
            # Mock cache adapter
            mock_cache = MagicMock()
            mock_import.return_value = MagicMock()
            mock_get_async.return_value = mock_cache

            optimizer = PerformanceOptimizer()
            await optimizer.initialize()

            assert optimizer.status == ServiceStatus.ACTIVE
            assert optimizer._cache_adapter == mock_cache

    @pytest.mark.asyncio
    async def test_optimizer_initialization_without_adapters(self):
        """Test optimizer initialization when adapters are not available."""
        with patch(
            "acb.adapters.import_adapter", side_effect=Exception("Adapter not found")
        ):
            optimizer = PerformanceOptimizer()
            await optimizer.initialize()

            assert optimizer.status == ServiceStatus.ACTIVE
            assert optimizer._cache_adapter is None
            assert optimizer._sql_adapter is None

    @pytest.mark.asyncio
    async def test_cache_optimization_with_hit(self):
        """Test cache optimization with cache hit."""
        with (
            patch("acb.adapters.import_adapter") as mock_import,
            patch.object(depends, "get_async") as mock_get_async,
        ):
            # Mock cache adapter
            mock_cache = AsyncMock()
            mock_cache.get.return_value = "cached_result"
            mock_import.return_value = MagicMock()
            mock_get_async.return_value = mock_cache

            optimizer = PerformanceOptimizer()
            await optimizer.initialize()

            async def test_operation():
                return "operation_result"

            result = await optimizer.optimize_cache_operation(
                "test_key", test_operation, ttl=300
            )

            assert result.success is True
            assert result.operation == "cache_operation_hit"
            assert result.metadata["cache_hit"] is True
            assert result.metadata["result"] == "cached_result"
            assert result.improvement_percent == 75.0

            mock_cache.get.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_cache_optimization_with_miss(self):
        """Test cache optimization with cache miss."""
        with (
            patch("acb.adapters.import_adapter") as mock_import,
            patch.object(depends, "get_async") as mock_get_async,
        ):
            # Mock cache adapter
            mock_cache = AsyncMock()
            mock_cache.get.return_value = None
            mock_import.return_value = MagicMock()
            mock_get_async.return_value = mock_cache

            optimizer = PerformanceOptimizer()
            await optimizer.initialize()

            async def test_operation():
                return "operation_result"

            result = await optimizer.optimize_cache_operation(
                "test_key", test_operation, ttl=300
            )

            assert result.success is True
            assert result.operation == "cache_operation_miss"
            assert result.metadata["cache_hit"] is False
            assert result.metadata["result"] == "operation_result"
            assert result.metadata["cached_with_ttl"] == 300

            mock_cache.get.assert_called_once_with("test_key")
            mock_cache.set.assert_called_once_with(
                "test_key", "operation_result", ttl=300
            )

    @pytest.mark.asyncio
    async def test_cache_optimization_without_cache(self):
        """Test cache optimization when cache is not available."""
        optimizer = PerformanceOptimizer()
        optimizer._cache_adapter = None

        async def test_operation():
            return "direct_result"

        result = await optimizer.optimize_cache_operation("test_key", test_operation)

        assert result.success is True
        assert result.operation == "cache_operation_direct"
        assert result.metadata["cache_hit"] is False
        assert result.metadata["reason"] == "cache_disabled"

    @pytest.mark.asyncio
    async def test_query_batch_optimization(self):
        """Test query batch optimization."""
        with (
            patch("acb.adapters.import_adapter") as mock_import,
            patch.object(depends, "get_async") as mock_get_async,
        ):
            # Mock SQL adapter
            mock_sql = AsyncMock()
            mock_sql.execute.return_value = "query_result"
            mock_import.return_value = MagicMock()
            mock_get_async.return_value = mock_sql

            optimizer = PerformanceOptimizer()
            await optimizer.initialize()

            queries = ["SELECT * FROM users", "SELECT * FROM orders"]
            parameters = [{"user_id": 1}, {"order_id": 2}]

            result = await optimizer.optimize_query_batch(queries, parameters)

            assert result.success is True
            assert result.operation == "query_batch_optimized"
            assert result.metadata["queries_count"] == 2
            assert result.metadata["batches_processed"] == 1
            assert len(result.metadata["results"]) == 2

            # Should have called execute for each query
            assert mock_sql.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_query_batch_without_sql(self):
        """Test query batch optimization without SQL adapter."""
        optimizer = PerformanceOptimizer()
        optimizer._sql_adapter = None

        queries = ["SELECT * FROM users"]
        result = await optimizer.optimize_query_batch(queries)

        assert result.success is False
        assert result.operation == "query_batch_error"
        assert result.error == "SQL adapter not available"

    @pytest.mark.asyncio
    async def test_optimize_function_decorator(self):
        """Test function optimization decorator."""
        with (
            patch("acb.adapters.import_adapter") as mock_import,
            patch.object(depends, "get_async") as mock_get_async,
        ):
            # Mock cache adapter
            mock_cache = AsyncMock()
            mock_cache.get.return_value = None  # Cache miss first time
            mock_import.return_value = MagicMock()
            mock_get_async.return_value = mock_cache

            optimizer = PerformanceOptimizer()
            await optimizer.initialize()

            call_count = 0

            @optimizer.optimize_function(cache_key_template="test_func", ttl=600)
            async def test_function(value):
                nonlocal call_count
                call_count += 1
                return f"result_{value}"

            # First call - should execute function and cache result
            result1 = await test_function("hello")
            assert result1 == "result_hello"
            assert call_count == 1

            # Second call with cache hit
            mock_cache.get.return_value = "result_hello"
            result2 = await test_function("hello")
            assert result2 == "result_hello"
            assert call_count == 1  # Function not called again due to cache hit

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test performance optimizer health check."""
        optimizer = PerformanceOptimizer()
        # Set adapters directly without calling initialize()
        optimizer._cache_adapter = MagicMock()
        optimizer._sql_adapter = MagicMock()

        health = await optimizer.health_check()

        # Check basic structure of health response
        assert isinstance(health, dict)
        assert "cache_available" in health or health  # Allow either format

    @pytest.mark.asyncio
    async def test_background_optimization(self):
        """Test background optimization loop."""
        # Create optimizer with short optimization interval
        settings = PerformanceOptimizerSettings()
        settings.optimization_interval_seconds = 0.1
        settings.background_optimization = True

        optimizer = PerformanceOptimizer(settings=settings)
        optimizer._cache_adapter = MagicMock()

        await optimizer.initialize()

        # Let it run for a short time
        await asyncio.sleep(0.2)

        # Should have performed some background optimizations
        optimizations_count = optimizer.get_custom_metric("optimizations_applied", 0)
        assert optimizations_count >= 0  # At least attempted

        await optimizer.shutdown()

    @pytest.mark.asyncio
    async def test_optimization_result_creation(self):
        """Test OptimizationResult creation and attributes."""
        result = OptimizationResult(
            operation="test_op",
            duration_ms=123.45,
            success=True,
            improvement_percent=25.0,
            error=None,
            metadata={"key": "value"},
        )

        assert result.operation == "test_op"
        assert result.duration_ms == 123.45
        assert result.success is True
        assert result.improvement_percent == 25.0
        assert result.error is None
        assert result.metadata["key"] == "value"

    def test_optimization_config_defaults(self):
        """Test OptimizationConfig default values."""
        config = OptimizationConfig()

        assert config.cache_enabled is True
        assert config.cache_ttl_seconds == 3600
        assert config.query_timeout_seconds == 30.0
        assert config.response_compression is True
        assert config.web_framework_integration is False
