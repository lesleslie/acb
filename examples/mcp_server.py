"""Example usage of the ACB MCP Server."""

import asyncio

from acb.mcp import create_mcp_server


async def main():
    """Example of using the ACB MCP Server."""
    print("Creating ACB MCP Server...")
    server = create_mcp_server()

    # Initialize the server components
    await server.component_registry.initialize()
    await server.tools.initialize()
    await server.resources.initialize()
    await server.orchestrator.initialize()

    print("ACB MCP Server components initialized.")

    # Example 1: List available components
    print("\n1. Listing available components:")
    components = await server.tools.list_components()
    for component_type, component_list in components.items():
        print(f"  {component_type}: {component_list}")

    # Example 2: Execute a simple action (if available)
    print("\n2. Executing a compression action:")
    try:
        result = await server.tools.execute_action(
            action_category="compress",
            action_name="brotli",
            data="Hello, ACB MCP Server!",
            level=4,
        )
        print(
            f"  Compression result: {result[:50]}..."
            if len(str(result)) > 50
            else f"  Compression result: {result}"
        )
    except Exception as e:
        print(f"  Action execution failed: {e}")

    # Example 3: Get adapter information
    print("\n3. Getting adapter information:")
    adapters = server.component_registry.get_adapters()
    for adapter_name in list(adapters.keys())[:3]:  # Limit to first 3 adapters
        try:
            info = await server.tools.get_adapter_info(adapter_name)
            print(f"  {adapter_name}: {info}")
        except Exception as e:
            print(f"  Failed to get info for {adapter_name}: {e}")

    # Example 4: Define and execute a workflow
    print("\n4. Defining and executing a workflow:")
    workflow_steps = [
        {
            "name": "step1",
            "type": "action",
            "component": "compress",
            "action": "brotli",
            "parameters": {"data": "Workflow data", "level": 1},
        }
    ]

    try:
        workflow_result = await server.orchestrator.execute_workflow(
            "example_workflow", workflow_steps
        )
        print(f"  Workflow result: {workflow_result}")
    except Exception as e:
        print(f"  Workflow execution failed: {e}")

    # Example 5: Get system metrics
    print("\n5. Getting system metrics:")
    try:
        metrics = await server.resources.get_system_metrics()
        print(f"  System metrics: {metrics}")
    except Exception as e:
        print(f"  Failed to get metrics: {e}")

    # Cleanup
    await server.orchestrator.cleanup()
    await server.resources.cleanup()
    await server.tools.cleanup()
    await server.component_registry.cleanup()

    print("\nACB MCP Server example completed.")


if __name__ == "__main__":
    asyncio.run(main())
