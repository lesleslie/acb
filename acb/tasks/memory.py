"""In-memory queue implementation for unit tests and lightweight usage.

Implements a simple priority + scheduled queue based on the core QueueBase
APIs defined in `acb.tasks._base` with minimal dependencies.
"""

from __future__ import annotations

import heapq
import time

import typing as t
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from ._base import (
    QueueBase,
    QueueSettings,
    TaskData,
    TaskResult,
    TaskStatus,
)

if t.TYPE_CHECKING:
    from uuid import UUID


@dataclass
class PriorityTaskItem:
    """Item used for priority scheduling in the in-memory queue."""

    # Order by schedule timestamp, then by priority, then by insertion counter
    scheduled_time: float
    priority: int
    task: TaskData
    _count: int = field(default=0)

    def __post_init__(self) -> None:
        # Set default priority based on task priority if not provided
        if self.priority == 0 and hasattr(self, "task") and self.task:
            self.priority = -int(self.task.priority.value)

    def __lt__(self, other: PriorityTaskItem) -> bool:
        return (self.scheduled_time, self.priority, self._count) < (
            other.scheduled_time,
            other.priority,
            other._count,
        )

    def __init__(
        self,
        task: TaskData,
        scheduled_time: float,
        priority: int = 0,
        _count: int = 0,
    ) -> None:
        self.task = task
        self.scheduled_time = scheduled_time
        self.priority = priority if priority != 0 else -int(task.priority.value)
        self._count = _count

    @classmethod
    def from_task(cls, task: TaskData, count: int) -> PriorityTaskItem:
        if task.scheduled_at:
            ts = task.scheduled_at.replace(tzinfo=UTC).timestamp()
        else:
            ts = time.time() + max(0.0, task.delay)
        # higher TaskPriority value should be dequeued first, hence negative
        prio = -int(task.priority.value)
        return cls(task=task, scheduled_time=ts, priority=prio, _count=count)


class MemoryQueueSettings(QueueSettings):
    """Settings for in-memory queue."""

    enable_task_persistence: bool = False


