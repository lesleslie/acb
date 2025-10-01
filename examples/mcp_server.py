"""Example usage of the ACB MCP Server."""

import asyncio
import contextlib

from acb.mcp import create_mcp_server


async def main() -> None:
    """Example of using the ACB MCP Server."""
    server = create_mcp_server()

    # Initialize the server components
    await server.component_registry.initialize()
    await server.tools.initialize()
    await server.resources.initialize()
    await server.orchestrator.initialize()

    # Example 1: List available components
    components = await server.tools.list_components()
    for _component_type, _component_list in components.items():
        pass

    # Example 2: Execute a simple action (if available)
    with contextlib.suppress(Exception):
        await server.tools.execute_action(
            action_category="compress",
            action_name="brotli",
            data="Hello, ACB MCP Server!",
            level=4,
        )

    # Example 3: Get adapter information
    adapters = server.component_registry.get_adapters()
    for adapter_name in list(adapters.keys())[:3]:  # Limit to first 3 adapters
        with contextlib.suppress(Exception):
            await server.tools.get_adapter_info(adapter_name)

    # Example 4: Define and execute a workflow
    workflow_steps = [
        {
            "name": "step1",
            "type": "action",
            "component": "compress",
            "action": "brotli",
            "parameters": {"data": "Workflow data", "level": 1},
        },
    ]

    with contextlib.suppress(Exception):
        await server.orchestrator.execute_workflow(
            "example_workflow",
            workflow_steps,
        )

    # Example 5: Get system metrics
    with contextlib.suppress(Exception):
        await server.resources.get_system_metrics()

    # Cleanup
    await server.orchestrator.cleanup()
    await server.resources.cleanup()
    await server.tools.cleanup()
    await server.component_registry.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
