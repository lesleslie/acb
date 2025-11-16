"""Unit of Work Pattern Implementation.

Provides transaction management and coordination across multiple repositories:
- Unit of Work pattern for managing database transactions
- Repository coordination within transactions
- Automatic rollback on failures
- Integration with ACB database adapters
"""

import uuid
from enum import Enum

import asyncio
import typing as t
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from acb.cleanup import CleanupMixin
from acb.depends import depends

from ._base import RepositoryBase, RepositoryError


class UnitOfWorkState(Enum):
    """Unit of Work state enumeration."""

    INACTIVE = "inactive"
    ACTIVE = "active"
    COMMITTING = "committing"
    COMMITTED = "committed"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


@dataclass
class UnitOfWorkMetrics:
    """Metrics for Unit of Work operations."""

    transaction_id: str
    start_time: datetime
    end_time: datetime | None = None
    state: UnitOfWorkState = UnitOfWorkState.INACTIVE
    operations_count: int = 0
    repositories_used: set[str] = field(default_factory=set)
    error_message: str | None = None

    @property
    def duration(self) -> float | None:
        """Get transaction duration in seconds."""
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time).total_seconds()


class UnitOfWorkError(RepositoryError):
    """Exception for Unit of Work operations."""

    def __init__(
        self,
        message: str,
        transaction_id: str | None = None,
        state: UnitOfWorkState | None = None,
    ) -> None:
        super().__init__(message, operation="unit_of_work")
        self.transaction_id = transaction_id
        self.state = state


