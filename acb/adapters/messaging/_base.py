"""Messaging adapter interfaces for ACB framework.

This module provides dual interfaces for messaging backends:
1. PubSubBackend - For event-driven pub/sub patterns (events system)
2. QueueBackend - For task queue patterns (tasks system)

Messaging implementations (Redis, RabbitMQ, etc.) can implement both
interfaces to support both patterns with a single backend.

Key Design Principles:
1. Clear separation between pub/sub and queue patterns
2. Type-safe interfaces preventing cross-pattern usage
3. Connection pooling and lifecycle management
4. Async-first with proper error handling
5. Follows ACB adapter patterns with MODULE_METADATA
"""

from collections.abc import AsyncGenerator, AsyncIterator
from enum import Enum
from uuid import UUID, uuid4

import asyncio
import typing as t
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pydantic import BaseModel, Field

# Re-export common types for convenience
__all__ = [
    # Mixins
    "ConnectionMixin",
    "DeliveryMode",
    # Enums
    "MessagePriority",
    "MessagingCapability",
    "MessagingConnectionError",
    # Exceptions
    "MessagingException",
    "MessagingOperationError",
    # Settings
    "MessagingSettings",
    "MessagingTimeoutError",
    # Interfaces
    "PubSubBackend",
    # Messages
    "PubSubMessage",
    "PubSubMixin",
    "QueueBackend",
    "QueueEmptyError",
    "QueueFullError",
    "QueueMessage",
    "QueueMixin",
    "UnifiedMessagingBackend",
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


class MessagingCapability(Enum):
    """Messaging backend capabilities for feature detection."""

    # Pub/Sub capabilities
    PUB_SUB = "pub_sub"  # Basic publish/subscribe
    PATTERN_SUBSCRIBE = "pattern_subscribe"  # Pattern-based subscriptions
    BROADCAST = "broadcast"  # Broadcast to all subscribers

    # Queue capabilities
    BASIC_QUEUE = "basic_queue"  # Basic enqueue/dequeue
    PRIORITY_QUEUE = "priority_queue"  # Priority ordering
    DELAYED_MESSAGES = "delayed_messages"  # Message delay/scheduling
    DEAD_LETTER_QUEUE = "dead_letter_queue"  # Failed message handling

    # Common capabilities
    PERSISTENCE = "persistence"  # Disk-backed storage
    TRANSACTIONS = "transactions"  # Atomic operations
    CONNECTION_POOLING = "connection_pooling"  # Connection reuse
    CLUSTERING = "clustering"  # Distributed deployment
    MESSAGE_TTL = "message_ttl"  # Time-to-live support
    BATCH_OPERATIONS = "batch_operations"  # Bulk send/receive
    STREAMING = "streaming"  # Continuous message streaming


# ============================================================================
# Exception Hierarchy
# ============================================================================


class MessagingException(Exception):
    """Base exception for all messaging-related errors."""

    def __init__(
        self,
        message: str,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.original_error = original_error


class MessagingConnectionError(MessagingException):
    """Raised when connection to messaging backend fails."""


class MessagingOperationError(MessagingException):
    """Raised when a messaging operation fails."""


class MessagingTimeoutError(MessagingException):
    """Raised when a messaging operation times out."""


class QueueFullError(MessagingException):
    """Raised when queue capacity is exceeded."""


class QueueEmptyError(MessagingException):
    """Raised when attempting to dequeue from empty queue."""


# ============================================================================
# Data Models
# ============================================================================


class PubSubMessage(BaseModel):
    """Message format for pub/sub operations."""

    # Core identification
    message_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))

    # Pub/sub specific
    topic: str = Field(description="Topic/channel for pub/sub")
    payload: bytes = Field(description="Message payload as bytes")

    # Optional metadata
    correlation_id: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)


class QueueMessage(BaseModel):
    """Message format for queue operations."""

    # Core identification
    message_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))

    # Queue specific
    queue: str = Field(description="Target queue name")
    payload: bytes = Field(description="Message payload as bytes")
    priority: MessagePriority = MessagePriority.NORMAL

    # Task queue features
    delay_seconds: float = 0.0
    max_retries: int = 3
    retry_count: int = 0

    # Optional metadata
    correlation_id: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)


