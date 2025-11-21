from uuid import UUID

import pytest
from datetime import datetime

from acb.tasks._base import (
    FunctionalTaskHandler,
    TaskData,
    TaskPriority,
    create_task_data,
    generate_queue_id,
    task_handler,
)


def test_taskdata_parses_scheduled_at_string() -> None:
    ts = "2025-01-02T03:04:05"
    td = TaskData(task_type="x", queue_name="q", scheduled_at=ts)
    assert isinstance(td.scheduled_at, datetime)


@pytest.mark.asyncio
async def test_task_handler_decorator_success() -> None:
    @task_handler("echo")
    async def echo(task: TaskData) -> int:
        return task.payload.get("value", 0) + 1

    # Decorator returns a FunctionalTaskHandler instance
    assert isinstance(echo, FunctionalTaskHandler)

    task = TaskData(task_type="echo", queue_name="q", payload={"value": 41})
    result = await echo.handle(task)
    assert result.result == 42
    assert result.status.name.lower() == "completed"


@pytest.mark.asyncio
async def test_task_handler_decorator_failure_path() -> None:
    @task_handler("boom")
    async def boom(_task: TaskData) -> int:  # pragma: no cover - invoked via handler
        raise RuntimeError("nope")

    task = TaskData(task_type="boom", queue_name="q")
    result = await boom.handle(task)
    assert result.status.name.lower() == "failed"
    assert "nope" in (result.error or "")


def test_create_task_data_defaults() -> None:
    td = create_task_data("t", queue_name="q")
    assert td.task_type == "t"
    assert td.queue_name == "q"
    assert td.priority == TaskPriority.NORMAL
    assert td.payload == {}


def test_generate_queue_id() -> None:
    a = generate_queue_id()
    b = generate_queue_id()
    assert isinstance(a, UUID) and isinstance(b, UUID)
    assert a != b


@pytest.mark.asyncio
async def test_task_handler_custom_callbacks() -> None:
    called = {"success": False}

    async def on_success(_task: TaskData, _result) -> None:
        called["success"] = True

    async def on_failure(_task: TaskData, _exc: Exception) -> bool:
        return False

    @task_handler("ok", on_success=on_success, on_failure=on_failure)
    async def ok(_task: TaskData) -> int:
        return 1

    task = TaskData(task_type="ok", queue_name="q")

    # success callback is invoked when called explicitly
    res = await ok.handle(task)
    await ok.on_success(task, res)
    assert called["success"] is True

    # failure callback returns False when invoked
    assert await ok.on_failure(task, RuntimeError("x")) is False
