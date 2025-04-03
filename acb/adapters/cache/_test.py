from unittest.mock import AsyncMock, patch

import pytest
from aiocache.serializers import PickleSerializer
from coredis.cache import TrackingCache
from coredis.client import Redis, RedisCluster
from pydantic import SecretStr
from acb.adapters.cache import _base, memory, redis
from acb.config import Config


class TestCacheBaseSettings:
    def test_default_values(self) -> None:
        settings = _base.CacheBaseSettings()
        assert settings.default_ttl == 86400
        assert settings.query_ttl == 600
        assert settings.response_ttl == 86400
        assert settings.template_ttl == 86400

    def test_custom_values(self) -> None:
        settings = _base.CacheBaseSettings(
            default_ttl=100, query_ttl=200, response_ttl=300, template_ttl=400
        )
        assert settings.default_ttl == 100
        assert settings.query_ttl == 200
        assert settings.response_ttl == 300
        assert settings.template_ttl == 400

    def test_response_ttl_deployed(self, config: Config) -> None:
        config.deployed = True
        settings = _base.CacheBaseSettings(config=config)
        assert settings.response_ttl == settings.default_ttl

    def test_response_ttl_not_deployed(self, config: Config) -> None:
        config.deployed = False
        settings = _base.CacheBaseSettings(config=config)
        assert settings.response_ttl == 1


@pytest.fixture
def config() -> Config:
    return Config()


