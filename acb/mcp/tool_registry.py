"""Tool and resource registration utilities for ACB MCP server.

This module provides functions to dynamically register tools and resources
with an ACB MCP server instance, primarily used by plugin servers like FastBlocks.
"""

from __future__ import annotations

import typing as t


async def register_tools(
    server: t.Any,
    tools: dict[str, t.Callable[..., t.Awaitable[t.Any]]],
) -> None:
    """Register tools with ACB MCP server.

    This function enables plugin servers (like FastBlocks) to dynamically
    register their MCP tools with an ACB-based server instance.

    Args:
        server: ACBMCPServer instance with `_server` attribute (FastMCP instance)
        tools: Dict mapping tool names to async functions

    Raises:
        AttributeError: If server doesn't have `_server` attribute
        ValueError: If any tool is not a callable

    Example:
        ```python
        from acb.mcp import create_mcp_server, register_tools

        server = create_mcp_server()


        async def my_tool(param: str) -> dict[str, str]:
            return {"result": f"Processed: {param}"}


        await register_tools(server, {"my_tool": my_tool})
        ```
    """
    if not hasattr(server, "_server"):
        msg = "Server instance must have '_server' attribute (FastMCP instance)"
        raise AttributeError(msg)

    # Access the FastMCP instance
    fastmcp_instance = server._server

    # Register each tool using FastMCP decorator
    for name, func in tools.items():
        if not callable(func):
            msg = f"Tool '{name}' must be a callable, got {type(func)}"
            raise ValueError(msg)

        # Apply FastMCP tool decorator
        fastmcp_instance.tool()(func)


async def register_resources(
    server: t.Any,
    resources: dict[str, t.Callable[..., t.Awaitable[str]]],
) -> None:
    r"""Register resources with ACB MCP server.

    This function enables plugin servers to dynamically register their
    MCP resources (documentation, schemas, etc.) with an ACB-based server instance.

    Args:
        server: ACBMCPServer instance with `_server` attribute (FastMCP instance)
        resources: Dict mapping resource URIs to async functions returning strings

    Raises:
        AttributeError: If server doesn't have `_server` attribute
        ValueError: If any resource is not a callable

    Example:
        ```python
        from acb.mcp import create_mcp_server, register_resources

        server = create_mcp_server()


        async def api_docs() -> str:
            return "# API Documentation\\n..."


        await register_resources(server, {"api_docs": api_docs})
        ```
    """
    if not hasattr(server, "_server"):
        msg = "Server instance must have '_server' attribute (FastMCP instance)"
        raise AttributeError(msg)

    # Access the FastMCP instance
    fastmcp_instance = server._server

    # Register each resource using FastMCP decorator
    for uri, func in resources.items():
        if not callable(func):
            msg = f"Resource '{uri}' must be a callable, got {type(func)}"
            raise ValueError(msg)

        # Apply FastMCP resource decorator
        fastmcp_instance.resource(uri)(func)
