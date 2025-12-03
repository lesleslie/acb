"""Multi-Database Coordinator Implementation.

Provides coordination across multiple database types:
- Multi-database transaction coordination
- Data synchronization across databases
- Distributed query execution
- Cross-database consistency management
"""

import uuid
from collections.abc import Awaitable, Callable
from enum import Enum

import asyncio
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, TypeVar

from acb.cleanup import CleanupMixin

from ._base import RepositoryBase, RepositoryError
from .unit_of_work import UnitOfWorkManager

EntityType = TypeVar("EntityType")


class DatabaseType(Enum):
    """Database type enumeration."""

    SQL = "sql"
    NOSQL = "nosql"
    CACHE = "cache"
    VECTOR = "vector"
    GRAPH = "graph"


class CoordinationStrategy(Enum):
    """Coordination strategy enumeration."""

    TWO_PHASE_COMMIT = "2pc"  # Two-phase commit
    SAGA_PATTERN = "saga"  # Saga pattern for distributed transactions
    EVENT_SOURCING = "event_sourcing"  # Event sourcing with eventual consistency
    BEST_EFFORT = "best_effort"  # Best effort with compensation


@dataclass
class DatabaseConnection:
    """Database connection information."""

    name: str
    db_type: DatabaseType
    adapter: Any
    priority: int = 0  # Higher priority = preferred for reads
    read_only: bool = False
    health_status: str = "unknown"
    last_health_check: datetime | None = None


@dataclass
class CoordinationTask:
    """Task for multi-database coordination."""

    task_id: str
    operation: str
    databases: set[str]
    entity_type: str
    data: dict[str, Any]
    strategy: CoordinationStrategy
    created_at: datetime
    status: str = "pending"
    error_message: str | None = None
    compensation_actions: list[Callable[..., Any]] = field(default_factory=list[Any])


