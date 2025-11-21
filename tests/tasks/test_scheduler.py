import pytest
from datetime import UTC, datetime, timedelta
from typing import Any

from acb.tasks._base import (
    QueueBase,
    TaskData,
    TaskPriority,
)
from acb.tasks.scheduler import ScheduleRule, TaskScheduler


class DummyQueue(QueueBase):
    """Minimal QueueBase implementation capturing enqueued tasks for tests."""

    def __init__(self) -> None:
        super().__init__(None)
        self.enqueued: list[TaskData] = []

    async def enqueue(self, task: TaskData) -> str:
        self.enqueued.append(task)
        return str(task.task_id)

    async def dequeue(
        self, queue_name: str | None = None
    ) -> TaskData | None:  # pragma: no cover - not used
        return None

    async def get_task_status(self, task_id):  # pragma: no cover - not used
        return None

    async def cancel_task(self, task_id):  # pragma: no cover - not used
        return False

    async def get_queue_info(
        self, queue_name: str
    ) -> dict[str, Any]:  # pragma: no cover - not used
        return {"name": queue_name}

    async def purge_queue(self, queue_name: str) -> int:  # pragma: no cover - not used
        return 0

    async def list_queues(self) -> list[str]:  # pragma: no cover - not used
        return []


@pytest.mark.asyncio
async def test_execute_rule_enqueues_task_with_tags() -> None:
    queue = DummyQueue()
    scheduler = TaskScheduler(queue)

    rule = ScheduleRule(
        name="rule1",
        task_type="t",
        queue_name="q",
        payload={"x": 1},
        priority=TaskPriority.HIGH,
        interval_seconds=1,
    )

    now = datetime.now(tz=UTC)
    await scheduler._execute_rule(rule, now)

    assert len(queue.enqueued) == 1
    task = queue.enqueued[0]
    assert task.task_type == "t"
    assert task.queue_name == "q"
    # Scheduler injects tags including scheduled flag and rule metadata
    assert task.tags.get("scheduled") == "true"
    assert task.tags.get("rule_name") == "rule1"


def test_schedule_rule_interval_next_run_and_should_run() -> None:
    rule = ScheduleRule(
        name="interval_test",
        task_type="t",
        queue_name="q",
        interval_seconds=0.01,
    )

    assert rule.next_run is not None
    # If current time advances past next_run, should_run becomes True
    future = (rule.next_run or datetime.now(tz=UTC)) + timedelta(seconds=0.05)
    assert rule.should_run(future) is True


def test_schedule_rule_start_end_bounds_disable_runs() -> None:
    start = datetime.now(tz=UTC) + timedelta(seconds=10)
    end = start + timedelta(milliseconds=500)
    rule = ScheduleRule(
        name="bounded",
        task_type="t",
        queue_name="q",
        interval_seconds=1.0,
        start_time=start,
        end_time=end,
    )

    # Next run would be start+interval which exceeds end_time → no next run
    assert rule.next_run is None
    assert rule.should_run(start) is False


def test_cron_expression_requires_croniter(monkeypatch: pytest.MonkeyPatch) -> None:
    # Force croniter to be unavailable to exercise ImportError path
    import acb.tasks.scheduler as mod

    monkeypatch.setattr(mod, "CRONITER_AVAILABLE", False, raising=False)
    monkeypatch.setattr(mod, "croniter", None, raising=False)

    with pytest.raises(ImportError):
        ScheduleRule(
            name="cron_rule",
            task_type="t",
            queue_name="q",
            cron_expression="*/5 * * * *",
        )


def test_scheduled_task_requires_one_of_cron_or_interval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queue = DummyQueue()
    scheduler = TaskScheduler(queue)

    from acb.tasks.scheduler import scheduled_task

    with pytest.raises(ValueError):

        @scheduled_task(scheduler)  # neither cron nor interval provided
        def demo():
            return None
