"""Tests for queue base classes and common functionality."""

from uuid import uuid4

import asyncio
import pytest
from datetime import datetime, timedelta

from acb.tasks._base import (
    FunctionalTaskHandler,
    QueueBase,
    QueueMetrics,
    QueueSettings,
    TaskData,
    TaskHandler,
    TaskPriority,
    TaskResult,
    TaskStatus,
    WorkerMetrics,
    create_task_data,
    task_handler,
)


class MockTaskHandler(TaskHandler):
    """Mock task handler for testing."""

    def __init__(self, result_value=None, should_fail=False, delay=0.0):
        self.result_value = result_value or "success"
        self.should_fail = should_fail
        self.delay = delay
        self.handle_calls = []
        self.failure_calls = []
        self.success_calls = []

    async def handle(self, task: TaskData) -> TaskResult:
        """Handle a task."""
        self.handle_calls.append(task)

        if self.delay > 0:
            await asyncio.sleep(self.delay)

        if self.should_fail:
            raise ValueError("Simulated task failure")

        return TaskResult(
            task_id=task.task_id,
            status=TaskStatus.COMPLETED,
            result=self.result_value,
            queue_name=task.queue_name,
        )

    async def on_failure(self, task: TaskData, error: Exception) -> bool:
        """Handle task failure."""
        self.failure_calls.append((task, error))
        return True  # Allow retry by default

    async def on_success(self, task: TaskData, result: TaskResult) -> None:
        """Handle task success."""
        self.success_calls.append((task, result))


class MockQueue(QueueBase):
    """Mock queue implementation for testing base functionality."""

    def __init__(self, settings: QueueSettings | None = None):
        super().__init__(settings)
        self.enqueued_tasks = []
        self.dequeued_tasks = []
        self.task_storage = {}
        self.queue_storage = {}

    async def enqueue(self, task: TaskData) -> str:
        """Enqueue a task."""
        self.enqueued_tasks.append(task)
        self.task_storage[task.task_id] = task
        return str(task.task_id)

    async def dequeue(self, queue_name: str | None = None) -> TaskData | None:
        """Dequeue a task."""
        if self.enqueued_tasks:
            task = self.enqueued_tasks.pop(0)
            self.dequeued_tasks.append(task)
            return task
        return None

    async def get_task_status(self, task_id) -> TaskResult | None:
        """Get task status."""
        return None

    async def cancel_task(self, task_id) -> bool:
        """Cancel a task."""
        return False

    async def get_queue_info(self, queue_name: str) -> dict:
        """Get queue info."""
        return {"name": queue_name}

    async def purge_queue(self, queue_name: str) -> int:
        """Purge queue."""
        return 0

    async def list_queues(self) -> list[str]:
        """List queues."""
        return ["default"]

    async def _store_dead_letter_task(self, task: TaskData, result: TaskResult) -> None:
        """Store dead letter task."""
        pass


@pytest.fixture
def sample_task():
    """Create a sample task for testing."""
    return TaskData(
        task_type="test_task",
        queue_name="test_queue",
        payload={"message": "Hello, World!"},
        priority=TaskPriority.NORMAL,
    )


@pytest.fixture
def mock_handler():
    """Create a mock task handler."""
    return MockTaskHandler()


@pytest.fixture
def mock_queue():
    """Create a mock queue."""
    return MockQueue()


