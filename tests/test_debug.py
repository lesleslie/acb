import asyncio
from pathlib import Path
from time import sleep
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from acb.config import Config
from acb.debug import (
    _colorized_stderr_print_async,
    colorized_stderr_print,
    debug,
    get_calling_module,
    patch_record,
    print_debug_info,
    timeit,
)


@pytest.fixture
def mock_config():
    mock_config = MagicMock(spec=Config)
    mock_config.deployed = False
    mock_config.debug = MagicMock()
    mock_config.debug.production = False
    return mock_config


@pytest.fixture
def mock_logger():
    mock_logger = MagicMock()
    mock_logger.patch.return_value = mock_logger
    mock_logger.debug = MagicMock()
    return mock_logger


@pytest.fixture
def mock_adapter_registry():
    mock_registry = MagicMock()
    mock_registry.get.return_value = [MagicMock(category="logger", name="loguru")]
    return mock_registry


class TestGetCallingModule:
    def test_get_calling_module_success(self, mock_config: MagicMock) -> None:
        mock_frame = MagicMock()
        mock_frame.f_back.f_back.f_back.f_code.co_filename = "/path/to/module/file.py"

        setattr(mock_config.debug, "module", True)

        with (
            patch("acb.debug.config", mock_config),
            patch("acb.debug.logging.currentframe", return_value=mock_frame),
        ):
            result = get_calling_module()

            assert result == Path("/path/to/module")

    def test_get_calling_module_no_debug_config(self, mock_config: MagicMock) -> None:
        mock_frame = MagicMock()
        mock_frame.f_back.f_back.f_back.f_code.co_filename = "/path/to/module/file.py"

        with (
            patch("acb.debug.config", mock_config),
            patch("acb.debug.logging.currentframe", return_value=mock_frame),
            patch("acb.debug.getattr", return_value=None),
        ):
            result = get_calling_module()

            assert result is None

    def test_get_calling_module_exception(self, mock_config: MagicMock) -> None:
        with (
            patch("acb.debug.config", mock_config),
            patch("acb.debug.logging.currentframe", side_effect=AttributeError),
        ):
            result = get_calling_module()

            assert result is None


class TestPatchRecord:
    def test_patch_record_with_loguru(self, mock_logger: MagicMock) -> None:
        mock_mod = MagicMock(spec=Path)
        mock_mod.name = "module"
        msg = "Test debug message"

        patched_logger = MagicMock()
        mock_logger.patch.return_value = patched_logger

        with patch("acb.debug.any", return_value=True) as mock_any:
            patch_record(mock_mod, msg, logger=mock_logger)

            assert mock_logger.patch.call_count == 1
            patched_logger.debug.assert_called_once_with(msg)
            mock_any.assert_called_once()

    def test_patch_record_without_loguru(self, mock_logger: MagicMock) -> None:
        mock_mod = MagicMock(spec=Path)
        mock_mod.name = "module"
        msg = "Test debug message"

        with patch("acb.debug.any", return_value=False) as mock_any:
            patch_record(mock_mod, msg, logger=mock_logger)

            mock_logger.patch.assert_not_called()
            mock_any.assert_called_once()

    def test_patch_record_exception(self, mock_logger: MagicMock) -> None:
        mock_mod = MagicMock(spec=Path)
        mock_mod.name = "module"
        msg = "Test debug message"

        mock_logger.patch.side_effect = Exception("Test exception")

        with patch("acb.debug.any", return_value=True) as mock_any:
            patch_record(mock_mod, msg, logger=mock_logger)

            assert mock_logger.patch.call_count == 1
            mock_any.assert_called_once()


class TestColorizedStderrPrint:
    async def test_colorized_stderr_print_async(self) -> None:
        test_string = "Test colored string"

        with (
            patch("acb.debug.aprint") as mock_aprint,
            patch("acb.debug.colorize") as mock_colorize,
        ):
            mock_colorize.return_value = "colored test string"
            await _colorized_stderr_print_async(test_string)

            mock_colorize.assert_called_once_with(test_string)
            mock_aprint.assert_called_once_with("colored test string", use_stderr=True)

    def test_colorized_stderr_print(self) -> None:
        test_string = "Test colored string"

        async_mock = AsyncMock()

        with (
            patch("acb.debug.supportTerminalColorsInWindows") as mock_support_colors,
            patch(
                "acb.debug._colorized_stderr_print_async", return_value=async_mock()
            ) as mock_print_async,
            patch("acb.debug.asyncio.run") as mock_run,
        ):
            colorized_stderr_print(test_string)

            mock_support_colors.assert_called_once()
            mock_support_colors().__enter__.assert_called()
            mock_support_colors().__exit__.assert_called_once()

            mock_print_async.assert_called_once_with(test_string)

            assert mock_run.call_count == 1
            args, _ = mock_run.call_args
            assert asyncio.iscoroutine(args[0])


