"""Tests for the Sentry monitoring adapter."""

import typing as t
from unittest.mock import MagicMock, patch

import pytest
from acb.adapters.monitoring.sentry import Monitoring, MonitoringSettings
from acb.config import Config


@pytest.fixture
def mock_sentry_init() -> t.Generator[MagicMock]:
    mock = MagicMock()
    with patch("acb.adapters.monitoring.sentry.sentry_init", mock):
        yield mock


@pytest.fixture
def mock_integrations() -> dict[str, MagicMock]:
    integrations = {
        "GcpIntegration": MagicMock(),
        "AsyncioIntegration": MagicMock(),
    }

    integrations["GcpIntegration"].return_value = MagicMock(
        name="GcpIntegration_instance"
    )
    integrations["AsyncioIntegration"].return_value = MagicMock(
        name="AsyncioIntegration_instance"
    )

    return integrations


@pytest.fixture
def patch_integrations(
    mock_integrations: dict[str, MagicMock],
) -> t.Generator[None]:
    with (
        patch(
            "acb.adapters.monitoring.sentry.GcpIntegration",
            mock_integrations["GcpIntegration"],
        ),
        patch(
            "acb.adapters.monitoring.sentry.AsyncioIntegration",
            mock_integrations["AsyncioIntegration"],
        ),
    ):
        yield


@pytest.fixture
def monitoring_adapter(
    mock_sentry_init: MagicMock, patch_integrations: None
) -> Monitoring:
    mock_config = MagicMock()
    mock_config.monitoring = MonitoringSettings(
        sentry_dsn="https://test@sentry.io/123456",
        sample_rate=0.75,
        debug=True,
        traces_sample_rate=0.5,
        profiles_sample_rate=0.25,
    )
    mock_config.app.name = "test_app"
    mock_config.app.version = "1.0.0"
    mock_config.deployed = False

    adapter = Monitoring()
    adapter.config = mock_config

    return adapter


@pytest.mark.asyncio
async def test_init(
    monitoring_adapter: Monitoring,
    mock_sentry_init: MagicMock,
    mock_integrations: dict[str, MagicMock],
) -> None:
    await monitoring_adapter.init()

    mock_sentry_init.assert_called_once_with(
        dsn="https://test@sentry.io/123456",
        server_name="test_app",
        release="1.0.0",
        environment="development",
        sample_rate=0.75,
        debug=True,
        traces_sample_rate=0.5,
        profiles_sample_rate=0.25,
        integrations=[
            mock_integrations["GcpIntegration"].return_value,
            mock_integrations["AsyncioIntegration"].return_value,
        ],
    )


@pytest.mark.asyncio
async def test_init_production_environment(
    monitoring_adapter: Monitoring, mock_sentry_init: MagicMock
) -> None:
    monitoring_adapter.config.deployed = True

    await monitoring_adapter.init()

    called_args = mock_sentry_init.call_args[1]
    assert called_args["environment"] == "production"


class TestMonitoringSettings:
    def test_default_values(self) -> None:
        settings = MonitoringSettings()
        assert settings.sentry_dsn.get_secret_value() == "https://"
        assert settings.sample_rate == 1.0
        assert settings.debug is False
        assert settings.profiles_sample_rate == 0
        assert settings.traces_sample_rate == 0

    def test_valid_sample_rates(self) -> None:
        settings = MonitoringSettings(
            sample_rate=0.5, profiles_sample_rate=0.75, traces_sample_rate=0.25
        )
        assert settings.sample_rate == 0.5
        assert settings.profiles_sample_rate == 0.75
        assert settings.traces_sample_rate == 0.25

    def test_invalid_sample_rates(self) -> None:
        with pytest.raises(ValueError):
            MonitoringSettings(sample_rate=-0.1)

        with pytest.raises(ValueError):
            MonitoringSettings(sample_rate=1.1)

        with pytest.raises(ValueError):
            MonitoringSettings(profiles_sample_rate=-0.1)

        with pytest.raises(ValueError):
            MonitoringSettings(profiles_sample_rate=1.1)

    @patch("acb.adapters.monitoring.sentry.depends.inject")
    def test_init_with_config(self, mock_inject: MagicMock) -> None:
        mock_config = MagicMock(spec=Config)
        mock_config.deployed = False

        settings = MonitoringSettings()

        settings.__init__(config=mock_config)

        assert settings.sample_rate == 1.0

        mock_config.deployed = True
        settings.__init__(config=mock_config)

        assert settings.sample_rate == 1.0

    @patch("acb.adapters.monitoring.sentry.depends.inject")
    def test_init_with_explicit_sample_rate(self, mock_inject: MagicMock) -> None:
        mock_config = MagicMock(spec=Config)
        mock_config.deployed = True

        settings = MonitoringSettings(sample_rate=0.5)

        settings.__init__(config=mock_config, sample_rate=0.5)

        assert settings.sample_rate == 0.5
