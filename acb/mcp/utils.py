"""Utility functions for ACB MCP server."""

import json
from typing import Any, Dict, List, Optional, Union
from acb.depends import depends
from acb.logger import Logger


def serialize_component_info(component: Any) -> Dict[str, Any]:
    """Serialize component information for MCP transmission."""
    try:
        # Get basic component information
        info = {
            "type": type(component).__name__,
            "module": type(component).__module__,
            "methods": [],
            "attributes": []
        }
        
        # Get public methods
        for attr_name in dir(component):
            if not attr_name.startswith('_'):
                attr = getattr(component, attr_name)
                if callable(attr):
                    info["methods"].append(attr_name)
                else:
                    info["attributes"].append(attr_name)
        
        return info
    except Exception as e:
        return {
            "type": "Unknown",
            "error": str(e)
        }


def format_tool_response(response: Any) -> Dict[str, Any]:
    """Format a tool response for MCP transmission."""
    if isinstance(response, dict):
        return response
    elif isinstance(response, (list, tuple)):
        return {"items": list(response)}
    elif isinstance(response, (str, int, float, bool)):
        return {"value": response}
    else:
        return {"value": str(response)}


def validate_parameters(parameters: Dict[str, Any], required_params: List[str]) -> bool:
    """Validate that required parameters are present."""
    for param in required_params:
        if param not in parameters:
            return False
    return True


def get_parameter(parameters: Dict[str, Any], name: str, default: Any = None) -> Any:
    """Get a parameter value with a default."""
    return parameters.get(name, default)


async def async_retry(func, max_attempts: int = 3, delay: float = 1.0, *args, **kwargs) -> Any:
    """Execute a function with retry logic."""
    last_exception = None
    
    for attempt in range(max_attempts):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if attempt < max_attempts - 1:
                import asyncio
                await asyncio.sleep(delay * (2 ** attempt))  # Exponential backoff
            else:
                raise last_exception
    
    raise last_exception