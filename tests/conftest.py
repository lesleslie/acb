import asyncio
import os
import signal
import sys
from contextlib import suppress
from typing import AsyncGenerator, Final, NoReturn, TypeAlias

import pytest
from _pytest.config import Config
from _pytest.config.argparsing import Parser
from _pytest.main import Session

TaskSet: TypeAlias = set[asyncio.Task[object]]
MarkerTuple: TypeAlias = tuple[str, str]

pytest_plugins: Final[list[str]] = ["pytest_asyncio"]


def pytest_configure(config: Config) -> None:
    markers: list[MarkerTuple] = [
        ("unit", "Mark test as a unit test"),
        ("integration", "Mark test as an integration test"),
        ("async_test", "Mark test as an async test"),
        ("slow", "Mark test as a slow running test"),
    ]
    for marker, help_text in markers:
        config.addinivalue_line("markers", f"{marker}: {help_text}")


@pytest.fixture(autouse=True)
async def cleanup_async_tasks() -> AsyncGenerator[None, None]:
    yield
    current_task: asyncio.Task[object] | None = asyncio.current_task()
    tasks: TaskSet = {task for task in asyncio.all_tasks() if task is not current_task}
    if tasks:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def pytest_sessionfinish(session: Session, exitstatus: int | pytest.ExitCode) -> None:
    sys.stdout.flush()
    sys.stderr.flush()

    def kill_process() -> NoReturn:
        os.kill(os.getpid(), signal.SIGTERM)
        raise SystemExit(exitstatus)

    loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
    loop.call_later(1.0, kill_process)

    with suppress(Exception):
        loop.run_until_complete(asyncio.sleep(0.5))


def pytest_addoption(parser: Parser) -> None:
    parser.addoption(
        "--run-slow", action="store_true", default=False, help="run slow tests"
    )


def pytest_collection_modifyitems(config: Config, items: list[pytest.Item]) -> None:
    if not config.getoption("--run-slow"):
        skip_slow = pytest.mark.skip(reason="need --run-slow option to run")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)
