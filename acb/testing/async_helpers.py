"""ACB Async Testing Helpers.

Provides utilities for testing asynchronous code, managing async contexts,
and handling async lifecycle management in ACB applications.

Features:
- Async test case base class
- Async fixture management
- Task cleanup utilities
- Condition waiting helpers
- Timeout handling for async operations
"""

from unittest import TestCase
from unittest.mock import AsyncMock

import asyncio
import typing as t
from contextlib import asynccontextmanager, suppress


class AsyncTestCase(TestCase):
    """Base test case for async testing with proper setup and teardown."""

    def setUp(self) -> None:
        """Setup async test environment."""
        super().setUp()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self._async_resources: list[t.Any] = []

    def tearDown(self) -> None:
        """Cleanup async test environment."""
        # Cleanup registered resources
        for resource in self._async_resources:
            with suppress(Exception):
                if hasattr(resource, "cleanup"):
                    self.loop.run_until_complete(resource.cleanup())
                elif hasattr(resource, "close"):
                    self.loop.run_until_complete(resource.close())
                elif hasattr(resource, "__aexit__"):
                    self.loop.run_until_complete(resource.__aexit__(None, None, None))

        # Close the loop
        with suppress(Exception):
            self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            self.loop.close()

        super().tearDown()

    def run_async(self, coro: t.Awaitable[t.Any]) -> t.Any:
        """Run an async coroutine in the test loop."""
        return self.loop.run_until_complete(coro)

    def register_async_resource(self, resource: t.Any) -> t.Any:
        """Register an async resource for cleanup."""
        self._async_resources.append(resource)
        return resource

    async def async_setup(self) -> None:
        """Override this method for async setup logic."""

    async def async_teardown(self) -> None:
        """Override this method for async teardown logic."""

    def run(self, result: t.Any = None) -> None:
        """Override run to handle async setup/teardown."""
        # Run async setup
        if hasattr(self, "async_setup"):
            self.loop.run_until_complete(self.async_setup())

        try:
            super().run(result)
        finally:
            # Run async teardown
            if hasattr(self, "async_teardown"):
                self.loop.run_until_complete(self.async_teardown())


@asynccontextmanager
async def async_test_fixture(
    setup_func: t.Callable[[], t.Any]
    | t.Callable[[], t.Awaitable[t.Any]]
    | None = None,
    teardown_func: t.Callable[[t.Any], t.Any]
    | t.Callable[[t.Any], t.Awaitable[t.Any]]
    | None = None,
) -> t.AsyncGenerator[t.Any]:
    """Async context manager for test fixtures."""
    resource = None

    try:
        # Setup
        if setup_func:
            if asyncio.iscoroutinefunction(setup_func):
                resource = await setup_func()
            else:
                resource = setup_func()

        yield resource

    finally:
        # Teardown
        if teardown_func:
            with suppress(Exception):
                if asyncio.iscoroutinefunction(teardown_func):
                    await teardown_func(resource)
                else:
                    teardown_func(resource)


async def cleanup_async_tasks(timeout: float = 5.0) -> None:
    """Cleanup all pending async tasks."""
    with suppress(Exception):
        # Get all pending tasks
        tasks = [task for task in asyncio.all_tasks() if not task.done()]

        if not tasks:
            return

        # Cancel all tasks
        for task in tasks:
            task.cancel()

        # Wait for tasks to complete or timeout
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=timeout,
            )
        except TimeoutError:
            # Force cleanup if timeout exceeded
            for task in tasks:
                if not task.done():
                    task.cancel()


async def wait_for_condition(
    condition_func: t.Callable[[], bool] | t.Callable[[], t.Awaitable[bool]],
    timeout: float = 10.0,
    interval: float = 0.1,
    timeout_message: str | None = None,
) -> bool:
    """Wait for a condition to become true."""
    start_time = asyncio.get_event_loop().time()
    end_time = start_time + timeout

    while asyncio.get_event_loop().time() < end_time:
        with suppress(Exception):
            if asyncio.iscoroutinefunction(condition_func):
                result = await condition_func()
            else:
                result = condition_func()

            if result:
                return True

        await asyncio.sleep(interval)

    # Timeout exceeded
    message = timeout_message or f"Condition not met within {timeout} seconds"
    raise TimeoutError(message)


async def timeout_async_call(
    coro: t.Awaitable[t.Any],
    timeout: float,
    timeout_message: str | None = None,
) -> t.Any:
    """Execute an async call with timeout."""
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except TimeoutError:
        message = timeout_message or f"Operation timed out after {timeout} seconds"
        raise TimeoutError(message)


@asynccontextmanager
async def mock_async_context(
    mock_class: type = AsyncMock,
    **mock_kwargs: t.Any,
) -> t.AsyncGenerator[AsyncMock]:
    """Create a mock async context manager."""
    mock = mock_class(**mock_kwargs)

    # Ensure it has async context manager methods
    if not hasattr(mock, "__aenter__"):
        mock.__aenter__ = AsyncMock(return_value=mock)
    if not hasattr(mock, "__aexit__"):
        mock.__aexit__ = AsyncMock(return_value=None)

    async with mock:
        yield mock


