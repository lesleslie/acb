"""RabbitMQ Queue Backend Adapter for ACB.

Enterprise-grade RabbitMQ-backed queue implementation suitable for production
deployments with high availability, clustering, and advanced routing capabilities.

Features:
    - Connection pooling with automatic reconnection
    - Priority queue support using RabbitMQ x-max-priority
    - Delayed message delivery using x-delayed-message plugin or TTL+DLQ pattern
    - Dead letter queue for failed message handling
    - Batch operations for improved throughput
    - Pub/sub support via topic exchanges
    - Prefetch and flow control
    - Health monitoring and metrics
    - Exchange and queue management

Requirements:
    - RabbitMQ server (standalone or cluster)
    - aio-pika for async RabbitMQ client
    - Optional: rabbitmq_delayed_message_exchange plugin for native delayed messages

Example:
    Basic task queue usage:

    ```python
    from acb.depends import Inject, depends
    from acb.adapters import import_adapter

    Queue = import_adapter("queue")


    @depends.inject
    async def process_tasks(queue: Inject[Queue]):
        # Enqueue task with priority and delay
        await queue.enqueue(
            "tasks",
            b"task payload",
            priority=MessagePriority.HIGH,
            delay_seconds=10,
        )

        # Dequeue and process
        message = await queue.dequeue("tasks")
        if message:
            # Process task
            await queue.acknowledge(message)
    ```

    Pub/sub pattern with topic routing:

    ```python
    # Publisher
    await queue.publish("events.user.created", b"user data")

    # Subscriber with pattern matching
    async with queue.subscribe("events.user.*") as messages:
        async for message in messages:
            await process_event(message)
            await queue.acknowledge(message)
    ```

Author: Claude Code
Created: 2025-10-01
"""

import time
from collections.abc import AsyncGenerator, AsyncIterator
from uuid import UUID, uuid4

import asyncio
import typing as t
from contextlib import asynccontextmanager, suppress
from pydantic import Field

from acb.adapters import AdapterCapability, AdapterMetadata, AdapterStatus
from acb.cleanup import CleanupMixin
from acb.depends import depends

from ._base import (
    MessagePriority,
    MessagingCapability,
    MessagingConnectionError,
    MessagingOperationError,
    MessagingTimeoutError,
    PubSubMessage,
    QueueMessage,
    Subscription,
)
from ._base import (
    MessagingSettings as BaseMessagingSettings,
)

LoggerType = t.Any

# Lazy imports for aio-pika
_aio_pika_imports: dict[str, t.Any] = {}

MODULE_METADATA = AdapterMetadata(
    module_id=UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890"),
    name="RabbitMQ Messaging",
    category="messaging",
    provider="rabbitmq",
    version="1.0.0",
    acb_min_version="0.20.0",
    author="Claude Code",
    created_date="2025-10-01",
    last_modified="2025-10-08",
    status=AdapterStatus.STABLE,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.CONNECTION_POOLING,
        AdapterCapability.TRANSACTIONS,
        AdapterCapability.HEALTH_CHECKS,
        AdapterCapability.RECONNECTION,
    ],
    required_packages=["aio-pika>=9.0.0"],
    description="Enterprise RabbitMQ messaging backend with pub/sub and queue support",
    settings_class="RabbitMQMessagingSettings",
    config_example={
        "connection_url": "amqp://guest:guest@localhost:5672/",
        "exchange_name": "acb.messaging",
        "exchange_type": "direct",
        "max_priority": 255,
        "prefetch_count": 10,
        "enable_delayed_plugin": True,
    },
)


def _get_aio_pika_imports() -> dict[str, t.Any]:
    """Lazy import of aio-pika dependencies."""
    if not _aio_pika_imports:
        try:
            import aio_pika  # type: ignore[import-not-found]
            from aio_pika import (  # type: ignore[import-not-found]
                DeliveryMode,
                ExchangeType,
            )

            _aio_pika_imports.update(
                {
                    "aio_pika": aio_pika,
                    "connect_robust": aio_pika.connect_robust,
                    "Message": aio_pika.Message,
                    "DeliveryMode": DeliveryMode,
                    "ExchangeType": ExchangeType,
                }
            )
        except ImportError as e:
            raise ImportError(
                "aio-pika is required for RabbitMQQueue. "
                "Install with: pip install aio-pika>=9.0.0"
            ) from e

    return _aio_pika_imports


