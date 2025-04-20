import asyncio
import os
import signal
import sys
import typing as t
from contextlib import suppress

import pytest

pytest_plugins = ["pytest_asyncio"]


@pytest.fixture(autouse=True)
async def cleanup_async_tasks():
    yield
    tasks = [a for a in asyncio.all_tasks() if a is not asyncio.current_task()]
    if tasks:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def pytest_sessionfinish(session: t.Any, exitstatus: t.Any) -> None:
    sys.stdout.flush()
    sys.stderr.flush()

    def kill_process() -> None:
        os.kill(os.getpid(), signal.SIGTERM)

    asyncio.get_event_loop().call_later(1.0, kill_process)

    with suppress(Exception):
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.5))
