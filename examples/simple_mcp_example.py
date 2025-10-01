"""Simple example of using the ACB MCP Server."""

import asyncio

from acb.mcp import create_mcp_server


async def main() -> None:
    """Simple example of using the ACB MCP Server."""
    server = create_mcp_server()

    # Initialize the server components
    await server.component_registry.initialize()
    await server.tools.initialize()
    await server.resources.initialize()
    await server.orchestrator.initialize()

    # List available components
    components = await server.tools.list_components()
    for _component_type, _component_list in components.items():
        pass

    # Cleanup
    await server.orchestrator.cleanup()
    await server.resources.cleanup()
    await server.tools.cleanup()
    await server.component_registry.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
