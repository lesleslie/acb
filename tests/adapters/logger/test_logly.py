"""Tests for Logly logger adapter."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from acb.adapters import AdapterCapability, AdapterStatus


# Mock logly module before importing the adapter
@pytest.fixture(autouse=True)
def mock_logly():
    """Mock the logly module for testing."""
    mock_logger = MagicMock()
    mock_logger.debug = Mock()
    mock_logger.info = Mock()
    mock_logger.warning = Mock()
    mock_logger.error = Mock()
    mock_logger.critical = Mock()
    mock_logger.log = Mock()
    mock_logger.bind = Mock(return_value=mock_logger)
    mock_logger.add = Mock()
    mock_logger.remove = Mock()
    mock_logger.configure = Mock()
    mock_logger.add_callback = Mock()
    mock_logger.remove_callback = Mock()
    # Make contextualize return a context manager mock
    mock_context = MagicMock()
    mock_context.__enter__ = Mock(return_value=mock_context)
    mock_context.__exit__ = Mock(return_value=False)
    mock_logger.contextualize = Mock(return_value=mock_context)
    mock_logger.complete = Mock()
    mock_logger.trace = Mock()
    mock_logger.success = Mock()

    with patch.dict("sys.modules", {"logly": MagicMock(logger=mock_logger)}):
        yield mock_logger


@pytest.fixture
def mock_config():
    """Create a mock config for testing."""
    config = Mock()
    config.deployed = False
    config.debug = Mock(production=False, logger=False)
    config.root_path = "/test/path"
    config.logger = Mock()
    config.logger.log_level = "INFO"
    config.logger.level_per_module = {}
    return config


class TestLoglySettings:
    """Test LoglySettings configuration."""

    def test_default_settings(self):
        """Test default Logly settings."""
        from acb.adapters.logger.logly import LoglySettings

        settings = LoglySettings()

        assert settings.rust_optimized is True
        assert settings.thread_safe is True
        assert settings.lock_free is True
        assert settings.compression is None
        assert settings.compression_level == 6

    def test_compression_settings(self):
        """Test compression configuration."""
        from acb.adapters.logger.logly import LoglySettings

        settings = LoglySettings(compression="zstd", compression_level=9)

        assert settings.compression == "zstd"
        assert settings.compression_level == 9

    def test_callback_configuration(self):
        """Test callback settings."""
        from acb.adapters.logger.logly import LoglySettings

        settings = LoglySettings(
            enable_callbacks=True,
            callback_async=True,
            callback_on_levels=["ERROR", "CRITICAL"],
        )

        assert settings.enable_callbacks is True
        assert settings.callback_async is True
        assert settings.callback_on_levels == ["ERROR", "CRITICAL"]

    def test_rotation_settings(self):
        """Test rotation configuration."""
        from acb.adapters.logger.logly import LoglySettings

        settings = LoglySettings(
            rotation_policy="both", rotation_size="50 MB", rotation_time="12 hours"
        )

        assert settings.rotation_policy == "both"
        assert settings.rotation_size == "50 MB"
        assert settings.rotation_time == "12 hours"

    def test_format_inheritance(self):
        """Test format inheritance from base."""
        from acb.adapters.logger.logly import LoglySettings

        settings = LoglySettings()

        assert settings.format is not None
        assert "time" in settings.format
        assert "level" in settings.format

    def test_settings_building(self):
        """Test settings dict building."""
        from acb.adapters.logger.logly import LoglySettings

        settings = LoglySettings()

        assert "format" in settings.settings
        assert "enqueue" in settings.settings
        assert "colorize" in settings.settings
        assert "compression" in settings.settings

    def test_rust_optimization_settings(self):
        """Test Rust optimization flags."""
        from acb.adapters.logger.logly import LoglySettings

        settings = LoglySettings(
            rust_optimized=False, thread_safe=False, lock_free=False
        )

        assert settings.rust_optimized is False
        assert settings.thread_safe is False
        assert settings.lock_free is False


class TestLoglyMetadata:
    """Test MODULE_METADATA for Logly adapter."""

    def test_metadata_structure(self):
        """Test metadata has required fields."""
        from acb.adapters.logger.logly import MODULE_METADATA

        assert MODULE_METADATA.name == "Logly Logger"
        assert MODULE_METADATA.category == "logger"
        assert MODULE_METADATA.provider == "logly"
        assert MODULE_METADATA.status == AdapterStatus.STABLE

    def test_metadata_capabilities(self):
        """Test metadata includes required capabilities."""
        from acb.adapters.logger.logly import MODULE_METADATA

        capabilities = MODULE_METADATA.capabilities

        assert AdapterCapability.ASYNC_LOGGING in capabilities
        assert AdapterCapability.CONTEXTUAL in capabilities
        assert AdapterCapability.ROTATION in capabilities
        assert AdapterCapability.FILE_LOGGING in capabilities
        assert AdapterCapability.CORRELATION_ID in capabilities
        assert AdapterCapability.COMPRESSION in capabilities  # Logly-specific

    def test_metadata_packages(self):
        """Test required packages are listed."""
        from acb.adapters.logger.logly import MODULE_METADATA

        packages = MODULE_METADATA.required_packages

        assert "logly>=0.1.0" in packages

    def test_metadata_optional_packages(self):
        """Test optional packages for compression."""
        from acb.adapters.logger.logly import MODULE_METADATA

        optional = MODULE_METADATA.optional_packages

        assert "zstd" in optional
        assert "zstandard" in optional["zstd"]


class TestLoglyLogger:
    """Test Logly Logger adapter."""

    def test_logger_initialization(self, mock_logly):
        """Test logger can be initialized."""
        from acb.adapters.logger.logly import Logger

        logger = Logger()

        assert logger is not None
        assert hasattr(logger, "_bound_context")
        assert logger._bound_context == {}
        assert hasattr(logger, "_callbacks")
        assert logger._callbacks == []

    def test_settings_property(self):
        """Test settings property returns LoglySettings."""
        from acb.adapters.logger.logly import Logger, LoglySettings

        logger = Logger()

        settings = logger.settings
        assert isinstance(settings, LoglySettings)

    def test_ensure_logger_lazy_init(self, mock_logly):
        """Test logger is lazily initialized."""
        from acb.adapters.logger.logly import Logger

        logger = Logger()
        assert logger._logger is None

        # Access _ensure_logger should initialize
        result = logger._ensure_logger()
        assert result is not None

    def test_context_binding(self, mock_logly):
        """Test context binding creates new logger instance."""
        from acb.adapters.logger.logly import Logger

        logger = Logger()

        bound_logger = logger._bind(user_id="123")

        assert bound_logger is not logger
        assert bound_logger._bound_context == {"user_id": "123"}

    def test_correlation_id_binding(self, mock_logly):
        """Test correlation ID binding."""
        from acb.adapters.logger.logly import Logger

        logger = Logger()

        corr_logger = logger._with_correlation_id("test-correlation-id")

        assert corr_logger._bound_context == {"correlation_id": "test-correlation-id"}

    def test_init_testing_mode(self, mock_logly, mock_config):
        """Test initialization in testing mode."""
        from acb.adapters.logger.logly import Logger
        from acb.config import Config
        from acb.depends import depends

        # Register mock config in DI so property can access it
        depends.set(Config, mock_config)

        logger = Logger()

        with patch.object(logger, "_is_testing_mode", return_value=True):
            logger._init()

            # Verify testing mode configuration was called
            mock_logly.remove.assert_called_once()
            mock_logly.configure.assert_called_once_with(handlers=[])

    def test_init_normal_mode(self, mock_logly, mock_config):
        """Test initialization in normal mode."""
        from acb.adapters.logger.logly import Logger
        from acb.config import Config
        from acb.depends import depends

        # Register mock config in DI so property can access it
        depends.set(Config, mock_config)

        logger = Logger()

        with patch.object(logger, "_is_testing_mode", return_value=False):
            logger._init()

            # Verify normal mode configuration
            assert mock_logly.remove.called

    def test_logging_methods(self, mock_logly):
        """Test all basic logging methods."""
        from acb.adapters.logger.logly import Logger

        logger = Logger()

        logger._debug("debug message")
        logger._info("info message")
        logger._warning("warning message")
        logger._error("error message")
        logger._critical("critical message")

        mock_logly.debug.assert_called_once_with("debug message")
        mock_logly.info.assert_called_once_with("info message")
        mock_logly.warning.assert_called_once_with("warning message")
        mock_logly.error.assert_called_once_with("error message")
        mock_logly.critical.assert_called_once_with("critical message")


class TestLoglyStructuredLogging:
    """Test Logly structured logging features."""

    def test_log_structured(self, mock_logly):
        """Test structured logging implementation."""
        from acb.adapters.logger.logly import Logger

        logger = Logger()

        logger._log_structured("info", "test message", user_id="123")

        # Verify bind was called with context
        mock_logly.bind.assert_called_once_with(user_id="123")

    def test_log_structured_with_existing_context(self, mock_logly):
        """Test structured logging with existing bound context."""
        from acb.adapters.logger.logly import Logger

        logger = Logger()
        logger._bound_context = {"session": "abc"}

        logger._log_structured("error", "test error", error_code="E001")

        # Verify context was merged
        mock_logly.bind.assert_called_once_with(session="abc", error_code="E001")


class TestLoglyCallbacks:
    """Test Logly callback functionality."""

    def test_add_callback(self, mock_logly):
        """Test adding a callback."""
        from acb.adapters.logger.logly import Logger

        logger = Logger()
        callback = Mock()

        logger.add_callback(callback)

        assert callback in logger._callbacks
        mock_logly.add_callback.assert_called_once_with(callback)

    def test_remove_callback(self, mock_logly):
        """Test removing a callback."""
        from acb.adapters.logger.logly import Logger

        logger = Logger()
        callback = Mock()

        logger.add_callback(callback)
        logger.remove_callback(callback)

        assert callback not in logger._callbacks
        mock_logly.remove_callback.assert_called_once_with(callback)

    def test_callback_not_supported_gracefully(self, mock_logly):
        """Test graceful handling when callbacks not supported."""
        from acb.adapters.logger.logly import Logger

        # Remove add_callback method to simulate unsupported feature
        del mock_logly.add_callback

        logger = Logger()
        callback = Mock()

        # Should not raise an exception
        logger.add_callback(callback)
        assert callback in logger._callbacks


class TestLoglyContextualize:
    """Test Logly contextualize context manager."""

    def test_contextualize(self, mock_logly):
        """Test contextualize context manager."""
        from acb.adapters.logger.logly import Logger

        logger = Logger()

        logger.contextualize(request_id="123")

        mock_logly.contextualize.assert_called_once_with(request_id="123")

    def test_contextualize_fallback(self, mock_logly):
        """Test contextualize falls back to bind if not supported."""
        from acb.adapters.logger.logly import Logger

        # Remove contextualize method to simulate unsupported feature
        del mock_logly.contextualize

        logger = Logger()

        result = logger.contextualize(request_id="123")

        # Should fall back to bind
        assert result._bound_context == {"request_id": "123"}


class TestLoglyCompression:
    """Test Logly compression features."""

    def test_compression_in_settings(self):
        """Test compression configuration in settings."""
        from acb.adapters.logger.logly import LoglySettings

        settings = LoglySettings(compression="gzip", compression_level=9)

        assert "compression" in settings.settings
        assert settings.settings["compression"] == "gzip"
        assert settings.settings["compression_level"] == 9

    def test_zstd_compression(self):
        """Test zstd compression configuration."""
        from acb.adapters.logger.logly import LoglySettings

        settings = LoglySettings(compression="zstd", compression_level=15)

        assert settings.compression == "zstd"
        assert settings.compression_level == 15


class TestLoglyComplete:
    """Test Logly complete/flush functionality."""

    def test_complete(self, mock_logly):
        """Test complete method flushes logs."""
        from acb.adapters.logger.logly import Logger

        logger = Logger()

        logger.complete()

        mock_logly.complete.assert_called_once()

    def test_complete_fallback_to_flush(self, mock_logly):
        """Test complete falls back to flush if not supported."""
        from acb.adapters.logger.logly import Logger

        # Remove complete method but add flush
        del mock_logly.complete
        mock_logly.flush = Mock()

        logger = Logger()
        logger.complete()

        # Should fall back to flush
        mock_logly.flush.assert_called_once()

    def test_complete_no_method_available(self, mock_logly):
        """Test complete handles missing methods gracefully."""
        from acb.adapters.logger.logly import Logger

        # Remove both complete and flush
        del mock_logly.complete

        logger = Logger()

        # Should not raise an exception
        logger.complete()


class TestLoglyExtendedLevels:
    """Test Logly extended log levels (trace, success)."""

    def test_trace(self, mock_logly):
        """Test trace logging level."""
        from acb.adapters.logger.logly import Logger

        logger = Logger()

        logger.trace("trace message")

        mock_logly.trace.assert_called_once_with("trace message")

    def test_trace_fallback(self, mock_logly):
        """Test trace falls back to debug if not supported."""
        from acb.adapters.logger.logly import Logger

        # Remove trace method
        del mock_logly.trace

        logger = Logger()
        logger.trace("trace message")

        # Should fall back to debug with [TRACE] prefix
        mock_logly.debug.assert_called_once()
        assert "[TRACE]" in str(mock_logly.debug.call_args)

    def test_success(self, mock_logly):
        """Test success logging level."""
        from acb.adapters.logger.logly import Logger

        logger = Logger()

        logger.success("success message")

        mock_logly.success.assert_called_once_with("success message")

    def test_success_fallback(self, mock_logly):
        """Test success falls back to info if not supported."""
        from acb.adapters.logger.logly import Logger

        # Remove success method
        del mock_logly.success

        logger = Logger()
        logger.success("success message")

        # Should fall back to info with checkmark
        mock_logly.info.assert_called_once()


class TestLoglyCleanup:
    """Test Logly cleanup and resource management."""

    @pytest.mark.asyncio
    async def test_cleanup_resources(self, mock_logly):
        """Test cleanup flushes logs."""
        from acb.adapters.logger.logly import Logger

        logger = Logger()

        with patch.object(logger, "complete") as mock_complete:
            await logger._cleanup_resources()

            mock_complete.assert_called_once()


class TestInterceptHandler:
    """Test InterceptHandler for stdlib logging integration."""

    def test_emit_with_logly_logger(self, mock_logly):
        """Test emit with Logly logger."""
        from acb.adapters.logger.logly import InterceptHandler, Logger

        handler = InterceptHandler()

        mock_logger = Mock(spec=Logger)
        mock_logger.log = Mock()

        record = Mock()
        record.levelname = "INFO"
        record.getMessage.return_value = "test message"

        with (
            patch("acb.adapters.logger.logly.currentframe"),
            patch(
                "acb.adapters.logger.logly.depends.get_sync", return_value=mock_logger
            ),
        ):
            handler.emit(record)

            mock_logger.log.assert_called_once_with("INFO", "test message")

    def test_emit_exception_handling(self, mock_logly):
        """Test emit handles exceptions gracefully."""
        from acb.adapters.logger.logly import InterceptHandler

        handler = InterceptHandler()

        record = Mock()
        record.levelname = "ERROR"
        record.getMessage.return_value = "error message"

        with patch(
            "acb.adapters.logger.logly.depends.get_sync", side_effect=Exception("error")
        ):
            # Should not raise an exception
            handler.emit(record)


@pytest.mark.integration
class TestLoglyIntegration:
    """Integration tests for Logly adapter."""

    def test_logger_creation_and_basic_usage(self, mock_logly):
        """Test creating logger and basic logging operations."""
        from acb.adapters.logger.logly import Logger

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

    def test_context_operations(self, mock_logly):
        """Test context binding operations."""
        from acb.adapters.logger.logly import Logger

        logger = Logger()
        logger.init()

        # Test context binding
        bound_logger = logger.bind(user_id="test123")
        assert bound_logger is not logger

        # Test correlation ID
        corr_logger = logger.with_correlation_id("test-corr-id")
        assert corr_logger._bound_context["correlation_id"] == "test-corr-id"

    def test_logly_specific_features(self, mock_logly, mock_config):
        """Test Logly-specific features."""
        from acb.adapters.logger.logly import Logger
        from acb.config import Config
        from acb.depends import depends

        # Register mock config in DI so property can access it
        depends.set(Config, mock_config)

        logger = Logger()

        # Test trace and success levels
        logger.trace("trace message")
        logger.success("success message")

        # Test contextualize
        with logger.contextualize(request_id="123"):
            pass

        # Test complete
        logger.complete()

    @pytest.mark.skip(reason="Cannot test real dependencies with autouse mock fixture")
    def test_with_real_dependencies(self, mock_logly):
        """Test logger with ACB dependencies."""
        from acb.adapters.logger.logly import Logger
        from acb.config import Config
        from acb.depends import depends

        # Ensure real config is available in DI system
        try:
            config = depends.get_sync(Config)
        except Exception:
            # If config not in DI, create and register it
            config = Config()
            depends.set(Config, config)

        logger = Logger()

        # Config should be available through depends
        logger_config = logger.config
        assert isinstance(logger_config, Config)


@pytest.mark.benchmark
class TestLoglyPerformance:
    """Performance benchmark tests for Logly adapter."""

    def test_logging_overhead(self, benchmark, mock_logly):
        """Benchmark basic logging overhead."""
        from acb.adapters.logger.logly import Logger

        logger = Logger()

        def log_message():
            logger.info("test message")

        benchmark(log_message)

    def test_context_binding_overhead(self, benchmark, mock_logly):
        """Benchmark context binding overhead."""
        from acb.adapters.logger.logly import Logger

        logger = Logger()

        def bind_context():
            return logger.bind(user_id="123", session="abc")

        benchmark(bind_context)