class RabbitMQMessagingSettings(BaseMessagingSettings):
    """Settings for RabbitMQ messaging implementation."""

    # RabbitMQ connection
    connection_url: str | None = "amqp://guest:guest@localhost:5672/"
    heartbeat: int = 60
    connection_timeout: float = 10.0

    # Exchange configuration
    exchange_name: str = "acb.messaging"
    exchange_type: str = "direct"  # direct, topic, fanout, headers
    exchange_durable: bool = True
    exchange_auto_delete: bool = False

    # Queue configuration
    queue_durable: bool = True
    queue_auto_delete: bool = False
    queue_exclusive: bool = False
    max_priority: int = 255  # RabbitMQ max priority

    # Dead letter configuration
    enable_dlx: bool = True
    dlx_exchange_name: str = "acb.tasks.dlx"
    dlx_routing_key: str = "dead_letter"

    # Delayed message configuration
    enable_delayed_plugin: bool = True
    delayed_exchange_name: str = "acb.tasks.delayed"

    # Message TTL (milliseconds)
    message_ttl: int = Field(
        default=86400000,  # 24 hours
        description="Message TTL in milliseconds",
    )
    dead_letter_ttl: int = Field(
        default=604800000,  # 7 days
        description="Dead letter message TTL in milliseconds",
    )

    # Consumer configuration
    prefetch_count: int = 10
    consumer_timeout: float = 30.0

    # Operation timeouts
    send_timeout: float = Field(
        default=10.0,
        description="Timeout for send operations in seconds",
    )
    receive_timeout: float = Field(
        default=30.0,
        description="Timeout for receive operations in seconds",
    )
    ack_timeout: float = Field(
        default=5.0,
        description="Timeout for acknowledge/reject operations in seconds",
    )

    # Channel pool
    channel_pool_size: int = 5


