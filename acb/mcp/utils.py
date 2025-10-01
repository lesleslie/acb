"""Utility functions for ACB MCP server."""

from typing import Any


def serialize_component_info(component: Any) -> dict[str, Any]:
    """Serialize component information for MCP transmission."""
    try:
        # Get basic component information
        info: dict[str, Any] = {
            "type": type(component).__name__,
            "module": type(component).__module__,
            "methods": [],
            "attributes": [],
        }

        # Get public methods
        for attr_name in dir(component):
            if not attr_name.startswith("_"):
                attr = getattr(component, attr_name)
                if callable(attr):
                    info["methods"].append(attr_name)
                else:
                    info["attributes"].append(attr_name)

        return info
    except Exception as e:
        return {"type": "Unknown", "error": str(e)}


def format_tool_response(response: Any) -> dict[str, Any]:
    """Format a tool response for MCP transmission."""
    if isinstance(response, dict):
        return response
    if isinstance(response, list | tuple):
        return {"items": list(response)}
    if isinstance(response, str | int | float | bool):
        return {"value": response}
    return {"value": str(response)}


def validate_parameters(parameters: dict[str, Any], required_params: list[str]) -> bool:
    """Validate that required parameters are present."""
    return all(param in parameters for param in required_params)


def get_parameter(parameters: dict[str, Any], name: str, default: Any = None) -> Any:
    """Get a parameter value with a default."""
    return parameters.get(name, default)


async def async_retry(
    func: Any,
    max_attempts: int = 3,
    delay: float = 1.0,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Execute a function with retry logic."""
    last_exception: Exception | None = None

    for attempt in range(max_attempts):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if attempt < max_attempts - 1:
                import asyncio

                await asyncio.sleep(delay * (2**attempt))  # Exponential backoff
            else:
                raise last_exception

    # This should never be reached due to the loop logic, but just in case
    if last_exception:
        raise last_exception
    msg = "Unexpected error in async_retry"
    raise RuntimeError(msg)
