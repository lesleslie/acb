# ACB Queue Adapters

Enterprise-grade asynchronous task queue adapters for the ACB framework, providing flexible scheduling, persistence, and distributed execution capabilities.

## Available Adapters

### Memory Queue (`queue.memory`)

In-memory task queue with priority support and delayed execution.

**Best For:**

- Development and testing
- Single-process applications
- Temporary task queues
- Low-latency requirements

**Features:**

- Priority-based task ordering
- Delayed task scheduling
- Memory usage limits
- Rate limiting
- Dead letter queue

### APScheduler Queue (`queue.apscheduler`) ⭐ NEW

Enterprise task scheduler with persistence, clustering, and advanced scheduling.

**Best For:**

- Production applications requiring persistence
- Distributed systems with clustering
- Complex scheduling (cron, intervals)
- Mission-critical task execution
- Applications with high availability requirements

**Features:**

- **Multiple Job Stores**: Memory, SQLAlchemy, MongoDB, Redis
- **Multiple Executors**: Asyncio, thread pool, process pool
- **Advanced Scheduling**: Cron expressions, intervals, one-time jobs
- **Job Control**: Pause, resume, modify, reschedule
- **Missed Job Handling**: Configurable grace time and coalescing
- **Clustering**: Distributed execution with heartbeat monitoring
- **Event System**: Track job execution, errors, and misses
- **Dead Letter Queue**: Automatic retry of failed tasks

## Quick Start

### Basic Usage

```python
from acb.depends import depends
from acb.adapters import import_adapter
from acb.queues._base import TaskData, TaskHandler, TaskResult, TaskStatus

# Import queue adapter (loads from settings/adapters.yaml)
Queue = import_adapter("queue")
queue = depends.get(Queue)


# Define a task handler
class EmailHandler(TaskHandler):
    async def handle(self, task: TaskData) -> TaskResult:
        # Send email logic here
        email = task.payload["email"]
        await send_email(email)

        return TaskResult(
            task_id=task.task_id,
            status=TaskStatus.COMPLETED,
            result={"sent": True},
            queue_name=task.queue_name,
        )


# Register handler
queue.register_handler("send_email", EmailHandler())

# Enqueue task
task = TaskData(
    task_type="send_email",
    queue_name="notifications",
    payload={"email": "user@example.com"},
)
task_id = await queue.enqueue(task)

# Check task status
status = await queue.get_task_status(task_id)
print(f"Task status: {status.status}")
```

### Memory Queue Configuration

```yaml
# settings/adapters.yaml
queue: memory

# settings/queue.yaml (optional)
queue:
  max_memory_usage: 100_000_000  # 100MB
  max_tasks_per_queue: 10_000
  enable_rate_limiting: true
  rate_limit_per_second: 100
  max_workers: 10
```

### APScheduler Queue Configuration

```yaml
# settings/adapters.yaml
queue: apscheduler

# settings/queue.yaml
queue:
  # Job Store (choose one)
  job_store_type: memory  # or: sqlalchemy, mongodb, redis

  # For SQLAlchemy:
  # job_store_type: sqlalchemy
  # job_store_url: postgresql://user:pass@localhost/scheduler
  # sqlalchemy_tablename: apscheduler_jobs

  # For MongoDB:
  # job_store_type: mongodb
  # job_store_url: mongodb://localhost:27017
  # mongodb_database: scheduler
  # mongodb_collection: jobs

  # For Redis:
  # job_store_type: redis
  # job_store_url: redis://localhost:6379/0
  # redis_jobs_key: apscheduler.jobs

  # Executor (choose one)
  executor_type: asyncio  # or: thread, process
  thread_pool_max_workers: 20  # for thread executor
  process_pool_max_workers: 4   # for process executor

  # Clustering
  enable_clustering: false
  cluster_id: worker-1  # unique per worker
  cluster_heartbeat_interval: 30

  # Missed Job Handling
  misfire_grace_time: 3600  # 1 hour
  coalesce: true  # combine missed runs
  max_instances: 1  # concurrent job instances
```

## APScheduler Advanced Features

### Cron Jobs

```python
from uuid import uuid4

# Schedule recurring task with cron expression
task_id = await queue.add_cron_job(
    task_type="cleanup_logs",
    cron_expression="0 2 * * *",  # Daily at 2 AM
    queue_name="maintenance",
    payload={"retention_days": 30},
)

# With timezone
task_id = await queue.add_cron_job(
    task_type="send_report",
    cron_expression="0 9 * * MON",  # Mondays at 9 AM
    timezone="America/New_York",
    queue_name="reports",
)
```

