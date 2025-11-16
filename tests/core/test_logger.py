"""Tests for the logger module.

NOTE: Many tests in this file are obsolete after the logger refactoring
to use the adapter system. Tests for internal implementation details of
the old Logger class have been marked as skipped. New tests should focus
on the logger adapter system in acb/adapters/logger/ instead.
"""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from acb.adapters.logger import LoggerProtocol
from acb.adapters.logger._base import LoggerBase
from acb.logger import (
    InterceptHandler,
    Logger,
    LoggerSettings,
)


class TestLoggerSettings:
    """Test LoggerSettings class."""

    def test_default_logger_settings(self) -> None:
        """Test default LoggerSettings values."""
        settings = LoggerSettings()
        assert settings.verbose is False
        assert settings.deployed_level == "WARNING"
        assert settings.log_level == "INFO"
        assert settings.serialize is False
        assert isinstance(settings.format, dict)
        assert "time" in settings.format
        assert settings.level_per_module == {}
        assert settings.level_colors == {}
        assert isinstance(settings.settings, dict)
        assert "format" in settings.settings
        assert settings.settings["enqueue"] is True
        assert settings.settings["backtrace"] is False
        assert settings.settings["catch"] is False
        assert settings.settings["serialize"] is False
        assert settings.settings["diagnose"] is False
        assert settings.settings["colorize"] is True

    def test_custom_logger_settings(self) -> None:
        """Test custom LoggerSettings values."""
        custom_format = {
            "time": "[{time:HH:mm:ss}]",
            "level": " {level}",
            "message": " {message}",
        }
        settings = LoggerSettings(
            verbose=True,
            deployed_level="ERROR",
            log_level="DEBUG",
            serialize=True,
            format=custom_format,
            level_per_module={"module1": "DEBUG"},
            level_colors={"DEBUG": "blue"},
        )
        assert settings.verbose is True
        assert settings.deployed_level == "ERROR"
        assert settings.log_level == "DEBUG"
        assert settings.serialize is True
        assert settings.format == custom_format
        assert settings.level_per_module == {"module1": "DEBUG"}
        assert settings.level_colors == {"DEBUG": "blue"}
        assert settings.settings["serialize"] is True


class TestLoggerProtocol:
    """Test LoggerProtocol."""

    def test_logger_protocol(self) -> None:
        """Test that LoggerProtocol defines the expected interface."""
        # This is more of a static check - we're verifying the protocol definition
        assert hasattr(LoggerProtocol, "debug")
        assert hasattr(LoggerProtocol, "info")
        assert hasattr(LoggerProtocol, "warning")
        assert hasattr(LoggerProtocol, "error")
        assert hasattr(LoggerProtocol, "init")


class TestLoggerBase:
    """Test LoggerBase class."""

    def test_logger_base_initialization(self) -> None:
        """Test LoggerBase initialization."""
        # LoggerBase is abstract, so we can't instantiate it directly
        # But we can verify it has the expected attributes
        assert hasattr(LoggerBase, "config")