class UnitOfWork(CleanupMixin):
    """Unit of Work implementation for transaction management.

    Coordinates database operations across multiple repositories within
    a single transaction, ensuring ACID properties and automatic rollback
    on failures.
    """

    def __init__(
        self,
        isolation_level: str | None = None,
        timeout: float | None = None,
    ) -> None:
        super().__init__()
        transaction_id = str(uuid.uuid4())
        self.isolation_level = isolation_level
        self.timeout = timeout or 60.0
        self._state = UnitOfWorkState.INACTIVE
        self._repositories: dict[str, RepositoryBase[Any, Any]] = {}
        self._operations: list[dict[str, Any]] = []
        self._sql_sessions: dict[str, Any] = {}
        self._nosql_sessions: dict[str, Any] = {}
        self._metrics = UnitOfWorkMetrics(
            transaction_id=transaction_id,
            start_time=datetime.now(UTC),
        )
        self._transaction_context = None
        self._rollback_operations: list[t.Callable[..., Any]] = []

    @property
    def state(self) -> UnitOfWorkState:
        """Get current Unit of Work state."""
        return self._state

    @property
    def is_active(self) -> bool:
        """Check if Unit of Work is active."""
        return self._state == UnitOfWorkState.ACTIVE

    @property
    def transaction_id(self) -> str:
        """Get transaction ID."""
        return self._metrics.transaction_id

    @transaction_id.setter
    def transaction_id(self, value: str) -> None:
        """Set transaction ID."""
        self._metrics.transaction_id = value

    def add_repository(self, name: str, repository: RepositoryBase[Any, Any]) -> None:
        """Add a repository to this Unit of Work.

        Args:
            name: Repository identifier
            repository: Repository instance
        """
        if self._state != UnitOfWorkState.INACTIVE:
            msg = f"Cannot add repository {name} in state {self._state}"
            raise UnitOfWorkError(
                msg,
                self.transaction_id,
                self._state,
            )

        self._repositories[name] = repository
        self._metrics.repositories_used.add(name)

    def get_repository(self, name: str) -> RepositoryBase[Any, Any] | None:
        """Get repository by name.

        Args:
            name: Repository identifier

        Returns:
            Repository instance or None if not found
        """
        return self._repositories.get(name)

    async def begin(self) -> None:
        """Begin the Unit of Work transaction."""
        if self._state != UnitOfWorkState.INACTIVE:
            msg = f"Cannot begin transaction in state {self._state}"
            raise UnitOfWorkError(
                msg,
                self.transaction_id,
                self._state,
            )

        try:
            self._state = UnitOfWorkState.ACTIVE
            self._metrics.start_time = datetime.now(UTC)

            # Initialize database sessions
            await self._initialize_sessions()

            # Set up timeout
            if self.timeout:
                asyncio.create_task(self._timeout_handler())

        except Exception as e:
            self._state = UnitOfWorkState.FAILED
            self._metrics.error_message = str(e)
            msg = f"Failed to begin transaction: {e}"
            raise UnitOfWorkError(
                msg,
                self.transaction_id,
                self._state,
            ) from e

    async def commit(self) -> None:
        """Commit the Unit of Work transaction."""
        if self._state != UnitOfWorkState.ACTIVE:
            msg = f"Cannot commit transaction in state {self._state}"
            raise UnitOfWorkError(
                msg,
                self.transaction_id,
                self._state,
            )

        try:
            self._state = UnitOfWorkState.COMMITTING

            # Commit all database sessions
            await self._commit_sessions()

            self._state = UnitOfWorkState.COMMITTED
            self._metrics.end_time = datetime.now(UTC)

        except Exception as e:
            self._metrics.error_message = str(e)
            await self.rollback()
            msg = f"Failed to commit transaction: {e}"
            raise UnitOfWorkError(
                msg,
                self.transaction_id,
                self._state,
            ) from e

    async def rollback(self) -> None:
        """Rollback the Unit of Work transaction."""
        if self._state in (UnitOfWorkState.COMMITTED, UnitOfWorkState.ROLLED_BACK):
            return  # Already completed

        try:
            self._state = UnitOfWorkState.ROLLING_BACK

            # Execute rollback operations in reverse order
            for rollback_op in reversed(self._rollback_operations):
                with suppress(Exception):
                    await rollback_op()

            # Rollback all database sessions
            await self._rollback_sessions()

            self._state = UnitOfWorkState.ROLLED_BACK
            self._metrics.end_time = datetime.now(UTC)

        except Exception as e:
            self._state = UnitOfWorkState.FAILED
            self._metrics.error_message = str(e)
            msg = f"Failed to rollback transaction: {e}"
            raise UnitOfWorkError(
                msg,
                self.transaction_id,
                self._state,
            ) from e

    def add_operation(self, operation: str, entity_type: str, data: Any = None) -> None:
        """Record an operation for tracking.

        Args:
            operation: Operation type (create, update, delete)
            entity_type: Type of entity being operated on
            data: Optional operation data
        """
        self._operations.append(
            {
                "operation": operation,
                "entity_type": entity_type,
                "timestamp": datetime.now(UTC),
                "data": data,
            },
        )
        self._metrics.operations_count += 1

    def add_rollback_operation(self, operation: t.Callable[..., Any]) -> None:
        """Add a rollback operation to be executed if transaction fails.

        Args:
            operation: Async callable to execute during rollback
        """
        self._rollback_operations.append(operation)

    async def _initialize_sessions(self) -> None:
        """Initialize database sessions for transaction."""
        try:
            # Initialize SQL sessions
            from acb.adapters import import_adapter

            with suppress(ImportError):
                Sql = import_adapter("sql")
                sql = await depends.get(Sql)
                session = await sql._ensure_session()
                self._sql_sessions["default"] = session
                # Begin SQL transaction
                await session.begin()
            # SQL adapter not available

            # Initialize NoSQL sessions if needed
            with suppress(ImportError):
                Nosql = import_adapter("nosql")
                nosql = await depends.get(Nosql)
                session = await nosql.get_client()
                self._nosql_sessions["default"] = session
                # NoSQL doesn't typically support transactions like SQL
        # NoSQL adapter not available

        except Exception as e:
            msg = f"Failed to initialize sessions: {e}"
            raise UnitOfWorkError(msg) from e

    async def _commit_sessions(self) -> None:
        """Commit all database sessions."""
        errors = []

        # Commit SQL sessions
        for name, session in self._sql_sessions.items():
            try:
                if hasattr(session, "commit"):
                    await session.commit()
            except Exception as e:
                errors.append(f"SQL session {name}: {e}")

        # NoSQL doesn't typically need explicit commit
        # But we can flush any pending operations

        if errors:
            msg = f"Session commit errors: {'; '.join(errors)}"
            raise UnitOfWorkError(msg)

    async def _rollback_sessions(self) -> None:
        """Rollback all database sessions."""
        errors = []

        # Rollback SQL sessions
        for name, session in self._sql_sessions.items():
            try:
                if hasattr(session, "rollback"):
                    await session.rollback()
            except Exception as e:
                errors.append(f"SQL session {name}: {e}")

        # NoSQL rollback is more complex and may not be supported
        # We rely on application-level rollback operations

        if errors:
            pass

    async def _timeout_handler(self) -> None:
        """Handle transaction timeout."""
        await asyncio.sleep(self.timeout)
        if self._state == UnitOfWorkState.ACTIVE:
            self._metrics.error_message = f"Transaction timeout after {self.timeout}s"
            await self.rollback()

    async def get_metrics(self) -> UnitOfWorkMetrics:
        """Get Unit of Work metrics.

        Returns:
            Metrics object with transaction information
        """
        self._metrics.state = self._state
        return self._metrics

    async def _cleanup_resources(self) -> None:
        """Clean up Unit of Work resources."""
        if self._state == UnitOfWorkState.ACTIVE:
            await self.rollback()

        # Close database sessions
        for session in self._sql_sessions.values():
            with suppress(Exception):
                if hasattr(session, "close"):
                    await session.close()

        self._sql_sessions.clear()
        self._nosql_sessions.clear()
        self._repositories.clear()
        self._operations.clear()
        self._rollback_operations.clear()

    async def cleanup(self) -> None:
        """Clean up Unit of Work resources and ensure rollback if active."""
        # If still active, perform rollback
        if self._state == UnitOfWorkState.ACTIVE:
            await self.rollback()

        # Clean up registered resources
        await super().cleanup()


