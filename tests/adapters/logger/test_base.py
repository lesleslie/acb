"""Tests for logger base adapter functionality."""

from unittest.mock import patch

import pytest

from acb.adapters.logger._base import LoggerBase, LoggerBaseSettings, LoggerProtocol
from acb.config import Config


class MockLogger(LoggerBase):
    """Mock logger implementation for testing."""

    def __init__(self):
        super().__init__()
        self.logged_messages = []
        self.bound_context = {}

    def _debug(self, msg: str, *args, **kwargs):
        self.logged_messages.append(("debug", msg, args, kwargs))

    def _info(self, msg: str, *args, **kwargs):
        self.logged_messages.append(("info", msg, args, kwargs))

    def _warning(self, msg: str, *args, **kwargs):
        self.logged_messages.append(("warning", msg, args, kwargs))

    def _error(self, msg: str, *args, **kwargs):
        self.logged_messages.append(("error", msg, args, kwargs))

    def _critical(self, msg: str, *args, **kwargs):
        self.logged_messages.append(("critical", msg, args, kwargs))

    def exception(self, msg: str, *args, **kwargs):
        self.logged_messages.append(("exception", msg, args, kwargs))

    def _log_structured(self, level: str, msg: str, **context):
        self.logged_messages.append(("structured", level, msg, context))

    def _bind(self, **context):
        new_logger = MockLogger()
        new_logger.bound_context = {**self.bound_context, **context}
        new_logger.logged_messages = self.logged_messages
        return new_logger

    def _with_context(self, **context):
        return self._bind(**context)

    def _with_correlation_id(self, correlation_id: str):
        return self._bind(correlation_id=correlation_id)

    def _init(self):
        self._initialized = True


class TestLoggerBaseSettings:
    """Test LoggerBaseSettings configuration."""

    def test_default_settings(self):
        """Test default settings are properly configured."""
        settings = LoggerBaseSettings()

        assert settings.verbose is False
        assert settings.deployed_level == "WARNING"
        assert settings.log_level == "INFO"
        assert settings.serialize is False
        assert settings.json_output is False
        assert settings.async_logging is True
        assert settings.context_vars is True

    def test_format_configuration(self):
        """Test format configuration."""
        settings = LoggerBaseSettings()

        assert settings.format is not None
        assert "time" in settings.format
        assert "level" in settings.format
        assert "message" in settings.format

    def test_structured_logging_settings(self):
        """Test structured logging configuration."""
        settings = LoggerBaseSettings(
            json_output=True, include_metadata=True, include_caller_info=True
        )

        assert settings.json_output is True
        assert settings.include_metadata is True
        assert settings.include_caller_info is True

    def test_remote_logging_settings(self):
        """Test remote logging configuration."""
        settings = LoggerBaseSettings(remote_batch_size=50, remote_flush_interval=10.0)

        assert settings.remote_batch_size == 50
        assert settings.remote_flush_interval == 10.0

    def test_adapter_settings_building(self):
        """Test that adapter-specific settings are built correctly."""
        settings = LoggerBaseSettings(
            serialize=True, async_logging=False, json_output=True
        )

        adapter_settings = settings.settings
        assert adapter_settings["serialize"] is True
        assert adapter_settings["enqueue"] is False
        assert adapter_settings["colorize"] is False


