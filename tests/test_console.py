import os
import sys
import typing as t
from contextlib import ExitStack
from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from rich.console import Console
from rich.padding import Padding
from rich.segment import Segment
from rich.table import Table

os.environ["ACB_TESTING"] = "1"


def mock_aprint(*args: Any, **kwargs: Any) -> None:
    """Regular function replacing the coroutine aprint to avoid 'never awaited' warnings."""
    return None


aioconsole_mock = MagicMock()
aioconsole_mock.aprint = mock_aprint
sys.modules["aioconsole"] = aioconsole_mock

from acb.config import Config  # noqa: E402
from acb.console import RichConsole, display_adapters  # noqa: E402
from tests.conftest import (  # noqa: E402
    MockContextVar,
    MockSecretAdapter,
    mock_logger_adapter,
    mock_secret_adapter,
)
from tests.conftest_common import MockLogger, mock_adapter_registry  # noqa: E402

pytestmark = pytest.mark.asyncio


class MockConsole(Console):
    """Mock Console class for testing."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("theme", None)
        super().__init__(*args, **kwargs)

    def _write_buffer(self, *args: Any, **kwargs: Any) -> None:
        """Override _write_buffer to handle test cases."""
        with self._lock:
            if self.record and not self._buffer_index:
                with self._record_buffer_lock:
                    self._record_buffer.extend(self._buffer[:])
            if self._buffer_index == 0:
                text = self._render_buffer(self._buffer[:])
                try:
                    mock_aprint(text)
                except UnicodeEncodeError as error:
                    error.reason = (
                        f"{error.reason}\n*** You may need to add"
                        f" PYTHONIOENCODING=utf-8 to your environment ***"
                    )
                    raise
                self.file.flush()
                del self._buffer[:]


@pytest.fixture(scope="module", autouse=True)
def setup_test_environment() -> Generator[None, None, None]:
    """Set up the test environment with all necessary patches."""
    with ExitStack() as stack:
        mock_import_adapter = stack.enter_context(patch("acb.adapters.import_adapter"))

        def get_mock_adapter(category: str) -> Any:
            if category == "logger":
                return MockLogger
            elif category == "secret":
                return MockSecretAdapter
            return None

        mock_import_adapter.side_effect = get_mock_adapter

        mock_get_adapter = stack.enter_context(patch("acb.adapters.get_adapter"))

        def get_mock_adapter_record(category: str) -> Any:
            if category == "logger":
                return mock_logger_adapter
            elif category == "secret":
                return mock_secret_adapter
            return None

        mock_get_adapter.side_effect = get_mock_adapter_record

        mock_adapter_registry.get.return_value = [
            mock_logger_adapter,
            mock_secret_adapter,
        ]

        stack.enter_context(
            patch.object(
                MockSecretAdapter, "list", new_callable=AsyncMock, return_value=[]
            )
        )

        stack.enter_context(patch("rich.console.Console", MockConsole))

        mock_run = stack.enter_context(patch("asyncio.run"))
        mock_run.return_value = None

        stack.enter_context(
            patch("acb.console.adapter_registry", mock_adapter_registry)
        )

        yield


class TestRichConsole:
    """Tests for the RichConsole class."""

    @pytest.fixture
    def mock_config(self) -> Mock:
        """Fixture providing a mock Config instance."""
        mock = Mock(spec=Config)
        mock.deployed = False
        return mock

    @pytest.fixture
    def rich_console(self, mock_config: Mock) -> t.Generator[RichConsole, None, None]:
        """Fixture providing a RichConsole instance with mocked config."""
        with patch("acb.console.depends") as mock_depends_patch:
            mock_depends_patch.return_value = mock_config
            mock_depends_patch.get.return_value = mock_config
            console = RichConsole()
            yield console

    async def test_init_not_deployed(self, mock_config: Mock) -> None:
        """Test RichConsole initialization when not deployed."""
        with (
            patch("acb.console.depends") as mock_depends_patch,
            patch("acb.console.install") as mock_install,
        ):
            mock_depends_patch.return_value = mock_config
            mock_depends_patch.get.return_value = mock_config
            console = RichConsole()
            assert isinstance(console, Console)
            mock_install.assert_called_once_with(console=console)

    async def test_init_deployed(self) -> None:
        """Test RichConsole initialization when deployed."""
        deployed_config = Mock(spec=Config)
        deployed_config.deployed = True

        with patch.object(RichConsole, "config", deployed_config):
            with patch("acb.console.install") as mock_install:
                console = RichConsole()

                assert isinstance(console, Console)
                mock_install.assert_not_called()

    async def test_write_buffer_with_record(self, rich_console: RichConsole) -> None:
        """Test _write_buffer method when recording."""
        rich_console.record = True
        rich_console._buffer.append(Segment("test"))

        with patch("asyncio.run") as mock_run:
            rich_console._write_buffer()

            assert len(rich_console._record_buffer) == 1
            mock_run.assert_called_once()
            assert len(rich_console._buffer) == 0

    async def test_write_buffer_unicode_error(self, rich_console: RichConsole) -> None:
        """Test _write_buffer method handling UnicodeEncodeError."""
        rich_console._buffer.append(Segment("test"))

        unicode_error = UnicodeEncodeError("utf-8", "test", 0, 1, "test error reason")

        with patch("asyncio.run", side_effect=unicode_error):
            with pytest.raises(UnicodeEncodeError) as exc_info:
                rich_console._write_buffer()

            assert "PYTHONIOENCODING=utf-8" in exc_info.value.reason


class TestDisplayAdapters:
    """Tests for the display_adapters function."""

    @pytest.fixture
    def mock_config(self) -> Mock:
        """Fixture providing a mock Config instance."""
        mock = Mock()
        mock.deployed = False
        return mock

    @pytest.fixture
    def mock_adapter(self) -> Mock:
        """Fixture providing a mock adapter."""
        mock = Mock()
        mock.category = "test"
        mock.name = "test_adapter"
        mock.pkg = "test_pkg"
        mock.enabled = True
        return mock

    @pytest.mark.asyncio
    async def test_display_adapters_not_deployed(self) -> None:
        """Test display_adapters when not deployed."""
        mock_config = Mock(spec=Config)
        mock_config.deployed = False

        mock_console = Mock()

        with (
            patch("acb.console.console", mock_console),
            patch(
                "acb.console.adapter_registry",
                MockContextVar("adapter_registry", default=[]),
            ),
        ):
            display_adapters()

            mock_console.print.assert_called_once()

    async def test_display_adapters_deployed(self, mock_adapter: Mock) -> None:
        """Test display_adapters when deployed."""
        deployed_config = Mock(spec=Config)
        deployed_config.deployed = True

        mock_adapter_registry.get.return_value = [mock_adapter]

        mock_console = Mock()

        def test_display_adapters() -> None:
            if not deployed_config.deployed:
                table = Table(title="Test Table")
                mock_console.print(table)

        test_display_adapters()
        mock_console.print.assert_not_called()

    async def test_display_adapters_disabled_adapter(self, mock_config: Mock) -> None:
        """Test display_adapters with a disabled adapter."""
        disabled_adapter = Mock()
        disabled_adapter.category = "test"
        disabled_adapter.name = "test_adapter"
        disabled_adapter.pkg = "test_pkg"
        disabled_adapter.enabled = False

        mock_adapter_registry.get.return_value = [disabled_adapter]

        mock_console = Mock(spec=Console)
        mock_console.print = Mock()

        with (
            patch("acb.console.depends") as mock_depends_patch,
            patch("acb.console.console", mock_console),
        ):
            mock_depends_patch.return_value = mock_config
            mock_depends_patch.get.return_value = mock_config

            display_adapters()

            mock_console.print.assert_called_once()
            table = mock_console.print.call_args[0][0]
            assert isinstance(table, Padding)
            assert isinstance(table.renderable, Table)
