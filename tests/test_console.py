import typing as t
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console
from acb.config import Config
from acb.console import console


class TestGetConsole:
    @pytest.fixture
    def mock_config(self) -> t.Generator[MagicMock]:
        mock_config: MagicMock = MagicMock(spec=Config)
        mock_config.debug = MagicMock()

        with patch(
            "acb.console.depends.inject",
            lambda f: lambda *args, **kwargs: f(*args, config=mock_config, **kwargs),
        ):
            yield mock_config


class TestGetConsoleManager:
    @pytest.fixture
    def mock_config(self) -> t.Generator[MagicMock]:
        mock_config: MagicMock = MagicMock(spec=Config)
        mock_config.debug = MagicMock()

        with patch(
            "acb.console.depends.inject",
            lambda f: lambda *args, **kwargs: f(*args, config=mock_config, **kwargs),
        ):
            yield mock_config


class TestInitConsole:
    @pytest.fixture
    def mock_config(self) -> t.Generator[MagicMock]:
        mock_config: MagicMock = MagicMock(spec=Config)
        mock_config.debug = MagicMock()

        with patch(
            "acb.console.depends.inject",
            lambda f: lambda *args, **kwargs: f(*args, config=mock_config, **kwargs),
        ):
            yield mock_config


class TestConsoleGlobal:
    def test_console_global(self) -> None:
        assert isinstance(console, Console)
