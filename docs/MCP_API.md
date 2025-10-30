# ACB MCP API Reference

**Version**: 1.0.0
**Module**: `acb.mcp`
**Python**: 3.13+
**Last Updated**: 2025-01-27

______________________________________________________________________

## Overview

The `acb.mcp` module provides the public API for creating and extending ACB MCP servers. This API enables plugin developers to inherit ACB's infrastructure (rate limiting, component registry, logging) while adding domain-specific functionality.

______________________________________________________________________

## Module Exports

```python
from acb.mcp import (
    # Server Creation
    create_mcp_server,
    mcp,  # Direct FastMCP instance access
    # Plugin API
    register_tools,
    register_resources,
    # Server Classes
    ACBMCPServer,
    ACMCPServer,  # Backwards compatibility alias
    # Components
    ComponentRegistry,
    WorkflowOrchestrator,
    ACBMCPTools,
    ACBMCPResources,
)
```

______________________________________________________________________

## Core Functions

### `create_mcp_server()`

Create an ACB MCP server instance with full infrastructure.

**Signature**:

```python
def create_mcp_server() -> ACBMCPServer:
    """Create and return an ACB MCP server instance."""
```

**Returns**:

- `ACBMCPServer`: Configured server instance ready to run

**Server Includes**:

- ✅ FastMCP instance (`server._server`)
- ✅ Rate limiting (15 req/sec, burst 40)
- ✅ Component registry
- ✅ Action execution engine
- ✅ Workflow orchestration
- ✅ Structured logging

**Example**:

```python
from acb.mcp import create_mcp_server

# Create server
server = create_mcp_server()

# Access FastMCP instance
fastmcp_instance = server._server

# Initialize and run
await server.initialize()
server.run()  # STDIO mode
server.run(transport="http", host="127.0.0.1", port=8080)  # HTTP mode
```

**Rate Limiting Configuration**:

```
# Automatically configured:
- max_requests_per_second: 15.0
- burst_capacity: 40
- global_limit: True
```

______________________________________________________________________

### `register_tools()`

Register MCP tools with an ACB server instance.

**Signature**:

```python
async def register_tools(
    server: Any,
    tools: dict[str, Callable[..., Awaitable[Any]]],
) -> None:
    """Register tools with ACB MCP server."""
```

**Parameters**:

- `server` (`ACBMCPServer`): Server instance from `create_mcp_server()`
- `tools` (`dict[str, Callable]`): Mapping of tool names to async functions

**Raises**:

- `AttributeError`: If server doesn't have `_server` attribute
- `ValueError`: If any tool is not callable

**Tool Requirements**:

- ✅ Must be async functions (`async def`)
- ✅ Must be callable
- ✅ Should return JSON-serializable types
- ✅ Should use type hints

**Example**:

```python
from acb.mcp import create_mcp_server, register_tools

server = create_mcp_server()


# Define tools
async def create_user(name: str, email: str) -> dict[str, Any]:
    """Create a new user."""
    user_id = await db.create_user(name, email)
    return {"success": True, "user_id": user_id}


async def get_user(user_id: int) -> dict[str, Any]:
    """Retrieve user by ID."""
    user = await db.get_user(user_id)
    if not user:
        return {"success": False, "error": "User not found"}
    return {"success": True, "user": user}


# Register with server
tools = {
    "create_user": create_user,
    "get_user": get_user,
}
await register_tools(server, tools)
```

**Error Handling Pattern**:

```python
async def safe_tool(param: str) -> dict[str, Any]:
    """Tool with proper error handling."""
    try:
        result = await perform_operation(param)
        return {"success": True, "data": result}
    except ValueError as e:
        # Expected validation errors
        return {"success": False, "error": f"Invalid input: {e}"}
    except ConnectionError as e:
        # Expected network errors
        return {"success": False, "error": f"Connection failed: {e}"}
    except Exception as e:
        # Unexpected errors - log and re-raise
        logger.exception(f"Unexpected error in safe_tool: {e}")
        raise
```

______________________________________________________________________

### `register_resources()`

Register MCP resources (documentation/data) with an ACB server instance.

**Signature**:

```python
async def register_resources(
    server: Any,
    resources: dict[str, Callable[..., Awaitable[str]]],
) -> None:
    """Register resources with ACB MCP server."""
```

**Parameters**:

- `server` (`ACBMCPServer`): Server instance from `create_mcp_server()`
- `resources` (`dict[str, Callable]`): Mapping of resource URIs to async functions

