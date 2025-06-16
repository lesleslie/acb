"""Tests for the Memory Cache adapter."""

from unittest.mock import MagicMock, patch

import pytest
from aiocache.backends.memory import SimpleMemoryCache
from aiocache.serializers import PickleSerializer
from pytest_benchmark.fixture import BenchmarkFixture
from acb.adapters.cache._base import CacheBaseSettings
from acb.adapters.cache.memory import Cache, CacheSettings


@pytest.fixture
def mock_config() -> MagicMock:
    mock = MagicMock()
    mock.app.name = "test_app"
    mock.deployed = False
    return mock


@pytest.fixture
def mock_logger() -> MagicMock:
    return MagicMock()


class TestCacheSettings:
    def test_default_values(self) -> None:
        settings = CacheSettings()
        assert settings.default_ttl == 86400
        assert settings.query_ttl == 600
        assert settings.template_ttl == 86400

    def test_custom_values(self) -> None:
        settings = CacheSettings(default_ttl=3600, query_ttl=300, template_ttl=7200)
        assert settings.default_ttl == 3600
        assert settings.query_ttl == 300
        assert settings.template_ttl == 7200

    def test_response_ttl_with_config(self, mock_config: MagicMock) -> None:
        mock_config.deployed = False
        settings = CacheBaseSettings()
        settings.__init__(config=mock_config)
        assert settings.response_ttl == 1

        mock_config.deployed = True
        settings = CacheBaseSettings()
        settings.__init__(config=mock_config)
        assert settings.response_ttl == settings.default_ttl


class TestMemoryCache:
    @pytest.mark.asyncio
    async def test_init_basic(
        self, mock_config: MagicMock, mock_logger: MagicMock
    ) -> None:
        with patch("acb.adapters.cache.memory.SimpleMemoryCache") as mock_smc:
            mock_instance = MagicMock()
            mock_smc.return_value = mock_instance

            adapter = Cache()
            adapter.config = mock_config
            adapter.logger = mock_logger

            # Initialize adapter - should not create cache yet (lazy loading)
            await adapter.init()
            mock_smc.assert_not_called()

            # Access _cache property to trigger lazy creation
            cache = adapter._cache
            mock_smc.assert_called_once()
            call_kwargs = mock_smc.call_args[1]
            assert "namespace" in call_kwargs
            assert call_kwargs["namespace"] == "test_app:"
            assert "serializer" in call_kwargs
            assert isinstance(call_kwargs["serializer"], PickleSerializer)

            assert mock_instance.timeout == 0.0
            assert cache is mock_instance

    @pytest.mark.asyncio
    async def test_init_with_custom_kwargs(
        self, mock_config: MagicMock, mock_logger: MagicMock
    ) -> None:
        with patch("acb.adapters.cache.memory.SimpleMemoryCache") as mock_smc:
            mock_instance = MagicMock()
            mock_smc.return_value = mock_instance

            adapter = Cache()
            adapter.config = mock_config
            adapter.logger = mock_logger

            # Pass kwargs to init - they should be stored for lazy creation
            await adapter.init(timeout=5.0)
            mock_smc.assert_not_called()

            # Access _cache property to trigger lazy creation with stored kwargs
            cache = adapter._cache
            mock_smc.assert_called_once()
            call_kwargs = mock_smc.call_args[1]
            assert "namespace" in call_kwargs
            assert call_kwargs["namespace"] == "test_app:"
            assert "serializer" in call_kwargs
            assert isinstance(call_kwargs["serializer"], PickleSerializer)
            assert "timeout" in call_kwargs
            assert call_kwargs["timeout"] == 5.0

            assert mock_instance.timeout == 0.0
            assert cache is mock_instance

    @pytest.mark.asyncio
    async def test_integration_init(self) -> None:
        mock_config = MagicMock()
        mock_config.app.name = "test_app"
        mock_logger = MagicMock()

        adapter = Cache()
        adapter.config = mock_config
        adapter.logger = mock_logger

        result = await adapter.init()

        assert result is None
        assert hasattr(adapter, "_cache")
        assert isinstance(adapter._cache, SimpleMemoryCache)
        assert adapter._cache.namespace == "test_app:"
        assert adapter._cache.timeout == 0.0
        assert isinstance(adapter._cache.serializer, PickleSerializer)


