"""Simple tests for the config module."""

import tempfile
from pathlib import Path

import pytest
from acb.config import Settings


@pytest.mark.unit
class TestConfig:
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def config_files(self, temp_dir: Path):
        app_yml = temp_dir / "app.yml"
        app_yml.write_text("")

        adapters_yml = temp_dir / "adapters.yml"
        adapters_yml.write_text("")

        debug_yml = temp_dir / "debug.yml"
        debug_yml.write_text("")

        yield {
            "app": app_yml,
            "adapters": adapters_yml,
            "debug": debug_yml,
            "dir": temp_dir,
        }

    @pytest.mark.asyncio
    async def test_settings_class(self) -> None:
        class TestSettings(Settings):
            name: str = "test_name"
            value: int = 123

        settings = TestSettings()

        assert settings.name == "test_name"
        assert settings.value == 123

        custom_settings = TestSettings(name="custom_name", value=456)

        assert custom_settings.name == "custom_name"
        assert custom_settings.value == 456

    @pytest.mark.asyncio
    async def test_app_settings(self) -> None:
        from acb.config import AppSettings

        app_settings = AppSettings()

        assert hasattr(app_settings, "name")
        assert hasattr(app_settings, "title")
        assert hasattr(app_settings, "version")

    @pytest.mark.asyncio
    async def test_debug_settings(self) -> None:
        from acb.config import DebugSettings

        debug_settings = DebugSettings()

        assert hasattr(debug_settings, "production")
        assert hasattr(debug_settings, "secrets")
        assert hasattr(debug_settings, "logger")
