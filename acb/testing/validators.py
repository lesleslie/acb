"""ACB Testing Validation Utilities.

Provides functions for validating test results and parameters.
"""

import typing as t

from acb.depends import depends


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


def validate_parameters(
    parameters: dict[str, t.Any], required_params: list[str]
) -> bool:
    """Validate that required parameters are present."""
    return all(param in parameters for param in required_params)


def get_parameter(
    parameters: dict[str, t.Any], name: str, default: t.Any = None
) -> t.Any:
    """Get a parameter value with a default."""
    return parameters.get(name, default)


def assert_dependency_injected(dependency_type: type) -> t.Any:
    """Assert that a dependency is properly injected."""
    instance = depends.get(dependency_type)
    if instance is None:
        raise AssertionError(
            f"Dependency {dependency_type.__name__} not injected",
        )
    return instance
