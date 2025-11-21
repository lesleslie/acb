"""Tests for the base cache components."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typing as t

from acb.adapters.cache._base import CacheBase, CacheBaseSettings, MsgPackSerializer
from acb.adapters.cache.memory import Cache as MemoryCache
from acb.config import Config


class TestMsgPackSerializer:
    @pytest.mark.unit
    def test_init(self) -> None:
        serializer: MsgPackSerializer = MsgPackSerializer()
        assert serializer.use_list

        serializer = MsgPackSerializer(use_list=False)
        assert not serializer.use_list

    @pytest.mark.unit
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

    @pytest.mark.unit
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
            assert result == {"key": "value"}

    @pytest.mark.unit
    def test_loads_empty_string(self) -> None:
        serializer: MsgPackSerializer = MsgPackSerializer()
        result: t.Any = serializer.loads("")
        assert result is None

    @pytest.mark.unit
    def test_loads_none_value(self) -> None:
        serializer: MsgPackSerializer = MsgPackSerializer()
        result: t.Any = serializer.loads(None)  # type: ignore
        assert result is None

    @pytest.mark.unit
    def test_loads_no_decompressed_data(self) -> None:
        """Test handling when decompress.brotli returns empty data."""
        serializer: MsgPackSerializer = MsgPackSerializer()
        test_data: str = "compressed_data"

        with patch("acb.adapters.cache._base.decompress.brotli") as mock_decompress:
            mock_decompress.return_value = b""  # Empty data

            result: t.Any = serializer.loads(test_data)
            assert result is None

    @pytest.mark.unit
    def test_integration(self) -> None:
        serializer: MsgPackSerializer = MsgPackSerializer()
        test_data: dict[str, t.Any] = {
            "string": "test",
            "number": 42,
            "list": [1, 2, 3],
            "nested": {"key": "value"},
        }
        serialized: str = serializer.dumps(test_data)
        # We can't easily test deserialization without the actual compression/decompression
        # but we can at least verify it's a string
        assert isinstance(serialized, str)
        assert len(serialized) > 0


class TestCacheBaseSettings:
    @pytest.fixture
    def mock_config(self) -> MagicMock:
        config = MagicMock(spec=Config)
        config.deployed = False
        return config

    def _build_settings(
        self,
        config: t.Any,
        **values: t.Any,
    ) -> CacheBaseSettings:
        instance = CacheBaseSettings.__new__(CacheBaseSettings)
        CacheBaseSettings.__init__.__wrapped__(instance, config=config, **values)
        return instance

    @pytest.mark.unit
    def test_init_default_values(self, mock_config: MagicMock) -> None:
        settings = self._build_settings(mock_config)
        assert settings.default_ttl == 86400
        assert settings.query_ttl == 600
        assert settings.host.get_secret_value() == "127.0.0.1"
        assert settings.response_ttl == 1  # Not deployed, so 1

    @pytest.mark.unit
    def test_init_custom_values(self, mock_config: MagicMock) -> None:
        settings = self._build_settings(
            mock_config,
            default_ttl=3600,
            host="custom.host",
            port=1234,
            response_ttl=720,
        )
        assert settings.default_ttl == 3600
        assert settings.host.get_secret_value() == "custom.host"
        assert settings.port == 1234
        assert settings.response_ttl == 720

    @pytest.mark.unit
    def test_init_deployed(self) -> None:
        # Create a mock config with deployed=True
        mock_config = MagicMock(spec=Config)
        mock_config.deployed = True

        settings = self._build_settings(mock_config)

        # When deployed, response_ttl should be the default_ttl
        assert settings.response_ttl == 86400

    @pytest.mark.unit
    def test_missing_deployed_attr_falls_back_to_depends(self) -> None:
        fallback_config = MagicMock(spec=Config)
        fallback_config.deployed = True

        with patch(
            "acb.adapters.cache._base.depends.get_sync",
            return_value=fallback_config,
        ) as mock_get_sync:
            settings = self._build_settings(config=object())

            mock_get_sync.assert_called_once_with(Config)
            assert settings.response_ttl == settings.default_ttl


class TestCacheBase:
    """Test the CacheBase class."""

    class MockCache(CacheBase):
        """Mock implementation of CacheBase for testing."""

        async def _create_client(self) -> t.Any:
            """Create a mock client."""
            return MagicMock()

    @pytest.fixture
    def mock_cache(self) -> MockCache:
        """Create a mock cache instance."""
        return self.MockCache()

    @pytest.mark.unit
    def test_init(self) -> None:
        """Test CacheBase initialization."""
        cache = self.MockCache()
        assert cache._client is None
        assert cache._client_lock is None

    @pytest.mark.asyncio
    async def test_ensure_client_creates_lock(self, mock_cache: MockCache) -> None:
        """Test that _ensure_client creates a lock when needed."""
        # First call should create the lock
        client = await mock_cache._ensure_client()
        assert client is not None
        assert mock_cache._client_lock is not None
        assert mock_cache._client is not None

    @pytest.mark.asyncio
    async def test_create_client_not_implemented(self) -> None:
        """Test that _create_client raises NotImplementedError."""

        class IncompleteCache(CacheBase):
            pass

        cache = IncompleteCache()
        with pytest.raises(NotImplementedError):
            await cache._create_client()

    @pytest.mark.asyncio
    async def test_cleanup_resources(self, mock_cache: MockCache) -> None:
        """Test _cleanup_resources method."""
        # First ensure we have a client
        await mock_cache._ensure_client()
        assert mock_cache._client is not None

        # Test cleanup
        await mock_cache._cleanup_resources()
        assert mock_cache._client is None

    @pytest.mark.asyncio
    async def test_delete_method(self, mock_cache: MockCache) -> None:
        """Test the delete method."""
        # Mock the client and its delete method
        mock_client = MagicMock()
        mock_client.delete = AsyncMock(return_value=True)

        # Set the mock client
        mock_cache._client = mock_client

        # Test delete
        result = await mock_cache.delete("test_key")
        assert result is True
        mock_client.delete.assert_called_once_with("test_key")


class TestMemoryCache:
    @pytest.mark.unit
    def test_init(self) -> None:
        cache = MemoryCache()
        assert cache is not None

    @pytest.mark.asyncio
    async def test_set_get(self, mock_config: MagicMock) -> None:
        mock_config.app = MagicMock()
        mock_config.app.name = "test"

        cache = MemoryCache()
        cache.config = mock_config

        await cache.set("test_key", "test_value", ttl=10)
        result = await cache.get("test_key")
        assert result == "test_value"
