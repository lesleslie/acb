import typing as t
from unittest.mock import MagicMock, Mock, patch

import pytest
from rich.console import Console
from acb.console import RichConsole


@pytest.fixture
def testable_rich_console():
    class TestableRichConsole(Console):
        def __init__(
            self,
            test_buffer: t.Any,
            buffer_index: int,
            record_mode: bool,
        ) -> None:
            super().__init__()
            self.test_buffer = test_buffer
            self.test_buffer_index = buffer_index
            self.record = record_mode
            self.test_record_buffer = []
            self._lock = MagicMock()
            self._record_buffer_lock = MagicMock()
            self._lock.__enter__ = MagicMock(return_value=None)
            self._lock.__exit__ = MagicMock(return_value=None)
            self._record_buffer_lock.__enter__ = MagicMock(return_value=None)
            self._record_buffer_lock.__exit__ = MagicMock(return_value=None)
            self.file = MagicMock()
            self.file.flush = MagicMock()

        def _render_buffer(self, buffer: t.Any) -> str:
            return "rendered content"

        def _write_buffer(self) -> None:
            with self._lock:
                if self.record and not self.test_buffer_index:
                    with self._record_buffer_lock:
                        self.test_record_buffer.extend(self.test_buffer[:])

                if self.test_buffer_index == 0:
                    text = self._render_buffer(self.test_buffer[:])
                    try:
                        print(text)
                    except UnicodeEncodeError as error:
                        error.reason = (
                            f"{error.reason}\n*** You may need to add"
                            f" PYTHONIOENCODING=utf-8 to your environment ***"
                        )
                        raise
                    self.file.flush()
                    del self.test_buffer[:]

    return TestableRichConsole


class TestRichConsole:
    def test_init_with_deployed_config(self) -> None:
        mock_config = Mock()
        mock_config.deployed = True

        with patch("acb.console.depends") as mock_depends:
            mock_depends.return_value = mock_config
            with patch("acb.console.install") as mock_install:
                with patch.object(
                    RichConsole, "__init__", return_value=None
                ) as mock_init:
                    rich_console = RichConsole()

                    mock_init.side_effect = None
                    RichConsole.__init__(rich_console)

                mock_install.assert_not_called()
                assert isinstance(rich_console, Console)

    def test_init_with_non_deployed_config(self) -> None:
        mock_config = Mock()
        mock_config.deployed = False

        with patch("acb.console.depends") as mock_depends:
            mock_depends.return_value = mock_config
            with patch("acb.console.install") as mock_install:
                rich_console = RichConsole()

                mock_install.assert_called_once_with(console=rich_console)
                assert isinstance(rich_console, Console)

    def test_init_with_string_config(self) -> None:
        mock_config = "string_config"

        with patch("acb.console.depends") as mock_depends:
            mock_depends.return_value = mock_config
            with patch("acb.console.install") as mock_install:
                with patch.object(
                    RichConsole, "__init__", return_value=None
                ) as mock_init:
                    rich_console = RichConsole()

                    mock_init.side_effect = None
                    RichConsole.__init__(rich_console)

                mock_install.assert_not_called()
                assert isinstance(rich_console, Console)

    def test_write_buffer_functionality(self, testable_rich_console: t.Any) -> None:
        test_buffer = ["test buffer content"]

        with patch("acb.console.depends") as mock_depends:
            mock_config = Mock()
            mock_depends.return_value = mock_config

            console = testable_rich_console(test_buffer.copy(), 0, False)

            with patch("builtins.print") as mock_print:
                console._write_buffer()

                mock_print.assert_called_once_with("rendered content")

    def test_write_buffer_with_record(self, testable_rich_console: t.Any) -> None:
        test_buffer = ["test buffer content"]

        with patch("acb.console.depends") as mock_depends:
            mock_config = Mock()
            mock_depends.return_value = mock_config

            console = testable_rich_console(test_buffer.copy(), 0, True)

            with patch("builtins.print") as mock_print:
                console._write_buffer()

                mock_print.assert_called_once_with("rendered content")
                assert console.test_record_buffer

    def test_write_buffer_with_unicode_error(
        self, testable_rich_console: t.Any
    ) -> None:
        test_buffer = ["test buffer content"]

        with patch("acb.console.depends") as mock_depends:
            mock_config = Mock()
            mock_depends.return_value = mock_config

            console = testable_rich_console(test_buffer.copy(), 0, False)

            unicode_error = UnicodeEncodeError("utf-8", "test", 0, 1, "test error")
            mock_print = Mock(side_effect=unicode_error)

            with (
                patch("builtins.print", mock_print),
                pytest.raises(UnicodeEncodeError) as exc_info,
            ):
                console._write_buffer()

            mock_print.assert_called_once_with("rendered content")
            assert "PYTHONIOENCODING=utf-8" in exc_info.value.reason
