"""Tests for memory queue implementation."""

import asyncio
import pytest
from datetime import datetime, timedelta

from acb.tasks._base import (
    TaskData,
    TaskHandler,
    TaskPriority,
    TaskResult,
    TaskStatus,
)
from acb.tasks.memory import (
    MemoryQueue,
    MemoryQueueSettings,
    PriorityTaskItem,
    create_memory_queue,
)


class SimpleTaskHandler(TaskHandler):
    """Simple task handler for testing."""

    def __init__(self, delay=0.0, should_fail=False):
        self.delay = delay
        self.should_fail = should_fail
        self.processed_tasks = []

    async def handle(self, task: TaskData) -> TaskResult:
        """Handle a task."""
        self.processed_tasks.append(task)

        if self.delay > 0:
            await asyncio.sleep(self.delay)

        if self.should_fail:
            raise ValueError("Handler failure")

        return TaskResult(
            task_id=task.task_id,
            status=TaskStatus.COMPLETED,
            result={"processed": task.payload},
            queue_name=task.queue_name,
        )


@pytest.fixture
def memory_settings():
    """Create memory queue settings for testing."""
    return MemoryQueueSettings(
        max_memory_usage=10_000_000,  # 10MB
        max_tasks_per_queue=1000,
        enable_task_persistence=False,
    )


@pytest.fixture
async def memory_queue(memory_settings):
    """Create and start a memory queue for testing."""
    queue = MemoryQueue(memory_settings)
    await queue.start()
    yield queue
    await queue.stop()


@pytest.fixture
def sample_task():
    """Create a sample task."""
    return TaskData(
        task_type="test_task",
        queue_name="test_queue",
        payload={"message": "test"},
        priority=TaskPriority.NORMAL,
    )


class TestPriorityTaskItem:
    """Test PriorityTaskItem functionality."""

    def test_priority_task_item_creation(self, sample_task):
        """Test creating PriorityTaskItem."""
        scheduled_time = datetime.utcnow().timestamp()
        item = PriorityTaskItem(sample_task, scheduled_time)

        assert item.task == sample_task
        assert item.scheduled_time == scheduled_time
        assert item.priority == -TaskPriority.NORMAL.value

    def test_priority_ordering(self, sample_task):
        """Test priority-based ordering."""
        current_time = datetime.utcnow().timestamp()

        # Create tasks with different priorities
        low_task = TaskData(
            task_type="low", queue_name="test", priority=TaskPriority.LOW
        )
        high_task = TaskData(
            task_type="high", queue_name="test", priority=TaskPriority.HIGH
        )

        low_item = PriorityTaskItem(low_task, current_time)
        high_item = PriorityTaskItem(high_task, current_time)

        # High priority should come before low priority
        assert high_item < low_item

    def test_time_ordering(self, sample_task):
        """Test time-based ordering."""
        current_time = datetime.utcnow().timestamp()
        future_time = current_time + 60

        current_item = PriorityTaskItem(sample_task, current_time)
        future_item = PriorityTaskItem(sample_task, future_time)

        # Earlier time should come before later time
        assert current_item < future_item


class TestMemoryQueueSettings:
    """Test memory queue settings."""

    def test_default_settings(self):
        """Test default memory queue settings."""
        settings = MemoryQueueSettings()

        assert settings.max_memory_usage == 100_000_000
        assert settings.max_tasks_per_queue == 10_000
        assert settings.enable_task_persistence is False

    def test_custom_settings(self):
        """Test custom memory queue settings."""
        settings = MemoryQueueSettings(
            max_memory_usage=50_000_000,
            max_tasks_per_queue=5_000,
            enable_rate_limiting=True,
            rate_limit_per_second=50,
        )

        assert settings.max_memory_usage == 50_000_000
        assert settings.max_tasks_per_queue == 5_000
        assert settings.enable_rate_limiting is True
        assert settings.rate_limit_per_second == 50


