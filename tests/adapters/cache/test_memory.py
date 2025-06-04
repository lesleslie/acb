"""Tests for the Memory Cache adapter."""

from unittest.mock import MagicMock, patch

import pytest
from aiocache.backends.memory import SimpleMemoryCache
from aiocache.serializers import PickleSerializer
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

            await adapter.init()

            mock_smc.assert_called_once()
            call_kwargs = mock_smc.call_args[1]
            assert "namespace" in call_kwargs
            assert call_kwargs["namespace"] == "test_app:"
            assert "serializer" in call_kwargs
            assert isinstance(call_kwargs["serializer"], PickleSerializer)

            assert mock_instance.timeout == 0.0

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

            await adapter.init(timeout=5.0)

            mock_smc.assert_called_once()
            call_kwargs = mock_smc.call_args[1]
            assert "namespace" in call_kwargs
            assert call_kwargs["namespace"] == "test_app:"
            assert "serializer" in call_kwargs
            assert isinstance(call_kwargs["serializer"], PickleSerializer)
            assert "timeout" in call_kwargs
            assert call_kwargs["timeout"] == 5.0

            assert mock_instance.timeout == 0.0

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
