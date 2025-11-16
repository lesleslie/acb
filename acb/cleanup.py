"""Basic resource cleanup patterns for ACB adapters.

This module provides simple resource cleanup patterns for adapter connections
and other resources that need proper lifecycle management.
"""

import logging

import asyncio
import typing as t

logger = logging.getLogger(__name__)


class CleanupMixin:
    """Simple mixin for resource cleanup."""

    def __init__(self) -> None:
        self._resources: list[t.Any] = []
        self._cleaned_up = False
        self._cleanup_lock: asyncio.Lock | None = None

    def register_resource(self, resource: t.Any) -> None:
        """Register a resource for cleanup."""
        if resource not in self._resources:
            self._resources.append(resource)

    async def cleanup_resource(self, resource: t.Any) -> None:
        """Clean up a single resource using common patterns."""
        if resource is None:
            return

        cleanup_methods = [
            "close",
            "aclose",
            "disconnect",
            "shutdown",
            "dispose",
            "terminate",
            "quit",
            "release",
        ]

        for method_name in cleanup_methods:
            if hasattr(resource, method_name):
                try:
                    method = getattr(resource, method_name)
                    if asyncio.iscoroutinefunction(method):
                        await method()
                    else:
                        method()
                    logger.debug(f"Cleaned up resource using {method_name}()")
                    return
                except Exception as e:
                    logger.debug(f"Failed to cleanup using {method_name}(): {e}")
                    continue

    async def cleanup(self) -> None:
        """Clean up all registered resources."""
        if self._cleanup_lock is None:
            self._cleanup_lock = asyncio.Lock()

        async with self._cleanup_lock:
            if self._cleaned_up:
                return

            errors = []
            for resource in self._resources.copy():
                try:
                    await self.cleanup_resource(resource)
                except Exception as e:
                    errors.append(f"Failed to cleanup resource: {e}")

            self._resources.clear()
            self._cleaned_up = True

            if errors:
                logger.warning(f"Resource cleanup errors: {'; '.join(errors)}")

    async def __aenter__(self) -> "CleanupMixin":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: t.Any, exc_val: t.Any, exc_tb: t.Any) -> None:
        """Async context manager exit with cleanup."""
        await self.cleanup()
