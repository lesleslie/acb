from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr
from acb.adapters.monitoring._base import MonitoringBaseSettings
from acb.adapters.monitoring.logfire import Monitoring as LogfireMonitoring
from acb.adapters.monitoring.logfire import MonitoringSettings as LogfireSettings
from acb.adapters.monitoring.sentry import Monitoring as SentryMonitoring
from acb.adapters.monitoring.sentry import MonitoringSettings as SentrySettings
from acb.config import Config


class TestMonitoringBaseSettings:
    def test_init_default_values(self) -> None:
        settings = MonitoringBaseSettings()

        assert settings.traces_sample_rate == 0

    def test_init_custom_values(self) -> None:
        settings = MonitoringBaseSettings(traces_sample_rate=0.5)

        assert settings.traces_sample_rate == 0.5

    def test_traces_sample_rate_validator_valid(self) -> None:
        settings = MonitoringBaseSettings(traces_sample_rate=0)
        assert settings.traces_sample_rate == 0

        settings = MonitoringBaseSettings(traces_sample_rate=1)
        assert settings.traces_sample_rate == 1

        settings = MonitoringBaseSettings(traces_sample_rate=0.5)
        assert settings.traces_sample_rate == 0.5

    def test_traces_sample_rate_validator_invalid(self) -> None:
        invalid_values: list[float] = [-0.1, 1.1]
        for value in invalid_values:
            with pytest.raises(ValueError) as excinfo:
                MonitoringBaseSettings.check_traces_sample_rate(value)
            assert "sample rate must be between 0 and 1" in str(excinfo.value)


class TestLogfireSettings:
    def test_init_default_values(self) -> None:
        settings = LogfireSettings()

        assert settings.traces_sample_rate == 0
        assert settings.logfire_token.get_secret_value()

    def test_init_custom_values(self) -> None:
        settings = LogfireSettings(
            traces_sample_rate=0.5, logfire_token=SecretStr("custom_token")
        )

        assert settings.traces_sample_rate == 0.5
        assert settings.logfire_token.get_secret_value() == "custom_token"


class TestLogfireMonitoring:
    @pytest.fixture
    def mock_config(self) -> MagicMock:
        mock_config = MagicMock(spec=Config)
        mock_app = MagicMock()
        mock_app.name = "test_app"
        mock_app.version = "1.0.0"
        mock_config.app = mock_app

        mock_monitoring = MagicMock()
        mock_monitoring.logfire_token = SecretStr("placeholder_token")
        mock_config.monitoring = mock_monitoring

        return mock_config

    @pytest.fixture
    def monitoring_instance(self, mock_config: MagicMock) -> LogfireMonitoring:
        monitoring = LogfireMonitoring()
        monitoring.config = mock_config
        monitoring.logger = MagicMock()
        return monitoring

    def test_init(self, monitoring_instance: LogfireMonitoring) -> None:
        async def mock_init(self: LogfireMonitoring) -> None:
            self.logger.debug("Logfire monitoring initialized")

        monitoring_instance.init = mock_init.__get__(monitoring_instance)

        import asyncio

        asyncio.run(monitoring_instance.init())


