"""Tests for Unit of Work Pattern."""

from unittest.mock import AsyncMock, patch

import asyncio
import pytest
from dataclasses import dataclass
from datetime import datetime

from acb.services.repository._base import RepositoryBase
from acb.services.repository.unit_of_work import (
    UnitOfWork,
    UnitOfWorkError,
    UnitOfWorkManager,
    UnitOfWorkMetrics,
    UnitOfWorkState,
)


@dataclass
class SampleEntity:
    """Test entity for UoW tests."""

    id: int | None = None
    name: str = ""


class MockRepository(RepositoryBase):
    """Mock repository for testing."""

    def __init__(self):
        super().__init__(SampleEntity)
        self.operations = []

    async def create(self, entity):
        self.operations.append(("create", entity))
        return entity

    async def update(self, entity):
        self.operations.append(("update", entity))
        return entity

    async def delete(self, entity_id):
        self.operations.append(("delete", entity_id))
        return True

    async def get_by_id(self, entity_id):
        return SampleEntity(id=entity_id, name=f"Entity {entity_id}")

    async def list(self, filters=None, sort=None, pagination=None):
        return []

    async def count(self, filters=None):
        return 0


@pytest.fixture
def mock_repository():
    """Create mock repository."""
    return MockRepository()


@pytest.fixture
def uow():
    """Create Unit of Work."""
    return UnitOfWork()


@pytest.fixture
def uow_manager():
    """Create Unit of Work Manager."""
    return UnitOfWorkManager()


