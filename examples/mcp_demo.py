"""Comprehensive demo of ACB MCP Server capabilities.

This example demonstrates all the features of the FastMCP-based ACB server.
"""

import asyncio

from acb.mcp import create_mcp_server


async def demo_server_capabilities() -> None:
    """Demonstrate the capabilities of the ACB MCP Server."""
    # Create and initialize the server
    server = create_mcp_server()  # type: ignore
    await server.initialize()

    print("=" * 70)
    print("ACB MCP Server - FastMCP Integration Demo")
    print("=" * 70)

    # Demo 1: List all registered tools
    print("\n1. Registered MCP Tools:")
    print("-" * 70)
    for tool_name in (
        "list_components",
        "execute_action",
        "get_adapter_info",
        "execute_workflow",
    ):
        print(f"   ✓ {tool_name}")

    # Demo 2: List all registered resources
    print("\n2. Registered MCP Resources:")
    print("-" * 70)
    for resource_uri in ("registry://components", "metrics://system", "config://app"):
        print(f"   ✓ {resource_uri}")

    # Demo 3: Component discovery
    print("\n3. Component Discovery:")
    print("-" * 70)
    try:
        from acb.mcp.server import list_components

        list_components_fn = list_components  # type: ignore

        components = await list_components_fn()  # type: ignore
        for component_type, component_list in components.items():
            print(f"\n   {component_type.upper()}:")
            for component in component_list[:5]:  # Show first 5
                print(f"      - {component}")
            if len(component_list) > 5:
                print(f"      ... and {len(component_list) - 5} more")
    except Exception as e:
        print(f"   ℹ Component discovery demo: {e}")

    # Demo 4: Execute a sample action
    print("\n4. Action Execution Example:")
    print("-" * 70)
    try:
        from acb.mcp.server import execute_action

        execute_action_fn = execute_action  # type: ignore

        # Example: compress data with brotli
        result = await execute_action_fn(  # type: ignore
            action_category="compress",
            action_name="brotli",
            data=b"Hello, ACB MCP Server with FastMCP!",
            level=4,
        )
        print(f"   ✓ Compressed data: {len(result)} bytes")
    except Exception as e:
        print(f"   ℹ Action execution demo: {e}")

    # Demo 5: Workflow execution
    print("\n5. Workflow Execution Example:")
    print("-" * 70)
    workflow_steps = [
        {
            "name": "compress_step",
            "type": "action",
            "component": "compress",
            "action": "brotli",
            "parameters": {"data": b"Workflow test data", "level": 1},
        },
    ]
    try:
        from acb.mcp.server import execute_workflow

        execute_workflow_fn = execute_workflow  # type: ignore

        workflow_result = await execute_workflow_fn("demo_workflow", workflow_steps)  # type: ignore
        print(f"   ✓ Workflow status: {workflow_result.get('status')}")
    except Exception as e:
        print(f"   ℹ Workflow execution demo: {e}")

    # Demo 6: Resource access
    print("\n6. Resource Access Example:")
    print("-" * 70)
    try:
        from acb.mcp.server import get_system_metrics

        get_system_metrics_fn = get_system_metrics  # type: ignore

        metrics = await get_system_metrics_fn()  # type: ignore
        print("   ✓ System metrics retrieved (JSON formatted)")
        print(f"   {metrics[:100]}...")
    except Exception as e:
        print(f"   ℹ Resource access demo: {e}")

    print("\n" + "=" * 70)
    print("Demo Complete!")
    print("=" * 70)
    print("\nTo run this server with Claude Desktop:")
    print("  server.run(transport='stdio')")
    print("\nTo run this server with HTTP/SSE:")
    print("  server.run(transport='sse', host='127.0.0.1', port=8000)")
    print("=" * 70)

    # Cleanup
    await server.cleanup()


if __name__ == "__main__":
    asyncio.run(demo_server_capabilities())
