"""FastMCP-based server implementation for ACB.

This module provides a standards-compliant MCP server using FastMCP,
exposing ACB's capabilities through the Model Context Protocol.
"""

import importlib.util
from collections.abc import Awaitable, Callable

import typing as t
from contextlib import suppress
from fastmcp import FastMCP
from typing import Any

from acb.adapters.logger import LoggerProtocol
from acb.config import Config
from acb.depends import depends
from acb.logger import Logger

from .registry import ComponentRegistry

# Check FastMCP rate limiting middleware availability (Phase 3.3 M2: improved pattern)
RATE_LIMITING_AVAILABLE = (
    importlib.util.find_spec("fastmcp.server.middleware.rate_limiting") is not None
)

# Check mcp-common ServerPanels availability (Phase 3.3 M2: improved pattern)
SERVERPANELS_AVAILABLE = importlib.util.find_spec("mcp_common.ui") is not None

# Create the FastMCP server instance
mcp = FastMCP("ACB MCP Server", version="1.0.0")

# Add rate limiting middleware (Phase 3 Security Hardening)
if RATE_LIMITING_AVAILABLE:
    from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware

    rate_limiter = RateLimitingMiddleware(
        max_requests_per_second=15.0,  # Sustainable rate for framework operations
        burst_capacity=40,  # Allow bursts for component execution
        global_limit=True,  # Protect the ACB framework server globally
    )
    # Use public API (Phase 3.1 C1 fix: standardize middleware access)
    mcp.add_middleware(rate_limiter)

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

    logger: LoggerProtocol = depends.get(Logger)  # type: ignore[assignment]
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
    info: dict[str, Any] = {
        "name": adapter_name,
        "type": type(adapter).__name__,
        "module": type(adapter).__module__,
    }

    # Include MODULE_METADATA if available
    if hasattr(adapter, "MODULE_METADATA"):
        metadata = adapter.MODULE_METADATA
        metadata_dict: dict[str, Any] = {
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
        info["metadata"] = metadata_dict

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
    logger: LoggerProtocol = depends.get(Logger)  # type: ignore[assignment]
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
            if component_type == "action" and component_name and action_name:
                exec_action: Callable[
                    [str, str, dict[str, Any] | None], Awaitable[Any]
                ] = t.cast(
                    Callable[[str, str, dict[str, Any] | None], Awaitable[Any]],
                    execute_action,
                )  # type: ignore[no-redef]
                result = await exec_action(component_name, action_name, parameters)
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
    import json

    import asyncio

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

    config: Config = depends.get(Config)  # type: ignore[assignment]

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
        self._logger: LoggerProtocol | None = None

    @property
    def logger(self) -> LoggerProtocol:
        """Lazy-initialize logger."""
        if self._logger is None:
            self._logger = depends.get(Logger)  # type: ignore[assignment]
        return self._logger  # type: ignore[return-value]

    async def initialize(self) -> None:
        """Initialize the server and components."""
        with suppress(Exception):
            self.logger.info("Initializing ACB MCP Server")
        await self.registry.initialize()
        with suppress(Exception):
            self.logger.info("ACB MCP Server initialized")

    def run(self, transport: str = "stdio", **kwargs: Any) -> None:
        """Run the MCP server.

        Args:
            transport: Transport protocol ('stdio', 'sse', 'http')
            **kwargs: Additional arguments for the transport
        """
        # Display beautiful startup message with ServerPanels (or fallback to plain text)
        if SERVERPANELS_AVAILABLE:
            from mcp_common.ui import ServerPanels

            features = [
                "🔧 Component Management",
                "⚙️  Action Execution",
                "📦 Adapter Integration",
                "🎯 Event Orchestration",
                "🔌 Service Registry",
            ]
            if RATE_LIMITING_AVAILABLE:
                features.append("⚡ Rate Limiting (15 req/sec, burst 40)")

            if transport in ("http", "sse"):
                # HTTP/SSE mode display
                host = kwargs.get("host", "127.0.0.1")
                port = kwargs.get("port", 8080)
                ServerPanels.startup_success(
                    server_name="ACB MCP Server",
                    version="1.0.0",
                    features=features,
                    endpoint=f"http://{host}:{port}",
                    transport="HTTP (streamable)" if transport == "http" else "SSE",
                )
            else:
                # STDIO mode display
                ServerPanels.startup_success(
                    server_name="ACB MCP Server",
                    version="1.0.0",
                    features=features,
                    transport="STDIO",
                    mode="Claude Desktop",
                )
        else:
            # Fallback to simple logging
            with suppress(Exception):
                self.logger.info(f"Starting ACB MCP Server with {transport} transport")

        mcp.run(transport=transport, **kwargs)  # type: ignore[arg-type]

    async def cleanup(self) -> None:
        """Clean up server resources."""
        with suppress(Exception):
            self.logger.info("Cleaning up ACB MCP Server")
        await self.registry.cleanup()
        with suppress(Exception):
            self.logger.info("ACB MCP Server cleaned up")


def create_mcp_server() -> ACBMCPServer:
    """Create and return an ACB MCP server instance.

    Returns:
        Configured ACBMCPServer instance ready to run
    """
    return ACBMCPServer()


# For backwards compatibility
ACMCPServer = ACBMCPServer