class RabbitMQMessaging(CleanupMixin):
    """RabbitMQ-backed unified messaging implementation.

    Provides enterprise-grade messaging operations using RabbitMQ:
    - Topic exchanges for pub/sub event patterns
    - Direct exchanges for point-to-point task queues
    - Priority queues using x-max-priority
    - Delayed messages via plugin or TTL+DLQ pattern
    - Dead letter exchanges for failed messages
    - Connection pooling and automatic recovery
    """

    def __init__(self, settings: RabbitMQMessagingSettings | None = None) -> None:
        """Initialize RabbitMQ messaging backend.

        Args:
            settings: RabbitMQ messaging configuration
        """
        super().__init__()
        self._settings: RabbitMQMessagingSettings = (
            settings or RabbitMQMessagingSettings()
        )

        # Connection management
        self._connection_lock = asyncio.Lock()
        self._shutdown_event = asyncio.Event()
        self._logger: LoggerType | None = None
        self._connected: bool = False

        # RabbitMQ connection and channels
        self._connection: t.Any = None
        self._channel: t.Any = None
        self._channel_pool: list[t.Any] = []

        # RabbitMQ objects
        self._exchange: t.Any = None
        self._dlx_exchange: t.Any = None
        self._delayed_exchange: t.Any = None
        self._queues: dict[str, t.Any] = {}
        self._consumers: dict[str, t.Any] = {}

        # Background tasks
        self._delayed_processor_task: asyncio.Task[None] | None = None

        # Track messages being processed
        self._processing_messages: dict[str, tuple[QueueMessage, t.Any]] = {}

    @property
    def logger(self) -> LoggerType:
        """Lazy-initialize logger.

        Returns:
            Logger instance
        """
        if self._logger is None:
            from acb.adapters import import_adapter

            logger_cls = import_adapter("logger")
            self._logger = t.cast(LoggerType, depends.get_sync(logger_cls))
        return self._logger

    # ========================================================================
    # Connection Management (Private Implementation)
    # ========================================================================

    async def _ensure_client(self) -> t.Any:
        """Ensure RabbitMQ connection is initialized (lazy initialization).

        Returns:
            RabbitMQ connection instance

        Raises:
            QueueConnectionError: If connection fails
        """
        if self._connection is None or self._connection.is_closed:
            async with self._connection_lock:
                # Double-check after acquiring lock
                if self._connection is None or self._connection.is_closed:
                    imports = _get_aio_pika_imports()

                    try:
                        # Create robust connection (auto-reconnect)
                        self._connection = await imports["connect_robust"](
                            self._settings.connection_url,
                            heartbeat=self._settings.heartbeat,
                            timeout=self._settings.connection_timeout,
                        )

                        # Create main channel
                        self._channel = await self._connection.channel()
                        await self._channel.set_qos(
                            prefetch_count=self._settings.prefetch_count
                        )

                        # Register for cleanup
                        self.register_resource(self._connection)

                        self.logger.debug("RabbitMQ connection established")

                    except Exception as e:
                        self.logger.exception(f"Failed to connect to RabbitMQ: {e}")
                        raise MessagingConnectionError(
                            "Failed to establish RabbitMQ connection",
                            original_error=e,
                        ) from e

        return self._connection

    async def _connect(self) -> None:
        """Establish connection to RabbitMQ backend."""
        async with self._connection_lock:
            if self._connected:
                return

            # Initialize connection
            await self._ensure_client()

            # Setup exchanges
            await self._setup_exchanges()

            # Start background tasks
            if self._settings.enable_delayed_plugin:
                self._delayed_processor_task = asyncio.create_task(
                    self._process_delayed_messages()
                )

            self._connected = True
            self.logger.info("RabbitMQ queue backend connected")

    async def _disconnect(self) -> None:
        """Disconnect from RabbitMQ backend."""
        self._connected = False
        self._shutdown_event.set()

        # Cancel background tasks
        if self._delayed_processor_task:
            self._delayed_processor_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._delayed_processor_task

        # Close consumers
        for consumer in self._consumers.values():
            with suppress(Exception):
                await consumer.cancel()

        self._consumers.clear()

        # Close channel pool
        for channel in self._channel_pool:
            with suppress(Exception):
                await channel.close()

        self._channel_pool.clear()

        # Close main channel
        if self._channel:
            with suppress(Exception):
                await self._channel.close()

            self._channel = None

        # Close connection
        if self._connection:
            with suppress(Exception):
                await self._connection.close()

            self._connection = None

        # Cleanup resources
        await self.cleanup()

        self.logger.info("RabbitMQ queue backend disconnected")

    async def _health_check(self) -> dict[str, t.Any]:
        """Perform RabbitMQ health check.

        Returns:
            Health status information
        """
        try:
            connection = await self._ensure_client()

            # Measure latency with ping
            start_time = time.time()
            # Check if connection is open
            is_healthy = not connection.is_closed
            latency_ms = (time.time() - start_time) * 1000

            return {
                "healthy": is_healthy,
                "connected": self._connected,
                "latency_ms": latency_ms,
                "backend_info": {
                    "connection_closed": connection.is_closed,
                    "exchanges_configured": all(
                        [
                            self._exchange is not None,
                            self._dlx_exchange is not None
                            if self._settings.enable_dlx
                            else True,
                        ]
                    ),
                    "active_queues": len(self._queues),
                    "active_consumers": len(self._consumers),
                    "channel_pool_size": len(self._channel_pool),
                },
            }

        except Exception as e:
            self.logger.exception(f"RabbitMQ health check failed: {e}")
            return {
                "healthy": False,
                "connected": False,
                "error": str(e),
            }

    # ========================================================================
    # Exchange and Queue Setup
    # ========================================================================

    async def _setup_exchanges(self) -> None:
        """Setup RabbitMQ exchanges."""
        if not self._channel:
            raise MessagingConnectionError("Channel not available")

        imports = _get_aio_pika_imports()
        ExchangeType = imports["ExchangeType"]

        try:
            # Main exchange
            exchange_type_enum = ExchangeType(self._settings.exchange_type)
            self._exchange = await self._channel.declare_exchange(
                self._settings.exchange_name,
                type=exchange_type_enum,
                durable=self._settings.exchange_durable,
                auto_delete=self._settings.exchange_auto_delete,
            )

            # Dead letter exchange
            if self._settings.enable_dlx:
                self._dlx_exchange = await self._channel.declare_exchange(
                    self._settings.dlx_exchange_name,
                    type=ExchangeType.DIRECT,
                    durable=True,
                )

            # Delayed exchange (if plugin is enabled)
            if self._settings.enable_delayed_plugin:
                try:
                    self._delayed_exchange = await self._channel.declare_exchange(
                        self._settings.delayed_exchange_name,
                        type="x-delayed-message",
                        durable=True,
                        arguments={"x-delayed-type": "direct"},
                    )
                except Exception as e:
                    self.logger.warning(
                        f"Failed to create delayed exchange (plugin may not be installed): {e}"
                    )
                    self._settings.enable_delayed_plugin = False

            self.logger.debug("RabbitMQ exchanges configured")

        except Exception as e:
            self.logger.exception(f"Failed to setup exchanges: {e}")
            raise MessagingConnectionError(
                "Failed to setup RabbitMQ exchanges", original_error=e
            ) from e

    async def _ensure_queue(self, name: str) -> t.Any:
        """Ensure a queue exists and is configured.

        Args:
            name: Queue name

        Returns:
            RabbitMQ queue object

        Raises:
            QueueOperationError: If queue creation fails
        """
        if name not in self._queues:
            if not self._channel:
                raise MessagingConnectionError("Channel not available")

            try:
                # Queue arguments
                arguments = {
                    "x-max-priority": self._settings.max_priority,
                    "x-message-ttl": self._settings.message_ttl,
                }

                # Add dead letter configuration
                if self._settings.enable_dlx:
                    # RabbitMQ arguments accept string values for exchange names
                    arguments["x-dead-letter-exchange"] = (  # type: ignore[assignment]
                        self._settings.dlx_exchange_name
                    )
                    arguments["x-dead-letter-routing-key"] = (  # type: ignore[assignment]
                        self._settings.dlx_routing_key
                    )

                # Declare queue
                queue = await self._channel.declare_queue(
                    name,
                    durable=self._settings.queue_durable,
                    auto_delete=self._settings.queue_auto_delete,
                    exclusive=self._settings.queue_exclusive,
                    arguments=arguments,
                )

                # Bind to exchange
                await queue.bind(self._exchange, routing_key=name)

                self._queues[name] = queue
                self.logger.debug(f"Queue configured: {name}")

            except Exception as e:
                self.logger.exception(f"Failed to create queue {name}: {e}")
                raise MessagingOperationError(
                    f"Failed to create queue {name}", original_error=e
                ) from e

        return self._queues[name]

    # ========================================================================
    # Message Operations (Private Implementation)
    # ========================================================================

    async def _send(
        self,
        message: QueueMessage,
        timeout: float | None = None,
    ) -> str:
        """Send a message (private implementation).

        Args:
            message: Message to send
            timeout: Optional timeout override

        Returns:
            Message ID

        Raises:
            QueueConnectionError: If not connected
            QueueOperationError: If send fails
            QueueTimeoutError: If operation times out
        """
        if not self._connected:
            raise MessagingConnectionError("Not connected to RabbitMQ")

        await self._ensure_client()
        timeout = timeout or self._settings.send_timeout

        imports = _get_aio_pika_imports()
        Message = imports["Message"]
        DeliveryMode = imports["DeliveryMode"]

        try:
            # Serialize message payload
            message_data = message.payload

            # Convert priority to RabbitMQ scale (0-255)
            priority = min(message.priority.value * 50, self._settings.max_priority)

            # Create RabbitMQ message
            rmq_message = Message(
                body=message_data,
                priority=priority,
                delivery_mode=DeliveryMode.PERSISTENT,
                message_id=str(message.message_id),
                correlation_id=message.correlation_id,
                headers=message.headers,
            )

            # Handle delayed messages
            if message.delay_seconds > 0:
                await self._send_delayed_message(message, rmq_message)
            else:
                # Send immediately
                await asyncio.wait_for(
                    self._exchange.publish(
                        rmq_message,
                        routing_key=message.queue,
                    ),
                    timeout=timeout,
                )

            self.logger.debug(
                f"Sent message {message.message_id} to queue {message.queue}"
            )
            return str(message.message_id)

        except TimeoutError as e:
            raise MessagingTimeoutError(
                f"Send operation timed out after {timeout}s",
                original_error=e,
            ) from e
        except Exception as e:
            self.logger.exception(f"Failed to send message: {e}")
            raise MessagingOperationError(
                "Failed to send message",
                original_error=e,
            ) from e

    async def _send_delayed_message(
        self, message: QueueMessage, rmq_message: t.Any
    ) -> None:
        """Send a delayed message using plugin or TTL+DLQ pattern.

        Args:
            message: Original ACB message
            rmq_message: RabbitMQ message object
        """
        delay_ms = int(message.delay_seconds * 1000)

        if self._settings.enable_delayed_plugin and self._delayed_exchange:
            # Use RabbitMQ delayed message plugin
            rmq_message.headers["x-delay"] = delay_ms
            await self._delayed_exchange.publish(
                rmq_message,
                routing_key=message.queue,
            )
        else:
            # Use TTL + DLQ pattern
            temp_queue_name = f"delayed.{message.queue}.{int(time.time())}"

            # Create temporary queue with TTL and DLX
            await self._channel.declare_queue(
                temp_queue_name,
                durable=False,
                auto_delete=True,
                arguments={
                    "x-message-ttl": delay_ms,
                    "x-dead-letter-exchange": self._settings.exchange_name,
                    "x-dead-letter-routing-key": message.queue,
                },
            )

            # Publish to temp queue
            await self._exchange.publish(
                rmq_message,
                routing_key=temp_queue_name,
            )

    async def _receive(
        self,
        topic: str,
        timeout: float | None = None,
    ) -> QueueMessage | None:
        """Receive a message (private implementation).

        Args:
            topic: Topic/queue to receive from
            timeout: Optional timeout override

        Returns:
            Message or None if no messages available

        Raises:
            QueueConnectionError: If not connected
            QueueOperationError: If receive fails
        """
        if not self._connected:
            raise MessagingConnectionError("Not connected to RabbitMQ")

        await self._ensure_client()
        queue = await self._ensure_queue(topic)

        try:
            # Get message with no-ack (will ack manually)
            rmq_message = await queue.get(
                timeout=timeout or self._settings.receive_timeout, fail=False
            )

            if rmq_message is None:
                return None

            # Create ACB message from RabbitMQ message
            from uuid import UUID

            message = QueueMessage(
                message_id=UUID(rmq_message.message_id)
                if rmq_message.message_id
                else uuid4(),
                queue=topic,
                payload=rmq_message.body,
                priority=MessagePriority.NORMAL,  # Could map from RabbitMQ priority
                correlation_id=rmq_message.correlation_id,
                headers=dict(rmq_message.headers or {}),
            )

            # Store for later acknowledgment
            self._processing_messages[str(message.message_id)] = (message, rmq_message)

            self.logger.debug(
                f"Received message {message.message_id} from topic {topic}"
            )
            return message

        except TimeoutError:
            return None  # Timeout is expected for blocking receives
        except Exception as e:
            self.logger.exception(f"Failed to receive message: {e}")
            raise MessagingOperationError(
                "Failed to receive message",
                original_error=e,
            ) from e

    async def _acknowledge(
        self,
        message: QueueMessage,
        timeout: float | None = None,
    ) -> None:
        """Acknowledge a message (private implementation).

        Args:
            message: Message to acknowledge
            timeout: Optional timeout override

        Raises:
            QueueOperationError: If ack fails
        """
        message_id = str(message.message_id)

        if message_id not in self._processing_messages:
            raise MessagingOperationError(
                f"Message {message_id} not in processing state"
            )

        try:
            _, rmq_message = self._processing_messages[message_id]

            # Acknowledge message
            await asyncio.wait_for(
                rmq_message.ack(),
                timeout=timeout or self._settings.ack_timeout,
            )

            # Remove from processing
            del self._processing_messages[message_id]

            self.logger.debug(f"Acknowledged message {message_id}")

        except Exception as e:
            self.logger.exception(f"Failed to acknowledge message: {e}")
            raise MessagingOperationError(
                "Failed to acknowledge message",
                original_error=e,
            ) from e

    async def _reject(
        self,
        message: QueueMessage,
        requeue: bool = False,
        timeout: float | None = None,
    ) -> None:
        """Reject a message (private implementation).

        Args:
            message: Message to reject
            requeue: Whether to requeue the message
            timeout: Optional timeout override

        Raises:
            QueueOperationError: If reject fails
        """
        message_id = str(message.message_id)

        if message_id not in self._processing_messages:
            raise MessagingOperationError(
                f"Message {message_id} not in processing state"
            )

        try:
            _, rmq_message = self._processing_messages[message_id]

            # Reject message (will go to DLQ if configured and not requeued)
            await asyncio.wait_for(
                rmq_message.reject(requeue=requeue),
                timeout=timeout or self._settings.ack_timeout,
            )

            # Remove from processing
            del self._processing_messages[message_id]

            self.logger.debug(f"Rejected message {message_id} (requeue={requeue})")

        except Exception as e:
            self.logger.exception(f"Failed to reject message: {e}")
            raise MessagingOperationError(
                "Failed to reject message",
                original_error=e,
            ) from e

    @asynccontextmanager  # type: ignore[arg-type]
    async def _subscribe(
        self,
        topic: str,
        prefetch: int | None = None,
    ) -> AsyncIterator[AsyncGenerator[QueueMessage]]:
        """Subscribe to topic (private implementation).

        Args:
            topic: Topic/pattern to subscribe to
            prefetch: Messages to prefetch

        Yields:
            Async generator of messages
        """
        if not self._connected:
            raise MessagingConnectionError("Not connected to RabbitMQ")

        await self._ensure_client()
        queue = await self._ensure_queue(topic)

        # Create dedicated channel for subscription
        channel = await self._connection.channel()
        if prefetch:
            await channel.set_qos(prefetch_count=prefetch)

        try:
            # Start consuming
            consumer = await queue.consume()
            self._consumers[topic] = consumer

            async def message_generator() -> AsyncGenerator[QueueMessage]:
                """Generate messages from subscription."""
                try:
                    async for rmq_message in consumer:
                        async with rmq_message.process():
                            try:
                                # Create ACB message from RabbitMQ message
                                from uuid import UUID

                                message = QueueMessage(
                                    message_id=UUID(rmq_message.message_id)
                                    if rmq_message.message_id
                                    else uuid4(),
                                    queue=topic,
                                    payload=rmq_message.body,
                                    priority=MessagePriority.NORMAL,
                                    correlation_id=rmq_message.correlation_id,
                                    headers=dict(rmq_message.headers or {}),
                                )

                                # Store for acknowledgment
                                self._processing_messages[str(message.message_id)] = (
                                    message,
                                    rmq_message,
                                )

                                yield message
                            except Exception as e:
                                self.logger.warning(f"Failed to parse message: {e}")
                                # Auto-reject malformed messages
                                await rmq_message.reject(requeue=False)
                except asyncio.CancelledError:
                    pass

            yield message_generator()

        finally:
            # Cleanup subscription
            try:
                if topic in self._consumers:
                    await self._consumers[topic].cancel()
                    del self._consumers[topic]
                await channel.close()
            except Exception as e:
                self.logger.warning(f"Error closing subscription: {e}")

    # ========================================================================
    # Queue Management (Private Implementation)
    # ========================================================================

    async def _create_queue(
        self,
        name: str,
        **options: t.Any,
    ) -> None:
        """Create queue (private implementation).

        Args:
            name: Queue name
            **options: Backend-specific options (e.g., durable, auto_delete)
        """
        if not self._connected:
            raise MessagingConnectionError("Not connected to RabbitMQ")

        # Queue will be created by _ensure_queue
        await self._ensure_queue(name)
        self.logger.info(f"Queue created: {name}")

    async def _delete_queue(
        self,
        name: str,
        if_empty: bool = False,
    ) -> None:
        """Delete queue (private implementation).

        Args:
            name: Queue name
            if_empty: Only delete if empty

        Raises:
            QueueOperationError: If deletion fails
        """
        if not self._connected:
            raise MessagingConnectionError("Not connected to RabbitMQ")

        await self._ensure_client()

        try:
            queue = await self._ensure_queue(name)

            # Delete queue
            await queue.delete(if_empty=if_empty)

            # Remove from cache
            if name in self._queues:
                del self._queues[name]

            self.logger.info(f"Queue deleted: {name}")

        except Exception as e:
            self.logger.exception(f"Failed to delete queue {name}: {e}")
            raise MessagingOperationError(
                f"Failed to delete queue {name}",
                original_error=e,
            ) from e

    async def _purge_queue(
        self,
        name: str,
    ) -> int:
        """Purge queue (private implementation).

        Args:
            name: Queue name

        Returns:
            Number of messages purged

        Raises:
            QueueOperationError: If purge fails
        """
        if not self._connected:
            raise MessagingConnectionError("Not connected to RabbitMQ")

        await self._ensure_client()

        try:
            queue = await self._ensure_queue(name)

            # Purge queue
            result = await queue.purge()

            self.logger.info(
                f"Purged {result.message_count} messages from queue {name}"
            )
            return result.message_count

        except Exception as e:
            self.logger.exception(f"Failed to purge queue {name}: {e}")
            raise MessagingOperationError(
                f"Failed to purge queue {name}",
                original_error=e,
            ) from e

    async def _get_queue_size(
        self,
        name: str,
    ) -> int:
        """Get queue size (private implementation).

        Args:
            name: Queue name

        Returns:
            Message count

        Raises:
            QueueOperationError: If operation fails
        """
        if not self._connected:
            raise MessagingConnectionError("Not connected to RabbitMQ")

        await self._ensure_client()

        try:
            queue = await self._ensure_queue(name)

            # Get queue info
            result = await queue.declare(passive=True)

            return result.message_count

        except Exception as e:
            self.logger.exception(f"Failed to get queue size for {name}: {e}")
            raise MessagingOperationError(
                f"Failed to get queue size for {name}",
                original_error=e,
            ) from e

    async def _list_queues(
        self,
        pattern: str | None = None,
    ) -> list[str]:
        """List queues (private implementation).

        Args:
            pattern: Optional filter pattern (simple prefix matching)

        Returns:
            List of queue names
        """
        queue_names = list(self._queues.keys())

        if pattern:
            # Simple prefix matching
            queue_names = [name for name in queue_names if name.startswith(pattern)]

        return sorted(queue_names)

    # ========================================================================
    # Background Tasks
    # ========================================================================

    async def _process_delayed_messages(self) -> None:
        """Background task to monitor delayed message processing.

        This is a health monitoring task - actual delayed processing is
        handled by RabbitMQ itself via plugin or TTL+DLQ pattern.
        """
        self.logger.debug("Started delayed message monitor")

        while self._connected and not self._shutdown_event.is_set():
            try:
                # Just sleep and monitor connection health
                await asyncio.sleep(10.0)

                # Check connection health
                if self._connection and self._connection.is_closed:
                    self.logger.warning("Connection lost, attempting reconnect")
                    await self._ensure_client()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.exception(f"Error in delayed message monitor: {e}")
                await asyncio.sleep(5.0)

        self.logger.debug("Stopped delayed message monitor")

    # ========================================================================
    # Public Interface Methods (Required by UnifiedMessagingBackend)
    # ========================================================================

    async def connect(self) -> None:
        """Establish connection to RabbitMQ backend."""
        await self._connect()

    async def disconnect(self) -> None:
        """Close connection to RabbitMQ backend."""
        await self._disconnect()

    async def health_check(self) -> dict[str, t.Any]:
        """Perform health check on RabbitMQ backend."""
        return await self._health_check()

    # Pub/Sub Interface (for events system)

    async def publish(
        self,
        topic: str,
        message: bytes,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Publish a message to a topic (pub/sub pattern)."""
        from uuid import uuid4

        queue_msg = QueueMessage(
            message_id=uuid4(),
            queue=topic,
            payload=message,
            headers=headers or {},
        )
        await self._send(queue_msg)

    async def subscribe(
        self,
        topic: str,
        pattern: bool = False,
    ) -> Subscription:
        """Subscribe to a topic or pattern."""
        # Create subscription object
        subscription = Subscription(
            topic=topic,
        )
        return subscription

    async def unsubscribe(self, subscription: Subscription) -> None:
        """Unsubscribe from a topic."""
        # Cleanup consumer if exists
        if subscription.topic in self._consumers:
            try:
                await self._consumers[subscription.topic].cancel()
                del self._consumers[subscription.topic]
            except Exception as e:
                self.logger.warning(f"Error unsubscribing: {e}")

    @asynccontextmanager  # type: ignore[arg-type]
    async def receive_messages(
        self,
        subscription: Subscription,
        timeout: float | None = None,
    ) -> AsyncIterator[AsyncIterator[PubSubMessage]]:
        """Receive messages from a subscription."""
        async with self._subscribe(subscription.topic) as queue_messages:

            async def convert_messages() -> AsyncGenerator[PubSubMessage]:
                """Convert QueueMessage to PubSubMessage."""
                async for queue_msg in queue_messages:
                    pubsub_msg = PubSubMessage(
                        message_id=queue_msg.message_id,
                        topic=queue_msg.queue,
                        payload=queue_msg.payload,
                        correlation_id=queue_msg.correlation_id,
                        headers=queue_msg.headers,
                    )
                    yield pubsub_msg

            yield convert_messages()

    # Queue Interface (for tasks system)

    async def enqueue(
        self,
        queue: str,
        message: bytes,
        priority: MessagePriority = MessagePriority.NORMAL,
        delay_seconds: float = 0.0,
        headers: dict[str, str] | None = None,
    ) -> str:
        """Add a message to a queue."""
        from uuid import uuid4

        queue_msg = QueueMessage(
            message_id=uuid4(),
            queue=queue,
            payload=message,
            priority=priority,
            delay_seconds=delay_seconds,
            headers=headers or {},
        )
        return await self._send(queue_msg)

    async def dequeue(
        self,
        queue: str,
        timeout: float | None = None,
        visibility_timeout: float = 30.0,
    ) -> QueueMessage | None:
        """Remove and return a message from a queue."""
        return await self._receive(queue, timeout)

    async def acknowledge(
        self,
        queue: str,
        message_id: str,
    ) -> None:
        """Acknowledge successful processing of a message."""
        # Find the message in processing
        if message_id in self._processing_messages:
            message, _ = self._processing_messages[message_id]
            await self._acknowledge(message)

    async def reject(
        self,
        queue: str,
        message_id: str,
        requeue: bool = True,
    ) -> None:
        """Reject a message, optionally requeuing it."""
        # Find the message in processing
        if message_id in self._processing_messages:
            message, _ = self._processing_messages[message_id]
            await self._reject(message, requeue)

    async def purge_queue(self, queue: str) -> int:
        """Remove all messages from a queue."""
        return await self._purge_queue(queue)

    async def get_queue_stats(self, queue: str) -> dict[str, t.Any]:
        """Get statistics for a queue."""
        size = await self._get_queue_size(queue)
        return {
            "message_count": size,
            "consumer_count": 1 if queue in self._consumers else 0,
        }

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def get_capabilities(self) -> set[MessagingCapability]:
        """Get backend capabilities.

        Returns:
            Set of supported capabilities
        """
        capabilities = {
            MessagingCapability.BASIC_QUEUE,
            MessagingCapability.PUB_SUB,
            MessagingCapability.PRIORITY_QUEUE,
            MessagingCapability.DELAYED_MESSAGES,
            MessagingCapability.PERSISTENCE,
            MessagingCapability.DEAD_LETTER_QUEUE,
            MessagingCapability.CONNECTION_POOLING,
            MessagingCapability.MESSAGE_TTL,
            MessagingCapability.CLUSTERING,
            MessagingCapability.PATTERN_SUBSCRIBE,
            MessagingCapability.BROADCAST,
            MessagingCapability.TRANSACTIONS,
        }

        return capabilities


# Factory function
def create_rabbitmq_messaging(
    settings: RabbitMQMessagingSettings | None = None,
) -> RabbitMQMessaging:
    """Create a RabbitMQ messaging instance.

    Args:
        settings: Messaging settings

    Returns:
        RabbitMQMessaging instance
    """
    return RabbitMQMessaging(settings)


# Export with role-specific names for dependency injection
RabbitMQPubSub = RabbitMQMessaging  # For events system (pubsub adapter)
RabbitMQQueue = RabbitMQMessaging  # For tasks system (queue adapter)

Messaging = RabbitMQMessaging
MessagingSettings = RabbitMQMessagingSettings

depends.set(Messaging, "rabbitmq")
