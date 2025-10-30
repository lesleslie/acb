"""Repository Service Implementation.

Provides centralized repository management service:
- Integration with ACB Services Layer
- Repository lifecycle management
- Health monitoring and metrics
- Configuration and dependency injection
"""

import asyncio
import contextlib
import typing as t
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, TypeVar

from acb.depends import depends
from acb.services._base import ServiceBase
from acb.services._base import ServiceStatus as BaseServiceStatus
from acb.services.health import HealthCheckMixin

from ._base import RepositoryBase, RepositoryError, RepositorySettings
from .cache import RepositoryCacheSettings
from .coordinator import CoordinationStrategy, DatabaseType, MultiDatabaseCoordinator
from .registry import RepositoryScope, get_registry
from .unit_of_work import UnitOfWork, UnitOfWorkManager

# Service metadata for discovery system
try:
    from acb.services.discovery import (
        ServiceCapability,
        ServiceMetadata,
        ServiceStatus,
        generate_service_id,
    )

    SERVICE_METADATA: ServiceMetadata | None = ServiceMetadata(
        service_id=generate_service_id(),
        name="Repository Service",
        category="repository",
        service_type="data_access",
        version="1.0.0",
        acb_min_version="0.19.1",
        author="ACB Framework Team",
        created_date="2024-01-01T00:00:00",
        last_modified="2024-01-01T00:00:00",
        status=ServiceStatus.STABLE,
        capabilities=[
            ServiceCapability.ASYNC_OPERATIONS,
            ServiceCapability.LIFECYCLE_MANAGEMENT,
            ServiceCapability.METRICS_COLLECTION,
            ServiceCapability.DEPENDENCY_INJECTION,
        ],
        description="Repository pattern service with Unit of Work transaction management",
        settings_class="RepositoryServiceSettings",
        config_example={
            "enable_unit_of_work": True,
            "default_transaction_timeout": 30.0,
            "enable_repository_registry": True,
            "enable_query_caching": False,
        },
    )
except ImportError:
    # Discovery system not available
    SERVICE_METADATA = None
    # Use base ServiceStatus when discovery is not available
    ServiceStatus = BaseServiceStatus  # type: ignore[misc,no-redef]


EntityType = TypeVar("EntityType")


@dataclass
class RepositoryServiceMetrics:
    """Repository service metrics."""

    total_repositories: int = 0
    active_repositories: int = 0
    cache_hit_rate: float = 0.0
    active_transactions: int = 0
    coordination_success_rate: float = 0.0
    health_check_failures: int = 0


class RepositoryServiceSettings(RepositorySettings):
    """Repository service configuration settings."""

    # Service settings
    auto_register_repositories: bool = True
    health_check_interval: float = 30.0
    metrics_collection_interval: float = 60.0

    # Multi-database settings
    enable_coordination: bool = False
    default_coordination_strategy: CoordinationStrategy = (
        CoordinationStrategy.BEST_EFFORT
    )

    # Cache settings integration
    cache_settings: RepositoryCacheSettings = RepositoryCacheSettings()


