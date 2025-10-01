"""FastMCP-based server implementation for ACB.

This module provides a standards-compliant MCP server using FastMCP,
exposing ACB's capabilities through the Model Context Protocol.
"""

from typing import Any

from fastmcp import FastMCP
from acb.config import Config
from acb.depends import depends
from acb.logger import Logger

from .registry import ComponentRegistry

# Create the FastMCP server instance
mcp = FastMCP("ACB MCP Server", version="1.0.0")

# Global component registry instance
_registry: ComponentRegistry | None = None


def get_registry() -> ComponentRegistry:
    """Get or create the component registry."""
    global _registry
    if _registry is None:
        _registry = ComponentRegistry()
    return _registry


# ============================================================================
# TOOLS: Expose ACB actions and adapter operations
# ============================================================================


@mcp.tool()
async def list_components(component_type: str | None = None) -> dict[str, list[str]]:
    """List available ACB components.

    Args:
        component_type: Optional filter by type (actions, adapters, services, events).
                       If None, returns all components.

    Returns:
        Dictionary mapping component types to lists of component names.
    """
    registry = get_registry()
    if not registry._initialized:
        await registry.initialize()

    result = {}

    if not component_type or component_type == "actions":
        actions = registry.get_actions()
        result["actions"] = list(actions.keys())

    if not component_type or component_type == "adapters":
        adapters = registry.get_adapters()
        result["adapters"] = list(adapters.keys())

    if not component_type or component_type == "services":
        services = registry.get_services()
        result["services"] = list(services.keys())

    if not component_type or component_type == "events":
        events = registry.get_events()
        result["events"] = list(events.keys())

    return result


@mcp.tool()
async def execute_action(
    action_category: str,
    action_name: str,
    parameters: dict[str, Any] | None = None,
) -> Any:
    """Execute an ACB action with the given parameters.

    Args:
        action_category: The action category (e.g., 'compress', 'encode', 'hash')
        action_name: The specific action name within the category
        parameters: Dictionary of parameters to pass to the action

    Returns:
        The result of executing the action

    Raises:
        ValueError: If the action category or action name is not found
    """
    import asyncio

    logger: Logger = depends.get(Logger)
    registry = get_registry()
    if not registry._initialized:
        await registry.initialize()

    # Default to empty dict if no parameters provided
    params = parameters or {}

    try:
        # Get the action category
        actions = registry.get_actions()
        category = actions.get(action_category)

        if not category:
            msg = f"Action category '{action_category}' not found"
            raise ValueError(msg)

        # Get the specific action
        action = getattr(category, action_name, None)
        if not action:
            msg = f"Action '{action_name}' not found in category '{action_category}'"
            raise ValueError(msg)

        # Execute the action
        if asyncio.iscoroutinefunction(action):
            result = await action(**params)
        else:
            result = action(**params)

        logger.info(f"Executed action: {action_category}.{action_name}")
        return result
    except Exception as e:
        logger.exception(
            f"Failed to execute action {action_category}.{action_name}: {e}"
        )
        raise


@mcp.tool()
async def get_adapter_info(adapter_name: str) -> dict[str, Any]:
    """Get information about a specific ACB adapter.

    Args:
        adapter_name: Name of the adapter to query

    Returns:
        Dictionary containing adapter metadata and capabilities

    Raises:
        ValueError: If the adapter is not found
    """
    registry = get_registry()
    if not registry._initialized:
        await registry.initialize()

    adapter = registry.get_adapter(adapter_name)
    if not adapter:
        msg = f"Adapter '{adapter_name}' not found"
        raise ValueError(msg)

    # Return adapter information
    info = {
        "name": adapter_name,
        "type": type(adapter).__name__,
        "module": type(adapter).__module__,
    }

    # Include MODULE_METADATA if available
    if hasattr(adapter, "MODULE_METADATA"):
        metadata = adapter.MODULE_METADATA
        info["metadata"] = {
            "module_id": str(metadata.module_id),
            "name": metadata.name,
            "category": metadata.category,
            "provider": metadata.provider,
            "version": metadata.version,
            "status": metadata.status.value
            if hasattr(metadata.status, "value")
            else str(metadata.status),
            "capabilities": [
                cap.value if hasattr(cap, "value") else str(cap)
                for cap in metadata.capabilities
            ],
            "description": metadata.description,
        }

    return info


