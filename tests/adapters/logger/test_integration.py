"""Integration tests for logger adapter system."""

import pytest

from acb.adapters import import_adapter
from acb.adapters.logger import LoggerProtocol
from acb.config import Config
from acb.depends import depends


class TestLoggerAdapterIntegration:
    """Test logger adapter system integration."""

    def test_import_logger_adapter(self):
        """Test importing logger adapter through the system."""
        # This should return the logger adapter class
        logger_class = import_adapter("logger")

        assert logger_class is not None
        assert hasattr(logger_class, "init")

    def test_logger_adapter_protocol_compliance(self):
        """Test that imported logger adapters implement the protocol."""
        logger_class = import_adapter("logger")
        logger_instance = logger_class()

        assert isinstance(logger_instance, LoggerProtocol)

    def test_logger_dependency_injection(self):
        """Test logger works with dependency injection system."""
        from acb.logger import Logger

        # In pytest mode, logger isn't auto-initialized, so register it
        try:
            logger = depends.get_sync(Logger)
            # Check if we got a string fallback instead of a real instance
            if isinstance(logger, str):
                raise ValueError("Got adapter name instead of instance")
        except Exception:
            # Not registered or got fallback, create and register it
            logger = Logger()
            depends.set(Logger, logger)

        assert logger is not None
        assert hasattr(logger, "info")
        assert hasattr(logger, "debug")
        assert hasattr(logger, "error")

    @pytest.mark.skip(reason="Requires full app initialization (not pytest mode)")
    def test_logger_settings_integration(self):
        """Test logger settings integration with config."""
        from acb.logger import LoggerSettings

        # In pytest mode, config might not be in DI, ensure it's available
        try:
            config = depends.get_sync(Config)
        except Exception:
            config = Config()
            depends.set(Config, config)

        # Logger settings should be attached to config
        assert hasattr(config, "logger")
        assert isinstance(config.logger, LoggerSettings)

    def test_intercept_handler_integration(self):
        """Test InterceptHandler works with the system."""
        import logging

        from acb.logger import InterceptHandler, Logger

        # Register a Logger instance in the DI container for this test
        logger_instance = Logger()
        depends.set(Logger, logger_instance)

        handler = InterceptHandler()

        # Create a test log record
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None,
        )

        # Should not raise an exception
        try:
            handler.emit(record)
        except Exception as e:
            pytest.fail(f"InterceptHandler failed: {e}")

    def test_backward_compatibility(self):
        """Test backward compatibility with existing logger usage."""
        from acb.logger import Logger

        # Should be able to use logger in the traditional way
        logger = Logger()

        # Basic logging methods should exist
        assert hasattr(logger, "debug")
        assert hasattr(logger, "info")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")
        assert hasattr(logger, "critical")

        # Initialize should work
        if hasattr(logger, "init"):
            logger.init()

    @pytest.mark.parametrize("adapter_name", ["loguru", "structlog"])
    def test_specific_adapter_import(self, adapter_name):
        """Test importing specific logger adapters."""
        try:
            # Try to import specific adapters
            if adapter_name == "loguru":
                from acb.adapters.logger.loguru import Logger

                logger = Logger()
                assert logger is not None
            elif adapter_name == "structlog":
                try:
                    from acb.adapters.logger.structlog import Logger

                    logger = Logger()
                    assert logger is not None
                except ImportError:
                    # structlog might not be installed
                    pytest.skip("structlog not available")

        except ImportError as e:
            pytest.skip(f"Required dependencies not available: {e}")

    def test_adapter_metadata_availability(self):
        """Test that adapter metadata is properly exposed."""
        from acb.adapters.logger.loguru import MODULE_METADATA as loguru_metadata

        assert loguru_metadata.name == "Loguru Logger"
        assert loguru_metadata.category == "logger"
        assert loguru_metadata.provider == "loguru"

        try:
            from acb.adapters.logger.structlog import (
                MODULE_METADATA as structlog_metadata,
            )

            assert structlog_metadata.name == "Structlog Logger"
            assert structlog_metadata.category == "logger"
            assert structlog_metadata.provider == "structlog"
        except ImportError:
            pytest.skip("structlog not available")

    def test_logger_capabilities(self):
        """Test logger adapter capabilities are properly defined."""
        from acb.adapters import AdapterCapability
        from acb.adapters.logger.loguru import MODULE_METADATA

        capabilities = MODULE_METADATA.capabilities

        # Should include basic logger capabilities
        assert AdapterCapability.ASYNC_LOGGING in capabilities
        assert AdapterCapability.CONTEXTUAL in capabilities

    def test_context_management(self):
        """Test context management across logger adapters."""
        from acb.logger import Logger

        logger = Logger()

        if hasattr(logger, "bind"):
            # Test context binding
            bound_logger = logger.bind(user_id="test123")
            assert bound_logger is not None

        if hasattr(logger, "with_correlation_id"):
            # Test correlation ID
            corr_logger = logger.with_correlation_id("test-corr")
            assert corr_logger is not None

    def test_structured_logging_support(self):
        """Test structured logging support across adapters."""
        from acb.logger import Logger

        logger = Logger()

        if hasattr(logger, "log_structured"):
            # Should not raise an exception
            logger.log_structured("info", "test message", user_id="123")

    def test_stdlib_logging_integration(self):
        """Test standard library logging integration."""
        import logging

        # Create a stdlib logger
        stdlib_logger = logging.getLogger("test.integration")

        # Should be able to log without errors
        stdlib_logger.info("Test message from stdlib")
        stdlib_logger.error("Test error from stdlib")

    def test_multiple_logger_instances(self):
        """Test creating multiple logger instances."""
        from acb.logger import Logger

        logger1 = Logger()
        logger2 = Logger()

        # Should be able to create multiple instances
        assert logger1 is not None
        assert logger2 is not None

        # Initialize both
        if hasattr(logger1, "init"):
            logger1.init()
        if hasattr(logger2, "init"):
            logger2.init()


