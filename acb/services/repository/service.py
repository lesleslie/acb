"""Repository Service Implementation.

Provides centralized repository management service:
- Integration with ACB Services Layer
- Repository lifecycle management
- Health monitoring and metrics
- Configuration and dependency injection
"""

import typing as t
from typing import Any, Dict, List, Optional, Type, TypeVar
from dataclasses import dataclass
from enum import Enum
import asyncio
from datetime import datetime, timezone

from acb.depends import depends
from .._base import ServiceBase, ServiceStatus
from ..health import HealthCheckMixin
from ._base import RepositoryBase, RepositorySettings, RepositoryError
from .registry import RepositoryRegistry, RepositoryScope, get_registry
from .unit_of_work import UnitOfWork, UnitOfWorkManager
from .coordinator import MultiDatabaseCoordinator, DatabaseType, CoordinationStrategy
from .cache import RepositoryCacheSettings

# Service metadata for discovery system
try:
    from ..discovery import (
        ServiceMetadata,
        ServiceCapability,
        generate_service_id
    )

    SERVICE_METADATA = ServiceMetadata(
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
            ServiceCapability.DEPENDENCY_INJECTION
        ],
        description="Repository pattern service with Unit of Work transaction management",
        settings_class="RepositoryServiceSettings",
        config_example={
            "enable_unit_of_work": True,
            "default_transaction_timeout": 30.0,
            "enable_repository_registry": True,
            "enable_query_caching": False
        }
    )
