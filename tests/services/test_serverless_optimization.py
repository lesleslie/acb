"""Tests for serverless optimization services."""

from unittest.mock import AsyncMock, MagicMock, patch

import asyncio
import pytest

from acb.depends import depends
from acb.services.performance.serverless import (
    AdapterPreInitializer,
    ColdStartMetrics,
    FastDependencies,
    LazyInitializer,
    ServerlessOptimizer,
    ServerlessOptimizerSettings,
    ServerlessResourceCleanup,
    lazy_resource,
    optimize_cold_start,
)


class TestLazyInitializer:
    """Test LazyInitializer functionality."""

    @pytest.mark.asyncio
    async def test_lazy_initialization(self):
        """Test basic lazy initialization."""
        call_count = 0

        async def factory():
            nonlocal call_count
            call_count += 1
            return "initialized_resource"

        initializer = LazyInitializer(factory)

        # Resource should not be initialized yet
        assert not initializer.is_initialized

        # First call should initialize
        result1 = await initializer.get()
        assert result1 == "initialized_resource"
        assert initializer.is_initialized
        assert call_count == 1

        # Second call should return cached result
        result2 = await initializer.get()
        assert result2 == "initialized_resource"
        assert call_count == 1  # Factory not called again

        await initializer.cleanup()

    @pytest.mark.asyncio
    async def test_lazy_initialization_timeout(self):
        """Test lazy initialization with timeout."""

        async def slow_factory():
            await asyncio.sleep(1.0)
            return "resource"

        initializer = LazyInitializer(slow_factory, timeout=0.1)

        with pytest.raises(RuntimeError, match="timed out"):
            await initializer.get()

    @pytest.mark.asyncio
    async def test_lazy_initialization_reset(self):
        """Test resetting lazy initializer."""
        call_count = 0

        async def factory():
            nonlocal call_count
            call_count += 1
            return f"resource_{call_count}"

        initializer = LazyInitializer(factory)

        # First initialization
        result1 = await initializer.get()
        assert result1 == "resource_1"
        assert call_count == 1

        # Reset and initialize again
        await initializer.reset()
        assert not initializer.is_initialized

        result2 = await initializer.get()
        assert result2 == "resource_2"
        assert call_count == 2

        await initializer.cleanup()


class TestAdapterPreInitializer:
    """Test AdapterPreInitializer functionality."""

    def setup_method(self):
        """Setup test fixtures."""
        self.preinitializer = AdapterPreInitializer()

    @pytest.mark.asyncio
    async def test_eager_preinitialize_adapter(self):
        """Test eager adapter pre-initialization."""
        mock_adapter = AsyncMock()
        mock_adapter.initialize = AsyncMock()

        with (
            patch("acb.adapters.import_adapter") as mock_import,
            patch("acb.services.performance.serverless.depends.get") as mock_get,
        ):
            mock_import.return_value = "MockAdapterClass"
            mock_get.return_value = mock_adapter

            await self.preinitializer.preinitialize_adapter("test_adapter", eager=True)

            assert self.preinitializer.is_preinitialized("test_adapter")
            adapter = await self.preinitializer.get_adapter("test_adapter")
            assert adapter is mock_adapter
            mock_adapter.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_lazy_preinitialize_adapter(self):
        """Test lazy adapter pre-initialization."""
        mock_adapter = AsyncMock()
        mock_adapter.initialize = AsyncMock()

        with (
            patch("acb.adapters.import_adapter") as mock_import,
            patch("acb.services.performance.serverless.depends.get") as mock_get,
        ):
            mock_import.return_value = "MockAdapterClass"
            mock_get.return_value = mock_adapter

            await self.preinitializer.preinitialize_adapter("test_adapter", eager=False)

            assert self.preinitializer.is_preinitialized("test_adapter")

            # Adapter should only initialize when accessed
            mock_adapter.initialize.assert_not_called()

            adapter = await self.preinitializer.get_adapter("test_adapter")
            assert adapter is mock_adapter
            mock_adapter.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_non_preinitialized_adapter(self):
        """Test getting a non-preinitialized adapter."""
        with pytest.raises(ValueError, match="not pre-initialized"):
            await self.preinitializer.get_adapter("non_existent_adapter")


