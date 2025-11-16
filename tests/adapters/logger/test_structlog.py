"""Tests for Structlog logger adapter."""

from unittest.mock import Mock, patch

import pytest

from acb.adapters import AdapterCapability, AdapterStatus
from acb.adapters.logger.structlog import MODULE_METADATA, Logger, LoggerSettings

# Mock structlog if not available
try:
    import structlog
except ImportError:
    structlog = None


class TestLoggerSettings:
    """Test LoggerSettings configuration."""

    def test_default_settings(self):
        """Test default Structlog settings."""
        settings = LoggerSettings()

        assert settings.json_output is True
        assert settings.include_metadata is True
        assert settings.include_caller_info is True
        assert settings.pretty_print is False
        assert settings.add_log_level is True
        assert settings.add_timestamp is True
        assert settings.context_vars is True

    def test_processor_configuration(self):
        """Test processor configuration."""
        settings = LoggerSettings(
            add_timestamp=False, context_vars=False, include_caller_info=False
        )

        assert settings.add_timestamp is False
        assert settings.context_vars is False
        assert settings.include_caller_info is False

    def test_renderer_configuration(self):
        """Test renderer configuration for dev vs prod."""
        settings = LoggerSettings(dev_renderer="console", prod_renderer="json")

        assert settings.dev_renderer == "console"
        assert settings.prod_renderer == "json"

    @pytest.mark.skipif(structlog is None, reason="structlog not available")
    def test_build_processors_json_output(self):
        """Test processor building for JSON output."""
        settings = LoggerSettings(json_output=True)

        processors = settings._build_processors()

        assert len(processors) > 0
        # Should include JSON renderer for JSON output
        assert any(
            isinstance(p, type(structlog.processors.JSONRenderer()))
            for p in processors
            if hasattr(p, "__class__")
        )

    @pytest.mark.skipif(structlog is None, reason="structlog not available")
    def test_build_processors_console_output(self):
        """Test processor building for console output."""
        settings = LoggerSettings(json_output=False, pretty_print=True)

        processors = settings._build_processors()

        assert len(processors) > 0

    @pytest.mark.skipif(structlog is None, reason="structlog not available")
    def test_structlog_settings_building(self):
        """Test structlog-specific settings building."""
        settings = LoggerSettings()

        structlog_settings = settings.settings

        assert "processors" in structlog_settings
        assert "wrapper_class" in structlog_settings
        assert "context_class" in structlog_settings
        assert "logger_factory" in structlog_settings

    def test_build_processors_no_structlog(self):
        """Test processor building when structlog is not available."""
        with patch("acb.adapters.logger.structlog.structlog", None):
            settings = LoggerSettings()

            processors = settings._build_processors()

            assert processors == []


class TestStructlogMetadata:
    """Test MODULE_METADATA for Structlog adapter."""

    def test_metadata_structure(self):
        """Test metadata has required fields."""
        assert MODULE_METADATA.name == "Structlog Logger"
        assert MODULE_METADATA.category == "logger"
        assert MODULE_METADATA.provider == "structlog"
        assert MODULE_METADATA.status == AdapterStatus.STABLE

    def test_metadata_capabilities(self):
        """Test metadata includes structured logging capabilities."""
        capabilities = MODULE_METADATA.capabilities

        assert AdapterCapability.STRUCTURED_OUTPUT in capabilities
        assert AdapterCapability.ASYNC_LOGGING in capabilities
        assert AdapterCapability.CONTEXTUAL in capabilities
        assert AdapterCapability.JSON_OUTPUT in capabilities
        assert AdapterCapability.FILE_LOGGING in capabilities
        assert AdapterCapability.CORRELATION_ID in capabilities
        assert AdapterCapability.REMOTE_LOGGING in capabilities

    def test_metadata_packages(self):
        """Test required packages are listed."""
        packages = MODULE_METADATA.required_packages

        assert "structlog" in packages