**Raises**:

- `AttributeError`: If server doesn't have `_server` attribute
- `ValueError`: If any resource is not callable

**Resource Requirements**:

- ✅ Must be async functions (`async def`)
- ✅ Must return `str` (typically markdown)
- ✅ Should be idempotent (safe to call multiple times)

**Example**:

```python
from acb.mcp import create_mcp_server, register_resources

server = create_mcp_server()


# Define resources
async def get_api_documentation() -> str:
    """Return API documentation in markdown format."""
    return """# API Documentation

## Endpoints

### create_user
Creates a new user account.

**Parameters**:
- `name` (string): User's full name
- `email` (string): User's email address

**Returns**: User ID and success status
"""


async def get_configuration_schema() -> str:
    """Return JSON schema for configuration."""
    import json

    schema = {
        "type": "object",
        "properties": {
            "api_key": {"type": "string", "minLength": 32},
            "timeout": {"type": "number", "minimum": 1},
        },
        "required": ["api_key"],
    }
    return json.dumps(schema, indent=2)


# Register with server
resources = {
    "api_docs": get_api_documentation,
    "config_schema": get_configuration_schema,
}
await register_resources(server, resources)
```

______________________________________________________________________

## Server Classes

### `ACBMCPServer`

Main MCP server class with lifecycle management.

**Attributes**:

- `_server` (`FastMCP`): Underlying FastMCP instance
- `registry` (`ComponentRegistry`): ACB component registry
- `logger` (`Logger`): Structured logger instance

**Methods**:

#### `async initialize() -> None`

Initialize server and components.

```python
server = create_mcp_server()
await server.initialize()  # Must call before running
```

#### `run(transport: str = "stdio", **kwargs) -> None`

Run the MCP server.

**Parameters**:

- `transport` (`str`): Transport protocol ("stdio", "http", "sse")
- `**kwargs`: Additional transport-specific arguments

**Example**:

```python
# STDIO mode (Claude Desktop)
server.run()

# HTTP mode
server.run(transport="http", host="127.0.0.1", port=8080)

# SSE mode
server.run(transport="sse", host="0.0.0.0", port=3000)
```

#### `async cleanup() -> None`

Clean up server resources.

```python
try:
    server.run()
finally:
    await server.cleanup()
```

______________________________________________________________________

## Component Classes

### `ComponentRegistry`

Access to registered ACB components.

**Methods**:

#### `get_actions() -> dict[str, Any]`

Get all registered action categories.

```python
from acb.mcp import create_mcp_server

server = create_mcp_server()
await server.initialize()

actions = server.registry.get_actions()
# {'compress': CompressActions, 'encode': EncodeActions, ...}
```

#### `get_adapters() -> dict[str, Any]`

Get all registered adapters.

```python
adapters = server.registry.get_adapters()
# {'http': HTTPAdapter, 'websocket': WebSocketAdapter, ...}
```

#### `get_services() -> dict[str, Any]`

Get all registered services.

#### `get_events() -> dict[str, Any]`

Get all registered event handlers.

______________________________________________________________________

### `WorkflowOrchestrator`

Execute multi-step workflows across ACB components.

**Example**:

```python
from acb.depends import depends
from acb.mcp import WorkflowOrchestrator

orchestrator = depends.get(WorkflowOrchestrator)

workflow = {
    "name": "data-processing",
    "steps": [
        {
            "name": "validate",
            "type": "action",
            "component": "validate",
            "action": "check_schema",
            "parameters": {"data": input_data},
        },
        {
            "name": "transform",
            "type": "action",
            "component": "transform",
            "action": "apply_rules",
            "parameters": {"rules": transform_rules},
        },
    ],
}

result = await orchestrator.execute(workflow)
```

______________________________________________________________________

## Direct FastMCP Access

The `mcp` export provides direct access to the global FastMCP instance.

**Use Cases**:

- Debugging
- Advanced FastMCP features
- Direct decorator usage (not recommended for plugins)

**Example**:

```python
from acb.mcp import mcp


# Direct tool registration (not recommended for plugins)
@mcp.tool()
async def debug_tool() -> dict:
    return {"status": "ok"}


# Access server internals (debugging only)
print(f"Registered tools: {len(mcp._mcp_server.tools)}")
```

**⚠️ Warning**: Direct `mcp` usage bypasses plugin registration patterns. Use `create_mcp_server()` + `register_tools()` for production plugins.

______________________________________________________________________

## Type Hints Reference

### Common Type Patterns

