"""ACB Testing Factory Utilities.

Provides functions for creating test components and configurations.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import typing as t
import yaml

from acb.config import Config


def create_test_config(overrides: dict[str, t.Any] | None = None) -> Config:
    """Create a test configuration with sensible defaults."""
    base_config = {
        "app": {
            "name": "test-app",
            "version": "1.0.0",
            "environment": "test",
        },
        "debug": {
            "enabled": True,
            "level": "DEBUG",
        },
        "adapters": {
            "cache": "memory",
            "storage": "memory",
            "sql": "sqlite",
        },
        "testing": {
            "mock_external_services": True,
            "use_in_memory_db": True,
            "cleanup_resources": True,
        },
    }

    if overrides:
        # Deep merge overrides
        def deep_merge(
            base: dict[str, t.Any],
            override: dict[str, t.Any],
        ) -> dict[str, t.Any]:
            result = base.copy()
            for key, value in override.items():
                if (
                    key in result
                    and isinstance(result[key], dict)
                    and isinstance(value, dict)
                ):
                    result[key] = deep_merge(result[key], value)
                else:
                    result[key] = value
            return result

        base_config = deep_merge(base_config, overrides)

    config = Config()
    # Store config data as test attribute for test utilities
    config._test_config_data = base_config  # type: ignore[attr-defined]
    return config


async def create_test_adapter(
    adapter_type: str,
    config: dict[str, t.Any] | None = None,
) -> t.Any:
    """Create a test adapter instance with mock configuration."""
    try:
        from acb.adapters import import_adapter

        # Import the adapter class
        AdapterClass = import_adapter(adapter_type)

        # Create instance
        adapter = AdapterClass()

        # Mock the settings if needed
        if config:
            adapter._settings = MagicMock()
            for key, value in config.items():
                setattr(adapter._settings, key, value)

        return adapter

    except Exception:
        # Return a mock adapter if real one not available
        mock_adapter = AsyncMock()

        # Add common adapter methods
        mock_adapter._ensure_client = AsyncMock()
        mock_adapter._create_client = AsyncMock()

        # Configure based on adapter type
        if adapter_type == "cache":
            mock_adapter.get = AsyncMock(return_value=None)
            mock_adapter.set = AsyncMock(return_value=True)
            mock_adapter.delete = AsyncMock(return_value=True)

        elif adapter_type == "storage":
            mock_adapter.read = AsyncMock(return_value=b"test data")
            mock_adapter.write = AsyncMock(return_value=True)
            mock_adapter.exists = AsyncMock(return_value=True)

        elif adapter_type == "sql":
            mock_result = MagicMock()
            mock_result.rowcount = 1
            mock_adapter.execute = AsyncMock(return_value=mock_result)
            mock_adapter.fetch_one = AsyncMock(return_value={"id": 1})
            mock_adapter.fetch_all = AsyncMock(return_value=[{"id": 1}])

        return mock_adapter


async def create_test_service(
    service_type: str,
    config: dict[str, t.Any] | None = None,
) -> t.Any:
    """Create a test service instance with mock configuration."""
    try:
        from acb.services.discovery import import_service

        # Import the service class
        ServiceClass = import_service(service_type)

        # Create instance
        service = ServiceClass()

        # Mock the settings if needed
        if config:
            service._settings = MagicMock()
            for key, value in config.items():
                setattr(service._settings, key, value)

        return service

    except Exception:
        # Return a mock service if real one not available
        mock_service = AsyncMock()

        # Configure based on service type
        if service_type == "performance":
            mock_service.optimize = AsyncMock(return_value={"optimized": True})
            mock_service.get_metrics = AsyncMock(return_value={"cpu": 50})

        elif service_type == "health":
            mock_service.check = AsyncMock(return_value={"status": "healthy"})
            mock_service.get_status = AsyncMock(return_value="healthy")

        elif service_type == "validation":
            mock_service.validate = AsyncMock(
                return_value={"valid": True, "errors": []},
            )
            mock_service.sanitize = AsyncMock(return_value="clean data")

        return mock_service


def create_mock_dependency(
    interface_type: type,
    behavior: dict[str, t.Any] | None = None,
) -> MagicMock:
    """Create a mock dependency that implements a specific interface."""
    mock = MagicMock(spec=interface_type)

    # Configure behavior if provided
    if behavior:
        for attr_name, attr_value in behavior.items():
            if callable(attr_value):
                setattr(mock, attr_name, attr_value)
            else:
                mock.configure_mock(**{attr_name: attr_value})

    return mock


def create_temporary_config_file(
    config_data: dict[str, t.Any],
    file_path: Path,
) -> Path:
    """Create a temporary configuration file for testing."""
    # Ensure parent directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Write config data
    with file_path.open("w") as f:
        yaml.dump(config_data, f, default_flow_style=False)

    return file_path
