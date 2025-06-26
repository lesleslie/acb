"""Tests for the Logfire monitoring adapter."""

import typing as t
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from pydantic import SecretStr
from acb.adapters.monitoring.logfire import Monitoring, MonitoringSettings
from acb.logger import Logger


@pytest.fixture
def mock_logfire_modules() -> t.Generator[dict[str, MagicMock]]:
    mocks = {
        "configure": MagicMock(),
        "instrument_pydantic": MagicMock(),
        "instrument_httpx": MagicMock(),
        "instrument_redis": MagicMock(),
        "instrument_sqlalchemy": MagicMock(),
        "instrument_system_metrics": MagicMock(),
        "loguru_handler": MagicMock(),
    }

    with (
        patch("acb.adapters.monitoring.logfire.configure", mocks["configure"]),
        patch(
            "acb.adapters.monitoring.logfire.instrument_pydantic",
            mocks["instrument_pydantic"],
        ),
        patch(
            "acb.adapters.monitoring.logfire.instrument_httpx",
            mocks["instrument_httpx"],
        ),
        patch(
            "acb.adapters.monitoring.logfire.instrument_redis",
            mocks["instrument_redis"],
        ),
        patch(
            "acb.adapters.monitoring.logfire.instrument_sqlalchemy",
            mocks["instrument_sqlalchemy"],
        ),
        patch(
            "acb.adapters.monitoring.logfire.instrument_system_metrics",
            mocks["instrument_system_metrics"],
        ),
        patch(
            "acb.adapters.monitoring.logfire.loguru_handler", mocks["loguru_handler"]
        ),
    ):
        yield mocks


@pytest.fixture
def mock_adapters() -> t.Generator[MagicMock]:
    mock = MagicMock()

    adapters = []
    for name in ("loguru", "httpx", "redis", "sqlalchemy", "other_adapter"):
        adapter_mock = MagicMock()
        type(adapter_mock).name = PropertyMock(return_value=name)
        adapters.append(adapter_mock)

    mock.return_value = adapters

    with patch("acb.adapters.monitoring.logfire.get_installed_adapters", mock):
        yield mock


@pytest.fixture
def mock_sql() -> t.Generator[MagicMock]:
    mock = MagicMock()
    mock.engine = MagicMock()

    with patch("acb.adapters.monitoring.logfire.depends.get", return_value=mock):
        yield mock


@pytest.fixture
def monitoring_adapter(
    mock_logfire_modules: dict[str, MagicMock],
    mock_adapters: MagicMock,
    mock_sql: MagicMock,
) -> Monitoring:
    mock_config = MagicMock()
    mock_config.monitoring = MonitoringSettings(logfire_token=SecretStr("test_token"))
    mock_config.app.name = "test_app"
    mock_config.app.version = "1.0.0"

    mock_logger = MagicMock(spec=Logger)

    adapter = Monitoring()
    adapter.config = mock_config
    adapter.logger = mock_logger

    return adapter


@pytest.mark.asyncio
async def test_init(
    monitoring_adapter: Monitoring,
    mock_logfire_modules: dict[str, MagicMock],
    mock_sql: MagicMock,
) -> None:
    with patch("loguru.logger") as mock_loguru_logger:
        await monitoring_adapter.init()

        mock_logfire_modules["configure"].assert_called_once_with(
            token="test_token",
            service_name="test_app",
            service_version="1.0.0",
        )

        mock_logfire_modules["instrument_pydantic"].assert_called_once_with(
            record="all"
        )

        mock_logfire_modules["loguru_handler"].assert_called_once()
        mock_loguru_logger.configure.assert_called_once()
        mock_logfire_modules["instrument_httpx"].assert_called_once()
        mock_logfire_modules["instrument_redis"].assert_called_once()
        mock_logfire_modules["instrument_sqlalchemy"].assert_called_once_with(
            engine=mock_sql.engine
        )
        mock_logfire_modules["instrument_system_metrics"].assert_called_once()


@pytest.mark.asyncio
async def test_init_with_no_adapters(
    monitoring_adapter: Monitoring, mock_logfire_modules: dict[str, MagicMock]
) -> None:
    with patch(
        "acb.adapters.monitoring.logfire.get_installed_adapters", return_value=[]
    ):
        await monitoring_adapter.init()

    mock_logfire_modules["configure"].assert_called_once()
    mock_logfire_modules["instrument_pydantic"].assert_called_once()
    mock_logfire_modules["instrument_system_metrics"].assert_called_once()

    # configure is called once during init, not during adapter-specific setup
    mock_logfire_modules["instrument_httpx"].assert_not_called()
    mock_logfire_modules["instrument_redis"].assert_not_called()
    mock_logfire_modules["instrument_sqlalchemy"].assert_not_called()


class TestMonitoringSettings:
    def test_valid_traces_sample_rate(self) -> None:
        settings = MonitoringSettings(traces_sample_rate=0.5)
        assert settings.traces_sample_rate == 0.5

        settings = MonitoringSettings(traces_sample_rate=0.0)
        assert settings.traces_sample_rate == 0.0

        settings = MonitoringSettings(traces_sample_rate=1.0)
        assert settings.traces_sample_rate == 1.0

    def test_invalid_traces_sample_rate(self) -> None:
        with pytest.raises(ValueError):
            MonitoringSettings(traces_sample_rate=-0.1)

        with pytest.raises(ValueError):
            MonitoringSettings(traces_sample_rate=1.1)
