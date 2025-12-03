"""Task scheduler for ACB queue system.

This module provides cron-like scheduling capabilities for the ACB task queue
system, allowing tasks to be scheduled based on time patterns, intervals,
and complex scheduling rules.
"""

import logging
from collections.abc import Callable
from uuid import UUID, uuid4

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

try:
    import croniter

    CRONITER_AVAILABLE = True
except ImportError:
    croniter = None  # type: ignore[assignment]
    CRONITER_AVAILABLE = False

import contextlib
from pydantic import BaseModel, Field, field_validator

from ._base import (
    QueueBase,
    TaskData,
    TaskPriority,
)

logger = logging.getLogger(__name__)


class ScheduleRule(BaseModel):
    """Scheduling rule definition."""

    rule_id: UUID = Field(default_factory=uuid4)
    name: str = Field(description="Human-readable rule name")

    # Task configuration
    task_type: str = Field(description="Task type to schedule")
    queue_name: str = Field(default="default", description="Target queue")
    payload: dict[str, Any] = Field(default_factory=dict, description="Task payload")
    priority: TaskPriority = TaskPriority.NORMAL

    # Scheduling configuration
    cron_expression: str | None = Field(default=None, description="Cron expression")
    interval_seconds: float | None = Field(
        default=None,
        description="Interval in seconds",
    )
    start_time: datetime | None = Field(default=None, description="Start time")
    end_time: datetime | None = Field(default=None, description="End time")
    max_runs: int | None = Field(default=None, description="Maximum number of runs")

    # State
    enabled: bool = True
    last_run: datetime | None = None
    next_run: datetime | None = None
    run_count: int = 0

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    tags: dict[str, str] = Field(default_factory=dict)

    @field_validator("cron_expression")
    @classmethod
    def validate_cron_expression(cls, v: Any) -> Any:
        if v and not CRONITER_AVAILABLE:
            msg = "croniter is required for cron expressions. Install with: pip install croniter"
            raise ImportError(
                msg,
            )

        if v:
            try:
                if croniter:
                    croniter.croniter(v)
            except Exception as e:
                msg = f"Invalid cron expression: {e}"
                raise ValueError(msg)

        return v

    @field_validator("interval_seconds")
    @classmethod
    def validate_interval(cls, v: Any) -> Any:
        if v is not None and v <= 0:
            msg = "Interval must be positive"
            raise ValueError(msg)
        return v

    def model_post_init(self, __context: Any) -> None:
        """Calculate next run time after initialization."""
        if self.enabled:
            self.calculate_next_run()

    def calculate_next_run(self, from_time: datetime | None = None) -> datetime | None:
        """Calculate and persist the next run time."""
        if not self.enabled:
            return self._set_next_run(None)

        base_time = self._resolve_base_time(from_time)
        if self._schedule_exhausted(base_time):
            return self._set_next_run(None)

        next_time = self._compute_next_time(base_time)
        if not self._is_within_schedule_window(next_time):
            return self._set_next_run(None)

        return self._set_next_run(next_time)

    def _resolve_base_time(self, from_time: datetime | None) -> datetime:
        base_time = from_time or datetime.now(tz=UTC)
        if self.start_time and base_time < self.start_time:
            return self.start_time
        return base_time

    def _schedule_exhausted(self, base_time: datetime) -> bool:
        if self.max_runs is not None and self.run_count >= self.max_runs:
            return True
        return bool(self.end_time and base_time >= self.end_time)

    def _compute_next_time(self, base_time: datetime) -> datetime | None:
        if self.cron_expression:
            if not croniter:
                msg = "croniter is required for cron expressions"
                raise ImportError(msg)
            cron = croniter.croniter(self.cron_expression, base_time)
            return cron.get_next(datetime)

        if self.interval_seconds:
            anchor = self.last_run or base_time
            return anchor + timedelta(seconds=self.interval_seconds)

        return None

    def _is_within_schedule_window(self, next_time: datetime | None) -> bool:
        if next_time is None:
            return False
        return not (self.end_time and next_time > self.end_time)

    def _set_next_run(self, next_time: datetime | None) -> datetime | None:
        self.next_run = next_time
        return next_time

    def should_run(self, current_time: datetime | None = None) -> bool:
        """Check if the rule should run now."""
        if not self.enabled:
            return False

        current_time = current_time or datetime.now(tz=UTC)

        # Check max runs
        if self.max_runs is not None and self.run_count >= self.max_runs:
            return False

        # Check time bounds
        if self.start_time and current_time < self.start_time:
            return False

        if self.end_time and current_time >= self.end_time:
            return False

        # Check if it's time to run
        return bool(self.next_run and current_time >= self.next_run)

    def mark_run(self, run_time: datetime | None = None) -> None:
        """Mark the rule as having run."""
        run_time = run_time or datetime.now(tz=UTC)
        self.last_run = run_time
        self.run_count += 1
        self.calculate_next_run(run_time)


