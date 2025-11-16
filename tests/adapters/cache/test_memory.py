"""Tests for the Memory Cache adapter."""

from unittest.mock import AsyncMock, MagicMock, patch

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
    @pytest.mark.unit
    def test_default_values(self) -> None:
        settings = CacheSettings()
        assert settings.default_ttl == 86400
        assert settings.query_ttl == 600
        assert settings.template_ttl == 86400

    @pytest.mark.unit
    def test_custom_values(self) -> None:
        settings = CacheSettings(default_ttl=3600, query_ttl=300, template_ttl=7200)
        assert settings.default_ttl == 3600
        assert settings.query_ttl == 300
        assert settings.template_ttl == 7200

    @pytest.mark.unit
    def test_response_ttl_deployed_false(self) -> None:
        from acb.config import Config
        from acb.depends import depends

        # Test with deployed=False
        mock_config = MagicMock()
        mock_config.deployed = False
        depends.set(Config, mock_config)
        try:
            settings = CacheBaseSettings()
            assert settings.response_ttl == 1
        finally:
            # Reset to avoid affecting other tests
            try:
                depends.set(Config, Config())
            except Exception:
                pass

    @pytest.mark.unit
    def test_response_ttl_deployed_true(self) -> None:
        from acb.config import Config
        from acb.depends import depends

        # Test with deployed=True
        mock_config = MagicMock()
        mock_config.deployed = True
        depends.set(Config, mock_config)
        try:
            settings = CacheBaseSettings()
            assert settings.response_ttl == settings.default_ttl
        finally:
            # Reset to avoid affecting other tests
            try:
                depends.set(Config, Config())
            except Exception:
                pass