class TestUnitOfWork:
    """Test Unit of Work functionality."""

    @pytest.mark.asyncio
    async def test_uow_initialization(self, uow):
        """Test UoW initialization."""
        assert uow.state == UnitOfWorkState.INACTIVE
        assert uow.transaction_id is not None
        assert not uow.is_active

    @pytest.mark.asyncio
    async def test_uow_begin(self, uow):
        """Test UoW begin operation."""
        with patch.object(uow, "_initialize_sessions", new_callable=AsyncMock):
            await uow.begin()
            assert uow.state == UnitOfWorkState.ACTIVE
            assert uow.is_active

    @pytest.mark.asyncio
    async def test_uow_begin_invalid_state(self, uow):
        """Test UoW begin from invalid state."""
        uow._state = UnitOfWorkState.COMMITTED

        with pytest.raises(UnitOfWorkError) as exc_info:
            await uow.begin()

        assert "Cannot begin transaction in state" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_uow_add_repository(self, uow, mock_repository):
        """Test adding repository to UoW."""
        uow.add_repository("test_repo", mock_repository)

        assert uow.get_repository("test_repo") is mock_repository
        assert "test_repo" in uow._metrics.repositories_used

    @pytest.mark.asyncio
    async def test_uow_add_repository_invalid_state(self, uow, mock_repository):
        """Test adding repository in invalid state."""
        uow._state = UnitOfWorkState.ACTIVE

        with pytest.raises(UnitOfWorkError):
            uow.add_repository("test_repo", mock_repository)

    @pytest.mark.asyncio
    async def test_uow_commit(self, uow):
        """Test UoW commit operation."""
        with (
            patch.object(uow, "_initialize_sessions", new_callable=AsyncMock),
            patch.object(uow, "_commit_sessions", new_callable=AsyncMock),
        ):
            await uow.begin()
            await uow.commit()

            assert uow.state == UnitOfWorkState.COMMITTED
            assert uow._metrics.end_time is not None

    @pytest.mark.asyncio
    async def test_uow_commit_invalid_state(self, uow):
        """Test UoW commit from invalid state."""
        with pytest.raises(UnitOfWorkError) as exc_info:
            await uow.commit()

        assert "Cannot commit transaction in state" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_uow_rollback(self, uow):
        """Test UoW rollback operation."""
        with (
            patch.object(uow, "_initialize_sessions", new_callable=AsyncMock),
            patch.object(uow, "_rollback_sessions", new_callable=AsyncMock),
        ):
            await uow.begin()
            await uow.rollback()

            assert uow.state == UnitOfWorkState.ROLLED_BACK
            assert uow._metrics.end_time is not None

    @pytest.mark.asyncio
    async def test_uow_rollback_idempotent(self, uow):
        """Test UoW rollback is idempotent."""
        with (
            patch.object(uow, "_initialize_sessions", new_callable=AsyncMock),
            patch.object(uow, "_rollback_sessions", new_callable=AsyncMock),
        ):
            await uow.begin()
            await uow.rollback()

            # Second rollback should not raise error
            await uow.rollback()
            assert uow.state == UnitOfWorkState.ROLLED_BACK

    @pytest.mark.asyncio
    async def test_uow_add_operation(self, uow):
        """Test adding operation to UoW."""
        uow.add_operation("create", "SampleEntity", {"name": "test"})

        assert uow._metrics.operations_count == 1
        assert len(uow._operations) == 1

        operation = uow._operations[0]
        assert operation["operation"] == "create"
        assert operation["entity_type"] == "SampleEntity"

    @pytest.mark.asyncio
    async def test_uow_add_rollback_operation(self, uow):
        """Test adding rollback operation."""
        rollback_called = False

        async def rollback_op():
            nonlocal rollback_called
            rollback_called = True

        uow.add_rollback_operation(rollback_op)
        assert len(uow._rollback_operations) == 1

        # Execute rollback
        with (
            patch.object(uow, "_initialize_sessions", new_callable=AsyncMock),
            patch.object(uow, "_rollback_sessions", new_callable=AsyncMock),
        ):
            await uow.begin()
            await uow.rollback()

            assert rollback_called

    @pytest.mark.asyncio
    async def test_uow_timeout(self, uow):
        """Test UoW timeout handling."""
        uow.timeout = 0.1  # 100ms timeout

        with patch.object(uow, "_initialize_sessions", new_callable=AsyncMock):
            await uow.begin()

            # Wait for timeout
            await asyncio.sleep(0.2)

            # Should be rolled back due to timeout
            assert uow.state == UnitOfWorkState.ROLLED_BACK
            assert "timeout" in uow._metrics.error_message.lower()

    @pytest.mark.asyncio
    async def test_uow_get_metrics(self, uow):
        """Test UoW metrics."""
        uow.add_operation("create", "SampleEntity")
        uow.add_operation("update", "SampleEntity")

        metrics = await uow.get_metrics()

        assert isinstance(metrics, UnitOfWorkMetrics)
        assert metrics.transaction_id == uow.transaction_id
        assert metrics.operations_count == 2
        assert metrics.state == uow.state

    @pytest.mark.asyncio
    async def test_uow_cleanup(self, uow, mock_repository):
        """Test UoW cleanup."""
        with patch.object(uow, "_initialize_sessions", new_callable=AsyncMock):
            uow.add_repository("test_repo", mock_repository)
            await uow.begin()

            # Cleanup should rollback if active
            await uow.cleanup()

            assert uow.state == UnitOfWorkState.ROLLED_BACK


