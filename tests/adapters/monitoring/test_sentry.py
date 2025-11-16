"""Tests for the Sentry monitoring adapter."""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr, ValidationError

from acb.adapters.monitoring.sentry import Monitoring, MonitoringSettings
from acb.config import Config


class TestSentryMonitoringSettings:
    def test_init(self) -> None:
        settings = MonitoringSettings(
            sentry_dsn=SecretStr("https://key@sentry.io/project"),
            sample_rate=0.5,
            debug=True,
            profiles_sample_rate=0.1,
        )
        assert settings.sentry_dsn.get_secret_value() == "https://key@sentry.io/project"
        assert settings.sample_rate == 0.5
        assert settings.debug is True
        assert settings.profiles_sample_rate == 0.1

    def test_default_values(self) -> None:
        settings = MonitoringSettings()
        assert settings.sentry_dsn.get_secret_value() == "https://"
        assert settings.sample_rate == 1.0
        assert settings.debug is False
        assert settings.profiles_sample_rate == 0

    def test_sample_rate_validation_valid(self) -> None:
        # Valid sample rates should pass
        settings = MonitoringSettings(sample_rate=0.0)
        assert settings.sample_rate == 0.0

        settings = MonitoringSettings(sample_rate=1.0)
        assert settings.sample_rate == 1.0

        settings = MonitoringSettings(sample_rate=0.5)
        assert settings.sample_rate == 0.5

    def test_sample_rate_validation_invalid(self) -> None:
        # Invalid sample rates should raise ValidationError
        with pytest.raises(ValidationError):
            MonitoringSettings(sample_rate=1.5)

        with pytest.raises(ValidationError):
            MonitoringSettings(sample_rate=-0.1)

    def test_profiles_sample_rate_validation_valid(self) -> None:
        # Valid profiles sample rates should pass
        settings = MonitoringSettings(profiles_sample_rate=0.0)
        assert settings.profiles_sample_rate == 0.0

        settings = MonitoringSettings(profiles_sample_rate=1.0)
        assert settings.profiles_sample_rate == 1.0

    def test_profiles_sample_rate_validation_invalid(self) -> None:
        # Invalid profiles sample rates should raise ValidationError
        with pytest.raises(ValidationError):
            MonitoringSettings(profiles_sample_rate=2.0)

        with pytest.raises(ValidationError):
            MonitoringSettings(profiles_sample_rate=-1.0)


class TestSentryMonitoring:
    @pytest.fixture
    def mock_config(self) -> MagicMock:
        config = MagicMock(spec=Config)
        config.monitoring = MagicMock(spec=MonitoringSettings)
        config.monitoring.sentry_dsn = SecretStr("https://key@sentry.io/project")
        config.monitoring.sample_rate = 1.0
        config.monitoring.debug = False
        config.monitoring.profiles_sample_rate = 0
        config.monitoring.traces_sample_rate = 0.5
        config.app = MagicMock()
        config.app.name = "test-app"
        config.app.version = "1.0.0"
        config.deployed = False
        return config

    @pytest.fixture
    def sentry_monitoring(self, mock_config: MagicMock) -> Monitoring:
        monitoring = Monitoring()
        monitoring.config = mock_config
        return monitoring

    @pytest.mark.asyncio
    @patch("acb.adapters.monitoring.sentry.sentry_init")
    async def test_init_success(
        self, mock_sentry_init: MagicMock, sentry_monitoring: Monitoring
    ) -> None:
        await sentry_monitoring.init()

        mock_sentry_init.assert_called_once()

        # Verify the call arguments separately
        call_args = mock_sentry_init.call_args[1]
        assert call_args["dsn"] == "https://key@sentry.io/project"
        assert call_args["server_name"] == "test-app"
        assert call_args["release"] == "1.0.0"
        assert call_args["environment"] == "development"
        assert call_args["sample_rate"] == 1.0
        assert call_args["debug"] is False
        assert call_args["traces_sample_rate"] == 0.5
        assert call_args["profiles_sample_rate"] == 0
        assert (
            len(call_args["integrations"]) == 2
        )  # GcpIntegration and AsyncioIntegration

    @pytest.mark.asyncio
    @patch("acb.adapters.monitoring.sentry.sentry_init")
    async def test_init_production_environment(
        self, mock_sentry_init: MagicMock, sentry_monitoring: Monitoring
    ) -> None:
        sentry_monitoring.config.deployed = True

        await sentry_monitoring.init()

        # Should use production environment when deployed
        call_args = mock_sentry_init.call_args[1]
        assert call_args["environment"] == "production"

    @pytest.mark.asyncio
    @patch("acb.adapters.monitoring.sentry.sentry_init")
    async def test_init_with_debug(
        self, mock_sentry_init: MagicMock, sentry_monitoring: Monitoring
    ) -> None:
        sentry_monitoring.config.monitoring.debug = True

        await sentry_monitoring.init()

        # Should pass debug flag
        call_args = mock_sentry_init.call_args[1]
        assert call_args["debug"] is True

    def test_module_metadata(self) -> None:
        # Test that module has proper structure
        from uuid import UUID

        from acb.adapters.monitoring.sentry import MODULE_ID, MODULE_STATUS

        assert isinstance(MODULE_ID, UUID)
        assert MODULE_STATUS is not None
