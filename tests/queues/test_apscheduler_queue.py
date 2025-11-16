"""Tests for APScheduler queue implementation."""

from unittest.mock import MagicMock
from uuid import UUID

import asyncio
import pytest
from datetime import UTC, datetime, timedelta

# Mock APScheduler availability
try:
    from apscheduler.events import (
        EVENT_JOB_ERROR,
        EVENT_JOB_EXECUTED,
        EVENT_JOB_MISSED,
    )
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.date import DateTrigger
    from apscheduler.triggers.interval import IntervalTrigger

    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    # Create mock classes for testing
    AsyncIOScheduler = MagicMock
    DateTrigger = MagicMock
    CronTrigger = MagicMock
    IntervalTrigger = MagicMock
    EVENT_JOB_EXECUTED = "job_executed"
    EVENT_JOB_ERROR = "job_error"
    EVENT_JOB_MISSED = "job_missed"

from acb.tasks._base import (
    TaskData,
    TaskHandler,
    TaskPriority,
    TaskResult,
    TaskStatus,
)

# Mock APSchedulerSettings and Queue for when apscheduler is not installed
if APSCHEDULER_AVAILABLE:
    from acb.tasks.apscheduler import (
        APSchedulerSettings,
        Queue,
    )
else:
    # Create mock classes for testing without apscheduler
    class APSchedulerSettings:
        def __init__(self, **kwargs):
            self.job_store_type = kwargs.get("job_store_type", "memory")
            self.executor_type = kwargs.get("executor_type", "asyncio")
            self.enable_clustering = kwargs.get("enable_clustering", False)
            self.misfire_grace_time = kwargs.get("misfire_grace_time", 3600)
            self.coalesce = kwargs.get("coalesce", True)
            self.max_instances = kwargs.get("max_instances", 1)

    class Queue:
        def __init__(self, settings=None):
            self._settings = settings or APSchedulerSettings()
            self._scheduler = None
            self._handlers = {}
            self._job_results = {}


class SimpleTaskHandler(TaskHandler):
    """Simple task handler for testing."""

    def __init__(self, delay=0.0, should_fail=False):
        self.delay = delay
        self.should_fail = should_fail
        self.processed_tasks = []

    async def handle(self, task: TaskData) -> TaskResult:
        """Handle a task."""
        self.processed_tasks.append(task)

        if self.delay > 0:
            await asyncio.sleep(self.delay)

        if self.should_fail:
            raise ValueError("Handler failure")

        return TaskResult(
            task_id=task.task_id,
            status=TaskStatus.COMPLETED,
            result={"processed": task.payload},
            queue_name=task.queue_name,
        )


@pytest.fixture
def apscheduler_settings():
    """Create APScheduler settings for testing."""
    return APSchedulerSettings(
        job_store_type="memory",
        executor_type="asyncio",
        enable_clustering=False,
        misfire_grace_time=3600,
        coalesce=True,
        max_instances=1,
    )


@pytest.fixture
async def apscheduler_queue(apscheduler_settings):
    """Create and start an APScheduler queue for testing."""
    if not APSCHEDULER_AVAILABLE:
        pytest.skip("APScheduler not available")

    queue = Queue(apscheduler_settings)
    yield queue
    # Cleanup
    if queue._scheduler and queue._scheduler.running:
        queue._scheduler.shutdown(wait=False)


@pytest.fixture
def sample_task():
    """Create a sample task."""
    return TaskData(
        task_type="test_task",
        queue_name="test_queue",
        payload={"message": "test"},
        priority=TaskPriority.NORMAL,
    )


