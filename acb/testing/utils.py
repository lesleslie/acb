from typing import Any

"""ACB Testing Utilities.

Provides utility functions for testing ACB components, adapters,
and services with interface validation and test environment setup.

Features:
- Interface validation for adapters, services, and actions
- Test configuration creation
- Test component creation
- Environment setup and teardown
- Test suite orchestration
"""

import asyncio
import typing as t
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from acb.config import Config
from acb.depends import depends


def assert_adapter_interface(
    adapter_class: type,
    expected_methods: list[str] | None = None,
) -> None:
    """Assert that an adapter implements the expected interface."""
    if expected_methods is None:
        # Common adapter methods
        expected_methods = [
            "_ensure_client",
            "_create_client",
        ]

    for method_name in expected_methods:
        assert hasattr(adapter_class, method_name), (
            f"Adapter missing method: {method_name}"
        )

        method = getattr(adapter_class, method_name)
        assert callable(method), f"Adapter method {method_name} is not callable"

        # Check if async method
        if method_name.startswith("_") or asyncio.iscoroutinefunction(method):
            assert asyncio.iscoroutinefunction(method), (
                f"Method {method_name} should be async"
            )


def assert_service_interface(
    service_class: type,
    expected_methods: list[str] | None = None,
) -> None:
    """Assert that a service implements the expected interface."""
    if expected_methods is None:
        # Common service methods vary by type, but check basic structure
        expected_methods = []

    # Check that service has SERVICE_METADATA if it's a discoverable service
    if hasattr(service_class, "SERVICE_METADATA"):
        metadata = service_class.SERVICE_METADATA
        assert metadata is not None, "Service metadata should not be None"
        assert hasattr(metadata, "name"), "Service metadata should have name"
        assert hasattr(metadata, "category"), "Service metadata should have category"

    for method_name in expected_methods:
        assert hasattr(service_class, method_name), (
            f"Service missing method: {method_name}"
        )

        method = getattr(service_class, method_name)
        assert callable(method), f"Service method {method_name} is not callable"


def assert_action_interface(
    action_module: t.Any,
    expected_functions: list[str] | None = None,
) -> None:
    """Assert that an action module implements the expected interface."""
    if expected_functions is None:
        # Actions typically have these patterns
        expected_functions = []

    for function_name in expected_functions:
        assert hasattr(action_module, function_name), (
            f"Action missing function: {function_name}"
        )

        function = getattr(action_module, function_name)
        assert callable(function), f"Action function {function_name} is not callable"


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
            base: dict[str, Any], override: dict[str, Any]
        ) -> dict[str, Any]:
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
    config._config_data = base_config
    return config


async def create_test_adapter(adapter_type: str, config: dict | None = None) -> t.Any:
    """Create a test adapter instance with mock configuration."""
    from acb.adapters import import_adapter

    try:
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


async def create_test_service(service_type: str, config: dict | None = None) -> t.Any:
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


async def setup_test_environment(config: dict | None = None) -> dict[str, t.Any]:
    """Setup a complete test environment with all necessary components."""
    # Create test config
    test_config = create_test_config(config)

    # Initialize dependency injection
    depends.set(Config, test_config)

    # Create test adapters based on configuration
    adapters = {}
    adapter_configs = test_config._config_data.get("adapters", {})

    for adapter_type in adapter_configs:
        try:
            adapter = await create_test_adapter(adapter_type)
            adapters[adapter_type] = adapter
            depends.set(type(adapter), adapter)
        except Exception:
            # Skip if adapter creation fails
            pass

    # Create test environment info
    return {
        "config": test_config,
        "adapters": adapters,
        "dependencies": dict(depends._instances),
        "status": "ready",
        "created_at": "2024-01-01T12:00:00Z",
    }