class MemoryQueue(QueueBase):
    """A simple in-memory queue implementation with scheduling and priorities."""

    def __init__(self, settings: MemoryQueueSettings | None = None) -> None:
        super().__init__(settings or MemoryQueueSettings())
        self._queues: dict[str, list[PriorityTaskItem]] = {}
        self._task_status: dict[UUID, TaskResult] = {}
        self._completed_tasks: dict[UUID, TaskResult] = {}
        self._dead_letter_tasks: dict[UUID, tuple[TaskData, TaskResult]] = {}
        self._enqueue_counter = 0
        self._rate_window: list[float] = []  # timestamps of recent enqueues
        self._memory_usage = 0

    @property
    def _mem_limit(self) -> int:
        return self._settings.max_memory_usage

    def _estimate_size(self, task: TaskData) -> int:
        # Very rough estimate: serialize payload and some metadata
        payload_size = len(str(task.payload))
        overhead = 256
        return payload_size + overhead

    def _check_rate_limit(self) -> None:
        if not self._settings.enable_rate_limiting:
            return
        now = time.time()
        one_sec_ago = now - 1.0
        self._rate_window = [t for t in self._rate_window if t >= one_sec_ago]
        if len(self._rate_window) >= self._settings.rate_limit_per_second:
            msg = "Rate limit exceeded"
            raise RuntimeError(msg)
        self._rate_window.append(now)

    async def enqueue(self, task: TaskData) -> str:
        self._check_rate_limit()

        size = self._estimate_size(task)
        if self._memory_usage + size > self._mem_limit:
            msg = "Memory limit exceeded"
            raise RuntimeError(msg)

        qname = task.queue_name
        q = self._queues.setdefault(qname, [])
        if (
            self._settings.max_tasks_per_queue
            and len(q) >= self._settings.max_tasks_per_queue
        ):
            msg = f"Queue {qname} is full"
            raise RuntimeError(msg)

        self._enqueue_counter += 1
        item = PriorityTaskItem.from_task(task, self._enqueue_counter)
        heapq.heappush(q, item)

        self._memory_usage += size
        self._metrics.pending_tasks += 1

        # Track status
        self._task_status[task.task_id] = TaskResult(
            task_id=task.task_id,
            status=TaskStatus.PENDING,
            queue_name=task.queue_name,
        )

        return str(task.task_id)

    async def dequeue(self, queue_name: str | None = None) -> TaskData | None:
        now = time.time()

        if queue_name is not None:
            return self._pop_ready_from_queue(
                self._queues.setdefault(queue_name, []),
                now,
            )

        # No specific queue: consider heads of all queues
        best_queue, _best_item = self._find_best_queue_item(now)
        if best_queue is not None:
            return self._pop_ready_from_queue(best_queue, now)
        return None

    def _pop_ready_from_queue(
        self,
        q: list[PriorityTaskItem],
        now: float,
    ) -> TaskData | None:
        if not q:
            return None
        item = q[0]
        if item.scheduled_time > now:
            return None
        heapq.heappop(q)
        # Update counters
        self._metrics.pending_tasks = max(0, self._metrics.pending_tasks - 1)
        self._metrics.processing_tasks += 1
        # Track status
        self._task_status[item.task.task_id] = TaskResult(
            task_id=item.task.task_id,
            status=TaskStatus.PROCESSING,
            queue_name=item.task.queue_name,
        )
        return item.task

    def _find_best_queue_item(
        self,
        now: float,
    ) -> tuple[list[PriorityTaskItem] | None, PriorityTaskItem | None]:
        best_q: list[PriorityTaskItem] | None = None
        best_item: PriorityTaskItem | None = None
        for q in self._queues.values():
            if not q:
                continue
            head = q[0]
            if head.scheduled_time > now:
                continue
            if best_item is None or self._is_better_item(head, best_item):
                best_item = head
                best_q = q
        return best_q, best_item

    def _is_better_item(
        self,
        head: PriorityTaskItem,
        best_item: PriorityTaskItem,
    ) -> bool:
        return (
            head.scheduled_time,
            head.priority,
            head._count,
        ) < (
            best_item.scheduled_time,
            best_item.priority,
            best_item._count,
        )

    async def get_task_status(self, task_id: UUID) -> TaskResult | None:
        return self._task_status.get(task_id)

    async def cancel_task(self, task_id: UUID) -> bool:
        # Remove from any queue where present
        for q in self._queues.values():
            for i, item in enumerate(q):
                if item.task.task_id == task_id:
                    self._memory_usage = max(
                        0,
                        self._memory_usage - self._estimate_size(item.task),
                    )
                    del q[i]
                    heapq.heapify(q)
                    self._metrics.pending_tasks = max(
                        0,
                        self._metrics.pending_tasks - 1,
                    )
                    self._task_status[task_id] = TaskResult(
                        task_id=task_id,
                        status=TaskStatus.CANCELLED,
                    )
                    return True
        return False

    async def get_queue_info(self, queue_name: str) -> dict[str, t.Any]:
        q = self._queues.get(queue_name, [])
        return {"name": queue_name, "pending_tasks": len(q)}

    async def purge_queue(self, queue_name: str) -> int:
        q = self._queues.get(queue_name, [])
        count = len(q)
        # Update memory usage
        for item in q:
            self._memory_usage = max(
                0,
                self._memory_usage - self._estimate_size(item.task),
            )
        self._queues[queue_name] = []
        self._metrics.pending_tasks = max(0, self._metrics.pending_tasks - count)
        return count

    async def list_queues(self) -> list[str]:
        return list(self._queues.keys())

    async def _store_dead_letter_task(self, task: TaskData, result: TaskResult) -> None:
        self._dead_letter_tasks[task.task_id] = (task, result)
        self._metrics.dead_letter_tasks = len(self._dead_letter_tasks)

    async def get_dead_letter_tasks(self) -> list[tuple[TaskData, TaskResult]]:
        return list(self._dead_letter_tasks.values())

    async def retry_dead_letter_task(self, task_id: UUID) -> bool:
        entry = self._dead_letter_tasks.pop(task_id, None)
        if not entry:
            return False
        task, _ = entry
        await self.enqueue(task)
        self._metrics.dead_letter_tasks = len(self._dead_letter_tasks)
        return True

    async def clear_completed_tasks(self, *, older_than: timedelta) -> int:
        cutoff = datetime.now(tz=UTC) - older_than
        to_delete = []
        for tid, res in self._completed_tasks.items():
            if res.completed_at:
                # Ensure both datetimes are timezone-aware for comparison
                completed_at = res.completed_at
                if completed_at.tzinfo is None:
                    # Convert naive datetime to UTC
                    completed_at = completed_at.replace(tzinfo=UTC)
                if completed_at < cutoff:
                    to_delete.append(tid)
        for tid in to_delete:
            del self._completed_tasks[tid]
        return len(to_delete)

    async def health_check(self) -> dict[str, t.Any]:
        base = await super().health_check()
        base["memory_queue"] = {
            "memory_usage": self._memory_usage,
            "memory_limit": self._mem_limit,
            "total_tasks": base["metrics"]["pending_tasks"]
            + base["metrics"]["processing_tasks"],
        }
        return base


def create_memory_queue(settings: MemoryQueueSettings | None = None) -> MemoryQueue:
    return MemoryQueue(settings)
