"""Base queue system for ACB framework.

This module provides the foundation for ACB's task queue system with
persistent job processing, worker management, and multiple backend support.
Designed to complement the Events System with reliable background processing.
"""

import logging
import time
from abc import ABC, abstractmethod
from enum import Enum
from uuid import UUID, uuid4

import asyncio
import typing as t
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pydantic import BaseModel, Field, field_validator
from typing import Any

from acb.cleanup import CleanupMixin
from acb.config import Config, Settings
from acb.depends import Inject, depends

if t.TYPE_CHECKING:
    from acb.logger import Logger as LoggerType
else:
    LoggerType = object

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task execution status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD_LETTER = "dead_letter"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    """Task priority levels."""

    LOW = 1
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20


class QueueCapability(Enum):
    """Queue backend capabilities."""

    # Basic operations
    BASIC_QUEUE = "basic_queue"
    PRIORITY_QUEUE = "priority_queue"
    DELAYED_TASKS = "delayed_tasks"

    # Advanced features
    RETRY_MECHANISMS = "retry_mechanisms"
    DEAD_LETTER_QUEUE = "dead_letter_queue"
    BATCH_PROCESSING = "batch_processing"
    PERSISTENCE = "persistence"

    # Monitoring and observability
    METRICS_COLLECTION = "metrics_collection"
    HEALTH_MONITORING = "health_monitoring"
    TASK_TRACKING = "task_tracking"

    # Scalability
    WORKER_POOLS = "worker_pools"
    HORIZONTAL_SCALING = "horizontal_scaling"
    LOAD_BALANCING = "load_balancing"

    # Advanced scheduling
    CRON_SCHEDULING = "cron_scheduling"
    RATE_LIMITING = "rate_limiting"
    CIRCUIT_BREAKER = "circuit_breaker"


@dataclass
class QueueMetadata:
    """Metadata for queue backends."""

    queue_id: UUID = field(default_factory=uuid4)
    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    capabilities: list[QueueCapability] = field(default_factory=list)

    # Performance characteristics
    max_throughput: int | None = None  # tasks per second
    max_workers: int | None = None
    supports_clustering: bool = False

    # Dependencies
    required_packages: list[str] = field(default_factory=list)
    min_python_version: str = "3.13"

    # Configuration
    config_schema: dict[str, t.Any] = field(default_factory=dict)
    default_settings: dict[str, t.Any] = field(default_factory=dict)


class TaskData(BaseModel):
    """Task data structure."""

    task_id: UUID = Field(default_factory=uuid4)
    queue_name: str = Field(description="Target queue name")
    task_type: str = Field(description="Task type identifier")
    payload: dict[str, t.Any] = Field(default_factory=dict, description="Task payload")

    # Scheduling
    priority: TaskPriority = TaskPriority.NORMAL
    delay: float = 0.0  # Delay in seconds
    scheduled_at: datetime | None = None

    # Execution control
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: float = 300.0  # 5 minutes default

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    tags: dict[str, str] = Field(default_factory=dict)

    @field_validator("scheduled_at", mode="before")
    @classmethod
    def parse_scheduled_at(cls, v: t.Any) -> datetime | t.Any:
        if isinstance(v, str):
            return datetime.fromisoformat(v)
        return v


class TaskResult(BaseModel):
    """Task execution result."""

    task_id: UUID
    status: TaskStatus
    result: t.Any = None
    error: str | None = None

    # Timing information
    started_at: datetime | None = None
    completed_at: datetime | None = None
    execution_time: float | None = None  # seconds

    # Retry information
    retry_count: int = 0
    next_retry_at: datetime | None = None

    # Worker information
    worker_id: str | None = None
    queue_name: str | None = None


@dataclass
class WorkerMetrics:
    """Worker pool metrics."""

    active_workers: int = 0
    idle_workers: int = 0
    total_workers: int = 0

    tasks_processed: int = 0
    tasks_failed: int = 0
    avg_execution_time: float = 0.0

    last_activity: datetime | None = None
    uptime: float = 0.0  # seconds