class TestMemoryCache:
    @pytest.mark.anyio
    async def test_init(self, config: Config) -> None:
        config.app.name = "test_app"
        cache = memory.Cache(config=config)
        await cache.init()
        assert cache.serializer == PickleSerializer()
        assert cache.namespace == "test_app:"

    @pytest.mark.anyio
    async def test_set_get(self, config: Config) -> None:
        cache = memory.Cache(config=config)
        await cache.init()
        await cache.set("key", "value")
        value = await cache.get("key")
        assert value == "value"

    @pytest.mark.anyio
    async def test_set_get_none(self, config: Config) -> None:
        cache = memory.Cache(config=config)
        await cache.init()
        await cache.set("key", None)
        value = await cache.get("key")
        assert value is None

    @pytest.mark.anyio
    async def test_set_get_bytes(self, config: Config) -> None:
        cache = memory.Cache(config=config)
        await cache.init()
        data = b"This is a test bytes to be cached."
        await cache.set("key", data)
        value = await cache.get("key")
        assert value == data

    @pytest.mark.anyio
    async def test_set_get_dict(self, config: Config) -> None:
        cache = memory.Cache(config=config)
        await cache.init()
        data = {"key1": "value1", "key2": 123, "key3": True}
        await cache.set("key", data)
        value = await cache.get("key")
        assert value == data

    @pytest.mark.anyio
    async def test_set_get_list(self, config: Config) -> None:
        cache = memory.Cache(config=config)
        await cache.init()
        data = ["value1", 123, True]
        await cache.set("key", data)
        value = await cache.get("key")
        assert value == data

    @pytest.mark.anyio
    async def test_set_get_int(self, config: Config) -> None:
        cache = memory.Cache(config=config)
        await cache.init()
        data = 123
        await cache.set("key", data)
        value = await cache.get("key")
        assert value == data

    @pytest.mark.anyio
    async def test_set_get_float(self, config: Config) -> None:
        cache = memory.Cache(config=config)
        await cache.init()
        data = 123.45
        await cache.set("key", data)
        value = await cache.get("key")
        assert value == data

    @pytest.mark.anyio
    async def test_set_get_bool(self, config: Config) -> None:
        cache = memory.Cache(config=config)
        await cache.init()
        data = True
        await cache.set("key", data)
        value = await cache.get("key")
        assert value == data

    @pytest.mark.anyio
    async def test_delete(self, config: Config) -> None:
        cache = memory.Cache(config=config)
        await cache.init()
        await cache.set("key", "value")
        await cache.delete("key")
        value = await cache.get("key")
        assert value is None

    @pytest.mark.anyio
    async def test_clear(self, config: Config) -> None:
        cache = memory.Cache(config=config)
        await cache.init()
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.clear()
        value1 = await cache.get("key1")
        value2 = await cache.get("key2")
        assert value1 is None
        assert value2 is None

    @pytest.mark.anyio
    async def test_exists(self, config: Config) -> None:
        cache = memory.Cache(config=config)
        await cache.init()
        await cache.set("key", "value")
        assert await cache.exists("key")
        assert not await cache.exists("nonexistent_key")

    @pytest.mark.anyio
    async def test_raw(self, config: Config) -> None:
        cache = memory.Cache(config=config)
        await cache.init()
        await cache.set("key", "value")
        assert cache.raw("key") == "value"

    @pytest.mark.anyio
    async def test_raw_none(self, config: Config) -> None:
        cache = memory.Cache(config=config)
        await cache.init()
        assert cache.raw("key") is None

    @pytest.mark.anyio
    async def test_add(self, config: Config) -> None:
        cache = memory.Cache(config=config)
        await cache.init()
        assert await cache.add("key", "value")
        assert not await cache.add("key", "value")
        assert await cache.get("key") == "value"

    @pytest.mark.anyio
    async def test_multi_get(self, config: Config) -> None:
        cache = memory.Cache(config=config)
        await cache.init()
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        values = await cache.multi_get(["key1", "key2", "key3"])
        assert values == ["value1", "value2", None]

    @pytest.mark.anyio
    async def test_multi_set(self, config: Config) -> None:
        cache = memory.Cache(config=config)
        await cache.init()
        await cache.multi_set({"key1": "value1", "key2": "value2"})
        values = await cache.multi_get(["key1", "key2"])
        assert values == ["value1", "value2"]

    @pytest.mark.anyio
    async def test_increment(self, config: Config) -> None:
        cache = memory.Cache(config=config)
        await cache.init()
        await cache.set("key", 1)
        assert await cache.increment("key") == 2
        assert await cache.increment("key", 5) == 7
        assert await cache.get("key") == 7

    @pytest.mark.anyio
    async def test_increment_not_exist(self, config: Config) -> None:
        cache = memory.Cache(config=config)
        await cache.init()
        assert await cache.increment("key") == 1
        assert await cache.get("key") == 1

    @pytest.mark.anyio
    async def test_expire(self, config: Config) -> None:
        cache = memory.Cache(config=config)
        await cache.init()
        await cache.set("key", "value")
        assert await cache.expire("key", 1)
        assert await cache.get("key") == "value"

    @pytest.mark.anyio
    async def test_expire_not_exist(self, config: Config) -> None:
        cache = memory.Cache(config=config)
        await cache.init()
        assert not await cache.expire("key", 1)

    @pytest.mark.anyio
    async def test_ttl(self, config: Config) -> None:
        cache = memory.Cache(config=config)
        await cache.init()
        await cache.set("key", "value")
        assert cache.ttl == -1

    @pytest.mark.anyio
    async def test_ttl_not_exist(self, config: Config) -> None:
        cache = memory.Cache(config=config)
        await cache.init()
        assert cache.ttl == -2


class TestRedisCacheSettings:
    def test_default_values(self) -> None:
        settings = redis.CacheSettings()
        assert settings.host == SecretStr("127.0.0.1")
        assert settings.local_host == "127.0.0.1"
        assert settings.port == 6379
        assert settings.cluster is False
        assert settings.connect_timeout is None
        assert settings.max_connections is None
        assert settings.health_check_interval == 0

    def test_custom_values(self) -> None:
        settings = redis.CacheSettings(
            host=SecretStr("redis.example.com"),
            local_host="localhost",
            port=1234,
            cluster=True,
            connect_timeout=5.0,
            max_connections=100,
            health_check_interval=60,
        )
        assert settings.host == SecretStr("redis.example.com")
        assert settings.local_host == "localhost"
        assert settings.port == 1234
        assert settings.cluster is True
        assert settings.connect_timeout == 5.0
        assert settings.max_connections == 100
        assert settings.health_check_interval == 60

    def test_host_not_deployed(self, config: Config) -> None:
        config.deployed = False
        settings = redis.CacheSettings(config=config, local_host="localhost")
        assert settings.host == SecretStr("localhost")


