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

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import asyncio
import typing as t
from contextlib import suppress

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
        if not hasattr(adapter_class, method_name):
            raise AssertionError(f"Adapter missing method: {method_name}")

        method = getattr(adapter_class, method_name)
        if not callable(method):
            raise AssertionError(
                f"Adapter method {method_name} is not callable",
            )

        # Check if async method
        if method_name.startswith("_") or asyncio.iscoroutinefunction(method):
            if not asyncio.iscoroutinefunction(method):
                raise AssertionError(f"Method {method_name} should be async")


def assert_service_interface(
    service_class: type,
    expected_methods: list[str] | None = None,
) -> None:
    """Assert that a service implements the expected interface."""
    if expected_methods is None:
        # Common service methods vary by type, but check basic structure
        expected_methods = []

    _validate_service_metadata(service_class)
    _validate_expected_methods(service_class, expected_methods)


def _validate_service_metadata(service_class: type) -> None:
    """Validate service metadata if present."""
    if hasattr(service_class, "SERVICE_METADATA"):
        metadata = service_class.SERVICE_METADATA
        if metadata is None:
            raise AssertionError("Service metadata should not be None")
        _validate_metadata_attributes(metadata)


def _validate_metadata_attributes(metadata: t.Any) -> None:
    """Validate that metadata has required attributes."""
    if not hasattr(metadata, "name"):
        raise AssertionError("Service metadata should have name")
    if not hasattr(metadata, "category"):
        raise AssertionError("Service metadata should have category")


def _validate_expected_methods(
    service_class: type, expected_methods: list[str]
) -> None:
    """Validate that all expected methods exist and are callable."""
    for method_name in expected_methods:
        _validate_single_method(service_class, method_name)


def _validate_single_method(service_class: type, method_name: str) -> None:
    """Validate a single method."""
    if not hasattr(service_class, method_name):
        raise AssertionError(f"Service missing method: {method_name}")

    method = getattr(service_class, method_name)
    if not callable(method):
        raise AssertionError(
            f"Service method {method_name} is not callable",
        )


def assert_action_interface(
    action_module: t.Any,
    expected_functions: list[str] | None = None,
) -> None:
    """Assert that an action module implements the expected interface."""
    if expected_functions is None:
        # Actions typically have these patterns
        expected_functions = []

    for function_name in expected_functions:
        if not hasattr(action_module, function_name):
            raise AssertionError(f"Action missing function: {function_name}")

        function = getattr(action_module, function_name)
        if not callable(function):
            raise AssertionError(
                f"Action function {function_name} is not callable",
            )


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
            base: dict[str, t.Any], override: dict[str, t.Any]
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
    adapter_type: str, config: dict[str, t.Any] | None = None
) -> t.Any:
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


