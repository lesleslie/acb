"""ACB MCP Parameter Utilities.

Provides functions for validating and handling parameters.
"""

from typing import Any


def validate_parameters(parameters: dict[str, Any], required_params: list[str]) -> bool:
    """Validate that required parameters are present."""
    return all(param in parameters for param in required_params)


def get_parameter(parameters: dict[str, Any], name: str, default: Any = None) -> Any:
    """Get a parameter value with a default."""
    return parameters.get(name, default)