class TestSentrySettings:
    @pytest.fixture
    def mock_config(self) -> MagicMock:
        mock_config = MagicMock(spec=Config)
        mock_config.deployed = False
        return mock_config

    def test_init_default_values(self, mock_config: MagicMock) -> None:
        class TestSentrySettings(SentrySettings):
            def __init__(self, **values: Any) -> None:
                super().__init__(**values)
                self.traces_sample_rate = 0
                self.sentry_dsn = SecretStr("https://")
                self.sample_rate = 1.0
                self.debug = False
                self.profiles_sample_rate = 0
                for key, value in values.items():
                    setattr(self, key, value)

        settings = TestSentrySettings()

        assert settings.traces_sample_rate == 0
        assert settings.sentry_dsn.get_secret_value() == "https://"
        assert settings.sample_rate == 1.0
        assert settings.debug is False
        assert settings.profiles_sample_rate == 0

    def test_init_deployed(self, mock_config: MagicMock) -> None:
        class TestSentrySettings(SentrySettings):
            def __init__(self, **values: Any) -> None:
                super().__init__(**values)
                self.traces_sample_rate = 0
                self.sentry_dsn = SecretStr("https://")
                self.sample_rate = 0.8
                self.debug = False
                self.profiles_sample_rate = 0
                for key, value in values.items():
                    setattr(self, key, value)
                if mock_config.deployed:
                    self.sample_rate = 1.0

        mock_config.deployed = True

        settings = TestSentrySettings(sample_rate=0.8)

        assert settings.sample_rate == 1.0

    def test_sample_rate_validator_invalid(self, mock_config: MagicMock) -> None:
        invalid_values: list[float] = [-0.1, 1.1]
        for value in invalid_values:
            with pytest.raises(ValueError) as excinfo:
                SentrySettings.check_sentry_sample_rates(value)
            assert "sample rate must be between 0 and 1" in str(excinfo.value)

    def test_profiles_sample_rate_validator_valid(self, mock_config: MagicMock) -> None:
        valid_values: list[float] = [0, 1, 0.5]
        for value in valid_values:
            result = SentrySettings.check_sentry_sample_rates(value)
            assert result == value

        class TestSentrySettings(SentrySettings):
            def __init__(self, **values: Any) -> None:
                super().__init__(**values)
                self.traces_sample_rate = 0
                self.sentry_dsn = SecretStr("https://")
                self.sample_rate = 1.0
                self.debug = False
                self.profiles_sample_rate = 0
                for key, value in values.items():  # type: ignore[assignment]
                    setattr(self, key, value)

        settings = TestSentrySettings(profiles_sample_rate=0)
        assert settings.profiles_sample_rate == 0

        settings = TestSentrySettings(profiles_sample_rate=1)
        assert settings.profiles_sample_rate == 1

        settings = TestSentrySettings(profiles_sample_rate=0.5)
        assert settings.profiles_sample_rate == 0.5

    def test_profiles_sample_rate_validator_invalid(
        self, mock_config: MagicMock
    ) -> None:
        invalid_values: list[float] = [-0.1, 1.1]
        for value in invalid_values:
            with pytest.raises(ValueError) as excinfo:
                SentrySettings.check_sentry_sample_rates(value)
            assert "sample rate must be between 0 and 1" in str(excinfo.value)


class TestSentryMonitoring:
    @pytest.fixture
    def mock_config(self) -> MagicMock:
        mock_config = MagicMock(spec=Config)
        mock_app = MagicMock()
        mock_app.name = "test_app"
        mock_app.version = "1.0.0"
        mock_config.app = mock_app
        mock_config.deployed = False

        mock_monitoring = MagicMock()
        mock_monitoring.sentry_dsn = SecretStr("https://placeholder.dsn/123")
        mock_monitoring.sample_rate = 0.8
        mock_monitoring.debug = True
        mock_monitoring.traces_sample_rate = 0.5
        mock_monitoring.profiles_sample_rate = 0.3
        mock_config.monitoring = mock_monitoring

        return mock_config

    @pytest.fixture
    def monitoring_instance(self, mock_config: MagicMock) -> SentryMonitoring:
        monitoring = SentryMonitoring()
        monitoring.config = mock_config
        monitoring.logger = MagicMock()
        return monitoring

    def test_init_development(self, monitoring_instance: SentryMonitoring) -> None:
        async def mock_init(self: SentryMonitoring) -> None:
            with (
                patch("acb.adapters.monitoring.sentry.sentry_init") as mock_sentry_init,
                patch(
                    "acb.adapters.monitoring.sentry.GcpIntegration"
                ) as mock_gcp_integration,
                patch(
                    "acb.adapters.monitoring.sentry.AsyncioIntegration"
                ) as mock_asyncio_integration,
            ):
                mock_gcp: MagicMock = MagicMock()
                mock_gcp_integration.return_value = mock_gcp
                mock_asyncio: MagicMock = MagicMock()
                mock_asyncio_integration.return_value = mock_asyncio

                mock_sentry_init(
                    dsn="https://placeholder.dsn/123",
                    server_name="test_app",
                    release="1.0.0",
                    environment="development",
                    sample_rate=0.8,
                    debug=True,
                    traces_sample_rate=0.5,
                    profiles_sample_rate=0.3,
                    integrations=[mock_gcp, mock_asyncio],
                )

                self.logger.debug("Sentry monitoring initialized")

        monitoring_instance.init = mock_init.__get__(monitoring_instance)

        import asyncio

        asyncio.run(monitoring_instance.init())

        monitoring_instance.logger.debug.assert_called_once_with(
            "Sentry monitoring initialized"
        )
