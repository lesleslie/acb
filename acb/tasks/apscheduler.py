"""APScheduler-based queue adapter for persistent, distributed scheduling.

This adapter integrates APScheduler 3.x with ACB's queue system, providing:
- Persistent job storage (SQL, MongoDB, Redis)
- Distributed scheduling with clustering support
- Advanced missed-run handling strategies
- Rich event system for monitoring
- Runtime job modification capabilities
"""

# Avoid static imports for optional APScheduler dependency
import importlib
import importlib.util as _il_util
import logging
from uuid import UUID, uuid4

import typing as t
from datetime import UTC, datetime

AsyncIOScheduler = t.Any
CronTrigger = t.Any
DateTrigger = t.Any
IntervalTrigger = t.Any
APSCHEDULER_AVAILABLE = _il_util.find_spec("apscheduler") is not None


from ._base import (
    QueueBase,
    QueueCapability,
    QueueMetadata,
    QueueSettings,
    TaskData,
    TaskHandler,
    TaskResult,
    TaskStatus,
)

logger = logging.getLogger(__name__)


class APSchedulerSettings(QueueSettings):
    """APScheduler-specific queue settings."""

    # === Job Store Configuration ===
    job_store_type: str = "memory"  # memory, sqlalchemy, mongodb, redis
    job_store_url: str | None = None  # Connection URL for persistent stores

    # SQLAlchemy-specific
    sqlalchemy_engine_options: dict[str, t.Any] = {}  # e.g., pool_size, max_overflow
    sqlalchemy_tablename: str = "apscheduler_jobs"
    sqlalchemy_pickle_protocol: int = 2

    # MongoDB-specific
    mongodb_database: str = "apscheduler"
    mongodb_collection: str = "jobs"
    mongodb_client_options: dict[str, t.Any] = {}

    # Redis-specific
    redis_jobs_key: str = "apscheduler.jobs"
    redis_run_times_key: str = "apscheduler.run_times"
    redis_client_options: dict[str, t.Any] = {}

    # === Executor Configuration ===
    executor_type: str = "asyncio"  # asyncio, thread, process
    thread_pool_max_workers: int = 20
    process_pool_max_workers: int = 5

    # === Clustering Configuration ===
    enable_clustering: bool = False
    cluster_id: str | None = None  # Unique identifier for this scheduler instance

    # === Missed Job Handling ===
    misfire_grace_time: int = 3600  # Default grace time in seconds (1 hour)
    coalesce: bool = True  # Combine multiple missed runs into one
    max_instances: int = 1  # Maximum concurrent instances per job

    # === Job Defaults ===
    default_jobstore: str = "default"
    default_executor: str = "default"
    replace_existing: bool = True  # Replace job if already exists with same ID

    # === Scheduler Configuration ===
    timezone: str = "UTC"  # Timezone for scheduler
    job_defaults: dict[str, t.Any] = {}  # Default job settings
    job_lookup_interval: float = 1.0  # How often to check for due jobs (seconds)

    # === Event System ===
    enable_event_listeners: bool = True
    event_mask: int | None = None  # Bitmask for specific events

    # === Performance Tuning ===
    max_job_instances: int = 3  # Global max instances across all jobs
    job_result_cache_size: int = 1000  # Number of job results to keep in memory


MODULE_METADATA = QueueMetadata(
    queue_id=UUID("01940000-0000-7000-8000-000000000002"),  # Static UUID7
    name="APScheduler Queue",
    description="Production-grade queue adapter with job persistence, distributed scheduling, and advanced missed-run handling via APScheduler",
    version="1.0.0",
    capabilities=[
        QueueCapability.PRIORITY_QUEUE,
        QueueCapability.DELAYED_TASKS,
        QueueCapability.CRON_SCHEDULING,
        QueueCapability.PERSISTENCE,
        QueueCapability.HORIZONTAL_SCALING,
        QueueCapability.TASK_TRACKING,
        QueueCapability.METRICS_COLLECTION,
    ],
    max_throughput=None,  # Depends on job store backend
    max_workers=None,  # Configurable via executor settings
    supports_clustering=True,
    required_packages=["apscheduler>=3.10.0"],
    min_python_version="3.13",
)


