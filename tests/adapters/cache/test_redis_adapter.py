"""Tests for the Redis Cache adapter."""

from collections.abc import AsyncGenerator
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from acb.adapters.cache.redis import Cache, CacheSettings
from acb.config import SecretStr


class MockRedisClient:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self._keys = AsyncMock()
        self._get = AsyncMock()
        self._set = AsyncMock()
        self._delete = AsyncMock()
        self._exists = AsyncMock()
        self._unlink = AsyncMock()
        self._close = AsyncMock()

    async def keys(self, pattern: str) -> list[str]:
        return await self._keys(pattern)

    async def get(self, key: str) -> bytes | None:
        return await self._get(key)

    async def set(
        self, key: str, value: bytes, ex: int | None = None, nx: bool = False
    ) -> bool:
        return await self._set(key, value, ex=ex, nx=nx)

    async def delete(self, *keys: str) -> int:
        return await self._delete(*keys)

    async def exists(self, *keys: str) -> int:
        return await self._exists(*keys)

    async def unlink(self, *keys: str) -> int:
        return await self._unlink(*keys)

    async def close(self) -> None:
        await self._close()


class TestCacheSettings:
    def test_default_values(self) -> None:
        with patch("acb.adapters.cache.redis.depends") as mock_depends:
            mock_config = MagicMock()
            mock_config.deployed = False
            mock_depends.return_value = mock_config

            settings = CacheSettings()

            assert settings.host.get_secret_value() == "127.0.0.1"
            assert settings.local_host == "127.0.0.1"
            assert settings.port == 6379
            assert settings.cluster is False
            assert settings.connect_timeout == 3
            assert settings.max_connections is None
            assert settings.health_check_interval == 0

    @pytest.mark.skip(
        reason="Host setting behavior in deployed mode needs further investigation"
    )
    def test_deployed_mode(self) -> None:
        mock_config = MagicMock()
        mock_config.deployed = True

        with patch("acb.adapters.cache.redis.depends") as mock_depends:
            mock_depends.return_value = mock_config

            test_host = "redis.example.com"
            settings = CacheSettings(host=SecretStr(test_host))

            assert settings.host.get_secret_value() == test_host


@pytest.fixture
async def redis_cache() -> AsyncGenerator[Cache]:
    with (
        patch("acb.adapters.cache.redis.Redis") as mock_redis_cls,
        patch("acb.adapters.cache.redis.PickleSerializer") as mock_serializer_cls,
    ):
        mock_client = MockRedisClient()
        mock_redis_cls.return_value = mock_client

        mock_serializer = MagicMock()
        mock_serializer.dumps.return_value = "serialized_data"
        mock_serializer.loads.return_value = {"key": "value"}
        mock_serializer_cls.return_value = mock_serializer

        mock_config = MagicMock()
        mock_config.app.name = "test_app"
        mock_config.cache.host.get_secret_value.return_value = "localhost"
        mock_config.cache.port = 6379
        mock_config.cache.db = 0
        mock_config.cache.username = None
        mock_config.cache.password = None
        mock_config.cache.ssl = False
        mock_config.cache.cluster = False
        mock_config.cache.connection_timeout = 2.0
        mock_config.cache.health_check_interval = 0

        cache = Cache()
        cache.config = mock_config
        cache.logger = MagicMock()

        await cache.init()

        setattr(cache, "client", mock_client)

        cache._namespace = f"{mock_config.app.name}:"
        cache._serializer = mock_serializer

        mock_client._exists.return_value = 1
        mock_client._keys.return_value = ["test_app:key1", "test_app:key2"]
        mock_client._get.return_value = b"test_value"
        mock_client._set.return_value = True
        mock_client._delete.return_value = 1
        mock_client._unlink.return_value = 2

        yield cache


@pytest.fixture
async def redis_cluster_cache() -> AsyncGenerator[Cache]:
    with (
        patch("acb.adapters.cache.redis.RedisCluster") as mock_redis_cls,
        patch("acb.adapters.cache.redis.PickleSerializer") as mock_serializer_cls,
    ):
        mock_client = MockRedisClient()
        mock_redis_cls.return_value = mock_client

        mock_serializer = MagicMock()
        mock_serializer.dumps.return_value = "serialized_data"
        mock_serializer.loads.return_value = {"key": "value"}
        mock_serializer_cls.return_value = mock_serializer

        mock_config = MagicMock()
        mock_config.app.name = "test_app"
        mock_config.cache.host.get_secret_value.return_value = "localhost"
        mock_config.cache.port = 6379
        mock_config.cache.db = 0
        mock_config.cache.username = None
        mock_config.cache.password = None
        mock_config.cache.ssl = False
        mock_config.cache.cluster = True
        mock_config.cache.connection_timeout = 2.0
        mock_config.cache.health_check_interval = 0

        cache = Cache()
        cache.config = mock_config
        cache.logger = MagicMock()

        await cache.init()

        setattr(cache, "client", mock_client)

        cache._namespace = f"{mock_config.app.name}:"
        cache._serializer = mock_serializer

        yield cache


@pytest.mark.asyncio
async def test_init_standard_mode(redis_cache: Cache) -> None:
    assert redis_cache._namespace == "test_app:"
    assert isinstance(redis_cache._serializer, MagicMock)
    assert redis_cache.client is not None

    logger_mock = cast(MagicMock, redis_cache.logger)
    logger_mock.info.assert_not_called()


@pytest.mark.asyncio
async def test_init_cluster_mode(redis_cluster_cache: Cache) -> None:
    assert redis_cluster_cache._namespace == "test_app:"
    assert isinstance(redis_cluster_cache._serializer, MagicMock)
    assert redis_cluster_cache.client is not None

    logger_mock = cast(MagicMock, redis_cluster_cache.logger)
    logger_mock.info.assert_called_once_with("RedisCluster mode enabled")


@pytest.mark.asyncio
async def test_exists_method(redis_cache: Cache) -> None:
    client = cast(MockRedisClient, redis_cache.client)
    client._exists.return_value = 1
    result = await redis_cache._exists("test_key")
    assert result
    client._exists.return_value = 0
    result = await redis_cache._exists("test_key")
    assert not result


@pytest.mark.asyncio
async def test_clear_method_without_namespace(redis_cache: Cache) -> None:
    client = cast(MockRedisClient, redis_cache.client)
    keys = ["test_app:key1", "test_app:key2"]
    client._keys.return_value = keys

    result = await redis_cache._clear()
    assert result is True
    client._keys.assert_called_with(f"{redis_cache._namespace}*")
    assert client._unlink.call_count == len(keys)


@pytest.mark.asyncio
async def test_clear_method_with_namespace(redis_cache: Cache) -> None:
    client = cast(MockRedisClient, redis_cache.client)
    keys = ["test_app:user:key1", "test_app:user:key2"]
    client._keys.return_value = keys

    result = await redis_cache._clear("user")
    assert result is True
    client._keys.assert_called_with(f"{redis_cache._namespace}user:*")
    assert client._unlink.call_count == len(keys)


@pytest.mark.asyncio
async def test_clear_method_with_no_keys(redis_cache: Cache) -> None:
    client = cast(MockRedisClient, redis_cache.client)
    client._keys.return_value = []

    result = await redis_cache._clear()
    assert result is True
    client._keys.assert_called_with(f"{redis_cache._namespace}*")
    assert client._unlink.call_count == 0


@pytest.mark.asyncio
async def test_close_method(redis_cache: Cache) -> None:
    await redis_cache._close()