class TestTaskData:
    """Test TaskData model."""

    def test_task_data_creation(self):
        """Test creating TaskData."""
        task = TaskData(
            task_type="email_task",
            queue_name="email_queue",
            payload={"to": "user@example.com", "subject": "Test"},
            priority=TaskPriority.HIGH,
        )

        assert task.task_type == "email_task"
        assert task.queue_name == "email_queue"
        assert task.payload["to"] == "user@example.com"
        assert task.priority == TaskPriority.HIGH
        assert isinstance(task.created_at, datetime)

    def test_task_data_with_delay(self):
        """Test TaskData with delay."""
        task = TaskData(
            task_type="delayed_task",
            queue_name="default",
            delay=60.0,
        )

        assert task.delay == 60.0

    def test_task_data_with_scheduled_time(self):
        """Test TaskData with scheduled time."""
        scheduled_time = datetime.utcnow() + timedelta(hours=1)
        task = TaskData(
            task_type="scheduled_task",
            queue_name="default",
            scheduled_at=scheduled_time,
        )

        assert task.scheduled_at == scheduled_time

    def test_create_task_data_helper(self):
        """Test create_task_data helper function."""
        task = create_task_data(
            "helper_task",
            payload={"key": "value"},
            priority=TaskPriority.LOW,
        )

        assert task.task_type == "helper_task"
        assert task.payload["key"] == "value"
        assert task.priority == TaskPriority.LOW


class TestTaskResult:
    """Test TaskResult model."""

    def test_task_result_creation(self):
        """Test creating TaskResult."""
        task_id = uuid4()
        result = TaskResult(
            task_id=task_id,
            status=TaskStatus.COMPLETED,
            result={"success": True},
            queue_name="test_queue",
        )

        assert result.task_id == task_id
        assert result.status == TaskStatus.COMPLETED
        assert result.result["success"] is True
        assert result.queue_name == "test_queue"

    def test_task_result_with_error(self):
        """Test TaskResult with error."""
        task_id = uuid4()
        result = TaskResult(
            task_id=task_id,
            status=TaskStatus.FAILED,
            error="Something went wrong",
            queue_name="test_queue",
        )

        assert result.status == TaskStatus.FAILED
        assert result.error == "Something went wrong"

    def test_task_result_timing(self):
        """Test TaskResult with timing information."""
        task_id = uuid4()
        start_time = datetime.utcnow()
        end_time = start_time + timedelta(seconds=5)

        result = TaskResult(
            task_id=task_id,
            status=TaskStatus.COMPLETED,
            started_at=start_time,
            completed_at=end_time,
            execution_time=5.0,
            queue_name="test_queue",
        )

        assert result.started_at == start_time
        assert result.completed_at == end_time
        assert result.execution_time == 5.0


class TestTaskHandler:
    """Test task handler functionality."""

    @pytest.mark.asyncio
    async def test_mock_task_handler_success(self, sample_task):
        """Test successful task handling."""
        handler = MockTaskHandler(result_value="test_success")

        result = await handler.handle(sample_task)

        assert result.status == TaskStatus.COMPLETED
        assert result.result == "test_success"
        assert len(handler.handle_calls) == 1

    @pytest.mark.asyncio
    async def test_mock_task_handler_failure(self, sample_task):
        """Test task handling failure."""
        handler = MockTaskHandler(should_fail=True)

        with pytest.raises(ValueError, match="Simulated task failure"):
            await handler.handle(sample_task)

        assert len(handler.handle_calls) == 1

    @pytest.mark.asyncio
    async def test_task_handler_callbacks(self, sample_task):
        """Test task handler callbacks."""
        handler = MockTaskHandler()

        # Test success callback
        result = await handler.handle(sample_task)
        await handler.on_success(sample_task, result)

        assert len(handler.success_calls) == 1
        assert handler.success_calls[0][0] == sample_task
        assert handler.success_calls[0][1] == result

        # Test failure callback
        error = ValueError("Test error")
        should_retry = await handler.on_failure(sample_task, error)

        assert should_retry is True
        assert len(handler.failure_calls) == 1
        assert handler.failure_calls[0][0] == sample_task
        assert handler.failure_calls[0][1] == error


