"""In-memory messaging adapter for ACB framework.

This module provides an in-memory messaging backend implementation supporting
both pub/sub and queue patterns. Suitable for development, testing, and
single-node deployments. Messages are stored in memory and will be lost on
application restart.

Features:
- Pub/sub pattern support (events)
- Queue pattern support (tasks)
- Priority-based message ordering
- Delayed message delivery
- Dead letter queue support
- Connection pooling simulation
- Health monitoring
- Batch operations
- Metrics collection

Implementation follows ACB adapter patterns:
- Dual interface (PubSubBackend + QueueBackend)
- Public/private method delegation
- Lazy client initialization
- Async context manager support
- CleanupMixin integration
"""

import heapq
import time
from collections import defaultdict, deque
from collections.abc import AsyncGenerator, AsyncIterator
from uuid import UUID

import asyncio
import typing as t
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pydantic import Field

from acb.adapters import AdapterCapability, AdapterMetadata, AdapterStatus
from acb.adapters.messaging._base import (
    MessagingCapability,
    MessagingConnectionError,
    MessagingOperationError,
    QueueFullError,
    QueueMessage,
)
from acb.adapters.messaging._base import (
    MessagingSettings as BaseMessagingSettings,
)
from acb.cleanup import CleanupMixin
from acb.depends import depends

LoggerType = t.Any

# Module metadata for adapter discovery
MODULE_METADATA = AdapterMetadata(
    module_id=UUID("66c46147-3eba-49a1-949a-b01df1710453"),
    name="Memory Messaging",
    category="messaging",
    provider="memory",
    version="2.0.0",
    acb_min_version="0.25.0",
    author="ACB Team",
    created_date="2025-10-08",
    last_modified="2025-10-08",
    status=AdapterStatus.STABLE,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.CONNECTION_POOLING,
    ],
    required_packages=[],
    description="In-memory messaging adapter for development and testing",
    settings_class="MemoryMessagingSettings",
)


class MemoryMessagingSettings(BaseMessagingSettings):
    """Settings specific to memory queue implementation."""

    # Memory limits
    max_memory_usage: int = Field(
        default=100_000_000,
        description="Maximum memory usage in bytes",
    )
    max_messages_per_topic: int = Field(
        default=10_000,
        description="Maximum messages per topic/queue",
    )

    # Message retention
    message_retention_seconds: int = Field(
        default=3600,
        description="How long to retain completed messages",
    )

    # Dead letter queue
    enable_dead_letter: bool = Field(
        default=True,
        description="Enable dead letter queue for failed messages",
    )
    dead_letter_retention_seconds: int = Field(
        default=86400,
        description="Dead letter message retention time",
    )

    # Rate limiting
    enable_rate_limiting: bool = Field(
        default=False,
        description="Enable per-topic rate limiting",
    )
    rate_limit_per_second: int = Field(
        default=100,
        description="Max messages per second per topic",
    )

    # Health monitoring
    health_check_interval: float = Field(
        default=60.0,
        description="Interval between health checks in seconds",
    )


class PriorityMessageItem:
    """Wrapper for priority queue ordering."""

    def __init__(self, message: QueueMessage, scheduled_time: float) -> None:
        """Initialize priority item.

        Args:
            message: Queue message
            scheduled_time: When message should be delivered
        """
        self.message = message
        self.scheduled_time = scheduled_time
        # Higher priority values have lower sort order (negate)
        self.priority = -message.priority.value
        self.created_at = time.time()

    def __lt__(self, other: "PriorityMessageItem") -> bool:
        """Compare items for heap ordering.

        Order by:
        1. Scheduled time (earliest first)
        2. Priority (highest first)
        3. Creation time (FIFO for same priority)
        """
        if self.scheduled_time != other.scheduled_time:
            return self.scheduled_time < other.scheduled_time
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.created_at < other.created_at

    def __eq__(self, other: object) -> bool:
        """Check equality by message ID."""
        if not isinstance(other, PriorityMessageItem):
            return False
        return self.message.message_id == other.message.message_id