class TestRedisCache:
    @pytest.mark.anyio
    async def test_init_default(self, config: Config) -> None:
        config.app.name = "test_app"
        cache = redis.Cache(config=config)
        with patch.object(Redis, "__init__", return_value=None) as mock_redis_init:
            await cache.init()
            assert cache.serializer == PickleSerializer()
            assert cache.namespace == "test_app:"
            mock_redis_init.assert_called_once_with(
                host="127.0.0.1",
                port=6379,
                client_name="test_app",
                cache=TrackingCache(),
                decode_responses=False,
                connect_timeout=None,
                max_connections=None,
                health_check_interval=0,
            )
            assert isinstance(cache.client, Redis)

    @pytest.mark.anyio
    async def test_init_cluster(self, config: Config) -> None:
        config.app.name = "test_app"
        config.cache.cluster = True
        cache = redis.Cache(config=config)
        with patch.object(
            RedisCluster, "__init__", return_value=None
        ) as mock_redis_init:
            await cache.init()
            assert cache.serializer == PickleSerializer()
            assert cache.namespace == "test_app:"
            mock_redis_init.assert_called_once_with(
                host="127.0.0.1",
                port=6379,
                client_name="test_app",
                cache=TrackingCache(),
                decode_responses=False,
                connect_timeout=None,
                max_connections=None,
            )
            assert isinstance(cache.client, RedisCluster)

    @pytest.mark.anyio
    async def test_clear_no_namespace(self, config: Config) -> None:
        config.app.name = "test_app"
        cache = redis.Cache(config=config)
        mock_client = AsyncMock()
        cache.client = mock_client
        mock_client.keys.return_value = [b"test_app:key1", b"test_app:key2"]
        await cache._clear()
        mock_client.keys.assert_called_once_with("test_app:*")
        mock_client.unlink.assert_called_with((b"test_app:key2",))
        assert mock_client.unlink.call_count == 2

    @pytest.mark.anyio
    async def test_clear_with_namespace(self, config: Config) -> None:
        config.app.name = "test_app"
        cache = redis.Cache(config=config)
        mock_client = AsyncMock()
        cache.client = mock_client
        mock_client.keys.return_value = [b"test_app:ns:key1", b"test_app:ns:key2"]
        await cache._clear(namespace="ns")
        mock_client.keys.assert_called_once_with("test_app:ns:*")
        mock_client.unlink.assert_called_with((b"test_app:ns:key2",))
        assert mock_client.unlink.call_count == 2

    @pytest.mark.anyio
    async def test_clear_no_keys(self, config: Config) -> None:
        config.app.name = "test_app"
        cache = redis.Cache(config=config)
        mock_client = AsyncMock()
        cache.client = mock_client
        mock_client.keys.return_value = []
        await cache._clear()
        mock_client.keys.assert_called_once_with("test_app:*")
        mock_client.unlink.assert_not_called()

    @pytest.mark.anyio
    async def test_exists(self, config: Config) -> None:
        cache = redis.Cache(config=config)
        mock_client = AsyncMock()
        cache.client = mock_client
        mock_client.exists.return_value = 1
        assert await cache._exists("key")
        mock_client.exists.assert_called_once_with(["key"])

        mock_client.exists.return_value = 0
        assert not await cache._exists("key")
        assert mock_client.exists.call_count == 2

    @pytest.mark.anyio
    async def test_close(self, config: Config) -> None:
        cache = redis.Cache(config=config)
        mock_client = AsyncMock()
        cache.client = mock_client
        await cache._close()
        mock_client.close.assert_not_called()
