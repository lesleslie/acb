"""Service registry for ACB services layer.

Provides centralized management for service discovery, lifecycle,
and dependency resolution following ACB's simplified architecture.
"""

import logging
from operator import itemgetter

import asyncio
import typing as t
from contextlib import suppress

from acb.depends import depends

if t.TYPE_CHECKING:
    from ._base import ServiceBase, ServiceConfig

logger = logging.getLogger(__name__)


class ServiceNotFoundError(Exception):
    """Raised when a requested service is not found."""

    def __init__(self, service_id: str) -> None:
        self.service_id = service_id
        super().__init__(f"Service '{service_id}' not found in registry")


class ServiceDependencyError(Exception):
    """Raised when service dependencies cannot be resolved."""

    def __init__(self, service_id: str, missing_deps: list[str]) -> None:
        self.service_id = service_id
        self.missing_deps = missing_deps
        super().__init__(
            f"Service '{service_id}' has unresolved dependencies: {', '.join(missing_deps)}",
        )


class ServiceRegistry:
    """Central registry for service management.

    Provides service discovery, lifecycle management, and dependency resolution
    with ACB's dependency injection integration.
    """

    def __init__(self) -> None:
        self._services: dict[str, ServiceBase] = {}
        self._service_configs: dict[str, ServiceConfig] = {}
        self._initialization_order: list[str] = []
        self._shutdown_order: list[str] = []
        self._registry_lock = asyncio.Lock()
        self._initialized = False
        # Initialize logger - use standard logging for reliability
        self.logger = logging.getLogger(__name__)

    async def register_service(
        self,
        service: "ServiceBase",
        config: "ServiceConfig | None" = None,
    ) -> None:
        """Register a service with the registry.

        Args:
            service: The service instance to register
            config: Optional service configuration (uses service's config if not provided)
        """
        async with self._registry_lock:
            service_config = config or service._service_config
            service_id = service_config.service_id

            if service_id in self._services:
                self.logger.warning(
                    f"Service '{service_id}' already registered, replacing",
                )

            self._services[service_id] = service
            self._service_configs[service_id] = service_config

            # Register with ACB dependency injection
            depends.set(type(service), service)

            self.logger.info(f"Registered service: {service_id}")

    async def unregister_service(self, service_id: str) -> None:
        """Unregister a service from the registry.

        Args:
            service_id: The ID of the service to unregister
        """
        async with self._registry_lock:
            if service_id not in self._services:
                self.logger.warning(
                    f"Service '{service_id}' not found for unregistration",
                )
                return

            service = self._services.pop(service_id)
            self._service_configs.pop(service_id, None)

            # Remove from initialization/shutdown orders
            if service_id in self._initialization_order:
                self._initialization_order.remove(service_id)
            if service_id in self._shutdown_order:
                self._shutdown_order.remove(service_id)

            # Shutdown the service if it's still running
            with suppress(Exception):
                await service.shutdown()

            self.logger.info(f"Unregistered service: {service_id}")

    def get_service(self, service_id: str) -> "ServiceBase":
        """Get a service by ID.

        Args:
            service_id: The ID of the service to retrieve

        Returns:
            The service instance

        Raises:
            ServiceNotFoundError: If the service is not found
        """
        if service_id not in self._services:
            raise ServiceNotFoundError(service_id)

        return self._services[service_id]

    def get_service_config(self, service_id: str) -> "ServiceConfig":
        """Get service configuration by ID.

        Args:
            service_id: The ID of the service

        Returns:
            The service configuration

        Raises:
            ServiceNotFoundError: If the service is not found
        """
        if service_id not in self._service_configs:
            raise ServiceNotFoundError(service_id)

        return self._service_configs[service_id]

    def list_services(self) -> list[str]:
        """List all registered service IDs.

        Returns:
            List of service IDs
        """
        return list(self._services.keys())

    def get_services_by_status(self, status: "str") -> list["ServiceBase"]:
        """Get services by their current status.

        Args:
            status: The status to filter by

        Returns:
            List of services with the specified status
        """
        from ._base import ServiceStatus

        try:
            status_enum = ServiceStatus(status)
        except ValueError:
            return []

        return [
            service
            for service in self._services.values()
            if service.status == status_enum
        ]

    async def initialize_all(self) -> None:
        """Initialize all registered services in dependency order."""
        async with self._registry_lock:
            if self._initialized:
                self.logger.info("Services already initialized")
                return

            # Calculate initialization order based on dependencies
            self._calculate_initialization_order()

            # Initialize services in order
            for service_id in self._initialization_order:
                service = self._services[service_id]
                try:
                    await service.initialize()
                    self.logger.info(f"Initialized service: {service_id}")
                except Exception as e:
                    self.logger.exception(
                        f"Failed to initialize service '{service_id}': {e}",
                    )
                    # Continue with other services but log the failure
                    continue

            self._initialized = True
            self.logger.info("All services initialization completed")

    async def shutdown_all(self) -> None:
        """Shutdown all services in reverse dependency order."""
        async with self._registry_lock:
            if not self._initialized:
                self.logger.info("Services not initialized, nothing to shutdown")
                return

            # Shutdown in reverse order
            for service_id in reversed(self._shutdown_order):
                if service_id in self._services:
                    service = self._services[service_id]
                    try:
                        await service.shutdown()
                        self.logger.info(f"Shut down service: {service_id}")
                    except Exception as e:
                        self.logger.exception(
                            f"Error shutting down service '{service_id}': {e}",
                        )
                        # Continue with other services

            self._initialized = False
            self.logger.info("All services shutdown completed")

    async def get_health_status(self) -> dict[str, t.Any]:
        """Get health status of all services.

        Returns:
            Dictionary containing health status of all services
        """
        health_results = {}
        errors = []

        for service_id, service in self._services.items():
            try:
                health_results[service_id] = await service.health_check()
            except Exception as e:
                error_msg = f"Health check failed for '{service_id}': {e}"
                errors.append(error_msg)
                health_results[service_id] = {
                    "service_id": service_id,
                    "healthy": False,
                    "error": str(e),
                }

        # Calculate overall health
        healthy_services = sum(
            1 for health in health_results.values() if health.get("healthy", False)
        )
        total_services = len(health_results)

        return {
            "overall_healthy": healthy_services == total_services,
            "healthy_services": healthy_services,
            "total_services": total_services,
            "services": health_results,
            "errors": errors,
        }

    def _calculate_initialization_order(self) -> None:
        """Calculate service initialization order based on dependencies and priorities."""
        # Create a list of (priority, service_id) tuples
        services_with_priority = [
            (config.priority, service_id)
            for service_id, config in self._service_configs.items()
        ]

        # Sort by priority (lower number = higher priority)
        services_with_priority.sort(key=itemgetter(0))

        # Resolve dependencies using topological sort
        ordered_services = self._topological_sort(
            [s[1] for s in services_with_priority],
        )

        self._initialization_order = ordered_services
        self._shutdown_order = ordered_services.copy()

    def _initialize_dependency_graph(
        self, service_ids: list[str]
    ) -> tuple[dict[str, set[str]], dict[str, int]]:
        """Initialize empty dependency graph and in-degree counters."""
        graph: dict[str, set[str]] = {}
        in_degree: dict[str, int] = {}

        for service_id in service_ids:
            graph[service_id] = set()
            in_degree[service_id] = 0

        return graph, in_degree

    def _build_dependency_edges(
        self,
        service_ids: list[str],
        graph: dict[str, set[str]],
        in_degree: dict[str, int],
    ) -> None:
        """Build edges in dependency graph based on service dependencies."""
        for service_id in service_ids:
            if service_id not in self._service_configs:
                continue

            dependencies = self._service_configs[service_id].dependencies
            for dep in dependencies:
                if dep in graph:
                    graph[dep].add(service_id)
                    in_degree[service_id] += 1
                else:
                    self.logger.warning(
                        f"Service '{service_id}' depends on '{dep}' which is not registered",
                    )

    def _perform_kahns_algorithm(
        self,
        graph: dict[str, set[str]],
        in_degree: dict[str, int],
    ) -> list[str]:
        """Perform Kahn's algorithm for topological sorting."""
        queue = [service_id for service_id, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            current = queue.pop(0)
            result.append(current)

            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return result

    def _handle_circular_dependencies(
        self,
        result: list[str],
        service_ids: list[str],
    ) -> list[str]:
        """Handle circular dependencies by adding remaining services."""
        if len(result) == len(service_ids):
            return result

        remaining = [s for s in service_ids if s not in result]
        self.logger.error(
            f"Circular dependency detected among services: {remaining}",
        )
        # Add remaining services anyway to prevent complete failure
        result.extend(remaining)
        return result

    def _topological_sort(self, service_ids: list[str]) -> list[str]:
        """Perform topological sort to resolve service dependencies."""
        # Build dependency graph
        graph, in_degree = self._initialize_dependency_graph(service_ids)

        # Add edges based on dependencies
        self._build_dependency_edges(service_ids, graph, in_degree)

        # Kahn's algorithm for topological sorting
        result = self._perform_kahns_algorithm(graph, in_degree)

        # Check for circular dependencies
        return self._handle_circular_dependencies(result, service_ids)

    async def __aenter__(self) -> "ServiceRegistry":
        """Async context manager entry."""
        await self.initialize_all()
        return self

    async def __aexit__(self, exc_type: t.Any, exc_val: t.Any, exc_tb: t.Any) -> None:
        """Async context manager exit."""
        await self.shutdown_all()


# Global service registry instance
_registry: ServiceRegistry | None = None


def get_registry() -> ServiceRegistry:
    """Get the global service registry instance."""
    global _registry
    if _registry is None:
        _registry = ServiceRegistry()
    return _registry


async def register_service(
    service: "ServiceBase",
    config: "ServiceConfig | None" = None,
) -> None:
    """Register a service with the global registry."""
    registry = get_registry()
    await registry.register_service(service, config)


async def get_service(service_id: str) -> "ServiceBase":
    """Get a service from the global registry."""
    registry = get_registry()
    return registry.get_service(service_id)


async def initialize_services() -> None:
    """Initialize all services in the global registry."""
    registry = get_registry()
    await registry.initialize_all()


async def shutdown_services() -> None:
    """Shutdown all services in the global registry."""
    registry = get_registry()
    await registry.shutdown_all()