@dataclass
class QueueMetrics:
    """Queue performance metrics."""

    # Queue state
    pending_tasks: int = 0
    processing_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    dead_letter_tasks: int = 0

    # Performance
    throughput: float = 0.0  # tasks per second
    avg_processing_time: float = 0.0
    queue_depth: int = 0

    # Workers
    worker_metrics: WorkerMetrics = field(default_factory=WorkerMetrics)

    # Health
    last_task_processed: datetime | None = None
    error_rate: float = 0.0
    is_healthy: bool = True


class TaskHandler(ABC):
    """Abstract base class for task handlers."""

    @abstractmethod
    async def handle(self, task: TaskData) -> TaskResult:
        """Handle a task and return the result.

        Args:
            task: Task to process

        Returns:
            TaskResult with execution status and result
        """
        ...

    async def on_failure(self, task: TaskData, error: Exception) -> bool:
        """Handle task failure.

        Args:
            task: Failed task
            error: Exception that caused failure

        Returns:
            True if task should be retried, False otherwise
        """
        return True

    async def on_success(self, task: TaskData, result: TaskResult) -> None:
        """Handle successful task completion.

        Args:
            task: Completed task
            result: Task result
        """


class FunctionalTaskHandler(TaskHandler):
    """Task handler that wraps a function."""

    def __init__(
        self,
        handler_func: t.Callable[[TaskData], t.Awaitable[t.Any]],
        on_failure_func: t.Callable[[TaskData, Exception], t.Awaitable[bool]]
        | None = None,
        on_success_func: t.Callable[[TaskData, TaskResult], t.Awaitable[None]]
        | None = None,
    ) -> None:
        self._handler_func = handler_func
        self._on_failure_func = on_failure_func
        self._on_success_func = on_success_func
        self.task_type: str = ""  # Will be set by decorator

    async def handle(self, task: TaskData) -> TaskResult:
        """Handle task using the wrapped function."""
        start_time = time.time()

        try:
            result = await self._handler_func(task)

            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.COMPLETED,
                result=result,
                started_at=datetime.now(tz=UTC),
                completed_at=datetime.now(tz=UTC),
                execution_time=time.time() - start_time,
                queue_name=task.queue_name,
            )

        except Exception as e:
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                error=str(e),
                started_at=datetime.now(tz=UTC),
                completed_at=datetime.now(tz=UTC),
                execution_time=time.time() - start_time,
                queue_name=task.queue_name,
            )

    async def on_failure(self, task: TaskData, error: Exception) -> bool:
        """Handle failure using wrapped function if provided."""
        if self._on_failure_func:
            return await self._on_failure_func(task, error)
        return await super().on_failure(task, error)

    async def on_success(self, task: TaskData, result: TaskResult) -> None:
        """Handle success using wrapped function if provided."""
        if self._on_success_func:
            await self._on_success_func(task, result)
        else:
            await super().on_success(task, result)


def task_handler(
    task_type: str,
    on_failure: t.Callable[[TaskData, Exception], t.Awaitable[bool]] | None = None,
    on_success: t.Callable[[TaskData, TaskResult], t.Awaitable[None]] | None = None,
) -> t.Callable[[t.Callable[..., Any]], FunctionalTaskHandler]:
    """Decorator to create a task handler from a function.

    Args:
        task_type: Task type identifier
        on_failure: Optional failure handler
        on_success: Optional success handler

    Returns:
        Decorator function
    """

    def decorator(
        func: t.Callable[[TaskData], t.Awaitable[t.Any]],
    ) -> FunctionalTaskHandler:
        handler = FunctionalTaskHandler(func, on_failure, on_success)
        handler.task_type = task_type
        return handler

    return decorator


