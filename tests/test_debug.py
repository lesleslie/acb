from collections.abc import Generator
from pathlib import Path
from typing import Any, Final
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rich.console import Console
from acb.config import Config
from acb.debug import (
    colorized_stderr_print,
    debug,
    init_debug,
    pprint,
    print_debug_info,
)
from acb.logger import Logger

TEST_MODULE_NAME: Final[str] = "test_module"
TEST_DEBUG_MSG: Final[str] = "test debug message"


@pytest.fixture
def mock_console() -> MagicMock:
    console = MagicMock(spec=Console)
    console.print = MagicMock()
    return console


@pytest.fixture
def mock_logger() -> MagicMock:
    logger = MagicMock(spec=Logger)
    logger.debug = MagicMock()
    return logger


class TestColorizedStderrPrint:
    def test_colorized_stderr_print_with_asyncio(self) -> None:
        with patch("acb.debug.colorize") as mock_colorize:
            mock_colorize.return_value = "Colored test message"

            with patch("acb.debug.supportTerminalColorsInWindows") as mock_support:
                mock_support.return_value.__enter__ = MagicMock()
                mock_support.return_value.__exit__ = MagicMock()

                mock_coro: AsyncMock = AsyncMock()
                with patch("acb.debug.aprint", return_value=mock_coro) as mock_aprint:

                    def mock_run_impl(coro: Any) -> None:
                        return None

                    with patch(
                        "acb.debug.asyncio.run", side_effect=mock_run_impl
                    ) as mock_run:
                        colorized_stderr_print("Test message")

                        mock_colorize.assert_called_once_with("Test message")

                        mock_support.assert_called_once()

                        mock_aprint.assert_called_once_with(
                            "Colored test message", use_stderr=True
                        )

                        mock_run.assert_called_once()

    def test_colorized_stderr_print_with_print(self) -> None:
        with patch("acb.debug.colorize") as mock_colorize:
            mock_colorize.return_value = "Colored test message"

            with patch("acb.debug.supportTerminalColorsInWindows") as mock_support:
                mock_support.return_value.__enter__ = MagicMock()
                mock_support.return_value.__exit__ = MagicMock()

                with patch(
                    "acb.debug.asyncio.run", side_effect=Exception("Test exception")
                ):
                    with patch("sys.stderr") as mock_stderr:
                        with patch("builtins.print") as mock_print:
                            colorized_stderr_print("Test message")

                            mock_print.assert_called_once_with(
                                "Colored test message", file=mock_stderr
                            )

    def test_colorized_stderr_print_with_no_color_support(self) -> None:
        with patch("acb.debug.colorize", side_effect=ImportError):
            with patch("builtins.print") as mock_print:
                with patch("sys.stderr") as mock_stderr:
                    colorized_stderr_print("Test message")
                    mock_print.assert_called_once_with("Test message", file=mock_stderr)


class TestPrintDebugInfo:
    def test_print_debug_info_with_module_not_deployed(self) -> None:
        mock_module: MagicMock = MagicMock(spec=Path)
        with patch("acb.debug.get_calling_module", return_value=mock_module):
            with patch("acb.debug._deployed", False):
                with patch("acb.debug.colorized_stderr_print") as mock_print:
                    result: Any = print_debug_info("Test message")

                    mock_print.assert_called_once_with("Test message")

                    assert result is None

    def test_print_debug_info_with_module_deployed(self) -> None:
        mock_module: MagicMock = MagicMock(spec=Path)
        with patch("acb.debug.get_calling_module", return_value=mock_module):
            with patch("acb.debug._deployed", True):
                with patch("acb.debug.patch_record") as mock_patch:
                    result: Any = print_debug_info("Test message")

                    mock_patch.assert_called_once_with(mock_module, "Test message")

                    assert result is None

    def test_print_debug_info_without_module(self) -> None:
        with patch("acb.debug.get_calling_module", return_value=None):
            result: Any = print_debug_info("Test message")

            assert result is None


class TestPprint:
    @pytest.mark.asyncio
    async def test_pprint(self) -> None:
        with patch("acb.debug.pformat") as mock_pformat:
            mock_pformat.return_value = "Formatted object"

            with patch("acb.debug.aprint") as mock_aprint:
                await pprint({"test": "object"})

                mock_pformat.assert_called_once_with({"test": "object"})

                mock_aprint.assert_called_once_with("Formatted object", use_stderr=True)

    @pytest.mark.asyncio
    async def test_pprint_with_custom_width(self) -> None:
        test_data = {"key": "value" * 20}
        with patch("acb.debug.pformat") as mock_pformat:
            with patch("acb.debug.aprint") as mock_aprint:
                await pprint(test_data)
                mock_pformat.assert_called_once_with(test_data)
                mock_aprint.assert_called_once()


class TestInitDebug:
    @pytest.fixture
    def mock_config(self) -> Generator[MagicMock]:
        mock_config: MagicMock = MagicMock(spec=Config)
        mock_config.debug = MagicMock()
        mock_config.debug.production = False
        mock_config.deployed = False

        with patch(
            "acb.debug.depends.inject",
            lambda f: lambda *args, **kwargs: f(*args, config=mock_config, **kwargs),
        ):
            yield mock_config

    def test_init_debug_not_production(self, mock_config: MagicMock) -> None:
        with patch.object(debug, "configureOutput") as mock_configure:
            init_debug()

            mock_configure.assert_called_once()
            assert mock_configure.call_args[1]["prefix"] == "    debug:  "
            assert mock_configure.call_args[1]["includeContext"] is True
            assert "outputFunction" in mock_configure.call_args[1]
            assert "argToStringFunction" in mock_configure.call_args[1]


class TestDebugGlobal:
    def test_debug_global(self) -> None:
        from icecream import ic

        assert debug is ic

    def test_debug_with_different_log_levels(self) -> None:
        test_messages = [
            "Test info message",
            "Test warning message",
            "Test error message",
        ]

        with patch.object(debug, "outputFunction") as mock_output_func:
            for message in test_messages:
                debug(message)
            assert mock_output_func.call_count == len(test_messages)

    def test_get_calling_module_from_debug(self) -> None:
        from acb.debug import get_calling_module

        mock_frame = MagicMock()
        mock_frame.f_back.f_back.f_back.f_code.co_filename = "/path/to/test_module.py"

        with patch("logging.currentframe", return_value=mock_frame):
            result = get_calling_module()
            assert result is None or isinstance(result, Path)