class UnitOfWorkManager(CleanupMixin):
    """Manager for Unit of Work instances.

    Provides factory methods and tracking for Unit of Work instances,
    with automatic cleanup and monitoring capabilities.
    """

    def __init__(self) -> None:
        super().__init__()
        self._active_transactions: dict[str, UnitOfWork] = {}
        self._completed_transactions: list[UnitOfWorkMetrics] = []
        self._max_completed_history = 1000

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
        uow = UnitOfWork(isolation_level, timeout)
        self._active_transactions[uow.transaction_id] = uow
        return uow

    @asynccontextmanager
    async def transaction(
        self,
        isolation_level: str | None = None,
        timeout: float | None = None,
    ) -> t.AsyncGenerator[UnitOfWork]:
        """Context manager for Unit of Work transactions.

        Args:
            isolation_level: Database isolation level
            timeout: Transaction timeout in seconds

        Yields:
            Unit of Work instance
        """
        uow = await self.create_unit_of_work(isolation_level, timeout)
        try:
            await uow.begin()
            yield uow
            await uow.commit()
        except Exception:
            await uow.rollback()
            raise
        finally:
            await self._complete_transaction(uow)

    async def get_active_transactions(self) -> list[UnitOfWorkMetrics]:
        """Get metrics for all active transactions.

        Returns:
            List of metrics for active transactions
        """
        return [await uow.get_metrics() for uow in self._active_transactions.values()]

    async def get_transaction_history(
        self,
        limit: int = 100,
    ) -> list[UnitOfWorkMetrics]:
        """Get completed transaction history.

        Args:
            limit: Maximum number of transactions to return

        Returns:
            List of completed transaction metrics
        """
        return self._completed_transactions[-limit:]

    async def get_transaction_stats(self) -> dict[str, Any]:
        """Get transaction statistics.

        Returns:
            Dictionary of transaction statistics
        """
        active_count = len(self._active_transactions)
        completed_count = len(self._completed_transactions)

        # Calculate success rate from recent transactions
        recent_transactions = self._completed_transactions[-100:]
        success_count = sum(
            1
            for metrics in recent_transactions
            if metrics.state == UnitOfWorkState.COMMITTED
        )
        success_rate = (
            success_count / len(recent_transactions) if recent_transactions else 0.0
        )

        # Calculate average duration
        durations = [
            metrics.duration
            for metrics in recent_transactions
            if metrics.duration is not None
        ]
        avg_duration = sum(durations) / len(durations) if durations else 0.0

        return {
            "active_transactions": active_count,
            "completed_transactions": completed_count,
            "success_rate": success_rate,
            "average_duration_seconds": avg_duration,
            "max_history_size": self._max_completed_history,
        }

    async def _complete_transaction(self, uow: UnitOfWork) -> None:
        """Complete a transaction and move to history.

        Args:
            uow: Unit of Work instance to complete
        """
        # Remove from active transactions
        if uow.transaction_id in self._active_transactions:
            del self._active_transactions[uow.transaction_id]

        # Add to completed history
        metrics = await uow.get_metrics()
        self._completed_transactions.append(metrics)

        # Trim history if needed
        if len(self._completed_transactions) > self._max_completed_history:
            self._completed_transactions = self._completed_transactions[
                -self._max_completed_history :
            ]

        # Clean up the UoW
        await uow.cleanup()

    async def _cleanup_resources(self) -> None:
        """Clean up all Unit of Work resources."""
        # Rollback all active transactions
        for uow in list(self._active_transactions.values()):
            with suppress(Exception):
                await uow.rollback()
                await uow.cleanup()

        self._active_transactions.clear()
        self._completed_transactions.clear()

    async def cleanup(self) -> None:
        """Clean up manager and all active transactions."""
        await self._cleanup_resources()
        await super().cleanup()
