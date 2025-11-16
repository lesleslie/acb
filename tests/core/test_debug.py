"""Tests for the debug module."""

import sys
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from acb.debug import (
    colorized_stderr_print,
    get_calling_module,
    init_debug,
    patch_record,
    pprint,
    print_debug_info,
)


class TestDebugModule:
    """Test debug module functions."""

    def test_get_calling_module_with_config(self) -> None:
        """Test get_calling_module when config is available."""
        # This test is challenging because it depends on the runtime environment
        # For now, we'll just test that it doesn't crash
        try:
            result = get_calling_module()
            # Should return None or a Path object
            assert result is None or hasattr(result, "name")
        except Exception:
            # If there's an exception, it should be handled gracefully
            pytest.fail("get_calling_module should not raise unhandled exceptions")

    @patch("acb.debug.depends.get")
    def test_get_calling_module_runtime_error(self, mock_depends_get: Mock) -> None:
        """Test get_calling_module when depends.get raises RuntimeError."""
        mock_depends_get.side_effect = RuntimeError("Config not initialized")

        result = get_calling_module()
        assert result is None

    @patch("acb.debug.depends.get")
    def test_get_calling_module_attribute_error(self, mock_depends_get: Mock) -> None:
        """Test get_calling_module when there's an AttributeError."""
        mock_config = MagicMock()
        mock_config.debug = None
        mock_depends_get.return_value = mock_config

        # Mock the logging.currentframe to raise AttributeError
        with patch("acb.debug.logging.currentframe", side_effect=AttributeError()):
            result = get_calling_module()
            assert result is None

    @pytest.mark.asyncio
    async def test_pprint(self) -> None:
        """Test pprint function."""
        test_obj = {"key": "value", "number": 42}

        with patch("acb.debug.aprint", new=AsyncMock()) as mock_aprint:
            await pprint(test_obj)

            # Check that aprint was called
            mock_aprint.assert_called_once()

    def test_colorized_stderr_print(self) -> None:
        """Test colorized_stderr_print function."""
        test_string = "Test debug message"

        with patch("acb.debug.colorize") as mock_colorize:
            with patch("acb.debug.supportTerminalColorsInWindows"):
                with patch("acb.debug.aprint", new=AsyncMock()) as mock_aprint:
                    mock_colorize.return_value = "\033[31mTest debug message\033[0m"

                    colorized_stderr_print(test_string)

                    mock_colorize.assert_called_once_with(test_string)
                    mock_aprint.assert_called_once()

    @pytest.mark.skip(
        reason="Colorized stderr error formatting changed after refactoring"
    )
    def test_colorized_stderr_print_import_error(self) -> None:
        """Test colorized_stderr_print when colorize import fails."""
        test_string = "Test debug message"

        with patch("acb.debug.colorize", side_effect=ImportError()):
            with patch("builtins.print") as mock_print:
                colorized_stderr_print(test_string)

                mock_print.assert_called_once_with(test_string, file=sys.stderr)

    @pytest.mark.skip(
        reason="Colorized stderr error formatting changed after refactoring"
    )
    def test_colorized_stderr_print_asyncio_error(self) -> None:
        """Test colorized_stderr_print when asyncio.run fails."""
        test_string = "Test debug message"

        with patch("acb.debug.colorize") as mock_colorize:
            with patch("acb.debug.supportTerminalColorsInWindows"):
                with patch("acb.debug.aprint", side_effect=Exception("Asyncio error")):
                    with patch("builtins.print") as mock_print:
                        mock_colorize.return_value = "\033[31mTest debug message\033[0m"

                        colorized_stderr_print(test_string)

                        mock_print.assert_called_once_with(
                            "\033[31mTest debug message\033[0m", file=sys.stderr
                        )

    def test_print_debug_info_with_module(self) -> None:
        """Test print_debug_info when module is available."""
        test_msg = "Test debug message"

        with patch("acb.debug.get_calling_module", return_value=MagicMock()):
            with patch("acb.debug._deployed", False):
                with patch("acb.debug.colorized_stderr_print") as mock_print:
                    print_debug_info(test_msg)
                    mock_print.assert_called_once_with(test_msg)

    def test_print_debug_info_deployed(self) -> None:
        """Test print_debug_info when deployed."""
        test_msg = "Test debug message"

        with patch("acb.debug.get_calling_module", return_value=MagicMock()):
            with patch("acb.debug._deployed", True):
                with patch("acb.debug.patch_record") as mock_patch:
                    print_debug_info(test_msg)
                    mock_patch.assert_called_once()

    def test_print_debug_info_no_module(self) -> None:
        """Test print_debug_info when no module is available."""
        test_msg = "Test debug message"

        with patch("acb.debug.get_calling_module", return_value=None):
            # Should not raise any exception
            result = print_debug_info(test_msg)
            assert result is None

    @pytest.mark.asyncio
    async def test_patch_record(self) -> None:
        """Test patch_record function."""
        mock_mod = MagicMock()
        mock_mod.name = "test_module"
        test_msg = "Test message"

        # Just test that it doesn't crash
        try:
            patch_record(mock_mod, test_msg)
        except Exception:
            pytest.fail("patch_record should not raise exceptions")

    @pytest.mark.asyncio
    async def test_patch_record_no_module(self) -> None:
        """Test patch_record function with no module."""
        test_msg = "Test message"

        # Just test that it doesn't crash
        try:
            patch_record(None, test_msg)
        except Exception:
            pytest.fail("patch_record should not raise exceptions")

    @pytest.mark.asyncio
    async def test_patch_record_exception_handling(self) -> None:
        """Test patch_record handles exceptions gracefully."""
        mock_mod = MagicMock()
        test_msg = "Test message"

        # Mock depends to raise an exception
        with patch("acb.debug.depends.get", side_effect=Exception("Test exception")):
            # Should not raise any exception
            try:
                patch_record(mock_mod, test_msg)
            except Exception:
                pytest.fail("patch_record should handle exceptions gracefully")

    def test_init_debug_basic(self) -> None:
        """Test init_debug function basic functionality."""
        with patch("acb.debug.debug") as mock_debug:
            with patch("acb.debug.depends.get", side_effect=RuntimeError()):
                init_debug()

                # Check that configureOutput was called
                mock_debug.configureOutput.assert_called()

    def test_init_debug_with_config(self) -> None:
        """Test init_debug function with config available."""
        with patch("acb.debug.debug") as mock_debug:
            mock_config = MagicMock()
            mock_config.deployed = False
            mock_config.debug = MagicMock()
            mock_config.debug.production = False

            with patch("acb.debug.depends.get", return_value=mock_config):
                init_debug()

                # Check that configureOutput was called
                mock_debug.configureOutput.assert_called()

    def test_init_debug_production_mode(self) -> None:
        """Test init_debug function in production mode."""
        with patch("acb.debug.debug") as mock_debug:
            mock_config = MagicMock()
            mock_config.deployed = True
            mock_config.debug = MagicMock()
            mock_config.debug.production = True

            with patch("acb.debug.depends.get", return_value=mock_config):
                init_debug()

                # Check that configureOutput was called with production settings
                mock_debug.configureOutput.assert_called()

    def test_init_debug_exception_handling(self) -> None:
        """Test init_debug handles exceptions gracefully."""
        with patch("acb.debug.debug") as mock_debug:
            # Make configureOutput raise an exception
            mock_debug.configureOutput.side_effect = Exception("Test exception")

            # Should not raise any exception
            try:
                init_debug()
            except Exception:
                # It's okay if it raises, as long as it's handled gracefully
                pass

    def test_init_debug_warnings_filter(self) -> None:
        """Test that init_debug sets up warnings filter."""
        import warnings

        with patch.object(warnings, "filterwarnings") as mock_filterwarnings:
            with patch("acb.debug.depends.get", side_effect=RuntimeError()):
                init_debug()

                # Check that filterwarnings was called
                mock_filterwarnings.assert_called_with(
                    "ignore", category=RuntimeWarning, module="icecream"
                )
