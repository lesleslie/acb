"""RabbitMQ-based queue implementation for ACB framework.

This module provides a RabbitMQ-backed task queue implementation suitable for
enterprise deployments with high availability, clustering, and advanced routing.
"""

import logging
import time
from uuid import UUID

import asyncio
import typing as t
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

try:
    import aio_pika  # type: ignore[import-not-found]
    from aio_pika import (  # type: ignore[import-not-found]
        Channel,
        Connection,
        DeliveryMode,
        ExchangeType,
        Message,
        Queue,
    )
    from aio_pika.abc import (  # type: ignore[import-not-found]
        AbstractExchange,
        AbstractIncomingMessage,
        AbstractQueueIterator,
    )

    RABBITMQ_AVAILABLE = True
except ImportError:
    aio_pika = None  # type: ignore[assignment]
    Connection = None  # type: ignore[assignment,misc]
    Channel = None  # type: ignore[assignment,misc]
    Queue = None
    Message = None
    DeliveryMode = None
    ExchangeType = None
    AbstractIncomingMessage = None
    AbstractQueueIterator = None
    AbstractExchange = None
    RABBITMQ_AVAILABLE = False

import contextlib

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
    name="RabbitMQ Queue",
    description="RabbitMQ-backed task queue for enterprise deployments",
    version="1.0.0",
    capabilities=[
        QueueCapability.BASIC_QUEUE,
        QueueCapability.PRIORITY_QUEUE,
        QueueCapability.DELAYED_TASKS,
        QueueCapability.RETRY_MECHANISMS,
        QueueCapability.DEAD_LETTER_QUEUE,
        QueueCapability.BATCH_PROCESSING,
        QueueCapability.PERSISTENCE,
        QueueCapability.METRICS_COLLECTION,
        QueueCapability.HEALTH_MONITORING,
        QueueCapability.TASK_TRACKING,
        QueueCapability.WORKER_POOLS,
        QueueCapability.HORIZONTAL_SCALING,
        QueueCapability.LOAD_BALANCING,
        QueueCapability.RATE_LIMITING,
        QueueCapability.CIRCUIT_BREAKER,
        QueueCapability.CRON_SCHEDULING,
    ],
    max_throughput=50_000,  # tasks per second
    max_workers=10_000,
    supports_clustering=True,
    required_packages=["aio-pika>=9.0.0"],
    min_python_version="3.13",
    config_schema={
        "rabbitmq_url": {"type": "string", "default": "amqp://localhost:5672/"},
        "exchange_name": {"type": "string", "default": "acb.tasks"},
        "exchange_type": {"type": "string", "default": "direct"},
        "queue_durable": {"type": "boolean", "default": True},
        "message_ttl": {"type": "integer", "default": 86400000},  # 24 hours in ms
        "max_priority": {"type": "integer", "default": 255},
        "prefetch_count": {"type": "integer", "default": 10},
        "heartbeat": {"type": "integer", "default": 60},
        "connection_timeout": {"type": "number", "default": 10.0},
    },
    default_settings={
        "rabbitmq_url": "amqp://localhost:5672/",
        "exchange_name": "acb.tasks",
        "exchange_type": "direct",
        "queue_durable": True,
        "message_ttl": 86400000,
        "max_priority": 255,
        "prefetch_count": 10,
        "heartbeat": 60,
        "connection_timeout": 10.0,
    },
)


class RabbitMQQueueSettings(QueueSettings):
    """Settings for RabbitMQ queue implementation."""

    # RabbitMQ connection
    rabbitmq_url: str = "amqp://localhost:5672/"
    virtual_host: str = "/"
    heartbeat: int = 60
    connection_timeout: float = 10.0

    # Exchange configuration
    exchange_name: str = "acb.tasks"
    exchange_type: str = "direct"  # direct, topic, fanout, headers
    exchange_durable: bool = True

    # Queue configuration
    queue_durable: bool = True
    queue_auto_delete: bool = False
    message_ttl: int = 86400000  # 24 hours in milliseconds
    max_priority: int = 255

    # Consumer configuration
    prefetch_count: int = 10
    consumer_timeout: float = 300.0  # 5 minutes

    # Dead letter configuration
    dead_letter_exchange: str = "acb.tasks.dlx"
    dead_letter_routing_key: str = "dead_letter"

    # Delayed message configuration
    delayed_exchange: str = "acb.tasks.delayed"
    use_delayed_exchange_plugin: bool = True

    # High availability
    enable_ha: bool = False
    ha_policy: str = "all"  # all, exactly, nodes
    ha_params: list[str] = []