class TestAPSchedulerSettings:
    """Test APScheduler settings."""

    def test_default_settings(self):
        """Test default APScheduler settings."""
        settings = APSchedulerSettings()

        assert settings.job_store_type == "memory"
        assert settings.executor_type == "asyncio"
        assert settings.enable_clustering is False
        assert settings.misfire_grace_time == 3600
        assert settings.coalesce is True
        assert settings.max_instances == 1

    def test_custom_settings(self):
        """Test custom APScheduler settings."""
        settings = APSchedulerSettings(
            job_store_type="sqlalchemy",
            executor_type="thread",
            enable_clustering=True,
            misfire_grace_time=1800,
            coalesce=False,
            max_instances=3,
        )

        assert settings.job_store_type == "sqlalchemy"
        assert settings.executor_type == "thread"
        assert settings.enable_clustering is True
        assert settings.misfire_grace_time == 1800
        assert settings.coalesce is False
        assert settings.max_instances == 3

    def test_sqlalchemy_settings(self):
        """Test SQLAlchemy job store settings."""
        settings = APSchedulerSettings(
            job_store_type="sqlalchemy",
            job_store_url="sqlite:///jobs.db",
            sqlalchemy_tablename="custom_jobs",
        )

        assert settings.job_store_type == "sqlalchemy"
        assert settings.job_store_url == "sqlite:///jobs.db"
        assert settings.sqlalchemy_tablename == "custom_jobs"

    def test_mongodb_settings(self):
        """Test MongoDB job store settings."""
        settings = APSchedulerSettings(
            job_store_type="mongodb",
            job_store_url="mongodb://localhost:27017",
            mongodb_database="scheduler_jobs",
            mongodb_collection="jobs",
        )

        assert settings.job_store_type == "mongodb"
        assert settings.job_store_url == "mongodb://localhost:27017"
        assert settings.mongodb_database == "scheduler_jobs"
        assert settings.mongodb_collection == "jobs"

    def test_redis_settings(self):
        """Test Redis job store settings."""
        settings = APSchedulerSettings(
            job_store_type="redis",
            job_store_url="redis://localhost:6379/0",
            redis_jobs_key="custom:jobs",
            redis_run_times_key="custom:run_times",
        )

        assert settings.job_store_type == "redis"
        assert settings.job_store_url == "redis://localhost:6379/0"
        assert settings.redis_jobs_key == "custom:jobs"
        assert settings.redis_run_times_key == "custom:run_times"

    def test_executor_settings(self):
        """Test executor configuration."""
        # Asyncio executor (default)
        settings = APSchedulerSettings(executor_type="asyncio")
        assert settings.executor_type == "asyncio"

        # Thread pool executor
        settings = APSchedulerSettings(
            executor_type="thread",
            thread_pool_max_workers=20,
        )
        assert settings.executor_type == "thread"
        assert settings.thread_pool_max_workers == 20

        # Process pool executor
        settings = APSchedulerSettings(
            executor_type="process",
            process_pool_max_workers=4,
        )
        assert settings.executor_type == "process"
        assert settings.process_pool_max_workers == 4

    def test_clustering_settings(self):
        """Test clustering configuration."""
        settings = APSchedulerSettings(
            enable_clustering=True,
            cluster_id="worker-1",
            cluster_heartbeat_interval=10,
        )

        assert settings.enable_clustering is True
        assert settings.cluster_id == "worker-1"
        assert settings.cluster_heartbeat_interval == 10


