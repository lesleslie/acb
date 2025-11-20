"""ACB Context Management.

This module provides centralized state management for ACB, replacing the
previous global state variables with a proper context class.
"""

from contextvars import ContextVar

import asyncio
import typing as t
from anyio import Path as AsyncPath
from pydantic import BaseModel, ConfigDict

from .actions import Action
from .adapters import Adapter


@t.runtime_checkable
class ContextProtocol(t.Protocol):
    """Protocol defining the ACB context interface."""

    async def ensure_registration(self) -> None:
        """Ensure all packages are registered."""
        ...

    async def register_pkg(self, name: str, path: AsyncPath) -> None:
        """Register a package explicitly."""
        ...

    def is_testing_mode(self) -> bool:
        """Check if running in testing mode."""
        ...

    def is_library_mode(self) -> bool:
        """Check if running in library mode."""
        ...


class Pkg(BaseModel):
    """Package representation."""

    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str
    path: AsyncPath
    actions: list[Action] = []
    adapters: list[Adapter] = []


class Context:
    """Centralized context for ACB state management.

    This class encapsulates all global state that was previously scattered
    across modules, providing better testability and cleaner architecture.
    """

    def __init__(self) -> None:
        # Package registration state
        self._lazy_registration_queue: list[tuple[str, AsyncPath]] = []
        self._registration_completed: bool = False
        self.pkg_registry: ContextVar[list[Pkg]] = ContextVar(
            "pkg_registry",
            default=[],
        )

        # Runtime mode detection
        self._testing_mode: bool | None = None
        self._library_mode: bool | None = None
        self._deployed: bool | None = None

        # Application state
        self.project: str = ""
        self.app_name: str = ""
        self.debug_settings: dict[str, bool] = {}

        # Configuration state
        self._config_initialized: bool = False

        # Adapter state
        self.adapters: ContextVar[dict[str, t.Any]] = ContextVar(
            "adapters",
            default={},
        )

        # Locks for thread safety
        self._registration_lock = asyncio.Lock()

    def is_testing_mode(self) -> bool:
        """Check if running in testing mode."""
        if self._testing_mode is None:
            import os
            import sys

            self._testing_mode = (
                os.getenv("TESTING", "").lower() == "true" or "pytest" in sys.modules
            )
        return self._testing_mode

    def is_library_mode(self) -> bool:
        """Check if running in library mode."""
        if self._library_mode is None:
            import os
            import sys
            from pathlib import Path

            # Check various indicators of library usage
            if any(
                cmd in sys.argv[0] for cmd in ("pip", "setup.py", "build", "install")
            ):
                self._library_mode = True
            elif self.is_testing_mode():
                self._library_mode = False
            elif "ACB_LIBRARY_MODE" in os.environ:
                self._library_mode = os.environ["ACB_LIBRARY_MODE"].lower() == "true"
            else:
                self._library_mode = Path.cwd().name != "acb"

        return self._library_mode

    def is_deployed(self) -> bool:
        """Check if running in deployed mode."""
        if self._deployed is None:
            import os

            self._deployed = os.getenv("DEPLOYED", "").lower() == "true"
        return self._deployed

    async def register_pkg(self, name: str, path: AsyncPath) -> None:
        """Register a package explicitly."""
        async with self._registration_lock:
            # Check if already queued
            if name not in [item[0] for item in self._lazy_registration_queue]:
                self._lazy_registration_queue.append((name, path))

    async def ensure_registration(self) -> None:
        """Ensure all packages are registered."""
        if self._registration_completed or not self._lazy_registration_queue:
            return

        async with self._registration_lock:
            if self._registration_completed:
                return

            await self._process_registration_queue()
            self._registration_completed = True

    async def _process_registration_queue(self) -> None:
        """Process the registration queue."""
        registry = self.pkg_registry.get()
        existing_names = {p.name for p in registry}

        for name, path in self._lazy_registration_queue:
            if name not in existing_names:
                # Import registration functions with proper async handling
                from .actions import register_actions
                from .adapters import register_adapters

                actions = await register_actions(path)
                adapters = await register_adapters(path)
                pkg = Pkg(name=name, path=path, actions=actions, adapters=adapters)
                registry.append(pkg)
                existing_names.add(name)

        self._lazy_registration_queue.clear()

    def set_app_info(self, name: str, project: str = "") -> None:
        """Set application information."""
        self.app_name = name
        self.project = project

    def set_debug_settings(self, settings: dict[str, bool]) -> None:
        """Set debug settings."""
        self.debug_settings = settings.copy()

    def mark_config_initialized(self) -> None:
        """Mark configuration as initialized."""
        self._config_initialized = True

    def is_config_initialized(self) -> bool:
        """Check if configuration is initialized."""
        return self._config_initialized

    def reset(self) -> None:
        """Reset the context (mainly for testing)."""
        self._lazy_registration_queue.clear()
        self._registration_completed = False
        self.pkg_registry.set([])
        self.project = ""
        self.app_name = ""
        self.debug_settings = {}
        self._config_initialized = False
        self._testing_mode = None
        self._library_mode = None
        self._deployed = None


# Global context instance - still a singleton but encapsulated
_global_context: Context | None = None


def get_context() -> Context:
    """Get the global ACB context."""
    global _global_context
    if _global_context is None:
        _global_context = Context()
    return _global_context


def set_context(context: Context) -> None:
    """Set the global ACB context (mainly for testing)."""
    global _global_context
    _global_context = context


def reset_context() -> None:
    """Reset the global context (mainly for testing)."""
    global _global_context
    if _global_context is not None:
        _global_context.reset()
    _global_context = None
