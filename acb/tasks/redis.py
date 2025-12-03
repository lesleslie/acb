"""Redis-based queue implementation for ACB framework.

This module provides a Redis-backed task queue implementation suitable for
production deployments with persistence, clustering, and high availability.
"""

import json
import logging
import time
from uuid import UUID

import asyncio
import typing as t
from datetime import UTC, datetime
from typing import Any

try:
    import redis.asyncio as redis
    from redis.asyncio import ConnectionPool, Redis

    REDIS_AVAILABLE = True
except ImportError:
    redis = None  # type: ignore[assignment]
    Redis = None  # type: ignore[assignment,no-redef]
    ConnectionPool = None  # type: ignore[assignment,no-redef]
    REDIS_AVAILABLE = False

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
    name="Redis Queue",
    description="Redis-backed task queue for production deployments",
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
    ],
    max_throughput=10_000,  # tasks per second
    max_workers=1000,
    supports_clustering=True,
    required_packages=["redis>=5.0.0"],
    min_python_version="3.13",
    config_schema={
        "redis_url": {"type": "string", "default": "redis://localhost:6379/0"},
        "key_prefix": {"type": "string", "default": "acb:queue"},
        "max_connections": {"type": "integer", "default": 20},
        "connection_timeout": {"type": "number", "default": 5.0},
        "retry_on_timeout": {"type": "boolean", "default": True},
        "health_check_interval": {"type": "number", "default": 30.0},
    },
    default_settings={
        "redis_url": "redis://localhost:6379/0",
        "key_prefix": "acb:queue",
        "max_connections": 20,
        "connection_timeout": 5.0,
        "retry_on_timeout": True,
        "health_check_interval": 30.0,
    },
)


class RedisQueueSettings(QueueSettings):
    """Settings for Redis queue implementation."""

    # Redis connection
    redis_url: str = "redis://localhost:6379/0"
    key_prefix: str = "acb:queue"
    max_connections: int = 20
    connection_timeout: float = 5.0
    retry_on_timeout: bool = True

    # Advanced Redis settings
    socket_connect_timeout: float = 5.0
    socket_timeout: float = 5.0
    retry_on_error: list[type] = []
    max_retries: int = 3

    # Clustering
    enable_clustering: bool = False
    cluster_nodes: list[str] = []

    # Performance
    pipeline_size: int = 100
    use_lua_scripts: bool = True