class QueueSettings(Settings):
    """Base settings for queue implementations."""

    enabled: bool = True

    # Worker configuration
    max_workers: int = 10
    min_workers: int = 1
    worker_timeout: float = 300.0

    # Task configuration
    default_task_timeout: float = 300.0
    max_retries: int = 3
    retry_delay: float = 1.0
    retry_exponential_base: float = 2.0

    # Dead letter queue
    enable_dead_letter: bool = True
    dead_letter_ttl: int = 7 * 24 * 3600  # 7 days

    # Performance
    batch_size: int = 10
    prefetch_count: int = 20

    # Health monitoring
    health_check_enabled: bool = True
    health_check_interval: float = 60.0

    # Metrics
    enable_metrics: bool = True
    metrics_interval: float = 30.0

    # Redis-specific attributes (will be overridden in subclasses)
    redis_url: str = "redis://localhost:6379/0"
    max_connections: int = 20
    socket_connect_timeout: float = 5.0
    socket_timeout: float = 5.0
    retry_on_timeout: bool = True
    use_lua_scripts: bool = True

    # RabbitMQ-specific attributes (will be overridden in subclasses)
    amqp_url: str = "amqp://guest:guest@localhost:5672/"
    connection_timeout: float = 10.0
    heartbeat: int = 600
    channel_max: int = 2048
    frame_max: int = 131072
    exchange_name: str = "acb.queues"
    exchange_type: str = "topic"
    exchange_durable: bool = True
    dead_letter_exchange: str = "acb.queues.dlx"

    # Memory-specific attributes (will be overridden in subclasses)
    max_memory_usage: int = 100_000_000  # 100MB
    max_tasks_per_queue: int = 10_000
    enable_rate_limiting: bool = False
    rate_limit_per_second: int = 100

    # Provider configuration
    queue_provider: str = "memory"
    queue_settings: dict[str, t.Any] = Field(default_factory=dict)

    @depends.inject
    def __init__(self, config: Inject[Config], **values: t.Any) -> None:
        super().__init__(**values)


