"""MCP tools implementation for ACB."""

import asyncio
from typing import TYPE_CHECKING, Any

from acb.depends import depends
from acb.logger import Logger

if TYPE_CHECKING:
    from acb.adapters.logger import LoggerProtocol

from .registry import ComponentRegistry


class ACBMCPTools:
    """MCP tools implementation for ACB."""

    def __init__(self, component_registry: ComponentRegistry) -> None:
        """Initialize the MCP tools."""
        self.component_registry = component_registry
        self.logger: LoggerProtocol = depends.get(Logger)  # type: ignore[assignment]
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the MCP tools."""
        if self._initialized:
            return

        self.logger.info("Initializing ACB MCP Tools")
        # Tool initialization logic would go here
        self._initialized = True
        self.logger.info("ACB MCP Tools initialized")

    async def list_components(
        self,
        component_type: str | None = None,
    ) -> dict[str, list[str]]:
        """List available components of a specific type or all components."""
        result = {}

        if not component_type or component_type == "actions":
            actions = self.component_registry.get_actions()
            result["actions"] = list(actions.keys())

        if not component_type or component_type == "adapters":
            adapters = self.component_registry.get_adapters()
            result["adapters"] = list(adapters.keys())

        if not component_type or component_type == "services":
            services = self.component_registry.get_services()
            result["services"] = list(services.keys())

        return result

    async def execute_action(
        self,
        action_category: str,
        action_name: str,
        **kwargs: Any,
    ) -> Any:
        """Execute a specific action with the given parameters."""
        try:
            # Get the action category
            actions = self.component_registry.get_actions()
            category = actions.get(action_category)

            if not category:
                msg = f"Action category '{action_category}' not found"
                raise ValueError(msg)

            # Get the specific action
            action = getattr(category, action_name, None)
            if not action:
                msg = (
                    f"Action '{action_name}' not found in category '{action_category}'"
                )
                raise ValueError(
                    msg,
                )

            # Execute the action
            if asyncio.iscoroutinefunction(action):
                result = await action(**kwargs)
            else:
                result = action(**kwargs)

            self.logger.info(f"Executed action: {action_category}.{action_name}")
            return result
        except Exception as e:
            self.logger.exception(
                f"Failed to execute action {action_category}.{action_name}: {e}",
            )
            raise

    async def get_adapter_info(self, adapter_name: str) -> dict[str, Any]:
        """Get information about a specific adapter."""
        adapter = self.component_registry.get_adapter(adapter_name)
        if not adapter:
            msg = f"Adapter '{adapter_name}' not found"
            raise ValueError(msg)

        # Return adapter information
        info = {
            "name": adapter_name,
            "type": type(adapter).__name__,
            "module": type(adapter).__module__,
        }

        # Add health check info if available
        if hasattr(adapter, "health_check"):
            try:
                health_result = await adapter.health_check()
                info["health"] = (
                    health_result.dict()
                    if hasattr(health_result, "dict")
                    else str(health_result)
                )
            except Exception as e:
                info["health_error"] = str(e)

        return info

    async def cleanup(self) -> None:
        """Clean up the MCP tools."""
        self._initialized = False
        self.logger.info("ACB MCP Tools cleaned up")