class AsyncMockContextManager:
    """Helper class for creating async context manager mocks."""

    def __init__(
        self,
        return_value: t.Any = None,
        side_effect: t.Callable[[], t.Any]
        | t.Callable[[], t.Awaitable[t.Any]]
        | None = None,
    ) -> None:
        self.return_value = return_value
        self.side_effect = side_effect
        self.enter_count = 0
        self.exit_count = 0

    async def __aenter__(self) -> t.Any:
        self.enter_count += 1
        if self.side_effect:
            if asyncio.iscoroutinefunction(self.side_effect):
                return await self.side_effect()
            return self.side_effect()
        return self.return_value or self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: t.Any,
    ) -> None:
        self.exit_count += 1


def create_async_mock_with_context(
    return_value: t.Any = None,
    side_effect: t.Callable[[], t.Any]
    | t.Callable[[], t.Awaitable[t.Any]]
    | None = None,
) -> AsyncMock:
    """Create an AsyncMock that can be used as an async context manager."""
    mock = AsyncMock()

    # Add context manager behavior
    context_manager = AsyncMockContextManager(return_value, side_effect)
    mock.__aenter__ = context_manager.__aenter__
    mock.__aexit__ = context_manager.__aexit__

    return mock


async def run_with_retry(
    coro_func: t.Callable[[], t.Awaitable[t.Any]],
    max_retries: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> t.Any:
    """Run an async function with retry logic."""
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return await coro_func()
        except exceptions as e:
            last_exception = e
            if attempt < max_retries:
                await asyncio.sleep(delay * (backoff_factor**attempt))
            else:
                raise last_exception
    return None


class AsyncEventWaiter:
    """Helper for waiting on async events."""

    def __init__(self) -> None:
        self._events: dict[str, asyncio.Event] = {}
        self._event_data: dict[str, t.Any] = {}

    def create_event(self, name: str) -> asyncio.Event:
        """Create a named event."""
        event = asyncio.Event()
        self._events[name] = event
        return event

    def set_event(self, name: str, data: t.Any = None) -> None:
        """Set an event and optionally store data."""
        if name in self._events:
            if data is not None:
                self._event_data[name] = data
            self._events[name].set()

    async def wait_for_event(self, name: str, timeout: float | None = None) -> t.Any:
        """Wait for an event to be set."""
        if name not in self._events:
            self.create_event(name)

        event = self._events[name]

        if timeout:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        else:
            await event.wait()

        return self._event_data.get(name)

    def clear_event(self, name: str) -> None:
        """Clear an event."""
        if name in self._events:
            self._events[name].clear()
            self._event_data.pop(name, None)


def async_test(
    coro_func: t.Callable[..., t.Awaitable[t.Any]],
) -> t.Callable[..., t.Any]:
    """Decorator to run async test functions."""

    def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro_func(*args, **kwargs))
        finally:
            loop.close()

    return wrapper


@asynccontextmanager
async def temporary_async_task(
    coro: t.Coroutine[t.Any, t.Any, t.Any],
    name: str | None = None,
) -> t.AsyncGenerator[asyncio.Task[t.Any]]:
    """Context manager for temporary async tasks."""
    task: asyncio.Task[t.Any] = asyncio.create_task(coro, name=name)

    try:
        yield task
    finally:
        if not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


class AsyncResourceManager:
    """Manager for async resources with automatic cleanup."""

    def __init__(self) -> None:
        self._resources: list[t.Any] = []

    def register(self, resource: t.Any) -> t.Any:
        """Register a resource for cleanup."""
        self._resources.append(resource)
        return resource

    async def cleanup_all(self) -> None:
        """Cleanup all registered resources."""
        for resource in reversed(self._resources):  # Cleanup in reverse order
            with suppress(Exception):
                if hasattr(resource, "cleanup"):
                    await resource.cleanup()
                elif hasattr(resource, "close"):
                    await resource.close()
                elif hasattr(resource, "__aexit__"):
                    await resource.__aexit__(None, None, None)

        self._resources.clear()

    async def __aenter__(self) -> "AsyncResourceManager":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: t.Any,
    ) -> None:
        await self.cleanup_all()


def create_async_generator_mock(items: list[t.Any]) -> AsyncMock:
    """Create a mock async generator."""

    async def async_generator() -> t.AsyncGenerator[t.Any]:
        for item in items:
            yield item

    mock = AsyncMock()
    mock.__aiter__ = AsyncMock(return_value=async_generator())
    return mock


async def assert_async_raises(
    exception_class: type[Exception],
    coro: t.Awaitable[t.Any],
    message: str | None = None,
) -> None:
    """Assert that an async operation raises a specific exception."""
    try:
        await coro
        msg = f"Expected {exception_class.__name__} was not raised"
        raise AssertionError(msg)
    except exception_class:
        # Expected exception was raised
        pass
    except Exception as e:
        if message:
            msg = f"{message}: Expected {exception_class.__name__}, got {type(e).__name__}"
            raise AssertionError(msg)
        msg = f"Expected {exception_class.__name__}, got {type(e).__name__}"
        raise AssertionError(msg)


@asynccontextmanager
async def async_timeout_context(
    timeout: float,
    message: str | None = None,
) -> t.AsyncGenerator[None]:
    """Context manager that raises TimeoutError if operations take too long."""
    try:
        async with asyncio.timeout(timeout):
            yield
    except TimeoutError:
        raise TimeoutError(message or f"Operation timed out after {timeout} seconds")