class TestStructlogLogger:
    """Test Structlog Logger adapter."""

    @pytest.mark.skipif(structlog is None, reason="structlog not available")
    def test_logger_initialization(self):
        """Test logger can be initialized when structlog is available."""
        logger = Logger()

        assert logger is not None
        assert hasattr(logger, "_logger")
        assert hasattr(logger, "_bound_context")
        assert logger._bound_context == {}

    def test_logger_initialization_no_structlog(self):
        """Test logger raises ImportError when structlog is not available."""
        with patch("acb.adapters.logger.structlog.structlog", None):
            with pytest.raises(ImportError, match="structlog is required"):
                Logger()

    @pytest.mark.skipif(structlog is None, reason="structlog not available")
    def test_settings_property(self):
        """Test settings property returns LoggerSettings."""
        logger = Logger()

        settings = logger.settings
        assert isinstance(settings, LoggerSettings)

    @pytest.mark.skipif(structlog is None, reason="structlog not available")
    def test_ensure_logger(self):
        """Test logger creation and caching."""
        logger = Logger()

        with patch(
            "acb.adapters.logger.structlog.structlog.get_logger"
        ) as mock_get_logger:
            mock_structlog_logger = Mock()
            mock_get_logger.return_value = mock_structlog_logger

            # First call should create logger
            result1 = logger._ensure_logger()
            assert result1 is mock_structlog_logger
            mock_get_logger.assert_called_once()

            # Second call should return cached logger
            result2 = logger._ensure_logger()
            assert result2 is mock_structlog_logger
            # get_logger should still only be called once
            assert mock_get_logger.call_count == 1

    @pytest.mark.skipif(structlog is None, reason="structlog not available")
    def test_logging_methods(self):
        """Test basic logging methods."""
        logger = Logger()

        with (
            patch.object(logger, "_ensure_logger") as mock_ensure,
            patch.object(logger, "_log_with_context") as mock_log_context,
        ):
            mock_structlog_logger = Mock()
            mock_ensure.return_value = mock_structlog_logger

            logger._debug("debug message", extra_arg="value")
            logger._info("info message")
            logger._warning("warning message")
            logger._error("error message")
            logger._critical("critical message")

            assert mock_log_context.call_count == 5

    @pytest.mark.skipif(structlog is None, reason="structlog not available")
    def test_structured_logging(self):
        """Test structured logging implementation."""
        logger = Logger()
        logger._bound_context = {"session": "abc123"}

        with patch.object(logger, "_ensure_logger") as mock_ensure:
            mock_structlog_logger = Mock()
            mock_structlog_logger.info = Mock()
            mock_ensure.return_value = mock_structlog_logger

            logger._log_structured(
                "info", "test message", user_id="456", action="login"
            )

            mock_structlog_logger.info.assert_called_once_with(
                "test message", session="abc123", user_id="456", action="login"
            )

    @pytest.mark.skipif(structlog is None, reason="structlog not available")
    def test_context_binding(self):
        """Test context binding creates new logger instance."""
        logger = Logger()
        logger._bound_context = {"existing": "context"}

        with patch.object(logger, "_ensure_logger") as mock_ensure:
            mock_structlog_logger = Mock()
            mock_bound_logger = Mock()
            mock_structlog_logger.bind.return_value = mock_bound_logger
            mock_ensure.return_value = mock_structlog_logger

            bound_logger = logger._bind(user_id="123", action="test")

            assert bound_logger is not logger
            assert bound_logger._bound_context == {
                "existing": "context",
                "user_id": "123",
                "action": "test",
            }
            mock_structlog_logger.bind.assert_called_once_with(
                user_id="123", action="test"
            )

    @pytest.mark.skipif(structlog is None, reason="structlog not available")
    def test_correlation_id_binding(self):
        """Test correlation ID binding."""
        logger = Logger()

        with patch.object(logger, "_bind") as mock_bind:
            logger._with_correlation_id("test-correlation-id")

            mock_bind.assert_called_once_with(correlation_id="test-correlation-id")

    @pytest.mark.skipif(structlog is None, reason="structlog not available")
    def test_log_with_context(self):
        """Test log_with_context method."""
        logger = Logger()
        logger._bound_context = {"session": "test"}

        mock_log_method = Mock()

        with patch("acb.adapters.logger.structlog.sys._getframe") as mock_frame:
            mock_frame_obj = Mock()
            mock_frame_obj.f_globals = {"__name__": "test.module"}
            mock_frame_obj.f_code.co_name = "test_function"
            mock_frame_obj.f_lineno = 42
            mock_frame.return_value = mock_frame_obj

            logger._log_with_context(
                mock_log_method,
                "test message %s",
                "arg1",
                extra={"request_id": "req123"},
            )

            mock_log_method.assert_called_once()
            call_args = mock_log_method.call_args
            assert (
                call_args[0][0] == "test message arg1"
            )  # Message is formatted with args
            # Check context includes session, extra, and module info
            context = call_args[1]
            assert "session" in context
            assert "request_id" in context
            assert "module" in context
            assert "function" in context
            assert "line" in context

    @pytest.mark.skipif(structlog is None, reason="structlog not available")
    def test_init_testing_mode(self):
        """Test initialization in testing mode."""
        logger = Logger()

        with (
            patch.object(logger, "_is_testing_mode", return_value=True),
            patch.object(logger, "_configure_for_testing") as mock_configure,
        ):
            logger._init()

            mock_configure.assert_called_once()

    @pytest.mark.skipif(structlog is None, reason="structlog not available")
    def test_init_normal_mode(self):
        """Test initialization in normal mode."""
        logger = Logger()

        with (
            patch.object(logger, "_is_testing_mode", return_value=False),
            patch.object(logger, "_configure_structlog") as mock_configure,
            patch.object(logger, "_setup_stdlib_integration") as mock_stdlib,
            patch.object(logger, "_log_app_info") as mock_info,
        ):
            logger._init()

            mock_configure.assert_called_once()
            mock_stdlib.assert_called_once()
            mock_info.assert_called_once()

    @pytest.mark.skipif(structlog is None, reason="structlog not available")
    def test_configure_for_testing(self):
        """Test testing configuration."""
        logger = Logger()

        with patch(
            "acb.adapters.logger.structlog.structlog.configure"
        ) as mock_configure:
            logger._configure_for_testing()

            mock_configure.assert_called_once()

    @pytest.mark.skipif(structlog is None, reason="structlog not available")
    def test_configure_structlog(self):
        """Test structlog configuration."""
        logger = Logger()

        with (
            patch(
                "acb.adapters.logger.structlog.structlog.configure"
            ) as mock_configure,
            patch(
                "acb.adapters.logger.structlog.structlog.contextvars.clear_contextvars"
            ) as mock_clear,
        ):
            logger._configure_structlog()

            mock_configure.assert_called_once()
            mock_clear.assert_called_once()

    @pytest.mark.skipif(structlog is None, reason="structlog not available")
    def test_setup_stdlib_integration(self, mock_config):
        """Test stdlib logging integration setup."""
        from acb.config import Config
        from acb.depends import depends

        # Register mock config in DI so property can access it
        depends.set(Config, mock_config)

        logger = Logger()

        with (
            patch(
                "acb.adapters.logger.structlog.logging.basicConfig"
            ) as mock_basic_config,
            patch(
                "acb.adapters.logger.structlog.structlog.stdlib.recreate_defaults"
            ) as mock_recreate,
        ):
            logger._setup_stdlib_integration()

            mock_basic_config.assert_called_once()
            mock_recreate.assert_called_once()

    @pytest.mark.skipif(structlog is None, reason="structlog not available")
    def test_additional_methods(self):
        """Test additional structured logging methods."""
        logger = Logger()

        with patch.object(logger, "_ensure_logger") as mock_ensure:
            mock_structlog_logger = Mock()
            mock_ensure.return_value = mock_structlog_logger

            # Test log_event
            logger.log_event("user_login", user_id="123")
            mock_structlog_logger.info.assert_called()

            # Test log_metric
            logger.log_metric("response_time", 150.5, endpoint="/api/users")
            assert mock_structlog_logger.info.call_count >= 2

            # Test log_performance
            logger.log_performance("database_query", 45.2, table="users")
            assert mock_structlog_logger.info.call_count >= 3

            # Test log_error_with_context
            test_error = ValueError("test error")
            logger.log_error_with_context(test_error, request_id="req123")
            mock_structlog_logger.error.assert_called()


