"""Tests for Loguru logger adapter."""

from unittest.mock import Mock, patch

import pytest

from acb.adapters import AdapterCapability, AdapterStatus
from acb.adapters.logger.loguru import (
    MODULE_METADATA,
    InterceptHandler,
    Logger,
    LoggerSettings,
)
from acb.config import Config


class TestLoggerSettings:
    """Test LoggerSettings configuration."""

    def test_default_settings(self):
        """Test default Logger settings."""
        settings = LoggerSettings()

        assert settings.backtrace is False
        assert settings.catch is False
        assert settings.diagnose is False
        assert settings.colorize is True

    def test_format_inheritance(self):
        """Test format inheritance from base."""
        settings = LoggerSettings()

        assert settings.format is not None
        assert "time" in settings.format
        assert "level" in settings.format

    def test_settings_building(self):
        """Test settings dict building."""
        settings = LoggerSettings()

        assert "format" in settings.settings
        assert "enqueue" in settings.settings
        assert "colorize" in settings.settings


class TestLoguruMetadata:
    """Test MODULE_METADATA for Loguru adapter."""

    def test_metadata_structure(self):
        """Test metadata has required fields."""
        assert MODULE_METADATA.name == "Loguru Logger"
        assert MODULE_METADATA.category == "logger"
        assert MODULE_METADATA.provider == "loguru"
        assert MODULE_METADATA.status == AdapterStatus.STABLE

    def test_metadata_capabilities(self):
        """Test metadata includes required capabilities."""
        capabilities = MODULE_METADATA.capabilities

        assert AdapterCapability.ASYNC_LOGGING in capabilities
        assert AdapterCapability.CONTEXTUAL in capabilities
        assert AdapterCapability.ROTATION in capabilities
        assert AdapterCapability.FILE_LOGGING in capabilities
        assert AdapterCapability.CORRELATION_ID in capabilities

    def test_metadata_packages(self):
        """Test required packages are listed."""
        packages = MODULE_METADATA.required_packages

        assert "loguru" in packages
        assert "aioconsole" in packages


