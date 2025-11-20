"""ACB MCP Serialization Utilities.

Provides functions for serializing and formatting component information for MCP transmission.
"""

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