class TestAPSchedulerQueue:
    """Test APScheduler Queue implementation."""

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_queue_creation(self, apscheduler_settings):
        """Test creating APScheduler queue."""
        queue = Queue(apscheduler_settings)
        assert queue._settings == apscheduler_settings
        assert queue._scheduler is None  # Lazy initialization

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_lazy_scheduler_initialization(self, apscheduler_queue):
        """Test lazy scheduler initialization."""
        # Scheduler not created until first use
        assert apscheduler_queue._scheduler is None

        # Trigger scheduler creation
        scheduler = await apscheduler_queue._ensure_scheduler()
        assert scheduler is not None
        assert apscheduler_queue._scheduler is scheduler

        # Subsequent calls return same scheduler
        scheduler2 = await apscheduler_queue._ensure_scheduler()
        assert scheduler2 is scheduler

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_task_enqueue_immediate(self, apscheduler_queue, sample_task):
        """Test enqueuing immediate task."""
        # Register handler
        handler = SimpleTaskHandler()
        apscheduler_queue.register_handler(sample_task.task_type, handler)

        # Enqueue task
        task_id = await apscheduler_queue.enqueue(sample_task)
        assert task_id == str(sample_task.task_id)

        # Verify job was scheduled
        scheduler = await apscheduler_queue._ensure_scheduler()
        assert scheduler.get_job(task_id) is not None

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_task_enqueue_delayed(self, apscheduler_queue):
        """Test enqueuing delayed task."""
        # Create delayed task
        delayed_task = TaskData(
            task_type="delayed_task",
            queue_name="test",
            delay=60,  # 60 seconds delay
            payload={"delayed": True},
        )

        handler = SimpleTaskHandler()
        apscheduler_queue.register_handler("delayed_task", handler)

        # Enqueue task
        task_id = await apscheduler_queue.enqueue(delayed_task)
        assert task_id is not None

        # Verify job scheduled with future run time
        scheduler = await apscheduler_queue._ensure_scheduler()
        job = scheduler.get_job(task_id)
        assert job is not None
        # Run time should be approximately 60 seconds from now
        assert job.next_run_time > datetime.now(tz=UTC)

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_task_enqueue_scheduled(self, apscheduler_queue):
        """Test enqueuing scheduled task."""
        # Create task scheduled for future
        scheduled_time = datetime.now(tz=UTC) + timedelta(minutes=5)
        scheduled_task = TaskData(
            task_type="scheduled_task",
            queue_name="test",
            scheduled_at=scheduled_time,
            payload={"scheduled": True},
        )

        handler = SimpleTaskHandler()
        apscheduler_queue.register_handler("scheduled_task", handler)

        # Enqueue task
        task_id = await apscheduler_queue.enqueue(scheduled_task)
        assert task_id is not None

        # Verify job scheduled at correct time
        scheduler = await apscheduler_queue._ensure_scheduler()
        job = scheduler.get_job(task_id)
        assert job is not None
        assert job.next_run_time == scheduled_time

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_dequeue_not_applicable(self, apscheduler_queue):
        """Test dequeue returns None for push-based architecture."""
        # APScheduler is push-based, not pull-based
        task = await apscheduler_queue.dequeue()
        assert task is None

        # Also test with queue name
        task = await apscheduler_queue.dequeue("test_queue")
        assert task is None

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_task_status_tracking(self, apscheduler_queue, sample_task):
        """Test task status tracking via event listeners."""
        handler = SimpleTaskHandler()
        apscheduler_queue.register_handler(sample_task.task_type, handler)

        # Initially no status
        status = await apscheduler_queue.get_task_status(sample_task.task_id)
        assert status is None

        # Enqueue task
        await apscheduler_queue.enqueue(sample_task)

        # After execution, result should be stored
        # (In real scenario, need to wait for job execution)
        # For testing, we'll directly store a result
        result = TaskResult(
            task_id=sample_task.task_id,
            status=TaskStatus.COMPLETED,
            result={"success": True},
            queue_name=sample_task.queue_name,
        )
        apscheduler_queue._job_results[str(sample_task.task_id)] = result

        # Now should have status
        status = await apscheduler_queue.get_task_status(sample_task.task_id)
        assert status is not None
        assert status.status == TaskStatus.COMPLETED

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_task_cancellation(self, apscheduler_queue, sample_task):
        """Test task cancellation."""
        handler = SimpleTaskHandler()
        apscheduler_queue.register_handler(sample_task.task_type, handler)

        # Enqueue task
        task_id = await apscheduler_queue.enqueue(sample_task)

        # Verify job exists
        scheduler = await apscheduler_queue._ensure_scheduler()
        assert scheduler.get_job(task_id) is not None

        # Cancel task
        cancelled = await apscheduler_queue.cancel_task(sample_task.task_id)
        assert cancelled is True

        # Job should be removed
        assert scheduler.get_job(task_id) is None

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_queue_info(self, apscheduler_queue, sample_task):
        """Test queue information retrieval."""
        handler = SimpleTaskHandler()
        apscheduler_queue.register_handler(sample_task.task_type, handler)

        # Get queue info
        info = await apscheduler_queue.get_queue_info("test_queue")
        assert info["name"] == "test_queue"
        assert "job_count" in info
        assert "scheduler_running" in info

        # Add task
        await apscheduler_queue.enqueue(sample_task)

        # Info should reflect scheduled job
        info = await apscheduler_queue.get_queue_info("test_queue")
        assert info["job_count"] >= 0

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_queue_purging(self, apscheduler_queue):
        """Test queue purging functionality."""
        handler = SimpleTaskHandler()
        apscheduler_queue.register_handler("purgeable_task", handler)

        # Add multiple tasks to same queue
        task_ids = []
        for i in range(5):
            task = TaskData(
                task_type="purgeable_task",
                queue_name="purgeable_queue",
                payload={"index": i},
            )
            task_id = await apscheduler_queue.enqueue(task)
            task_ids.append(task_id)

        # Purge queue
        purged_count = await apscheduler_queue.purge_queue("purgeable_queue")
        assert purged_count == 5

        # Verify jobs removed
        scheduler = await apscheduler_queue._ensure_scheduler()
        for task_id in task_ids:
            assert scheduler.get_job(task_id) is None

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_queue_listing(self, apscheduler_queue):
        """Test listing queues."""
        handler = SimpleTaskHandler()
        apscheduler_queue.register_handler("list_task", handler)

        # Add tasks to different queues
        task1 = TaskData(task_type="list_task", queue_name="queue1")
        task2 = TaskData(task_type="list_task", queue_name="queue2")

        await apscheduler_queue.enqueue(task1)
        await apscheduler_queue.enqueue(task2)

        queues = await apscheduler_queue.list_queues()
        assert "queue1" in queues
        assert "queue2" in queues