### Interval Jobs

```python
# Run every 30 minutes
task_id = await queue.add_interval_job(
    task_type="health_check",
    minutes=30,
    queue_name="monitoring",
    payload={"service": "api"},
)

# Complex intervals
task_id = await queue.add_interval_job(
    task_type="backup_database",
    hours=6,
    minutes=30,  # Every 6.5 hours
    queue_name="backups",
)
```

### Job Control

```python
# Pause job
await queue.pause_job(task_id)

# Resume job
await queue.resume_job(task_id)

# Modify job trigger
from apscheduler.triggers.cron import CronTrigger

await queue.modify_job(
    task_id=task_id,
    trigger=CronTrigger.from_crontab("*/10 * * * *"),  # Every 10 minutes
)

# Reschedule to specific time
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, timedelta, UTC

new_time = datetime.now(tz=UTC) + timedelta(hours=2)
await queue.reschedule_job(task_id=task_id, trigger=DateTrigger(run_date=new_time))

# Cancel job
await queue.cancel_task(task_id)
```

### Queue Management

```python
# Get queue information
info = await queue.get_queue_info("notifications")
print(f"Pending tasks: {info['job_count']}")

# List all queues
queues = await queue.list_queues()
for queue_name in queues:
    print(f"Queue: {queue_name}")

# Purge queue
count = await queue.purge_queue("stale_queue")
print(f"Removed {count} tasks")
```

### Dead Letter Queue

```python
# Get failed tasks
dead_letter_tasks = await queue.get_dead_letter_tasks()
for task, result in dead_letter_tasks:
    print(f"Failed task: {task.task_type}")
    print(f"Error: {result.error}")

# Retry dead letter task
await queue.retry_dead_letter_task(task_id)
```

## Installation

### Memory Queue

```bash
# No extra dependencies
uv add acb
```

### APScheduler Queue

```bash
# Base APScheduler
uv add --group queue-apscheduler

# With SQLAlchemy job store
uv add --group queue-apscheduler-sql

# With MongoDB job store
uv add --group queue-apscheduler-mongodb

# With Redis job store
uv add --group queue-apscheduler-redis
```

## Architecture Comparison

| Feature | Memory Queue | APScheduler Queue |
|---------|-------------|-------------------|
| **Persistence** | In-memory only | Multiple backends |
| **Clustering** | ❌ | ✅ |
| **Cron Jobs** | ❌ | ✅ |
| **Interval Jobs** | Via delay only | ✅ Native support |
| **Missed Job Handling** | ❌ | ✅ Configurable |
| **Job Control** | Limited | Full control |
| **Best For** | Development | Production |
| **Complexity** | Simple | Moderate |
| **Performance** | Fastest (in-memory) | Excellent |
| **Scalability** | Single process | Multi-worker/clustered |

## Task Data Model

All queue adapters use the same task data model from `QueueBase`:

```python
from acb.queues._base import TaskData, TaskPriority

task = TaskData(
    task_id=uuid4(),  # Auto-generated if not provided
    task_type="send_email",  # Handler registration key
    queue_name="notifications",  # Logical queue grouping
    payload={"email": "user@example.com"},  # Task-specific data
    priority=TaskPriority.HIGH,  # HIGH, NORMAL, LOW
    max_retries=3,  # Retry attempts on failure
    retry_count=0,  # Current retry count
    delay=0,  # Delay in seconds before execution
    scheduled_at=None,  # Specific datetime to run
    created_at=datetime.now(),  # Auto-generated
)
```

## Task Handler Interface

Implement the `TaskHandler` abstract class:

```python
from acb.queues._base import TaskHandler, TaskData, TaskResult, TaskStatus


class MyHandler(TaskHandler):
    async def handle(self, task: TaskData) -> TaskResult:
        """Process the task and return result."""
        try:
            # Your task logic here
            result_data = await process_task(task.payload)

            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.COMPLETED,
                result=result_data,
                queue_name=task.queue_name,
            )
        except Exception as e:
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                error=str(e),
                queue_name=task.queue_name,
            )
```

## Production Best Practices

### APScheduler with SQLAlchemy (Recommended)

```yaml
# High availability production setup
queue:
  job_store_type: sqlalchemy
  job_store_url: postgresql://user:pass@db.example.com/scheduler
  executor_type: asyncio

  # Clustering
  enable_clustering: true
  cluster_id: ${HOSTNAME}  # Unique per worker
  cluster_heartbeat_interval: 30

  # Missed job handling
  misfire_grace_time: 3600
  coalesce: true
  max_instances: 1
```