class TestPrintDebugInfo:
    def test_print_debug_info_production(self, mock_config: MagicMock) -> None:
        msg = "Test debug message"
        mock_mod = Path("/path/to/module")
        mock_config.deployed = True

        mock_patch_record = Mock()

        with (
            patch("acb.debug.config", mock_config),
            patch("acb.debug.get_calling_module", return_value=mock_mod),
            patch("acb.debug.patch_record", mock_patch_record),
            patch("acb.debug.colorized_stderr_print") as mock_colorized_print,
        ):
            print_debug_info(msg)

            mock_patch_record.assert_called_once_with(mock_mod, msg)
            mock_colorized_print.assert_not_called()

    def test_print_debug_info_development(self, mock_config: MagicMock) -> None:
        msg = "Test debug message"
        mock_mod = Path("/path/to/module")
        mock_config.deployed = False
        mock_config.debug.production = False

        mock_colorized_print = Mock()

        with (
            patch("acb.debug.config", mock_config),
            patch("acb.debug.get_calling_module", return_value=mock_mod),
            patch("acb.debug.patch_record") as mock_patch_record,
            patch("acb.debug.colorized_stderr_print", mock_colorized_print),
        ):
            print_debug_info(msg)

            mock_patch_record.assert_not_called()
            mock_colorized_print.assert_called_once_with(msg)

    def test_print_debug_info_no_module(self, mock_config: MagicMock) -> None:
        msg = "Test debug message"

        mock_patch_record = Mock()
        mock_colorized_print = AsyncMock()

        with (
            patch("acb.debug.config", mock_config),
            patch("acb.debug.get_calling_module", return_value=None),
            patch("acb.debug.patch_record", mock_patch_record),
            patch("acb.debug.colorized_stderr_print", mock_colorized_print),
        ):
            result = print_debug_info(msg)

            mock_patch_record.assert_not_called()
            mock_colorized_print.assert_not_awaited()
            assert result is None


class TestTimeit:
    def test_timeit_decorator(self, mock_logger: MagicMock) -> None:
        def test_function() -> str:
            sleep(0.01)
            return "test result"

        decorated_function = timeit(test_function, logger=mock_logger)

        result = decorated_function()

        assert result == "test result"
        mock_logger.debug.assert_called_once()
        debug_message = mock_logger.debug.call_args[0][0]
        assert "test_function" in debug_message
        assert "executed in" in debug_message
        assert "s" in debug_message

    @pytest.mark.asyncio
    async def test_timeit_with_args_and_kwargs(self, mock_logger: MagicMock) -> None:
        def test_function_with_args(
            arg1: str, arg2: str, kwarg1: object = None, kwarg2: object = None
        ) -> str:
            async def _test_function_with_args() -> str:
                sleep(0.01)
                return f"{arg1}-{arg2}-{kwarg1}-{kwarg2}"

            return asyncio.run(_test_function_with_args())

        decorated_function = timeit(test_function_with_args, logger=mock_logger)

        result = decorated_function("a", "b", kwarg1="c", kwarg2="d")

        assert result == "a-b-c-d"
        mock_logger.debug.assert_called_once()
        debug_message = mock_logger.debug.call_args[0][0]
        assert "test_function_with_args" in debug_message


class TestDebugConfiguration:
    def test_debug_configuration(self, mock_config: MagicMock) -> None:
        mock_config.deployed = False
        mock_config.debug.production = False

        mock_configure = MagicMock()

        with (
            patch("acb.debug.config", mock_config),
            patch("acb.debug.debug.configureOutput", mock_configure),
        ):
            from acb.debug import debug_args

            debug.configureOutput(
                prefix="    debug:  ",
                includeContext=True,
                **debug_args,
            )

            assert mock_configure.call_count >= 1

            mock_config.deployed = True

            if mock_config.deployed or mock_config.debug.production:
                debug.configureOutput(
                    prefix="",
                    includeContext=False,
                    **debug_args,
                )

            assert mock_configure.call_count >= 2
