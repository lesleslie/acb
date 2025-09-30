"""ACB Task Queue System - Persistent job processing and worker management.

Provides a comprehensive task queue system with multiple backend support,
worker pool management, retry mechanisms, and advanced scheduling capabilities.
Designed to complement the Events System with reliable background processing.

Features:
- Multiple queue backends (Memory, Redis, RabbitMQ)
- Priority-based task processing
- Delayed and scheduled tasks
- Retry mechanisms with exponential backoff
- Dead letter queues for failed tasks
- Worker pool management with scaling
- Comprehensive monitoring and metrics
- Service discovery and registration
- Integration with ACB Services Layer

Usage:
    # Basic task queue usage
    from acb.queues import create_queue, TaskData, task_handler

    # Create a queue
    async with create_queue("memory") as queue:
        # Define a task handler
        @task_handler("email_task")
        async def send_email(task):
            email = task.payload["email"]
            return {"sent": True, "email": email}

        # Register handler
        queue.register_handler("email_task", send_email)

        # Create and enqueue a task
        task = TaskData(
            task_type="email_task",
            payload={"email": "user@example.com"},
            priority=TaskPriority.HIGH
        )
        task_id = await queue.enqueue(task)

    # Task scheduling
    from acb.queues import TaskScheduler

    scheduler = TaskScheduler(queue)
    await scheduler.start()

    # Schedule a task to run every hour
    scheduler.schedule_cron(
        "0 * * * *",  # Every hour
        "cleanup_task",
        payload={"type": "hourly_cleanup"}
    )

    # Queue discovery
    from acb.queues import list_available_queue_providers, import_queue_provider

    providers = list_available_queue_providers()
    QueueClass = import_queue_provider("redis")
"""

# Core queue classes
from ._base import (
    FunctionalTaskHandler,
    QueueBase,
    QueueCapability,
    QueueMetadata,
    QueueMetrics,
    QueueSettings,
    TaskData,
    TaskHandler,
    TaskPriority,
    TaskResult,
    TaskStatus,
    WorkerMetrics,
    create_task_data,
    generate_queue_id,
    task_handler,
)

# Queue implementations
from .memory import (
    MemoryQueue,
    MemoryQueueSettings,
    create_memory_queue,
)

try:
    from .redis import (
        RedisQueue,
        RedisQueueSettings,
        create_redis_queue,
    )

    REDIS_AVAILABLE = True
except ImportError:
    RedisQueue = None
    RedisQueueSettings = None
    create_redis_queue = None
    REDIS_AVAILABLE = False

try:
    from .rabbitmq import (
        RabbitMQQueue,
        RabbitMQQueueSettings,
        create_rabbitmq_queue,
    )

    RABBITMQ_AVAILABLE = True
except ImportError:
    RabbitMQQueue = None
    RabbitMQQueueSettings = None
    create_rabbitmq_queue = None
    RABBITMQ_AVAILABLE = False

# Task scheduling
# Queue discovery system
from .discovery import (
    QueueContext,
    QueueProviderDescriptor,
    QueueProviderNotFound,
    QueueProviderNotInstalled,
    QueueProviderStatus,
    apply_queue_provider_overrides,
    create_queue_instance,
    create_queue_instance_async,
    create_queue_metadata_template,
    disable_queue_provider,
    enable_queue_provider,
    generate_provider_id,
    get_queue_provider_class,
    get_queue_provider_descriptor,
    get_queue_provider_info,
    get_queue_provider_override,
    import_queue_provider,
    initialize_queue_discovery,
    list_available_queue_providers,
    list_enabled_queue_providers,
    list_queue_providers,
    list_queue_providers_by_capability,
    queue_context,
    register_queue_providers,
    try_import_queue_provider,
)
from .scheduler import (
    ScheduleRule,
    TaskScheduler,
    create_scheduler,
    parse_cron_expression,
    scheduled_task,
)