class TestLoggerBase:
    """Test LoggerBase functionality."""

    def test_logger_protocol_compliance(self):
        """Test that LoggerBase implements LoggerProtocol."""
        logger = MockLogger()
        assert isinstance(logger, LoggerProtocol)

    def test_public_method_delegation(self):
        """Test that public methods delegate to private implementations."""
        logger = MockLogger()

        logger.debug("test debug")
        logger.info("test info")
        logger.warning("test warning")
        logger.error("test error")
        logger.critical("test critical")

        assert len(logger.logged_messages) == 5
        assert logger.logged_messages[0] == ("debug", "test debug", (), {})
        assert logger.logged_messages[1] == ("info", "test info", (), {})
        assert logger.logged_messages[2] == ("warning", "test warning", (), {})
        assert logger.logged_messages[3] == ("error", "test error", (), {})
        assert logger.logged_messages[4] == ("critical", "test critical", (), {})

    def test_structured_logging(self):
        """Test structured logging functionality."""
        logger = MockLogger()

        logger.log_structured("info", "test message", user_id="123", action="login")

        assert len(logger.logged_messages) == 1
        message = logger.logged_messages[0]
        assert message[0] == "structured"
        assert message[1] == "info"
        assert message[2] == "test message"
        assert message[3] == {"user_id": "123", "action": "login"}

    def test_context_binding(self):
        """Test context binding functionality."""
        logger = MockLogger()

        bound_logger = logger.bind(user_id="123", session="abc")

        assert bound_logger.bound_context == {"user_id": "123", "session": "abc"}
        assert bound_logger is not logger  # Should be a new instance

    def test_with_context(self):
        """Test with_context method."""
        logger = MockLogger()

        context_logger = logger.with_context(request_id="req-456")

        assert context_logger.bound_context == {"request_id": "req-456"}

    def test_with_correlation_id(self):
        """Test with_correlation_id method."""
        logger = MockLogger()

        corr_logger = logger.with_correlation_id("corr-789")

        assert corr_logger.bound_context == {"correlation_id": "corr-789"}

    def test_initialization(self):
        """Test logger initialization."""
        logger = MockLogger()

        assert not logger._initialized
        logger.init()
        assert logger._initialized

    def test_settings_property(self):
        """Test settings property access."""
        logger = MockLogger()

        settings = logger.settings
        assert isinstance(settings, LoggerBaseSettings)

    def test_is_testing_mode(self):
        """Test testing mode detection."""
        logger = MockLogger()

        # Should detect pytest environment
        assert logger._is_testing_mode() is True

    @patch.dict("os.environ", {"TESTING": "true"})
    def test_is_testing_mode_env_var(self):
        """Test testing mode detection via environment variable."""
        logger = MockLogger()

        assert logger._is_testing_mode() is True

    def test_get_effective_level(self, mock_config):
        """Test effective level calculation."""
        from acb.depends import depends

        # Register mock config in DI so property can access it
        depends.set(Config, mock_config)

        logger = MockLogger()

        level = logger._get_effective_level()
        assert level == "INFO"

    def test_get_effective_level_deployed(self, mock_config):
        """Test effective level in deployed environment."""
        from acb.depends import depends

        # Register mock config in DI so property can access it
        mock_config.deployed = True
        depends.set(Config, mock_config)

        logger = MockLogger()

        level = logger._get_effective_level()
        assert level == "WARNING"

    def test_should_log_level(self):
        """Test level filtering logic."""
        logger = MockLogger()

        # Test basic level comparison
        assert logger._should_log_level("ERROR", "test_module") is True
        assert logger._should_log_level("DEBUG", "test_module") is False

    def test_should_log_level_false_setting(self):
        """Test level filtering with False setting."""
        logger = MockLogger()
        logger.settings.level_per_module = {"test_module": False}

        assert logger._should_log_level("ERROR", "test_module") is False

    def test_extract_module_name(self):
        """Test module name extraction."""
        logger = MockLogger()

        record = {"name": "acb.adapters.logger.test"}
        module_name = logger._extract_module_name(record)

        assert module_name == "acb.adapters.logger"

    def test_extract_module_name_long_path(self):
        """Test module name extraction for long paths."""
        logger = MockLogger()

        record = {"name": "very.long.module.path.test"}
        module_name = logger._extract_module_name(record)

        assert module_name == "long.module.path"

    def test_extract_module_name_with_sdk(self):
        """Test module name extraction removes _sdk suffix."""
        logger = MockLogger()

        record = {"name": "acb.adapters.test_sdk.module"}
        module_name = logger._extract_module_name(record)

        assert module_name == "acb.adapters.test"

    async def test_cleanup_resources(self):
        """Test resource cleanup."""
        logger = MockLogger()

        # Should not raise an exception
        await logger._cleanup_resources()


@pytest.mark.integration
class TestLoggerBaseIntegration:
    """Integration tests for LoggerBase."""

    def test_with_real_config(self):
        """Test logger with real config instance."""
        from acb.config import Config
        from acb.depends import depends

        # Create a real config instance
        config = Config()
        depends.set(Config, config)

        MockLogger()

        # Config should be available through depends, not as logger attribute
        # The config: Inject[Config] annotation is for type hints only
        retrieved_config = depends.get_sync(Config)
        assert retrieved_config is not None
        assert isinstance(retrieved_config, Config)

    def test_settings_integration(self):
        """Test settings integration with config."""
        logger = MockLogger()

        # Access settings should create instance
        settings = logger.settings
        assert isinstance(settings, LoggerBaseSettings)

        # Second access should return same instance
        settings2 = logger.settings
        assert settings is settings2
