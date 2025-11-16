"""Memory-based queue implementation for ACB framework.

This module provides an in-memory task queue implementation suitable for
development, testing, and single-node deployments. Tasks are stored in
memory and will be lost on application restart.
"""

import heapq
import logging
import time
from collections import defaultdict, deque
from uuid import UUID

import asyncio
import contextlib
from datetime import UTC, datetime, timedelta
from typing import Any

from ._base import (
    QueueBase,
    QueueCapability,
    QueueMetadata,
    QueueSettings,
    TaskData,
    TaskResult,
    TaskStatus,
    generate_queue_id,
)

logger = logging.getLogger(__name__)


# Module metadata
MODULE_METADATA = QueueMetadata(
    queue_id=generate_queue_id(),
    name="Memory Queue",
    description="In-memory task queue for development and testing",
    version="1.0.0",
    capabilities=[
        QueueCapability.BASIC_QUEUE,
        QueueCapability.PRIORITY_QUEUE,
        QueueCapability.DELAYED_TASKS,
        QueueCapability.RETRY_MECHANISMS,
        QueueCapability.DEAD_LETTER_QUEUE,
        QueueCapability.BATCH_PROCESSING,
        QueueCapability.METRICS_COLLECTION,
        QueueCapability.HEALTH_MONITORING,
        QueueCapability.TASK_TRACKING,
        QueueCapability.WORKER_POOLS,
        QueueCapability.RATE_LIMITING,
    ],
    max_throughput=1000,  # tasks per second
    max_workers=50,
    supports_clustering=False,
    required_packages=[],
    min_python_version="3.13",
    config_schema={
        "max_memory_usage": {"type": "integer", "default": 100_000_000},  # 100MB
        "max_tasks_per_queue": {"type": "integer", "default": 10_000},
        "enable_task_persistence": {"type": "boolean", "default": False},
    },
    default_settings={
        "max_memory_usage": 100_000_000,
        "max_tasks_per_queue": 10_000,
        "enable_task_persistence": False,
    },
)


class MemoryQueueSettings(QueueSettings):
    """Settings for memory queue implementation."""

    # Memory limits
    max_memory_usage: int = 100_000_000  # 100MB
    max_tasks_per_queue: int = 10_000

    # Task storage
    enable_task_persistence: bool = False
    persistence_file: str | None = None

    # Rate limiting
    enable_rate_limiting: bool = False
    rate_limit_per_second: int = 100


class PriorityTaskItem:
    """Priority queue item wrapper for tasks."""

    def __init__(self, task: TaskData, scheduled_time: float) -> None:
        self.task = task
        self.scheduled_time = scheduled_time
        # Higher priority values have lower sort order
        self.priority = -task.priority.value
        self.created_at = time.time()

    def __lt__(self, other: "PriorityTaskItem") -> bool:
        """Compare items for priority queue ordering."""
        # First by scheduled time
        if self.scheduled_time != other.scheduled_time:
            return self.scheduled_time < other.scheduled_time
        # Then by priority (higher priority first)
        if self.priority != other.priority:
            return self.priority < other.priority
        # Finally by creation time (FIFO for same priority)
        return self.created_at < other.created_at

    def __eq__(self, other: object) -> bool:
        """Check equality."""
        return (
            self.task.task_id == other.task.task_id
            if isinstance(other, PriorityTaskItem)
            else False
        )