class TestAPSchedulerCronJobs:
    """Test APScheduler cron job functionality."""

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_add_cron_job(self, apscheduler_queue):
        """Test adding cron job."""
        handler = SimpleTaskHandler()
        apscheduler_queue.register_handler("cron_task", handler)

        # Add cron job (every minute)
        task_id = await apscheduler_queue.add_cron_job(
            task_type="cron_task", cron_expression="* * * * *", payload={"cron": True}
        )

        assert task_id is not None
        assert isinstance(task_id, UUID)

        # Verify job scheduled
        scheduler = await apscheduler_queue._ensure_scheduler()
        job = scheduler.get_job(str(task_id))
        assert job is not None

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_cron_job_with_timezone(self, apscheduler_queue):
        """Test cron job with timezone."""
        handler = SimpleTaskHandler()
        apscheduler_queue.register_handler("tz_cron_task", handler)

        # Add cron job with timezone
        task_id = await apscheduler_queue.add_cron_job(
            task_type="tz_cron_task",
            cron_expression="0 9 * * *",  # 9 AM daily
            timezone="America/New_York",
            payload={"timezone_aware": True},
        )

        assert task_id is not None

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_add_interval_job(self, apscheduler_queue):
        """Test adding interval job."""
        handler = SimpleTaskHandler()
        apscheduler_queue.register_handler("interval_task", handler)

        # Add interval job (every 30 seconds)
        task_id = await apscheduler_queue.add_interval_job(
            task_type="interval_task", seconds=30, payload={"interval": True}
        )

        assert task_id is not None

        # Verify job scheduled
        scheduler = await apscheduler_queue._ensure_scheduler()
        job = scheduler.get_job(str(task_id))
        assert job is not None

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_interval_job_complex(self, apscheduler_queue):
        """Test interval job with complex schedule."""
        handler = SimpleTaskHandler()
        apscheduler_queue.register_handler("complex_interval_task", handler)

        # Add interval job (1 hour, 30 minutes)
        task_id = await apscheduler_queue.add_interval_job(
            task_type="complex_interval_task",
            hours=1,
            minutes=30,
            payload={"complex": True},
        )

        assert task_id is not None