### Monitoring

```python
# Monitor queue health
health = await queue.health_check()
if not health["healthy"]:
    alert_ops_team(health)

# Track metrics
info = await queue.get_queue_info("critical")
if info["job_count"] > 1000:
    scale_up_workers()
```

### Error Handling

```python
class RobustHandler(TaskHandler):
    async def handle(self, task: TaskData) -> TaskResult:
        try:
            result = await self.process_with_timeout(task)
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.COMPLETED,
                result=result,
                queue_name=task.queue_name,
            )
        except asyncio.TimeoutError:
            # Handle timeout
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                error="Task timed out",
                queue_name=task.queue_name,
            )
        except Exception as e:
            # Log error for monitoring
            logger.error(f"Task failed: {e}", task_id=task.task_id)

            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                error=str(e),
                queue_name=task.queue_name,
            )

    async def process_with_timeout(self, task: TaskData, timeout: int = 30):
        """Process task with timeout."""
        return await asyncio.wait_for(self.do_work(task), timeout=timeout)
```

## Migration Guide

### From Memory to APScheduler

1. **Update configuration:**

   ```yaml
   # Before
   queue: memory

   # After
   queue: apscheduler
   ```

1. **Add persistence (recommended):**

   ```yaml
   queue:
     job_store_type: sqlalchemy
     job_store_url: postgresql://localhost/scheduler
   ```

1. **No code changes required** - Both adapters implement `QueueBase`

### Upgrading to Cron/Interval Jobs

```python
# Before (delay-based)
task = TaskData(
    task_type="cleanup",
    delay=86400,  # Run in 24 hours
)
await queue.enqueue(task)

# After (cron-based recurring)
await queue.add_cron_job(
    task_type="cleanup",
    cron_expression="0 0 * * *",  # Daily at midnight
)
```

## Troubleshooting

### APScheduler Jobs Not Executing

1. **Check scheduler is running:**

   ```python
   scheduler = await queue._ensure_scheduler()
   print(f"Running: {scheduler.running}")
   ```

1. **Verify handler registration:**

   ```python
   assert "my_task" in queue._handlers
   ```

1. **Check job store configuration:**

   ```python
   info = await queue.get_queue_info("my_queue")
   print(info)
   ```

### Missed Jobs

```yaml
# Increase misfire grace time
queue:
  misfire_grace_time: 7200  # 2 hours
  coalesce: true  # Combine multiple missed runs
```

### Memory Issues

```yaml
# Limit result cache
queue:
  result_cache_limit: 1000  # Default in implementation
```

## Examples

See `tests/queues/test_apscheduler_queue.py` for comprehensive examples including:

- Job store configurations
- Executor types
- Clustering setup
- Cron and interval jobs
- Job control operations
- Dead letter queue handling

## API Reference

### QueueBase Methods (All Adapters)

- `enqueue(task: TaskData) -> str`: Schedule task execution
- `dequeue(queue_name: str | None) -> TaskData | None`: Pull task (memory queue only)
- `get_task_status(task_id: UUID) -> TaskResult | None`: Check task status
- `cancel_task(task_id: UUID) -> bool`: Cancel pending task
- `get_queue_info(queue_name: str) -> dict`: Queue statistics
- `purge_queue(queue_name: str) -> int`: Remove all tasks from queue
- `list_queues() -> list[str]`: List all queue names
- `register_handler(task_type: str, handler: TaskHandler)`: Register task handler
- `get_dead_letter_tasks() -> list[tuple[TaskData, TaskResult]]`: Get failed tasks
- `retry_dead_letter_task(task_id: UUID) -> bool`: Retry failed task

### APScheduler-Specific Methods

- `add_cron_job(...)`: Add recurring cron job
- `add_interval_job(...)`: Add interval-based job
- `pause_job(task_id: UUID)`: Pause job execution
- `resume_job(task_id: UUID)`: Resume paused job
- `modify_job(task_id: UUID, **changes)`: Modify job parameters
- `reschedule_job(task_id: UUID, trigger)`: Change job schedule

## Contributing

When adding new queue adapters, ensure:

1. Extend `QueueBase` abstract class
1. Implement all abstract methods
1. Add comprehensive tests (40+ test cases)
1. Include `MODULE_METADATA` with capabilities
1. Document in this README

## License

BSD-3-Clause - See LICENSE file for details.