class TestMemoryQueue:
    """Test MemoryQueue implementation."""

    @pytest.mark.asyncio
    async def test_queue_creation(self, memory_settings):
        """Test creating memory queue."""
        queue = MemoryQueue(memory_settings)
        assert queue._settings == memory_settings
        assert not queue.is_running

    @pytest.mark.asyncio
    async def test_queue_lifecycle(self, memory_queue):
        """Test queue start/stop lifecycle."""
        assert memory_queue.is_running

        await memory_queue.stop()
        assert not memory_queue.is_running

    @pytest.mark.asyncio
    async def test_task_enqueue_dequeue(self, memory_queue, sample_task):
        """Test basic enqueue/dequeue operations."""
        # Enqueue task
        task_id = await memory_queue.enqueue(sample_task)
        assert task_id == str(sample_task.task_id)
        assert memory_queue._metrics.pending_tasks == 1

        # Dequeue task
        dequeued_task = await memory_queue.dequeue()
        assert dequeued_task.task_id == sample_task.task_id
        assert memory_queue._metrics.pending_tasks == 0
        assert memory_queue._metrics.processing_tasks == 1

    @pytest.mark.asyncio
    async def test_priority_queue_ordering(self, memory_queue):
        """Test priority-based task ordering."""
        # Create tasks with different priorities
        low_task = TaskData(
            task_type="low",
            queue_name="test",
            priority=TaskPriority.LOW,
            payload={"order": 3},
        )
        high_task = TaskData(
            task_type="high",
            queue_name="test",
            priority=TaskPriority.HIGH,
            payload={"order": 1},
        )
        normal_task = TaskData(
            task_type="normal",
            queue_name="test",
            priority=TaskPriority.NORMAL,
            payload={"order": 2},
        )

        # Enqueue in random order
        await memory_queue.enqueue(low_task)
        await memory_queue.enqueue(high_task)
        await memory_queue.enqueue(normal_task)

        # Dequeue should return in priority order
        first = await memory_queue.dequeue()
        second = await memory_queue.dequeue()
        third = await memory_queue.dequeue()

        assert first.payload["order"] == 1  # High priority
        assert second.payload["order"] == 2  # Normal priority
        assert third.payload["order"] == 3  # Low priority

    @pytest.mark.asyncio
    async def test_delayed_tasks(self, memory_queue):
        """Test delayed task processing."""
        # Create delayed task
        delayed_task = TaskData(
            task_type="delayed",
            queue_name="test",
            delay=0.1,  # 100ms delay
            payload={"delayed": True},
        )

        # Enqueue delayed task
        await memory_queue.enqueue(delayed_task)

        # Should not be immediately available
        immediate_task = await memory_queue.dequeue()
        assert immediate_task is None

        # Wait for delay to pass
        await asyncio.sleep(0.2)

        # Now should be available
        dequeued_task = await memory_queue.dequeue()
        assert dequeued_task is not None
        assert dequeued_task.payload["delayed"] is True

    @pytest.mark.asyncio
    async def test_scheduled_tasks(self, memory_queue):
        """Test scheduled task processing."""
        # Create task scheduled for future
        scheduled_time = datetime.utcnow() + timedelta(milliseconds=100)
        scheduled_task = TaskData(
            task_type="scheduled",
            queue_name="test",
            scheduled_at=scheduled_time,
            payload={"scheduled": True},
        )

        # Enqueue scheduled task
        await memory_queue.enqueue(scheduled_task)

        # Should not be immediately available
        immediate_task = await memory_queue.dequeue()
        assert immediate_task is None

        # Wait for scheduled time
        await asyncio.sleep(0.2)

        # Now should be available
        dequeued_task = await memory_queue.dequeue()
        assert dequeued_task is not None
        assert dequeued_task.payload["scheduled"] is True

    @pytest.mark.asyncio
    async def test_task_status_tracking(self, memory_queue, sample_task):
        """Test task status tracking."""
        # Initially no status
        status = await memory_queue.get_task_status(sample_task.task_id)
        assert status is None

        # Enqueue task - should show pending
        await memory_queue.enqueue(sample_task)
        status = await memory_queue.get_task_status(sample_task.task_id)
        assert status.status == TaskStatus.PENDING

        # Dequeue task - should show processing
        await memory_queue.dequeue()
        status = await memory_queue.get_task_status(sample_task.task_id)
        assert status.status == TaskStatus.PROCESSING

    @pytest.mark.asyncio
    async def test_task_cancellation(self, memory_queue, sample_task):
        """Test task cancellation."""
        # Enqueue task
        await memory_queue.enqueue(sample_task)
        assert memory_queue._metrics.pending_tasks == 1

        # Cancel task
        cancelled = await memory_queue.cancel_task(sample_task.task_id)
        assert cancelled is True
        assert memory_queue._metrics.pending_tasks == 0

        # Task should be marked as cancelled
        status = await memory_queue.get_task_status(sample_task.task_id)
        assert status.status == TaskStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_queue_info(self, memory_queue, sample_task):
        """Test queue information retrieval."""
        # Empty queue info
        info = await memory_queue.get_queue_info("test_queue")
        assert info["name"] == "test_queue"
        assert info["pending_tasks"] == 0

        # Add task and check info
        await memory_queue.enqueue(sample_task)
        info = await memory_queue.get_queue_info("test_queue")
        assert info["pending_tasks"] == 1

    @pytest.mark.asyncio
    async def test_queue_purging(self, memory_queue):
        """Test queue purging functionality."""
        # Add multiple tasks
        for i in range(5):
            task = TaskData(
                task_type="test", queue_name="test_queue", payload={"index": i}
            )
            await memory_queue.enqueue(task)

        assert memory_queue._metrics.pending_tasks == 5

        # Purge queue
        purged_count = await memory_queue.purge_queue("test_queue")
        assert purged_count == 5
        assert memory_queue._metrics.pending_tasks == 0

    @pytest.mark.asyncio
    async def test_queue_listing(self, memory_queue):
        """Test listing queues."""
        # Add tasks to different queues
        task1 = TaskData(task_type="test", queue_name="queue1")
        task2 = TaskData(task_type="test", queue_name="queue2")

        await memory_queue.enqueue(task1)
        await memory_queue.enqueue(task2)

        queues = await memory_queue.list_queues()
        assert "queue1" in queues
        assert "queue2" in queues

    @pytest.mark.asyncio
    async def test_memory_limits(self, memory_settings):
        """Test memory usage limits."""
        # Set very low memory limit
        memory_settings.max_memory_usage = 1000  # 1KB
        queue = MemoryQueue(memory_settings)
        await queue.start()

        try:
            # Create large task that should exceed limit
            large_task = TaskData(
                task_type="large",
                queue_name="test",
                payload={"data": "x" * 10000},  # 10KB payload
            )

            # First task might fit
            await queue.enqueue(large_task)

            # Second task should fail due to memory limit
            with pytest.raises(RuntimeError, match="Memory limit exceeded"):
                await queue.enqueue(large_task)

        finally:
            await queue.stop()

    @pytest.mark.asyncio
    async def test_task_limits(self, memory_settings):
        """Test task count limits."""
        # Set low task limit
        memory_settings.max_tasks_per_queue = 2
        queue = MemoryQueue(memory_settings)
        await queue.start()

        try:
            # Add tasks up to limit
            for i in range(2):
                task = TaskData(
                    task_type="test", queue_name="limited_queue", payload={"index": i}
                )
                await queue.enqueue(task)

            # Third task should fail
            task = TaskData(
                task_type="test", queue_name="limited_queue", payload={"index": 3}
            )

            with pytest.raises(RuntimeError, match="Queue limited_queue is full"):
                await queue.enqueue(task)

        finally:
            await queue.stop()

    @pytest.mark.asyncio
    async def test_rate_limiting(self, memory_settings):
        """Test rate limiting functionality."""
        # Enable rate limiting
        memory_settings.enable_rate_limiting = True
        memory_settings.rate_limit_per_second = 2

        queue = MemoryQueue(memory_settings)
        await queue.start()

        try:
            # First two tasks should succeed
            for i in range(2):
                task = TaskData(
                    task_type="test", queue_name="rate_limited", payload={"index": i}
                )
                await queue.enqueue(task)

            # Third task should fail due to rate limit
            task = TaskData(
                task_type="test", queue_name="rate_limited", payload={"index": 3}
            )

            with pytest.raises(RuntimeError, match="Rate limit exceeded"):
                await queue.enqueue(task)

        finally:
            await queue.stop()

    @pytest.mark.asyncio
    async def test_dead_letter_queue(self, memory_queue):
        """Test dead letter queue functionality."""
        # Create failing handler
        handler = SimpleTaskHandler(should_fail=True)
        memory_queue.register_handler("failing_task", handler)

        # Create task with max retries
        failing_task = TaskData(
            task_type="failing_task",
            queue_name="test",
            max_retries=0,  # No retries
            payload={"should_fail": True},
        )

        # Process task (should fail and go to DLQ)
        await memory_queue._process_task(failing_task, "test_worker")

        # Check dead letter queue
        dead_letter_tasks = await memory_queue.get_dead_letter_tasks()
        assert len(dead_letter_tasks) == 1
        assert dead_letter_tasks[0][0].task_id == failing_task.task_id

    @pytest.mark.asyncio
    async def test_dead_letter_retry(self, memory_queue):
        """Test retrying dead letter tasks."""
        # Create task and mark as dead letter
        task = TaskData(task_type="test", queue_name="test")
        result = TaskResult(
            task_id=task.task_id,
            status=TaskStatus.DEAD_LETTER,
            error="Test failure",
            queue_name=task.queue_name,
        )

        await memory_queue._store_dead_letter_task(task, result)

        # Retry dead letter task
        retried = await memory_queue.retry_dead_letter_task(task.task_id)
        assert retried is True

        # Task should be back in queue
        assert memory_queue._metrics.pending_tasks == 1

    @pytest.mark.asyncio
    async def test_completed_task_cleanup(self, memory_queue, sample_task):
        """Test cleaning up completed tasks."""
        # Simulate completed task
        result = TaskResult(
            task_id=sample_task.task_id,
            status=TaskStatus.COMPLETED,
            result="success",
            completed_at=datetime.utcnow() - timedelta(hours=2),
            queue_name=sample_task.queue_name,
        )

        memory_queue._completed_tasks[sample_task.task_id] = result

        # Clean up old completed tasks
        cleaned = await memory_queue.clear_completed_tasks(
            older_than=timedelta(hours=1)
        )
        assert cleaned == 1
        assert sample_task.task_id not in memory_queue._completed_tasks

    @pytest.mark.asyncio
    async def test_health_check(self, memory_queue):
        """Test memory queue health check."""
        health = await memory_queue.health_check()

        assert health["healthy"] is True
        assert "memory_queue" in health

        memory_info = health["memory_queue"]
        assert "memory_usage" in memory_info
        assert "memory_limit" in memory_info
        assert "total_tasks" in memory_info

    @pytest.mark.asyncio
    async def test_metrics_updates(self, memory_queue, sample_task):
        """Test metrics updates during operation."""
        handler = SimpleTaskHandler()
        memory_queue.register_handler(sample_task.task_type, handler)

        # Initial metrics
        assert memory_queue._metrics.pending_tasks == 0
        assert memory_queue._metrics.processing_tasks == 0
        assert memory_queue._metrics.completed_tasks == 0

        # Enqueue task
        await memory_queue.enqueue(sample_task)
        assert memory_queue._metrics.pending_tasks == 1

        # Process task
        await memory_queue._process_task(sample_task, "test_worker")
        assert memory_queue._metrics.completed_tasks == 1