@pytest.mark.skip(
    reason="Obsolete after logger refactoring to adapter system - tests old internal implementation"
)
class TestLogger:
    """Test Logger class.

    OBSOLETE: These tests are for the old Logger implementation.
    The logger has been refactored to use the adapter system.
    Tests for logger functionality should be in adapter-specific test files.
    """

    @pytest.fixture
    def logger(self) -> Logger:
        """Create a Logger instance for testing."""
        # Create a new Logger instance for each test
        with patch("acb.logger.Logger._configure_logger"):
            with patch("acb.logger.Logger._setup_level_colors"):
                with patch("acb.logger.Logger._log_debug_levels"):
                    with patch("acb.logger.Logger._log_app_info"):
                        return Logger()

    def test_logger_initialization(self, logger: Logger) -> None:
        """Test Logger initialization."""
        assert isinstance(logger, Logger)
        assert isinstance(logger, LoggerBase)

    def test_async_sink(self) -> None:
        """Test async_sink method."""
        # This is a static method, so we can call it directly
        with patch("acb.logger.aprint", new=AsyncMock()) as mock_aprint:
            import asyncio

            async def test_async_sink():
                await Logger.async_sink("Test message")
                mock_aprint.assert_called_once_with("Test message", end="")

            asyncio.run(test_async_sink())

    def test_is_testing_mode_pytest(self) -> None:
        """Test _is_testing_mode when pytest is active."""
        with patch("sys.modules", {"pytest": MagicMock()}):
            with patch("acb.logger.Logger._configure_logger"):
                with patch("acb.logger.Logger._setup_level_colors"):
                    with patch("acb.logger.Logger._log_debug_levels"):
                        with patch("acb.logger.Logger._log_app_info"):
                            logger = Logger()
                            assert logger._is_testing_mode() is True

    def test_is_testing_mode_env_var(self) -> None:
        """Test _is_testing_mode when TESTING env var is set."""
        with patch.dict("os.environ", {"TESTING": "True"}):
            with patch("acb.logger.Logger._configure_logger"):
                with patch("acb.logger.Logger._setup_level_colors"):
                    with patch("acb.logger.Logger._log_debug_levels"):
                        with patch("acb.logger.Logger._log_app_info"):
                            logger = Logger()
                            assert logger._is_testing_mode() is True

    def test_is_testing_mode_normal(self) -> None:
        """Test _is_testing_mode in normal mode."""
        with patch("sys.modules", {}):
            with patch.dict("os.environ", {}, clear=True):
                with patch("acb.logger.Logger._configure_logger"):
                    with patch("acb.logger.Logger._setup_level_colors"):
                        with patch("acb.logger.Logger._log_debug_levels"):
                            with patch("acb.logger.Logger._log_app_info"):
                                logger = Logger()
                                assert logger._is_testing_mode() is False

    def test_configure_for_testing(self, logger: Logger) -> None:
        """Test _configure_for_testing method."""
        with patch.object(logger, "remove") as mock_remove:
            with patch.object(logger, "configure") as mock_configure:
                logger._configure_for_testing()
                mock_remove.assert_called_once()
                mock_configure.assert_called_once_with(handlers=[])

    def test_patch_name(self, logger: Logger) -> None:
        """Test _patch_name method."""
        # Test with a simple module name
        record = {"name": "acb.module.submodule"}
        result = logger._patch_name(record)
        assert isinstance(result, str)

        # Test with a longer module name
        record = {"name": "acb.adapters.cache.redis"}
        result = logger._patch_name(record)
        assert isinstance(result, str)

    def test_filter_by_module(self, logger: Logger) -> None:
        """Test _filter_by_module method."""
        # Mock the config
        mock_config = MagicMock()
        mock_config.logger.log_level = "INFO"
        mock_config.logger.level_per_module = {}
        logger.config = mock_config

        # Mock the level method to return a level object with a 'no' attribute
        mock_level = MagicMock()
        mock_level.no = 20  # INFO level
        with patch.object(logger, "level", return_value=mock_level):
            # Test record that should pass filter
            record = {"name": "acb.test", "level": mock_level}
            result = logger._filter_by_module(record)
            assert isinstance(result, bool)

    def test_add_sync_sink(self, logger: Logger) -> None:
        """Test _add_sync_sink method."""
        with patch.object(logger, "add") as mock_add:
            with patch.object(logger.config.logger, "settings", {"enqueue": True}):
                logger._add_sync_sink()
                mock_add.assert_called_once()

    def test_log_debug_levels(self, logger: Logger) -> None:
        """Test _log_debug_levels method."""
        # Mock the config
        mock_config = MagicMock()
        mock_config.debug.logger = True
        logger.config = mock_config

        # Mock the logging methods
        with patch.object(logger, "debug") as mock_debug:
            with patch.object(logger, "info") as mock_info:
                with patch.object(logger, "warning") as mock_warning:
                    with patch.object(logger, "error") as mock_error:
                        with patch.object(logger, "critical") as mock_critical:
                            logger._log_debug_levels()
                            mock_debug.assert_called_once_with("debug")
                            mock_info.assert_called_once_with("info")
                            mock_warning.assert_called_once_with("warning")
                            mock_error.assert_called_once_with("error")
                            mock_critical.assert_called_once_with("critical")

    def test_log_app_info(self, logger: Logger) -> None:
        """Test _log_app_info method."""
        # Mock the config
        mock_config = MagicMock()
        mock_config.root_path = "/test/path"
        mock_config.deployed = False
        logger.config = mock_config

        # Mock the info method
        with patch.object(logger, "info") as mock_info:
            logger._log_app_info()
            assert mock_info.call_count == 2
            mock_info.assert_any_call("App path: /test/path")
            mock_info.assert_any_call("App deployed: False")

    def test_init_testing_mode(self, logger: Logger) -> None:
        """Test init method in testing mode."""
        with patch.object(logger, "_is_testing_mode", return_value=True):
            with patch.object(logger, "_configure_for_testing") as mock_configure:
                logger.init()
                mock_configure.assert_called_once()

    def test_init_normal_mode(self, logger: Logger) -> None:
        """Test init method in normal mode."""
        with patch.object(logger, "_is_testing_mode", return_value=False):
            with patch.object(logger, "_configure_logger") as mock_configure:
                with patch.object(logger, "_setup_level_colors") as mock_setup_colors:
                    with patch.object(logger, "_log_debug_levels") as mock_log_debug:
                        with patch.object(logger, "_log_app_info") as mock_log_app:
                            logger.init()
                            mock_configure.assert_called_once()
                            mock_setup_colors.assert_called_once()
                            mock_log_debug.assert_called_once()
                            mock_log_app.assert_called_once()


class TestInterceptHandler:
    """Test InterceptHandler class."""

    def test_intercept_handler_initialization(self) -> None:
        """Test InterceptHandler initialization."""
        handler = InterceptHandler()
        assert isinstance(handler, InterceptHandler)
        assert isinstance(handler, logging.Handler)

    @pytest.mark.skip(
        reason="Obsolete test - depends module not exposed via acb.logger anymore"
    )
    def test_emit_method(self) -> None:
        """Test InterceptHandler emit method."""
        handler = InterceptHandler()

        # Create a mock LogRecord
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Mock the logger dependency
        with patch("acb.logger.depends.get") as mock_depends_get:
            mock_logger = MagicMock()
            mock_level = MagicMock()
            mock_level.name = "INFO"
            mock_logger.level.return_value = mock_level
            mock_opt = MagicMock()
            mock_opt.log = MagicMock()
            mock_logger.opt.return_value = mock_opt
            mock_depends_get.return_value = mock_logger

            # Test that emit doesn't raise exceptions
            try:
                handler.emit(record)
            except Exception:
                pytest.fail("emit method should not raise exceptions")