class TestMemoryCache:
    @pytest.mark.asyncio
    async def test_init_basic(
        self,
        mock_config: MagicMock,
        mock_logger: MagicMock,
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
        self,
        mock_config: MagicMock,
        mock_logger: MagicMock,
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

    @pytest.mark.asyncio
    async def test_aiocache_interface_methods(
        self,
        mock_config: MagicMock,
        mock_logger: MagicMock,
    ) -> None:
        """Test the new aiocache interface methods implementation."""
        adapter = Cache()
        adapter.config = mock_config
        adapter.logger = mock_logger

        # Mock the underlying SimpleMemoryCache
        with patch("acb.adapters.cache.memory.SimpleMemoryCache") as mock_smc:
            mock_cache = MagicMock()
            mock_smc.return_value = mock_cache

            # Configure mock cache methods
            mock_cache.set = AsyncMock()
            mock_cache.get = AsyncMock(return_value="test_value")
            mock_cache.delete = AsyncMock(return_value=True)
            mock_cache.exists = AsyncMock(return_value=True)
            mock_cache.clear = AsyncMock(return_value=True)
            mock_cache.multi_set = AsyncMock()
            mock_cache.multi_get = AsyncMock(return_value=["value1", "value2"])
            mock_cache.add = AsyncMock(return_value=True)
            mock_cache.increment = AsyncMock(return_value=5)
            mock_cache.expire = AsyncMock(return_value=True)

            # Test _set method
            await adapter._set("test_key", "test_value", ttl=300)
            mock_cache.set.assert_awaited_once_with("test_key", "test_value", ttl=300)

            # Test _get method
            result = await adapter._get("test_key")
            assert result == "test_value"
            mock_cache.get.assert_awaited_once_with("test_key")

            # Test _delete method
            delete_result = await adapter._delete("test_key")
            assert delete_result
            mock_cache.delete.assert_awaited_once_with("test_key")

            # Test _exists method
            exists_result = await adapter._exists("test_key")
            assert exists_result
            mock_cache.exists.assert_awaited_once_with("test_key")

            # Test _clear method
            clear_result = await adapter._clear()
            assert clear_result
            mock_cache.clear.assert_awaited_once_with(namespace=None)

            # Test _multi_set method
            pairs = [("key1", "value1"), ("key2", "value2")]
            await adapter._multi_set(pairs, ttl=600)
            mock_cache.multi_set.assert_awaited_once_with(pairs, ttl=600)

            # Test _multi_get method
            keys = ["key1", "key2"]
            multi_result = await adapter._multi_get(keys)
            assert multi_result == ["value1", "value2"]
            mock_cache.multi_get.assert_awaited_once_with(keys)

            # Test _add method
            add_result = await adapter._add("new_key", "new_value", ttl=120)
            assert add_result
            mock_cache.add.assert_awaited_once_with("new_key", "new_value", ttl=120)

            # Test _increment method
            inc_result = await adapter._increment("counter_key", delta=3)
            assert inc_result == 5
            mock_cache.increment.assert_awaited_once_with("counter_key", delta=3)

            # Test _expire method
            expire_result = await adapter._expire("expire_key", ttl=60)
            assert expire_result
            mock_cache.expire.assert_awaited_once_with("expire_key", ttl=60)

    @pytest.mark.asyncio
    async def test_aiocache_interface_with_connection_params(
        self,
        mock_config: MagicMock,
        mock_logger: MagicMock,
    ) -> None:
        """Test aiocache interface methods handle connection parameters correctly."""
        adapter = Cache()
        adapter.config = mock_config
        adapter.logger = mock_logger

        with patch("acb.adapters.cache.memory.SimpleMemoryCache") as mock_smc:
            mock_cache = MagicMock()
            mock_smc.return_value = mock_cache
            mock_cache.set = AsyncMock()
            mock_cache.get = AsyncMock(return_value="test_value")

            # Test that connection parameters are ignored (passed but not used)
            await adapter._set(
                "test_key",
                "test_value",
                ttl=300,
                _cas_token="token",
                _conn="connection",
            )
            mock_cache.set.assert_awaited_once_with("test_key", "test_value", ttl=300)

            await adapter._get("test_key", _conn="connection")
            mock_cache.get.assert_awaited_once_with("test_key")

    @pytest.mark.asyncio
    async def test_get_client_method(
        self,
        mock_config: MagicMock,
        mock_logger: MagicMock,
    ) -> None:
        """Test the get_client method returns properly configured client."""
        adapter = Cache()
        adapter.config = mock_config
        adapter.logger = mock_logger

        with patch("acb.adapters.cache.memory.SimpleMemoryCache") as mock_smc:
            mock_cache = MagicMock()
            mock_smc.return_value = mock_cache

            client = await adapter.get_client()
            assert client is mock_cache

            # Verify the cache was properly configured
            mock_smc.assert_called_once()
            call_kwargs = mock_smc.call_args[1]
            assert "namespace" in call_kwargs
            assert call_kwargs["namespace"] == "test_app:"
            assert "serializer" in call_kwargs
            assert isinstance(call_kwargs["serializer"], PickleSerializer)

    @pytest.mark.asyncio
    async def test_aiocache_interface_error_handling(
        self,
        mock_config: MagicMock,
        mock_logger: MagicMock,
    ) -> None:
        """Test error handling in aiocache interface methods."""
        adapter = Cache()
        adapter.config = mock_config
        adapter.logger = mock_logger

        with patch("acb.adapters.cache.memory.SimpleMemoryCache") as mock_smc:
            mock_cache = MagicMock()
            mock_smc.return_value = mock_cache

            # Test exception handling
            mock_cache.set = AsyncMock(side_effect=Exception("Cache error"))

            with pytest.raises(Exception) as exc_info:
                await adapter._set("test_key", "test_value")
            assert "Cache error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_namespace_configuration(
        self,
        mock_config: MagicMock,
        mock_logger: MagicMock,
    ) -> None:
        """Test that cache namespace is properly configured."""
        # Test with different app names
        test_cases = ["my_app", "test-app", "complex_app_name"]

        for app_name in test_cases:
            mock_config.app.name = app_name
            adapter = Cache()
            adapter.config = mock_config
            adapter.logger = mock_logger

            with patch("acb.adapters.cache.memory.SimpleMemoryCache") as mock_smc:
                mock_cache = MagicMock()
                mock_smc.return_value = mock_cache

                # Access _cache to trigger creation
                _ = adapter._cache

                # Verify namespace matches app name
                call_kwargs = mock_smc.call_args[1]
                assert call_kwargs["namespace"] == f"{app_name}:"

    @pytest.mark.asyncio
    async def test_cleanup_resources_with_multi_tier_cache(
        self,
        mock_config: MagicMock,
        mock_logger: MagicMock,
    ) -> None:
        """Test _cleanup_resources with multi-tier cache."""
        adapter = Cache()
        adapter.config = mock_config
        adapter.logger = mock_logger

        # Create a mock multi-tier cache
        mock_multi_tier_cache = MagicMock()
        mock_multi_tier_cache.cleanup = AsyncMock()
        adapter._multi_tier_cache = mock_multi_tier_cache

        # Create a mock client
        mock_client = MagicMock()
        mock_client.clear = AsyncMock()
        mock_client.close = AsyncMock()
        adapter._client = mock_client

        # Test cleanup
        await adapter._cleanup_resources()

        # Verify multi-tier cache cleanup was called
        mock_multi_tier_cache.cleanup.assert_awaited_once()

        # Verify client cleanup was called
        mock_client.clear.assert_awaited_once()
        mock_client.close.assert_awaited_once()
        assert adapter._client is None

    @pytest.mark.asyncio
    async def test_cleanup_resources_multi_tier_cache_error(
        self,
        mock_config: MagicMock,
        mock_logger: MagicMock,
    ) -> None:
        """Test _cleanup_resources when multi-tier cache cleanup fails."""
        adapter = Cache()
        adapter.config = mock_config
        adapter.logger = mock_logger

        # Create a mock multi-tier cache that raises an exception
        mock_multi_tier_cache = MagicMock()
        mock_multi_tier_cache.cleanup = AsyncMock(
            side_effect=Exception("Multi-tier cleanup failed")
        )
        adapter._multi_tier_cache = mock_multi_tier_cache

        # Create a mock client
        mock_client = MagicMock()
        mock_client.clear = AsyncMock()
        mock_client.close = AsyncMock()
        adapter._client = mock_client

        # Test cleanup - should not raise exception
        await adapter._cleanup_resources()

        # Verify client cleanup was still called despite multi-tier error
        mock_client.clear.assert_awaited_once()
        mock_client.close.assert_awaited_once()
        assert adapter._client is None

    @pytest.mark.asyncio
    async def test_cleanup_resources_client_error(
        self,
        mock_config: MagicMock,
        mock_logger: MagicMock,
    ) -> None:
        """Test _cleanup_resources when client cleanup fails."""
        adapter = Cache()
        adapter.config = mock_config
        adapter.logger = mock_logger

        # Create a mock client that raises an exception
        mock_client = MagicMock()
        mock_client.clear = AsyncMock(side_effect=Exception("Client cleanup failed"))
        mock_client.close = AsyncMock()
        adapter._client = mock_client

        # Test cleanup - should not raise exception
        await adapter._cleanup_resources()

        # Verify client was set to None despite error
        assert adapter._client is None

    @pytest.mark.asyncio
    async def test_cleanup_resources_client_close_method_missing(
        self,
        mock_config: MagicMock,
        mock_logger: MagicMock,
    ) -> None:
        """Test _cleanup_resources when client doesn't have close method."""
        adapter = Cache()
        adapter.config = mock_config
        adapter.logger = mock_logger

        # Create a mock client without close method
        mock_client = MagicMock()
        del mock_client.close  # Remove the close method
        mock_client.clear = AsyncMock()
        adapter._client = mock_client

        # Test cleanup
        await adapter._cleanup_resources()

        # Verify client was cleaned up (clear called, but not close)
        mock_client.clear.assert_awaited_once()
        assert adapter._client is None


