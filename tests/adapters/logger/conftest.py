"""Pytest fixtures for logger adapter tests."""

from unittest.mock import Mock

import pytest


@pytest.fixture
def mock_config():
    """Mock Config for unit testing logger adapters.

    This mock provides all the config attributes that logger adapters access.
    Use this with setup_logger_config() helper or manually assign to logger.__dict__['config'].
    """
    config = Mock()
    config.deployed = False
    config.debug = Mock()
    config.debug.production = False
    config.debug.logger = False
    config.root_path = "/test/path"
    config.logger = Mock()
    config.logger.log_level = "INFO"
    config.logger.level_per_module = {}
    return config


def setup_logger_config(logger, mock_config):
    """Helper to inject mock config into logger instance.

    Sets config directly on logger.__dict__ to bypass Inject descriptor
    and prevent DI initialization during tests.

    Usage:
        logger = Logger()
        setup_logger_config(logger, mock_config)
    """
    logger.__dict__["config"] = mock_config
    return logger
