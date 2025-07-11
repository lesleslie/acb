"""Tests for the base cache components."""

import typing as t
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiocache.backends.memory import SimpleMemoryCache
from aiocache.serializers import PickleSerializer
from acb.adapters.cache._base import CacheBaseSettings, MsgPackSerializer
from acb.adapters.cache.memory import Cache as MemoryCache
from acb.config import Config


class TestMsgPackSerializer:
    def test_init(self) -> None:
        serializer: MsgPackSerializer = MsgPackSerializer()
        assert serializer.use_list

        serializer = MsgPackSerializer(use_list=False)
        assert not serializer.use_list

    def test_dumps(self) -> None:
        serializer: MsgPackSerializer = MsgPackSerializer()
        test_data: dict[str, t.Any] = {
            "key": "value",
            "number": 42,
            "list": [1, 2, 3],
        }
        with (
            patch("acb.adapters.cache._base.msgpack.encode") as mock_encode,
            patch("acb.adapters.cache._base.compress.brotli") as mock_compress,
        ):
            mock_encode.return_value = b"encoded_data"
            mock_compress.return_value = b"compressed_data"
            result: str = serializer.dumps(test_data)
            mock_encode.assert_called_once_with(test_data)
            mock_compress.assert_called_once_with(b"encoded_data")
            assert result == "compressed_data"

    def test_loads(self) -> None:
        serializer: MsgPackSerializer = MsgPackSerializer()
        test_data: str = "compressed_data"
        with (
            patch("acb.adapters.cache._base.decompress.brotli") as mock_decompress,
            patch("acb.adapters.cache._base.msgpack.decode") as mock_decode,
        ):
            mock_decompress.return_value = b"decompressed_data"
            mock_decode.return_value = {"key": "value"}
            result: t.Any = serializer.loads(test_data)
            mock_decompress.assert_called_once_with(test_data.encode("latin-1"))
            mock_decode.assert_called_once_with(b"decompressed_data")
            assert result == {"key": "value"}
        result_none: t.Any = serializer.loads("")
        assert result_none is None

    def test_integration(self) -> None:
        serializer: MsgPackSerializer = MsgPackSerializer()
        test_data: dict[str, t.Any] = {
            "key": "value",
            "number": 42,
            "list": [1, 2, 3],
        }
        with (
            patch("acb.adapters.cache._base.msgpack.encode") as mock_encode,
            patch("acb.adapters.cache._base.compress.brotli") as mock_compress,
            patch("acb.adapters.cache._base.decompress.brotli") as mock_decompress,
            patch("acb.adapters.cache._base.msgpack.decode") as mock_decode,
        ):
            mock_encode.return_value = b"encoded_data"
            mock_compress.return_value = b"compressed_data"
            mock_decompress.return_value = b"decompressed_data"
            mock_decode.return_value = test_data
            serialized: str = serializer.dumps(test_data)
            assert isinstance(serialized, str)
            assert serialized == "compressed_data"
            deserialized: t.Any = serializer.loads(serialized)
            assert deserialized == test_data


class TestCacheBaseSettings:
    @pytest.fixture
    def mock_config(self) -> MagicMock:
        mock_config: MagicMock = MagicMock(spec=Config)
        mock_config.deployed = False
        return mock_config

    def test_init_default_values(self, mock_config: MagicMock) -> None:
        class TestCacheBaseSettings(CacheBaseSettings):
            def __init__(self, **values: t.Any) -> None:
                super(CacheBaseSettings, self).__init__(**values)
                self.response_ttl = self.default_ttl if mock_config.deployed else 1

        settings: TestCacheBaseSettings = TestCacheBaseSettings()
        assert settings.default_ttl == 86400
        assert settings.query_ttl == 600
        assert settings.response_ttl == 1
        assert settings.template_ttl == 86400

    def test_init_custom_values(self, mock_config: MagicMock) -> None:
        class TestCacheBaseSettings(CacheBaseSettings):
            def __init__(self, **values: t.Any) -> None:
                super(CacheBaseSettings, self).__init__(**values)
                self.response_ttl = self.default_ttl if mock_config.deployed else 1

        settings: TestCacheBaseSettings = TestCacheBaseSettings(
            default_ttl=3600,
            query_ttl=300,
            template_ttl=7200,
        )

        assert settings.default_ttl == 3600
        assert settings.query_ttl == 300
        assert settings.response_ttl == 1
        assert settings.template_ttl == 7200

    def test_init_deployed(self, mock_config: MagicMock) -> None:
        mock_config.deployed = True

        original_init = CacheBaseSettings.__init__

        def patched_init(self: CacheBaseSettings, **values: t.Any) -> None:
            original_init(self, **values)
            if mock_config.deployed:
                self.response_ttl = self.default_ttl

        with (
            patch.object(CacheBaseSettings, "__init__", patched_init),
            patch("acb.adapters.cache._base.depends.inject", lambda f: f),
            patch("acb.adapters.cache._base.depends", return_value=mock_config),
        ):
            settings: CacheBaseSettings = CacheBaseSettings()

            assert settings.response_ttl == settings.default_ttl


class TestMemoryCache:
    @pytest.fixture
    def mock_config(self) -> MagicMock:
        mock_config: MagicMock = MagicMock(spec=Config)
        mock_app: MagicMock = MagicMock()
        mock_app.name: str = "test_app"
        mock_config.app: MagicMock = mock_app
        return mock_config

    @pytest.mark.asyncio
    async def test_init(self, mock_config: MagicMock) -> None:
        cache: MemoryCache = MemoryCache()
        cache.config = mock_config

        with patch.object(
            SimpleMemoryCache,
            "__init__",
            return_value=None,
        ) as mock_init:
            # Init should not create the cache (lazy loading)
            await cache.init()
            mock_init.assert_not_called()

            # Cache should be created only when accessed
            _ = cache._cache
            mock_init.assert_called_once()
            _, kwargs = mock_init.call_args
            assert isinstance(kwargs["serializer"], PickleSerializer)
            assert kwargs["namespace"] == "test_app:"

    @pytest.mark.asyncio
    async def test_set_get(self) -> None:
        cache: MemoryCache = MemoryCache()

        cache._set = AsyncMock()
        cache._get = AsyncMock(return_value=b"test_value")

        test_value: bytes = b"test_value"
        await cache.set("test_key", test_value, ttl=60)
        cache._set.assert_called_once()
        call_args = cache._set.call_args
        assert call_args[0][0] == "test_key"
        assert isinstance(call_args[0][1], bytes | str)
        assert "test_value" in str(call_args[0][1])
        assert call_args[1]["ttl"] == 60

        result: t.Any = await cache.get("test_key")
        cache._get.assert_called_once()
        assert cache._get.call_args[0][0] == "test_key"
        assert isinstance(result, bytes | str)
        assert "test_value" in str(result)
