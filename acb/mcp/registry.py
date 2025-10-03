"""Component registry for ACB MCP server."""

from contextlib import suppress
from typing import Any

from acb.adapters import import_adapter
from acb.config import Config
from acb.depends import depends
from acb.logger import Logger


class ComponentRegistry:
    """Registry for ACB components exposed through MCP."""

    def __init__(self) -> None:
        """Initialize the component registry."""
        self._actions: dict[str, Any] = {}
        self._adapters: dict[str, Any] = {}
        self._services: dict[str, Any] = {}
        self._events: dict[str, Any] = {}
        self._initialized = False
        self._config: Config | None = None
        self._logger: Logger | None = None

    @property
    def config(self) -> Config:
        """Lazy-initialize config."""
        if self._config is None:
            self._config = depends.get(Config)
        return self._config

    @property
    def logger(self) -> Logger:
        """Lazy-initialize logger."""
        if self._logger is None:
            self._logger = depends.get(Logger)
        return self._logger

    async def initialize(self) -> None:
        """Initialize the component registry."""
        if self._initialized:
            return

        with suppress(Exception):
            self.logger.info("Initializing ACB Component Registry")

        # Register built-in actions
        await self._register_builtin_actions()

        # Register configured adapters
        await self._register_configured_adapters()

        # Register services (when implemented)
        await self._register_services()

        self._initialized = True
        with suppress(Exception):
            self.logger.info("ACB Component Registry initialized")

    async def _register_builtin_actions(self) -> None:
        """Register built-in ACB actions."""
        with suppress(Exception):
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

    async def _register_configured_adapters(self) -> None:
        """Register adapters configured in the system."""
        with suppress(Exception):
            # Get configured adapters from settings
            adapter_configs = getattr(self.config, "adapters", {})

            for adapter_name in adapter_configs:
                with suppress(Exception):
                    adapter_class = import_adapter(adapter_name)
                    adapter_instance = depends.get(adapter_class)
                    self._adapters[adapter_name] = adapter_instance

    async def _register_services(self) -> None:
        """Register services (placeholder for future implementation)."""
        # When services are implemented, register them here
        pass

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
        with suppress(Exception):
            self.logger.info("ACB Component Registry cleaned up")