async def teardown_test_environment(environment: dict[str, t.Any]) -> None:
    """Teardown a test environment and cleanup resources."""
    # Cleanup adapters
    for adapter in environment.get("adapters", {}).values():
        try:
            if hasattr(adapter, "cleanup"):
                await adapter.cleanup()
            elif hasattr(adapter, "close"):
                await adapter.close()
            elif hasattr(adapter, "__aexit__"):
                await adapter.__aexit__(None, None, None)
        except Exception:
            # Ignore cleanup errors
            pass

    # Clear dependency injection
    depends._instances.clear()

    # Update environment status
    environment["status"] = "cleaned_up"


async def run_acb_test_suite(
    test_functions: list[t.Callable[..., Any]],
    environment_config: dict | None = None,
    parallel: bool = False,
) -> dict[str, t.Any]:
    """Run a complete ACB test suite with environment setup and teardown."""
    # Setup test environment
    environment = await setup_test_environment(environment_config)

    results = []
    start_time = asyncio.get_event_loop().time()

    try:
        if parallel:
            # Run tests in parallel
            tasks = []
            for test_func in test_functions:
                if asyncio.iscoroutinefunction(test_func):
                    tasks.append(test_func())
                else:
                    # Wrap sync function in async
                    async def async_wrapper() -> None:
                        return test_func()

                    tasks.append(async_wrapper())

            test_results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(test_results):
                if isinstance(result, Exception):
                    results.append(
                        {
                            "test": test_functions[i].__name__,
                            "status": "failed",
                            "error": str(result),
                            "error_type": type(result).__name__,
                        },
                    )
                else:
                    results.append(
                        {
                            "test": test_functions[i].__name__,
                            "status": "passed",
                            "result": result,
                        },
                    )

        else:
            # Run tests sequentially
            for test_func in test_functions:
                try:
                    if asyncio.iscoroutinefunction(test_func):
                        result = await test_func()
                    else:
                        result = test_func()

                    results.append(
                        {
                            "test": test_func.__name__,
                            "status": "passed",
                            "result": result,
                        },
                    )

                except Exception as e:
                    results.append(
                        {
                            "test": test_func.__name__,
                            "status": "failed",
                            "error": str(e),
                            "error_type": type(e).__name__,
                        },
                    )

    finally:
        # Always cleanup
        await teardown_test_environment(environment)

    end_time = asyncio.get_event_loop().time()
    execution_time = end_time - start_time

    # Calculate summary
    passed_tests = [r for r in results if r["status"] == "passed"]
    failed_tests = [r for r in results if r["status"] == "failed"]

    return {
        "total_tests": len(test_functions),
        "passed": len(passed_tests),
        "failed": len(failed_tests),
        "success_rate": len(passed_tests) / len(test_functions)
        if test_functions
        else 1.0,
        "execution_time": execution_time,
        "parallel": parallel,
        "results": results,
        "environment": environment_config,
        "timestamp": "2024-01-01T12:00:00Z",
    }


def validate_test_result(
    result: dict[str, t.Any],
    expected_status: str = "passed",
) -> None:
    """Validate that a test result meets expectations."""
    assert "status" in result, "Test result missing status"
    assert result["status"] == expected_status, (
        f"Expected {expected_status}, got {result['status']}"
    )

    if expected_status == "passed":
        assert "error" not in result or result["error"] is None, (
            "Passed test should not have errors"
        )
    elif expected_status == "failed":
        assert "error" in result, "Failed test should have error information"


def create_mock_dependency(
    interface_type: type,
    behavior: dict | None = None,
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


def assert_dependency_injected(dependency_type: type) -> None:
    """Assert that a dependency is properly injected."""
    instance = depends.get(dependency_type)
    assert instance is not None, f"Dependency {dependency_type.__name__} not injected"
    return instance


def create_temporary_config_file(config_data: dict, file_path: Path) -> Path:
    """Create a temporary configuration file for testing."""
    import yaml

    # Ensure parent directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Write config data
    with open(file_path, "w") as f:
        yaml.dump(config_data, f, default_flow_style=False)

    return file_path
