import typing as t
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from acb.config import Config
from acb.debug import (
    colorized_stderr_print,
    debug,
    get_calling_module,
    init_debug,
    pprint,
    print_debug_info,
)
from acb.logger import Logger


class TestGetCallingModule:
    @pytest.fixture
    def mock_config(self) -> t.Generator[MagicMock, None, None]:
        mock_config: MagicMock = MagicMock(spec=Config)
        mock_config.debug = MagicMock()

        patcher = patch("acb.debug.depends.inject")
        mock_inject = patcher.start()

        def inject_mock_config(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
            def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                return func(*args, **kwargs, config=mock_config)

            return wrapper

        mock_inject.side_effect = inject_mock_config

        yield mock_config

        patcher.stop()

    def test_get_calling_module_with_debug_disabled(
        self, mock_config: MagicMock
    ) -> None:
        mock_frame: MagicMock = MagicMock()
        mock_frame.f_back.f_back.f_back.f_code.co_filename = "/test/path/test_module.py"

        with patch("acb.debug.logging.currentframe", return_value=mock_frame):
            type(mock_config.debug).test_module = False

            result: t.Any = get_calling_module()

            assert result is None

    def test_get_calling_module_with_exception(self, mock_config: MagicMock) -> None:
        with patch("acb.debug.logging.currentframe", side_effect=AttributeError):
            result: t.Any = get_calling_module()

            assert result is None


class TestPatchRecord:
    @pytest.fixture
    def mock_logger(self) -> t.Generator[MagicMock, None, None]:
        mock_logger: MagicMock = MagicMock(spec=Logger)

        mock_patched_logger: MagicMock = MagicMock()
        mock_logger.patch.return_value = mock_patched_logger

        patcher = patch("acb.debug.depends.inject")
        mock_inject = patcher.start()

        def inject_mock_logger(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
            def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                return func(*args, **kwargs, logger=mock_logger)

            return wrapper

        mock_inject.side_effect = inject_mock_logger

        yield mock_logger

        patcher.stop()


class TestColorizedStderrPrint:
    def test_colorized_stderr_print_with_asyncio(self) -> None:
        with patch("acb.debug.colorize") as mock_colorize:
            mock_colorize.return_value = "Colored test message"

            with patch("acb.debug.supportTerminalColorsInWindows") as mock_support:
                mock_support.return_value.__enter__ = MagicMock()
                mock_support.return_value.__exit__ = MagicMock()

                mock_coro: AsyncMock = AsyncMock()
                with patch("acb.debug.aprint", return_value=mock_coro) as mock_aprint:

                    def mock_run_impl(coro: t.Any) -> None:
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


class TestPrintDebugInfo:
    def test_print_debug_info_with_module_not_deployed(self) -> None:
        mock_module: MagicMock = MagicMock(spec=Path)
        with patch("acb.debug.get_calling_module", return_value=mock_module):
            with patch("acb.debug._deployed", False):
                with patch("acb.debug.colorized_stderr_print") as mock_print:
                    result: t.Any = print_debug_info("Test message")

                    mock_print.assert_called_once_with("Test message")

                    assert result is None

    def test_print_debug_info_with_module_deployed(self) -> None:
        mock_module: MagicMock = MagicMock(spec=Path)
        with patch("acb.debug.get_calling_module", return_value=mock_module):
            with patch("acb.debug._deployed", True):
                with patch("acb.debug.patch_record") as mock_patch:
                    result: t.Any = print_debug_info("Test message")

                    mock_patch.assert_called_once_with(mock_module, "Test message")

                    assert result is None

    def test_print_debug_info_without_module(self) -> None:
        with patch("acb.debug.get_calling_module", return_value=None):
            result: t.Any = print_debug_info("Test message")

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


class TestInitDebug:
    @pytest.fixture
    def mock_config(self) -> t.Generator[MagicMock, None, None]:
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
