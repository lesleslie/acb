"""Shared test fixtures and utilities for ACB tests.

This module contains common fixtures that can be used across multiple test files
to reduce redundancy and improve consistency.
"""

from unittest.mock import Mock

import pytest

from acb.config import AppSettings, Config, DebugSettings


@pytest.fixture
def mock_config():
    """Shared mock Config for unit testing adapters.

    This mock provides all the config attributes that adapters typically access.
    """
    config = Mock(spec=Config)
    config.deployed = False
    config.debug = Mock(spec=DebugSettings)
    config.debug.production = False
    config.debug.logger = False
    config.root_path = "/test/path"
    config.app = Mock(spec=AppSettings)
    config.app.name = "test_app"
    config.app.title = "Test App"
    config.logger = Mock()
    config.logger.log_level = "INFO"
    config.logger.level_per_module = {}
    return config


@pytest.fixture
def mock_config_with_app_name():
    """Shared mock Config with a specific app name for testing."""
    config = Mock(spec=Config)
    config.deployed = False
    config.debug = Mock(spec=DebugSettings)
    config.debug.production = False
    config.debug.logger = False
    config.root_path = "/test/path"
    config.app = Mock(spec=AppSettings)
    config.app.name = "my_test_app"
    config.app.title = "My Test App"
    config.logger = Mock()
    config.logger.log_level = "INFO"
    config.logger.level_per_module = {}
    return config


@pytest.fixture
def mock_config_deployed():
    """Shared mock Config in deployed mode."""
    config = Mock(spec=Config)
    config.deployed = True
    config.debug = Mock(spec=DebugSettings)
    config.debug.production = True
    config.debug.logger = False
    config.root_path = "/test/path"
    config.app = Mock(spec=AppSettings)
    config.app.name = "test_app"
    config.app.title = "Test App"
    config.logger = Mock()
    config.logger.log_level = "WARNING"
    config.logger.level_per_module = {}
    return config


@pytest.fixture
def simple_mock_config():
    """A simplified mock config for basic testing."""
    config = Mock(spec=Config)
    config.app = Mock(spec=AppSettings)
    config.app.name = "simple_test"
    config.app.title = "Simple Test"
    config.deployed = False
    config.debug = Mock(spec=DebugSettings)
    config.debug.production = False
    config.debug.logger = False
    return config
