"""Background task management for ACB framework.

This module provides utilities for managing background tasks to prevent
memory leaks and ensure proper cleanup of async operations.
"""

import asyncio
import typing as t
import weakref
from contextlib import suppress
from functools import wraps

from .depends import depends
from .logger import Logger

_background_tasks: set[asyncio.Task[t.Any]] = set()
_task_registry: weakref.WeakSet[asyncio.Task[t.Any]] = weakref.WeakSet()


def create_background_task(
    coro: t.Coroutine[t.Any, t.Any, t.Any],
    name: str | None = None,
    logger: Logger | None = None,
) -> asyncio.Task[t.Any]:
    """Create a background task with proper cleanup.

    Args:
        coro: The coroutine to run as a background task
        name: Optional name for the task (useful for debugging)
        logger: Optional logger instance

    Returns:
        The created asyncio.Task

    Example:
        >>> async def background_work():
        ...     await asyncio.sleep(10)
        ...     print("Background work completed")
        >>>
        >>> task = create_background_task(background_work())
    """
    if logger is None:
        logger = depends.get(Logger)

    task = asyncio.create_task(coro, name=name)
    _background_tasks.add(task)
    _task_registry.add(task)

    def _cleanup_task(task_ref: asyncio.Task[t.Any]) -> None:
        _background_tasks.discard(task_ref)
        if task_ref.done() and not task_ref.cancelled():
            with suppress(asyncio.CancelledError):
                exception = task_ref.exception()
                if exception is not None:
                    logger.error(
                        f"Background task {task_ref.get_name()} failed",
                        exc_info=exception,
                    )

    task.add_done_callback(_cleanup_task)
    return task


def background_task(
    name: str | None = None,
    logger: Logger | None = None,
) -> t.Callable[
    [t.Callable[..., t.Coroutine[t.Any, t.Any, t.Any]]],
    t.Callable[..., asyncio.Task[t.Any]],
]:
    """Decorator to automatically run a function as a background task.

    Args:
        name: Optional name for the task
        logger: Optional logger instance

    Example:
        >>> @background_task(name="data_processor")
        ... async def process_data(data: dict) -> None:
        ...     await asyncio.sleep(1)
        ...     print(f"Processed: {data}")
        >>>
        >>>
        >>> task = process_data({"key": "value"})
    """

    def decorator(
        func: t.Callable[..., t.Coroutine[t.Any, t.Any, t.Any]],
    ) -> t.Callable[..., asyncio.Task[t.Any]]:
        @wraps(func)
        def wrapper(*args: t.Any, **kwargs: t.Any) -> asyncio.Task[t.Any]:
            coro = func(*args, **kwargs)
            task_name = name or f"{func.__module__}.{func.__name__}"
            return create_background_task(coro, task_name, logger)

        return wrapper

    return decorator


async def wait_for_background_tasks(timeout: float | None = None) -> None:
    if not _background_tasks:
        return
    logger = depends.get(Logger)
    logger.info(f"Waiting for {len(_background_tasks)} background tasks to complete")
    try:
        await asyncio.wait_for(
            asyncio.gather(*_background_tasks, return_exceptions=True), timeout=timeout
        )
    except TimeoutError:
        logger.warning(f"Background tasks did not complete within {timeout} seconds")
        await cancel_background_tasks()


async def cancel_background_tasks() -> None:
    if not _background_tasks:
        return
    logger = depends.get(Logger)
    logger.info(f"Cancelling {len(_background_tasks)} background tasks")
    for task in _background_tasks.copy():
        if not task.done():
            task.cancel()
    if _background_tasks:
        await asyncio.gather(*_background_tasks, return_exceptions=True)
    _background_tasks.clear()


def get_background_task_count() -> int:
    return len(_background_tasks)


def get_background_task_info() -> list[dict[str, t.Any]]:
    task_info = []
    for task in _background_tasks:
        info = {
            "name": task.get_name(),
            "done": task.done(),
            "cancelled": task.cancelled(),
        }
        if task.done() and not task.cancelled():
            with suppress(Exception):
                exception = task.exception()
                info["exception"] = str(exception) if exception else ""
        task_info.append(info)
    return task_info


class BackgroundTaskManager:
    def __init__(self, cleanup_timeout: float = 30.0) -> None:
        self.cleanup_timeout = cleanup_timeout
        self.logger = depends.get(Logger)

    async def __aenter__(self) -> "BackgroundTaskManager":
        self.logger.debug("Background task manager started")
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: t.Any | None,
    ) -> None:
        del exc_type, exc_val, exc_tb
        self.logger.debug("Background task manager shutting down")
        await wait_for_background_tasks(self.cleanup_timeout)


class TaskRateLimiter:
    def __init__(self, max_concurrent: int = 10) -> None:
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.max_concurrent = max_concurrent

    async def submit(
        self,
        coro: t.Coroutine[t.Any, t.Any, t.Any],
        name: str | None = None,
    ) -> asyncio.Task[t.Any]:
        """Submit a coroutine with rate limiting."""

        async def rate_limited_coro() -> t.Any:
            async with self.semaphore:
                return await coro

        return create_background_task(rate_limited_coro(), name)

    def get_available_slots(self) -> int:
        return self.semaphore._value  # type: ignore
