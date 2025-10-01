"""Redis Queue Backend Adapter for ACB.

High-performance Redis-backed queue implementation suitable for production
deployments with persistence, clustering, and horizontal scaling support.

Features:
    - Connection pooling with configurable limits
    - Priority queue support using Redis sorted sets
    - Delayed message delivery with timestamp-based scheduling
    - Dead letter queue for failed message handling
    - Batch operations for improved throughput
    - Pub/sub support for event-driven messaging
    - Atomic operations using Lua scripts
    - Health monitoring and automatic reconnection

Requirements:
    - Redis server (standalone or cluster)
    - coredis for async Redis client

Example:
    Basic task queue usage:

    ```python
    from acb.depends import depends
    from acb.adapters import import_adapter

    Queue = import_adapter("queue")


    @depends.inject
    async def process_tasks(queue: Queue = depends()):
        # Enqueue task with priority
        await queue.enqueue(
            "tasks", b"task payload", priority=MessagePriority.HIGH, delay_seconds=10
        )

        # Dequeue and process
        message = await queue.dequeue("tasks")
        if message:
            # Process task
            await queue.acknowledge(message)
    ```

    Pub/sub pattern:

    ```python
    # Publisher
    await queue.publish("events.user", b"user.created")

    # Subscriber
    async with queue.subscribe("events.*") as messages:
        async for message in messages:
            await process_event(message)
            await queue.acknowledge(message)
    ```

Author: Claude Code
Created: 2025-10-01
"""

import asyncio
import time
import typing as t
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from pydantic import Field
from acb.adapters import AdapterCapability, AdapterMetadata, AdapterStatus
from acb.config import Config
from acb.depends import depends

from ._base import (
    QueueBackend,
    QueueCapability,
    QueueConnectionError,
    QueueMessage,
    QueueOperationError,
    QueueSettings,
    QueueTimeoutError,
    generate_adapter_id,
)

# Lazy imports for coredis
_coredis_imports: dict[str, t.Any] = {}

MODULE_METADATA = AdapterMetadata(
    module_id=generate_adapter_id(),
    name="Redis Queue",
    category="queue",
    provider="redis",
    version="1.0.0",
    acb_min_version="0.19.0",
    author="Claude Code",
    created_date="2025-10-01",
    last_modified="2025-10-01",
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
    description="High-performance Redis queue backend with clustering support",
    settings_class="RedisQueueSettings",
    config_example={
        "connection_url": "redis://localhost:6379/0",
        "max_connections": 20,
        "key_prefix": "acb:queue",
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
                }
            )
        except ImportError as e:
            raise ImportError(
                "coredis is required for RedisQueue. "
                "Install with: pip install coredis>=4.0.0"
            ) from e

    return _coredis_imports


class RedisQueueSettings(QueueSettings):
    """Settings for Redis queue implementation."""

    # Redis connection
    connection_url: str | None = "redis://localhost:6379/0"
    key_prefix: str = "acb:queue"

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
    dead_letter_ttl: int = 604800  # 7 days

    @depends.inject
    def __init__(self, config: Config = depends(), **values: t.Any) -> None:
        super().__init__(**values)


