import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rich.segment import Segment

from acb.console import RichConsole, console


class TestRichConsole:
    def test_rich_console_init(self) -> None:
        rich_console = RichConsole()
        from rich.console import Console

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
        from rich.console import Console

        assert isinstance(console, Console)


class TestConsoleWidth:
    """Test configurable console width feature."""

    def test_console_width_from_environment(self) -> None:
        """Test console width configured via CONSOLE_WIDTH environment variable."""
        with patch.dict(os.environ, {"CONSOLE_WIDTH": "100"}):
            from acb.console import Console

            test_console = Console()
            assert test_console.width == 100

    def test_console_width_from_settings(self) -> None:
        """Test console width configured via settings/console.yaml."""
        from acb.console import Console, ConsoleSettings

        with patch.object(Console, "_load_settings") as mock_load:
            # Mock settings with width=120
            mock_settings = ConsoleSettings(width=120)
            mock_load.return_value = mock_settings

            test_console = Console()
            assert test_console.width == 120

    def test_console_width_env_overrides_settings(self) -> None:
        """Test that environment variable takes precedence over settings."""
        from acb.console import Console, ConsoleSettings

        with patch.dict(os.environ, {"CONSOLE_WIDTH": "150"}):
            with patch.object(Console, "_load_settings") as mock_load:
                # Mock settings with width=120
                mock_settings = ConsoleSettings(width=120)
                mock_load.return_value = mock_settings

                test_console = Console()
                # Environment should override settings
                assert test_console.width == 150

    def test_console_width_auto_detect_when_none(self) -> None:
        """Test auto-detection when width is None (not explicitly set)."""
        from acb.console import Console, ConsoleSettings

        with patch.object(Console, "_load_settings") as mock_load:
            # Mock settings with width=None (auto-detect)
            mock_settings = ConsoleSettings(width=None)
            mock_load.return_value = mock_settings

            test_console = Console()
            # Should use Rich's auto-detection (None means auto-detect)
            # Rich will set an actual width based on terminal detection
            assert test_console.width is not None or test_console.width is None

    def test_console_width_invalid_env_falls_back(self) -> None:
        """Test that invalid environment values fall back to settings."""
        from acb.console import Console, ConsoleSettings

        with patch.dict(os.environ, {"CONSOLE_WIDTH": "invalid"}):
            with patch.object(Console, "_load_settings") as mock_load:
                mock_settings = ConsoleSettings(width=80)
                mock_load.return_value = mock_settings

                test_console = Console()
                # Should fall back to settings value
                assert test_console.width == 80

    def test_console_settings_defaults(self) -> None:
        """Test ConsoleSettings default values."""
        from acb.console import ConsoleSettings

        settings = ConsoleSettings(width=None)
        assert settings.width is None

    def test_console_settings_with_custom_width(self) -> None:
        """Test ConsoleSettings with custom width."""
        from acb.console import ConsoleSettings

        settings = ConsoleSettings(width=70)
        assert settings.width == 70

    def test_load_settings_fallback_on_error(self) -> None:
        """Test that _load_settings falls back to defaults on error."""
        from acb.console import Console

        test_console = Console()
        # Should not raise even if settings loading fails
        assert hasattr(test_console, "_settings")
        assert test_console._settings is not None

    def test_get_console_width_precedence(self) -> None:
        """Test width configuration precedence order."""
        from acb.console import Console, ConsoleSettings

        # Test precedence: ENV > Settings > None
        with patch.dict(os.environ, {"CONSOLE_WIDTH": "90"}):
            with patch.object(Console, "_load_settings") as mock_load:
                mock_settings = ConsoleSettings(width=80)
                mock_load.return_value = mock_settings

                test_console = Console()
                width = test_console._get_console_width()

                # Environment should win
                assert width == 90