@pytest.mark.skip(reason="Cache benchmark tests need adapter method implementation")
class TestMemoryCacheBenchmarks:
    @pytest.fixture
    def benchmark_adapter(
        self, mock_config: MagicMock, mock_logger: MagicMock
    ) -> Cache:
        adapter = Cache()
        adapter.config = mock_config
        adapter.logger = mock_logger
        return adapter

    @pytest.fixture
    def small_data(self) -> str:
        return "small_test_data"

    @pytest.fixture
    def medium_data(self) -> str:
        return "medium_test_data" * 100

    @pytest.fixture
    def large_data(self) -> str:
        return "large_test_data" * 10000

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_cache_set_small_data_performance(
        self, benchmark: BenchmarkFixture, benchmark_adapter: Cache, small_data: str
    ) -> None:
        await benchmark_adapter.init()

        async def cache_set_operation() -> bool:
            await benchmark_adapter._cache.set("test_key", small_data)
            return True

        result = await benchmark(cache_set_operation)
        assert result is True

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_cache_set_medium_data_performance(
        self, benchmark: BenchmarkFixture, benchmark_adapter: Cache, medium_data: str
    ) -> None:
        await benchmark_adapter.init()

        result = await benchmark(benchmark_adapter.set, "test_key", medium_data)
        assert result is True

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_cache_set_large_data_performance(
        self, benchmark: BenchmarkFixture, benchmark_adapter: Cache, large_data: str
    ) -> None:
        await benchmark_adapter.init()

        result = await benchmark(benchmark_adapter.set, "test_key", large_data)
        assert result is True

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_cache_get_small_data_performance(
        self, benchmark: BenchmarkFixture, benchmark_adapter: Cache, small_data: str
    ) -> None:
        await benchmark_adapter.init()
        await benchmark_adapter.set("test_key", small_data)

        result = await benchmark(benchmark_adapter.get, "test_key")
        assert result == small_data

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_cache_get_medium_data_performance(
        self, benchmark: BenchmarkFixture, benchmark_adapter: Cache, medium_data: str
    ) -> None:
        await benchmark_adapter.init()
        await benchmark_adapter.set("test_key", medium_data)

        result = await benchmark(benchmark_adapter.get, "test_key")
        assert result == medium_data

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_cache_get_large_data_performance(
        self, benchmark: BenchmarkFixture, benchmark_adapter: Cache, large_data: str
    ) -> None:
        await benchmark_adapter.init()
        await benchmark_adapter.set("test_key", large_data)

        result = await benchmark(benchmark_adapter.get, "test_key")
        assert result == large_data

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_cache_exists_performance(
        self, benchmark: BenchmarkFixture, benchmark_adapter: Cache, medium_data: str
    ) -> None:
        await benchmark_adapter.init()
        await benchmark_adapter.set("test_key", medium_data)

        result = await benchmark(benchmark_adapter.exists, "test_key")
        assert result is True

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_cache_bulk_operations_performance(
        self, benchmark: BenchmarkFixture, benchmark_adapter: Cache, small_data: str
    ) -> None:
        await benchmark_adapter.init()

        async def bulk_set_get() -> list[str]:
            for i in range(100):
                await benchmark_adapter.set(f"bulk_key_{i}", f"{small_data}_{i}")
            results: list[str] = []
            for i in range(100):
                result = await benchmark_adapter.get(f"bulk_key_{i}")
                if result is not None:
                    results.append(result)
            return results

        results = await benchmark(bulk_set_get)
        assert len(results) == 100
        assert all(result is not None for result in results)