__all__ = [
    # Core queue classes
    "QueueBase",
    "QueueCapability",
    "QueueMetadata",
    "QueueSettings",
    "TaskData",
    "TaskHandler",
    "TaskResult",
    "TaskStatus",
    "TaskPriority",
    "FunctionalTaskHandler",
    "WorkerMetrics",
    "QueueMetrics",
    "create_task_data",
    "generate_queue_id",
    "task_handler",
    # Memory queue implementation
    "MemoryQueue",
    "MemoryQueueSettings",
    "create_memory_queue",
    # Redis queue implementation (if available)
    "RedisQueue",
    "RedisQueueSettings",
    "create_redis_queue",
    "REDIS_AVAILABLE",
    # RabbitMQ queue implementation (if available)
    "RabbitMQQueue",
    "RabbitMQQueueSettings",
    "create_rabbitmq_queue",
    "RABBITMQ_AVAILABLE",
    # Task scheduling
    "ScheduleRule",
    "TaskScheduler",
    "create_scheduler",
    "parse_cron_expression",
    "scheduled_task",
    # Discovery system
    "QueueProviderDescriptor",
    "QueueProviderNotFound",
    "QueueProviderNotInstalled",
    "QueueProviderStatus",
    "QueueContext",
    "apply_queue_provider_overrides",
    "create_queue_instance",
    "create_queue_instance_async",
    "create_queue_metadata_template",
    "disable_queue_provider",
    "enable_queue_provider",
    "generate_provider_id",
    "get_queue_provider_class",
    "get_queue_provider_descriptor",
    "get_queue_provider_info",
    "get_queue_provider_override",
    "import_queue_provider",
    "initialize_queue_discovery",
    "list_available_queue_providers",
    "list_enabled_queue_providers",
    "list_queue_providers",
    "list_queue_providers_by_capability",
    "queue_context",
    "register_queue_providers",
    "try_import_queue_provider",
    # Service integration
    "QueueService",
    "QueueServiceSettings",
    "get_queue_service",
    "setup_queue_service",
]


# Queue System metadata following ACB patterns
QUEUE_SYSTEM_VERSION = "1.0.0"
ACB_MIN_VERSION = "0.19.1"


# Service integration with ACB Services Layer
import typing as t
from uuid import UUID

from acb.services import (
    ServiceBase,
    ServiceCapability,
    ServiceMetadata,
    ServiceSettings,
)
from acb.services.discovery import ServiceStatus, generate_service_id


class QueueServiceSettings(ServiceSettings):
    """Settings for the Queue System service."""

    # Queue provider
    queue_provider: str = "memory"
    queue_settings: dict[str, t.Any] = {}

    # Worker configuration
    default_max_workers: int = 10
    default_worker_timeout: float = 300.0

    # Scheduler settings
    enable_scheduler: bool = True
    scheduler_check_interval: float = 1.0

    # Health monitoring
    enable_health_checks: bool = True
    health_check_interval: float = 60.0

    # Metrics collection
    enable_metrics: bool = True
    metrics_interval: float = 30.0


