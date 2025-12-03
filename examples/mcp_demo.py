"""Comprehensive demo of ACB MCP Server capabilities.

This example demonstrates all the features of the FastMCP-based ACB server.
"""

import asyncio
from contextlib import suppress

from acb.mcp import create_mcp_server


async def demo_server_capabilities() -> None:
    """Demonstrate the capabilities of the ACB MCP Server."""
    # Create and initialize the server
    server = create_mcp_server()  # type: ignore
    await server.initialize()

    # Demo 1: List all registered tools
    for _tool_name in (
        "list_components",
        "execute_action",
        "get_adapter_info",
        "execute_workflow",
    ):
        pass

    # Demo 2: List all registered resources
    for _resource_uri in ("registry://components", "metrics://system", "config://app"):
        pass

    # Demo 3: Component discovery
    with suppress(Exception):
        from acb.mcp.server import list_components

        list_components_fn = list_components  # type: ignore

        components = await list_components_fn()  # type: ignore
        for component_list in components.values():
            for _component in component_list[:5]:  # Show first 5
                pass
            if len(component_list) > 5:
                pass

    # Demo 4: Execute a sample action
    with suppress(Exception):
        from acb.mcp.server import execute_action

        execute_action_fn = execute_action  # type: ignore

        # Example: compress data with brotli
        await execute_action_fn(  # type: ignore
            action_category="compress",
            action_name="brotli",
            data=b"Hello, ACB MCP Server with FastMCP!",
            level=4,
        )

    # Demo 5: Workflow execution
    workflow_steps = [
        {
            "name": "compress_step",
            "type": "action",
            "component": "compress",
            "action": "brotli",
            "parameters": {"data": b"Workflow test data", "level": 1},
        },
    ]
    with suppress(Exception):
        from acb.mcp.server import execute_workflow

        execute_workflow_fn = execute_workflow  # type: ignore

        await execute_workflow_fn("demo_workflow", workflow_steps)  # type: ignore

    # Demo 6: Resource access
    with suppress(Exception):
        from acb.mcp.server import get_system_metrics

        get_system_metrics_fn = get_system_metrics  # type: ignore

        await get_system_metrics_fn()  # type: ignore

    # Cleanup
    await server.cleanup()


if __name__ == "__main__":
    asyncio.run(demo_server_capabilities())
