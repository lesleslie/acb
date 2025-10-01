"""Base queue adapter interface for ACB framework.

This module provides the unified queue backend interface that supports both
task queue and event pub/sub use cases. All queue implementations (Memory,
Redis, RabbitMQ, etc.) must implement this interface.

Key Design Principles:
1. Single unified interface for all queue backends
2. Supports both task queues (enqueue/dequeue) and pub/sub (publish/subscribe)
3. Connection pooling and lifecycle management
4. Async-first with proper error handling
5. Follows ACB adapter patterns with MODULE_METADATA
"""

import asyncio
import typing as t
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from acb.cleanup import CleanupMixin
from acb.config import Config
from acb.depends import depends
from acb.logger import Logger

# Re-export common types for convenience
__all__ = [
    "QueueBackend",
    "QueueSettings",
    "QueueMessage",
    "QueueException",
    "QueueConnectionError",
    "QueueOperationError",
    "QueueTimeoutError",
    "MessagePriority",
    "DeliveryMode",
]


# ============================================================================
# Enums and Constants
# ============================================================================


class MessagePriority(Enum):
    """Message priority levels for queue ordering."""

    LOW = 1
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20


class DeliveryMode(Enum):
    """Message delivery guarantees."""

    FIRE_AND_FORGET = "fire_and_forget"  # No acknowledgment
    AT_LEAST_ONCE = "at_least_once"  # May be delivered multiple times
    EXACTLY_ONCE = "exactly_once"  # Delivered exactly once (if supported)


class QueueCapability(Enum):
    """Queue backend capabilities for feature detection."""

    # Core operations
    BASIC_QUEUE = "basic_queue"  # enqueue/dequeue support
    PUB_SUB = "pub_sub"  # publish/subscribe support
    PRIORITY_QUEUE = "priority_queue"  # Priority ordering
    DELAYED_MESSAGES = "delayed_messages"  # Message delay/scheduling

    # Reliability
    PERSISTENCE = "persistence"  # Disk-backed storage
    TRANSACTIONS = "transactions"  # Atomic operations
    DEAD_LETTER_QUEUE = "dead_letter_queue"  # Failed message handling

    # Scalability
    CONNECTION_POOLING = "connection_pooling"  # Connection reuse
    CLUSTERING = "clustering"  # Distributed deployment
    LOAD_BALANCING = "load_balancing"  # Work distribution

    # Advanced features
    MESSAGE_TTL = "message_ttl"  # Time-to-live support
    BATCH_OPERATIONS = "batch_operations"  # Bulk send/receive
    STREAMING = "streaming"  # Continuous message streaming


# ============================================================================
# Exception Hierarchy
# ============================================================================


