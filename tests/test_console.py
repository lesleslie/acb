import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rich.console import Console
from rich.segment import Segment
from acb.console import RichConsole, console


class TestRichConsole:
    def test_rich_console_init(self) -> None:
        rich_console = RichConsole()
        assert isinstance(rich_console, Console)

    @patch("acb.console.aprint")
    @patch("asyncio.run")
    def test_write_buffer_success(
        self, mock_run: MagicMock, mock_aprint: AsyncMock
    ) -> None:
        rich_console = RichConsole()
        # Add test content to buffer
        rich_console._buffer.append(Segment("test content"))
        rich_console._buffer_index = 0
        rich_console.record = False

        with patch.object(rich_console, "_render_buffer", return_value="rendered text"):
            rich_console._write_buffer()

        mock_run.assert_called_once()
        assert not rich_console._buffer

    @patch("acb.console.aprint")
    @patch("asyncio.run")
    def test_write_buffer_with_record(
        self, mock_run: MagicMock, mock_aprint: AsyncMock
    ) -> None:
        rich_console = RichConsole()
        # Add test content to buffer
        rich_console._buffer.append(Segment("test content"))
        rich_console._buffer_index = 0
        rich_console.record = True

        with patch.object(rich_console, "_render_buffer", return_value="rendered text"):
            rich_console._write_buffer()

        mock_run.assert_called_once()
        assert rich_console._record_buffer == [Segment("test content")]

    @patch("acb.console.aprint")
    @patch("asyncio.run")
    def test_write_buffer_unicode_error(
        self, mock_run: MagicMock, mock_aprint: AsyncMock
    ) -> None:
        rich_console = RichConsole()
        # Add test content to buffer
        rich_console._buffer.append(Segment("test content"))
        rich_console._buffer_index = 0
        rich_console.record = False

        unicode_error = UnicodeEncodeError("utf-8", "test", 0, 1, "original reason")
        mock_run.side_effect = unicode_error

        with patch.object(rich_console, "_render_buffer", return_value="rendered text"):
            with pytest.raises(UnicodeEncodeError) as exc_info:
                rich_console._write_buffer()

        assert (
            "original reason\n*** You may need to add PYTHONIOENCODING=utf-8 to your environment ***"
            in str(exc_info.value.reason)
        )

    @patch("acb.console.aprint")
    @patch("asyncio.run")
    def test_write_buffer_skip_when_buffer_index_nonzero(
        self, mock_run: MagicMock, mock_aprint: AsyncMock
    ) -> None:
        rich_console = RichConsole()
        # Add test content to buffer
        rich_console._buffer.append(Segment("test content"))
        rich_console._buffer_index = 1

        rich_console._write_buffer()

        mock_run.assert_not_called()


class TestConsoleInstallation:
    @patch.dict(os.environ, {"DEPLOYED": "false"})
    def test_install_called_when_not_deployed(self) -> None:
        # Re-import to trigger the installation logic
        import sys

        # Remove module from cache first
        if "acb.console" in sys.modules:
            del sys.modules["acb.console"]

        with patch("rich.traceback.install") as mock_install:
            import acb.console

            # Use the import to prevent unused import error
            _ = acb.console

            mock_install.assert_called()

    @patch.dict(os.environ, {"DEPLOYED": "true"})
    def test_install_not_called_when_deployed(self) -> None:
        # Re-import to trigger the installation logic
        import sys

        # Remove module from cache first
        if "acb.console" in sys.modules:
            del sys.modules["acb.console"]

        with patch("rich.traceback.install") as mock_install:
            import acb.console

            # Use the import to prevent unused import error
            _ = acb.console

            mock_install.assert_not_called()


class TestConsoleGlobal:
    def test_console_global(self) -> None:
        assert isinstance(console, Console)