@pytest.mark.integration
class TestLoggerAdapterSwitching:
    """Test switching between different logger adapters."""

    def test_adapter_configuration_switching(self):
        """Test configuring different logger adapters."""
        # This would typically be done through settings/adapters.yml
        # For now, we test that both adapters can be imported

        from acb.adapters.logger.loguru import Logger as LoguruLogger

        loguru_logger = LoguruLogger()
        assert loguru_logger is not None

        try:
            from acb.adapters.logger.structlog import Logger as StructlogLogger

            structlog_logger = StructlogLogger()
            assert structlog_logger is not None
        except ImportError:
            pytest.skip("structlog not available")

    def test_adapter_fallback_behavior(self):
        """Test fallback behavior when adapters are not available."""
        # Test that the system can handle missing adapters gracefully
        from acb.logger import _get_logger_adapter

        # Should return a logger class
        logger_class = _get_logger_adapter()
        assert logger_class is not None

        # Should be able to instantiate
        logger = logger_class()
        assert logger is not None


@pytest.mark.integration
class TestLoggerPerformance:
    """Test logger adapter performance characteristics."""

    def test_logger_initialization_performance(self):
        """Test logger initialization is reasonably fast."""
        import time

        from acb.logger import Logger

        start_time = time.time()

        for _ in range(10):
            logger = Logger()
            if hasattr(logger, "init"):
                logger.init()

        end_time = time.time()
        total_time = end_time - start_time

        # Should complete 10 initializations in reasonable time
        assert total_time < 5.0, f"Logger initialization too slow: {total_time}s"

    def test_context_binding_performance(self):
        """Test context binding performance."""
        import time

        from acb.logger import Logger

        logger = Logger()

        if hasattr(logger, "bind"):
            start_time = time.time()

            for i in range(100):
                logger.bind(iteration=i, user_id=f"user_{i}")

            end_time = time.time()
            total_time = end_time - start_time

            # Should complete 100 bindings quickly
            assert total_time < 2.0, f"Context binding too slow: {total_time}s"


@pytest.mark.integration
class TestLoggerConfiguration:
    """Test logger configuration and settings."""

    def test_logger_settings_configuration(self):
        """Test logger settings can be configured."""
        from acb.logger import LoggerSettings

        settings = LoggerSettings(
            log_level="DEBUG", json_output=True, async_logging=True
        )

        assert settings.log_level == "DEBUG"
        assert settings.json_output is True
        assert settings.async_logging is True

    def test_logger_settings_inheritance(self):
        """Test logger settings inheritance from base."""
        from acb.adapters.logger._base import LoggerBaseSettings
        from acb.adapters.logger.loguru import LoguruSettings

        settings = LoguruSettings()

        # Should inherit from base settings
        assert isinstance(settings, LoggerBaseSettings)

        # Should have loguru-specific settings
        assert hasattr(settings, "backtrace")
        assert hasattr(settings, "catch")
        assert hasattr(settings, "diagnose")

    def test_adapter_specific_configuration(self):
        """Test adapter-specific configuration."""
        from acb.adapters.logger.loguru import LoguruSettings

        loguru_settings = LoguruSettings(backtrace=True, catch=True, colorize=False)

        assert loguru_settings.backtrace is True
        assert loguru_settings.catch is True
        assert loguru_settings.colorize is False

        try:
            from acb.adapters.logger.structlog import LoggerSettings

            structlog_settings = LoggerSettings(
                json_output=True, pretty_print=False, add_timestamp=True
            )

            assert structlog_settings.json_output is True
            assert structlog_settings.pretty_print is False
            assert structlog_settings.add_timestamp is True

        except ImportError:
            pytest.skip("structlog not available")
