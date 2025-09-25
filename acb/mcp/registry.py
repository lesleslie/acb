"""Component registry for ACB MCP server."""

from typing import Any

from acb.adapters import import_adapter
from acb.config import Config
from acb.depends import depends
from acb.logger import Logger


class ComponentRegistry:
    """Registry for ACB components exposed through MCP."""

    def __init__(self):
        """Initialize the component registry."""
        self.config: Config = depends.get(Config)
        self.logger: Logger = depends.get(Logger)
        self._actions: dict[str, Any] = {}
        self._adapters: dict[str, Any] = {}
        self._services: dict[str, Any] = {}
        self._events: dict[str, Any] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the component registry."""
        if self._initialized:
            return

        self.logger.info("Initializing ACB Component Registry")

        # Register built-in actions
        await self._register_builtin_actions()

        # Register configured adapters
        await self._register_configured_adapters()

        # Register services (when implemented)
        await self._register_services()

        self._initialized = True
        self.logger.info("ACB Component Registry initialized")

    async def _register_builtin_actions(self) -> None:
        """Register built-in ACB actions."""
        try:
            # Compression actions
            from acb.actions import compress

            self._actions["compress"] = compress

            # Encoding actions
            from acb.actions import encode

            self._actions["encode"] = encode

            # Hashing actions
            from acb.actions import hash

            self._actions["hash"] = hash

            # Add more actions as needed
            self.logger.debug(f"Registered {len(self._actions)} action categories")
        except Exception as e:
            self.logger.warning(f"Failed to register some actions: {e}")

    async def _register_configured_adapters(self) -> None:
        """Register adapters configured in the system."""
        try:
            # Get configured adapters from settings
            adapter_configs = getattr(self.config, "adapters", {})

            for adapter_name in adapter_configs:
                try:
                    adapter_class = import_adapter(adapter_name)
                    adapter_instance = depends.get(adapter_class)
                    self._adapters[adapter_name] = adapter_instance
                except Exception as e:
                    self.logger.warning(
                        f"Failed to register adapter {adapter_name}: {e}"
                    )

            self.logger.debug(f"Registered {len(self._adapters)} adapters")
        except Exception as e:
            self.logger.warning(f"Failed to register adapters: {e}")

    async def _register_services(self) -> None:
        """Register services (placeholder for future implementation)."""
        # When services are implemented, register them here
        self.logger.debug("Services registration placeholder")

    def get_actions(self) -> dict[str, Any]:
        """Get all registered actions."""
        return self._actions.copy()

    def get_action(self, name: str) -> Any | None:
        """Get a specific action by name."""
        return self._actions.get(name)

    def get_adapters(self) -> dict[str, Any]:
        """Get all registered adapters."""
        return self._adapters.copy()

    def get_adapter(self, name: str) -> Any | None:
        """Get a specific adapter by name."""
        return self._adapters.get(name)

    def get_services(self) -> dict[str, Any]:
        """Get all registered services."""
        return self._services.copy()

    def get_service(self, name: str) -> Any | None:
        """Get a specific service by name."""
        return self._services.get(name)

    def get_events(self) -> dict[str, Any]:
        """Get all registered events."""
        return self._events.copy()

    def get_event(self, name: str) -> Any | None:
        """Get a specific event by name."""
        return self._events.get(name)

    async def cleanup(self) -> None:
        """Clean up the component registry."""
        self._actions.clear()
        self._adapters.clear()
        self._services.clear()
        self._events.clear()
        self._initialized = False
        self.logger.info("ACB Component Registry cleaned up")