@pytest.mark.skip(reason="Cache benchmark tests need adapter method implementation")
class TestMemoryCacheBenchmarks:
    @pytest.fixture
    def benchmark_adapter(
        self,
        mock_config: MagicMock,
        mock_logger: MagicMock,
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
        self,
        benchmark: BenchmarkFixture,
        benchmark_adapter: Cache,
        small_data: str,
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
        self,
        benchmark: BenchmarkFixture,
        benchmark_adapter: Cache,
        medium_data: str,
    ) -> None:
        await benchmark_adapter.init()

        result = await benchmark(benchmark_adapter.set, "test_key", medium_data)
        assert result is True

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_cache_set_large_data_performance(
        self,
        benchmark: BenchmarkFixture,
        benchmark_adapter: Cache,
        large_data: str,
    ) -> None:
        await benchmark_adapter.init()

        result = await benchmark(benchmark_adapter.set, "test_key", large_data)
        assert result is True

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_cache_get_small_data_performance(
        self,
        benchmark: BenchmarkFixture,
        benchmark_adapter: Cache,
        small_data: str,
    ) -> None:
        await benchmark_adapter.init()
        await benchmark_adapter.set("test_key", small_data)

        result = await benchmark(benchmark_adapter.get, "test_key")
        assert result == small_data

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_cache_get_medium_data_performance(
        self,
        benchmark: BenchmarkFixture,
        benchmark_adapter: Cache,
        medium_data: str,
    ) -> None:
        await benchmark_adapter.init()
        await benchmark_adapter.set("test_key", medium_data)

        result = await benchmark(benchmark_adapter.get, "test_key")
        assert result == medium_data

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_cache_get_large_data_performance(
        self,
        benchmark: BenchmarkFixture,
        benchmark_adapter: Cache,
        large_data: str,
    ) -> None:
        await benchmark_adapter.init()
        await benchmark_adapter.set("test_key", large_data)

        result = await benchmark(benchmark_adapter.get, "test_key")
        assert result == large_data

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_cache_exists_performance(
        self,
        benchmark: BenchmarkFixture,
        benchmark_adapter: Cache,
        medium_data: str,
    ) -> None:
        await benchmark_adapter.init()
        await benchmark_adapter.set("test_key", medium_data)

        result = await benchmark(benchmark_adapter.exists, "test_key")
        assert result is True

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_cache_bulk_operations_performance(
        self,
        benchmark: BenchmarkFixture,
        benchmark_adapter: Cache,
        small_data: str,
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