class TestFastDependencies:
    """Test FastDependencies functionality."""

    def setup_method(self):
        """Setup test fixtures."""
        self.fast_deps = FastDependencies()

    def test_cached_resolve(self):
        """Test cached dependency resolution."""
        mock_instance = MagicMock()
        mock_get_sync = MagicMock(return_value=mock_instance)

        with patch.object(depends, "get_sync", new=mock_get_sync):
            # First resolution
            result1 = self.fast_deps.cached_resolve(str, "test_key")
            assert result1 is mock_instance
            mock_get_sync.assert_called_once_with(str)

            # Second resolution should use cache
            mock_get_sync.reset_mock()
            result2 = self.fast_deps.cached_resolve(str, "test_key")
            assert result2 is mock_instance
            mock_get_sync.assert_not_called()

    def test_clear_cache(self):
        """Test cache clearing."""
        mock_instance = MagicMock()
        mock_get_sync = MagicMock(return_value=mock_instance)

        with patch.object(depends, "get_sync", new=mock_get_sync):
            # Cache a resolution
            self.fast_deps.cached_resolve(str, "test_key")

            # Clear cache
            self.fast_deps.clear_cache()

            # Next resolution should call depends.get_sync again
            result = self.fast_deps.cached_resolve(str, "test_key")
            assert result is mock_instance
            assert mock_get_sync.call_count == 2

    def test_resolution_stats(self):
        """Test resolution statistics tracking."""
        mock_instance = MagicMock()
        mock_get_sync = MagicMock(return_value=mock_instance)

        with patch.object(depends, "get_sync", new=mock_get_sync):
            self.fast_deps.cached_resolve(str, "test_key")
            stats = self.fast_deps.get_resolution_stats()

            assert "test_key" in stats
            assert isinstance(stats["test_key"], float)
            assert stats["test_key"] >= 0


class TestServerlessResourceCleanup:
    """Test ServerlessResourceCleanup functionality."""

    def setup_method(self):
        """Setup test fixtures."""
        self.cleanup_manager = ServerlessResourceCleanup(cleanup_interval=0.1)

    @pytest.mark.asyncio
    async def test_track_resource(self):
        """Test resource tracking."""
        mock_resource = MagicMock()
        mock_resource.cleanup = AsyncMock()

        self.cleanup_manager.track_resource(mock_resource)

        # Manually trigger cleanup to test tracking
        await self.cleanup_manager._perform_cleanup()
        mock_resource.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_loop_lifecycle(self):
        """Test cleanup loop start and stop."""
        await self.cleanup_manager.start_cleanup_loop()
        assert self.cleanup_manager._cleanup_task is not None
        assert not self.cleanup_manager._cleanup_task.done()

        await self.cleanup_manager.stop_cleanup_loop()
        assert self.cleanup_manager._cleanup_task.done()

        await self.cleanup_manager.cleanup()