```python
from typing import Any, Awaitable, Callable

# Tool signature
ToolFunc = Callable[..., Awaitable[dict[str, Any]]]

# Resource signature
ResourceFunc = Callable[..., Awaitable[str]]


# Common return types
class ToolResult(TypedDict):
    success: bool
    data: Any | None
    error: str | None
```

### Full Type-Safe Example

```python
from typing import Any, TypedDict


class UserData(TypedDict):
    id: int
    name: str
    email: str


class ToolResult(TypedDict):
    success: bool
    data: UserData | None
    error: str | None


async def create_user_typed(
    name: str,
    email: str,
) -> ToolResult:
    """Type-safe tool implementation."""
    try:
        user_id = await db.create_user(name, email)
        return {
            "success": True,
            "data": {"id": user_id, "name": name, "email": email},
            "error": None,
        }
    except ValueError as e:
        return {
            "success": False,
            "data": None,
            "error": str(e),
        }
```

______________________________________________________________________

## Best Practices

### 1. Always Initialize Before Running

```python
# ❌ Wrong
server = create_mcp_server()
server.run()  # Missing initialization

# ✅ Correct
server = create_mcp_server()
await server.initialize()
server.run()
```

### 2. Use Async Functions for Tools

```python
# ❌ Wrong
def sync_tool(param: str) -> dict:  # Not async
    return {"result": param}


# ✅ Correct
async def async_tool(param: str) -> dict:
    return {"result": param}
```

### 3. Handle Errors Gracefully

```python
# ❌ Wrong - swallows all errors
async def bad_tool(param: str) -> dict:
    try:
        return await operation(param)
    except Exception:
        return {}  # Silent failure


# ✅ Correct - specific handling + logging
async def good_tool(param: str) -> dict:
    try:
        result = await operation(param)
        return {"success": True, "data": result}
    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        raise
```

### 4. Use Type Hints Everywhere

```python
# ❌ Wrong - no type hints
async def unclear_tool(a, b):
    return {"x": a + b}


# ✅ Correct - full type hints
async def clear_tool(a: int, b: int) -> dict[str, int]:
    return {"x": a + b}
```

### 5. Register Tools in Bulk

```python
# ❌ Wrong - multiple register calls
await register_tools(server, {"tool1": tool1})
await register_tools(server, {"tool2": tool2})
await register_tools(server, {"tool3": tool3})

# ✅ Correct - single bulk registration
await register_tools(
    server,
    {
        "tool1": tool1,
        "tool2": tool2,
        "tool3": tool3,
    },
)
```

______________________________________________________________________

## Troubleshooting

### Common Errors

#### `AttributeError: 'ACBMCPServer' object has no attribute '_server'`

**Cause**: Server not created via `create_mcp_server()`

**Solution**: Always use the factory function:

```python
server = create_mcp_server()  # ✅ Correct
```

#### `RuntimeError: Server already running`

**Cause**: Attempted to run server multiple times

**Solution**: Only call `run()` once:

```python
server.run()  # First call - OK
server.run()  # Second call - Error!
```

#### `TypeError: Tool must be callable`

**Cause**: Registered non-function as tool

**Solution**: Ensure all tools are async functions:

```python
async def my_tool() -> dict:  # ✅ Callable async function
    return {}
```

______________________________________________________________________

## Migration Guide

### From Direct FastMCP → ACB MCP API

```python
# Before (Direct FastMCP)
from fastmcp import FastMCP

app = FastMCP("my-server")


@app.tool()
async def my_tool() -> dict:
    return {}


app.run()

# After (ACB MCP API)
from acb.mcp import create_mcp_server, register_tools

server = create_mcp_server()


async def my_tool() -> dict:
    return {}


await register_tools(server, {"my_tool": my_tool})
await server.initialize()
server.run()
```

**Benefits of migration**:

- ✅ Automatic rate limiting
- ✅ Component registry access
- ✅ Structured logging
- ✅ Consistent error handling

______________________________________________________________________

## See Also

- **[Plugin Architecture Guide](<./PLUGIN_ARCHITECTURE.md>)**: Complete guide to building ACB plugins
- **[FastBlocks Example](../../fastblocks/docs/ACB_PLUGIN_EXAMPLE.md)**: Reference implementation
- **[ACB Documentation](https://github.com/lesleslie/acb)**: Full ACB framework docs

______________________________________________________________________

**API Version**: 1.0.0
**Maintained By**: ACB Core Team
**License**: MIT
**Support**: GitHub Issues
