"""ACB Testing Interface Validation Utilities.

Provides functions for validating that components implement expected interfaces.
"""

import asyncio
import typing as t


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
            msg = f"Adapter missing method: {method_name}"
            raise AssertionError(msg)

        method = getattr(adapter_class, method_name)
        if not callable(method):
            msg = f"Adapter method {method_name} is not callable"
            raise AssertionError(
                msg,
            )

        # Check if async method
        if method_name.startswith("_") or asyncio.iscoroutinefunction(method):
            if not asyncio.iscoroutinefunction(method):
                msg = f"Method {method_name} should be async"
                raise AssertionError(msg)


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
            msg = "Service metadata should not be None"
            raise AssertionError(msg)
        _validate_metadata_attributes(metadata)


def _validate_metadata_attributes(metadata: t.Any) -> None:
    """Validate that metadata has required attributes."""
    if not hasattr(metadata, "name"):
        msg = "Service metadata should have name"
        raise AssertionError(msg)
    if not hasattr(metadata, "category"):
        msg = "Service metadata should have category"
        raise AssertionError(msg)


def _validate_expected_methods(
    service_class: type,
    expected_methods: list[str],
) -> None:
    """Validate that all expected methods exist and are callable."""
    for method_name in expected_methods:
        _validate_single_method(service_class, method_name)


def _validate_single_method(service_class: type, method_name: str) -> None:
    """Validate a single method."""
    if not hasattr(service_class, method_name):
        msg = f"Service missing method: {method_name}"
        raise AssertionError(msg)

    method = getattr(service_class, method_name)
    if not callable(method):
        msg = f"Service method {method_name} is not callable"
        raise AssertionError(
            msg,
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
            msg = f"Action missing function: {function_name}"
            raise AssertionError(msg)

        function = getattr(action_module, function_name)
        if not callable(function):
            msg = f"Action function {function_name} is not callable"
            raise AssertionError(
                msg,
            )