class QueueBase(CleanupMixin):
    """Abstract base class for queue implementations."""

    def __init__(self, settings: QueueSettings | None = None) -> None:
        super().__init__()
        CleanupMixin.__init__(self)

        # Initialize injected dependencies with fallback for tests
        self._config: Config | None = None
        self._logger: logging.Logger | None = None

        self._settings = settings or QueueSettings()
        self._handlers: dict[str, TaskHandler] = {}
        self._workers: dict[str, asyncio.Task[None]] = {}
        self._metrics = QueueMetrics()
        self._shutdown_event = asyncio.Event()
        self._running = False

    @property
    def config(self) -> Config:
        """Get config with lazy initialization."""
        if self._config is None:
            try:
                self._config = depends.get_sync(Config)
            except Exception:
                # Fallback - in test context, create a minimal config
                from acb.config import Config as RealConfig

                self._config = RealConfig()
        return self._config

    @config.setter
    def config(self, value: Config) -> None:
        """Set config instance."""
        self._config = value

    @property
    def logger(self) -> logging.Logger:
        """Get logger with lazy initialization."""
        if self._logger is None:
            try:
                imported_logger = depends.get_sync(LoggerType)
                self._logger = imported_logger
            except Exception:
                # Fallback to standard logging
                self._logger = logging.getLogger(self.__class__.__name__)
        return self._logger

    @logger.setter
    def logger(self, value: logging.Logger) -> None:
        """Set logger instance."""
        self._logger = value

    @property
    def settings(self) -> QueueSettings:
        """Get queue settings."""
        return self._settings

    @property
    def metrics(self) -> QueueMetrics:
        """Get queue metrics."""
        return self._metrics

    @property
    def is_running(self) -> bool:
        """Check if queue is running."""
        return self._running

    # Task management methods
    async def enqueue(self, task: TaskData) -> str:
        """Enqueue a task for processing.

        Args:
            task: Task to enqueue

        Returns:
            Task ID
        """
        msg = "enqueue method must be implemented by subclass"
        raise NotImplementedError(msg)

    async def dequeue(self, queue_name: str | None = None) -> TaskData | None:
        """Dequeue a task for processing.

        Args:
            queue_name: Optional queue name to dequeue from

        Returns:
            Task data or None if no tasks available
        """
        msg = "dequeue method must be implemented by subclass"
        raise NotImplementedError(msg)

    async def get_task_status(self, task_id: UUID) -> TaskResult | None:
        """Get task status and result.

        Args:
            task_id: Task identifier

        Returns:
            Task result or None if not found
        """
        msg = "get_task_status method must be implemented by subclass"
        raise NotImplementedError(
            msg,
        )

    async def cancel_task(self, task_id: UUID) -> bool:
        """Cancel a pending task.

        Args:
            task_id: Task identifier

        Returns:
            True if task was cancelled
        """
        msg = "cancel_task method must be implemented by subclass"
        raise NotImplementedError(msg)

    # Queue management methods
    async def get_queue_info(self, queue_name: str) -> dict[str, t.Any]:
        """Get information about a queue.

        Args:
            queue_name: Queue name

        Returns:
            Queue information
        """
        msg = "get_queue_info method must be implemented by subclass"
        raise NotImplementedError(
            msg,
        )

    async def purge_queue(self, queue_name: str) -> int:
        """Remove all tasks from a queue.

        Args:
            queue_name: Queue name

        Returns:
            Number of tasks removed
        """
        msg = "purge_queue method must be implemented by subclass"
        raise NotImplementedError(msg)

    async def list_queues(self) -> list[str]:
        """List all available queues.

        Returns:
            List of queue names
        """
        msg = "list_queues method must be implemented by subclass"
        raise NotImplementedError(msg)

    # Worker management methods
    async def start_workers(self, count: int | None = None) -> None:
        """Start worker processes.

        Args:
            count: Number of workers to start (default: max_workers)
        """
        if count is None:
            count = self._settings.max_workers

        for i in range(count):
            worker_id = f"worker-{i}"
            if worker_id not in self._workers:
                self._workers[worker_id] = asyncio.create_task(
                    self._worker_loop(worker_id),
                )

        self._metrics.worker_metrics.total_workers = len(self._workers)
        self.logger.info(f"Started {count} workers")

    async def stop_workers(self) -> None:
        """Stop all worker processes."""
        self._shutdown_event.set()

        # Cancel all worker tasks
        for task in self._workers.values():
            task.cancel()

        # Wait for workers to finish
        if self._workers:
            await asyncio.gather(*self._workers.values(), return_exceptions=True)

        self._workers.clear()
        self._metrics.worker_metrics.total_workers = 0
        self.logger.info("Stopped all workers")

    def _mark_worker_idle(self) -> None:
        """Mark worker as idle in metrics."""
        self._metrics.worker_metrics.idle_workers += 1

    def _mark_worker_active(self) -> None:
        """Mark worker as active in metrics (transitions from idle)."""
        self._metrics.worker_metrics.idle_workers -= 1
        self._metrics.worker_metrics.active_workers += 1

    def _cleanup_worker_metrics(self) -> None:
        """Cleanup worker metrics in finally block."""
        if self._metrics.worker_metrics.active_workers > 0:
            self._metrics.worker_metrics.active_workers -= 1
        if self._metrics.worker_metrics.idle_workers > 0:
            self._metrics.worker_metrics.idle_workers -= 1

    @staticmethod
    async def _handle_empty_queue() -> None:
        """Handle empty queue by waiting before next dequeue."""
        await asyncio.sleep(1.0)

    async def _execute_worker_iteration(self, worker_id: str) -> bool:
        """Execute one worker loop iteration. Returns True if should continue."""
        try:
            self._mark_worker_idle()

            # Dequeue a task
            task = await self.dequeue()
            if task is None:
                await self._handle_empty_queue()
                return True

            # Process the task
            self._mark_worker_active()
            await self._process_task(task, worker_id)
            return True

        except asyncio.CancelledError:
            return False
        except Exception as e:
            self.logger.exception(f"Worker {worker_id} error: {e}")
            await asyncio.sleep(self._settings.retry_delay)
            return True
        finally:
            self._cleanup_worker_metrics()

    async def _worker_loop(self, worker_id: str) -> None:
        """Main worker loop.

        Args:
            worker_id: Unique worker identifier
        """
        self.logger.debug(f"Worker {worker_id} started")

        try:
            while not self._shutdown_event.is_set():
                should_continue = await self._execute_worker_iteration(worker_id)
                if not should_continue:
                    break

        except asyncio.CancelledError:
            pass
        finally:
            self.logger.debug(f"Worker {worker_id} stopped")

    async def _process_task(self, task: TaskData, worker_id: str) -> None:
        """Process a single task.

        Args:
            task: Task to process
            worker_id: ID of processing worker
        """
        start_time = time.time()

        try:
            # Get task handler
            handler = self._handlers.get(task.task_type)
            if handler is None:
                msg = f"No handler registered for task type: {task.task_type}"
                raise ValueError(
                    msg,
                )

            # Execute task with timeout
            try:
                result = await asyncio.wait_for(
                    handler.handle(task),
                    timeout=task.timeout or self._settings.default_task_timeout,
                )
                result.worker_id = worker_id

                # Handle successful completion
                await handler.on_success(task, result)
                await self._on_task_completed(task, result)

            except TimeoutError:
                msg = f"Task timed out after {task.timeout}s"
                raise Exception(msg)

        except Exception as e:
            # Handle task failure
            result = TaskResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                error=str(e),
                started_at=datetime.now(tz=UTC),
                completed_at=datetime.now(tz=UTC),
                execution_time=time.time() - start_time,
                worker_id=worker_id,
                queue_name=task.queue_name,
            )

            handler = self._handlers.get(task.task_type)
            if handler:
                should_retry = await handler.on_failure(task, e)
                if should_retry and result.retry_count < task.max_retries:
                    await self._retry_task(task, result)
                else:
                    await self._move_to_dead_letter(task, result)
            else:
                await self._move_to_dead_letter(task, result)

            await self._on_task_failed(task, result)

    async def _retry_task(self, task: TaskData, result: TaskResult) -> None:
        """Retry a failed task.

        Args:
            task: Original task
            result: Failure result
        """
        retry_count = result.retry_count + 1
        retry_delay = task.retry_delay * (
            self._settings.retry_exponential_base**retry_count
        )

        # Create retry task
        retry_task = task.copy()
        retry_task.task_id = uuid4()
        retry_task.delay = retry_delay
        retry_task.tags["retry_count"] = str(retry_count)
        retry_task.tags["original_task_id"] = str(task.task_id)

        await self.enqueue(retry_task)
        self.logger.info(f"Retrying task {task.task_id} (attempt {retry_count})")

    async def _move_to_dead_letter(self, task: TaskData, result: TaskResult) -> None:
        """Move failed task to dead letter queue.

        Args:
            task: Failed task
            result: Failure result
        """
        if self._settings.enable_dead_letter:
            result.status = TaskStatus.DEAD_LETTER
            await self._store_dead_letter_task(task, result)
            self.logger.warning(f"Moved task {task.task_id} to dead letter queue")

    async def _store_dead_letter_task(self, task: TaskData, result: TaskResult) -> None:
        """Store task in dead letter queue.

        Args:
            task: Failed task
            result: Failure result
        """
        # Default implementation - derived classes should override with actual storage logic
        self.logger.warning(
            f"Storing task {task.task_id} in dead letter queue (default implementation)",
        )
        # In a real implementation, this would store the task to a persistent storage
        # for later inspection/reprocessing

    async def _on_task_completed(self, task: TaskData, result: TaskResult) -> None:
        """Handle task completion.

        Args:
            task: Completed task
            result: Task result
        """
        self._metrics.completed_tasks += 1
        self._metrics.worker_metrics.tasks_processed += 1
        self._metrics.last_task_processed = datetime.now(tz=UTC)

        # Update average processing time
        if result.execution_time:
            current_avg = self._metrics.avg_processing_time
            total_tasks = self._metrics.completed_tasks
            self._metrics.avg_processing_time = (
                current_avg * (total_tasks - 1) + result.execution_time
            ) / total_tasks

    async def _on_task_failed(self, task: TaskData, result: TaskResult) -> None:
        """Handle task failure.

        Args:
            task: Failed task
            result: Failure result
        """
        self._metrics.failed_tasks += 1
        self._metrics.worker_metrics.tasks_failed += 1

        # Update error rate
        total_tasks = self._metrics.completed_tasks + self._metrics.failed_tasks
        if total_tasks > 0:
            self._metrics.error_rate = self._metrics.failed_tasks / total_tasks

    # Handler registration
    def register_handler(self, task_type: str, handler: TaskHandler) -> None:
        """Register a task handler.

        Args:
            task_type: Task type identifier
            handler: Task handler instance
        """
        self._handlers[task_type] = handler
        self.logger.info(f"Registered handler for task type: {task_type}")

    def unregister_handler(self, task_type: str) -> None:
        """Unregister a task handler.

        Args:
            task_type: Task type identifier
        """
        if task_type in self._handlers:
            del self._handlers[task_type]
            self.logger.info(f"Unregistered handler for task type: {task_type}")

    def get_handler(self, task_type: str) -> TaskHandler | None:
        """Get a registered task handler.

        Args:
            task_type: Task type identifier

        Returns:
            Task handler or None if not found
        """
        return self._handlers.get(task_type)

    def list_handlers(self) -> list[str]:
        """List all registered task types.

        Returns:
            List of task type identifiers
        """
        return list(self._handlers.keys())

    # Lifecycle management
    async def start(self) -> None:
        """Start the queue system."""
        if self._running:
            return

        self._running = True
        self._shutdown_event.clear()

        # Start workers
        await self.start_workers()

        # Start health monitoring if enabled
        if self._settings.health_check_enabled:
            asyncio.create_task(self._health_check_loop())

        # Start metrics collection if enabled
        if self._settings.enable_metrics:
            asyncio.create_task(self._metrics_loop())

        self.logger.info("Queue system started")

    async def stop(self) -> None:
        """Stop the queue system."""
        if not self._running:
            return

        self._running = False

        # Stop workers
        await self.stop_workers()

        # Clean up resources
        await self.cleanup()

        self.logger.info("Queue system stopped")

    async def _health_check_loop(self) -> None:
        """Health check monitoring loop."""
        while self._running and not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(self._settings.health_check_interval)

                # Perform health checks
                health_status = await self.health_check()
                if not health_status.get("healthy", True):
                    self.logger.warning(f"Queue health check failed: {health_status}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.exception(f"Health check error: {e}")

    async def _metrics_loop(self) -> None:
        """Metrics collection loop."""
        while self._running and not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(self._settings.metrics_interval)

                # Update metrics
                await self._update_metrics()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.exception(f"Metrics collection error: {e}")

    async def _update_metrics(self) -> None:
        """Update queue metrics."""
        # Update queue depth and other metrics
        # This should be implemented by concrete queue implementations

    async def health_check(self) -> dict[str, t.Any]:
        """Perform health check.

        Returns:
            Health status information
        """
        return {
            "healthy": self._running,
            "metrics": {
                "pending_tasks": self._metrics.pending_tasks,
                "processing_tasks": self._metrics.processing_tasks,
                "active_workers": self._metrics.worker_metrics.active_workers,
                "total_workers": self._metrics.worker_metrics.total_workers,
                "error_rate": self._metrics.error_rate,
            },
        }

    # Convenience methods
    async def create_task(
        self,
        task_type: str,
        payload: dict[str, t.Any] | None = None,
        queue_name: str = "default",
        priority: TaskPriority = TaskPriority.NORMAL,
        delay: float = 0.0,
        **kwargs: t.Any,
    ) -> str:
        """Create and enqueue a task.

        Args:
            task_type: Task type identifier
            payload: Task payload
            queue_name: Target queue name
            priority: Task priority
            delay: Delay before processing
            **kwargs: Additional task options

        Returns:
            Task ID
        """
        task = TaskData(
            task_type=task_type,
            payload=payload or {},
            queue_name=queue_name,
            priority=priority,
            delay=delay,
            **kwargs,
        )

        return await self.enqueue(task)

    async def __aenter__(self) -> "QueueBase":
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type: t.Any, exc_val: t.Any, exc_tb: t.Any) -> None:
        """Async context manager exit."""
        await self.stop()


# Utility functions
def create_task_data(
    task_type: str,
    payload: dict[str, t.Any] | None = None,
    **kwargs: t.Any,
) -> TaskData:
    """Create a TaskData instance.

    Args:
        task_type: Task type identifier
        payload: Task payload
        **kwargs: Additional task options

    Returns:
        TaskData instance
    """
    return TaskData(
        task_type=task_type,
        payload=payload or {},
        **kwargs,
    )


def generate_queue_id() -> UUID:
    """Generate a unique queue identifier.

    Returns:
        UUID7 identifier
    """
    return uuid4()