class TestLoguruLogger:
    """Test Loguru Logger adapter."""

    def test_logger_initialization(self):
        """Test logger can be initialized."""
        logger = Logger()

        assert logger is not None
        assert hasattr(logger, "_bound_context")
        assert logger._bound_context == {}

    def test_settings_property(self):
        """Test settings property returns LoggerSettings."""
        logger = Logger()

        settings = logger.settings
        assert isinstance(settings, LoggerSettings)

    def test_context_binding(self):
        """Test context binding creates new logger instance."""
        logger = Logger()

        bound_logger = logger._bind(user_id="123")

        assert bound_logger is not logger
        assert bound_logger._bound_context == {"user_id": "123"}

    def test_correlation_id_binding(self):
        """Test correlation ID binding."""
        logger = Logger()

        corr_logger = logger._with_correlation_id("test-correlation-id")

        assert corr_logger._bound_context == {"correlation_id": "test-correlation-id"}

    @patch("sys.modules", {"pytest": Mock()})
    def test_init_testing_mode(self):
        """Test initialization in testing mode."""
        logger = Logger()

        with (
            patch.object(logger, "remove") as mock_remove,
            patch.object(logger, "configure") as mock_configure,
        ):
            logger._init()

            mock_remove.assert_called_once()
            mock_configure.assert_called_once_with(handlers=[])

    def test_init_normal_mode(self):
        """Test initialization in normal mode."""
        logger = Logger()

        with (
            patch.object(logger, "_is_testing_mode", return_value=False),
            patch.object(logger, "_configure_logger") as mock_configure,
            patch.object(logger, "_setup_level_colors") as mock_colors,
            patch.object(logger, "_log_debug_levels") as mock_debug,
            patch.object(logger, "_log_app_info") as mock_info,
        ):
            logger._init()

            mock_configure.assert_called_once()
            mock_colors.assert_called_once()
            mock_debug.assert_called_once()
            mock_info.assert_called_once()

    def test_patch_name(self):
        """Test module name patching."""
        logger = Logger()

        record = {"name": "acb.adapters.logger.test"}
        result = logger._patch_name(record)

        assert result == "acb.adapters.logger"

    def test_filter_by_module(self, mock_config):
        """Test module-based filtering."""
        from acb.depends import depends

        # Register mock config in DI so property can access it
        depends.set(Config, mock_config)

        logger = Logger()

        # Create mock level with proper name attribute
        mock_level = Mock()
        mock_level.name = "INFO"

        record = {"name": "test.module.function", "level": mock_level}

        result = logger._filter_by_module(record)

        assert result is True

    @pytest.mark.asyncio
    async def test_async_sink(self):
        """Test async sink functionality."""
        with patch("acb.adapters.logger.loguru.aprint") as mock_aprint:
            await Logger.async_sink("test message")

            mock_aprint.assert_called_once_with("test message", end="")

    def test_add_primary_sink_success(self):
        """Test successful primary sink addition."""
        logger = Logger()

        with patch.object(logger, "add") as mock_add:
            logger._add_primary_sink()

            mock_add.assert_called_once()

    def test_add_primary_sink_fallback(self):
        """Test fallback to sync sink on event loop error."""
        logger = Logger()

        with (
            patch.object(
                logger, "add", side_effect=ValueError("event loop is required")
            ),
            patch.object(logger, "_add_sync_sink") as mock_sync,
        ):
            logger._add_primary_sink()

            mock_sync.assert_called_once()

    def test_add_primary_sink_other_error(self):
        """Test other ValueError is re-raised."""
        logger = Logger()

        with patch.object(logger, "add", side_effect=ValueError("other error")):
            with pytest.raises(ValueError, match="other error"):
                logger._add_primary_sink()

    def test_add_sync_sink(self):
        """Test sync sink addition."""
        logger = Logger()
        logger.settings.settings = {"enqueue": True, "format": "test"}

        with patch.object(logger, "add") as mock_add:
            logger._add_sync_sink()

            mock_add.assert_called_once()
            # Check that enqueue was removed from settings
            call_args = mock_add.call_args
            assert "enqueue" not in call_args[1]
            assert "format" in call_args[1]

    def test_setup_level_colors(self):
        """Test level color setup."""
        logger = Logger()
        logger.settings.level_colors = {"INFO": "blue", "ERROR": "red"}

        with patch.object(logger, "level") as mock_level:
            logger._setup_level_colors()

            assert mock_level.call_count == 2

    def test_log_debug_levels(self, mock_config):
        """Test debug level logging."""
        from acb.depends import depends

        # Register mock config in DI so property can access it
        depends.set(Config, mock_config)
        mock_config.debug.logger = True

        logger = Logger()

        with (
            patch.object(logger, "debug") as mock_debug,
            patch.object(logger, "info") as mock_info,
            patch.object(logger, "warning") as mock_warning,
            patch.object(logger, "error") as mock_error,
            patch.object(logger, "critical") as mock_critical,
        ):
            logger._log_debug_levels()

            mock_debug.assert_called_once_with("debug")
            mock_info.assert_called_once_with("info")
            mock_warning.assert_called_once_with("warning")
            mock_error.assert_called_once_with("error")
            mock_critical.assert_called_once_with("critical")

    def test_log_app_info(self, mock_config):
        """Test application info logging."""
        from acb.depends import depends

        # Register mock config in DI so property can access it
        depends.set(Config, mock_config)
        mock_config.deployed = True

        logger = Logger()

        with patch.object(logger, "info") as mock_info:
            logger._log_app_info()

            assert mock_info.call_count == 2


class TestLoguruStructuredLogging:
    """Test Loguru structured logging features."""

    def test_log_structured(self):
        """Test structured logging implementation."""
        logger = Logger()

        with patch.object(logger, "bind") as mock_bind:
            mock_bound_logger = Mock()
            mock_bind.return_value = mock_bound_logger

            logger._log_structured("info", "test message", user_id="123")

            mock_bind.assert_called_once_with(user_id="123")
            mock_bound_logger.log.assert_called_once_with("INFO", "test message")

    def test_log_structured_with_existing_context(self):
        """Test structured logging with existing bound context."""
        logger = Logger()
        logger._bound_context = {"session": "abc"}

        with patch.object(logger, "bind") as mock_bind:
            mock_bound_logger = Mock()
            mock_bind.return_value = mock_bound_logger

            logger._log_structured("error", "test error", error_code="E001")

            mock_bind.assert_called_once_with(session="abc", error_code="E001")