class TestFunctionalTaskHandler:
    """Test functional task handler."""

    @pytest.mark.asyncio
    async def test_functional_handler_creation(self, sample_task):
        """Test creating functional task handler."""

        async def test_function(task):
            return {"processed": task.payload["message"]}

        handler = FunctionalTaskHandler(test_function)
        result = await handler.handle(sample_task)

        assert result.status == TaskStatus.COMPLETED
        assert result.result["processed"] == "Hello, World!"

    @pytest.mark.asyncio
    async def test_functional_handler_with_callbacks(self, sample_task):
        """Test functional handler with callbacks."""

        async def test_function(task):
            return "success"

        async def on_failure_func(task, error):
            return False  # Don't retry

        async def on_success_func(task, result):
            result.custom_field = "added"

        handler = FunctionalTaskHandler(test_function, on_failure_func, on_success_func)

        # Test success
        result = await handler.handle(sample_task)
        await handler.on_success(sample_task, result)

        assert result.result == "success"

        # Test failure callback
        error = ValueError("Test error")
        should_retry = await handler.on_failure(sample_task, error)
        assert should_retry is False

    @pytest.mark.asyncio
    async def test_task_handler_decorator(self, sample_task):
        """Test task_handler decorator."""

        @task_handler("decorated_task")
        async def decorated_function(task):
            return f"Processed: {task.payload.get('message', 'default')}"

        assert isinstance(decorated_function, FunctionalTaskHandler)
        assert hasattr(decorated_function, "task_type")
        assert decorated_function.task_type == "decorated_task"

        result = await decorated_function.handle(sample_task)
        assert result.status == TaskStatus.COMPLETED
        assert result.result == "Processed: Hello, World!"


class TestQueueBase:
    """Test QueueBase functionality."""

    @pytest.mark.asyncio
    async def test_queue_lifecycle(self, mock_queue):
        """Test queue lifecycle methods."""
        assert not mock_queue.is_running

        await mock_queue.start()
        assert mock_queue.is_running

        await mock_queue.stop()
        assert not mock_queue.is_running

    @pytest.mark.asyncio
    async def test_handler_registration(self, mock_queue, mock_handler):
        """Test handler registration."""
        task_type = "test_task"

        # Register handler
        mock_queue.register_handler(task_type, mock_handler)

        # Check handler is registered
        registered_handler = mock_queue.get_handler(task_type)
        assert registered_handler == mock_handler

        # Check handler list
        handlers = mock_queue.list_handlers()
        assert task_type in handlers

        # Unregister handler
        mock_queue.unregister_handler(task_type)
        assert mock_queue.get_handler(task_type) is None

    @pytest.mark.asyncio
    async def test_task_enqueue_dequeue(self, mock_queue, sample_task):
        """Test basic enqueue/dequeue functionality."""
        # Enqueue task
        task_id = await mock_queue.enqueue(sample_task)
        assert task_id == str(sample_task.task_id)
        assert len(mock_queue.enqueued_tasks) == 1

        # Dequeue task
        dequeued_task = await mock_queue.dequeue()
        assert dequeued_task == sample_task
        assert len(mock_queue.dequeued_tasks) == 1

    @pytest.mark.asyncio
    async def test_create_task_convenience_method(self, mock_queue):
        """Test create_task convenience method."""
        await mock_queue.create_task(
            "convenience_task",
            payload={"test": "data"},
            priority=TaskPriority.HIGH,
        )

        assert len(mock_queue.enqueued_tasks) == 1
        task = mock_queue.enqueued_tasks[0]
        assert task.task_type == "convenience_task"
        assert task.payload["test"] == "data"
        assert task.priority == TaskPriority.HIGH

    @pytest.mark.asyncio
    async def test_worker_management(self, mock_queue):
        """Test worker management."""
        await mock_queue.start()

        # Start workers
        await mock_queue.start_workers(3)
        assert len(mock_queue._workers) == 3

        # Stop workers
        await mock_queue.stop_workers()
        assert len(mock_queue._workers) == 0

        await mock_queue.stop()

    @pytest.mark.asyncio
    async def test_queue_metrics(self, mock_queue):
        """Test queue metrics."""
        metrics = mock_queue.metrics
        assert isinstance(metrics, QueueMetrics)
        assert isinstance(metrics.worker_metrics, WorkerMetrics)

        # Test metrics updates
        mock_queue._metrics.completed_tasks = 10
        mock_queue._metrics.failed_tasks = 2

        assert mock_queue.metrics.completed_tasks == 10
        assert mock_queue.metrics.failed_tasks == 2

    @pytest.mark.asyncio
    async def test_health_check(self, mock_queue):
        """Test health check functionality."""
        await mock_queue.start()

        health = await mock_queue.health_check()
        assert isinstance(health, dict)
        assert "healthy" in health
        assert "metrics" in health

        await mock_queue.stop()

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_queue):
        """Test queue as context manager."""
        async with mock_queue as queue:
            assert queue.is_running
            assert queue == mock_queue

        assert not mock_queue.is_running