@pytest.mark.integration
@pytest.mark.skipif(structlog is None, reason="structlog not available")
class TestStructlogIntegration:
    """Integration tests for Structlog adapter."""

    def test_logger_creation_and_basic_usage(self):
        """Test creating logger and basic logging operations."""
        logger = Logger()

        # Should be able to call basic methods without error
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

    def test_structured_logging_operations(self):
        """Test structured logging operations."""
        logger = Logger()
        logger.init()

        try:
            logger.log_structured("info", "test message", user_id="123")
            logger.log_event("test_event", action="testing")
            logger.log_metric("test_metric", 42.0, component="test")
            logger.log_performance("test_operation", 100.0, category="test")

            test_error = RuntimeError("test error")
            logger.log_error_with_context(test_error, context="testing")
        except Exception as e:
            pytest.fail(f"Structured logging operations failed: {e}")

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


class TestStructlogWithoutImport:
    """Test behavior when structlog is not available."""

    def test_import_error_on_initialization(self):
        """Test ImportError is raised when structlog is not available."""
        with patch("acb.adapters.logger.structlog.structlog", None):
            with pytest.raises(ImportError, match="structlog is required"):
                Logger()

    def test_settings_work_without_structlog(self):
        """Test settings can be created even without structlog."""
        with patch("acb.adapters.logger.structlog.structlog", None):
            # Settings should still be creatable
            settings = LoggerSettings()
            assert isinstance(settings, LoggerSettings)

            # But processors should be empty
            processors = settings._build_processors()
            assert processors == []