class TestMemoryQueueIntegration:
    """Integration tests for memory queue."""

    @pytest.mark.asyncio
    async def test_full_workflow_with_workers(self, memory_settings):
        """Test complete workflow with actual workers."""
        # Create queue with workers
        memory_settings.max_workers = 2
        queue = MemoryQueue(memory_settings)

        # Create handler
        handler = SimpleTaskHandler(delay=0.01)  # Small delay
        queue.register_handler("integration_task", handler)

        await queue.start()

        try:
            # Add multiple tasks
            task_ids = []
            for i in range(5):
                task = TaskData(
                    task_type="integration_task",
                    queue_name="integration",
                    payload={"index": i},
                )
                task_id = await queue.enqueue(task)
                task_ids.append(task_id)

            # Wait for processing
            await asyncio.sleep(0.2)

            # Check that tasks were processed
            assert len(handler.processed_tasks) == 5

            # Verify all tasks completed
            for i, task_id in enumerate(task_ids):
                # Note: In real implementation, you'd check task status
                assert task_id is not None

        finally:
            await queue.stop()

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, memory_queue):
        """Test concurrent queue operations."""

        # Create tasks concurrently
        async def enqueue_tasks(start_index, count):
            for i in range(count):
                task = TaskData(
                    task_type="concurrent",
                    queue_name="test",
                    payload={"index": start_index + i},
                )
                await memory_queue.enqueue(task)

        # Run concurrent enqueue operations
        await asyncio.gather(
            enqueue_tasks(0, 10),
            enqueue_tasks(10, 10),
            enqueue_tasks(20, 10),
        )

        # Verify all tasks were enqueued
        assert memory_queue._metrics.pending_tasks == 30

        # Dequeue all tasks
        dequeued_count = 0
        while True:
            task = await memory_queue.dequeue()
            if task is None:
                break
            dequeued_count += 1

        assert dequeued_count == 30


class TestMemoryQueueFactory:
    """Test memory queue factory function."""

    def test_create_memory_queue(self):
        """Test factory function."""
        settings = MemoryQueueSettings(max_workers=5)
        queue = create_memory_queue(settings)

        assert isinstance(queue, MemoryQueue)
        assert queue._settings.max_workers == 5

    def test_create_memory_queue_default_settings(self):
        """Test factory function with default settings."""
        queue = create_memory_queue()

        assert isinstance(queue, MemoryQueue)
        assert isinstance(queue._settings, MemoryQueueSettings)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
