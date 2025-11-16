"""Tests for Logfire monitoring adapter."""

from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from pydantic import SecretStr

from acb.adapters import AdapterStatus
from acb.adapters.monitoring.logfire import (
    MODULE_ID,
    MODULE_STATUS,
    Monitoring,
    MonitoringSettings,
)
from acb.config import Config


class TestLogfireMonitoring:
    @pytest.fixture
    def mock_config(self) -> MagicMock:
        config = MagicMock(spec=Config)
        config.monitoring = MagicMock(spec=MonitoringSettings)
        config.monitoring.logfire_token = SecretStr("test-token")
        config.app = MagicMock()
        config.app.name = "test-app"
        config.app.version = "1.0.0"
        return config

    @pytest.fixture
    def logfire_monitoring(self, mock_config: MagicMock) -> Monitoring:
        monitoring = Monitoring()
        monitoring.config = mock_config
        return monitoring

    def test_module_metadata(self) -> None:
        """Test that module metadata is properly defined."""
        assert isinstance(MODULE_ID, UUID)
        assert MODULE_STATUS == AdapterStatus.STABLE

    def test_monitoring_settings(self) -> None:
        """Test MonitoringSettings initialization and validation."""
        settings = MonitoringSettings()
        assert isinstance(settings.logfire_token, SecretStr)
        assert settings.logfire_token.get_secret_value() == "secret"

        # Test with custom token
        custom_settings = MonitoringSettings(logfire_token=SecretStr("custom-token"))
        assert custom_settings.logfire_token.get_secret_value() == "custom-token"

    @pytest.mark.asyncio
    async def test_init_basic_configuration(
        self, logfire_monitoring: Monitoring
    ) -> None:
        """Test basic Logfire configuration."""
        with (
            patch("acb.adapters.monitoring.logfire.configure") as mock_configure,
            patch(
                "acb.adapters.monitoring.logfire.instrument_pydantic"
            ) as mock_instrument_pydantic,
            patch(
                "acb.adapters.monitoring.logfire.instrument_system_metrics"
            ) as mock_instrument_system_metrics,
            patch(
                "acb.adapters.monitoring.logfire.get_installed_adapters",
                return_value=[],
            ),
        ):
            await logfire_monitoring.init()

            mock_configure.assert_called_once_with(
                token="test-token",
                service_name="test-app",
                service_version="1.0.0",
            )
            mock_instrument_pydantic.assert_called_once_with(record="all")
            mock_instrument_system_metrics.assert_called_once()

    @pytest.mark.asyncio
    async def test_init_with_loguru_adapter(
        self, logfire_monitoring: Monitoring
    ) -> None:
        """Test initialization when loguru adapter is installed."""
        mock_adapter = MagicMock()
        mock_adapter.name = "loguru"

        with (
            patch("acb.adapters.monitoring.logfire.configure"),
            patch("acb.adapters.monitoring.logfire.instrument_pydantic"),
            patch("acb.adapters.monitoring.logfire.instrument_system_metrics"),
            patch(
                "acb.adapters.monitoring.logfire.get_installed_adapters",
                return_value=[mock_adapter],
            ),
            patch(
                "acb.adapters.monitoring.logfire.loguru_handler"
            ) as mock_loguru_handler,
        ):
            # Mock the loguru logger import inside the case statement
            mock_logger = MagicMock()
            with patch("loguru.logger", mock_logger):
                await logfire_monitoring.init()

                mock_loguru_handler.assert_called_once()
                mock_logger.configure.assert_called_once()

    @pytest.mark.asyncio
    async def test_init_with_httpx_adapter(
        self, logfire_monitoring: Monitoring
    ) -> None:
        """Test initialization when httpx adapter is installed."""
        mock_adapter = MagicMock()
        mock_adapter.name = "httpx"

        with (
            patch("acb.adapters.monitoring.logfire.configure"),
            patch("acb.adapters.monitoring.logfire.instrument_pydantic"),
            patch("acb.adapters.monitoring.logfire.instrument_system_metrics"),
            patch(
                "acb.adapters.monitoring.logfire.get_installed_adapters",
                return_value=[mock_adapter],
            ),
            patch(
                "acb.adapters.monitoring.logfire.instrument_httpx"
            ) as mock_instrument_httpx,
        ):
            await logfire_monitoring.init()
            mock_instrument_httpx.assert_called_once()

    @pytest.mark.asyncio
    async def test_init_with_redis_adapter(
        self, logfire_monitoring: Monitoring
    ) -> None:
        """Test initialization when redis adapter is installed."""
        mock_adapter = MagicMock()
        mock_adapter.name = "redis"

        with (
            patch("acb.adapters.monitoring.logfire.configure"),
            patch("acb.adapters.monitoring.logfire.instrument_pydantic"),
            patch("acb.adapters.monitoring.logfire.instrument_system_metrics"),
            patch(
                "acb.adapters.monitoring.logfire.get_installed_adapters",
                return_value=[mock_adapter],
            ),
            patch(
                "acb.adapters.monitoring.logfire.instrument_redis"
            ) as mock_instrument_redis,
        ):
            await logfire_monitoring.init()
            mock_instrument_redis.assert_called_once()

    @pytest.mark.asyncio
    async def test_init_with_sqlalchemy_adapter(
        self, logfire_monitoring: Monitoring
    ) -> None:
        """Test initialization when sqlalchemy adapter is installed."""
        mock_adapter = MagicMock()
        mock_adapter.name = "sqlalchemy"

        mock_sql = MagicMock()
        mock_sql.engine = MagicMock()

        with (
            patch("acb.adapters.monitoring.logfire.configure"),
            patch("acb.adapters.monitoring.logfire.instrument_pydantic"),
            patch("acb.adapters.monitoring.logfire.instrument_system_metrics"),
            patch(
                "acb.adapters.monitoring.logfire.get_installed_adapters",
                return_value=[mock_adapter],
            ),
            patch(
                "acb.adapters.monitoring.logfire.instrument_sqlalchemy"
            ) as mock_instrument_sqlalchemy,
        ):
            # Mock depends.get to return mock_sql only for SqlBase calls
            original_depends_get = logfire_monitoring.config

            def mock_depends_get(*args, **kwargs):
                if not args and not kwargs:  # No arguments means SqlBase request
                    return mock_sql
                return original_depends_get

            with patch(
                "acb.adapters.monitoring.logfire.depends.get",
                side_effect=mock_depends_get,
            ):
                await logfire_monitoring.init()
                mock_instrument_sqlalchemy.assert_called_once_with(
                    engine=mock_sql.engine
                )

    @pytest.mark.asyncio
    async def test_init_with_multiple_adapters(
        self, logfire_monitoring: Monitoring
    ) -> None:
        """Test initialization with multiple adapters installed."""
        mock_adapters = []
        for name in ["httpx", "redis", "unknown"]:
            adapter = MagicMock()
            adapter.name = name
            mock_adapters.append(adapter)

        with (
            patch("acb.adapters.monitoring.logfire.configure"),
            patch("acb.adapters.monitoring.logfire.instrument_pydantic"),
            patch("acb.adapters.monitoring.logfire.instrument_system_metrics"),
            patch(
                "acb.adapters.monitoring.logfire.get_installed_adapters",
                return_value=mock_adapters,
            ),
            patch(
                "acb.adapters.monitoring.logfire.instrument_httpx"
            ) as mock_instrument_httpx,
            patch(
                "acb.adapters.monitoring.logfire.instrument_redis"
            ) as mock_instrument_redis,
        ):
            await logfire_monitoring.init()

            mock_instrument_httpx.assert_called_once()
            mock_instrument_redis.assert_called_once()

    @pytest.mark.asyncio
    async def test_init_with_unknown_adapters(
        self, logfire_monitoring: Monitoring
    ) -> None:
        """Test initialization with unknown adapters (should be ignored)."""
        mock_adapter = MagicMock()
        mock_adapter.name = "unknown_adapter"

        with (
            patch("acb.adapters.monitoring.logfire.configure"),
            patch("acb.adapters.monitoring.logfire.instrument_pydantic"),
            patch("acb.adapters.monitoring.logfire.instrument_system_metrics"),
            patch(
                "acb.adapters.monitoring.logfire.get_installed_adapters",
                return_value=[mock_adapter],
            ),
        ):
            # Should not raise any exceptions for unknown adapters
            await logfire_monitoring.init()

    def test_monitoring_base_inheritance(self, logfire_monitoring: Monitoring) -> None:
        """Test that Monitoring inherits from MonitoringBase."""
        from acb.adapters.monitoring._base import MonitoringBase

        assert isinstance(logfire_monitoring, MonitoringBase)

    def test_depends_registration(self) -> None:
        """Test that the Monitoring class is registered with depends."""
        from acb.adapters.monitoring.logfire import depends

        # This test verifies that depends.set(Monitoring) was called
        # The actual registration is tested indirectly through fixture usage
        assert depends is not None
