# ACB MCP Plugin Architecture

**Version**: 1.0.0
**Status**: Production Ready
**Last Updated**: 2025-01-27

______________________________________________________________________

## Overview

The ACB (Asynchronous Component Base) framework provides a plugin architecture that allows external projects to extend ACB's MCP (Model Context Protocol) server with their own tools and resources. This enables modular, composable MCP servers that inherit ACB's infrastructure while adding domain-specific functionality.

### Key Benefits

- ✅ **Infrastructure Reuse**: Inherit rate limiting, security, and logging from ACB
- ✅ **Modular Design**: Each plugin is self-contained with its own tools/resources
- ✅ **Type Safety**: Full Python 3.13+ type hints throughout
- ✅ **Async-First**: Built on FastMCP's async foundation
- ✅ **Zero Config**: Plugins work out-of-the-box with sensible defaults

______________________________________________________________________

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                   Plugin Project                        │
│                  (e.g., FastBlocks)                     │
│                                                         │
│  ┌────────────────────────────────────────────┐       │
│  │  Plugin MCP Server                         │       │
│  │  - Inherits from ACB infrastructure        │       │
│  │  - Registers domain-specific tools         │       │
│  │  - Registers domain-specific resources     │       │
│  └────────────────────────────────────────────┘       │
│                        │                                │
│                        │ uses                           │
│                        ▼                                │
│  ┌────────────────────────────────────────────┐       │
│  │  ACB MCP Plugin API                        │       │
│  │  - create_mcp_server()                     │       │
│  │  - register_tools()                        │       │
│  │  - register_resources()                    │       │
│  └────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────┘
                        │
                        │ extends
                        ▼
┌─────────────────────────────────────────────────────────┐
│                  ACB MCP Server                         │
│                  (Base Infrastructure)                  │
│                                                         │
│  ┌────────────────────────────────────────────┐       │
│  │  FastMCP Instance                          │       │
│  │  - Rate Limiting (15 req/sec, burst 40)    │       │
│  │  - Component Registry                      │       │
│  │  - Action Execution                        │       │
│  │  - Workflow Orchestration                  │       │
│  └────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────┘
```

______________________________________________________________________

## Core Concepts

### 1. Plugin Server Structure

A plugin MCP server has three main components:

```python
from acb.mcp import create_mcp_server, register_tools, register_resources


class MyPluginMCPServer:
    """Plugin server extending ACB infrastructure."""

    def __init__(self, name: str = "My Plugin", version: str = "1.0.0"):
        self.name = name
        self.version = version

        # Create ACB MCP server instance (inherits rate limiting)
        self._server = create_mcp_server()

    async def initialize(self) -> None:
        """Initialize plugin-specific tools and resources."""
        await self._register_tools()
        await self._register_resources()

    async def _register_tools(self) -> None:
        """Register plugin-specific MCP tools."""
        # ... implementation

    async def _register_resources(self) -> None:
        """Register plugin-specific MCP resources."""
        # ... implementation
```

### 2. Tool Registration

Tools are async functions that execute actions:

```python
async def my_tool(param: str) -> dict[str, str]:
    """Example tool implementation."""
    return {"result": f"Processed: {param}"}


# Register with ACB server
tools = {
    "my_tool": my_tool,
    "another_tool": another_tool,
}
await register_tools(server, tools)
```

### 3. Resource Registration

Resources provide documentation/data access:

```python
async def get_api_docs() -> str:
    """Return API documentation as markdown."""
    return "# API Documentation\\n..."