class TaskScheduler:
    """Task scheduler for ACB queue system."""

    def __init__(self, queue: QueueBase) -> None:
        self.queue = queue
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Schedule rules
        self._rules: dict[UUID, ScheduleRule] = {}

        # Scheduler state
        self._running = False
        self._scheduler_task: asyncio.Task[None] | None = None
        self._shutdown_event = asyncio.Event()

        # Configuration
        self._check_interval = 1.0  # Check every second
        self._max_concurrent_tasks = 100

    async def start(self) -> None:
        """Start the task scheduler."""
        if self._running:
            return

        self._running = True
        self._shutdown_event.clear()

        # Start scheduler loop
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())

        self.logger.info("Task scheduler started")

    async def stop(self) -> None:
        """Stop the task scheduler."""
        if not self._running:
            return

        self._running = False
        self._shutdown_event.set()

        # Stop scheduler task
        if self._scheduler_task:
            self._scheduler_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._scheduler_task

        self.logger.info("Task scheduler stopped")

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        while self._running and not self._shutdown_event.is_set():
            try:
                current_time = datetime.now(tz=UTC)
                tasks_scheduled = 0

                # Check all rules
                for rule in list(self._rules.values()):
                    if rule.should_run(current_time):
                        try:
                            await self._execute_rule(rule, current_time)
                            tasks_scheduled += 1
                        except Exception as e:
                            self.logger.exception(
                                f"Failed to execute rule {rule.name}: {e}",
                            )

                if tasks_scheduled > 0:
                    self.logger.debug(f"Scheduled {tasks_scheduled} tasks")

                # Sleep until next check
                await asyncio.sleep(self._check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.exception(f"Scheduler loop error: {e}")
                await asyncio.sleep(self._check_interval)

    async def _execute_rule(self, rule: ScheduleRule, run_time: datetime) -> None:
        """Execute a scheduling rule."""
        try:
            # Create task data
            task = TaskData(
                task_type=rule.task_type,
                queue_name=rule.queue_name,
                payload=rule.payload.copy(),
                priority=rule.priority,
                tags={
                    "scheduled": "true",
                    "rule_id": str(rule.rule_id),
                    "rule_name": rule.name,
                    "scheduled_at": run_time.isoformat(),
                }
                | rule.tags,
            )

            # Enqueue task
            task_id = await self.queue.enqueue(task)

            # Mark rule as run
            rule.mark_run(run_time)

            self.logger.debug(
                f"Scheduled task {task_id} for rule {rule.name} (run {rule.run_count})",
            )

        except Exception as e:
            self.logger.exception(f"Failed to execute rule {rule.name}: {e}")
            raise

    def add_rule(self, rule: ScheduleRule) -> UUID:
        """Add a scheduling rule."""
        self._rules[rule.rule_id] = rule
        self.logger.info(f"Added scheduling rule: {rule.name}")
        return rule.rule_id

    def remove_rule(self, rule_id: UUID) -> bool:
        """Remove a scheduling rule."""
        if rule_id in self._rules:
            rule = self._rules.pop(rule_id)
            self.logger.info(f"Removed scheduling rule: {rule.name}")
            return True
        return False

    def get_rule(self, rule_id: UUID) -> ScheduleRule | None:
        """Get a scheduling rule by ID."""
        return self._rules.get(rule_id)

    def list_rules(self) -> list[ScheduleRule]:
        """List all scheduling rules."""
        return list(self._rules.values())

    def enable_rule(self, rule_id: UUID) -> bool:
        """Enable a scheduling rule."""
        rule = self._rules.get(rule_id)
        if rule:
            rule.enabled = True
            rule.calculate_next_run()
            self.logger.info(f"Enabled scheduling rule: {rule.name}")
            return True
        return False

    def disable_rule(self, rule_id: UUID) -> bool:
        """Disable a scheduling rule."""
        rule = self._rules.get(rule_id)
        if rule:
            rule.enabled = False
            rule.next_run = None
            self.logger.info(f"Disabled scheduling rule: {rule.name}")
            return True
        return False

    def update_rule(self, rule_id: UUID, **kwargs: Any) -> bool:
        """Update a scheduling rule."""
        rule = self._rules.get(rule_id)
        if not rule:
            return False

        # Update rule fields
        for key, value in kwargs.items():
            if hasattr(rule, key):
                setattr(rule, key, value)

        # Recalculate next run
        if rule.enabled:
            rule.calculate_next_run()

        self.logger.info(f"Updated scheduling rule: {rule.name}")
        return True

    def get_next_runs(self, limit: int = 10) -> list[tuple[datetime, ScheduleRule]]:
        """Get the next scheduled runs."""
        upcoming = [
            (rule.next_run, rule)
            for rule in self._rules.values()
            if rule.enabled and rule.next_run
        ]

        # Sort by next run time
        import operator

        upcoming.sort(key=operator.itemgetter(0))

        return upcoming[:limit]

    # Convenience methods for common scheduling patterns
    def schedule_cron(
        self,
        cron_expression: str,
        task_type: str,
        name: str | None = None,
        queue_name: str = "default",
        payload: dict[str, Any] | None = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        **kwargs: Any,
    ) -> UUID:
        """Schedule a task using a cron expression."""
        rule = ScheduleRule(
            name=name or f"cron_{task_type}",
            task_type=task_type,
            queue_name=queue_name,
            payload=payload or {},
            priority=priority,
            cron_expression=cron_expression,
            **kwargs,
        )

        return self.add_rule(rule)

    def schedule_interval(
        self,
        interval_seconds: float,
        task_type: str,
        name: str | None = None,
        queue_name: str = "default",
        payload: dict[str, Any] | None = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        **kwargs: Any,
    ) -> UUID:
        """Schedule a task to run at regular intervals."""
        rule = ScheduleRule(
            name=name or f"interval_{task_type}",
            task_type=task_type,
            queue_name=queue_name,
            payload=payload or {},
            priority=priority,
            interval_seconds=interval_seconds,
            **kwargs,
        )

        return self.add_rule(rule)

    def schedule_once(
        self,
        run_time: datetime,
        task_type: str,
        name: str | None = None,
        queue_name: str = "default",
        payload: dict[str, Any] | None = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        **kwargs: Any,
    ) -> UUID:
        """Schedule a task to run once at a specific time."""
        rule = ScheduleRule(
            name=name or f"once_{task_type}",
            task_type=task_type,
            queue_name=queue_name,
            payload=payload or {},
            priority=priority,
            start_time=run_time,
            max_runs=1,
            **kwargs,
        )

        return self.add_rule(rule)

    async def __aenter__(self) -> "TaskScheduler":
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.stop()


# Decorator for easy scheduling
def scheduled_task(
    scheduler: TaskScheduler,
    cron_expression: str | None = None,
    interval_seconds: float | None = None,
    name: str | None = None,
    queue_name: str = "default",
    priority: TaskPriority = TaskPriority.NORMAL,
    **rule_kwargs: Any,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to register a function as a scheduled task.

    Args:
        scheduler: TaskScheduler instance
        cron_expression: Cron expression for scheduling
        interval_seconds: Interval in seconds for scheduling
        name: Task name
        queue_name: Target queue name
        priority: Task priority
        **rule_kwargs: Additional rule arguments

    Returns:
        Decorator function
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        task_type = func.__name__
        rule_name = name or f"scheduled_{task_type}"

        if cron_expression:
            rule = ScheduleRule(
                name=rule_name,
                task_type=task_type,
                queue_name=queue_name,
                priority=priority,
                cron_expression=cron_expression,
                **rule_kwargs,
            )
        elif interval_seconds:
            rule = ScheduleRule(
                name=rule_name,
                task_type=task_type,
                queue_name=queue_name,
                priority=priority,
                interval_seconds=interval_seconds,
                **rule_kwargs,
            )
        else:
            msg = "Either cron_expression or interval_seconds must be provided"
            raise ValueError(
                msg,
            )

        # Register the rule
        scheduler.add_rule(rule)

        return func

    return decorator


# Utility functions
def create_scheduler(queue: QueueBase) -> TaskScheduler:
    """Create a task scheduler instance.

    Args:
        queue: Queue instance to schedule tasks on

    Returns:
        TaskScheduler instance
    """
    return TaskScheduler(queue)


def parse_cron_expression(expression: str) -> dict[str, Any]:
    """Parse a cron expression and return information about it.

    Args:
        expression: Cron expression to parse

    Returns:
        Information about the cron expression
    """
    if not CRONITER_AVAILABLE:
        msg = (
            "croniter is required for cron parsing. Install with: pip install croniter"
        )
        raise ImportError(
            msg,
        )

    try:
        if croniter:
            cron = croniter.croniter(expression)
        else:
            msg = "croniter is required for cron parsing"
            raise ImportError(msg)

        # Get next few runs
        next_runs = []
        datetime.now(tz=UTC)
        for _ in range(5):
            next_time = cron.get_next(datetime)
            next_runs.append(next_time.isoformat())

        return {
            "expression": expression,
            "valid": True,
            "next_runs": next_runs,
            "description": f"Cron expression: {expression}",
        }

    except Exception as e:
        return {
            "expression": expression,
            "valid": False,
            "error": str(e),
        }
