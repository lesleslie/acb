import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Sequence, TypeVar
from unittest.mock import Mock, patch

from tests.conftest_common import (
    MockContextVar,
    MockLogger,
)

T = TypeVar("T")

os.environ["TESTING"] = "True"
os.environ["ACB_TESTING"] = "1"


class MockAdapter:
    """Mock implementation of an adapter."""

    def __init__(
        self,
        category: str,
        name: str,
        class_name: str,
        module: str = "acb.tests.mocks.mock_adapter",
        pkg: str = "acb",
        enabled: bool = True,
        installed: bool = True,
    ) -> None:
        self.category = category
        self.name = name
        self.class_name = class_name
        self.module = module
        self.pkg = pkg
        self.enabled = enabled
        self.installed = installed

    def __eq__(self, other: Any) -> bool:
        if not hasattr(other, "category"):
            return False
        return self.category == other.category


mock_logger_adapter = MockAdapter(
    category="logger",
    name="loguru",
    class_name="Logger",
    module="acb.adapters.logger.loguru",
)

mock_registry: Sequence[MockAdapter] = [mock_logger_adapter]


def mock_asyncio_run(coro: Any) -> Any:
    """Mock implementation of asyncio.run that handles gather coroutines.

    This checks if the coroutine is from asyncio.gather and if so,
    returns a list with appropriate values for our tests.
    """
    if hasattr(coro, "_coro") and "gather" in str(coro._coro):
        return [MockLogger]
    return Mock()


root_path = Path(__file__).parent.parent / "acb"
adapters_path = root_path / "tests" / "adapters"
adapters_path.mkdir(exist_ok=True, parents=True)
adapters_file = adapters_path / "adapters.yml"
if not adapters_file.exists():
    adapters_file.write_text("---\nlogger: loguru\n")

if "acb.adapters" in sys.modules:
    from acb.adapters import adapter_registry

    adapter_registry.set(list(mock_registry))  # type: ignore
else:
    patch(
        "acb.adapters.adapter_registry",
        MockContextVar("adapter_registry", list(mock_registry)),
    ).start()
    patch("acb.adapters._install_lock", MockContextVar("install_lock", [])).start()

mock_logger_module = ModuleType("acb.tests.mocks.logger")
setattr(mock_logger_module, "Logger", MockLogger)
sys.modules["acb.tests.mocks.logger"] = mock_logger_module

patch("acb.adapters.asyncio.run", lambda coro: coro).start()