@mcp.tool()
async def execute_workflow(
    workflow_name: str,
    steps: list[dict[str, Any]],
) -> dict[str, Any]:
    """Execute a multi-step workflow across ACB components.

    Args:
        workflow_name: Name/identifier for this workflow
        steps: List of workflow steps, each containing:
               - name: Step name
               - type: Component type (action, adapter, etc.)
               - component: Component identifier
               - action: Action to execute
               - parameters: Parameters for the action

    Returns:
        Dictionary containing workflow results and metadata
    """
    logger: Logger = depends.get(Logger)
    registry = get_registry()
    if not registry._initialized:
        await registry.initialize()

    try:
        logger.info(f"Starting workflow: {workflow_name}")
        results = {}

        for i, step in enumerate(steps):
            step_name = step.get("name", f"step_{i}")
            component_type = step.get("type")
            component_name = step.get("component")
            action_name = step.get("action")
            parameters = step.get("parameters", {})

            logger.info(f"Executing step {i + 1}/{len(steps)}: {step_name}")

            # Execute based on component type
            if component_type == "action":
                result = await execute_action(component_name, action_name, **parameters)
                results[step_name] = result

        logger.info(f"Workflow '{workflow_name}' completed successfully")
        return {
            "workflow_name": workflow_name,
            "status": "completed",
            "results": results,
        }
    except Exception as e:
        logger.exception(f"Workflow '{workflow_name}' failed: {e}")
        return {
            "workflow_name": workflow_name,
            "status": "failed",
            "error": str(e),
        }


# ============================================================================
# RESOURCES: Expose ACB data and metrics
# ============================================================================


@mcp.resource("registry://components")
async def get_component_registry() -> str:
    """Get the complete component registry.

    Returns:
        JSON string containing all registered components
    """
    import json

    registry = get_registry()
    if not registry._initialized:
        await registry.initialize()

    data = {
        "actions": list(registry.get_actions().keys()),
        "adapters": list(registry.get_adapters().keys()),
        "services": list(registry.get_services().keys()),
        "events": list(registry.get_events().keys()),
    }
    return json.dumps(data, indent=2)


@mcp.resource("metrics://system")
async def get_system_metrics() -> str:
    """Get current system metrics.

    Returns:
        JSON string containing system metrics
    """
    import asyncio
    import json

    registry = get_registry()
    if not registry._initialized:
        await registry.initialize()

    data = {
        "timestamp": asyncio.get_event_loop().time(),
        "component_count": {
            "actions": len(registry.get_actions()),
            "adapters": len(registry.get_adapters()),
            "services": len(registry.get_services()),
            "events": len(registry.get_events()),
        },
    }
    return json.dumps(data, indent=2)


@mcp.resource("config://app")
async def get_app_config() -> str:
    """Get application configuration.

    Returns:
        JSON string containing application configuration
    """
    import json

    config: Config = depends.get(Config)

    # Return safe configuration data (exclude secrets)
    data = {
        "name": getattr(config, "name", "ACB"),
        "version": getattr(config, "version", "unknown"),
        "debug": getattr(config, "debug", False),
    }
    return json.dumps(data, indent=2)


# ============================================================================
# Server Lifecycle Management
# ============================================================================


class ACBMCPServer:
    """ACB MCP Server wrapper for lifecycle management."""

    def __init__(self) -> None:
        """Initialize the MCP server wrapper."""
        self.registry = get_registry()
        self._logger: Logger | None = None

    @property
    def logger(self) -> Logger:
        """Lazy-initialize logger."""
        if self._logger is None:
            self._logger = depends.get(Logger)
        return self._logger

    async def initialize(self) -> None:
        """Initialize the server and components."""
        try:
            self.logger.info("Initializing ACB MCP Server")
        except Exception:
            # Logger may not be initialized yet
            pass
        await self.registry.initialize()
        try:
            self.logger.info("ACB MCP Server initialized")
        except Exception:
            pass

    def run(self, transport: str = "stdio", **kwargs: Any) -> None:
        """Run the MCP server.

        Args:
            transport: Transport protocol ('stdio', 'sse', 'http')
            **kwargs: Additional arguments for the transport
        """
        try:
            self.logger.info(f"Starting ACB MCP Server with {transport} transport")
        except Exception:
            # Logger may not be available yet
            pass
        mcp.run(transport=transport, **kwargs)

    async def cleanup(self) -> None:
        """Clean up server resources."""
        try:
            self.logger.info("Cleaning up ACB MCP Server")
        except Exception:
            pass
        await self.registry.cleanup()
        try:
            self.logger.info("ACB MCP Server cleaned up")
        except Exception:
            pass


def create_mcp_server() -> ACBMCPServer:
    """Create and return an ACB MCP server instance.

    Returns:
        Configured ACBMCPServer instance ready to run
    """
    return ACBMCPServer()


# For backwards compatibility
ACMCPServer = ACBMCPServer