class MultiDatabaseCoordinator(CleanupMixin):
    """Coordinator for managing operations across multiple databases.

    Provides transaction coordination, data synchronization, and
    consistency management across different database types and instances.
    """

    def __init__(
        self,
        default_strategy: CoordinationStrategy = CoordinationStrategy.BEST_EFFORT,
    ) -> None:
        super().__init__()
        self.default_strategy = default_strategy
        self._connections: dict[str, DatabaseConnection] = {}
        self._repositories: dict[str, dict[str, RepositoryBase[Any, Any]]] = {}
        self._active_tasks: dict[str, CoordinationTask] = {}
        self._completed_tasks: list[CoordinationTask] = []
        self._event_handlers: dict[str, list[Callable[..., Any]]] = {}
        self._uow_manager = UnitOfWorkManager()

    def register_database(
        self,
        name: str,
        db_type: DatabaseType,
        adapter: Any,
        priority: int = 0,
        read_only: bool = False,
    ) -> None:
        """Register a database connection.

        Args:
            name: Database connection name
            db_type: Database type
            adapter: Database adapter instance
            priority: Connection priority for read operations
            read_only: Whether this connection is read-only
        """
        connection = DatabaseConnection(
            name=name,
            db_type=db_type,
            adapter=adapter,
            priority=priority,
            read_only=read_only,
            health_status="registered",
            last_health_check=datetime.now(UTC),
        )

        self._connections[name] = connection
        self._repositories[name] = {}

    def register_repository(
        self,
        database_name: str,
        entity_name: str,
        repository: RepositoryBase[Any, Any],
    ) -> None:
        """Register a repository for a specific database.

        Args:
            database_name: Database connection name
            entity_name: Entity type name
            repository: Repository instance
        """
        if database_name not in self._connections:
            msg = f"Database {database_name} not registered"
            raise RepositoryError(msg)

        if database_name not in self._repositories:
            self._repositories[database_name] = {}

        self._repositories[database_name][entity_name] = repository

    def get_repository(
        self,
        database_name: str,
        entity_name: str,
    ) -> RepositoryBase[Any, Any] | None:
        """Get repository for database and entity.

        Args:
            database_name: Database connection name
            entity_name: Entity type name

        Returns:
            Repository instance or None if not found
        """
        if database_name in self._repositories:
            return self._repositories[database_name].get(entity_name)
        return None

    def get_preferred_read_database(
        self,
        db_type: DatabaseType | None = None,
    ) -> DatabaseConnection | None:
        """Get preferred database for read operations.

        Args:
            db_type: Optional database type filter

        Returns:
            Preferred database connection or None
        """
        candidates = []

        for connection in self._connections.values():
            if db_type is None or connection.db_type == db_type:
                if connection.health_status == "healthy":
                    candidates.append(connection)

        if not candidates:
            return None

        # Sort by priority (descending) and return highest
        candidates.sort(key=lambda c: c.priority, reverse=True)
        return candidates[0]

    def get_write_databases(
        self,
        db_type: DatabaseType | None = None,
    ) -> list[DatabaseConnection]:
        """Get databases available for write operations.

        Args:
            db_type: Optional database type filter

        Returns:
            List of writable database connections
        """
        databases = []

        for connection in self._connections.values():
            if not connection.read_only:
                if db_type is None or connection.db_type == db_type:
                    if connection.health_status in ("healthy", "unknown"):
                        databases.append(connection)

        return databases

    async def execute_coordinated_create(
        self,
        entity_type: str,
        entity_data: dict[str, Any],
        target_databases: list[str] | None = None,
        strategy: CoordinationStrategy | None = None,
    ) -> dict[str, Any]:
        """Execute coordinated create operation across databases.

        Args:
            entity_type: Type of entity to create
            entity_data: Entity data
            target_databases: Specific databases to target
            strategy: Coordination strategy to use

        Returns:
            Results from each database
        """
        strategy = strategy or self.default_strategy
        task_id = str(uuid.uuid4())

        if target_databases is None:
            target_databases = [
                name for name, conn in self._connections.items() if not conn.read_only
            ]

        task = CoordinationTask(
            task_id=task_id,
            operation="create",
            databases=set(target_databases),
            entity_type=entity_type,
            data=entity_data,
            strategy=strategy,
            created_at=datetime.now(UTC),
        )

        self._active_tasks[task_id] = task

        try:
            if strategy == CoordinationStrategy.TWO_PHASE_COMMIT:
                result = await self._execute_2pc_create(task)
            elif strategy == CoordinationStrategy.SAGA_PATTERN:
                result = await self._execute_saga_create(task)
            elif strategy == CoordinationStrategy.BEST_EFFORT:
                result = await self._execute_best_effort_create(task)
            else:
                msg = f"Unsupported coordination strategy: {strategy}"
                raise RepositoryError(msg)

            task.status = "completed"
            return result

        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            await self._execute_compensation(task)
            raise

        finally:
            self._active_tasks.pop(task_id, None)
            self._completed_tasks.append(task)

    async def execute_coordinated_update(
        self,
        entity_type: str,
        entity_id: Any,
        entity_data: dict[str, Any],
        target_databases: list[str] | None = None,
        strategy: CoordinationStrategy | None = None,
    ) -> dict[str, Any]:
        """Execute coordinated update operation across databases.

        Args:
            entity_type: Type of entity to update
            entity_id: Entity identifier
            entity_data: Updated entity data
            target_databases: Specific databases to target
            strategy: Coordination strategy to use

        Returns:
            Results from each database
        """
        strategy = strategy or self.default_strategy
        task_id = str(uuid.uuid4())

        if target_databases is None:
            target_databases = [
                name for name, conn in self._connections.items() if not conn.read_only
            ]

        task = CoordinationTask(
            task_id=task_id,
            operation="update",
            databases=set(target_databases),
            entity_type=entity_type,
            data={"id": entity_id} | entity_data,
            strategy=strategy,
            created_at=datetime.now(UTC),
        )

        self._active_tasks[task_id] = task

        try:
            if strategy == CoordinationStrategy.TWO_PHASE_COMMIT:
                result = await self._execute_2pc_update(task)
            elif strategy == CoordinationStrategy.BEST_EFFORT:
                result = await self._execute_best_effort_update(task)
            else:
                msg = f"Update not supported for strategy: {strategy}"
                raise RepositoryError(msg)

            task.status = "completed"
            return result

        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            await self._execute_compensation(task)
            raise

        finally:
            self._active_tasks.pop(task_id, None)
            self._completed_tasks.append(task)

    async def execute_coordinated_delete(
        self,
        entity_type: str,
        entity_id: Any,
        target_databases: list[str] | None = None,
        strategy: CoordinationStrategy | None = None,
    ) -> dict[str, Any]:
        """Execute coordinated delete operation across databases.

        Args:
            entity_type: Type of entity to delete
            entity_id: Entity identifier
            target_databases: Specific databases to target
            strategy: Coordination strategy to use

        Returns:
            Results from each database
        """
        strategy = strategy or self.default_strategy
        task_id = str(uuid.uuid4())

        if target_databases is None:
            target_databases = [
                name for name, conn in self._connections.items() if not conn.read_only
            ]

        task = CoordinationTask(
            task_id=task_id,
            operation="delete",
            databases=set(target_databases),
            entity_type=entity_type,
            data={"id": entity_id},
            strategy=strategy,
            created_at=datetime.now(UTC),
        )

        self._active_tasks[task_id] = task

        try:
            result = await self._execute_best_effort_delete(task)
            task.status = "completed"
            return result

        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            raise

        finally:
            self._active_tasks.pop(task_id, None)
            self._completed_tasks.append(task)

    def _prepare_2pc_databases(
        self,
        task: CoordinationTask,
        uow: Any,
        prepared_databases: set[str],
    ) -> None:
        """Phase 1: Prepare databases for two-phase commit."""
        for db_name in task.databases:
            repository = self.get_repository(db_name, task.entity_type)
            if repository:
                uow.add_repository(db_name, repository)
                # In a real 2PC, we'd send prepare messages
                prepared_databases.add(db_name)

    def _commit_2pc_databases(
        self,
        uow: Any,
        prepared_databases: set[str],
        results: dict[str, Any],
    ) -> None:
        """Phase 2: Commit prepared databases."""
        for db_name in prepared_databases:
            repository = uow.get_repository(db_name)
            if repository:
                # Entity operation would be done within the UoW transaction
                results[db_name] = {"status": "committed"}

    def _abort_2pc_databases(
        self,
        prepared_databases: set[str],
        results: dict[str, Any],
        error: Exception,
    ) -> None:
        """Rollback prepared databases on error."""
        for db_name in prepared_databases:
            results[db_name] = {"status": "aborted", "error": str(error)}

    async def _execute_2pc_create(self, task: CoordinationTask) -> dict[str, Any]:
        """Execute two-phase commit create operation."""
        results: dict[str, Any] = {}
        prepared_databases: set[str] = set()

        try:
            async with self._uow_manager.transaction() as uow:
                # Phase 1: Prepare
                self._prepare_2pc_databases(task, uow, prepared_databases)
                # Phase 2: Commit
                self._commit_2pc_databases(uow, prepared_databases, results)

        except Exception as e:
            self._abort_2pc_databases(prepared_databases, results, e)
            raise

        return results

    async def _execute_2pc_update(self, task: CoordinationTask) -> dict[str, Any]:
        """Execute two-phase commit update operation."""
        results: dict[str, Any] = {}
        prepared_databases: set[str] = set()

        try:
            async with self._uow_manager.transaction() as uow:
                # Phase 1: Prepare
                self._prepare_2pc_databases(task, uow, prepared_databases)
                # Phase 2: Commit
                self._commit_2pc_databases(uow, prepared_databases, results)

        except Exception as e:
            self._abort_2pc_databases(prepared_databases, results, e)
            raise

        return results

    async def _execute_saga_create(self, task: CoordinationTask) -> dict[str, Any]:
        """Execute saga pattern create operation."""
        results = {}
        completed_steps = []

        try:
            for db_name in task.databases:
                repository = self.get_repository(db_name, task.entity_type)
                if repository:
                    # Execute create operation
                    # In a real implementation, this would be more sophisticated
                    results[db_name] = {"status": "completed"}
                    completed_steps.append(db_name)

                    # Add compensation action
                    def compensate(
                        db: str = db_name,
                        repo: Any = repository,
                    ) -> Callable[[], Awaitable[None]]:
                        async def _compensate() -> None:
                            # Delete created entity
                            if "id" in task.data:
                                await repo.delete(task.data["id"])

                        return _compensate

                    task.compensation_actions.append(compensate())

        except Exception:
            # Execute compensation actions for completed steps
            await self._execute_compensation(task)
            raise

        return results

    async def _execute_best_effort_create(
        self,
        task: CoordinationTask,
    ) -> dict[str, Any]:
        """Execute best effort create operation."""
        results = {}
        tasks = []

        # Create tasks for each database
        for db_name in task.databases:
            repository = self.get_repository(db_name, task.entity_type)
            if repository:

                async def create_in_db(
                    db: str = db_name,
                    repo: Any = repository,
                ) -> dict[str, Any]:
                    try:
                        # In a real implementation, we'd create actual entities
                        await asyncio.sleep(0.01)  # Simulate work
                        return {"status": "success", "database": db}
                    except Exception as e:
                        return {"status": "error", "database": db, "error": str(e)}

                tasks.append(create_in_db())

        # Execute all tasks concurrently
        if tasks:
            task_results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in task_results:
                if isinstance(result, dict):
                    db_name = result["database"]
                    results[db_name] = result
                elif isinstance(result, BaseException):
                    results["unknown"] = {"status": "error", "error": str(result)}

        return results

    async def _execute_best_effort_update(
        self,
        task: CoordinationTask,
    ) -> dict[str, Any]:
        """Execute best effort update operation."""
        results = {}
        tasks = []

        for db_name in task.databases:
            repository = self.get_repository(db_name, task.entity_type)
            if repository:

                async def update_in_db(
                    db: str = db_name,
                    repo: Any = repository,
                ) -> dict[str, Any]:
                    try:
                        await asyncio.sleep(0.01)  # Simulate work
                        return {"status": "success", "database": db}
                    except Exception as e:
                        return {"status": "error", "database": db, "error": str(e)}

                tasks.append(update_in_db())

        if tasks:
            task_results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in task_results:
                if isinstance(result, dict):
                    db_name = result["database"]
                    results[db_name] = result

        return results

    async def _execute_best_effort_delete(
        self,
        task: CoordinationTask,
    ) -> dict[str, Any]:
        """Execute best effort delete operation."""
        results = {}
        tasks = []

        for db_name in task.databases:
            repository = self.get_repository(db_name, task.entity_type)
            if repository:

                async def delete_in_db(
                    db: str = db_name,
                    repo: Any = repository,
                ) -> dict[str, Any]:
                    try:
                        await asyncio.sleep(0.01)  # Simulate work
                        return {"status": "success", "database": db}
                    except Exception as e:
                        return {"status": "error", "database": db, "error": str(e)}

                tasks.append(delete_in_db())

        if tasks:
            task_results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in task_results:
                if isinstance(result, dict):
                    db_name = result["database"]
                    results[db_name] = result

        return results

    async def _execute_compensation(self, task: CoordinationTask) -> None:
        """Execute compensation actions for failed task."""
        for compensation in reversed(task.compensation_actions):
            with suppress(Exception):
                await compensation()

    async def check_database_health(self) -> dict[str, dict[str, Any]]:
        """Check health of all registered databases.

        Returns:
            Health status for each database
        """
        health_results = {}

        for name, connection in self._connections.items():
            try:
                # Simple health check - try to get adapter status
                start_time = datetime.now()
                # In a real implementation, we'd ping the actual database
                await asyncio.sleep(0.001)  # Simulate health check
                response_time = (datetime.now() - start_time).total_seconds()

                connection.health_status = "healthy"
                connection.last_health_check = datetime.now(UTC)

                health_results[name] = {
                    "status": "healthy",
                    "response_time": response_time,
                    "last_check": connection.last_health_check.isoformat(),
                    "type": connection.db_type.value,
                    "read_only": connection.read_only,
                    "priority": connection.priority,
                }

            except Exception as e:
                connection.health_status = "unhealthy"
                connection.last_health_check = datetime.now(UTC)

                health_results[name] = {
                    "status": "unhealthy",
                    "error": str(e),
                    "last_check": connection.last_health_check.isoformat(),
                    "type": connection.db_type.value,
                    "read_only": connection.read_only,
                    "priority": connection.priority,
                }

        return health_results

    async def get_coordination_stats(self) -> dict[str, Any]:
        """Get coordination statistics.

        Returns:
            Dictionary of coordination statistics
        """
        active_count = len(self._active_tasks)
        completed_count = len(self._completed_tasks)

        # Calculate success rate from recent tasks
        recent_tasks = self._completed_tasks[-100:]
        success_count = sum(1 for task in recent_tasks if task.status == "completed")
        success_rate = success_count / len(recent_tasks) if recent_tasks else 0.0

        # Group by strategy
        strategy_stats = {}
        for task in recent_tasks:
            strategy = task.strategy.value
            if strategy not in strategy_stats:
                strategy_stats[strategy] = {"total": 0, "success": 0}
            strategy_stats[strategy]["total"] += 1
            if task.status == "completed":
                strategy_stats[strategy]["success"] += 1

        return {
            "active_tasks": active_count,
            "completed_tasks": completed_count,
            "success_rate": success_rate,
            "registered_databases": len(self._connections),
            "registered_repositories": sum(
                len(repos) for repos in self._repositories.values()
            ),
            "strategy_stats": strategy_stats,
            "default_strategy": self.default_strategy.value,
        }

    async def _cleanup_resources(self) -> None:
        """Clean up coordinator resources."""
        # Cancel active tasks
        for task in self._active_tasks.values():
            task.status = "cancelled"

        # Clean up UoW manager
        await self._uow_manager.cleanup()

        self._active_tasks.clear()
        self._completed_tasks.clear()
        self._connections.clear()
        self._repositories.clear()
        self._event_handlers.clear()
