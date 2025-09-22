"""Additional tests for the config module to improve coverage."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from acb.config import (
    Config,
    AppSettings,
    DebugSettings,
    Settings,
    _detect_library_usage,
    _is_pytest_test_context,
    _is_main_module_local,
    _should_initialize_eagerly,
    get_singleton_instance,
    Platform,
    get_version_default,
    gen_password,
)


class TestConfigClass:
    """Test Config class."""

    def test_config_initialization(self) -> None:
        """Test Config class initialization."""
        config = Config()
        assert isinstance(config, Config)
        assert hasattr(config, "deployed")
        assert hasattr(config, "root_path")
        assert hasattr(config, "secrets_path")
        assert hasattr(config, "settings_path")
        assert hasattr(config, "tmp_path")
        assert config._debug is None
        assert config._app is None
        assert config._initialized is False

    def test_config_init_method(self) -> None:
        """Test Config init method."""
        config = Config()

        with patch("acb.config._library_usage_mode", False):
            with patch("acb.config._testing", False):
                config.init()
                assert config._initialized is True
                assert isinstance(config._debug, DebugSettings)
                assert isinstance(config._app, AppSettings)

    def test_config_init_method_force(self) -> None:
        """Test Config init method with force parameter."""
        config = Config()
        config._initialized = True

        # Force initialization even when already initialized
        with patch("acb.config._library_usage_mode", False):
            with patch("acb.config._testing", False):
                config.init(force=True)
                assert config._initialized is True

    def test_config_init_method_library_mode(self) -> None:
        """Test Config init method in library mode."""
        config = Config()

        with patch("acb.config._library_usage_mode", True):
            with patch("acb.config._testing", False):
                config.init()
                # Should not initialize in library mode
                assert config._initialized is False

    def test_config_ensure_initialized(self) -> None:
        """Test Config ensure_initialized method."""
        config = Config()

        with patch("acb.config._library_usage_mode", False):
            config.ensure_initialized()
            assert config._initialized is True
            assert isinstance(config._debug, DebugSettings)
            assert isinstance(config._app, AppSettings)

    def test_config_ensure_initialized_library_mode(self) -> None:
        """Test Config ensure_initialized method in library mode."""
        config = Config()

        with patch("acb.config._library_usage_mode", True):
            config.ensure_initialized()
            assert config._initialized is True
            # In library mode, should use library settings
            assert config._debug is not None
            assert config._app is not None

    def test_config_debug_property(self) -> None:
        """Test Config debug property."""
        config = Config()

        # Accessing debug property should trigger initialization
        with patch("acb.config._library_usage_mode", False):
            debug_settings = config.debug
            assert isinstance(debug_settings, DebugSettings)
            assert config._initialized is True

    def test_config_app_property(self) -> None:
        """Test Config app property."""
        config = Config()

        # Accessing app property should trigger initialization
        with patch("acb.config._library_usage_mode", False):
            app_settings = config.app
            assert isinstance(app_settings, AppSettings)
            assert config._initialized is True

    def test_config_app_setter(self) -> None:
        """Test Config app setter."""
        config = Config()
        new_app_settings = AppSettings()

        config.app = new_app_settings
        assert config._app is new_app_settings

    def test_config_getattr_with_dot_notation(self) -> None:
        """Test Config __getattr__ with dot notation."""
        config = Config()

        with patch("acb.config._library_usage_mode", False):
            # Test accessing nested attributes
            result = config.debug.production
            assert isinstance(result, bool)

    def test_config_getattr_with_adapter(self) -> None:
        """Test Config __getattr__ with adapter access."""
        config = Config()

        # Mock adapter access
        with patch("acb.config._library_usage_mode", False):
            with patch("acb.adapters.get_adapter") as mock_get_adapter:
                mock_adapter = MagicMock()
                mock_adapter.settings = MagicMock()
                mock_get_adapter.return_value = mock_adapter

                result = config.some_adapter
                assert result is mock_adapter.settings

    def test_config_getattr_nonexistent(self) -> None:
        """Test Config __getattr__ with nonexistent attribute."""
        config = Config()

        with pytest.raises(AttributeError):
            _ = config.nonexistent_attribute


class TestUtilityFunctions:
    """Test utility functions in config module."""

    def test_is_pytest_test_context(self) -> None:
        """Test _is_pytest_test_context function."""
        # This function now delegates to context.is_testing_mode(), so we can't easily test it in isolation
        # Just verify it doesn't crash
        try:
            result = _is_pytest_test_context()
            assert isinstance(result, bool)
        except Exception:
            pytest.fail("_is_pytest_test_context should not raise exceptions")

    def test_is_main_module_local(self) -> None:
        """Test _is_main_module_local function."""
        # Just verify it doesn't crash
        try:
            result = _is_main_module_local()
            assert isinstance(result, bool)
        except Exception:
            pytest.fail("_is_main_module_local should not raise exceptions")

    def test_should_initialize_eagerly(self) -> None:
        """Test _should_initialize_eagerly function."""
        # Just verify it doesn't crash
        try:
            result = _should_initialize_eagerly()
            assert isinstance(result, bool)
        except Exception:
            pytest.fail("_should_initialize_eagerly should not raise exceptions")


class TestPlatformEnum:
    """Test Platform enum."""

    def test_platform_enum_values(self) -> None:
        """Test Platform enum values."""
        # Platform is actually an Enum with these values
        assert Platform.aws.value == "aws"
        assert Platform.gcp.value == "gcp"
        assert Platform.azure.value == "azure"
        assert Platform.cloudflare.value == "cloudflare"


class TestVersionFunctions:
    """Test version-related functions."""

    def test_get_version_default(self) -> None:
        """Test get_version_default function."""
        version = get_version_default()
        # Should return a version string like "0.0.0"
        assert isinstance(version, str)
        assert len(version.split(".")) == 3
        assert all(part.isdigit() for part in version.split("."))

    def test_gen_password(self) -> None:
        """Test gen_password function."""
        # Test default length
        password = gen_password()
        assert isinstance(password, str)
        # token_urlsafe(10) produces 14 characters
        assert len(password) >= 10

        # Test custom length
        password = gen_password(15)
        assert isinstance(password, str)
        assert len(password) >= 15

        # Test that password contains allowed characters
        allowed_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" + "-_"
        password = gen_password(20)
        assert all(char in allowed_chars for char in password)


class TestSingletonInstance:
    """Test singleton instance functionality."""

    def test_get_singleton_instance(self) -> None:
        """Test get_singleton_instance function."""

        class TestClass:
            def __init__(self, value: int = 0) -> None:
                self.value = value

        # Get first instance
        instance1 = get_singleton_instance(TestClass, 42)
        assert isinstance(instance1, TestClass)
        assert instance1.value == 42

        # Get second instance - should be the same
        instance2 = get_singleton_instance(TestClass, 99)
        assert instance2 is instance1
        assert instance2.value == 42  # Should keep original value