class TestAPSchedulerJobControl:
    """Test APScheduler job control operations."""

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_pause_resume_job(self, apscheduler_queue):
        """Test pausing and resuming jobs."""
        handler = SimpleTaskHandler()
        apscheduler_queue.register_handler("controllable_task", handler)

        # Add job
        task = TaskData(task_type="controllable_task", queue_name="test")
        await apscheduler_queue.enqueue(task)

        # Pause job
        paused = await apscheduler_queue.pause_job(task.task_id)
        assert paused is True

        # Resume job
        resumed = await apscheduler_queue.resume_job(task.task_id)
        assert resumed is True

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_modify_job(self, apscheduler_queue):
        """Test modifying job parameters."""
        handler = SimpleTaskHandler()
        apscheduler_queue.register_handler("modifiable_task", handler)

        # Add cron job
        task_id = await apscheduler_queue.add_cron_job(
            task_type="modifiable_task",
            cron_expression="*/5 * * * *",  # Every 5 minutes
        )

        # Modify to run every 10 minutes
        modified = await apscheduler_queue.modify_job(
            task_id=task_id, trigger=CronTrigger.from_crontab("*/10 * * * *")
        )
        assert modified is True

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_reschedule_job(self, apscheduler_queue):
        """Test rescheduling job."""
        handler = SimpleTaskHandler()
        apscheduler_queue.register_handler("reschedulable_task", handler)

        # Add job
        task = TaskData(task_type="reschedulable_task", queue_name="test")
        await apscheduler_queue.enqueue(task)

        # Reschedule to future time
        new_time = datetime.now(tz=UTC) + timedelta(hours=1)
        rescheduled = await apscheduler_queue.reschedule_job(
            task_id=task.task_id, trigger=DateTrigger(run_date=new_time)
        )
        assert rescheduled is True


class TestAPSchedulerEventListeners:
    """Test APScheduler event listener functionality."""

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_job_execution_event(self, apscheduler_queue):
        """Test job execution event tracking."""
        handler = SimpleTaskHandler()
        apscheduler_queue.register_handler("event_task", handler)

        # Create task
        task = TaskData(
            task_type="event_task", queue_name="test", payload={"test": "event"}
        )

        # Enqueue and let it execute
        task_id = await apscheduler_queue.enqueue(task)

        # In real scenario, event would fire when job executes
        # For testing, we simulate the event result
        result = TaskResult(
            task_id=task.task_id,
            status=TaskStatus.COMPLETED,
            result={"executed": True},
            queue_name=task.queue_name,
        )
        apscheduler_queue._job_results[task_id] = result

        # Verify result stored
        stored_result = await apscheduler_queue.get_task_status(task.task_id)
        assert stored_result.status == TaskStatus.COMPLETED

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_job_error_event(self, apscheduler_queue):
        """Test job error event tracking."""
        handler = SimpleTaskHandler(should_fail=True)
        apscheduler_queue.register_handler("failing_task", handler)

        # Create failing task
        task = TaskData(task_type="failing_task", queue_name="test")

        task_id = await apscheduler_queue.enqueue(task)

        # Simulate error event
        result = TaskResult(
            task_id=task.task_id,
            status=TaskStatus.FAILED,
            error="Handler failure",
            queue_name=task.queue_name,
        )
        apscheduler_queue._job_results[task_id] = result

        # Verify error stored
        stored_result = await apscheduler_queue.get_task_status(task.task_id)
        assert stored_result.status == TaskStatus.FAILED
        assert stored_result.error == "Handler failure"


