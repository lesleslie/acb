import sys
import tempfile
import typing as t
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from anyio import Path as AsyncPath
from acb.logger import (
    Logger,
    LoggerProtocol,
    LoggerSettings,
)


class Config:
    def __init__(self, root_path: str | None = None) -> None:
        self.deployed: bool = False
        self.debug: MagicMock = MagicMock()
        self.debug.production: bool = False
        self.debug.logger: bool = False
        self.root_path: AsyncPath = AsyncPath(
            root_path or tempfile.mkdtemp(prefix="test_logger_root_"),
        )
        self.logger: t.Any = None


class Settings:
    def __init__(self, **values: t.Any) -> None:
        for key, value in values.items():
            setattr(self, key, value)


mock_config: MagicMock = MagicMock()
mock_config.Config = Config
mock_config.Settings = Settings
mock_depends: MagicMock = MagicMock()

sys.modules["acb.config"] = mock_config
sys.modules["acb.depends"] = mock_depends


class TestLoggerSettings:
    def test_init_default(self) -> None:
        settings: LoggerSettings = LoggerSettings()

        assert not settings.verbose
        assert settings.deployed_level == "WARNING"
        assert settings.log_level == "INFO"
        assert settings.serialize is False
        assert isinstance(settings.format, dict)
        assert isinstance(settings.level_per_module, dict)
        assert isinstance(settings.level_colors, dict)

    def test_init_custom(self) -> None:
        custom_settings: dict[str, t.Any] = {
            "verbose": True,
            "deployed_level": "ERROR",
            "log_level": "DEBUG",
            "serialize": True,
            "format": {
                "time": "[{time}]",
                "level": "{level}",
                "sep": " - ",
                "name": "{name}",
                "line": "({line})",
                "message": "{message}",
            },
            "level_per_module": {"test": "DEBUG"},
            "level_colors": {"debug": "blue"},
        }

        settings: LoggerSettings = LoggerSettings(**custom_settings)

        assert settings.verbose
        assert settings.deployed_level == "ERROR"
        assert settings.log_level == "DEBUG"
        assert settings.serialize
        assert settings.format == custom_settings["format"]
        assert settings.level_per_module == custom_settings["level_per_module"]
        assert settings.level_colors == custom_settings["level_colors"]


class TestLoggerProtocol:
    def test_protocol_compliance(self) -> None:
        logger: Logger = Logger()
        assert isinstance(logger, LoggerProtocol)

        assert hasattr(logger, "debug")
        assert hasattr(logger, "info")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")
        assert hasattr(logger, "init")


class TestLogger:
    @pytest.fixture
    def mock_config(self) -> t.Generator[MagicMock]:
        with patch("acb.logger.depends.get") as mock_get:
            mock_config: MagicMock = MagicMock(spec=Config)
            mock_config.logger = LoggerSettings()
            mock_config.deployed = False
            mock_config.debug = MagicMock()
            mock_config.debug.production = False
            mock_config.debug.logger = False
            mock_config.root_path = "/test/path"

            mock_get.return_value = mock_config

            yield mock_config

    def test_init(self, mock_config: MagicMock) -> None:
        with patch("acb.logger._Logger.__init__") as mock_init:
            Logger()

            mock_init.assert_called_once()
            args: dict[str, t.Any] = mock_init.call_args[1]
            assert "core" in args
            assert args["exception"] is None
            assert args["depth"] == 0
            assert args["record"] is False
            assert args["lazy"] is False
            assert args["colors"] is False
            assert args["raw"] is False
            assert args["capture"] is True
            assert args["patchers"] == []
            assert args["extra"] == {}

    @pytest.mark.asyncio
    async def test_async_sink(self) -> None:
        with patch("acb.logger.aprint", new_callable=AsyncMock) as mock_aprint:
            await Logger.async_sink("Test message")

            mock_aprint.assert_called_once_with("Test message", end="")

    def test_logger_settings_format_none(self) -> None:
        settings = LoggerSettings(format=None)
        assert settings.settings is not None
        assert settings.settings["format"] == ""

    def test_logger_settings_serialize_none(self) -> None:
        settings = LoggerSettings(serialize=None)
        assert settings.settings is not None
        assert settings.settings["serialize"] is None

    def test_logger_settings_format_join(self) -> None:
        custom_format = {
            "time": "[{time}]",
            "level": " {level}",
            "message": " {message}",
        }
        settings = LoggerSettings(format=custom_format)
        expected_format = "[{time}] {level} {message}"
        assert settings.settings is not None
        assert settings.settings["format"] == expected_format

    def test_logger_settings_default_format_values(self) -> None:
        settings = LoggerSettings()
        assert settings.format is not None
        assert "time" in settings.format
        assert "level" in settings.format
        assert "sep" in settings.format
        assert "name" in settings.format
        assert "line" in settings.format
        assert "message" in settings.format

    def test_logger_settings_enqueue_setting(self) -> None:
        settings = LoggerSettings()
        assert settings.settings is not None
        assert settings.settings["enqueue"] is True

    def test_logger_settings_backtrace_setting(self) -> None:
        settings = LoggerSettings()
        assert settings.settings is not None
        assert settings.settings["backtrace"] is False

    def test_logger_settings_catch_setting(self) -> None:
        settings = LoggerSettings()
        assert settings.settings is not None
        assert settings.settings["catch"] is False

    def test_logger_settings_diagnose_setting(self) -> None:
        settings = LoggerSettings()
        assert settings.settings is not None
        assert settings.settings["diagnose"] is False

    def test_logger_settings_colorize_setting(self) -> None:
        settings = LoggerSettings()
        assert settings.settings is not None
        assert settings.settings["colorize"] is True