class RabbitMQQueue(QueueBase):
    """RabbitMQ-backed task queue implementation."""

    _settings: RabbitMQQueueSettings  # Type hint for proper attribute checking

    def __init__(self, settings: RabbitMQQueueSettings | None = None) -> None:
        if not RABBITMQ_AVAILABLE:
            msg = "aio-pika is required for RabbitMQQueue. Install with: pip install aio-pika>=9.0.0"
            raise ImportError(
                msg,
            )

        super().__init__(settings)
        self._settings = settings or RabbitMQQueueSettings()

        # RabbitMQ connection and channels
        self._connection: t.Any = None  # Connection | None when aio_pika available
        self._channel: t.Any = None  # Channel | None when aio_pika available
        self._consumer_channel: t.Any = None  # Channel | None when aio_pika available

        # RabbitMQ objects
        self._exchange: t.Any = None  # AbstractExchange | None when aio_pika available
        self._dead_letter_exchange: t.Any = (
            None  # AbstractExchange | None when aio_pika available
        )
        self._delayed_exchange: t.Any = (
            None  # AbstractExchange | None when aio_pika available
        )
        self._queues: dict[str, t.Any] = {}  # dict[str, Queue] when aio_pika available
        self._consumers: dict[
            str,
            t.Any,
        ] = {}  # dict[str, AbstractQueueIterator] when aio_pika available

        # Background tasks
        self._consumer_task: asyncio.Task[None] | None = None
        self._health_monitor: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the RabbitMQ queue."""
        await self._ensure_connection()
        await self._setup_exchanges()
        await super().start()

        # Start consumer
        self._consumer_task = asyncio.create_task(self._consumer_loop())

        # Start health monitor
        self._health_monitor = asyncio.create_task(self._health_monitor_loop())

        self.logger.info("RabbitMQ queue started")

    async def stop(self) -> None:
        """Stop the RabbitMQ queue."""
        # Stop background tasks
        if self._consumer_task:
            self._consumer_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._consumer_task

        if self._health_monitor:
            self._health_monitor.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._health_monitor

        await super().stop()

        # Close consumers
        for consumer in self._consumers.values():
            with suppress(Exception):
                await consumer.close()
        # pragma: allowlist secret  # Ignore consumer close errors during shutdown
        self._consumers.clear()

        # Close RabbitMQ connection
        if self._consumer_channel:
            await self._consumer_channel.close()
            self._consumer_channel = None

        if self._channel:
            await self._channel.close()
            self._channel = None

        if self._connection:
            await self._connection.close()
            self._connection = None

        self.logger.info("RabbitMQ queue stopped")

    async def _ensure_connection(self) -> t.Any:
        """Ensure RabbitMQ connection is available."""
        if self._connection is None or self._connection.is_closed:
            try:
                self._connection = await aio_pika.connect_robust(
                    self._settings.rabbitmq_url,
                    heartbeat=self._settings.heartbeat,
                    timeout=self._settings.connection_timeout,
                )

                # Create main channel
                self._channel = await self._connection.channel()
                await self._channel.set_qos(
                    prefetch_count=self._settings.prefetch_count,
                )

                # Create consumer channel
                self._consumer_channel = await self._connection.channel()
                await self._consumer_channel.set_qos(
                    prefetch_count=self._settings.prefetch_count,
                )

                self.logger.debug("RabbitMQ connection established")

            except Exception as e:
                self.logger.exception(f"Failed to connect to RabbitMQ: {e}")
                raise

        return self._connection

    async def _setup_exchanges(self) -> None:
        """Setup RabbitMQ exchanges."""
        if not self._channel:
            msg = "Channel not available"
            raise RuntimeError(msg)

        try:
            # Main exchange
            self._exchange = await self._channel.declare_exchange(
                self._settings.exchange_name,
                type=ExchangeType(self._settings.exchange_type),
                durable=self._settings.exchange_durable,
            )

            # Dead letter exchange
            self._dead_letter_exchange = await self._channel.declare_exchange(
                self._settings.dead_letter_exchange,
                type=ExchangeType.DIRECT,
                durable=True,
            )

            # Delayed exchange (if using plugin)
            if self._settings.use_delayed_exchange_plugin:
                try:
                    self._delayed_exchange = await self._channel.declare_exchange(
                        self._settings.delayed_exchange,
                        type="x-delayed-message",
                        durable=True,
                        arguments={"x-delayed-type": "direct"},
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to create delayed exchange: {e}")
                    self._settings.use_delayed_exchange_plugin = False

            self.logger.debug("RabbitMQ exchanges setup complete")

        except Exception as e:
            self.logger.exception(f"Failed to setup exchanges: {e}")
            raise

    async def _ensure_queue(self, queue_name: str) -> Queue:
        """Ensure a queue exists and return it."""
        if queue_name not in self._queues:
            if not self._channel:
                msg = "Channel not available"
                raise RuntimeError(msg)

            # Queue arguments
            arguments = {
                "x-message-ttl": self._settings.message_ttl,
                "x-max-priority": self._settings.max_priority,
                "x-dead-letter-exchange": self._settings.dead_letter_exchange,
                "x-dead-letter-routing-key": self._settings.dead_letter_routing_key,
            }

            # High availability
            if self._settings.enable_ha:
                arguments["x-ha-policy"] = self._settings.ha_policy
                if self._settings.ha_params:
                    arguments["x-ha-policy-params"] = self._settings.ha_params

            # Declare queue
            queue = await self._channel.declare_queue(
                queue_name,
                durable=self._settings.queue_durable,
                auto_delete=self._settings.queue_auto_delete,
                arguments=arguments,
            )

            # Bind to exchange
            await queue.bind(self._exchange, routing_key=queue_name)

            self._queues[queue_name] = queue
            self.logger.debug(f"Created queue: {queue_name}")

        return self._queues[queue_name]

    async def enqueue(self, task: TaskData) -> str:
        """Enqueue a task for processing."""
        if not self._running:
            msg = "Queue is not running"
            raise RuntimeError(msg)

        await self._ensure_connection()

        try:
            # Serialize task data
            task_json = task.model_dump_json()

            # Create message
            message = Message(
                task_json.encode(),
                priority=min(task.priority.value * 50, self._settings.max_priority),
                delivery_mode=DeliveryMode.PERSISTENT,
                message_id=str(task.task_id),
                correlation_id=str(task.task_id),
                headers={
                    "task_type": task.task_type,
                    "created_at": task.created_at.isoformat(),
                    "retry_count": 0,
                },
            )

            # Handle delayed tasks
            if task.delay > 0 or task.scheduled_at:
                await self._enqueue_delayed_task(task, message)
            else:
                # Send immediately
                await self._exchange.publish(
                    message,
                    routing_key=task.queue_name,
                )

            # Update metrics
            self._metrics.pending_tasks += 1

            self.logger.debug(
                f"Enqueued task {task.task_id} to queue {task.queue_name}",
            )
            return str(task.task_id)

        except Exception as e:
            self.logger.exception(f"Failed to enqueue task {task.task_id}: {e}")
            raise

    async def _enqueue_delayed_task(self, task: TaskData, message: Message) -> None:
        """Enqueue a delayed task."""
        # Calculate delay in milliseconds
        if task.delay > 0:
            delay_ms = int(task.delay * 1000)
        elif task.scheduled_at:
            delay_ms = max(0, int((task.scheduled_at.timestamp() - time.time()) * 1000))
        else:
            delay_ms = 0

        if self._settings.use_delayed_exchange_plugin and self._delayed_exchange:
            # Use RabbitMQ delayed message plugin
            message.headers["x-delay"] = delay_ms
            await self._delayed_exchange.publish(
                message,
                routing_key=task.queue_name,
            )
        else:
            # Use TTL + dead letter pattern
            temp_queue_name = f"delayed.{task.queue_name}.{int(time.time())}"

            # Create temporary queue with TTL
            await self._channel.declare_queue(
                temp_queue_name,
                durable=False,
                auto_delete=True,
                arguments={
                    "x-message-ttl": delay_ms,
                    "x-dead-letter-exchange": self._settings.exchange_name,
                    "x-dead-letter-routing-key": task.queue_name,
                },
            )

            # Publish to temporary queue
            await self._exchange.publish(
                message,
                routing_key=temp_queue_name,
            )

    async def dequeue(self, queue_name: str | None = None) -> TaskData | None:
        """Dequeue a task for processing."""
        # This method is not used directly in RabbitMQ implementation
        # Instead, tasks are consumed via the consumer loop
        return None

    async def _consumer_loop(self) -> None:
        """Main consumer loop."""
        while self._running and not self._shutdown_event.is_set():
            try:
                # Get all queue names to consume from
                queue_names = (
                    list(self._handlers.keys()) if self._handlers else ["default"]
                )

                for queue_name in queue_names:
                    if queue_name not in self._consumers:
                        await self._start_queue_consumer(queue_name)

                await asyncio.sleep(1.0)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.exception(f"Consumer loop error: {e}")
                await asyncio.sleep(5.0)

    async def _start_queue_consumer(self, queue_name: str) -> None:
        """Start consuming from a specific queue."""
        try:
            queue = await self._ensure_queue(queue_name)

            # Start consuming
            consumer = queue.iterator()
            self._consumers[queue_name] = consumer

            # Process messages
            asyncio.create_task(self._process_queue_messages(queue_name, consumer))

            self.logger.debug(f"Started consumer for queue: {queue_name}")

        except Exception as e:
            self.logger.exception(
                f"Failed to start consumer for queue {queue_name}: {e}"
            )

    async def _process_queue_messages(
        self,
        queue_name: str,
        consumer: t.Any,  # AbstractQueueIterator when aio_pika available
    ) -> None:
        """Process messages from a queue."""
        try:
            async for message in consumer:
                if self._shutdown_event.is_set():
                    break

                async with message.process():
                    try:
                        # Parse task data
                        task_json = message.body.decode()
                        task = TaskData.model_validate_json(task_json)

                        # Update metrics
                        self._metrics.pending_tasks = max(
                            0,
                            self._metrics.pending_tasks - 1,
                        )
                        self._metrics.processing_tasks += 1

                        # Process task
                        await self._process_rabbitmq_task(task, message)

                    except Exception as e:
                        self.logger.exception(f"Failed to process message: {e}")
                        # Message will be rejected and potentially sent to DLQ
                        raise

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.exception(
                f"Queue message processor error for {queue_name}: {e}"
            )

    async def _process_rabbitmq_task(self, task: TaskData, message: t.Any) -> None:
        """Process a RabbitMQ task message."""
        start_time = time.time()
        current_task = asyncio.current_task()
        worker_id = f"rabbitmq-{current_task.get_name() if current_task else 'unknown'}"

        try:
            # Get task handler
            handler = self._handlers.get(task.task_type)
            if handler is None:
                msg = f"No handler registered for task type: {task.task_type}"
                raise ValueError(
                    msg,
                )

            # Execute task
            result = await asyncio.wait_for(
                handler.handle(task),
                timeout=task.timeout or self._settings.default_task_timeout,
            )
            result.worker_id = worker_id

            # Handle successful completion
            await handler.on_success(task, result)
            await self._on_task_completed(task, result)

            # Acknowledge message
            message.ack()

        except TimeoutError:
            error = f"Task timed out after {task.timeout}s"
            await self._handle_task_failure(
                task,
                message,
                Exception(error),
                worker_id,
                start_time,
            )
        except Exception as e:
            await self._handle_task_failure(task, message, e, worker_id, start_time)

    async def _handle_task_failure(
        self,
        task: TaskData,
        message: t.Any,  # AbstractIncomingMessage when aio_pika available
        error: Exception,
        worker_id: str,
        start_time: float,
    ) -> None:
        """Handle task failure."""
        result = TaskResult(
            task_id=task.task_id,
            status=TaskStatus.FAILED,
            error=str(error),
            started_at=datetime.now(tz=UTC),
            completed_at=datetime.now(tz=UTC),
            execution_time=time.time() - start_time,
            worker_id=worker_id,
            queue_name=task.queue_name,
        )

        handler = self._handlers.get(task.task_type)
        retry_count = int(message.headers.get("retry_count", 0))

        if (
            handler
            and await handler.on_failure(task, error)
            and retry_count < task.max_retries
        ):
            # Retry the task
            await self._retry_rabbitmq_task(task, message, retry_count + 1)
            message.ack()  # Acknowledge original message
        else:
            # Send to dead letter queue
            result.status = TaskStatus.DEAD_LETTER
            await self._on_task_failed(task, result)
            message.reject(requeue=False)  # Reject and send to DLQ

    async def _retry_rabbitmq_task(
        self,
        task: TaskData,
        original_message: t.Any,  # AbstractIncomingMessage when aio_pika available
        retry_count: int,
    ) -> None:
        """Retry a failed RabbitMQ task."""
        retry_delay = task.retry_delay * (
            self._settings.retry_exponential_base**retry_count
        )

        # Create retry task
        retry_task = task.copy()
        retry_task.task_id = task.task_id  # Keep same ID for tracking
        retry_task.delay = retry_delay
        retry_task.tags["retry_count"] = str(retry_count)
        retry_task.tags["original_task_id"] = str(task.task_id)

        # Create retry message
        retry_message = Message(
            retry_task.model_dump_json().encode(),
            priority=original_message.priority,
            delivery_mode=DeliveryMode.PERSISTENT,
            message_id=str(retry_task.task_id),
            correlation_id=str(task.task_id),
            headers={
                "task_type": retry_task.task_type,
                "created_at": retry_task.created_at.isoformat(),
                "retry_count": retry_count,
                "original_message_id": original_message.message_id,
            },
        )

        await self._enqueue_delayed_task(retry_task, retry_message)
        self.logger.info(f"Retrying task {task.task_id} (attempt {retry_count})")

    async def get_task_status(self, task_id: UUID) -> TaskResult | None:
        """Get task status and result."""
        # In RabbitMQ implementation, task status is tracked via external storage
        # This would typically be implemented using Redis or a database
        # For now, return None as tasks are processed immediately
        return None

    async def cancel_task(self, task_id: UUID) -> bool:
        """Cancel a pending task."""
        # Task cancellation in RabbitMQ would require message browsing
        # which is not efficient. Consider using Redis for task tracking.
        return False

    async def get_queue_info(self, queue_name: str) -> dict[str, Any]:
        """Get information about a queue."""
        try:
            queue = await self._ensure_queue(queue_name)

            # Get queue info from RabbitMQ
            declare_result = await queue.declare(passive=True)

            return {
                "name": queue_name,
                "message_count": declare_result.message_count,
                "consumer_count": declare_result.consumer_count,
                "durable": queue.durable,
                "auto_delete": queue.auto_delete,
            }

        except Exception as e:
            self.logger.exception(f"Failed to get queue info for {queue_name}: {e}")
            return {"name": queue_name, "error": str(e)}

    async def purge_queue(self, queue_name: str) -> int:
        """Remove all tasks from a queue."""
        try:
            queue = await self._ensure_queue(queue_name)

            # Purge queue
            result = await queue.purge()

            self.logger.info(
                f"Purged {result.message_count} messages from queue {queue_name}",
            )
            return result.message_count

        except Exception as e:
            self.logger.exception(f"Failed to purge queue {queue_name}: {e}")
            return 0

    async def list_queues(self) -> list[str]:
        """List all available queues."""
        return list(self._queues.keys())

    async def _store_dead_letter_task(self, task: TaskData, result: TaskResult) -> None:
        """Store task in dead letter queue."""
        # Dead letter tasks are automatically handled by RabbitMQ DLX
        self._metrics.dead_letter_tasks += 1

    async def _health_monitor_loop(self) -> None:
        """Monitor RabbitMQ connection health."""
        while self._running and not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(self._settings.health_check_interval)

                # Check connection
                if self._connection and not self._connection.is_closed:
                    # Connection is healthy
                    self._metrics.last_task_processed = datetime.now(tz=UTC)
                else:
                    # Try to reconnect
                    self.logger.warning(
                        "RabbitMQ connection lost, attempting reconnect",
                    )
                    await self._ensure_connection()
                    await self._setup_exchanges()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.exception(f"RabbitMQ health monitor error: {e}")

    async def _on_task_completed(self, task: TaskData, result: TaskResult) -> None:
        """Handle task completion."""
        await super()._on_task_completed(task, result)

        # Update metrics
        self._metrics.processing_tasks = max(0, self._metrics.processing_tasks - 1)

    async def _on_task_failed(self, task: TaskData, result: TaskResult) -> None:
        """Handle task failure."""
        await super()._on_task_failed(task, result)

        # Update metrics
        self._metrics.processing_tasks = max(0, self._metrics.processing_tasks - 1)

    async def health_check(self) -> dict[str, Any]:
        """Perform health check."""
        base_health = await super().health_check()

        try:
            rabbitmq_health = {
                "connected": self._connection and not self._connection.is_closed,
                "exchanges_ready": all(
                    [
                        self._exchange is not None,
                        self._dead_letter_exchange is not None,
                    ],
                ),
                "active_consumers": len(self._consumers),
                "queues_count": len(self._queues),
            }

            if self._connection and not self._connection.is_closed:
                rabbitmq_health["server_properties"] = (
                    self._connection.server_properties
                )

            base_health["rabbitmq"] = rabbitmq_health

        except Exception as e:
            base_health["rabbitmq"] = {
                "connected": False,
                "error": str(e),
            }
            base_health["healthy"] = False

        return base_health

    # Additional RabbitMQ specific methods
    async def create_dead_letter_consumer(self) -> None:
        """Create consumer for dead letter queue."""
        try:
            # Declare dead letter queue
            dlq = await self._channel.declare_queue(
                self._settings.dead_letter_routing_key,
                durable=True,
            )

            # Bind to dead letter exchange
            await dlq.bind(
                self._dead_letter_exchange,
                routing_key=self._settings.dead_letter_routing_key,
            )

            self.logger.info("Dead letter queue consumer created")

        except Exception as e:
            self.logger.exception(f"Failed to create dead letter consumer: {e}")

    async def get_dead_letter_messages(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get messages from dead letter queue."""
        try:
            dlq_name = self._settings.dead_letter_routing_key
            if dlq_name in self._queues:
                dlq = self._queues[dlq_name]

                messages = []
                for _ in range(limit):
                    message = await dlq.get(no_ack=True)
                    if message is None:
                        break

                    messages.append(
                        {
                            "message_id": message.message_id,
                            "correlation_id": message.correlation_id,
                            "body": message.body.decode(),
                            "headers": dict(message.headers) if message.headers else {},
                            "timestamp": message.timestamp,
                        },
                    )

                return messages

            return []

        except Exception as e:
            self.logger.exception(f"Failed to get dead letter messages: {e}")
            return []


# Factory function
def create_rabbitmq_queue(
    settings: RabbitMQQueueSettings | None = None,
) -> RabbitMQQueue:
    """Create a RabbitMQ queue instance.

    Args:
        settings: Queue settings

    Returns:
        RabbitMQQueue instance
    """
    return RabbitMQQueue(settings)