class MemoryQueue(QueueBase):
    """Memory-based task queue implementation."""

    def __init__(self, settings: MemoryQueueSettings | None = None) -> None:
        super().__init__(settings)
        self._settings = settings or MemoryQueueSettings()

        # Task storage
        self._queues: dict[str, list[PriorityTaskItem]] = defaultdict(list)
        self._processing_tasks: dict[UUID, TaskData] = {}
        self._completed_tasks: dict[UUID, TaskResult] = {}
        self._dead_letter_tasks: dict[UUID, tuple[TaskData, TaskResult]] = {}

        # Delayed tasks
        self._delayed_tasks: list[PriorityTaskItem] = []

        # Rate limiting
        self._rate_limiter: dict[str, deque[float]] = defaultdict(deque)

        # Memory tracking
        self._memory_usage = 0
        self._task_count = 0

        # Background tasks
        self._delayed_task_processor: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the memory queue."""
        await super().start()

        # Start delayed task processor
        self._delayed_task_processor = asyncio.create_task(
            self._process_delayed_tasks(),
        )

        self.logger.info("Memory queue started")

    async def stop(self) -> None:
        """Stop the memory queue."""
        # Stop delayed task processor
        if self._delayed_task_processor:
            self._delayed_task_processor.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._delayed_task_processor

        await super().stop()
        self.logger.info("Memory queue stopped")

    async def enqueue(self, task: TaskData) -> str:
        """Enqueue a task for processing."""
        if not self._running:
            msg = "Queue is not running"
            raise RuntimeError(msg)

        # Check memory limits
        if self._memory_usage > self._settings.max_memory_usage:
            msg = "Memory limit exceeded"
            raise RuntimeError(msg)

        # Check task count limits
        if len(self._queues[task.queue_name]) >= self._settings.max_tasks_per_queue:
            msg = f"Queue {task.queue_name} is full"
            raise RuntimeError(msg)

        # Check rate limiting
        if self._settings.enable_rate_limiting:
            if not await self._check_rate_limit(task.queue_name):
                msg = f"Rate limit exceeded for queue {task.queue_name}"
                raise RuntimeError(msg)

        # Calculate scheduled time
        if task.delay > 0:
            scheduled_time = time.time() + task.delay
        elif task.scheduled_at:
            scheduled_time = task.scheduled_at.timestamp()
        else:
            # Immediate tasks use priority-based ordering (set to 0 to ensure priority ordering)
            scheduled_time = 0.0

        # Create priority item
        item = PriorityTaskItem(task, scheduled_time)

        # Add to appropriate queue
        if scheduled_time > time.time():
            # Delayed task
            heapq.heappush(self._delayed_tasks, item)
        else:
            # Immediate task
            heapq.heappush(self._queues[task.queue_name], item)

        # Update metrics
        self._task_count += 1
        self._memory_usage += self._estimate_task_size(task)
        self._metrics.pending_tasks += 1

        self.logger.debug(f"Enqueued task {task.task_id} to queue {task.queue_name}")
        return str(task.task_id)

    async def dequeue(self, queue_name: str | None = None) -> TaskData | None:
        """Dequeue a task for processing."""
        if not self._running:
            return None

        # Determine which queues to check
        queue_names = [queue_name] if queue_name else list(self._queues.keys())
        if not queue_names:
            queue_names = ["default"]

        # Try to get task from queues (round-robin)
        for name in queue_names:
            queue = self._queues[name]
            if queue:
                # Get highest priority task
                item = heapq.heappop(queue)
                task = item.task

                # Move to processing
                self._processing_tasks[task.task_id] = task

                # Update metrics
                self._metrics.pending_tasks = max(0, self._metrics.pending_tasks - 1)
                self._metrics.processing_tasks += 1

                self.logger.debug(f"Dequeued task {task.task_id} from queue {name}")
                return task

        return None

    async def get_task_status(self, task_id: UUID) -> TaskResult | None:
        """Get task status and result."""
        # Check completed tasks
        if task_id in self._completed_tasks:
            return self._completed_tasks[task_id]

        # Check processing tasks
        if task_id in self._processing_tasks:
            return TaskResult(
                task_id=task_id,
                status=TaskStatus.PROCESSING,
                queue_name=self._processing_tasks[task_id].queue_name,
            )

        # Check dead letter tasks
        if task_id in self._dead_letter_tasks:
            _, result = self._dead_letter_tasks[task_id]
            return result

        # Check pending tasks
        for queue in self._queues.values():
            for item in queue:
                if item.task.task_id == task_id:
                    return TaskResult(
                        task_id=task_id,
                        status=TaskStatus.PENDING,
                        queue_name=item.task.queue_name,
                    )

        # Check delayed tasks
        for item in self._delayed_tasks:
            if item.task.task_id == task_id:
                return TaskResult(
                    task_id=task_id,
                    status=TaskStatus.PENDING,
                    queue_name=item.task.queue_name,
                    next_retry_at=datetime.fromtimestamp(item.scheduled_time),
                )

        return None

    async def cancel_task(self, task_id: UUID) -> bool:
        """Cancel a pending task."""
        # Remove from pending queues
        for queue_name, queue in self._queues.items():
            for i, item in enumerate(queue):
                if item.task.task_id == task_id:
                    queue.pop(i)
                    heapq.heapify(queue)

                    # Update metrics
                    self._metrics.pending_tasks = max(
                        0,
                        self._metrics.pending_tasks - 1,
                    )
                    self._task_count = max(0, self._task_count - 1)
                    self._memory_usage = max(
                        0,
                        self._memory_usage - self._estimate_task_size(item.task),
                    )

                    # Add cancelled result
                    self._completed_tasks[task_id] = TaskResult(
                        task_id=task_id,
                        status=TaskStatus.CANCELLED,
                        queue_name=queue_name,
                        completed_at=datetime.now(tz=UTC),
                    )

                    self.logger.debug(f"Cancelled task {task_id}")
                    return True

        # Remove from delayed tasks
        for i, item in enumerate(self._delayed_tasks):
            if item.task.task_id == task_id:
                self._delayed_tasks.pop(i)
                heapq.heapify(self._delayed_tasks)

                # Update metrics
                self._task_count = max(0, self._task_count - 1)
                self._memory_usage = max(
                    0,
                    self._memory_usage - self._estimate_task_size(item.task),
                )

                # Add cancelled result
                self._completed_tasks[task_id] = TaskResult(
                    task_id=task_id,
                    status=TaskStatus.CANCELLED,
                    queue_name=item.task.queue_name,
                    completed_at=datetime.now(tz=UTC),
                )

                self.logger.debug(f"Cancelled delayed task {task_id}")
                return True

        return False

    async def get_queue_info(self, queue_name: str) -> dict[str, Any]:
        """Get information about a queue."""
        queue = self._queues[queue_name]

        # Count tasks by priority
        priority_counts: defaultdict[str, int] = defaultdict(int)
        for item in queue:
            priority_counts[item.task.priority.name] += 1

        return {
            "name": queue_name,
            "pending_tasks": len(queue),
            "priority_distribution": dict(priority_counts),
            "oldest_task": min((item.created_at for item in queue), default=None),
            "newest_task": max((item.created_at for item in queue), default=None),
        }

    async def purge_queue(self, queue_name: str) -> int:
        """Remove all tasks from a queue."""
        queue = self._queues[queue_name]
        task_count = len(queue)

        if task_count > 0:
            # Update memory usage
            for item in queue:
                self._memory_usage = max(
                    0,
                    self._memory_usage - self._estimate_task_size(item.task),
                )

            # Clear queue
            queue.clear()

            # Update metrics
            self._metrics.pending_tasks = max(
                0,
                self._metrics.pending_tasks - task_count,
            )
            self._task_count = max(0, self._task_count - task_count)

            self.logger.info(f"Purged {task_count} tasks from queue {queue_name}")

        return task_count

    async def list_queues(self) -> list[str]:
        """List all available queues."""
        return list(self._queues.keys())

    async def _store_dead_letter_task(self, task: TaskData, result: TaskResult) -> None:
        """Store task in dead letter queue."""
        self._dead_letter_tasks[task.task_id] = (task, result)
        self._metrics.dead_letter_tasks += 1

        # Remove from processing
        if task.task_id in self._processing_tasks:
            del self._processing_tasks[task.task_id]
            self._metrics.processing_tasks = max(0, self._metrics.processing_tasks - 1)

        # Optionally clean up old dead letter tasks
        await self._cleanup_dead_letter_tasks()

    def _move_ready_delayed_tasks(self, current_time: float) -> int:
        """Move delayed tasks that are ready to main queues. Returns count moved."""
        moved_count = 0

        while self._delayed_tasks:
            if self._delayed_tasks[0].scheduled_time <= current_time:
                item = heapq.heappop(self._delayed_tasks)
                heapq.heappush(self._queues[item.task.queue_name], item)
                moved_count += 1
            else:
                break

        if moved_count > 0:
            self.logger.debug(f"Moved {moved_count} delayed tasks to main queues")

        return moved_count

    def _calculate_next_sleep_time(self, current_time: float) -> float:
        """Calculate sleep time until next delayed task is ready."""
        if not self._delayed_tasks:
            return 1.0

        next_task_time = self._delayed_tasks[0].scheduled_time
        return min(1.0, max(0.1, next_task_time - current_time))

    async def _process_delayed_tasks(self) -> None:
        """Process delayed tasks in background."""
        while self._running and not self._shutdown_event.is_set():
            try:
                current_time = time.time()

                # Move ready tasks to main queues
                self._move_ready_delayed_tasks(current_time)

                # Sleep until next task is ready
                sleep_time = self._calculate_next_sleep_time(current_time)
                await asyncio.sleep(sleep_time)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.exception(f"Delayed task processor error: {e}")
                await asyncio.sleep(1.0)

    async def _check_rate_limit(self, queue_name: str) -> bool:
        """Check if queue is within rate limits."""
        if not self._settings.enable_rate_limiting:
            return True

        current_time = time.time()
        window_start = current_time - 1.0  # 1 second window

        # Clean old timestamps
        rate_queue = self._rate_limiter[queue_name]
        while rate_queue and rate_queue[0] < window_start:
            rate_queue.popleft()

        # Check if under limit
        if len(rate_queue) < self._settings.rate_limit_per_second:
            rate_queue.append(current_time)
            return True

        return False

    async def _cleanup_dead_letter_tasks(self) -> None:
        """Clean up old dead letter tasks."""
        if not self._settings.enable_dead_letter:
            return

        current_time = datetime.now(tz=UTC)
        ttl = timedelta(seconds=self._settings.dead_letter_ttl)

        # Find expired tasks
        expired_ids = [
            task_id
            for task_id, (_task, result) in self._dead_letter_tasks.items()
            if result.completed_at and (current_time - result.completed_at) > ttl
        ]

        # Remove expired tasks
        for task_id in expired_ids:
            del self._dead_letter_tasks[task_id]
            self._metrics.dead_letter_tasks = max(
                0,
                self._metrics.dead_letter_tasks - 1,
            )

    async def _on_task_completed(self, task: TaskData, result: TaskResult) -> None:
        """Handle task completion."""
        await super()._on_task_completed(task, result)

        # Store result
        self._completed_tasks[task.task_id] = result

        # Remove from processing
        if task.task_id in self._processing_tasks:
            del self._processing_tasks[task.task_id]
            self._metrics.processing_tasks = max(0, self._metrics.processing_tasks - 1)

        # Update memory usage
        self._memory_usage = max(0, self._memory_usage - self._estimate_task_size(task))

    async def _on_task_failed(self, task: TaskData, result: TaskResult) -> None:
        """Handle task failure."""
        await super()._on_task_failed(task, result)

        # Remove from processing
        if task.task_id in self._processing_tasks:
            del self._processing_tasks[task.task_id]
            self._metrics.processing_tasks = max(0, self._metrics.processing_tasks - 1)

    async def _update_metrics(self) -> None:
        """Update queue metrics."""
        await super()._update_metrics()

        # Update queue depth
        total_pending = sum(len(queue) for queue in self._queues.values())
        total_pending += len(self._delayed_tasks)
        self._metrics.queue_depth = total_pending

        # Update worker metrics
        self._metrics.worker_metrics.last_activity = datetime.now(tz=UTC)

        # Calculate throughput
        if self._metrics.last_task_processed:
            time_since_last = (
                datetime.now(tz=UTC) - self._metrics.last_task_processed
            ).total_seconds()
            if time_since_last > 0:
                recent_tasks = self._metrics.worker_metrics.tasks_processed
                self._metrics.throughput = recent_tasks / max(1, time_since_last)

    def _estimate_task_size(self, task: TaskData) -> int:
        """Estimate memory usage of a task."""
        # Simple estimation based on payload size
        import sys

        try:
            return (
                sys.getsizeof(task.payload) + sys.getsizeof(task.task_type) + 1000
            )  # Base overhead
        except Exception:
            return 1000  # Default size if calculation fails

    async def health_check(self) -> dict[str, Any]:
        """Perform health check."""
        base_health = await super().health_check()

        # Add memory queue specific metrics
        memory_health = {
            "memory_usage": self._memory_usage,
            "memory_limit": self._settings.max_memory_usage,
            "memory_usage_percent": (
                self._memory_usage / self._settings.max_memory_usage
            )
            * 100,
            "total_tasks": self._task_count,
            "delayed_tasks": len(self._delayed_tasks),
            "dead_letter_tasks": len(self._dead_letter_tasks),
            "completed_tasks": len(self._completed_tasks),
            "queue_count": len(self._queues),
        }

        base_health["memory_queue"] = memory_health

        # Check health status
        if self._memory_usage > self._settings.max_memory_usage * 0.9:
            base_health["healthy"] = False
            base_health["warnings"] = base_health.get("warnings", [])
            base_health["warnings"].append("High memory usage")

        return base_health

    # Additional memory queue specific methods
    async def get_delayed_tasks(self) -> list[TaskData]:
        """Get list of delayed tasks."""
        return [item.task for item in self._delayed_tasks]

    async def get_dead_letter_tasks(self) -> list[tuple[TaskData, TaskResult]]:
        """Get list of dead letter tasks."""
        return list(self._dead_letter_tasks.values())

    async def retry_dead_letter_task(self, task_id: UUID) -> bool:
        """Retry a dead letter task."""
        if task_id not in self._dead_letter_tasks:
            return False

        task, _ = self._dead_letter_tasks[task_id]
        del self._dead_letter_tasks[task_id]
        self._metrics.dead_letter_tasks = max(0, self._metrics.dead_letter_tasks - 1)

        # Reset task and re-enqueue
        retry_task = task.copy()
        retry_task.task_id = task_id  # Keep same ID
        await self.enqueue(retry_task)

        self.logger.info(f"Retrying dead letter task {task_id}")
        return True

    async def clear_completed_tasks(self, older_than: timedelta | None = None) -> int:
        """Clear completed task results."""
        if older_than is None:
            count = len(self._completed_tasks)
            self._completed_tasks.clear()
            return count

        current_time = datetime.now(tz=UTC)
        expired_ids = [
            task_id
            for task_id, result in self._completed_tasks.items()
            if result.completed_at and (current_time - result.completed_at) > older_than
        ]

        for task_id in expired_ids:
            del self._completed_tasks[task_id]

        return len(expired_ids)


# Factory function
def create_memory_queue(settings: MemoryQueueSettings | None = None) -> MemoryQueue:
    """Create a memory queue instance.

    Args:
        settings: Queue settings

    Returns:
        MemoryQueue instance
    """
    return MemoryQueue(settings)