class TestQueueSettings:
    """Test queue settings."""

    def test_default_settings(self):
        """Test default queue settings."""
        settings = QueueSettings()

        assert settings.enabled is True
        assert settings.max_workers == 10
        assert settings.default_task_timeout == 300.0
        assert settings.max_retries == 3
        assert settings.retry_delay == 1.0

    def test_custom_settings(self):
        """Test custom queue settings."""
        settings = QueueSettings(
            max_workers=20,
            default_task_timeout=600.0,
            max_retries=5,
            retry_delay=2.0,
        )

        assert settings.max_workers == 20
        assert settings.default_task_timeout == 600.0
        assert settings.max_retries == 5
        assert settings.retry_delay == 2.0

    def test_settings_validation(self):
        """Test settings validation."""
        # Test that settings can be created with valid values
        settings = QueueSettings(
            max_workers=1,
            retry_delay=0.1,
        )
        assert settings.max_workers == 1
        assert settings.retry_delay == 0.1


@pytest.mark.asyncio
class TestIntegration:
    """Integration tests for queue functionality."""

    async def test_full_task_processing_workflow(self, mock_queue, sample_task):
        """Test complete task processing workflow."""
        # Create and register handler
        handler = MockTaskHandler(result_value="integration_success")
        mock_queue.register_handler(sample_task.task_type, handler)

        # Start queue
        await mock_queue.start()

        # Enqueue task
        task_id = await mock_queue.enqueue(sample_task)
        assert task_id == str(sample_task.task_id)

        # Simulate task processing
        dequeued_task = await mock_queue.dequeue()
        assert dequeued_task == sample_task

        # Process task
        await mock_queue._process_task(dequeued_task, "test_worker")

        # Verify handler was called
        assert len(handler.handle_calls) == 1
        assert len(handler.success_calls) == 1

        await mock_queue.stop()

    async def test_task_failure_and_retry(self, mock_queue, sample_task):
        """Test task failure and retry logic."""
        # Create failing handler
        handler = MockTaskHandler(should_fail=True)
        mock_queue.register_handler(sample_task.task_type, handler)

        await mock_queue.start()

        # Process task (should fail)
        await mock_queue._process_task(sample_task, "test_worker")

        # Verify failure was handled
        assert len(handler.handle_calls) == 1
        assert len(handler.failure_calls) == 1

        await mock_queue.stop()

    async def test_multiple_task_types(self, mock_queue):
        """Test handling multiple task types."""
        # Create handlers for different task types
        email_handler = MockTaskHandler(result_value="email_sent")
        sms_handler = MockTaskHandler(result_value="sms_sent")

        mock_queue.register_handler("email_task", email_handler)
        mock_queue.register_handler("sms_task", sms_handler)

        # Create tasks
        email_task = TaskData(task_type="email_task", queue_name="notifications")
        sms_task = TaskData(task_type="sms_task", queue_name="notifications")

        await mock_queue.start()

        # Process email task
        await mock_queue._process_task(email_task, "worker_1")
        assert len(email_handler.handle_calls) == 1
        assert len(sms_handler.handle_calls) == 0

        # Process SMS task
        await mock_queue._process_task(sms_task, "worker_2")
        assert len(email_handler.handle_calls) == 1
        assert len(sms_handler.handle_calls) == 1

        await mock_queue.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