class RepositoryService(ServiceBase, HealthCheckMixin):
    """Repository management service.

    Provides centralized management of repositories with:
    - Repository registration and discovery
    - Unit of Work transaction management
    - Multi-database coordination
    - Health monitoring and metrics
    - Cache management integration
    """

    def __init__(self, settings: RepositoryServiceSettings | None = None) -> None:
        self.settings = settings or depends.get_sync(RepositoryServiceSettings)

        # Create service config from settings
        from acb.services._base import ServiceConfig

        service_config = ServiceConfig(
            service_id="repository_service",
            name="RepositoryService",
        )

        super().__init__(service_config, self.settings)  # type: ignore[arg-type]
        self.registry = get_registry()
        self.uow_manager = UnitOfWorkManager()
        self.coordinator = (
            MultiDatabaseCoordinator(self.settings.default_coordination_strategy)
            if self.settings.enable_coordination
            else None
        )
        self._repo_metrics: RepositoryServiceMetrics = RepositoryServiceMetrics()
        # Override base class metrics with repository-specific metrics
        self._metrics = self._repo_metrics  # type: ignore[assignment]
        self._health_check_task: asyncio.Task[None] | None = None
        self._metrics_task: asyncio.Task[None] | None = None

    async def initialize(self) -> None:
        """Initialize the repository service."""
        await super().initialize()

        try:
            # Auto-register repositories if enabled
            if self.settings.auto_register_repositories:
                await self._auto_register_repositories()

            # Initialize coordinator if enabled
            if self.coordinator:
                await self._initialize_coordinator()

            # Start background tasks
            await self._start_background_tasks()

            self._status = ServiceStatus.ACTIVE  # type: ignore[attr-defined]
            self.logger.info("Repository service initialized successfully")

        except Exception as e:
            self._status = ServiceStatus.ERROR  # type: ignore[attr-defined]
            msg = f"Failed to initialize repository service: {e}"
            raise RepositoryError(
                msg,
            ) from e

    async def shutdown(self) -> None:
        """Shutdown the repository service."""
        self._status = ServiceStatus.STOPPING  # type: ignore[attr-defined]

        try:
            # Stop background tasks
            await self._stop_background_tasks()

            # Clean up coordinator
            if self.coordinator:
                await self.coordinator.cleanup()

            # Clean up UoW manager
            await self.uow_manager.cleanup()

            # Clean up registry
            await self.registry.cleanup()

            await super().shutdown()
            self.logger.info("Repository service shutdown complete")

        except Exception as e:
            self.logger.exception(f"Error during repository service shutdown: {e}")

    def register_repository(
        self,
        entity_type: type[EntityType],
        repository_type: type[RepositoryBase[EntityType, Any]],
        scope: RepositoryScope = RepositoryScope.SINGLETON,
    ) -> None:
        """Register a repository for an entity type.

        Args:
            entity_type: The entity type
            repository_type: The repository class
            scope: Repository scope
        """
        self.registry.register(entity_type, repository_type, scope)
        self.logger.debug(
            f"Registered repository {getattr(repository_type, '__name__', repository_type)} for {getattr(entity_type, '__name__', entity_type)}",
        )

    def register_repository_instance(
        self,
        entity_type: type[EntityType],
        repository_instance: RepositoryBase[EntityType, Any],
    ) -> None:
        """Register a pre-created repository instance.

        Args:
            entity_type: The entity type
            repository_instance: The repository instance
        """
        self.registry.register_instance(entity_type, repository_instance)
        self.logger.debug(
            f"Registered repository instance for {getattr(entity_type, '__name__', entity_type)}"
        )

    def get_repository(
        self,
        entity_type: type[EntityType],
    ) -> RepositoryBase[EntityType, Any]:
        """Get repository for entity type.

        Args:
            entity_type: The entity type

        Returns:
            Repository instance
        """
        return self.registry.get(entity_type)

    def try_get_repository(
        self,
        entity_type: type[EntityType],
    ) -> RepositoryBase[EntityType, Any] | None:
        """Try to get repository for entity type.

        Args:
            entity_type: The entity type

        Returns:
            Repository instance or None
        """
        return self.registry.try_get(entity_type)

    async def create_unit_of_work(
        self,
        isolation_level: str | None = None,
        timeout: float | None = None,
    ) -> UnitOfWork:
        """Create a new Unit of Work.

        Args:
            isolation_level: Database isolation level
            timeout: Transaction timeout in seconds

        Returns:
            New Unit of Work instance
        """
        return await self.uow_manager.create_unit_of_work(isolation_level, timeout)

    def transaction_context(
        self,
        isolation_level: str | None = None,
        timeout: float | None = None,
    ) -> t.Any:
        """Get transaction context manager.

        Args:
            isolation_level: Database isolation level
            timeout: Transaction timeout in seconds

        Returns:
            Transaction context manager
        """
        return self.uow_manager.transaction(isolation_level, timeout)

    def register_database(
        self,
        name: str,
        db_type: DatabaseType,
        adapter: Any,
        priority: int = 0,
        read_only: bool = False,
    ) -> None:
        """Register a database for coordination.

        Args:
            name: Database connection name
            db_type: Database type
            adapter: Database adapter instance
            priority: Connection priority
            read_only: Whether connection is read-only
        """
        if not self.coordinator:
            msg = "Multi-database coordination not enabled"
            raise RepositoryError(msg)

        self.coordinator.register_database(name, db_type, adapter, priority, read_only)
        self.logger.debug(f"Registered database {name} ({db_type.value})")

    def register_coordinated_repository(
        self,
        database_name: str,
        entity_name: str,
        repository: RepositoryBase[Any, Any],
    ) -> None:
        """Register a repository for coordinated operations.

        Args:
            database_name: Database connection name
            entity_name: Entity type name
            repository: Repository instance
        """
        if not self.coordinator:
            msg = "Multi-database coordination not enabled"
            raise RepositoryError(msg)

        self.coordinator.register_repository(database_name, entity_name, repository)

    async def execute_coordinated_operation(
        self,
        operation: str,
        entity_type: str,
        data: dict[str, Any],
        target_databases: list[str] | None = None,
        strategy: CoordinationStrategy | None = None,
    ) -> dict[str, Any]:
        """Execute coordinated operation across databases.

        Args:
            operation: Operation type (create, update, delete)
            entity_type: Entity type name
            data: Operation data
            target_databases: Target databases
            strategy: Coordination strategy

        Returns:
            Operation results
        """
        if not self.coordinator:
            msg = "Multi-database coordination not enabled"
            raise RepositoryError(msg)

        if operation == "create":
            return await self.coordinator.execute_coordinated_create(
                entity_type,
                data,
                target_databases,
                strategy,
            )
        if operation == "update":
            entity_id = data.pop("id")
            return await self.coordinator.execute_coordinated_update(
                entity_type,
                entity_id,
                data,
                target_databases,
                strategy,
            )
        if operation == "delete":
            entity_id = data["id"]
            return await self.coordinator.execute_coordinated_delete(
                entity_type,
                entity_id,
                target_databases,
                strategy,
            )
        msg = f"Unsupported coordinated operation: {operation}"
        raise RepositoryError(msg)

    async def check_health(self) -> dict[str, Any]:
        """Check repository service health.

        Returns:
            Health status information
        """
        health_status = {
            "service_status": self._status.value,
            "repositories_registered": len(self.registry.list_registrations()),
            "active_transactions": len(
                await self.uow_manager.get_active_transactions(),
            ),
            "metrics": {
                "total_repositories": self._repo_metrics.total_repositories,
                "active_repositories": self._repo_metrics.active_repositories,
                "cache_hit_rate": self._repo_metrics.cache_hit_rate,
                "coordination_success_rate": self._repo_metrics.coordination_success_rate,
                "health_check_failures": self._repo_metrics.health_check_failures,
            },
        }

        # Add coordinator health if enabled
        if self.coordinator:
            coordinator_health = await self.coordinator.check_database_health()
            health_status["database_health"] = coordinator_health

        # Add UoW statistics
        uow_stats = await self.uow_manager.get_transaction_stats()
        health_status["transaction_stats"] = uow_stats

        return health_status

    async def get_service_metrics(self) -> dict[str, Any]:
        """Get comprehensive service metrics.

        Returns:
            Service metrics dictionary
        """
        base_metrics = await super().get_metrics()  # type: ignore[misc]

        repository_metrics = {
            "registrations": self.registry.list_registrations(),
            "transaction_stats": await self.uow_manager.get_transaction_stats(),
            "performance_metrics": {
                "total_repositories": self._repo_metrics.total_repositories,
                "active_repositories": self._repo_metrics.active_repositories,
                "cache_hit_rate": self._repo_metrics.cache_hit_rate,
                "coordination_success_rate": self._repo_metrics.coordination_success_rate,
                "health_check_failures": self._repo_metrics.health_check_failures,
            },
        }

        # Add coordinator stats if enabled
        if self.coordinator:
            repository_metrics[
                "coordination_stats"
            ] = await self.coordinator.get_coordination_stats()

        return {**base_metrics, "repository_metrics": repository_metrics}

    async def _auto_register_repositories(self) -> None:
        """Auto-register repositories from common locations."""
        try:
            # Try to register repositories from common adapter packages
            adapter_packages = [
                "acb.adapters.sql",
                "acb.adapters.nosql",
                "acb.adapters.cache",
            ]

            for package_name in adapter_packages:
                try:
                    package = __import__(package_name, fromlist=[""])
                    registered = self.registry.auto_register_repositories(package)
                    if registered:
                        self.logger.debug(
                            f"Auto-registered {registered} repositories from {package_name}",
                        )
                except ImportError:
                    continue

        except Exception as e:
            self.logger.warning(f"Auto-registration failed: {e}")

    async def _initialize_coordinator(self) -> None:
        """Initialize multi-database coordinator."""
        try:
            # Register available database adapters
            await self._register_available_databases()

        except Exception as e:
            self.logger.warning(f"Coordinator initialization failed: {e}")

    async def _register_available_databases(self) -> None:
        """Register available database adapters with coordinator."""
        # Coordinator must exist when this method is called
        assert self.coordinator is not None

        try:
            # Try to register SQL adapter
            from acb.adapters import import_adapter

            with suppress(ImportError):
                Sql = import_adapter("sql")
                sql_adapter = await depends.get(Sql)
                self.coordinator.register_database(
                    "sql_primary",
                    DatabaseType.SQL,
                    sql_adapter,
                    priority=100,
                )

            # Try to register NoSQL adapter
            with suppress(ImportError):
                Nosql = import_adapter("nosql")
                nosql_adapter = await depends.get(Nosql)
                self.coordinator.register_database(
                    "nosql_primary",
                    DatabaseType.NOSQL,
                    nosql_adapter,
                    priority=90,
                )

            # Try to register Cache adapter
            with suppress(ImportError):
                Cache = import_adapter("cache")
                cache_adapter = await depends.get(Cache)
                self.coordinator.register_database(
                    "cache_primary",
                    DatabaseType.CACHE,
                    cache_adapter,
                    priority=80,
                )

        except Exception as e:
            self.logger.warning(f"Database adapter registration failed: {e}")

    async def _start_background_tasks(self) -> None:
        """Start background monitoring tasks."""
        if self.settings.health_check_interval > 0:
            self._health_check_task = asyncio.create_task(self._health_check_loop())

        if self.settings.metrics_collection_interval > 0:
            self._metrics_task = asyncio.create_task(self._metrics_collection_loop())

    async def _stop_background_tasks(self) -> None:
        """Stop background monitoring tasks."""
        if self._health_check_task:
            self._health_check_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._health_check_task

        if self._metrics_task:
            self._metrics_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._metrics_task

    async def _health_check_loop(self) -> None:
        """Background health check loop."""
        while self._status == ServiceStatus.ACTIVE:  # type: ignore[attr-defined]
            try:
                await self._perform_health_checks()
                await asyncio.sleep(self.settings.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.exception(f"Health check error: {e}")
                self._repo_metrics.health_check_failures += 1
                await asyncio.sleep(self.settings.health_check_interval)

    async def _perform_health_checks(self) -> None:
        """Perform health checks on repositories and databases."""
        # Check coordinator health if enabled
        if self.coordinator:
            try:
                await self.coordinator.check_database_health()
            except Exception as e:
                self.logger.warning(f"Coordinator health check failed: {e}")
                self._repo_metrics.health_check_failures += 1

        # Check UoW manager health
        try:
            active_transactions = await self.uow_manager.get_active_transactions()
            # Log if too many active transactions
            if len(active_transactions) > 100:
                self.logger.warning(
                    f"High number of active transactions: {len(active_transactions)}",
                )
        except Exception as e:
            self.logger.warning(f"UoW health check failed: {e}")

    async def _metrics_collection_loop(self) -> None:
        """Background metrics collection loop."""
        while self._status == ServiceStatus.ACTIVE:  # type: ignore[attr-defined]
            try:
                await self._collect_metrics()
                await asyncio.sleep(self.settings.metrics_collection_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.exception(f"Metrics collection error: {e}")
                await asyncio.sleep(self.settings.metrics_collection_interval)

    async def _collect_metrics(self) -> None:
        """Collect service metrics."""
        try:
            # Update basic metrics
            registrations = self.registry.list_registrations()
            self._repo_metrics.total_repositories = len(registrations)
            self._repo_metrics.active_repositories = sum(
                1 for reg in registrations.values() if reg.get("initialized", False)
            )

            # Update transaction metrics
            active_transactions = await self.uow_manager.get_active_transactions()
            self._repo_metrics.active_transactions = len(active_transactions)

            # Update coordination metrics if enabled
            if self.coordinator:
                coord_stats = await self.coordinator.get_coordination_stats()
                self._repo_metrics.coordination_success_rate = coord_stats.get(
                    "success_rate",
                    0.0,
                )

            # Calculate aggregate cache hit rate
            # This would need to be implemented by querying individual repositories

        except Exception as e:
            self.logger.warning(f"Metrics collection failed: {e}")

    async def _cleanup_resources(self) -> None:
        """Clean up service resources."""
        await self._stop_background_tasks()

        if self.coordinator:
            await self.coordinator.cleanup()

        await self.uow_manager.cleanup()
        await self.registry.cleanup()

        await super()._cleanup_resources()  # type: ignore[misc]
