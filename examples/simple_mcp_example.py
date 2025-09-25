"""Simple example of using the ACB MCP Server."""

import asyncio

from acb.mcp import create_mcp_server


async def main():
    """Simple example of using the ACB MCP Server."""
    print("Creating ACB MCP Server...")
    server = create_mcp_server()

    # Initialize the server components
    await server.component_registry.initialize()
    await server.tools.initialize()
    await server.resources.initialize()
    await server.orchestrator.initialize()

    print("ACB MCP Server components initialized.")

    # List available components
    print("\nListing available components:")
    components = await server.tools.list_components()
    for component_type, component_list in components.items():
        print(f"  {component_type}: {component_list}")

    # Cleanup
    await server.orchestrator.cleanup()
    await server.resources.cleanup()
    await server.tools.cleanup()
    await server.component_registry.cleanup()

    print("\nACB MCP Server example completed.")


if __name__ == "__main__":
    asyncio.run(main())
