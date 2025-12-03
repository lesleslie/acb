"""ACB Testing Environment Utilities.

Provides functions for setting up and tearing down test environments.
"""

import asyncio
import typing as t
from contextlib import suppress

from acb.config import Config
from acb.depends import depends

from .factories import create_test_adapter, create_test_config


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
        test_functions,
        results,
        execution_time,
        parallel,
        environment_config,
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
    test_func: t.Callable[..., t.Any],
    result: t.Any,
) -> dict[str, t.Any]:
    """Create test result from function and execution result."""
    if isinstance(result, BaseException):
        return _create_failure_result(test_func, result)
    return _create_success_result(test_func, result)


def _create_success_result(
    test_func: t.Callable[..., t.Any],
    result: t.Any,
) -> dict[str, t.Any]:
    """Create success result."""
    return {
        "test": test_func.__name__,
        "status": "passed",
        "result": result,
    }


def _create_failure_result(
    test_func: t.Callable[..., t.Any],
    error: BaseException,
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
