"""Example of refactored Redis Queue Backend Adapter for ACB (using mixins).

This shows how the existing Redis implementation could be refactored to use
the new mixins from _base.py to reduce duplicate code.

Note: This is an example implementation to demonstrate the refactoring approach.
"""

import json
import time
from collections.abc import AsyncGenerator, AsyncIterator
from uuid import UUID

import asyncio
import typing as t
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from pydantic import Field

from acb.adapters import AdapterCapability, AdapterMetadata, AdapterStatus
from acb.cleanup import CleanupMixin
from acb.config import Config
from acb.depends import Inject, depends

from ._base import (
    ConnectionMixin,
    MessagePriority,
    MessagingConnectionError,
    MessagingOperationError,
    PubSubMessage,
    PubSubMixin,
    QueueMessage,
    QueueMixin,
    Subscription,
)
from ._base import (
    MessagingSettings as BaseMessagingSettings,
)

LoggerType = t.Any

# Lazy imports for coredis
_coredis_imports: dict[str, t.Any] = {}

MODULE_METADATA = AdapterMetadata(
    module_id=UUID("fef2289a-83f8-43e3-a5c0-a5343ee8bc88"),
    name="Redis Messaging",
    category="messaging",
    provider="redis",
    version="1.0.0",
    acb_min_version="0.19.0",
    author="Claude Code",
    created_date="2025-10-01",
    last_modified="2025-10-08",
    status=AdapterStatus.STABLE,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.CONNECTION_POOLING,
        AdapterCapability.CACHING,
        AdapterCapability.TRANSACTIONS,
        AdapterCapability.HEALTH_CHECKS,
        AdapterCapability.RECONNECTION,
    ],
    required_packages=["coredis>=4.0.0"],
    description="High-performance Redis messaging backend with pub/sub and queue support",
    settings_class="RedisMessagingSettings",
    config_example={
        "connection_url": "redis://localhost:6379/0",
        "max_connections": 20,
        "key_prefix": "acb:messaging",
        "enable_clustering": False,
        "use_lua_scripts": True,
    },
)


def _get_coredis_imports() -> dict[str, t.Any]:
    """Lazy import of coredis dependencies."""
    if not _coredis_imports:
        try:
            from coredis import Redis, RedisCluster
            from coredis.exceptions import (
                ConnectionError,
                RedisError,
                TimeoutError,
            )
            from coredis.pool import ConnectionPool

            _coredis_imports.update(
                {
                    "Redis": Redis,
                    "RedisCluster": RedisCluster,
                    "ConnectionPool": ConnectionPool,
                    "ConnectionError": ConnectionError,
                    "RedisError": RedisError,
                    "TimeoutError": TimeoutError,
                },
            )
        except ImportError as e:
            msg = (
                "coredis is required for RedisQueue. "
                "Install with: pip install coredis>=4.0.0"
            )
            raise ImportError(
                msg,
            ) from e

    return _coredis_imports


class RedisMessagingSettings(BaseMessagingSettings):
    """Settings for Redis messaging implementation."""

    # Redis connection
    connection_url: str | None = "redis://localhost:6379/0"
    key_prefix: str = "acb:messaging"

    # Connection pool settings
    max_connections: int = 20
    socket_connect_timeout: float = 5.0
    socket_timeout: float = 5.0

    # Clustering
    enable_clustering: bool = False
    cluster_nodes: list[str] = Field(default_factory=list)

    # Performance
    use_lua_scripts: bool = True
    pipeline_size: int = 100

    # Message retention
    message_ttl: int = 86400  # 24 hours

    # Operation timeouts
    send_timeout: float = 10.0
    ack_timeout: float = 5.0
    dead_letter_ttl: int = 604800  # 7 days

    @depends.inject
    def __init__(self, config: Inject[Config], **values: t.Any) -> None:
        super().__init__(**values)