async def create_test_service(
    service_type: str, config: dict[str, t.Any] | None = None
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


async def setup_test_environment(
    config: dict[str, t.Any] | None = None,
) -> dict[str, t.Any]:
    """Setup a complete test environment with all necessary components."""
    # Create test config
    test_config = create_test_config(config)

    # Initialize dependency injection
    depends.set(Config, test_config)

    # Create test adapters based on configuration
    adapters: dict[str, t.Any] = {}
    # Access test config data
    adapter_configs = getattr(test_config, "_test_config_data", {}).get("adapters", {})

    for adapter_type in adapter_configs:
        with suppress(Exception):
            adapter = await create_test_adapter(adapter_type)
            adapters[adapter_type] = adapter
            depends.set(type(adapter), adapter)

    # Create test environment info
    # Access depends instances using get() method instead of private attribute
    dependencies: dict[str, t.Any] = {}
    return {
        "config": test_config,
        "adapters": adapters,
        "dependencies": dependencies,
        "status": "ready",
        "created_at": "2024-01-01T12:00:00Z",
    }


async def teardown_test_environment(environment: dict[str, t.Any]) -> None:
    """Teardown a test environment and cleanup resources."""
    # Cleanup adapters
    for adapter in environment.get("adapters", {}).values():
        with suppress(Exception):
            if hasattr(adapter, "cleanup"):
                await adapter.cleanup()
            elif hasattr(adapter, "close"):
                await adapter.close()
            elif hasattr(adapter, "__aexit__"):
                await adapter.__aexit__(None, None, None)

    # Clear dependency injection - note: we skip clearing private instances in testing

    # Update environment status
    environment["status"] = "cleaned_up"


async def run_acb_test_suite(
    test_functions: list[t.Callable[..., t.Any]],
    environment_config: dict[str, t.Any] | None = None,
    parallel: bool = False,
) -> dict[str, t.Any]:
    """Run a complete ACB test suite with environment setup and teardown."""
    environment = await setup_test_environment(environment_config)
    start_time = asyncio.get_event_loop().time()

    try:
        results = (
            await _run_tests_parallel(test_functions)
            if parallel
            else await _run_tests_sequential(test_functions)
        )
    finally:
        await teardown_test_environment(environment)

    execution_time = asyncio.get_event_loop().time() - start_time

    return _build_test_summary(
        test_functions, results, execution_time, parallel, environment_config
    )


async def _run_tests_parallel(
    test_functions: list[t.Callable[..., t.Any]],
) -> list[dict[str, t.Any]]:
    """Run tests in parallel."""
    tasks = [_wrap_test_function(func) for func in test_functions]
    test_results = await asyncio.gather(*tasks, return_exceptions=True)

    return [
        _create_test_result(test_functions[i], result)
        for i, result in enumerate(test_results)
    ]


async def _run_tests_sequential(
    test_functions: list[t.Callable[..., t.Any]],
) -> list[dict[str, t.Any]]:
    """Run tests sequentially."""
    results = []
    for test_func in test_functions:
        try:
            result = await _execute_test_function(test_func)
            results.append(_create_success_result(test_func, result))
        except Exception as e:
            results.append(_create_failure_result(test_func, e))

    return results


async def _wrap_test_function(test_func: t.Callable[..., t.Any]) -> t.Any:
    """Wrap test function for parallel execution."""
    if asyncio.iscoroutinefunction(test_func):
        return await test_func()

    async def async_wrapper() -> t.Any:
        return test_func()

    return await async_wrapper()


async def _execute_test_function(test_func: t.Callable[..., t.Any]) -> t.Any:
    """Execute a test function (async or sync)."""
    if asyncio.iscoroutinefunction(test_func):
        return await test_func()
    return test_func()


def _create_test_result(
    test_func: t.Callable[..., t.Any], result: t.Any
) -> dict[str, t.Any]:
    """Create test result from function and execution result."""
    if isinstance(result, BaseException):
        return _create_failure_result(test_func, result)
    return _create_success_result(test_func, result)


def _create_success_result(
    test_func: t.Callable[..., t.Any], result: t.Any
) -> dict[str, t.Any]:
    """Create success result."""
    return {
        "test": test_func.__name__,
        "status": "passed",
        "result": result,
    }


def _create_failure_result(
    test_func: t.Callable[..., t.Any], error: BaseException
) -> dict[str, t.Any]:
    """Create failure result."""
    return {
        "test": test_func.__name__,
        "status": "failed",
        "error": str(error),
        "error_type": type(error).__name__,
    }


def _build_test_summary(
    test_functions: list[t.Callable[..., t.Any]],
    results: list[dict[str, t.Any]],
    execution_time: float,
    parallel: bool,
    environment_config: dict[str, t.Any] | None,
) -> dict[str, t.Any]:
    """Build test execution summary."""
    passed_tests = [r for r in results if r["status"] == "passed"]

    return {
        "total_tests": len(test_functions),
        "passed": len(passed_tests),
        "failed": len(results) - len(passed_tests),
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
    if "status" not in result:
        raise AssertionError("Test result missing status")
    if result["status"] != expected_status:
        raise AssertionError(
            f"Expected {expected_status}, got {result['status']}",
        )

    if expected_status == "passed":
        if "error" in result and result["error"] is not None:
            raise AssertionError("Passed test should not have errors")
    elif expected_status == "failed":
        if "error" not in result:
            raise AssertionError("Failed test should have error information")


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


def assert_dependency_injected(dependency_type: type) -> t.Any:
    """Assert that a dependency is properly injected."""
    instance = depends.get(dependency_type)
    if instance is None:
        raise AssertionError(
            f"Dependency {dependency_type.__name__} not injected",
        )
    return instance


def create_temporary_config_file(
    config_data: dict[str, t.Any], file_path: Path
) -> Path:
    """Create a temporary configuration file for testing."""
    import yaml

    # Ensure parent directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Write config data
    with file_path.open("w") as f:
        yaml.dump(config_data, f, default_flow_style=False)

    return file_path