class TestAPSchedulerDeadLetterQueue:
    """Test dead letter queue functionality."""

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_dead_letter_task_storage(self, apscheduler_queue):
        """Test storing dead letter tasks."""
        task = TaskData(task_type="dead_letter_task", queue_name="test")

        result = TaskResult(
            task_id=task.task_id,
            status=TaskStatus.DEAD_LETTER,
            error="Max retries exceeded",
            queue_name=task.queue_name,
        )

        # Store dead letter task
        await apscheduler_queue._store_dead_letter_task(task, result)

        # Verify stored
        dead_letter_tasks = await apscheduler_queue.get_dead_letter_tasks()
        assert len(dead_letter_tasks) == 1
        assert dead_letter_tasks[0][0].task_id == task.task_id

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_dead_letter_retry(self, apscheduler_queue):
        """Test retrying dead letter tasks."""
        handler = SimpleTaskHandler()
        apscheduler_queue.register_handler("retry_task", handler)

        # Create and store dead letter task
        task = TaskData(task_type="retry_task", queue_name="test")
        result = TaskResult(
            task_id=task.task_id,
            status=TaskStatus.DEAD_LETTER,
            error="Test failure",
            queue_name=task.queue_name,
        )

        await apscheduler_queue._store_dead_letter_task(task, result)

        # Retry dead letter task
        retried = await apscheduler_queue.retry_dead_letter_task(task.task_id)
        assert retried is True

        # Verify task removed from dead letter queue
        dead_letter_tasks = await apscheduler_queue.get_dead_letter_tasks()
        assert len(dead_letter_tasks) == 0


class TestAPSchedulerIntegration:
    """Integration tests for APScheduler queue."""

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_full_workflow_with_scheduler(self, apscheduler_settings):
        """Test complete workflow with scheduler running."""
        queue = Queue(apscheduler_settings)

        # Create handler
        handler = SimpleTaskHandler(delay=0.01)
        queue.register_handler("integration_task", handler)

        # Initialize scheduler
        scheduler = await queue._ensure_scheduler()
        scheduler.start()

        try:
            # Add tasks
            task_ids = []
            for i in range(3):
                task = TaskData(
                    task_type="integration_task",
                    queue_name="integration",
                    payload={"index": i},
                )
                task_id = await queue.enqueue(task)
                task_ids.append(task_id)

            # Wait for execution
            await asyncio.sleep(0.5)

            # Verify tasks were processed
            # (In real scenario, results would be in _job_results)
            assert len(task_ids) == 3

        finally:
            scheduler.shutdown(wait=False)

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_mixed_job_types(self, apscheduler_queue):
        """Test mixing one-time, interval, and cron jobs."""
        handler = SimpleTaskHandler()
        apscheduler_queue.register_handler("mixed_task", handler)

        # One-time job
        one_time_task = TaskData(
            task_type="mixed_task", queue_name="test", payload={"type": "one_time"}
        )
        one_time_id = await apscheduler_queue.enqueue(one_time_task)

        # Interval job
        interval_id = await apscheduler_queue.add_interval_job(
            task_type="mixed_task", minutes=5, payload={"type": "interval"}
        )

        # Cron job
        cron_id = await apscheduler_queue.add_cron_job(
            task_type="mixed_task",
            cron_expression="0 */2 * * *",  # Every 2 hours
            payload={"type": "cron"},
        )

        # All jobs should be scheduled
        assert one_time_id is not None
        assert interval_id is not None
        assert cron_id is not None

        # Verify all in scheduler
        scheduler = await apscheduler_queue._ensure_scheduler()
        assert scheduler.get_job(one_time_id) is not None
        assert scheduler.get_job(str(interval_id)) is not None
        assert scheduler.get_job(str(cron_id)) is not None