class MessagingSettings(BaseModel):
    """Base settings for messaging adapters.

    Subclasses should extend this with backend-specific configuration.
    """

    # Connection settings
    connection_url: str | None = None
    connection_timeout: float = 10.0
    max_connections: int = 10

    # Performance tuning
    batch_size: int = 100
    prefetch_count: int = 10

    # Reliability
    retry_attempts: int = 3
    retry_delay: float = 1.0

    # Feature flags
    enable_persistence: bool = False
    enable_transactions: bool = False


class Subscription(BaseModel):
    """Represents an active subscription to a pub/sub topic."""

    subscription_id: UUID = Field(default_factory=uuid4)
    topic: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    active: bool = True


# ============================================================================
# Interface: PubSubBackend (for Events System)
# ============================================================================


class PubSubBackend(t.Protocol):
    """Protocol interface for pub/sub messaging patterns.

    Used by the events system for event-driven messaging.
    Supports multiple subscribers, topic-based routing, and broadcasts.

    Note: This is a Protocol (structural typing), not ABC (inheritance).
    Any class matching this interface can be used for pub/sub messaging.
    """

    _settings: MessagingSettings
    _logger: t.Any
    _connected: bool

    # Lifecycle Management

    async def connect(self) -> None:
        """Establish connection to the messaging backend."""
        ...

    async def disconnect(self) -> None:
        """Close connection to the messaging backend."""
        ...

    async def health_check(self) -> dict[str, t.Any]:
        """Check health status of the backend."""
        ...

    # Core Pub/Sub Operations

    async def publish(
        self,
        topic: str,
        message: bytes,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Publish a message to a topic.

        Args:
            topic: Topic/channel to publish to
            message: Message payload as bytes
            headers: Optional message headers
        """
        ...

    async def subscribe(
        self,
        topic: str,
        pattern: bool = False,
    ) -> Subscription:
        """Subscribe to a topic or pattern.

        Args:
            topic: Topic/pattern to subscribe to
            pattern: Whether topic is a pattern (e.g., "events.*")

        Returns:
            Subscription object for managing the subscription
        """
        ...

    async def unsubscribe(self, subscription: Subscription) -> None:
        """Unsubscribe from a topic."""
        ...

    @asynccontextmanager
    async def receive_messages(
        self,
        subscription: Subscription,
        timeout: float | None = None,
    ) -> AsyncGenerator[AsyncIterator[PubSubMessage]]:
        """Receive messages from a subscription.

        Args:
            subscription: Active subscription to receive from
            timeout: Timeout in seconds (None for no timeout)

        Yields:
            Async iterator of messages
        """
        raise NotImplementedError  # pragma: no cover

    # Batch Operations

    async def publish_batch(
        self,
        messages: list[tuple[str, bytes, dict[str, str] | None]],
    ) -> None:
        """Publish multiple messages in a batch.

        Default implementation calls publish() for each message.
        Backends can override for optimized batch operations.
        """
        ...

    # Capability Detection

    def get_capabilities(self) -> set[MessagingCapability]:
        """Get the capabilities supported by this backend."""
        ...


# ============================================================================
# Interface: QueueBackend (for Tasks System)
# ============================================================================


class QueueBackend(t.Protocol):
    """Protocol interface for work queue patterns.

    Used by the tasks system for job processing with workers.
    Supports single consumer per message, acknowledgments, and retries.

    Note: This is a Protocol (structural typing), not ABC (inheritance).
    Any class matching this interface can be used for task queues.
    """

    _settings: MessagingSettings
    _logger: t.Any
    _connected: bool

    # Lifecycle Management

    async def connect(self) -> None:
        """Establish connection to the messaging backend."""
        ...

    async def disconnect(self) -> None:
        """Close connection to the messaging backend."""
        ...

    async def health_check(self) -> dict[str, t.Any]:
        """Check health status of the backend."""
        ...

    # Core Queue Operations

    async def enqueue(
        self,
        queue: str,
        message: bytes,
        priority: MessagePriority = MessagePriority.NORMAL,
        delay_seconds: float = 0.0,
        headers: dict[str, str] | None = None,
    ) -> str:
        """Add a message to a queue.

        Args:
            queue: Queue name
            message: Message payload as bytes
            priority: Message priority
            delay_seconds: Delay before message becomes available
            headers: Optional message headers

        Returns:
            Message ID for tracking
        """
        ...

    async def dequeue(
        self,
        queue: str,
        timeout: float | None = None,
        visibility_timeout: float = 30.0,
    ) -> QueueMessage | None:
        """Remove and return a message from a queue.

        Args:
            queue: Queue name
            timeout: Wait timeout in seconds (None for no wait)
            visibility_timeout: Time before message returns to queue if not acked

        Returns:
            Message if available, None otherwise
        """
        ...

    async def acknowledge(
        self,
        queue: str,
        message_id: str,
    ) -> None:
        """Acknowledge successful processing of a message.

        Args:
            queue: Queue name
            message_id: ID of message to acknowledge
        """
        ...

    async def reject(
        self,
        queue: str,
        message_id: str,
        requeue: bool = True,
    ) -> None:
        """Reject a message, optionally requeuing it.

        Args:
            queue: Queue name
            message_id: ID of message to reject
            requeue: Whether to return message to queue
        """
        ...

    # Queue Management

    async def purge_queue(self, queue: str) -> int:
        """Remove all messages from a queue.

        Returns:
            Number of messages purged
        """
        ...

    async def get_queue_stats(self, queue: str) -> dict[str, t.Any]:
        """Get statistics for a queue.

        Returns:
            Dict with stats like message_count, consumer_count, etc.
        """
        ...

    # Dead Letter Queue

    async def send_to_dlq(
        self,
        queue: str,
        message: QueueMessage,
        reason: str,
    ) -> None:
        """Send a failed message to the dead letter queue.

        Default implementation enqueues to {queue}_dlq.
        Backends can override for custom DLQ handling.
        """
        ...

    # Batch Operations

    async def enqueue_batch(
        self,
        queue: str,
        messages: list[tuple[bytes, MessagePriority, dict[str, str] | None]],
    ) -> list[str]:
        """Enqueue multiple messages in a batch.

        Default implementation calls enqueue() for each message.
        Backends can override for optimized batch operations.
        """
        ...

    # Capability Detection

    def get_capabilities(self) -> set[MessagingCapability]:
        """Get the capabilities supported by this backend."""
        ...


# ============================================================================
# Unified Interface (for backends supporting both patterns)
# ============================================================================


class UnifiedMessagingBackend(t.Protocol):
    """Protocol combining pub/sub and queue patterns.

    Most messaging systems (Redis, RabbitMQ, etc.) support both patterns.
    Implementations should satisfy both PubSubBackend and QueueBackend protocols.

    Note: This is a Protocol (structural typing), not ABC (inheritance).
    Any class matching both interfaces can be used as a unified backend.
    """

    _settings: MessagingSettings
    _logger: t.Any
    _connected: bool

    # Shared lifecycle methods (identical in both interfaces)

    async def connect(self) -> None:
        """Establish connection to the messaging backend."""
        ...

    async def disconnect(self) -> None:
        """Close connection to the messaging backend."""
        ...

    async def health_check(self) -> dict[str, t.Any]:
        """Check health status of the backend."""
        ...

    def get_capabilities(self) -> set[MessagingCapability]:
        """Get the capabilities supported by this backend."""
        ...

    # PubSubBackend methods

    async def publish(
        self,
        topic: str,
        message: bytes,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Publish a message to a topic."""
        ...

    async def subscribe(
        self,
        topic: str,
        pattern: bool = False,
    ) -> Subscription:
        """Subscribe to a topic or pattern."""
        ...

    async def unsubscribe(self, subscription: Subscription) -> None:
        """Unsubscribe from a topic."""
        ...

    @asynccontextmanager
    async def receive_messages(
        self,
        subscription: Subscription,
        timeout: float | None = None,
    ) -> AsyncGenerator[AsyncIterator[PubSubMessage]]:
        """Receive messages from a subscription."""
        raise NotImplementedError  # pragma: no cover

    async def publish_batch(
        self,
        messages: list[tuple[str, bytes, dict[str, str] | None]],
    ) -> None:
        """Publish multiple messages in a batch."""
        ...

    # QueueBackend methods

    async def enqueue(
        self,
        queue: str,
        message: bytes,
        priority: MessagePriority = MessagePriority.NORMAL,
        delay_seconds: float = 0.0,
        headers: dict[str, str] | None = None,
    ) -> str:
        """Add a message to a queue."""
        ...

    async def dequeue(
        self,
        queue: str,
        timeout: float | None = None,
        visibility_timeout: float = 30.0,
    ) -> QueueMessage | None:
        """Remove and return a message from a queue."""
        ...

    async def acknowledge(
        self,
        queue: str,
        message_id: str,
    ) -> None:
        """Acknowledge successful processing of a message."""
        ...

    async def reject(
        self,
        queue: str,
        message_id: str,
        requeue: bool = True,
    ) -> None:
        """Reject a message, optionally requeuing it."""
        ...

    async def purge_queue(self, queue: str) -> int:
        """Remove all messages from a queue."""
        ...

    async def get_queue_stats(self, queue: str) -> dict[str, t.Any]:
        """Get statistics for a queue."""
        ...

    async def send_to_dlq(
        self,
        queue: str,
        message: QueueMessage,
        reason: str,
    ) -> None:
        """Send a failed message to the dead letter queue."""
        ...

    async def enqueue_batch(
        self,
        queue: str,
        messages: list[tuple[bytes, MessagePriority, dict[str, str] | None]],
    ) -> list[str]:
        """Enqueue multiple messages in a batch."""
        ...


# ============================================================================
# Mixin Classes with Common Implementations
# ============================================================================


class ConnectionMixin:
    """Provides common connection management functionality for messaging backends.

    This mixin implements shared connection logic that can be reused across
    different messaging implementations while preserving the Protocol interface.
    """

    _settings: MessagingSettings
    _logger: t.Any
    _connected: bool

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._connection_lock = asyncio.Lock()

    @property
    def logger(self) -> t.Any:
        """Lazy-initialize logger.

        Returns:
            Logger instance
        """
        if not hasattr(self, "_logger") or self._logger is None:
            try:
                from acb.adapters import import_adapter
                from acb.depends import depends

                logger_cls = import_adapter("logger")
                self._logger = depends.get_sync(logger_cls)
            except Exception:
                # Fallback if logger adapter unavailable
                import logging

                self._logger = logging.getLogger(self.__class__.__name__)
        return self._logger

    async def _ensure_connection(self) -> None:
        """Ensure backend is connected, connecting if necessary."""
        if not self._connected:
            await self.connect()

    async def health_check(self) -> dict[str, t.Any]:
        """Default health check implementation."""
        return {
            "connected": self._connected,
            "capabilities": list(self.get_capabilities()),
            "timestamp": datetime.now(tz=UTC).isoformat(),
        }

    def get_capabilities(self) -> set[MessagingCapability]:
        """Default capabilities implementation - override in subclasses."""
        return set()


class PubSubMixin:
    """Provides common pub/sub functionality for messaging backends."""

    _settings: MessagingSettings

    async def subscribe(
        self,
        topic: str,
        pattern: bool = False,
    ) -> Subscription:
        """Default subscription implementation."""
        await self._ensure_connection()
        return Subscription(topic=topic)

    async def publish_batch(
        self,
        messages: list[tuple[str, bytes, dict[str, str] | None]],
    ) -> None:
        """Default batch publish implementation - calls publish() for each message."""
        for topic, message, headers in messages:
            await self.publish(topic, message, headers)


class QueueMixin:
    """Provides common queue functionality for messaging backends."""

    _settings: MessagingSettings

    async def send_to_dlq(
        self,
        queue: str,
        message: QueueMessage,
        reason: str,
    ) -> None:
        """Default dead letter queue implementation - enqueues to {queue}_dlq."""
        dlq_name = f"{queue}_dlq"
        payload = message.model_dump_json().encode()
        await self.enqueue(
            dlq_name,
            payload,
            priority=MessagePriority.NORMAL,
            headers={"original_queue": queue, "failure_reason": reason},
        )

    async def enqueue_batch(
        self,
        queue: str,
        messages: list[tuple[bytes, MessagePriority, dict[str, str] | None]],
    ) -> list[str]:
        """Default batch enqueue implementation - calls enqueue() for each message."""
        results = []
        for message, priority, headers in messages:
            msg_id = await self.enqueue(queue, message, priority, 0.0, headers)
            results.append(msg_id)
        return results