class TestUnitOfWorkManager:
    """Test Unit of Work Manager functionality."""

    @pytest.mark.asyncio
    async def test_uow_manager_create_uow(self, uow_manager):
        """Test creating UoW through manager."""
        uow = await uow_manager.create_unit_of_work()

        assert uow is not None
        assert uow.transaction_id in uow_manager._active_transactions

    @pytest.mark.asyncio
    async def test_uow_manager_transaction_context(self, uow_manager):
        """Test transaction context manager."""
        operations_executed = []

        with (
            patch(
                "acb.services.repository.unit_of_work.UnitOfWork._initialize_sessions",
                new_callable=AsyncMock,
            ),
            patch(
                "acb.services.repository.unit_of_work.UnitOfWork._commit_sessions",
                new_callable=AsyncMock,
            ),
        ):
            async with uow_manager.transaction() as uow:
                operations_executed.append("operation")
                assert uow.is_active

            # UoW should be committed and cleaned up
            assert uow.state == UnitOfWorkState.COMMITTED
            assert len(operations_executed) == 1

    @pytest.mark.asyncio
    async def test_uow_manager_transaction_context_with_error(self, uow_manager):
        """Test transaction context manager with error."""
        with (
            patch(
                "acb.services.repository.unit_of_work.UnitOfWork._initialize_sessions",
                new_callable=AsyncMock,
            ),
            patch(
                "acb.services.repository.unit_of_work.UnitOfWork._rollback_sessions",
                new_callable=AsyncMock,
            ),
        ):
            with pytest.raises(ValueError):
                async with uow_manager.transaction() as uow:
                    assert uow.is_active
                    raise ValueError("Test error")

            # UoW should be rolled back
            assert uow.state == UnitOfWorkState.ROLLED_BACK

    @pytest.mark.asyncio
    async def test_uow_manager_get_active_transactions(self, uow_manager):
        """Test getting active transactions."""
        await uow_manager.create_unit_of_work()
        await uow_manager.create_unit_of_work()

        active_transactions = await uow_manager.get_active_transactions()

        assert len(active_transactions) == 2

    @pytest.mark.asyncio
    async def test_uow_manager_get_transaction_history(self, uow_manager):
        """Test getting transaction history."""
        with (
            patch(
                "acb.services.repository.unit_of_work.UnitOfWork._initialize_sessions",
                new_callable=AsyncMock,
            ),
            patch(
                "acb.services.repository.unit_of_work.UnitOfWork._commit_sessions",
                new_callable=AsyncMock,
            ),
        ):
            # Complete a transaction
            async with uow_manager.transaction():
                pass

            history = await uow_manager.get_transaction_history()
            assert len(history) == 1

    @pytest.mark.asyncio
    async def test_uow_manager_get_stats(self, uow_manager):
        """Test getting transaction statistics."""
        with (
            patch(
                "acb.services.repository.unit_of_work.UnitOfWork._initialize_sessions",
                new_callable=AsyncMock,
            ),
            patch(
                "acb.services.repository.unit_of_work.UnitOfWork._commit_sessions",
                new_callable=AsyncMock,
            ),
        ):
            # Create and complete some transactions
            async with uow_manager.transaction():
                pass

            stats = await uow_manager.get_transaction_stats()

            assert "active_transactions" in stats
            assert "completed_transactions" in stats
            assert "success_rate" in stats
            assert "average_duration_seconds" in stats

    @pytest.mark.asyncio
    async def test_uow_manager_cleanup(self, uow_manager):
        """Test UoW manager cleanup."""
        # Create some active transactions
        uow1 = await uow_manager.create_unit_of_work()
        uow2 = await uow_manager.create_unit_of_work()

        with (
            patch.object(uow1, "rollback", new_callable=AsyncMock) as rollback1,
            patch.object(uow2, "rollback", new_callable=AsyncMock) as rollback2,
            patch.object(uow1, "cleanup", new_callable=AsyncMock),
            patch.object(uow2, "cleanup", new_callable=AsyncMock),
        ):
            await uow_manager.cleanup()

            # All active transactions should be rolled back
            rollback1.assert_called_once()
            rollback2.assert_called_once()

            assert len(uow_manager._active_transactions) == 0
            assert len(uow_manager._completed_transactions) == 0


class TestUnitOfWorkMetrics:
    """Test Unit of Work Metrics functionality."""

    def test_metrics_initialization(self):
        """Test metrics initialization."""
        metrics = UnitOfWorkMetrics("test-id", datetime.now())

        assert metrics.transaction_id == "test-id"
        assert metrics.duration is None  # No end time set
        assert metrics.operations_count == 0

    def test_metrics_duration_calculation(self):
        """Test duration calculation."""
        from datetime import datetime, timedelta

        start_time = datetime.now()
        end_time = start_time + timedelta(seconds=1.5)

        metrics = UnitOfWorkMetrics("test-id", start_time, end_time)

        assert metrics.duration == 1.5


class TestUnitOfWorkErrors:
    """Test Unit of Work error handling."""

    def test_uow_error_basic(self):
        """Test basic UoW error."""
        error = UnitOfWorkError("Test error", "test-id", UnitOfWorkState.FAILED)

        assert error.transaction_id == "test-id"
        assert error.state == UnitOfWorkState.FAILED
        assert error.operation == "unit_of_work"
        assert "Test error" in str(error)