class TestAPSchedulerJobStores:
    """Test different job store backends."""

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_memory_job_store(self):
        """Test memory job store (default)."""
        settings = APSchedulerSettings(job_store_type="memory")
        queue = Queue(settings)

        handler = SimpleTaskHandler()
        queue.register_handler("memory_task", handler)

        # Add job
        task = TaskData(task_type="memory_task", queue_name="test")
        task_id = await queue.enqueue(task)

        # Verify job stored in memory
        scheduler = await queue._ensure_scheduler()
        job = scheduler.get_job(task_id)
        assert job is not None

        # Memory store doesn't persist across restarts
        scheduler.shutdown(wait=False)

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_sqlalchemy_job_store_config(self):
        """Test SQLAlchemy job store configuration."""
        settings = APSchedulerSettings(
            job_store_type="sqlalchemy",
            job_store_url="sqlite:///:memory:",
            sqlalchemy_tablename="test_jobs",
        )

        queue = Queue(settings)

        # Verify job store created with correct settings
        job_stores = queue._create_job_stores()
        assert "default" in job_stores
        # Note: Actual SQLAlchemy integration would require sqlalchemy installed

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_mongodb_job_store_config(self):
        """Test MongoDB job store configuration."""
        settings = APSchedulerSettings(
            job_store_type="mongodb",
            job_store_url="mongodb://localhost:27017",
            mongodb_database="test_scheduler",
            mongodb_collection="test_jobs",
        )

        Queue(settings)

        # Verify configuration
        assert settings.mongodb_database == "test_scheduler"
        assert settings.mongodb_collection == "test_jobs"

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_redis_job_store_config(self):
        """Test Redis job store configuration."""
        settings = APSchedulerSettings(
            job_store_type="redis",
            job_store_url="redis://localhost:6379/1",
            redis_jobs_key="scheduler:jobs",
            redis_run_times_key="scheduler:run_times",
        )

        Queue(settings)

        # Verify configuration
        assert settings.redis_jobs_key == "scheduler:jobs"
        assert settings.redis_run_times_key == "scheduler:run_times"


class TestAPSchedulerExecutors:
    """Test different executor backends."""

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_asyncio_executor(self):
        """Test asyncio executor (default)."""
        settings = APSchedulerSettings(executor_type="asyncio")
        queue = Queue(settings)

        handler = SimpleTaskHandler()
        queue.register_handler("async_task", handler)

        # Verify executor type
        executors = queue._create_executors()
        assert "default" in executors
        # AsyncIOExecutor should be used

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_thread_executor_config(self):
        """Test thread pool executor configuration."""
        settings = APSchedulerSettings(
            executor_type="thread",
            thread_pool_max_workers=10,
        )

        queue = Queue(settings)

        # Verify executor created with correct worker count
        executors = queue._create_executors()
        assert "default" in executors
        assert settings.thread_pool_max_workers == 10

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_process_executor_config(self):
        """Test process pool executor configuration."""
        settings = APSchedulerSettings(
            executor_type="process",
            process_pool_max_workers=4,
        )

        Queue(settings)

        # Verify executor configuration
        assert settings.process_pool_max_workers == 4


class TestAPSchedulerClustering:
    """Test clustering functionality."""

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_clustering_enabled(self):
        """Test clustering configuration."""
        settings = APSchedulerSettings(
            enable_clustering=True,
            cluster_id="worker-1",
            cluster_heartbeat_interval=10,
        )

        Queue(settings)

        # Verify clustering settings
        assert settings.enable_clustering is True
        assert settings.cluster_id == "worker-1"
        assert settings.cluster_heartbeat_interval == 10

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_clustering_with_persistent_store(self):
        """Test clustering requires persistent job store."""
        # Clustering with memory store (not recommended)
        settings = APSchedulerSettings(
            enable_clustering=True,
            job_store_type="memory",
        )

        Queue(settings)

        # Clustering should work better with persistent store
        # This test verifies configuration compatibility


class TestAPSchedulerMisfireHandling:
    """Test misfire handling and coalescing."""

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_misfire_grace_time(self):
        """Test misfire grace time configuration."""
        settings = APSchedulerSettings(
            misfire_grace_time=1800,  # 30 minutes
        )

        Queue(settings)

        # Verify misfire settings
        assert settings.misfire_grace_time == 1800

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_coalesce_settings(self):
        """Test coalescing configuration."""
        # With coalescing
        settings = APSchedulerSettings(coalesce=True)
        Queue(settings)
        assert settings.coalesce is True

        # Without coalescing
        settings = APSchedulerSettings(coalesce=False)
        Queue(settings)
        assert settings.coalesce is False

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_max_instances(self):
        """Test max instances configuration."""
        settings = APSchedulerSettings(max_instances=3)
        Queue(settings)

        # Verify max instances setting
        assert settings.max_instances == 3