class RedisMessaging(ConnectionMixin, PubSubMixin, QueueMixin, CleanupMixin):
    """Redis-backed unified messaging implementation using mixins.

    Provides high-performance messaging operations using Redis data structures:
    - Pub/sub for event-driven messaging patterns
    - Sorted sets for priority queues and delayed messages
    - Lists for FIFO queue operations
    - Hash maps for message metadata storage
    """

    config: Config

    def __init__(self, settings: RedisMessagingSettings | None = None) -> None:
        """Initialize Redis messaging backend.

        Args:
            settings: Redis messaging configuration
        """
        # Initialize all parent classes
        ConnectionMixin.__init__(self)
        CleanupMixin.__init__(self)

        self._settings: RedisMessagingSettings = settings or RedisMessagingSettings()

        # Redis client and pool
        self._client: t.Any = None
        self._connection_pool: t.Any = None

        # Connection management attributes (required by base class)
        self._shutdown_event = asyncio.Event()

        # Key patterns for Redis operations
        self._queue_key = f"{self._settings.key_prefix}:queues:{{topic}}"
        self._delayed_key = f"{self._settings.key_prefix}:delayed"
        self._processing_key = f"{self._settings.key_prefix}:processing"
        self._dead_letter_key = f"{self._settings.key_prefix}:dead_letter"
        self._message_key = f"{self._settings.key_prefix}:messages:{{message_id}}"
        self._pubsub_key = f"{self._settings.key_prefix}:pubsub:{{topic}}"

        # Lua scripts for atomic operations
        self._lua_scripts: dict[str, t.Any] = {}

        # Background task handles
        self._delayed_processor_task: asyncio.Task[None] | None = None
        self._pubsub_client: t.Any = None
        # Note: logger and connected are handled by ConnectionMixin
        self._connected: bool = False

    # ========================================================================
    # Connection Management (Implementation specific to Redis)
    # ========================================================================

    async def _ensure_client(self) -> t.Any:
        """Ensure Redis client is initialized (lazy initialization).

        Returns:
            Redis client instance

        Raises:
            MessagingConnectionError: If connection fails
        """
        if self._client is None:
            async with self._connection_lock:
                # Double-check after acquiring lock
                if self._client is None:
                    imports = _get_coredis_imports()

                    try:
                        # Create connection pool
                        self._connection_pool = imports["ConnectionPool"].from_url(
                            self._settings.connection_url,
                            max_connections=self._settings.max_connections,
                            socket_connect_timeout=self._settings.socket_connect_timeout,
                            socket_timeout=self._settings.socket_timeout,
                            decode_responses=False,  # We handle encoding
                        )

                        # Create Redis client
                        if self._settings.enable_clustering:
                            self._client = imports["RedisCluster"](
                                connection_pool=self._connection_pool,
                            )
                        else:
                            self._client = imports["Redis"](
                                connection_pool=self._connection_pool,
                            )

                        # Register for cleanup
                        self.register_resource(self._client)

                        # Test connection
                        await self._client.ping()  # type: ignore[attr-defined]

                        self.logger.debug("Redis connection established")

                    except Exception as e:
                        self.logger.exception(f"Failed to connect to Redis: {e}")
                        msg = "Failed to establish Redis connection"
                        raise MessagingConnectionError(
                            msg,
                            original_error=e,
                        ) from e

        return self._client

    async def connect(self) -> None:
        """Establish connection to Redis backend."""
        async with self._connection_lock:
            if self._connected:
                return

            # Initialize client
            await self._ensure_client()

            # Load Lua scripts if enabled
            if self._settings.use_lua_scripts:
                await self._load_lua_scripts()

            # Start background tasks
            self._delayed_processor_task = asyncio.create_task(
                self._process_delayed_messages(),
            )

            self._connected = True
            self.logger.info("Redis queue backend connected")

    async def disconnect(self) -> None:
        """Disconnect from Redis backend."""
        self._connected = False
        self._shutdown_event.set()

        # Cancel background tasks
        if self._delayed_processor_task:
            self._delayed_processor_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._delayed_processor_task

        # Close pub/sub client if active
        if self._pubsub_client:
            with suppress(Exception):
                await self._pubsub_client.close()

        # Close main client
        if self._client:
            with suppress(Exception):
                await self._client.close()

            self._client = None

        # Close connection pool
        if self._connection_pool:
            with suppress(Exception):
                await self._connection_pool.disconnect()

            self._connection_pool = None

        # Cleanup resources
        await self.cleanup()

        self.logger.info("Redis queue backend disconnected")

    # ========================================================================
    # Core Pub/Sub Operations (Redis-specific implementation)
    # ========================================================================

    async def publish(
        self,
        topic: str,
        message: bytes,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Publish a message to a Redis channel."""
        if not self._connected:
            await self.connect()

        client = await self._ensure_client()
        pubsub_key = self._pubsub_key.format(topic=topic)

        try:
            await client.publish(pubsub_key, message)  # type: ignore[attr-defined]
            self.logger.debug(f"Published message to topic: {topic}")
        except Exception as e:
            self.logger.exception(f"Failed to publish message to topic {topic}")
            msg = f"Failed to publish to topic {topic}"
            raise MessagingOperationError(
                msg,
                original_error=e,
            ) from e

    async def unsubscribe(self, subscription: Subscription) -> None:
        """Unsubscribe from a topic."""
        # Redis pubsub typically handles unsubscription automatically
        # when the pubsub client is closed
        subscription.active = False

    @asynccontextmanager
    async def receive_messages(
        self,
        subscription: Subscription,
        timeout: float | None = None,
    ) -> AsyncGenerator[AsyncIterator[PubSubMessage]]:
        """Receive messages from a subscription."""
        if not self._connected:
            await self.connect()

        client = await self._ensure_client()
        pubsub = client.pubsub()  # type: ignore[attr-defined]

        try:
            # Subscribe to the topic
            await pubsub.subscribe(subscription.topic)  # type: ignore[attr-defined]

            async def message_generator():
                start_time = time.time()
                while subscription.active and (
                    timeout is None or (time.time() - start_time) < timeout
                ):
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=1,
                    )  # type: ignore[attr-defined]
                    if message and message.get("type") == "message":
                        pubsub_msg = PubSubMessage(
                            topic=subscription.topic,
                            payload=message["data"],
                        )
                        yield pubsub_msg
                    elif timeout and (time.time() - start_time) >= timeout:
                        break

            yield message_generator()

        finally:
            await pubsub.unsubscribe(subscription.topic)  # type: ignore[attr-defined]
            await pubsub.close()  # type: ignore[attr-defined]

    # ========================================================================
    # Core Queue Operations (Redis-specific implementation)
    # ========================================================================

    async def enqueue(
        self,
        queue: str,
        message: bytes,
        priority: MessagePriority = MessagePriority.NORMAL,
        delay_seconds: float = 0.0,
        headers: dict[str, str] | None = None,
    ) -> str:
        """Add a message to a Redis queue."""
        if not self._connected:
            await self.connect()

        client = await self._ensure_client()

        # Create QueueMessage object

        queue_message = QueueMessage(
            queue=queue,
            payload=message,
            priority=priority,
            delay_seconds=delay_seconds,
            headers=headers or {},
        )

        try:
            # Calculate score for sorted set based on schedule time
            scheduled_time = time.time() + delay_seconds
            # Score = scheduled_time * 1M - priority (higher priority = lower score)
            score = scheduled_time * 1_000_000 - priority.value

            # Store message details in hash
            message_key = self._message_key.format(message_id=queue_message.message_id)
            await client.hset(  # type: ignore[attr-defined]
                message_key,
                mapping={
                    "payload": queue_message.payload,
                    "priority": queue_message.priority.value,
                    "headers": str(queue_message.headers),
                },
            )

            # Set TTL for message metadata
            if self._settings.message_ttl:
                await client.expire(  # type: ignore[attr-defined]
                    message_key,
                    self._settings.message_ttl,
                )

            # Add to queue sorted set with appropriate score
            if delay_seconds > 0:
                # Add to delayed queue
                await client.zadd(  # type: ignore[attr-defined]
                    self._delayed_key,
                    {str(queue_message.message_id): score},
                )
                self.logger.debug(
                    f"Enqueued delayed message {queue_message.message_id} to {queue}",
                )
            else:
                # Add directly to target queue
                queue_key = self._queue_key.format(topic=queue)
                await client.zadd(  # type: ignore[attr-defined]
                    queue_key,
                    {str(queue_message.message_id): queue_message.priority.value},
                )
                self.logger.debug(
                    f"Enqueued message {queue_message.message_id} to {queue}",
                )

            return str(queue_message.message_id)

        except Exception as e:
            self.logger.exception(f"Failed to enqueue message to queue {queue}")
            msg = f"Failed to enqueue to queue {queue}"
            raise MessagingOperationError(
                msg,
                original_error=e,
            ) from e

    async def dequeue(
        self,
        queue: str,
        timeout: float | None = None,
        visibility_timeout: float = 30.0,
    ) -> QueueMessage | None:
        """Remove and return a message from a Redis queue."""
        if not self._connected:
            await self.connect()

        client = await self._ensure_client()

        try:
            queue_key = self._queue_key.format(topic=queue)
            start_time = time.time()

            while timeout is None or (time.time() - start_time) < timeout:
                # Get the lowest score (highest priority) message
                results = await client.zpopmin(queue_key, count=1)  # type: ignore[attr-defined]

                # Skip if no results
                if results:
                    # Extract message ID from results
                    msg_id_str, _ = next(iter(results.items()))
                    msg_id = UUID(msg_id_str)

                    # Fetch the full message details
                    message_key = self._message_key.format(message_id=msg_id)
                    msg_data = await client.hgetall(message_key)  # type: ignore[attr-defined]

                    # Process message data if it exists
                    if msg_data:
                        # Create QueueMessage from stored data
                        headers_data = msg_data.get(b"headers", b"{}").decode()
                        try:
                            headers = json.loads(headers_data)
                        except json.JSONDecodeError:
                            # Fallback to empty dict if JSON is invalid
                            headers = {}

                        queue_message = QueueMessage(
                            message_id=msg_id,
                            queue=queue,
                            payload=msg_data.get(b"payload", b""),
                            priority=MessagePriority(
                                int(msg_data.get(b"priority", MessagePriority.NORMAL)),
                            ),
                            headers=headers,
                        )

                        # Add to processing queue with visibility timeout
                        processing_key = f"{self._processing_key}:{msg_id}"
                        await client.setex(
                            processing_key,
                            int(visibility_timeout),
                            b"1",
                        )  # type: ignore[attr-defined]

                        self.logger.debug(f"Dequeued message {msg_id} from {queue}")
                        return queue_message
                elif timeout is not None:
                    # Wait a bit before trying again if there's a timeout
                    await asyncio.sleep(0.1)
                else:
                    # If no timeout and no results, return None
                    return None

            return None
        except Exception as e:
            self.logger.exception(f"Failed to dequeue message from queue {queue}")
            msg = f"Failed to dequeue from queue {queue}"
            raise MessagingOperationError(
                msg,
                original_error=e,
            ) from e

    async def acknowledge(
        self,
        queue: str,
        message_id: str,
    ) -> None:
        """Acknowledge successful processing of a message."""
        if not self._connected:
            await self.connect()

        client = await self._ensure_client()

        try:
            # Remove from processing queue
            processing_key = f"{self._processing_key}:{message_id}"
            await client.delete(processing_key)  # type: ignore[attr-defined]

            # Remove message data
            message_key = self._message_key.format(message_id=message_id)
            await client.delete(message_key)  # type: ignore[attr-defined]

            self.logger.debug(f"Acknowledged message {message_id} from {queue}")

        except Exception as e:
            self.logger.exception(f"Failed to acknowledge message {message_id}")
            msg = f"Failed to acknowledge message {message_id}"
            raise MessagingOperationError(
                msg,
                original_error=e,
            ) from e

    async def reject(
        self,
        queue: str,
        message_id: str,
        requeue: bool = True,
    ) -> None:
        """Reject a message, optionally requeuing it."""
        if not self._connected:
            await self.connect()

        client = await self._ensure_client()

        try:
            # Remove from processing queue
            processing_key = f"{self._processing_key}:{message_id}"
            await client.delete(processing_key)  # type: ignore[attr-defined]

            if requeue:
                # Just return message to main queue (retries handled by caller logic)
                queue_key = self._queue_key.format(topic=queue)
                # Re-add with normal priority
                await client.zadd(  # type: ignore[attr-defined]
                    queue_key,
                    {message_id: MessagePriority.NORMAL.value},
                )
                self.logger.debug(
                    f"Rejected and requeued message {message_id} to {queue}",
                )
            else:
                # Don't requeue - the message data will eventually expire
                self.logger.debug(
                    f"Rejected message {message_id} from {queue} (not requeued)",
                )

        except Exception as e:
            self.logger.exception(f"Failed to reject message {message_id}")
            msg = f"Failed to reject message {message_id}"
            raise MessagingOperationError(
                msg,
                original_error=e,
            ) from e

    async def purge_queue(self, queue: str) -> int:
        """Remove all messages from a Redis queue."""
        if not self._connected:
            await self.connect()

        client = await self._ensure_client()

        try:
            queue_key = self._queue_key.format(topic=queue)
            # Get all message IDs in the queue
            message_ids = await client.zrange(queue_key, 0, -1)  # type: ignore[attr-defined]

            # Delete all message data
            for msg_id in message_ids:
                message_key = self._message_key.format(message_id=msg_id.decode())
                await client.delete(message_key)  # type: ignore[attr-defined]

            # Delete the queue itself
            count = await client.delete(queue_key)  # type: ignore[attr-defined]

            self.logger.debug(f"Purged queue {queue}, removed {count} messages")
            return count

        except Exception as e:
            self.logger.exception(f"Failed to purge queue {queue}")
            msg = f"Failed to purge queue {queue}"
            raise MessagingOperationError(
                msg,
                original_error=e,
            ) from e

    async def get_queue_stats(self, queue: str) -> dict[str, t.Any]:
        """Get statistics for a Redis queue."""
        if not self._connected:
            await self.connect()

        client = await self._ensure_client()

        try:
            queue_key = self._queue_key.format(topic=queue)
            # Get queue length
            length = await client.zcard(queue_key)  # type: ignore[attr-defined]

            return {
                "queue": queue,
                "message_count": length,
                "timestamp": datetime.now(tz=UTC).isoformat(),
            }

        except Exception as e:
            self.logger.exception(f"Failed to get stats for queue {queue}")
            msg = f"Failed to get stats for queue {queue}"
            raise MessagingOperationError(
                msg,
                original_error=e,
            ) from e

    # ========================================================================
    # Lua Scripts and Background Processing
    # ========================================================================

    async def _load_lua_scripts(self) -> None:
        """Load Lua scripts for atomic operations."""
        # Implementation would go here

    async def _process_delayed_messages(self) -> None:
        """Background task to move delayed messages to their target queues."""
        # Implementation would go here
        while not self._shutdown_event.is_set():
            try:
                # Check for delayed messages ready to be moved
                await asyncio.sleep(1)  # Check every second
            except asyncio.CancelledError:
                break