except ImportError:
    # Discovery system not available
    SERVICE_METADATA = None


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
    default_coordination_strategy: CoordinationStrategy = CoordinationStrategy.BEST_EFFORT

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

    def __init__(self, name: str = "RepositoryService"):
        super().__init__(name)
        self.settings = depends.get(RepositoryServiceSettings)
        self.registry = get_registry()
        self.uow_manager = UnitOfWorkManager()
        self.coordinator = MultiDatabaseCoordinator(
            self.settings.default_coordination_strategy
        ) if self.settings.enable_coordination else None
        self._metrics = RepositoryServiceMetrics()
        self._health_check_task: asyncio.Task | None = None
        self._metrics_task: asyncio.Task | None = None

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

            self._status = ServiceStatus.ACTIVE
            self.logger.info("Repository service initialized successfully")

        except Exception as e:
            self._status = ServiceStatus.ERROR
            raise RepositoryError(f"Failed to initialize repository service: {e}") from e

    async def shutdown(self) -> None:
        """Shutdown the repository service."""
        self._status = ServiceStatus.STOPPING

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
            self.logger.error(f"Error during repository service shutdown: {e}")

    def register_repository(
        self,
        entity_type: Type[EntityType],
        repository_type: Type[RepositoryBase[EntityType, Any]],
        scope: RepositoryScope = RepositoryScope.SINGLETON
    ) -> None:
        """Register a repository for an entity type.

        Args:
            entity_type: The entity type
            repository_type: The repository class
            scope: Repository scope
        """
        self.registry.register(entity_type, repository_type, scope)
        self.logger.debug(f"Registered repository {repository_type.__name__} for {entity_type.__name__}")

    def register_repository_instance(
        self,
        entity_type: Type[EntityType],
        repository_instance: RepositoryBase[EntityType, Any]
    ) -> None:
        """Register a pre-created repository instance.

        Args:
            entity_type: The entity type
            repository_instance: The repository instance
        """
        self.registry.register_instance(entity_type, repository_instance)
        self.logger.debug(f"Registered repository instance for {entity_type.__name__}")

    def get_repository(self, entity_type: Type[EntityType]) -> RepositoryBase[EntityType, Any]:
        """Get repository for entity type.

        Args:
            entity_type: The entity type

        Returns:
            Repository instance
        """
        return self.registry.get(entity_type)

    def try_get_repository(self, entity_type: Type[EntityType]) -> RepositoryBase[EntityType, Any] | None:
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
        timeout: float | None = None
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
        timeout: float | None = None
    ):
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
        read_only: bool = False
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
            raise RepositoryError("Multi-database coordination not enabled")

        self.coordinator.register_database(name, db_type, adapter, priority, read_only)
        self.logger.debug(f"Registered database {name} ({db_type.value})")

    def register_coordinated_repository(
        self,
        database_name: str,
        entity_name: str,
        repository: RepositoryBase
    ) -> None:
        """Register a repository for coordinated operations.

        Args:
            database_name: Database connection name
            entity_name: Entity type name
            repository: Repository instance
        """
        if not self.coordinator:
            raise RepositoryError("Multi-database coordination not enabled")

        self.coordinator.register_repository(database_name, entity_name, repository)

    async def execute_coordinated_operation(
        self,
        operation: str,
        entity_type: str,
        data: Dict[str, Any],
        target_databases: List[str] | None = None,
        strategy: CoordinationStrategy | None = None
    ) -> Dict[str, Any]:
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
            raise RepositoryError("Multi-database coordination not enabled")

        if operation == "create":
            return await self.coordinator.execute_coordinated_create(
                entity_type, data, target_databases, strategy
            )
        elif operation == "update":
            entity_id = data.pop("id")
            return await self.coordinator.execute_coordinated_update(
                entity_type, entity_id, data, target_databases, strategy
            )
        elif operation == "delete":
            entity_id = data["id"]
            return await self.coordinator.execute_coordinated_delete(
                entity_type, entity_id, target_databases, strategy
            )
        else:
            raise RepositoryError(f"Unsupported coordinated operation: {operation}")

    async def check_health(self) -> Dict[str, Any]:
        """Check repository service health.

        Returns:
            Health status information
        """
        health_status = {
            "service_status": self._status.value,
            "repositories_registered": len(self.registry.list_registrations()),
            "active_transactions": len(await self.uow_manager.get_active_transactions()),
            "metrics": {
                "total_repositories": self._metrics.total_repositories,
                "active_repositories": self._metrics.active_repositories,
                "cache_hit_rate": self._metrics.cache_hit_rate,
                "coordination_success_rate": self._metrics.coordination_success_rate,
                "health_check_failures": self._metrics.health_check_failures
            }
        }

        # Add coordinator health if enabled
        if self.coordinator:
            coordinator_health = await self.coordinator.check_database_health()
            health_status["database_health"] = coordinator_health

        # Add UoW statistics
        uow_stats = await self.uow_manager.get_transaction_stats()
        health_status["transaction_stats"] = uow_stats

        return health_status

    async def get_service_metrics(self) -> Dict[str, Any]:
        """Get comprehensive service metrics.

        Returns:
            Service metrics dictionary
        """
        base_metrics = await super().get_metrics()

        repository_metrics = {
            "registrations": self.registry.list_registrations(),
            "transaction_stats": await self.uow_manager.get_transaction_stats(),
            "performance_metrics": {
                "total_repositories": self._metrics.total_repositories,
                "active_repositories": self._metrics.active_repositories,
                "cache_hit_rate": self._metrics.cache_hit_rate,
                "coordination_success_rate": self._metrics.coordination_success_rate,
                "health_check_failures": self._metrics.health_check_failures
            }
        }

        # Add coordinator stats if enabled
        if self.coordinator:
            repository_metrics["coordination_stats"] = await self.coordinator.get_coordination_stats()

        return {
            **base_metrics,
            "repository_metrics": repository_metrics
        }

    async def _auto_register_repositories(self) -> None:
        """Auto-register repositories from common locations."""
        try:
            # Try to register repositories from common adapter packages
            adapter_packages = [
                "acb.adapters.sql",
                "acb.adapters.nosql",
                "acb.adapters.cache"
            ]

            for package_name in adapter_packages:
                try:
                    package = __import__(package_name, fromlist=[''])
                    registered = self.registry.auto_register_repositories(package)
                    if registered:
                        self.logger.debug(f"Auto-registered {registered} repositories from {package_name}")
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
        try:
            # Try to register SQL adapter
            from acb.adapters import import_adapter
            try:
                Sql = import_adapter("sql")
                sql_adapter = depends.get(Sql)
                self.coordinator.register_database("sql_primary", DatabaseType.SQL, sql_adapter, priority=100)
            except ImportError:
                pass

            # Try to register NoSQL adapter
            try:
                Nosql = import_adapter("nosql")
                nosql_adapter = depends.get(Nosql)
                self.coordinator.register_database("nosql_primary", DatabaseType.NOSQL, nosql_adapter, priority=90)
            except ImportError:
                pass

            # Try to register Cache adapter
            try:
                Cache = import_adapter("cache")
                cache_adapter = depends.get(Cache)
                self.coordinator.register_database("cache_primary", DatabaseType.CACHE, cache_adapter, priority=80)
            except ImportError:
                pass

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
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        if self._metrics_task:
            self._metrics_task.cancel()
            try:
                await self._metrics_task
            except asyncio.CancelledError:
                pass

    async def _health_check_loop(self) -> None:
        """Background health check loop."""
        while self._status == ServiceStatus.ACTIVE:
            try:
                await self._perform_health_checks()
                await asyncio.sleep(self.settings.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Health check error: {e}")
                self._metrics.health_check_failures += 1
                await asyncio.sleep(self.settings.health_check_interval)

    async def _perform_health_checks(self) -> None:
        """Perform health checks on repositories and databases."""
        # Check coordinator health if enabled
        if self.coordinator:
            try:
                await self.coordinator.check_database_health()
            except Exception as e:
                self.logger.warning(f"Coordinator health check failed: {e}")
                self._metrics.health_check_failures += 1

        # Check UoW manager health
        try:
            active_transactions = await self.uow_manager.get_active_transactions()
            # Log if too many active transactions
            if len(active_transactions) > 100:
                self.logger.warning(f"High number of active transactions: {len(active_transactions)}")
        except Exception as e:
            self.logger.warning(f"UoW health check failed: {e}")

    async def _metrics_collection_loop(self) -> None:
        """Background metrics collection loop."""
        while self._status == ServiceStatus.ACTIVE:
            try:
                await self._collect_metrics()
                await asyncio.sleep(self.settings.metrics_collection_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Metrics collection error: {e}")
                await asyncio.sleep(self.settings.metrics_collection_interval)

    async def _collect_metrics(self) -> None:
        """Collect service metrics."""
        try:
            # Update basic metrics
            registrations = self.registry.list_registrations()
            self._metrics.total_repositories = len(registrations)
            self._metrics.active_repositories = sum(
                1 for reg in registrations.values()
                if reg.get("initialized", False)
            )

            # Update transaction metrics
            active_transactions = await self.uow_manager.get_active_transactions()
            self._metrics.active_transactions = len(active_transactions)

            # Update coordination metrics if enabled
            if self.coordinator:
                coord_stats = await self.coordinator.get_coordination_stats()
                self._metrics.coordination_success_rate = coord_stats.get("success_rate", 0.0)

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

        await super()._cleanup_resources()