class TestInterceptHandler:
    """Test InterceptHandler for stdlib logging integration."""

    def test_emit_with_loguru_logger(self):
        """Test emit with Loguru-style logger."""
        handler = InterceptHandler()

        mock_logger = Mock()
        mock_logger.level.return_value.name = "INFO"
        mock_opt = Mock()
        mock_logger.opt.return_value = mock_opt

        record = Mock()
        record.levelname = "INFO"
        record.exc_info = None
        record.getMessage.return_value = "test message"

        with (
            patch("acb.adapters.logger.loguru.currentframe"),
            patch(
                "acb.adapters.logger.loguru.depends.get_sync", return_value=mock_logger
            ),
        ):
            handler.emit(record)

            mock_logger.level.assert_called_once_with("INFO")
            mock_logger.opt.assert_called_once()
            mock_opt.log.assert_called_once_with("INFO", "test message")

    def test_emit_with_basic_logger(self):
        """Test emit with basic logger (no opt method)."""
        handler = InterceptHandler()

        mock_logger = Mock()
        mock_logger.level.return_value.name = "INFO"
        # Remove opt method to simulate basic logger
        del mock_logger.opt

        record = Mock()
        record.levelname = "INFO"
        record.exc_info = None
        record.getMessage.return_value = "test message"

        with (
            patch("acb.adapters.logger.loguru.currentframe"),
            patch(
                "acb.adapters.logger.loguru.depends.get_sync", return_value=mock_logger
            ),
        ):
            # Should raise AttributeError when trying to call opt()
            with pytest.raises(AttributeError):
                handler.emit(record)

    def test_emit_level_error(self):
        """Test emit when level method raises ValueError."""
        handler = InterceptHandler()

        mock_logger = Mock()
        mock_logger.level.side_effect = ValueError("invalid level")
        mock_opt = Mock()
        mock_logger.opt.return_value = mock_opt

        record = Mock()
        record.levelname = "INVALID"
        record.levelno = 20
        record.exc_info = None
        record.getMessage.return_value = "test message"

        with (
            patch("acb.adapters.logger.loguru.currentframe"),
            patch(
                "acb.adapters.logger.loguru.depends.get_sync", return_value=mock_logger
            ),
        ):
            handler.emit(record)

            mock_opt.log.assert_called_once_with(20, "test message")


@pytest.mark.integration
class TestLoguruIntegration:
    """Integration tests for Loguru adapter."""

    def test_logger_creation_and_basic_usage(self):
        """Test creating logger and basic logging operations."""
        logger = Logger()

        # Should be able to call basic methods without error
        # Note: In testing mode, these won't actually log
        logger.init()

        # Test method calls don't raise exceptions
        try:
            logger.debug("test debug")
            logger.info("test info")
            logger.warning("test warning")
            logger.error("test error")
            logger.critical("test critical")
        except Exception as e:
            pytest.fail(f"Basic logging operations failed: {e}")

    def test_context_operations(self):
        """Test context binding operations."""
        logger = Logger()
        logger.init()

        # Test context binding
        bound_logger = logger.bind(user_id="test123")
        assert bound_logger is not logger

        # Test correlation ID
        corr_logger = logger.with_correlation_id("test-corr-id")
        assert corr_logger._bound_context["correlation_id"] == "test-corr-id"

    @pytest.mark.skip(reason="Requires full app initialization (not pytest mode)")
    def test_with_real_dependencies(self):
        """Test logger with real ACB dependencies."""
        from acb.config import Config
        from acb.depends import depends

        # Ensure real config is available in DI system
        try:
            config = depends.get_sync(Config)
        except Exception:
            # If config not in DI, create and register it
            config = Config()
            depends.set(Config, config)

        # This should work with the real dependency system
        logger = Logger()

        # Config should be available through depends
        logger_config = logger.config
        assert isinstance(logger_config, Config)