class Queue(QueueBase):
    """APScheduler-based queue adapter for persistent, distributed scheduling."""

    def __init__(self, settings: APSchedulerSettings | None = None) -> None:
        if not APSCHEDULER_AVAILABLE:
            msg = "APScheduler is required for APSchedulerQueue. Install with: pip install apscheduler"
            raise ImportError(msg)

        super().__init__(settings)

        self._scheduler: AsyncIOScheduler | None = None
        self._job_stores: dict[str, t.Any] = {}
        self._executors: dict[str, t.Any] = {}
        self._job_results: dict[str, TaskResult] = {}  # Track job results
        self._dead_letter_tasks: dict[UUID, tuple[TaskData, TaskResult]] = {}

    @property
    def settings(self) -> APSchedulerSettings:
        """Get APScheduler-specific settings."""
        if not isinstance(self._settings, APSchedulerSettings):
            self._settings = APSchedulerSettings()
        return self._settings  # type: ignore[return-value]

    # === Lazy Initialization ===

    async def _ensure_scheduler(self) -> AsyncIOScheduler:
        """Lazy initialization pattern - ACB standard."""
        if self._scheduler is None:
            self._scheduler = await self._create_scheduler()
        return self._scheduler

    async def _create_scheduler(self) -> AsyncIOScheduler:
        """Create APScheduler instance with ACB configuration."""
        # Create job stores
        self._job_stores = self._create_job_stores()

        # Create executors
        self._executors = self._create_executors()

        # Initialize scheduler
        aio_sched_mod = importlib.import_module("apscheduler.schedulers.asyncio")
        AsyncIOSchedulerClass = aio_sched_mod.AsyncIOScheduler
        scheduler = AsyncIOSchedulerClass(
            jobstores=self._job_stores,
            executors=self._executors,
            job_defaults=self.settings.job_defaults
            or {
                "coalesce": self.settings.coalesce,
                "max_instances": self.settings.max_instances,
                "misfire_grace_time": self.settings.misfire_grace_time,
            },
            timezone=self.settings.timezone,
        )

        # Register event listeners
        if self.settings.enable_event_listeners:
            self._setup_event_listeners(scheduler)

        # Register for cleanup - CleanupMixin pattern
        self.register_resource(scheduler)

        return scheduler

    # === Job Store Creation ===

    def _create_job_stores(self) -> dict[str, t.Any]:
        """Create job store based on settings."""
        stores = {}

        if self.settings.job_store_type == "memory":
            memory_mod = importlib.import_module("apscheduler.jobstores.memory")
            MemoryJobStore = memory_mod.MemoryJobStore

            stores["default"] = MemoryJobStore()

        elif self.settings.job_store_type == "sqlalchemy":
            sqlalchemy_mod = importlib.import_module(
                "apscheduler.jobstores.sqlalchemy",
            )
            SQLAlchemyJobStore = sqlalchemy_mod.SQLAlchemyJobStore

            if not self.settings.job_store_url:
                msg = "job_store_url required for SQLAlchemy job store"
                raise ValueError(msg)

            stores["default"] = SQLAlchemyJobStore(
                url=self.settings.job_store_url,
                tablename=self.settings.sqlalchemy_tablename,
                engine_options=self.settings.sqlalchemy_engine_options,
                pickle_protocol=self.settings.sqlalchemy_pickle_protocol,
            )

        elif self.settings.job_store_type == "mongodb":
            pymongo = importlib.import_module("pymongo")
            mongodb_mod = importlib.import_module("apscheduler.jobstores.mongodb")
            MongoDBJobStore = mongodb_mod.MongoDBJobStore

            client_options = self.settings.mongodb_client_options.copy()
            # Extract connection URL if provided in job_store_url
            if self.settings.job_store_url:
                mongo_client = pymongo.MongoClient(
                    self.settings.job_store_url,
                    **client_options,
                )
            else:
                mongo_client = pymongo.MongoClient(**client_options)

            stores["default"] = MongoDBJobStore(
                client=mongo_client,
                database=self.settings.mongodb_database,
                collection=self.settings.mongodb_collection,
            )

        elif self.settings.job_store_type == "redis":
            redis = importlib.import_module("redis")
            redis_mod = importlib.import_module("apscheduler.jobstores.redis")
            RedisJobStore = redis_mod.RedisJobStore

            # Extract connection parameters if URL provided
            if self.settings.job_store_url:
                redis_client = redis.from_url(
                    self.settings.job_store_url,
                    **self.settings.redis_client_options,
                )
            else:
                redis_client = redis.StrictRedis(**self.settings.redis_client_options)

            stores["default"] = RedisJobStore(
                client=redis_client,
                jobs_key=self.settings.redis_jobs_key,
                run_times_key=self.settings.redis_run_times_key,
            )

        else:
            msg = f"Unsupported job_store_type: {self.settings.job_store_type}"
            raise ValueError(msg)

        return stores

    # === Executor Creation ===

    def _create_executors(self) -> dict[str, t.Any]:
        """Create executor based on settings."""
        executors = {}

        if self.settings.executor_type == "asyncio":
            aio_mod = importlib.import_module("apscheduler.executors.asyncio")
            AsyncIOExecutor = aio_mod.AsyncIOExecutor

            executors["default"] = AsyncIOExecutor()

        elif self.settings.executor_type == "thread":
            pool_mod = importlib.import_module("apscheduler.executors.pool")
            ThreadPoolExecutor = pool_mod.ThreadPoolExecutor

            executors["default"] = ThreadPoolExecutor(
                max_workers=self.settings.thread_pool_max_workers,
            )

        elif self.settings.executor_type == "process":
            pool_mod = importlib.import_module("apscheduler.executors.pool")
            ProcessPoolExecutor = pool_mod.ProcessPoolExecutor

            executors["default"] = ProcessPoolExecutor(
                max_workers=self.settings.process_pool_max_workers,
            )

        else:
            msg = f"Unsupported executor_type: {self.settings.executor_type}"
            raise ValueError(msg)

        return executors

    # === Event System ===

    def _setup_event_listeners(self, scheduler: AsyncIOScheduler) -> None:
        """Set up event listeners for job tracking."""
        events_mod = importlib.import_module("apscheduler.events")
        EVENT_JOB_ERROR = events_mod.EVENT_JOB_ERROR
        EVENT_JOB_EXECUTED = events_mod.EVENT_JOB_EXECUTED
        EVENT_JOB_MISSED = events_mod.EVENT_JOB_MISSED

        def job_executed_listener(event: t.Any) -> None:
            """Track successful job execution."""
            self._job_results[event.job_id] = TaskResult(
                task_id=UUID(event.job_id),
                status=TaskStatus.COMPLETED,
                result=event.retval,
                completed_at=datetime.now(tz=UTC),
            )

            # Maintain cache size
            if len(self._job_results) > self.settings.job_result_cache_size:
                # Remove oldest result
                oldest_key = next(iter(self._job_results))
                del self._job_results[oldest_key]

        def job_error_listener(event: t.Any) -> None:
            """Track failed job execution."""
            self._job_results[event.job_id] = TaskResult(
                task_id=UUID(event.job_id),
                status=TaskStatus.FAILED,
                error=str(event.exception),
                completed_at=datetime.now(tz=UTC),
            )

        def job_missed_listener(event: t.Any) -> None:
            """Track missed job execution."""
            self.logger.warning(
                f"Job {event.job_id} missed execution at {event.scheduled_run_time}",
            )

        scheduler.add_listener(job_executed_listener, EVENT_JOB_EXECUTED)
        scheduler.add_listener(job_error_listener, EVENT_JOB_ERROR)
        scheduler.add_listener(job_missed_listener, EVENT_JOB_MISSED)

    # === QueueBase Abstract Method Implementation ===

    async def enqueue(self, task: TaskData) -> str:
        """Enqueue task for immediate or delayed execution.

        Args:
            task: Task to enqueue

        Returns:
            Task ID as string
        """
        scheduler = await self._ensure_scheduler()

        # Get handler for task type
        handler = self._handlers.get(task.task_type)
        if not handler:
            msg = f"No handler registered for task type: {task.task_type}"
            raise ValueError(msg)

        # Create trigger based on task scheduling
        if task.scheduled_at:
            trig_date_mod = importlib.import_module("apscheduler.triggers.date")
            DateTrigger = trig_date_mod.DateTrigger
            trigger = DateTrigger(run_date=task.scheduled_at)  # type: ignore[call-arg]
        elif task.delay > 0:
            from datetime import timedelta

            run_date = datetime.now(tz=UTC) + timedelta(seconds=task.delay)
            trig_date_mod = importlib.import_module("apscheduler.triggers.date")
            DateTrigger = trig_date_mod.DateTrigger
            trigger = DateTrigger(run_date=run_date)  # type: ignore[call-arg]
        else:
            # Immediate execution
            trig_date_mod = importlib.import_module("apscheduler.triggers.date")
            DateTrigger = trig_date_mod.DateTrigger
            trigger = DateTrigger(run_date=datetime.now(tz=UTC))  # type: ignore[call-arg]

        # Add job to scheduler
        scheduler.add_job(
            func=self._execute_handler,
            trigger=trigger,
            args=[handler, task],
            id=str(task.task_id),
            name=task.task_type,
            jobstore=self.settings.default_jobstore,
            executor=self.settings.default_executor,
            replace_existing=self.settings.replace_existing,
        )

        self.logger.debug(f"Enqueued task {task.task_id} for execution")

        return str(task.task_id)

    async def _execute_handler(self, handler: TaskHandler, task: TaskData) -> t.Any:
        """Execute handler and track result.

        Args:
            handler: Task handler to execute
            task: Task data

        Returns:
            Task result
        """
        try:
            result = await handler.handle(task)
            return result.result if hasattr(result, "result") else result
        except Exception as e:
            self.logger.exception(f"Handler execution failed for {task.task_id}: {e}")
            raise

    async def dequeue(self, queue_name: str | None = None) -> TaskData | None:
        """Not applicable for push-based APScheduler.

        APScheduler uses a push-based architecture where the scheduler automatically
        triggers jobs based on their schedule. This method is not applicable.

        Args:
            queue_name: Optional queue name (ignored)

        Returns:
            Always returns None
        """
        self.logger.warning(
            "dequeue() not applicable for APScheduler (push-based architecture)",
        )
        return None

    async def get_task_status(self, task_id: UUID) -> TaskResult | None:
        """Get task status from job tracking.

        Args:
            task_id: Task identifier

        Returns:
            Task result or None if not found
        """
        # Check completed/failed results cache
        task_id_str = str(task_id)
        if task_id_str in self._job_results:
            return self._job_results[task_id_str]

        # Check scheduled jobs
        scheduler = await self._ensure_scheduler()
        job = scheduler.get_job(task_id_str)

        if job:
            return TaskResult(
                task_id=task_id,
                status=TaskStatus.PENDING,
                result={
                    "next_run_time": (
                        job.next_run_time.isoformat() if job.next_run_time else None
                    ),
                },
            )

        return None

    async def cancel_task(self, task_id: UUID) -> bool:
        """Cancel scheduled task.

        Args:
            task_id: Task identifier

        Returns:
            True if task was cancelled
        """
        scheduler = await self._ensure_scheduler()
        try:
            scheduler.remove_job(str(task_id))
            self.logger.info(f"Cancelled task {task_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to cancel task {task_id}: {e}")
            return False

    async def get_queue_info(self, queue_name: str) -> dict[str, t.Any]:
        """Get information about a queue.

        Args:
            queue_name: Queue name

        Returns:
            Queue information
        """
        scheduler = await self._ensure_scheduler()

        # Get all jobs
        jobs = scheduler.get_jobs(jobstore=self.settings.default_jobstore)

        # Filter by queue name if needed
        queue_jobs = [
            job
            for job in jobs
            if job.kwargs.get("task", {}).get("queue_name") == queue_name
        ]

        return {
            "queue_name": queue_name,
            "pending_jobs": len(queue_jobs),
            "total_jobs": len(jobs),
            "job_store": self.settings.job_store_type,
        }

    async def purge_queue(self, queue_name: str) -> int:
        """Remove all tasks from a queue.

        Args:
            queue_name: Queue name

        Returns:
            Number of tasks removed
        """
        scheduler = await self._ensure_scheduler()

        # Get all jobs
        jobs = scheduler.get_jobs(jobstore=self.settings.default_jobstore)

        # Remove jobs for this queue
        removed_count = 0
        for job in jobs:
            task_data = job.args[1] if len(job.args) > 1 else None
            if task_data and isinstance(task_data, TaskData):
                if task_data.queue_name == queue_name:
                    scheduler.remove_job(job.id)
                    removed_count += 1

        self.logger.info(f"Purged {removed_count} tasks from queue '{queue_name}'")
        return removed_count

    async def list_queues(self) -> list[str]:
        """List all available queues.

        Returns:
            List of queue names
        """
        scheduler = await self._ensure_scheduler()

        # Get all jobs and extract unique queue names
        jobs = scheduler.get_jobs(jobstore=self.settings.default_jobstore)
        queue_names = set()

        for job in jobs:
            task_data = job.args[1] if len(job.args) > 1 else None
            if task_data and isinstance(task_data, TaskData):
                queue_names.add(task_data.queue_name)

        return sorted(queue_names)

    async def _store_dead_letter_task(
        self,
        task: TaskData,
        result: TaskResult,
    ) -> None:
        """Store task in dead letter queue.

        Args:
            task: Failed task
            result: Failure result
        """
        self._dead_letter_tasks[task.task_id] = (task, result)
        self._metrics.dead_letter_tasks = len(self._dead_letter_tasks)

        self.logger.warning(f"Stored task {task.task_id} in dead letter queue")

    # === Lifecycle Management ===

    async def start(self) -> None:
        """Start the APScheduler queue system."""
        if self._running:
            return

        # Start scheduler
        scheduler = await self._ensure_scheduler()
        scheduler.start()

        # Call parent start (which starts workers, but we don't use them for APScheduler)
        await super().start()

        self.logger.info("APScheduler queue system started")

    async def stop(self) -> None:
        """Stop the APScheduler queue system."""
        if not self._running:
            return

        # Stop scheduler
        if self._scheduler:
            self._scheduler.shutdown(wait=True)

        # Call parent stop
        await super().stop()

        self.logger.info("APScheduler queue system stopped")

    # === APScheduler-Specific Extensions ===

    async def add_cron_job(
        self,
        task_type: str,
        cron_expression: str,
        task_id: UUID | None = None,
        payload: dict[str, t.Any] | None = None,
        queue_name: str = "default",
        **job_kwargs: t.Any,
    ) -> UUID:
        """Add cron-scheduled job.

        Args:
            task_type: Task type identifier
            cron_expression: Cron expression (5 fields: min hour day month dow)
            task_id: Optional task ID (generated if not provided)
            payload: Optional task payload
            queue_name: Target queue name
            **job_kwargs: Additional APScheduler job arguments

        Returns:
            Task ID
        """
        scheduler = await self._ensure_scheduler()
        handler = self._handlers.get(task_type)

        if not handler:
            msg = f"No handler registered for task type: {task_type}"
            raise ValueError(msg)

        task = TaskData(
            task_type=task_type,
            task_id=task_id or uuid4(),
            payload=payload or {},
            queue_name=queue_name,
        )

        # Parse cron expression
        parts = cron_expression.split()
        if len(parts) != 5:
            msg = f"Invalid cron expression: {cron_expression} (expected 5 fields)"
            raise ValueError(msg)

        cron_mod = importlib.import_module("apscheduler.triggers.cron")
        CronTrigger = cron_mod.CronTrigger
        trigger = CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
            timezone=self.settings.timezone,
        )

        scheduler.add_job(
            func=self._execute_handler,
            trigger=trigger,
            args=[handler, task],
            id=str(task.task_id),
            name=task_type,
            **job_kwargs,
        )

        self.logger.info(
            f"Added cron job {task.task_id} with expression: {cron_expression}"
        )

        return task.task_id

    async def add_interval_job(
        self,
        task_type: str,
        interval_seconds: float,
        task_id: UUID | None = None,
        payload: dict[str, t.Any] | None = None,
        queue_name: str = "default",
        **job_kwargs: t.Any,
    ) -> UUID:
        """Add interval-scheduled job.

        Args:
            task_type: Task type identifier
            interval_seconds: Interval in seconds
            task_id: Optional task ID
            payload: Optional task payload
            queue_name: Target queue name
            **job_kwargs: Additional APScheduler job arguments

        Returns:
            Task ID
        """
        scheduler = await self._ensure_scheduler()
        handler = self._handlers.get(task_type)

        if not handler:
            msg = f"No handler registered for task type: {task_type}"
            raise ValueError(msg)

        task = TaskData(
            task_type=task_type,
            task_id=task_id or uuid4(),
            payload=payload or {},
            queue_name=queue_name,
        )

        interval_mod = importlib.import_module("apscheduler.triggers.interval")
        IntervalTrigger = interval_mod.IntervalTrigger
        trigger = IntervalTrigger(  # type: ignore[call-arg]
            seconds=interval_seconds,
            timezone=self.settings.timezone,
        )

        scheduler.add_job(
            func=self._execute_handler,
            trigger=trigger,
            args=[handler, task],
            id=str(task.task_id),
            name=task_type,
            **job_kwargs,
        )

        self.logger.info(f"Added interval job {task.task_id} every {interval_seconds}s")

        return task.task_id

    async def pause_job(self, task_id: UUID) -> bool:
        """Pause scheduled job.

        Args:
            task_id: Task identifier

        Returns:
            True if job was paused
        """
        scheduler = await self._ensure_scheduler()
        try:
            scheduler.pause_job(str(task_id))
            self.logger.info(f"Paused job {task_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to pause job {task_id}: {e}")
            return False

    async def resume_job(self, task_id: UUID) -> bool:
        """Resume paused job.

        Args:
            task_id: Task identifier

        Returns:
            True if job was resumed
        """
        scheduler = await self._ensure_scheduler()
        try:
            scheduler.resume_job(str(task_id))
            self.logger.info(f"Resumed job {task_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to resume job {task_id}: {e}")
            return False

    async def modify_job(
        self,
        task_id: UUID,
        **changes: t.Any,
    ) -> bool:
        """Modify existing job.

        Args:
            task_id: Task identifier
            **changes: Job parameters to modify

        Returns:
            True if job was modified
        """
        scheduler = await self._ensure_scheduler()
        try:
            scheduler.modify_job(str(task_id), **changes)
            self.logger.info(f"Modified job {task_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to modify job {task_id}: {e}")
            return False

    async def get_job_info(self, task_id: UUID) -> dict[str, t.Any] | None:
        """Get detailed job information.

        Args:
            task_id: Task identifier

        Returns:
            Job information dict or None if not found
        """
        scheduler = await self._ensure_scheduler()
        job = scheduler.get_job(str(task_id))

        if not job:
            return None

        return {
            "id": job.id,
            "name": job.name,
            "trigger": str(job.trigger),
            "next_run_time": job.next_run_time.isoformat()
            if job.next_run_time
            else None,
            "pending": job.pending,
            "misfire_grace_time": job.misfire_grace_time,
            "max_instances": job.max_instances,
            "coalesce": job.coalesce,
        }