class TestServerlessOptimizer:
    """Test ServerlessOptimizer functionality."""

    def setup_method(self):
        """Setup test fixtures."""
        self.settings = ServerlessOptimizerSettings()
        self.optimizer = ServerlessOptimizer(settings=self.settings)

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test optimizer initialization."""
        with patch.object(
            self.optimizer, "_perform_cold_start_optimizations"
        ) as mock_optimize:
            await self.optimizer.initialize()

            mock_optimize.assert_called_once()
            assert self.optimizer.status.value == "active"

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check functionality."""
        await self.optimizer.initialize()

        health = await self.optimizer.health_check()

        assert "service_specific" in health
        service_health = health["service_specific"]
        assert "cold_starts" in service_health
        assert "warm_starts" in service_health
        assert "preloaded_adapters" in service_health
        assert "average_cold_start_ms" in service_health
        assert "memory_usage_mb" in service_health

        await self.optimizer.shutdown()

    @pytest.mark.asyncio
    async def test_cold_start_metrics_update(self):
        """Test cold start metrics tracking."""
        # Initialize the metrics properly
        self.optimizer._cold_start_metrics.cold_starts_count = 1
        duration = 150.0
        self.optimizer._update_cold_start_average(duration)

        metrics = self.optimizer.get_metrics()
        assert metrics.cold_starts_count == 1
        assert metrics.average_cold_start_time_ms == duration

        # Test averaging - increment count first
        self.optimizer._cold_start_metrics.cold_starts_count = 2
        self.optimizer._update_cold_start_average(50.0)
        assert metrics.cold_starts_count == 2
        assert metrics.average_cold_start_time_ms == 100.0  # (150 + 50) / 2

    @pytest.mark.asyncio
    async def test_adapter_preloading(self):
        """Test adapter preloading functionality."""
        mock_adapter = AsyncMock()
        mock_adapter.initialize = AsyncMock()

        with (
            patch("acb.adapters.import_adapter") as mock_import,
            patch("acb.services.performance.serverless.depends.get") as mock_get,
        ):
            mock_import.return_value = "MockAdapterClass"
            mock_get.return_value = mock_adapter

            self.optimizer._settings.critical_adapters = ["test_adapter"]
            await self.optimizer._preload_adapters()

            assert "test_adapter" in self.optimizer._preloaded_adapters
            mock_adapter.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown(self):
        """Test optimizer shutdown."""
        await self.optimizer.initialize()
        await self.optimizer.shutdown()

        assert self.optimizer.status.value == "stopped"


class TestOptimizationDecorators:
    """Test optimization decorator functions."""

    @pytest.mark.asyncio
    async def test_optimize_cold_start_decorator(self):
        """Test cold start optimization decorator."""
        call_count = 0

        @optimize_cold_start()
        async def test_function(value: int) -> int:
            nonlocal call_count
            call_count += 1
            return value * 2

        result = await test_function(5)
        assert result == 10
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_lazy_resource_context_manager(self):
        """Test lazy resource context manager."""
        call_count = 0

        async def factory():
            nonlocal call_count
            call_count += 1
            resource = MagicMock()
            resource.cleanup = AsyncMock()
            # CleanupMixin looks for 'close' method first
            resource.close = resource.cleanup
            return resource

        async with lazy_resource(factory) as resource:
            assert call_count == 1
            assert resource is not None

        # Cleanup should have been called via close()
        resource.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_lazy_resource_timeout(self):
        """Test lazy resource with timeout."""

        async def slow_factory():
            await asyncio.sleep(1.0)
            return MagicMock()

        with pytest.raises(RuntimeError, match="timed out"):
            async with lazy_resource(slow_factory, timeout=0.1):
                pass


class TestColdStartMetrics:
    """Test ColdStartMetrics dataclass."""

    def test_metrics_initialization(self):
        """Test metrics initialization with defaults."""
        metrics = ColdStartMetrics()

        assert metrics.cold_starts_count == 0
        assert metrics.warm_starts_count == 0
        assert metrics.average_cold_start_time_ms == 0.0
        assert metrics.average_warm_start_time_ms == 0.0
        assert metrics.resources_preloaded == 0
        assert metrics.memory_usage_mb == 0.0
        assert isinstance(metrics.optimizations_applied, dict)

    def test_metrics_custom_values(self):
        """Test metrics with custom values."""
        optimizations = {"cache": 5, "query": 3}
        metrics = ColdStartMetrics(
            cold_starts_count=10,
            warm_starts_count=50,
            average_cold_start_time_ms=125.5,
            optimizations_applied=optimizations,
        )

        assert metrics.cold_starts_count == 10
        assert metrics.warm_starts_count == 50
        assert metrics.average_cold_start_time_ms == 125.5
        assert metrics.optimizations_applied == optimizations