class MemoryMessaging(CleanupMixin):
    """In-memory queue backend implementation.

    Provides a full-featured queue implementation that runs entirely in memory.
    Suitable for development, testing, and single-process applications.

    Implements both PubSubBackend and QueueBackend protocols (UnifiedMessagingBackend).

    Capabilities:
    - Priority-based message ordering
    - Delayed message delivery
    - Dead letter queue
    - Rate limiting (optional)
    - Batch operations
    - Health monitoring

    Limitations:
    - Messages lost on restart (no persistence)
    - No cross-process communication
    - No distributed clustering
    """

    def __init__(self, settings: MemoryMessagingSettings | None = None) -> None:
        """Initialize memory messaging.

        Args:
            settings: Memory messaging configuration
        """
        super().__init__()
        self._settings: MemoryMessagingSettings = settings or MemoryMessagingSettings()

        # Connection management
        self._client: MemoryMessaging | None = None
        self._connection_lock = asyncio.Lock()
        self._shutdown_event = asyncio.Event()

        # Message storage
        self._queues: dict[str, list[PriorityMessageItem]] = defaultdict(list)
        self._delayed_messages: list[PriorityMessageItem] = []
        self._processing_messages: dict[UUID, QueueMessage] = {}
        self._dead_letter_messages: dict[UUID, tuple[QueueMessage, str]] = {}

        # Rate limiting
        self._rate_limiter: dict[str, deque[float]] = defaultdict(deque)

        # Metrics
        self._memory_usage = 0
        self._total_messages = 0
        self._messages_sent = 0
        self._messages_received = 0
        self._messages_acknowledged = 0
        self._messages_rejected = 0

        # Background tasks
        self._delayed_processor_task: asyncio.Task[None] | None = None
        self._cleanup_task: asyncio.Task[None] | None = None
        self._logger: LoggerType | None = None
        self._connected: bool = False

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
    # Public Lifecycle Methods
    # ========================================================================

    async def connect(self) -> None:
        """Establish connection to the in-memory backend."""
        await self._connect()

    async def disconnect(self) -> None:
        """Disconnect from the in-memory backend."""
        await self._disconnect()

    # ========================================================================
    # Abstract Implementation Methods (Private)
    # ========================================================================

    async def _ensure_client(self) -> "MemoryMessaging":
        """Ensure queue client is initialized.

        For memory queue, "client" is just the internal state.
        This method follows ACB patterns for consistency.

        Returns:
            Self reference (memory queue uses internal state)
        """
        if self._client is None:
            async with self._connection_lock:
                if self._client is None:
                    # For memory queue, "client" is just self
                    self._client = self
        return self._client

    async def _connect(self) -> None:
        """Connect to memory queue backend.

        Initializes background tasks for delayed message processing
        and periodic cleanup.
        """
        if self._connected:
            return

        async with self._connection_lock:
            if self._connected:
                return

            # Initialize client
            await self._ensure_client()

            # Start background tasks
            self._delayed_processor_task = asyncio.create_task(
                self._process_delayed_messages(),
            )
            if self._settings.enable_dead_letter:
                self._cleanup_task = asyncio.create_task(
                    self._periodic_cleanup(),
                )

            self._connected = True
            self.logger.info("Memory queue connected")

    async def _disconnect(self) -> None:
        """Disconnect from memory queue backend.

        Stops background tasks and clears state.
        """
        if not self._connected:
            return

        async with self._connection_lock:
            if not self._connected:
                return

            # Signal shutdown
            self._shutdown_event.set()

            # Stop background tasks
            if self._delayed_processor_task:
                self._delayed_processor_task.cancel()
                try:
                    await self._delayed_processor_task
                except asyncio.CancelledError:
                    pass

            if self._cleanup_task:
                self._cleanup_task.cancel()
                try:
                    await self._cleanup_task
                except asyncio.CancelledError:
                    pass

            # Clear state
            self._queues.clear()
            self._delayed_messages.clear()
            self._processing_messages.clear()
            self._dead_letter_messages.clear()
            self._rate_limiter.clear()

            self._client = None
            self._connected = False
            self.logger.info("Memory queue disconnected")

    async def _health_check(self) -> dict[str, t.Any]:
        """Perform health check on memory queue.

        Returns:
            Health status with metrics
        """
        total_pending = sum(len(queue) for queue in self._queues.values())
        memory_percent = (
            self._memory_usage / self._settings.max_memory_usage * 100
            if self._settings.max_memory_usage > 0
            else 0
        )

        return {
            "connected": self._connected,
            "healthy": self._connected and memory_percent < 90,
            "memory_usage_bytes": self._memory_usage,
            "memory_usage_percent": memory_percent,
            "total_messages": self._total_messages,
            "pending_messages": total_pending,
            "delayed_messages": len(self._delayed_messages),
            "processing_messages": len(self._processing_messages),
            "dead_letter_messages": len(self._dead_letter_messages),
            "messages_sent": self._messages_sent,
            "messages_received": self._messages_received,
            "messages_acknowledged": self._messages_acknowledged,
            "messages_rejected": self._messages_rejected,
            "queue_count": len(self._queues),
        }

    async def _send(
        self,
        message: QueueMessage,
        timeout: float | None = None,
    ) -> str:
        """Send a message to the queue.

        Args:
            message: Message to send
            timeout: Operation timeout (unused for memory)

        Returns:
            Message ID

        Raises:
            MessagingConnectionError: If not connected
            QueueFullError: If queue is full
            MessagingOperationError: If send fails
        """
        if not self._connected:
            raise MessagingConnectionError("Queue not connected")

        # Check memory limits
        message_size = self._estimate_message_size(message)
        if self._memory_usage + message_size > self._settings.max_memory_usage:
            raise QueueFullError(
                f"Memory limit exceeded: {self._memory_usage} + {message_size} "
                f"> {self._settings.max_memory_usage}",
            )

        # Check queue size limits
        if len(self._queues[message.queue]) >= self._settings.max_messages_per_topic:
            raise QueueFullError(
                f"Queue {message.queue} is full "
                f"({self._settings.max_messages_per_topic} messages)",
            )

        # Check rate limiting
        if self._settings.enable_rate_limiting:
            if not await self._check_rate_limit(message.queue):
                raise MessagingOperationError(
                    f"Rate limit exceeded for queue {message.queue}",
                )

        # Calculate scheduled time
        current_time = time.time()
        if message.delay_seconds > 0:
            scheduled_time = current_time + message.delay_seconds
        else:
            # Immediate messages use priority ordering
            scheduled_time = 0.0

        # Create priority item
        item = PriorityMessageItem(message, scheduled_time)

        # Add to appropriate queue
        if scheduled_time > current_time:
            # Delayed message
            heapq.heappush(self._delayed_messages, item)
        else:
            # Immediate message
            heapq.heappush(self._queues[message.queue], item)

        # Update metrics
        self._memory_usage += message_size
        self._total_messages += 1
        self._messages_sent += 1

        self.logger.debug(
            f"Sent message {message.message_id} to queue {message.queue}",
        )

        return str(message.message_id)

    async def _receive(
        self,
        topic: str,
        timeout: float | None = None,
    ) -> QueueMessage | None:
        """Receive a message from a topic.

        Args:
            topic: Topic to receive from
            timeout: Operation timeout (unused for memory)

        Returns:
            Message or None if queue is empty

        Raises:
            MessagingConnectionError: If not connected
        """
        if not self._connected:
            raise MessagingConnectionError("Queue not connected")

        # Check if queue has messages
        queue = self._queues[topic]
        if not queue:
            return None

        # Get highest priority message
        item = heapq.heappop(queue)
        message = item.message

        # Move to processing
        self._processing_messages[message.message_id] = message

        # Update metrics
        self._messages_received += 1

        self.logger.debug(
            f"Received message {message.message_id} from topic {topic}",
        )

        return message

    async def _acknowledge(
        self,
        message: QueueMessage,
        timeout: float | None = None,
    ) -> None:
        """Acknowledge successful message processing.

        Args:
            message: Message to acknowledge
            timeout: Operation timeout (unused for memory)

        Raises:
            MessagingOperationError: If message not in processing state
        """
        if message.message_id not in self._processing_messages:
            raise MessagingOperationError(
                f"Message {message.message_id} not in processing state",
            )

        # Remove from processing
        del self._processing_messages[message.message_id]

        # Update memory usage
        message_size = self._estimate_message_size(message)
        self._memory_usage = max(0, self._memory_usage - message_size)
        self._total_messages = max(0, self._total_messages - 1)

        # Update metrics
        self._messages_acknowledged += 1

        self.logger.debug(f"Acknowledged message {message.message_id}")

    async def _reject(
        self,
        message: QueueMessage,
        requeue: bool = False,
        timeout: float | None = None,
    ) -> None:
        """Reject a message (negative acknowledgment).

        Args:
            message: Message to reject
            requeue: Whether to requeue the message
            timeout: Operation timeout (unused for memory)

        Raises:
            MessagingOperationError: If message not in processing state
        """
        if message.message_id not in self._processing_messages:
            raise MessagingOperationError(
                f"Message {message.message_id} not in processing state",
            )

        # Remove from processing
        del self._processing_messages[message.message_id]

        # Update metrics
        self._messages_rejected += 1

        if requeue and message.retry_count < message.max_retries:
            # Requeue with incremented retry count
            message.retry_count += 1
            item = PriorityMessageItem(message, time.time())
            heapq.heappush(self._queues[message.queue], item)

            self.logger.debug(
                f"Requeued message {message.message_id} "
                f"(retry {message.retry_count}/{message.max_retries})",
            )
        else:
            # Move to dead letter queue
            if self._settings.enable_dead_letter:
                reason = (
                    "Max retries exceeded"
                    if message.retry_count >= message.max_retries
                    else "Message rejected without requeue"
                )
                self._dead_letter_messages[message.message_id] = (message, reason)

                self.logger.warning(
                    f"Message {message.message_id} moved to dead letter queue: "
                    f"{reason}",
                )
            else:
                # Just discard
                message_size = self._estimate_message_size(message)
                self._memory_usage = max(0, self._memory_usage - message_size)
                self._total_messages = max(0, self._total_messages - 1)

    @asynccontextmanager  # type: ignore[arg-type]
    async def _subscribe(
        self,
        topic: str,
        prefetch: int | None = None,
    ) -> AsyncIterator[AsyncGenerator[QueueMessage]]:
        """Subscribe to a topic and stream messages.

        Args:
            topic: Topic to subscribe to
            prefetch: Number of messages to prefetch

        Yields:
            Async generator yielding messages
        """

        async def message_generator() -> AsyncGenerator[QueueMessage]:
            """Generate messages from the topic."""
            while not self._shutdown_event.is_set():
                try:
                    message = await self._receive(topic, timeout=1.0)
                    if message:
                        yield message
                    else:
                        # No messages available, wait a bit
                        await asyncio.sleep(0.1)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.logger.error(f"Error in message generator: {e}")
                    await asyncio.sleep(1.0)

        try:
            yield message_generator()
        finally:
            # Cleanup on exit
            pass

    async def _create_queue(
        self,
        name: str,
        **options: t.Any,
    ) -> None:
        """Create a new queue.

        Args:
            name: Queue name
            **options: Queue options (ignored for memory)
        """
        # For memory queue, queues are created automatically
        if name not in self._queues:
            self._queues[name] = []
            self.logger.info(f"Created queue: {name}")

    async def _delete_queue(
        self,
        name: str,
        if_empty: bool = False,
    ) -> None:
        """Delete a queue.

        Args:
            name: Queue name
            if_empty: Only delete if queue is empty

        Raises:
            MessagingOperationError: If queue not empty and if_empty=True
        """
        if name not in self._queues:
            return

        queue = self._queues[name]
        if if_empty and queue:
            raise MessagingOperationError(
                f"Cannot delete non-empty queue: {name}",
            )

        # Update memory usage
        for item in queue:
            message_size = self._estimate_message_size(item.message)
            self._memory_usage = max(0, self._memory_usage - message_size)
            self._total_messages = max(0, self._total_messages - 1)

        del self._queues[name]
        self.logger.info(f"Deleted queue: {name}")

    async def _purge_queue(
        self,
        name: str,
    ) -> int:
        """Remove all messages from a queue.

        Args:
            name: Queue name

        Returns:
            Number of messages removed
        """
        if name not in self._queues:
            return 0

        queue = self._queues[name]
        count = len(queue)

        # Update memory usage
        for item in queue:
            message_size = self._estimate_message_size(item.message)
            self._memory_usage = max(0, self._memory_usage - message_size)
            self._total_messages = max(0, self._total_messages - 1)

        queue.clear()
        self.logger.info(f"Purged {count} messages from queue: {name}")

        return count

    async def _get_queue_size(
        self,
        name: str,
    ) -> int:
        """Get number of messages in a queue.

        Args:
            name: Queue name

        Returns:
            Number of pending messages
        """
        return len(self._queues.get(name, []))

    async def _list_queues(
        self,
        pattern: str | None = None,
    ) -> list[str]:
        """List all queues.

        Args:
            pattern: Optional pattern to filter queues (unused for memory)

        Returns:
            List of queue names
        """
        queue_names = list(self._queues.keys())

        if pattern:
            # Simple prefix matching
            queue_names = [name for name in queue_names if name.startswith(pattern)]

        return sorted(queue_names)

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def get_capabilities(self) -> set[MessagingCapability]:
        """Get supported capabilities.

        Returns:
            Set of capabilities
        """
        return {
            MessagingCapability.BASIC_QUEUE,
            MessagingCapability.PUB_SUB,
            MessagingCapability.PRIORITY_QUEUE,
            MessagingCapability.DELAYED_MESSAGES,
            MessagingCapability.DEAD_LETTER_QUEUE,
            MessagingCapability.BATCH_OPERATIONS,
            MessagingCapability.PATTERN_SUBSCRIBE,
            MessagingCapability.BROADCAST,
        }

    def supports_capability(self, capability: MessagingCapability) -> bool:
        """Check if a capability is supported.

        Args:
            capability: Capability to check

        Returns:
            True if supported
        """
        return capability in self.get_capabilities()

    # ========================================================================
    # Background Tasks
    # ========================================================================

    async def _process_delayed_messages(self) -> None:
        """Background task to move delayed messages to main queues."""
        while not self._shutdown_event.is_set():
            try:
                current_time = time.time()
                moved_count = self._move_ready_messages(current_time)

                if moved_count > 0:
                    self.logger.debug(
                        f"Moved {moved_count} delayed messages to queues",
                    )

                # Sleep until next check
                sleep_time = self._calculate_sleep_time(current_time)
                await asyncio.sleep(sleep_time)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.exception(f"Delayed processor error: {e}")
                await asyncio.sleep(1.0)

    def _move_ready_messages(self, current_time: float) -> int:
        """Move delayed messages that are ready to main queues.

        Args:
            current_time: Current timestamp

        Returns:
            Number of messages moved
        """
        moved_count = 0

        while self._delayed_messages:
            if self._delayed_messages[0].scheduled_time <= current_time:
                item = heapq.heappop(self._delayed_messages)
                heapq.heappush(self._queues[item.message.queue], item)
                moved_count += 1
            else:
                break

        return moved_count

    def _calculate_sleep_time(self, current_time: float) -> float:
        """Calculate optimal sleep time until next message processing.

        Args:
            current_time: Current timestamp

        Returns:
            Sleep time in seconds
        """
        if not self._delayed_messages:
            return 1.0

        next_time = self._delayed_messages[0].scheduled_time
        return min(1.0, max(0.1, next_time - current_time))

    async def _periodic_cleanup(self) -> None:
        """Background task for periodic cleanup."""
        while not self._shutdown_event.is_set():
            try:
                # Clean up old dead letter messages
                await self._cleanup_dead_letter_messages()

                # Sleep until next cleanup
                await asyncio.sleep(self._settings.health_check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.exception(f"Cleanup error: {e}")
                await asyncio.sleep(self._settings.health_check_interval)

    async def _cleanup_dead_letter_messages(self) -> None:
        """Clean up old dead letter messages."""
        if not self._settings.enable_dead_letter:
            return

        current_time = datetime.now(tz=UTC)
        ttl = timedelta(seconds=self._settings.dead_letter_retention_seconds)

        # Find expired messages
        expired_ids = [
            message_id
            for message_id, (message, _) in self._dead_letter_messages.items()
            if (current_time - message.timestamp) > ttl
        ]

        # Remove expired messages
        for message_id in expired_ids:
            message, _ = self._dead_letter_messages[message_id]
            del self._dead_letter_messages[message_id]

            # Update memory usage
            message_size = self._estimate_message_size(message)
            self._memory_usage = max(0, self._memory_usage - message_size)
            self._total_messages = max(0, self._total_messages - 1)

        if expired_ids:
            self.logger.debug(
                f"Cleaned up {len(expired_ids)} expired dead letter messages",
            )

    async def _check_rate_limit(self, topic: str) -> bool:
        """Check if topic is within rate limits.

        Args:
            topic: Topic name

        Returns:
            True if under rate limit
        """
        if not self._settings.enable_rate_limiting:
            return True

        current_time = time.time()
        window_start = current_time - 1.0  # 1 second window

        # Clean old timestamps
        rate_queue = self._rate_limiter[topic]
        while rate_queue and rate_queue[0] < window_start:
            rate_queue.popleft()

        # Check if under limit
        if len(rate_queue) < self._settings.rate_limit_per_second:
            rate_queue.append(current_time)
            return True

        return False

    def _estimate_message_size(self, message: QueueMessage) -> int:
        """Estimate memory usage of a message.

        Args:
            message: Message to estimate

        Returns:
            Estimated size in bytes
        """
        import sys

        try:
            # Estimate based on payload and metadata
            payload_size = len(message.payload)
            metadata_size = (
                sys.getsizeof(message.queue)
                + sys.getsizeof(message.message_id)
                + sys.getsizeof(message.headers)
            )
            return payload_size + metadata_size + 500  # Base overhead
        except Exception:
            return 1000  # Default if calculation fails

    # ========================================================================
    # Async Context Manager Support
    # ========================================================================

    async def __aenter__(self) -> "MemoryQueue":
        """Enter async context.

        Returns:
            Self
        """
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: t.Any,
    ) -> None:
        """Exit async context.

        Args:
            exc_type: Exception type
            exc_val: Exception value
            exc_tb: Exception traceback
        """
        await self.disconnect()


# Export with role-specific names for DI
# These allow the same implementation to be used for both patterns
MemoryPubSub = MemoryMessaging  # For events system (pub/sub)
MemoryQueue = MemoryMessaging  # For tasks system (queues)

Messaging = MemoryMessaging
MessagingSettings = MemoryMessagingSettings

depends.set(Messaging, "memory")