# Register with ACB server
resources = {
    "api_docs": get_api_docs,
    "schemas": get_schemas,
}
await register_resources(server, resources)
```

______________________________________________________________________

## Inheritance Model

### What Plugins Inherit from ACB

1. **Rate Limiting** (automatic)

   - 15 requests/second sustainable rate
   - Burst capacity of 40 requests
   - Global rate limiting enabled by default

1. **Component Registry**

   - Access to ACB actions (compress, encode, hash, etc.)
   - Adapter integration (HTTP, WebSocket, etc.)
   - Service orchestration

1. **FastMCP Infrastructure**

   - Async request handling
   - Tool/resource decorators
   - Transport layer (STDIO, HTTP, SSE)

1. **Logging & Observability**

   - Structured logging via ACB logger
   - Error tracking and reporting

### What Plugins Provide

1. **Domain-Specific Tools**

   - Plugin-specific MCP tool implementations
   - Custom validation and error handling

1. **Domain-Specific Resources**

   - API documentation
   - Configuration schemas
   - Best practices guides

1. **Custom Initialization**

   - Plugin-specific setup logic
   - External service connections

______________________________________________________________________

## Reference Implementation: FastBlocks

FastBlocks is the reference implementation of an ACB MCP plugin. See:

- **Source**: `/Users/les/Projects/fastblocks/fastblocks/mcp/`
- **Documentation**: `/Users/les/Projects/fastblocks/docs/ACB_PLUGIN_EXAMPLE.md`

### FastBlocks Structure

```
fastblocks/mcp/
├── server.py           # Plugin server class
├── tools.py            # Tool implementations + registration
├── resources.py        # Resource implementations + registration
└── README.md           # Plugin-specific documentation
```

### Key FastBlocks Patterns

1. **Server Initialization**:

   ```python
   class FastBlocksMCPServer:
       def __init__(self, name: str = "FastBlocks"):
           # Create ACB server (inherits rate limiting)
           self._server = create_mcp_server()
   ```

1. **Tool Registration**:

   ```python
   async def register_fastblocks_tools(server: Any) -> None:
       from acb.mcp import register_tools

       tools = {
           "create_template": create_template,
           "validate_template": validate_template,
           # ...
       }
       await register_tools(server, tools)
   ```

1. **Resource Registration**:

   ```python
   async def register_fastblocks_resources(server: Any) -> None:
       from acb.mcp import register_resources

       resources = {
           "template_syntax": get_template_syntax_reference,
           "component_catalog": get_htmy_component_catalog,
           # ...
       }
       await register_resources(server, resources)
   ```

______________________________________________________________________

## API Contracts

### `create_mcp_server()` Contract

```python
def create_mcp_server() -> ACBMCPServer:
    """Create ACB MCP server instance.

    Returns:
        ACBMCPServer instance with:
        - _server attribute (FastMCP instance)
        - Rate limiting enabled (15 req/sec, burst 40)
        - Component registry initialized

    Example:
        >>> server = create_mcp_server()
        >>> server._server  # FastMCP instance
    """
```

### `register_tools()` Contract

```python
async def register_tools(
    server: ACBMCPServer,
    tools: dict[str, Callable[..., Awaitable[Any]]],
) -> None:
    """Register tools with ACB MCP server.

    Args:
        server: ACBMCPServer instance with _server attribute
        tools: Dict mapping tool names to async functions

    Raises:
        AttributeError: If server lacks _server attribute
        ValueError: If any tool is not callable

    Example:
        >>> async def my_tool(param: str) -> dict:
        ...     return {"result": param}
        >>> await register_tools(server, {"my_tool": my_tool})
    """
```

### `register_resources()` Contract

```python
async def register_resources(
    server: ACBMCPServer,
    resources: dict[str, Callable[..., Awaitable[str]]],
) -> None:
    """Register resources with ACB MCP server.

    Args:
        server: ACBMCPServer instance with _server attribute
        resources: Dict mapping resource URIs to async functions

    Raises:
        AttributeError: If server lacks _server attribute
        ValueError: If any resource is not callable

    Example:
        >>> async def api_docs() -> str:
        ...     return "# API Docs"
        >>> await register_resources(server, {"api_docs": api_docs})
    """
```

______________________________________________________________________

## Development Guidelines

### 1. Plugin Project Structure

```
my-plugin-mcp/
├── my_plugin_mcp/
│   ├── mcp/
│   │   ├── __init__.py
│   │   ├── server.py       # Plugin server class
│   │   ├── tools.py        # Tool implementations
│   │   └── resources.py    # Resource implementations
│   ├── config.py           # Plugin configuration
│   └── ...
├── tests/
│   └── test_mcp_integration.py
├── pyproject.toml
└── README.md
```

### 2. Dependencies

Add ACB to your plugin's dependencies:

```toml
[project]
dependencies = [
    "acb>=1.0.0",  # ACB framework
    "fastmcp>=2.0.0",  # MCP protocol
]
```

### 3. Type Hints

Use comprehensive type hints:

```python
from typing import Any, Callable, Awaitable


