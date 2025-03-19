import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

os.environ["ACB_TESTING"] = "1"

from tests.conftest_common import (
    mock_adapter_registry,
    mock_colorized_stderr_print,
    mock_get_calling_module,
    mock_patch_record,
    mock_print_debug_info,
    mock_timeit,
)

mock_adapter_registry_patch = patch("acb.debug.adapter_registry", mock_adapter_registry)
mock_adapter_registry_patch.start()

colorized_stderr_print_patch = patch(
    "acb.debug.colorized_stderr_print", mock_colorized_stderr_print
)
colorized_stderr_print_patch.start()

get_calling_module_patch = patch(
    "acb.debug.get_calling_module", mock_get_calling_module
)
get_calling_module_patch.start()

patch_record_patch = patch("acb.debug.patch_record", mock_patch_record)
patch_record_patch.start()

print_debug_info_patch = patch("acb.debug.print_debug_info", mock_print_debug_info)
print_debug_info_patch.start()

timeit_patch = patch("acb.debug.timeit", mock_timeit)
timeit_patch.start()


def mock_aprint(*args: Any, **kwargs: Any) -> None:
    return None


def mock_asyncio_run(coro: Any) -> None:
    return None


mock_asyncio = MagicMock()
mock_asyncio.run = mock_asyncio_run
sys.modules["asyncio"] = mock_asyncio

sys.modules["aioconsole"] = MagicMock()
sys.modules["aioconsole"].aprint = mock_aprint

from tests.conftest import mock_logger_adapter  # noqa: E402

mock_import_adapter = patch("acb.adapters.import_adapter")
mock_import_adapter.start().return_value = mock_logger_adapter

mock_ic_config = patch("icecream.ic.configureOutput")
mock_ic_config.start()

import acb.config as config  # noqa: E402

if not hasattr(config, "adapter_registry"):
    setattr(config, "adapter_registry", mock_adapter_registry)

from acb.debug import (  # noqa: E402
    colorized_stderr_print,
    get_calling_module,
    patch_record,
)

pytestmark = pytest.mark.asyncio


def teardown_module() -> None:
    mock_import_adapter.stop()
    mock_ic_config.stop()
    mock_adapter_registry_patch.stop()
    colorized_stderr_print_patch.stop()
    get_calling_module_patch.stop()
    patch_record_patch.stop()
    print_debug_info_patch.stop()
    timeit_patch.stop()


class TestGetCallingModule:
    """Test the get_calling_module function."""

    async def test_get_calling_module_debug_enabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test getting the calling module when debugging is enabled."""
        mock_code = MagicMock()
        mock_code.co_filename = "/path/to/module/file.py"

        mock_frame = MagicMock()
        mock_frame.f_back.f_back.f_back.f_code = mock_code

        mock_config = MagicMock()
        mock_config.debug = MagicMock()
        setattr(mock_config.debug, "module", True)

        with patch("logging.currentframe", return_value=mock_frame):
            with patch("acb.debug.config", mock_config):
                result = get_calling_module()

                assert result is not None
                assert isinstance(result, Path)
                assert result.stem == "module"

    async def test_get_calling_module_debug_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test getting the calling module when debugging is disabled."""
        mock_code = MagicMock()
        mock_code.co_filename = "/path/to/module/file.py"

        mock_frame = MagicMock()
        mock_frame.f_back.f_back.f_back.f_code = mock_code

        mock_config = MagicMock()
        mock_config.debug = MagicMock()
        setattr(mock_config.debug, "module", False)

        with patch("logging.currentframe", return_value=mock_frame):
            with patch("acb.debug.config", mock_config):
                result = get_calling_module()

                assert result is None


class TestPatchRecord:
    """Test the patch_record function."""

    async def test_patch_record_with_loguru(self) -> None:
        """Test patching a record when loguru adapter is available."""
        mock_mod = MagicMock(spec=Path)
        mock_mod.name = "test_module"

        mock_logger = MagicMock()
        mock_patched_logger = MagicMock()
        mock_logger.patch.return_value = mock_patched_logger

        mock_adapter = MagicMock()
        mock_adapter.category = "logger"
        mock_adapter.name = "loguru"

        mock_adapter_registry.set([mock_adapter])

        patch_record(mock_mod, "Test message", logger=mock_logger)

        mock_logger.patch.assert_called_once()
        mock_patched_logger.debug.assert_called_once_with("Test message")

    async def test_patch_record_without_loguru(self) -> None:
        """Test patching a record when loguru adapter is not available."""
        mock_mod = MagicMock(spec=Path)
        mock_mod.name = "test_module"

        mock_logger = MagicMock()

        mock_adapter = MagicMock()
        mock_adapter.category = "logger"
        mock_adapter.name = "structlog"

        mock_adapter_registry.set([mock_adapter])

        patch_record(mock_mod, "Test message", logger=mock_logger)

        mock_logger.patch.assert_not_called()


class TestColorizedStderrPrint:
    """Test the colorized_stderr_print function."""

    async def test_colorized_stderr_print(self) -> None:
        """Test printing colorized output to stderr."""
        with patch(
            "acb.debug.colorize", return_value="<colorized>test</colorized>"
        ) as mock_colorize:
            with patch("acb.debug.supportTerminalColorsInWindows") as mock_support:
                with patch("sys.stderr") as mock_stderr:
                    colorized_stderr_print("test")

                    mock_colorize.assert_called_once_with("test")
                    mock_support.assert_called_once()
                    mock_stderr.write.assert_called_once_with("<colorized>test\n")