class QueueException(Exception):
    """Base exception for all queue-related errors."""

    def __init__(
        self,
        message: str,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.original_error = original_error


class QueueConnectionError(QueueException):
    """Raised when connection to queue backend fails."""


class QueueOperationError(QueueException):
    """Raised when a queue operation fails."""


class QueueTimeoutError(QueueException):
    """Raised when a queue operation times out."""


class QueueFullError(QueueException):
    """Raised when queue capacity is exceeded."""


class QueueEmptyError(QueueException):
    """Raised when attempting to dequeue from empty queue."""


# ============================================================================
# Data Models
# ============================================================================


class QueueMessage(BaseModel):
    """Universal message format for queue operations.

    This structure works for both task queues and event pub/sub, providing
    a common interface while allowing backend-specific extensions.
    """

    # Core identification
    message_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Routing information
    topic: str = Field(description="Topic/queue/routing key for message")
    payload: bytes = Field(description="Message payload as bytes")

    # Delivery control
    priority: MessagePriority = MessagePriority.NORMAL
    delivery_mode: DeliveryMode = DeliveryMode.AT_LEAST_ONCE

    # Scheduling
    delay_seconds: float = 0.0  # Delay before delivery
    ttl_seconds: int | None = None  # Time-to-live

    # Correlation and tracing
    correlation_id: str | None = None  # For request-response patterns
    reply_to: str | None = None  # Response destination

    # Retry handling
    retry_count: int = 0
    max_retries: int = 3

    # Custom metadata
    headers: dict[str, t.Any] = Field(default_factory=dict)

    def to_bytes(self) -> bytes:
        """Serialize message to bytes for transport."""
        return self.model_dump_json().encode("utf-8")

    @classmethod
    def from_bytes(cls, data: bytes) -> "QueueMessage":
        """Deserialize message from bytes."""
        return cls.model_validate_json(data)


class QueueSettings(BaseModel):
    """Base settings for queue adapters.

    Subclasses should extend this with backend-specific configuration.
    """

    # Connection settings
    connection_url: str | None = None
    connection_timeout: float = 10.0
    max_connections: int = 10

    # Operation timeouts
    send_timeout: float = 30.0
    receive_timeout: float = 30.0
    ack_timeout: float = 30.0

    # Retry configuration
    enable_retries: bool = True
    max_retry_attempts: int = 3
    retry_delay: float = 1.0
    retry_exponential_backoff: bool = True
    max_retry_delay: float = 60.0

    # Performance tuning
    prefetch_count: int = 10  # Number of messages to prefetch
    batch_size: int = 100  # Max messages per batch operation

    # Feature flags
    enable_dead_letter: bool = True
    enable_persistence: bool = True
    enable_metrics: bool = True

    # Health monitoring
    health_check_interval: float = 30.0
    connection_pool_cleanup_interval: float = 60.0


# ============================================================================
# Queue Backend Interface
# ============================================================================


class QueueBackend(ABC, CleanupMixin):
    """Unified queue backend interface for task queues and event pub/sub.

    This interface is designed to support both use cases:
    1. Task Queues: Use enqueue/dequeue for worker-based processing
    2. Event Pub/Sub: Use publish/subscribe for event-driven messaging

    All implementations must follow ACB adapter patterns:
    - Public methods delegate to private implementation methods
    - Lazy client initialization with _ensure_client pattern
    - Proper async context manager support
    - Automatic resource cleanup via CleanupMixin
    """

    def __init__(self, settings: QueueSettings | None = None) -> None:
        """Initialize queue backend.

        Args:
            settings: Queue configuration settings
        """
        super().__init__()
        CleanupMixin.__init__(self)

        # Injected dependencies
        self.config: Config = depends.get(Config)
        self.logger: Logger = depends.get(Logger)

        # Settings
        self._settings = settings or QueueSettings()

        # Connection state
        self._client: t.Any = None
        self._connected = False
        self._connection_lock = asyncio.Lock()

        # Background tasks
        self._health_check_task: asyncio.Task[None] | None = None
        self._cleanup_task: asyncio.Task[None] | None = None
        self._shutdown_event = asyncio.Event()

    # ========================================================================
    # Connection Management (Public API)
    # ========================================================================

    async def connect(self) -> None:
        """Connect to queue backend.

        Public method that delegates to private implementation.
        Idempotent - safe to call multiple times.
        """
        await self._connect()

    async def disconnect(self) -> None:
        """Disconnect from queue backend.

        Public method that delegates to private implementation.
        Cleans up all resources and background tasks.
        """
        await self._disconnect()

    async def is_connected(self) -> bool:
        """Check if connected to queue backend.

        Returns:
            True if connected and healthy
        """
        return self._connected and self._client is not None

    async def health_check(self) -> dict[str, t.Any]:
        """Perform health check on queue backend.

        Returns:
            Health status information
        """
        return await self._health_check()

    # ========================================================================
    # Message Operations (Public API)
    # ========================================================================

    async def send(
        self,
        message: QueueMessage,
        timeout: float | None = None,
    ) -> str:
        """Send a message to the queue/topic.

        Generic send operation that works for both task queues and pub/sub.

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
        return await self._send(message, timeout)

    async def receive(
        self,
        topic: str,
        timeout: float | None = None,
    ) -> QueueMessage | None:
        """Receive a single message from topic/queue.

        Args:
            topic: Topic or queue name to receive from
            timeout: Optional timeout override

        Returns:
            Message or None if no messages available

        Raises:
            QueueConnectionError: If not connected
            QueueOperationError: If receive fails
        """
        return await self._receive(topic, timeout)

    async def acknowledge(
        self,
        message: QueueMessage,
        timeout: float | None = None,
    ) -> None:
        """Acknowledge successful message processing.

        Required for AT_LEAST_ONCE and EXACTLY_ONCE delivery modes.

        Args:
            message: Message to acknowledge
            timeout: Optional timeout override

        Raises:
            QueueOperationError: If acknowledgment fails
        """
        await self._acknowledge(message, timeout)

    async def reject(
        self,
        message: QueueMessage,
        requeue: bool = False,
        timeout: float | None = None,
    ) -> None:
        """Reject a message (negative acknowledgment).

        Args:
            message: Message to reject
            requeue: Whether to requeue the message
            timeout: Optional timeout override

        Raises:
            QueueOperationError: If rejection fails
        """
        await self._reject(message, requeue, timeout)

    # ========================================================================
    # Task Queue API (Specialized Operations)
    # ========================================================================

    async def enqueue(
        self,
        topic: str,
        payload: bytes,
        priority: MessagePriority = MessagePriority.NORMAL,
        delay_seconds: float = 0.0,
        **kwargs: t.Any,
    ) -> str:
        """Enqueue a task for processing (convenience method).

        Higher-level API for task queue use case.

        Args:
            topic: Queue name
            payload: Task payload
            priority: Task priority
            delay_seconds: Delay before processing
            **kwargs: Additional message options

        Returns:
            Message ID
        """
        message = QueueMessage(
            topic=topic,
            payload=payload,
            priority=priority,
            delay_seconds=delay_seconds,
            **kwargs,
        )
        return await self.send(message)

    async def dequeue(
        self,
        topic: str,
        timeout: float | None = None,
    ) -> QueueMessage | None:
        """Dequeue a task for processing (convenience method).

        Higher-level API for task queue use case.

        Args:
            topic: Queue name
            timeout: Optional timeout override

        Returns:
            Message or None if queue is empty
        """
        return await self.receive(topic, timeout)

    # ========================================================================
    # Pub/Sub API (Specialized Operations)
    # ========================================================================

    async def publish(
        self,
        topic: str,
        payload: bytes,
        **kwargs: t.Any,
    ) -> str:
        """Publish an event to subscribers (convenience method).

        Higher-level API for pub/sub use case.

        Args:
            topic: Event topic/channel
            payload: Event payload
            **kwargs: Additional message options

        Returns:
            Message ID
        """
        message = QueueMessage(
            topic=topic,
            payload=payload,
            delivery_mode=DeliveryMode.FIRE_AND_FORGET,
            **kwargs,
        )
        return await self.send(message)

    @asynccontextmanager
    async def subscribe(
        self,
        topic: str,
        prefetch: int | None = None,
    ) -> AsyncGenerator[AsyncGenerator[QueueMessage]]:
        """Subscribe to a topic and stream messages (context manager).

        Higher-level API for pub/sub use case.

        Args:
            topic: Topic or pattern to subscribe to
            prefetch: Number of messages to prefetch

        Yields:
            Async generator yielding messages

        Example:
            async with queue.subscribe("events.*") as messages:
                async for message in messages:
                    await process_message(message)
                    await queue.acknowledge(message)
        """
        async with self._subscribe(topic, prefetch) as message_stream:
            yield message_stream

    # ========================================================================
    # Queue Management (Public API)
    # ========================================================================

    async def create_queue(
        self,
        name: str,
        **options: t.Any,
    ) -> None:
        """Create a new queue/topic.

        Args:
            name: Queue or topic name
            **options: Backend-specific options

        Raises:
            QueueOperationError: If creation fails
        """
        await self._create_queue(name, **options)

    async def delete_queue(
        self,
        name: str,
        if_empty: bool = False,
    ) -> None:
        """Delete a queue/topic.

        Args:
            name: Queue or topic name
            if_empty: Only delete if queue is empty

        Raises:
            QueueOperationError: If deletion fails
        """
        await self._delete_queue(name, if_empty)

    async def purge_queue(
        self,
        name: str,
    ) -> int:
        """Remove all messages from a queue.

        Args:
            name: Queue name

        Returns:
            Number of messages purged

        Raises:
            QueueOperationError: If purge fails
        """
        return await self._purge_queue(name)

    async def get_queue_size(
        self,
        name: str,
    ) -> int:
        """Get number of messages in queue.

        Args:
            name: Queue name

        Returns:
            Message count

        Raises:
            QueueOperationError: If operation fails
        """
        return await self._get_queue_size(name)

    async def list_queues(
        self,
        pattern: str | None = None,
    ) -> list[str]:
        """List all queues/topics.

        Args:
            pattern: Optional pattern to filter queues

        Returns:
            List of queue names
        """
        return await self._list_queues(pattern)

    # ========================================================================
    # Batch Operations (Public API)
    # ========================================================================

    async def send_batch(
        self,
        messages: list[QueueMessage],
        timeout: float | None = None,
    ) -> list[str]:
        """Send multiple messages in a batch.

        More efficient than individual sends if backend supports batching.

        Args:
            messages: List of messages to send
            timeout: Optional timeout override

        Returns:
            List of message IDs

        Raises:
            QueueOperationError: If batch send fails
        """
        return await self._send_batch(messages, timeout)

    async def receive_batch(
        self,
        topic: str,
        max_messages: int,
        timeout: float | None = None,
    ) -> list[QueueMessage]:
        """Receive multiple messages in a batch.

        More efficient than individual receives if backend supports batching.

        Args:
            topic: Topic or queue name
            max_messages: Maximum messages to receive
            timeout: Optional timeout override

        Returns:
            List of messages (may be less than max_messages)

        Raises:
            QueueOperationError: If batch receive fails
        """
        return await self._receive_batch(topic, max_messages, timeout)

    # ========================================================================
    # Abstract Methods (Private Implementation)
    # ========================================================================

    @abstractmethod
    async def _ensure_client(self) -> t.Any:
        """Ensure backend client is initialized (lazy initialization).

        This is the core pattern for ACB adapters. Implementations should:
        1. Check if self._client is None
        2. If None, create and configure the client
        3. Register client for cleanup
        4. Return the client

        Returns:
            Backend client instance

        Raises:
            QueueConnectionError: If connection fails
        """
        ...

    @abstractmethod
    async def _connect(self) -> None:
        """Establish connection to queue backend.

        Implementation should:
        1. Acquire connection lock
        2. Skip if already connected
        3. Call _ensure_client()
        4. Verify connection health
        5. Start background tasks (health checks, etc.)
        6. Set self._connected = True
        """
        ...

    @abstractmethod
    async def _disconnect(self) -> None:
        """Disconnect from queue backend.

        Implementation should:
        1. Set self._connected = False
        2. Signal shutdown event
        3. Cancel background tasks
        4. Close client connections
        5. Call self.cleanup()
        """
        ...

    @abstractmethod
    async def _health_check(self) -> dict[str, t.Any]:
        """Perform backend-specific health check.

        Returns:
            Health status dict with keys:
            - healthy (bool): Overall health status
            - connected (bool): Connection status
            - latency_ms (float): Connection latency
            - backend_info (dict): Backend-specific info
        """
        ...

    @abstractmethod
    async def _send(
        self,
        message: QueueMessage,
        timeout: float | None = None,
    ) -> str:
        """Send a message (private implementation).

        Args:
            message: Message to send
            timeout: Optional timeout

        Returns:
            Message ID

        Raises:
            QueueConnectionError: If not connected
            QueueOperationError: If send fails
            QueueTimeoutError: If operation times out
        """
        ...

    @abstractmethod
    async def _receive(
        self,
        topic: str,
        timeout: float | None = None,
    ) -> QueueMessage | None:
        """Receive a message (private implementation).

        Args:
            topic: Topic/queue to receive from
            timeout: Optional timeout

        Returns:
            Message or None

        Raises:
            QueueConnectionError: If not connected
            QueueOperationError: If receive fails
        """
        ...

    @abstractmethod
    async def _acknowledge(
        self,
        message: QueueMessage,
        timeout: float | None = None,
    ) -> None:
        """Acknowledge a message (private implementation).

        Args:
            message: Message to acknowledge
            timeout: Optional timeout

        Raises:
            QueueOperationError: If ack fails
        """
        ...

    @abstractmethod
    async def _reject(
        self,
        message: QueueMessage,
        requeue: bool = False,
        timeout: float | None = None,
    ) -> None:
        """Reject a message (private implementation).

        Args:
            message: Message to reject
            requeue: Whether to requeue
            timeout: Optional timeout

        Raises:
            QueueOperationError: If reject fails
        """
        ...

    @abstractmethod
    @asynccontextmanager
    async def _subscribe(
        self,
        topic: str,
        prefetch: int | None = None,
    ) -> AsyncGenerator[AsyncGenerator[QueueMessage]]:
        """Subscribe to topic (private implementation).

        Args:
            topic: Topic/pattern to subscribe to
            prefetch: Messages to prefetch

        Yields:
            Async generator of messages
        """
        ...

    @abstractmethod
    async def _create_queue(
        self,
        name: str,
        **options: t.Any,
    ) -> None:
        """Create queue (private implementation).

        Args:
            name: Queue name
            **options: Backend-specific options
        """
        ...

    @abstractmethod
    async def _delete_queue(
        self,
        name: str,
        if_empty: bool = False,
    ) -> None:
        """Delete queue (private implementation).

        Args:
            name: Queue name
            if_empty: Only delete if empty
        """
        ...

    @abstractmethod
    async def _purge_queue(
        self,
        name: str,
    ) -> int:
        """Purge queue (private implementation).

        Args:
            name: Queue name

        Returns:
            Number of messages purged
        """
        ...

    @abstractmethod
    async def _get_queue_size(
        self,
        name: str,
    ) -> int:
        """Get queue size (private implementation).

        Args:
            name: Queue name

        Returns:
            Message count
        """
        ...

    @abstractmethod
    async def _list_queues(
        self,
        pattern: str | None = None,
    ) -> list[str]:
        """List queues (private implementation).

        Args:
            pattern: Optional filter pattern

        Returns:
            List of queue names
        """
        ...

    # Optional batch operations (default implementations provided)

    async def _send_batch(
        self,
        messages: list[QueueMessage],
        timeout: float | None = None,
    ) -> list[str]:
        """Send batch (default implementation - calls _send for each).

        Subclasses should override for more efficient batch operations.

        Args:
            messages: Messages to send
            timeout: Optional timeout

        Returns:
            List of message IDs
        """
        message_ids = []
        for message in messages:
            message_id = await self._send(message, timeout)
            message_ids.append(message_id)
        return message_ids

    async def _receive_batch(
        self,
        topic: str,
        max_messages: int,
        timeout: float | None = None,
    ) -> list[QueueMessage]:
        """Receive batch (default implementation - calls _receive repeatedly).

        Subclasses should override for more efficient batch operations.

        Args:
            topic: Topic to receive from
            max_messages: Max messages to receive
            timeout: Optional timeout

        Returns:
            List of messages
        """
        messages = []
        for _ in range(max_messages):
            message = await self._receive(topic, timeout)
            if message is None:
                break
            messages.append(message)
        return messages

    # ========================================================================
    # Async Context Manager Support
    # ========================================================================

    async def __aenter__(self) -> "QueueBackend":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: t.Any,
    ) -> None:
        """Async context manager exit."""
        await self.disconnect()

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def get_capabilities(self) -> list[QueueCapability]:
        """Get backend capabilities.

        Subclasses should override to return their specific capabilities.

        Returns:
            List of supported capabilities
        """
        return [QueueCapability.BASIC_QUEUE]

    def supports_capability(self, capability: QueueCapability) -> bool:
        """Check if backend supports a specific capability.

        Args:
            capability: Capability to check

        Returns:
            True if supported
        """
        return capability in self.get_capabilities()


# ============================================================================
# Utility Functions
# ============================================================================


def generate_adapter_id() -> UUID:
    """Generate unique adapter ID."""
    return uuid4()


def create_queue_message(
    topic: str,
    payload: bytes | str,
    **kwargs: t.Any,
) -> QueueMessage:
    """Create a queue message with sensible defaults.

    Args:
        topic: Topic/queue name
        payload: Message payload (bytes or str)
        **kwargs: Additional message options

    Returns:
        QueueMessage instance
    """
    if isinstance(payload, str):
        payload = payload.encode("utf-8")

    return QueueMessage(
        topic=topic,
        payload=payload,
        **kwargs,
    )