async def my_tool(
    param1: str,
    param2: int | None = None,
) -> dict[str, Any]:
    """Tool with full type hints."""
    ...
```

### 4. Error Handling

Handle errors gracefully in tools:

```python
async def risky_tool(param: str) -> dict[str, Any]:
    try:
        result = await perform_operation(param)
        return {"success": True, "data": result}
    except SpecificError as e:
        logger.error(f"Expected error: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        raise  # Re-raise unexpected errors
```

### 5. Testing

Test plugin integration:

```python
import pytest
from acb.mcp import create_mcp_server, register_tools


@pytest.mark.asyncio
async def test_plugin_tools_register():
    server = create_mcp_server()

    async def test_tool(param: str) -> dict:
        return {"param": param}

    await register_tools(server, {"test_tool": test_tool})
    # Tool is now registered with server._server
    assert test_tool.__name__ in str(server._server._mcp_server.tools)
```

______________________________________________________________________

## Migration Guide

### From Standalone MCP Server → ACB Plugin

**Before** (standalone):

```python
from fastmcp import FastMCP

app = FastMCP("my-server")


@app.tool()
async def my_tool(param: str) -> dict:
    return {"result": param}


app.run()
```

**After** (ACB plugin):

```python
from acb.mcp import create_mcp_server, register_tools

server = create_mcp_server()  # Inherits rate limiting


async def my_tool(param: str) -> dict:
    return {"result": param}


await register_tools(server, {"my_tool": my_tool})

server.run()  # Use ACB server's run method
```

**Benefits**:

- ✅ Automatic rate limiting (15 req/sec, burst 40)
- ✅ Access to ACB component registry
- ✅ Structured logging
- ✅ Consistent error handling

______________________________________________________________________

## Troubleshooting

### Issue: `AttributeError: 'ACBMCPServer' object has no attribute '_server'`

**Cause**: Server not created via `create_mcp_server()`

**Solution**:

```python
# ❌ Wrong
server = ACBMCPServer()  # Missing FastMCP instance

# ✅ Correct
server = create_mcp_server()  # Creates with _server attribute
```

### Issue: `ImportError: cannot import name 'register_tools'`

**Cause**: ACB version too old

**Solution**:

```bash
uv add "acb>=1.0.0"  # Ensure recent version
```

### Issue: Tool registration fails silently

**Cause**: Tool is not async or not callable

**Solution**:

```python
# ❌ Wrong
def my_tool(param: str) -> dict:  # Not async
    return {"result": param}


# ✅ Correct
async def my_tool(param: str) -> dict:  # Async function
    return {"result": param}
```

______________________________________________________________________

## FAQ

**Q: Can I override ACB's rate limiting?**
A: Not currently. Rate limiting is configured at the ACB server level (15 req/sec, burst 40). If you need different limits, consider forking ACB or requesting a configuration API.

**Q: Can I access ACB's component registry from my plugin?**
A: Yes! Use dependency injection:

```python
from acb.depends import depends
from acb.mcp import ComponentRegistry

registry = depends.get(ComponentRegistry)
actions = registry.get_actions()
```

**Q: Should my plugin have its own FastMCP instance?**
A: No. Always use `create_mcp_server()` to get an ACB server instance. This ensures you inherit ACB's infrastructure.

**Q: Can I create multiple plugin servers?**
A: Yes, but each creates a separate ACB server instance with its own rate limiting. Consider using a single server with multiple tool namespaces instead.

______________________________________________________________________

## Resources

- **FastBlocks Reference Implementation**: `/Users/les/Projects/fastblocks/`
- **ACB MCP API Reference**: `/Users/les/Projects/acb/docs/MCP_API.md`
- **Plugin Example**: `/Users/les/Projects/fastblocks/docs/ACB_PLUGIN_EXAMPLE.md`
- **ACB Framework**: `/Users/les/Projects/acb/`

______________________________________________________________________

**Maintained by**: ACB Core Team
**License**: MIT
**Contributions**: Welcome via GitHub PRs