class RedisQueue(QueueBackend):
    """Redis-backed queue implementation.

    Provides high-performance queue operations using Redis data structures:
    - Sorted sets for priority queues and delayed messages
    - Lists for FIFO queue operations
    - Pub/sub for event messaging
    - Hash maps for message metadata storage
    """

    config: Config

    def __init__(self, settings: RedisQueueSettings | None = None) -> None:
        """Initialize Redis queue backend.

        Args:
            settings: Redis queue configuration
        """
        super().__init__(settings)
        self._settings: RedisQueueSettings = settings or RedisQueueSettings()

        # Redis client and pool
        self._client: t.Any = None
        self._connection_pool: t.Any = None

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

    # ========================================================================
    # Connection Management (Private Implementation)
    # ========================================================================

    async def _ensure_client(self) -> t.Any:
        """Ensure Redis client is initialized (lazy initialization).

        Returns:
            Redis client instance

        Raises:
            QueueConnectionError: If connection fails
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
                                connection_pool=self._connection_pool
                            )
                        else:
                            self._client = imports["Redis"](
                                connection_pool=self._connection_pool
                            )

                        # Register for cleanup
                        self.register_resource(self._client)

                        # Test connection
                        await self._client.ping()

                        self.logger.debug("Redis connection established")

                    except Exception as e:
                        self.logger.exception(f"Failed to connect to Redis: {e}")
                        raise QueueConnectionError(
                            "Failed to establish Redis connection",
                            original_error=e,
                        ) from e

        return self._client

    async def _connect(self) -> None:
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
                self._process_delayed_messages()
            )

            self._connected = True
            self.logger.info("Redis queue backend connected")

    async def _disconnect(self) -> None:
        """Disconnect from Redis backend."""
        self._connected = False
        self._shutdown_event.set()

        # Cancel background tasks
        if self._delayed_processor_task:
            self._delayed_processor_task.cancel()
            try:
                await self._delayed_processor_task
            except asyncio.CancelledError:
                pass

        # Close pub/sub client if active
        if self._pubsub_client:
            try:
                await self._pubsub_client.close()
            except Exception:
                pass

        # Close main client
        if self._client:
            try:
                await self._client.close()
            except Exception:
                pass
            self._client = None

        # Close connection pool
        if self._connection_pool:
            try:
                await self._connection_pool.disconnect()
            except Exception:
                pass
            self._connection_pool = None

        # Cleanup resources
        await self.cleanup()

        self.logger.info("Redis queue backend disconnected")

    async def _health_check(self) -> dict[str, t.Any]:
        """Perform Redis health check.

        Returns:
            Health status information
        """
        try:
            client = await self._ensure_client()

            # Measure latency
            start_time = time.time()
            await client.ping()
            latency_ms = (time.time() - start_time) * 1000

            # Get Redis info
            info = await client.info()

            return {
                "healthy": True,
                "connected": self._connected,
                "latency_ms": latency_ms,
                "backend_info": {
                    "redis_version": info.get(b"redis_version", b"").decode(),
                    "used_memory": info.get(b"used_memory", 0),
                    "connected_clients": info.get(b"connected_clients", 0),
                    "uptime_seconds": info.get(b"uptime_in_seconds", 0),
                },
            }

        except Exception as e:
            self.logger.exception(f"Redis health check failed: {e}")
            return {
                "healthy": False,
                "connected": False,
                "error": str(e),
            }

    # ========================================================================
    # Lua Scripts
    # ========================================================================

    async def _load_lua_scripts(self) -> None:
        """Load Lua scripts for atomic operations."""
        client = await self._ensure_client()

        try:
            # Script for atomic enqueue with priority
            enqueue_script = """
            local queue_key = KEYS[1]
            local message_key = KEYS[2]
            local message_data = ARGV[1]
            local score = tonumber(ARGV[2])

            -- Store message data
            redis.call('SET', message_key, message_data)
            redis.call('EXPIRE', message_key, tonumber(ARGV[3]))

            -- Add to sorted set with score (timestamp + priority)
            redis.call('ZADD', queue_key, score, message_key)

            return 1
            """

            # Script for atomic dequeue
            dequeue_script = """
            local queue_key = KEYS[1]
            local processing_key = KEYS[2]
            local current_time = tonumber(ARGV[1])

            -- Get messages ready for processing
            local messages = redis.call('ZRANGEBYSCORE', queue_key, '-inf', current_time, 'LIMIT', 0, 1)

            if #messages == 0 then
                return nil
            end

            local message_key = messages[1]

            -- Move to processing atomically
            redis.call('ZREM', queue_key, message_key)
            redis.call('ZADD', processing_key, current_time, message_key)

            -- Get message data
            local message_data = redis.call('GET', message_key)
            return {message_key, message_data}
            """

            # Script for message acknowledgment
            ack_script = """
            local processing_key = KEYS[1]
            local message_key = ARGV[1]

            -- Remove from processing
            redis.call('ZREM', processing_key, message_key)

            -- Delete message data (or keep based on retention policy)
            redis.call('DEL', message_key)

            return 1
            """

            # Register scripts
            self._lua_scripts = {
                "enqueue": await client.script_load(enqueue_script.encode()),
                "dequeue": await client.script_load(dequeue_script.encode()),
                "ack": await client.script_load(ack_script.encode()),
            }

            self.logger.debug("Lua scripts loaded successfully")

        except Exception as e:
            self.logger.warning(f"Failed to load Lua scripts: {e}")
            self._settings.use_lua_scripts = False

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
            raise QueueConnectionError("Not connected to Redis")

        client = await self._ensure_client()
        timeout = timeout or self._settings.send_timeout

        try:
            # Serialize message
            message_data = message.to_bytes()
            message_key = self._message_key.format(message_id=message.message_id)

            # Calculate score for sorted set
            # Score = scheduled_time * 1M - priority (higher priority = lower score)
            scheduled_time = time.time()
            if message.delay_seconds > 0:
                scheduled_time += message.delay_seconds

            score = scheduled_time * 1_000_000 - message.priority.value

            # Determine target queue
            if message.delay_seconds > 0:
                queue_key = self._delayed_key
            else:
                queue_key = self._queue_key.format(topic=message.topic)

            # Use Lua script for atomic operation if available
            if self._settings.use_lua_scripts and "enqueue" in self._lua_scripts:
                await asyncio.wait_for(
                    client.evalsha(
                        self._lua_scripts["enqueue"],
                        3,
                        queue_key.encode(),
                        message_key.encode(),
                        message_data,
                        str(score).encode(),
                        str(self._settings.message_ttl).encode(),
                    ),
                    timeout=timeout,
                )
            else:
                # Use pipeline for atomic operation
                async with client.pipeline() as pipe:
                    await pipe.set(
                        message_key.encode(),
                        message_data,
                        ex=self._settings.message_ttl,
                    )
                    await pipe.zadd(queue_key.encode(), {message_key.encode(): score})
                    await asyncio.wait_for(pipe.execute(), timeout=timeout)

            self.logger.debug(
                f"Sent message {message.message_id} to queue {message.topic}"
            )
            return str(message.message_id)

        except TimeoutError as e:
            raise QueueTimeoutError(
                f"Send operation timed out after {timeout}s",
                original_error=e,
            ) from e
        except Exception as e:
            self.logger.exception(f"Failed to send message: {e}")
            raise QueueOperationError(
                "Failed to send message",
                original_error=e,
            ) from e

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
            raise QueueConnectionError("Not connected to Redis")

        client = await self._ensure_client()
        timeout = timeout or self._settings.receive_timeout
        queue_key = self._queue_key.format(topic=topic)

        try:
            current_time = time.time() * 1_000_000

            # Use Lua script for atomic operation if available
            if self._settings.use_lua_scripts and "dequeue" in self._lua_scripts:
                result = await asyncio.wait_for(
                    client.evalsha(
                        self._lua_scripts["dequeue"],
                        2,
                        queue_key.encode(),
                        self._processing_key.encode(),
                        str(current_time).encode(),
                    ),
                    timeout=timeout,
                )

                if result is None:
                    return None

                message_key, message_data = result
                return QueueMessage.from_bytes(message_data)

            else:
                # Manual atomic operation using WATCH
                messages = await client.zrangebyscore(
                    queue_key.encode(),
                    b"-inf",
                    str(current_time).encode(),
                    start=0,
                    num=1,
                )

                if not messages:
                    return None

                message_key = messages[0]

                # Move to processing
                async with client.pipeline() as pipe:
                    await pipe.zrem(queue_key.encode(), message_key)
                    await pipe.zadd(
                        self._processing_key.encode(),
                        {message_key: time.time()},
                    )
                    await pipe.get(message_key)
                    results = await asyncio.wait_for(pipe.execute(), timeout=timeout)

                message_data = results[-1]
                if message_data:
                    return QueueMessage.from_bytes(message_data)

                return None

        except TimeoutError:
            return None  # Timeout is expected for blocking receives
        except Exception as e:
            self.logger.exception(f"Failed to receive message: {e}")
            raise QueueOperationError(
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
        if not self._connected:
            raise QueueConnectionError("Not connected to Redis")

        client = await self._ensure_client()
        timeout = timeout or self._settings.ack_timeout
        message_key = self._message_key.format(message_id=message.message_id)

        try:
            # Use Lua script for atomic operation if available
            if self._settings.use_lua_scripts and "ack" in self._lua_scripts:
                await asyncio.wait_for(
                    client.evalsha(
                        self._lua_scripts["ack"],
                        1,
                        self._processing_key.encode(),
                        message_key.encode(),
                    ),
                    timeout=timeout,
                )
            else:
                # Manual operation
                async with client.pipeline() as pipe:
                    await pipe.zrem(self._processing_key.encode(), message_key.encode())
                    await pipe.delete(message_key.encode())
                    await asyncio.wait_for(pipe.execute(), timeout=timeout)

            self.logger.debug(f"Acknowledged message {message.message_id}")

        except Exception as e:
            self.logger.exception(f"Failed to acknowledge message: {e}")
            raise QueueOperationError(
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
        if not self._connected:
            raise QueueConnectionError("Not connected to Redis")

        client = await self._ensure_client()
        timeout = timeout or self._settings.ack_timeout
        message_key = self._message_key.format(message_id=message.message_id)

        try:
            async with client.pipeline() as pipe:
                # Remove from processing
                await pipe.zrem(self._processing_key.encode(), message_key.encode())

                if requeue and message.retry_count < message.max_retries:
                    # Increment retry count and requeue
                    message.retry_count += 1
                    queue_key = self._queue_key.format(topic=message.topic)
                    score = time.time() * 1_000_000 - message.priority.value

                    await pipe.set(
                        message_key.encode(),
                        message.to_bytes(),
                        ex=self._settings.message_ttl,
                    )
                    await pipe.zadd(queue_key.encode(), {message_key.encode(): score})
                else:
                    # Move to dead letter queue
                    await pipe.zadd(
                        self._dead_letter_key.encode(),
                        {message_key.encode(): time.time()},
                    )
                    await pipe.expire(
                        message_key.encode(), self._settings.dead_letter_ttl
                    )

                await asyncio.wait_for(pipe.execute(), timeout=timeout)

            self.logger.debug(
                f"Rejected message {message.message_id} (requeue={requeue})"
            )

        except Exception as e:
            self.logger.exception(f"Failed to reject message: {e}")
            raise QueueOperationError(
                "Failed to reject message",
                original_error=e,
            ) from e

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
        if not self._connected:
            raise QueueConnectionError("Not connected to Redis")

        client = await self._ensure_client()
        pubsub_channel = self._pubsub_key.format(topic=topic)

        # Create pub/sub client
        pubsub = client.pubsub()

        try:
            # Subscribe to channel/pattern
            if "*" in topic or "?" in topic:
                await pubsub.psubscribe(pubsub_channel.encode())
            else:
                await pubsub.subscribe(pubsub_channel.encode())

            async def message_generator() -> AsyncGenerator[QueueMessage]:
                """Generate messages from pub/sub."""
                try:
                    async for raw_message in pubsub.listen():
                        if raw_message[b"type"] in (b"message", b"pmessage"):
                            message_data = raw_message[b"data"]
                            try:
                                message = QueueMessage.from_bytes(message_data)
                                yield message
                            except Exception as e:
                                self.logger.warning(
                                    f"Failed to parse pub/sub message: {e}"
                                )
                except asyncio.CancelledError:
                    pass

            yield message_generator()

        finally:
            # Cleanup subscription
            try:
                await pubsub.unsubscribe()
                await pubsub.close()
            except Exception as e:
                self.logger.warning(f"Error closing pub/sub connection: {e}")

    # ========================================================================
    # Queue Management (Private Implementation)
    # ========================================================================

    async def _create_queue(
        self,
        name: str,
        **options: t.Any,
    ) -> None:
        """Create queue (private implementation).

        Redis queues are created implicitly on first use.
        This method is a no-op but included for interface compatibility.

        Args:
            name: Queue name
            **options: Backend-specific options
        """
        # Redis queues are created implicitly
        self.logger.debug(f"Queue {name} will be created on first use")

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
            raise QueueConnectionError("Not connected to Redis")

        client = await self._ensure_client()
        queue_key = self._queue_key.format(topic=name)

        try:
            if if_empty:
                size = await client.zcard(queue_key.encode())
                if size > 0:
                    raise QueueOperationError(f"Queue {name} is not empty")

            # Get all message keys and delete
            message_keys = await client.zrange(queue_key.encode(), 0, -1)

            async with client.pipeline() as pipe:
                for message_key in message_keys:
                    await pipe.delete(message_key)
                await pipe.delete(queue_key.encode())
                await pipe.execute()

            self.logger.info(f"Deleted queue {name}")

        except Exception as e:
            self.logger.exception(f"Failed to delete queue {name}: {e}")
            raise QueueOperationError(
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
            raise QueueConnectionError("Not connected to Redis")

        client = await self._ensure_client()
        queue_key = self._queue_key.format(topic=name)

        try:
            # Get all message keys
            message_keys = await client.zrange(queue_key.encode(), 0, -1)
            count = len(message_keys)

            if count > 0:
                async with client.pipeline() as pipe:
                    for message_key in message_keys:
                        await pipe.delete(message_key)
                    await pipe.delete(queue_key.encode())
                    await pipe.execute()

            self.logger.info(f"Purged {count} messages from queue {name}")
            return count

        except Exception as e:
            self.logger.exception(f"Failed to purge queue {name}: {e}")
            raise QueueOperationError(
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
            raise QueueConnectionError("Not connected to Redis")

        client = await self._ensure_client()
        queue_key = self._queue_key.format(topic=name)

        try:
            size = await client.zcard(queue_key.encode())
            return size

        except Exception as e:
            self.logger.exception(f"Failed to get queue size for {name}: {e}")
            raise QueueOperationError(
                f"Failed to get queue size for {name}",
                original_error=e,
            ) from e

    async def _list_queues(
        self,
        pattern: str | None = None,
    ) -> list[str]:
        """List queues (private implementation).

        Args:
            pattern: Optional filter pattern

        Returns:
            List of queue names

        Raises:
            QueueOperationError: If operation fails
        """
        if not self._connected:
            raise QueueConnectionError("Not connected to Redis")

        client = await self._ensure_client()

        try:
            # Build key pattern
            if pattern:
                key_pattern = self._queue_key.format(topic=pattern)
            else:
                key_pattern = self._queue_key.format(topic="*")

            # Get matching keys
            keys = await client.keys(key_pattern.encode())

            # Extract queue names
            prefix = self._queue_key.format(topic="").encode()
            queue_names = [
                key[len(prefix) :].decode() for key in keys if key.startswith(prefix)
            ]

            return sorted(queue_names)

        except Exception as e:
            self.logger.exception(f"Failed to list queues: {e}")
            raise QueueOperationError(
                "Failed to list queues",
                original_error=e,
            ) from e

    # ========================================================================
    # Background Tasks
    # ========================================================================

    async def _process_delayed_messages(self) -> None:
        """Background task to process delayed messages."""
        self.logger.debug("Started delayed message processor")

        while self._connected and not self._shutdown_event.is_set():
            try:
                client = await self._ensure_client()
                current_time = time.time() * 1_000_000

                # Get ready delayed messages
                messages = await client.zrangebyscore(
                    self._delayed_key.encode(),
                    b"-inf",
                    str(current_time).encode(),
                    start=0,
                    num=self._settings.batch_size,
                )

                if messages:
                    # Move messages to appropriate queues
                    for message_key in messages:
                        try:
                            # Get message data
                            message_data = await client.get(message_key)
                            if message_data:
                                message = QueueMessage.from_bytes(message_data)

                                # Calculate new score
                                score = time.time() * 1_000_000 - message.priority.value
                                queue_key = self._queue_key.format(topic=message.topic)

                                # Move atomically
                                async with client.pipeline() as pipe:
                                    await pipe.zrem(
                                        self._delayed_key.encode(), message_key
                                    )
                                    await pipe.zadd(
                                        queue_key.encode(), {message_key: score}
                                    )
                                    await pipe.execute()

                        except Exception as e:
                            self.logger.warning(
                                f"Failed to process delayed message: {e}"
                            )

                    self.logger.debug(
                        f"Processed {len(messages)} delayed messages to queues"
                    )

                # Sleep before next check
                await asyncio.sleep(1.0)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.exception(f"Error in delayed message processor: {e}")
                await asyncio.sleep(5.0)

        self.logger.debug("Stopped delayed message processor")

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def get_capabilities(self) -> list[QueueCapability]:
        """Get backend capabilities.

        Returns:
            List of supported capabilities
        """
        capabilities = [
            QueueCapability.BASIC_QUEUE,
            QueueCapability.PUB_SUB,
            QueueCapability.PRIORITY_QUEUE,
            QueueCapability.DELAYED_MESSAGES,
            QueueCapability.PERSISTENCE,
            QueueCapability.DEAD_LETTER_QUEUE,
            QueueCapability.CONNECTION_POOLING,
            QueueCapability.MESSAGE_TTL,
            QueueCapability.BATCH_OPERATIONS,
        ]

        if self._settings.enable_clustering:
            capabilities.extend(
                [
                    QueueCapability.CLUSTERING,
                    QueueCapability.LOAD_BALANCING,
                ]
            )

        return capabilities


# Factory function
def create_redis_queue(settings: RedisQueueSettings | None = None) -> RedisQueue:
    """Create a Redis queue instance.

    Args:
        settings: Queue settings

    Returns:
        RedisQueue instance
    """
    return RedisQueue(settings)