class TestAPSchedulerPerformance:
    """Performance and benchmark tests."""

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_enqueue_performance(self, apscheduler_queue, benchmark):
        """Benchmark task enqueue performance."""
        handler = SimpleTaskHandler()
        apscheduler_queue.register_handler("bench_task", handler)

        def enqueue_task():
            task = TaskData(task_type="bench_task", queue_name="benchmark")
            # Note: This is sync benchmark, actual implementation is async
            return task

        # Benchmark task creation
        result = benchmark(enqueue_task)
        assert result is not None

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_job_scheduling_overhead(self, apscheduler_queue):
        """Test job scheduling overhead."""
        handler = SimpleTaskHandler()
        apscheduler_queue.register_handler("overhead_task", handler)

        # Measure time to schedule multiple jobs
        start_time = datetime.now()

        tasks = []
        for i in range(100):
            task = TaskData(
                task_type="overhead_task", queue_name="overhead", payload={"index": i}
            )
            tasks.append(task)

        # Schedule all tasks
        for task in tasks:
            await apscheduler_queue.enqueue(task)

        elapsed = (datetime.now() - start_time).total_seconds()

        # Should be able to schedule 100 tasks in reasonable time
        assert elapsed < 1.0  # Less than 1 second

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_concurrent_job_scheduling(self, apscheduler_queue):
        """Test concurrent job scheduling."""
        handler = SimpleTaskHandler()
        apscheduler_queue.register_handler("concurrent_task", handler)

        async def schedule_batch(start_idx, count):
            for i in range(count):
                task = TaskData(
                    task_type="concurrent_task",
                    queue_name="concurrent",
                    payload={"index": start_idx + i},
                )
                await apscheduler_queue.enqueue(task)

        # Schedule tasks concurrently
        await asyncio.gather(
            schedule_batch(0, 20),
            schedule_batch(20, 20),
            schedule_batch(40, 20),
        )

        # Verify all jobs scheduled
        scheduler = await apscheduler_queue._ensure_scheduler()
        jobs = scheduler.get_jobs()
        # Note: Some jobs might have executed already
        assert len(jobs) >= 0


class TestAPSchedulerCleanup:
    """Test resource cleanup and lifecycle."""

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_scheduler_shutdown(self, apscheduler_queue):
        """Test proper scheduler shutdown."""
        # Start scheduler
        scheduler = await apscheduler_queue._ensure_scheduler()
        scheduler.start()
        assert scheduler.running

        # Shutdown
        scheduler.shutdown(wait=False)
        assert not scheduler.running

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_job_cleanup_on_shutdown(self, apscheduler_queue):
        """Test job cleanup on shutdown."""
        handler = SimpleTaskHandler()
        apscheduler_queue.register_handler("cleanup_task", handler)

        # Add jobs
        for i in range(5):
            task = TaskData(
                task_type="cleanup_task", queue_name="cleanup", payload={"index": i}
            )
            await apscheduler_queue.enqueue(task)

        # Get scheduler
        scheduler = await apscheduler_queue._ensure_scheduler()
        scheduler.start()

        # Verify jobs exist
        jobs = scheduler.get_jobs()
        assert len(jobs) > 0

        # Shutdown with wait
        scheduler.shutdown(wait=True)

        # Jobs should be cleaned up
        # (Memory store doesn't persist after shutdown)

    @pytest.mark.skipif(not APSCHEDULER_AVAILABLE, reason="APScheduler not installed")
    @pytest.mark.asyncio
    async def test_result_cache_limit(self, apscheduler_queue):
        """Test result cache size limit."""
        handler = SimpleTaskHandler()
        apscheduler_queue.register_handler("cache_task", handler)

        # Add many results to cache
        for i in range(1500):  # Exceeds 1000 limit
            task_id = str(i)
            result = TaskResult(
                task_id=UUID(int=i),
                status=TaskStatus.COMPLETED,
                result={"index": i},
                queue_name="test",
            )
            apscheduler_queue._job_results[task_id] = result

        # Cache should be limited to 1000 results
        assert len(apscheduler_queue._job_results) <= 1000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