class RedisQueue(QueueBase):
    """Redis-backed task queue implementation."""

    def __init__(self, settings: RedisQueueSettings | None = None) -> None:
        if not REDIS_AVAILABLE:
            msg = "Redis is required for RedisQueue. Install with: pip install redis>=5.0.0"
            raise ImportError(
                msg,
            )

        super().__init__(settings)
        self._settings = settings or RedisQueueSettings()

        # Redis connection
        self._redis: t.Any = None  # Redis | None when redis available
        self._connection_pool: t.Any = (
            None  # ConnectionPool | None when redis available
        )

        # Key patterns
        self._key_prefix = self._settings.key_prefix
        self._queue_key = f"{self._key_prefix}:queues:{{queue_name}}"
        self._delayed_key = f"{self._key_prefix}:delayed"
        self._processing_key = f"{self._key_prefix}:processing"
        self._dead_letter_key = f"{self._key_prefix}:dead_letter"
        self._task_data_key = f"{self._key_prefix}:tasks:{{task_id}}"
        self._task_result_key = f"{self._key_prefix}:results:{{task_id}}"
        self._metrics_key = f"{self._key_prefix}:metrics"

        # Lua scripts for atomic operations
        self._lua_scripts: dict[str, Any] = {}

        # Background tasks
        self._delayed_task_processor: asyncio.Task[None] | None = None
        self._health_monitor: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the Redis queue."""
        await self._ensure_redis()
        await self._load_lua_scripts()
        await super().start()

        # Start delayed task processor
        self._delayed_task_processor = asyncio.create_task(
            self._process_delayed_tasks(),
        )

        # Start health monitor
        self._health_monitor = asyncio.create_task(self._health_monitor_loop())

        self.logger.info("Redis queue started")

    async def stop(self) -> None:
        """Stop the Redis queue."""
        # Stop background tasks
        if self._delayed_task_processor:
            self._delayed_task_processor.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._delayed_task_processor

        if self._health_monitor:
            self._health_monitor.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._health_monitor

        await super().stop()

        # Close Redis connection
        if self._redis:
            await self._redis.aclose()
            self._redis = None

        if self._connection_pool:
            await self._connection_pool.aclose()
            self._connection_pool = None

        self.logger.info("Redis queue stopped")

    async def _ensure_redis(self) -> t.Any:
        """Ensure Redis connection is available."""
        if self._redis is None:
            # Create connection pool
            self._connection_pool = redis.ConnectionPool.from_url(
                self._settings.redis_url,
                max_connections=self._settings.max_connections,
                socket_connect_timeout=self._settings.socket_connect_timeout,
                socket_timeout=self._settings.socket_timeout,
                retry_on_timeout=self._settings.retry_on_timeout,
            )

            # Create Redis client
            self._redis = Redis(  # type: ignore[abstract]
                connection_pool=self._connection_pool,
                decode_responses=True,
            )

            # Test connection
            try:
                await self._redis.ping()
                self.logger.debug("Redis connection established")
            except Exception as e:
                self.logger.exception(f"Failed to connect to Redis: {e}")
                raise

        return self._redis

    async def _load_lua_scripts(self) -> None:
        """Load Lua scripts for atomic operations."""
        if not self._settings.use_lua_scripts:
            return

        redis_client = await self._ensure_redis()

        # Script for atomic enqueue with priority
        enqueue_script = """
        local queue_key = KEYS[1]
        local task_data_key = KEYS[2]
        local metrics_key = KEYS[3]
        local task_data = ARGV[1]
        local priority = tonumber(ARGV[2])
        local scheduled_time = tonumber(ARGV[3])

        -- Store task data
        redis.call('SET', task_data_key, task_data)

        -- Add to queue with priority and timestamp
        local score = scheduled_time * 1000000 - priority
        redis.call('ZADD', queue_key, score, task_data_key)

        -- Update metrics
        redis.call('HINCRBY', metrics_key, 'pending_tasks', 1)
        redis.call('HINCRBY', metrics_key, 'total_enqueued', 1)

        return 1
        """

        # Script for atomic dequeue
        dequeue_script = """
        local queue_key = KEYS[1]
        local processing_key = KEYS[2]
        local metrics_key = KEYS[3]
        local current_time = tonumber(ARGV[1])

        -- Get tasks ready for processing
        local tasks = redis.call('ZRANGEBYSCORE', queue_key, '-inf', current_time, 'LIMIT', 0, 1)

        if #tasks == 0 then
            return nil
        end

        local task_key = tasks[1]

        -- Move from queue to processing
        redis.call('ZREM', queue_key, task_key)
        redis.call('ZADD', processing_key, current_time, task_key)

        -- Update metrics
        redis.call('HINCRBY', metrics_key, 'pending_tasks', -1)
        redis.call('HINCRBY', metrics_key, 'processing_tasks', 1)

        -- Get task data
        local task_data = redis.call('GET', task_key)
        return {task_key, task_data}
        """

        # Script for task completion
        complete_script = """
        local processing_key = KEYS[1]
        local result_key = KEYS[2]
        local metrics_key = KEYS[3]
        local task_key = ARGV[1]
        local result_data = ARGV[2]
        local success = tonumber(ARGV[3])

        -- Remove from processing
        redis.call('ZREM', processing_key, task_key)

        -- Store result
        redis.call('SET', result_key, result_data)
        redis.call('EXPIRE', result_key, 86400)  -- 24 hours

        -- Update metrics
        redis.call('HINCRBY', metrics_key, 'processing_tasks', -1)
        if success == 1 then
            redis.call('HINCRBY', metrics_key, 'completed_tasks', 1)
        else
            redis.call('HINCRBY', metrics_key, 'failed_tasks', 1)
        end

        return 1
        """

        try:
            self._lua_scripts = {
                "enqueue": redis_client.register_script(enqueue_script),
                "dequeue": redis_client.register_script(dequeue_script),
                "complete": redis_client.register_script(complete_script),
            }
            self.logger.debug("Lua scripts loaded")
        except Exception as e:
            self.logger.warning(f"Failed to load Lua scripts: {e}")
            self._settings.use_lua_scripts = False

    async def enqueue(self, task: TaskData) -> str:
        """Enqueue a task for processing."""
        if not self._running:
            msg = "Queue is not running"
            raise RuntimeError(msg)

        redis_client = await self._ensure_redis()

        # Serialize task data
        task_json = task.model_dump_json()

        # Calculate scheduled time
        scheduled_time = time.time()
        if task.delay > 0:
            scheduled_time += task.delay
        elif task.scheduled_at:
            scheduled_time = task.scheduled_at.timestamp()

        # Generate keys
        task_key = self._task_data_key.format(task_id=task.task_id)

        try:
            if self._settings.use_lua_scripts and "enqueue" in self._lua_scripts:
                # Use atomic Lua script
                queue_key = self._queue_key.format(queue_name=task.queue_name)
                await self._lua_scripts["enqueue"](
                    keys=[queue_key, task_key, self._metrics_key],
                    args=[task_json, task.priority.value, scheduled_time],
                )
            else:
                # Use pipeline for atomic operation
                pipe = redis_client.pipeline()

                # Store task data
                pipe.set(task_key, task_json)

                # Add to appropriate queue
                if scheduled_time > time.time():
                    # Delayed task
                    pipe.zadd(self._delayed_key, {task_key: scheduled_time})
                else:
                    # Immediate task with priority
                    queue_key = self._queue_key.format(queue_name=task.queue_name)
                    score = scheduled_time * 1_000_000 - task.priority.value
                    pipe.zadd(queue_key, {task_key: score})

                # Update metrics
                pipe.hincrby(self._metrics_key, "pending_tasks", 1)
                pipe.hincrby(self._metrics_key, "total_enqueued", 1)

                await pipe.execute()

            self.logger.debug(
                f"Enqueued task {task.task_id} to queue {task.queue_name}",
            )
            return str(task.task_id)

        except Exception as e:
            self.logger.exception(f"Failed to enqueue task {task.task_id}: {e}")
            raise

    async def _resolve_queue_keys(
        self,
        redis_client: t.Any,
        queue_name: str | None,
    ) -> list[str]:
        """Resolve which queue keys to check for dequeue."""
        if queue_name:
            return [self._queue_key.format(queue_name=queue_name)]

        pattern = self._queue_key.format(queue_name="*")
        return await redis_client.keys(pattern)

    async def _dequeue_with_lua(
        self,
        queue_key: str,
        current_time: float,
    ) -> TaskData | None:
        """Dequeue using Lua script for atomic operation."""
        result = await self._lua_scripts["dequeue"](
            keys=[queue_key, self._processing_key, self._metrics_key],
            args=[current_time],
        )

        if not result:
            return None

        _task_key, task_data = result
        return TaskData.model_validate_json(task_data)

    async def _dequeue_manual(
        self,
        redis_client: t.Any,
        queue_key: str,
        current_time: float,
    ) -> TaskData | None:
        """Dequeue using manual pipeline operations."""
        # Get task ready for processing
        tasks = await redis_client.zrangebyscore(
            queue_key,
            "-inf",
            current_time,
            start=0,
            num=1,
        )

        if not tasks:
            return None

        task_key = tasks[0]

        # Move to processing atomically
        pipe = redis_client.pipeline()
        pipe.zrem(queue_key, task_key)
        pipe.zadd(self._processing_key, {task_key: current_time})
        pipe.hincrby(self._metrics_key, "pending_tasks", -1)
        pipe.hincrby(self._metrics_key, "processing_tasks", 1)
        pipe.get(task_key)

        results = await pipe.execute()
        task_data = results[-1]

        if not task_data:
            return None

        task = TaskData.model_validate_json(task_data)
        self.logger.debug(f"Dequeued task {task.task_id}")
        return task

    async def _try_dequeue_from_queues(
        self,
        queue_keys: list[str],
        current_time: float,
        redis_client: t.Any,
    ) -> TaskData | None:
        """Try to dequeue from multiple queue keys."""
        use_lua = self._settings.use_lua_scripts and "dequeue" in self._lua_scripts

        for queue_key in queue_keys:
            if use_lua:
                task = await self._dequeue_with_lua(queue_key, current_time)
            else:
                task = await self._dequeue_manual(redis_client, queue_key, current_time)

            if task:
                return task

        return None

    async def dequeue(self, queue_name: str | None = None) -> TaskData | None:
        """Dequeue a task for processing."""
        if not self._running:
            return None

        redis_client = await self._ensure_redis()
        current_time = time.time()

        try:
            queue_keys = await self._resolve_queue_keys(redis_client, queue_name)
            return await self._try_dequeue_from_queues(
                queue_keys,
                current_time,
                redis_client,
            )
        except Exception as e:
            self.logger.exception(f"Failed to dequeue task: {e}")
            return None

    async def _check_result_storage(
        self,
        redis_client: t.Any,
        task_id: UUID,
    ) -> TaskResult | None:
        """Check if task result exists in storage."""
        result_key = self._task_result_key.format(task_id=task_id)
        result_data = await redis_client.get(result_key)

        if result_data:
            return TaskResult.model_validate_json(result_data)

        return None

    async def _check_processing_status(
        self,
        redis_client: t.Any,
        task_id: UUID,
        task_key: str,
    ) -> TaskResult | None:
        """Check if task is currently being processed."""
        processing_score = await redis_client.zscore(self._processing_key, task_key)

        if processing_score is None:
            return None

        task_data = await redis_client.get(task_key)
        if not task_data:
            return None

        task = TaskData.model_validate_json(task_data)
        return TaskResult(
            task_id=task_id,
            status=TaskStatus.PROCESSING,
            queue_name=task.queue_name,
            started_at=datetime.fromtimestamp(processing_score),
        )

    async def _check_pending_queues(
        self,
        redis_client: t.Any,
        task_id: UUID,
        task_key: str,
    ) -> TaskResult | None:
        """Check if task is pending in any queue."""
        queue_pattern = self._queue_key.format(queue_name="*")
        queue_keys = await redis_client.keys(queue_pattern)
        queue_keys.append(self._delayed_key)

        for key in queue_keys:
            score = await redis_client.zscore(key, task_key)
            if score is None:
                continue

            task_data = await redis_client.get(task_key)
            if not task_data:
                continue

            task = TaskData.model_validate_json(task_data)
            return TaskResult(
                task_id=task_id,
                status=TaskStatus.PENDING,
                queue_name=task.queue_name,
            )

        return None

    async def get_task_status(self, task_id: UUID) -> TaskResult | None:
        """Get task status and result."""
        redis_client = await self._ensure_redis()

        try:
            # Check for completed result
            result = await self._check_result_storage(redis_client, task_id)
            if result:
                return result

            # Check if processing
            task_key = self._task_data_key.format(task_id=task_id)
            result = await self._check_processing_status(
                redis_client,
                task_id,
                task_key,
            )
            if result:
                return result

            # Check pending queues
            return await self._check_pending_queues(redis_client, task_id, task_key)

        except Exception as e:
            self.logger.exception(f"Failed to get task status for {task_id}: {e}")
            return None

    async def cancel_task(self, task_id: UUID) -> bool:
        """Cancel a pending task."""
        redis_client = await self._ensure_redis()
        task_key = self._task_data_key.format(task_id=task_id)

        try:
            pipe = redis_client.pipeline()

            # Remove from all possible locations
            queue_pattern = self._queue_key.format(queue_name="*")
            queue_keys = await redis_client.keys(queue_pattern)
            queue_keys.append(self._delayed_key)

            removed = False
            for key in queue_keys:
                zrem_result = await redis_client.zrem(key, task_key)
                if zrem_result > 0:
                    removed = True
                    break

            if removed:
                # Create cancelled result
                task_result = TaskResult(
                    task_id=task_id,
                    status=TaskStatus.CANCELLED,
                    completed_at=datetime.now(tz=UTC),
                )

                result_key = self._task_result_key.format(task_id=task_id)
                pipe.set(result_key, task_result.model_dump_json())
                pipe.expire(result_key, 86400)  # 24 hours
                pipe.hincrby(self._metrics_key, "pending_tasks", -1)

                await pipe.execute()

                self.logger.debug(f"Cancelled task {task_id}")
                return True

            return False

        except Exception as e:
            self.logger.exception(f"Failed to cancel task {task_id}: {e}")
            return False

    async def get_queue_info(self, queue_name: str) -> dict[str, Any]:
        """Get information about a queue."""
        redis_client = await self._ensure_redis()
        queue_key = self._queue_key.format(queue_name=queue_name)

        try:
            # Get queue size
            queue_size = await redis_client.zcard(queue_key)

            # Get oldest and newest tasks
            oldest = await redis_client.zrange(queue_key, 0, 0, withscores=True)
            newest = await redis_client.zrange(queue_key, -1, -1, withscores=True)

            return {
                "name": queue_name,
                "pending_tasks": queue_size,
                "oldest_task_score": oldest[0][1] if oldest else None,
                "newest_task_score": newest[0][1] if newest else None,
            }

        except Exception as e:
            self.logger.exception(f"Failed to get queue info for {queue_name}: {e}")
            return {"name": queue_name, "error": str(e)}

    async def purge_queue(self, queue_name: str) -> int:
        """Remove all tasks from a queue."""
        redis_client = await self._ensure_redis()
        queue_key = self._queue_key.format(queue_name=queue_name)

        try:
            # Get all tasks in queue
            tasks = await redis_client.zrange(queue_key, 0, -1)
            task_count = len(tasks)

            if task_count > 0:
                pipe = redis_client.pipeline()

                # Remove queue
                pipe.delete(queue_key)

                # Remove task data
                for task_key in tasks:
                    pipe.delete(task_key)

                # Update metrics
                pipe.hincrby(self._metrics_key, "pending_tasks", -task_count)

                await pipe.execute()

                self.logger.info(f"Purged {task_count} tasks from queue {queue_name}")

            return task_count

        except Exception as e:
            self.logger.exception(f"Failed to purge queue {queue_name}: {e}")
            return 0

    async def list_queues(self) -> list[str]:
        """List all available queues."""
        redis_client = await self._ensure_redis()

        try:
            pattern = self._queue_key.format(queue_name="*")
            queue_keys = await redis_client.keys(pattern)

            # Extract queue names from keys
            prefix = self._queue_key.format(queue_name="")
            queue_names = []
            for key in queue_keys:
                if key.startswith(prefix):
                    queue_name = key[len(prefix) :]
                    queue_names.append(queue_name)

            return sorted(queue_names)

        except Exception as e:
            self.logger.exception(f"Failed to list queues: {e}")
            return []

    def _build_dead_letter_data(
        self,
        task: TaskData,
        result: TaskResult,
    ) -> dict[str, t.Any]:
        """Build dead letter data structure."""
        return {
            "task": task.model_dump(),
            "result": result.model_dump(),
            "timestamp": time.time(),
        }

    def _configure_dead_letter_pipeline(
        self,
        pipe: t.Any,
        task_key: str,
        dead_letter_data: dict[str, t.Any],
    ) -> None:
        """Configure pipeline operations for dead letter storage."""
        # Store in dead letter queue
        pipe.zadd(self._dead_letter_key, {task_key: time.time()})
        pipe.set(f"{task_key}:dead_letter", json.dumps(dead_letter_data))
        pipe.expire(f"{task_key}:dead_letter", self._settings.dead_letter_ttl)

        # Remove from processing
        pipe.zrem(self._processing_key, task_key)

        # Update metrics
        pipe.hincrby(self._metrics_key, "processing_tasks", -1)
        pipe.hincrby(self._metrics_key, "dead_letter_tasks", 1)

    async def _store_dead_letter_task(self, task: TaskData, result: TaskResult) -> None:
        """Store task in dead letter queue."""
        redis_client = await self._ensure_redis()

        try:
            dead_letter_data = self._build_dead_letter_data(task, result)
            task_key = self._task_data_key.format(task_id=task.task_id)

            pipe = redis_client.pipeline()
            self._configure_dead_letter_pipeline(pipe, task_key, dead_letter_data)
            await pipe.execute()

        except Exception as e:
            self.logger.exception(
                f"Failed to store dead letter task {task.task_id}: {e}",
            )

    async def _move_task_to_queue(
        self,
        redis_client: t.Any,
        task_key: str,
        current_time: float,
    ) -> tuple[str, float] | None:
        """Move a single delayed task to its appropriate queue.

        Returns:
            Tuple of (queue_key, score) if successful, None otherwise
        """
        task_data = await redis_client.get(task_key)
        if not task_data:
            return None

        task = TaskData.model_validate_json(task_data)
        queue_key = self._queue_key.format(queue_name=task.queue_name)
        score = current_time * 1_000_000 - task.priority.value
        return (queue_key, score)

    async def _process_ready_delayed_tasks(
        self,
        redis_client: t.Any,
        ready_tasks: list[str],
        current_time: float,
    ) -> None:
        """Process a batch of ready delayed tasks."""
        pipe = redis_client.pipeline()

        for task_key in ready_tasks:
            result = await self._move_task_to_queue(
                redis_client,
                task_key,
                current_time,
            )
            if result:
                queue_key, score = result
                pipe.zadd(queue_key, {task_key: score})
                pipe.zrem(self._delayed_key, task_key)

        await pipe.execute()
        self.logger.debug(f"Moved {len(ready_tasks)} delayed tasks to queues")

    async def _process_delayed_tasks(self) -> None:
        """Process delayed tasks in background."""
        redis_client = await self._ensure_redis()

        while self._running and not self._shutdown_event.is_set():
            try:
                current_time = time.time()

                # Get ready delayed tasks
                ready_tasks = await redis_client.zrangebyscore(
                    self._delayed_key,
                    "-inf",
                    current_time,
                    start=0,
                    num=100,
                )

                if ready_tasks:
                    await self._process_ready_delayed_tasks(
                        redis_client,
                        ready_tasks,
                        current_time,
                    )

                await asyncio.sleep(1.0)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.exception(f"Delayed task processor error: {e}")
                await asyncio.sleep(5.0)

    async def _health_monitor_loop(self) -> None:
        """Monitor Redis connection health."""
        while self._running and not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(self._settings.health_check_interval)

                # Ping Redis
                redis_client = await self._ensure_redis()
                await redis_client.ping()

                # Update metrics
                await self._update_redis_metrics()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.exception(f"Redis health monitor error: {e}")
                # Try to reconnect
                if self._redis:
                    with contextlib.suppress(Exception):
                        await self._redis.aclose()
                    self._redis = None

    async def _update_redis_metrics(self) -> None:
        """Update metrics from Redis."""
        redis_client = await self._ensure_redis()

        try:
            # Get metrics from Redis
            metrics_data = await redis_client.hgetall(self._metrics_key)

            if metrics_data:
                self._metrics.pending_tasks = int(metrics_data.get("pending_tasks", 0))
                self._metrics.processing_tasks = int(
                    metrics_data.get("processing_tasks", 0),
                )
                self._metrics.completed_tasks = int(
                    metrics_data.get("completed_tasks", 0),
                )
                self._metrics.failed_tasks = int(metrics_data.get("failed_tasks", 0))
                self._metrics.dead_letter_tasks = int(
                    metrics_data.get("dead_letter_tasks", 0),
                )

            # Update queue depth
            self._metrics.queue_depth = self._metrics.pending_tasks

            # Update last activity
            self._metrics.last_task_processed = datetime.now(tz=UTC)

        except Exception as e:
            self.logger.exception(f"Failed to update Redis metrics: {e}")

    async def _on_task_completed(self, task: TaskData, result: TaskResult) -> None:
        """Handle task completion."""
        await super()._on_task_completed(task, result)

        redis_client = await self._ensure_redis()

        try:
            if self._settings.use_lua_scripts and "complete" in self._lua_scripts:
                # Use atomic Lua script
                task_key = self._task_data_key.format(task_id=task.task_id)
                result_key = self._task_result_key.format(task_id=task.task_id)

                await self._lua_scripts["complete"](
                    keys=[self._processing_key, result_key, self._metrics_key],
                    args=[task_key, result.model_dump_json(), 1],
                )
            else:
                # Manual operation
                pipe = redis_client.pipeline()

                task_key = self._task_data_key.format(task_id=task.task_id)
                result_key = self._task_result_key.format(task_id=task.task_id)

                # Remove from processing
                pipe.zrem(self._processing_key, task_key)

                # Store result
                pipe.set(result_key, result.model_dump_json())
                pipe.expire(result_key, 86400)  # 24 hours

                # Update metrics
                pipe.hincrby(self._metrics_key, "processing_tasks", -1)
                pipe.hincrby(self._metrics_key, "completed_tasks", 1)

                await pipe.execute()

        except Exception as e:
            self.logger.exception(
                f"Failed to handle task completion for {task.task_id}: {e}",
            )

    async def _on_task_failed(self, task: TaskData, result: TaskResult) -> None:
        """Handle task failure."""
        await super()._on_task_failed(task, result)

        redis_client = await self._ensure_redis()

        try:
            if self._settings.use_lua_scripts and "complete" in self._lua_scripts:
                # Use atomic Lua script
                task_key = self._task_data_key.format(task_id=task.task_id)
                result_key = self._task_result_key.format(task_id=task.task_id)

                await self._lua_scripts["complete"](
                    keys=[self._processing_key, result_key, self._metrics_key],
                    args=[task_key, result.model_dump_json(), 0],
                )
            else:
                # Manual operation
                pipe = redis_client.pipeline()

                task_key = self._task_data_key.format(task_id=task.task_id)
                result_key = self._task_result_key.format(task_id=task.task_id)

                # Store result
                pipe.set(result_key, result.model_dump_json())
                pipe.expire(result_key, 86400)  # 24 hours

                # Update metrics
                pipe.hincrby(self._metrics_key, "failed_tasks", 1)

                await pipe.execute()

        except Exception as e:
            self.logger.exception(
                f"Failed to handle task failure for {task.task_id}: {e}",
            )

    async def health_check(self) -> dict[str, Any]:
        """Perform health check."""
        base_health = await super().health_check()

        try:
            redis_client = await self._ensure_redis()

            # Test Redis connection
            start_time = time.time()
            await redis_client.ping()
            latency = (time.time() - start_time) * 1000  # ms

            # Get Redis info
            redis_info = await redis_client.info()

            redis_health = {
                "connected": True,
                "latency_ms": latency,
                "redis_version": redis_info.get("redis_version"),
                "used_memory": redis_info.get("used_memory"),
                "connected_clients": redis_info.get("connected_clients"),
                "total_commands_processed": redis_info.get("total_commands_processed"),
            }

            base_health["redis"] = redis_health

        except Exception as e:
            base_health["redis"] = {
                "connected": False,
                "error": str(e),
            }
            base_health["healthy"] = False

        return base_health


# Factory function
def create_redis_queue(settings: RedisQueueSettings | None = None) -> RedisQueue:
    """Create a Redis queue instance.

    Args:
        settings: Queue settings

    Returns:
        RedisQueue instance
    """
    return RedisQueue(settings)