class QueueService(ServiceBase):
    """Queue System service for ACB framework integration."""

    SERVICE_METADATA = ServiceMetadata(
        service_id=generate_service_id(),
        name="Queue Service",
        category="queues",
        service_type="messaging",
        version=QUEUE_SYSTEM_VERSION,
        acb_min_version=ACB_MIN_VERSION,
        author="ACB Framework",
        created_date="2024-01-01",
        last_modified="2024-01-01",
        status=ServiceStatus.STABLE,
        capabilities=[
            ServiceCapability.ASYNC_OPERATIONS,
            ServiceCapability.HEALTH_MONITORING,
            ServiceCapability.METRICS_COLLECTION,
            ServiceCapability.ERROR_HANDLING,
        ],
        description="Task queue service with persistent job processing",
        settings_class="QueueServiceSettings",
    )

    def __init__(self, settings: QueueServiceSettings | None = None):
        super().__init__()
        self._settings = settings or QueueServiceSettings()
        self._queue: QueueBase | None = None
        self._scheduler: TaskScheduler | None = None

    async def _initialize(self) -> None:
        """Service-specific initialization logic."""
        # Create queue instance
        queue_settings_class = None

        # Get provider-specific settings class
        try:
            descriptor = get_queue_provider_descriptor(self._settings.queue_provider)
            if descriptor:
                import importlib

                module = importlib.import_module(descriptor.module_path)
                settings_class_name = f"{descriptor.class_name}Settings"

                if hasattr(module, settings_class_name):
                    queue_settings_class = getattr(module, settings_class_name)
        except Exception:
            pass  # Ignore import errors for optional settings classes

        # Create queue settings
        if queue_settings_class:
            queue_settings = queue_settings_class(**self._settings.queue_settings)
        else:
            queue_settings = None

        # Create and start queue
        self._queue = create_queue_instance(
            self._settings.queue_provider, queue_settings
        )
        await self._queue.start()

        # Create and start scheduler if enabled
        if self._settings.enable_scheduler:
            self._scheduler = TaskScheduler(self._queue)
            await self._scheduler.start()

    async def _shutdown(self) -> None:
        """Service-specific shutdown logic."""
        # Stop scheduler
        if self._scheduler:
            await self._scheduler.stop()
            self._scheduler = None

        # Stop queue
        if self._queue:
            await self._queue.stop()
            self._queue = None

    async def _health_check(self) -> dict[str, t.Any]:
        """Service-specific health check logic."""
        health: dict[str, t.Any] = {"status": "ok"}

        if self._queue:
            queue_health = await self._queue.health_check()
            health["queue"] = queue_health

        if self._scheduler:
            health["scheduler"] = {
                "running": getattr(self._scheduler, "_running", False),
                "rules_count": len(getattr(self._scheduler, "_rules", [])),
            }

        return health

    @property
    def queue(self) -> QueueBase | None:
        """Get the queue instance."""
        return self._queue

    @property
    def scheduler(self) -> TaskScheduler | None:
        """Get the scheduler instance."""
        return self._scheduler

    async def enqueue(self, task: TaskData) -> str:
        """Enqueue a task."""
        if not self._queue:
            raise RuntimeError("Queue not available")
        return await self._queue.enqueue(task)

    async def create_task(
        self,
        task_type: str,
        payload: dict[str, t.Any] | None = None,
        queue_name: str = "default",
        priority: TaskPriority = TaskPriority.NORMAL,
        **kwargs: t.Any,
    ) -> str:
        """Create and enqueue a task."""
        if not self._queue:
            raise RuntimeError("Queue not available")
        return await self._queue.create_task(
            task_type, payload, queue_name, priority, **kwargs
        )

    def register_handler(self, task_type: str, handler: TaskHandler) -> None:
        """Register a task handler."""
        if not self._queue:
            raise RuntimeError("Queue not available")
        self._queue.register_handler(task_type, handler)

    def schedule_cron(
        self,
        cron_expression: str,
        task_type: str,
        name: str | None = None,
        **kwargs: t.Any,
    ) -> UUID:
        """Schedule a task using cron expression."""
        if not self._scheduler:
            raise RuntimeError("Scheduler not available")
        return self._scheduler.schedule_cron(cron_expression, task_type, name, **kwargs)

    def schedule_interval(
        self,
        interval_seconds: float,
        task_type: str,
        name: str | None = None,
        **kwargs: t.Any,
    ) -> UUID:
        """Schedule a task at regular intervals."""
        if not self._scheduler:
            raise RuntimeError("Scheduler not available")
        return self._scheduler.schedule_interval(
            interval_seconds, task_type, name, **kwargs
        )


# Global queue service instance
_queue_service: QueueService | None = None


def get_queue_service() -> QueueService:
    """Get the global queue service instance."""
    global _queue_service
    if _queue_service is None:
        _queue_service = QueueService()
    return _queue_service


async def setup_queue_service(
    settings: QueueServiceSettings | None = None,
) -> QueueService:
    """Setup and start the queue service.

    Args:
        settings: Queue service settings

    Returns:
        Started QueueService instance
    """
    global _queue_service
    _queue_service = QueueService(settings)
    await _queue_service.initialize()

    # Register with ACB dependency injection
    from acb.depends import depends

    depends.set(QueueService, _queue_service)

    return _queue_service


# Convenience functions
def create_queue(
    provider_name: str | None = None,
    **kwargs: t.Any,
) -> QueueContext:
    """Create a queue context manager.

    Args:
        provider_name: Queue provider name
        **kwargs: Additional settings

    Returns:
        QueueContext instance
    """
    return queue_context(provider_name, **kwargs)


async def create_task_queue(
    provider_name: str | None = None,
    settings: QueueSettings | None = None,
    **kwargs: t.Any,
) -> QueueBase:
    """Create and start a task queue.

    Args:
        provider_name: Queue provider name
        settings: Queue settings
        **kwargs: Additional settings

    Returns:
        Started queue instance
    """
    return await create_queue_instance_async(provider_name, settings, **kwargs)


# Integration with Services Layer discovery
from acb.services.discovery import enable_service

# Register queue service in service discovery
try:
    enable_service("queues", "queue_service")
except Exception:
    pass  # pragma: allowlist secret  # Service registry may not be initialized yet


# Auto-initialize discovery
import typing as t
