import os
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

os.environ["ACB_TESTING"] = "1"

from tests.conftest_common import (
    MockAppSettings,
    MockConfig,
    MockLogger,
    mock_adapter_registry,
)

adapter_registry_patch = patch("acb.config.adapter_registry", mock_adapter_registry)
adapter_registry_patch.start()

mock_import_adapter = patch("acb.adapters.import_adapter")
mock_import_adapter_obj = mock_import_adapter.start()
mock_import_adapter_obj.return_value = MockLogger

app_settings_patch = patch("acb.config.AppSettings", MockAppSettings)
app_settings_patch.start()

config_patch = patch("acb.config.Config", MockConfig)
config_patch.start()

import acb.config as config  # noqa: E402
from acb.config import (  # noqa: E402
    AppSettings,
    Config,
    gen_password,
    get_version,
    get_version_default,
)

if not hasattr(config, "adapter_registry"):
    setattr(config, "adapter_registry", mock_adapter_registry)

pytestmark = pytest.mark.asyncio


def teardown_module() -> None:
    """Clean up all patches at the end of the module."""
    mock_import_adapter.stop()
    adapter_registry_patch.stop()
    app_settings_patch.stop()
    config_patch.stop()


class TestPasswordGeneration:
    """Test the password generation function."""

    async def test_gen_password_default_size(self) -> None:
        """Test generating a password with the default size."""
        password = gen_password()
        assert password

    async def test_gen_password_custom_size(self) -> None:
        """Test generating a password with a custom size."""
        size = 20
        password = gen_password(size)
        assert len(password) > size


class TestAppNameValidation:
    """Test the app name validation function."""

    async def test_valid_app_names(self) -> None:
        """Test validation of valid app names."""
        valid_names = ["myapp", "my-app", "app123"]
        for name in valid_names:
            result = AppSettings.cloud_compliant_app_name(name)
            assert result == name

    async def test_app_name_with_spaces(self) -> None:
        """Test validation of app name with spaces."""
        name = "My App"
        result = AppSettings.cloud_compliant_app_name(name)
        assert result == "my-app"

    async def test_app_name_with_special_chars(self) -> None:
        """Test validation of app name with special characters."""
        name = "my_app.test!"
        result = AppSettings.cloud_compliant_app_name(name)
        assert result == "my-app-test"

    async def test_app_name_too_short(self) -> None:
        """Test validation of app name that is too short."""
        with pytest.raises(SystemExit, match="App name to short"):
            AppSettings.cloud_compliant_app_name("ab")

    async def test_app_name_too_long(self) -> None:
        """Test validation of app name that is too long."""
        long_name = "a" * 64
        with pytest.raises(SystemExit, match="App name to long"):
            AppSettings.cloud_compliant_app_name(long_name)


class TestAppSettings:
    """Test the AppSettings class."""

    @patch("acb.config._testing", True)
    @patch("acb.config.get_version_default", return_value="0.0.0-test")
    async def test_app_settings_init(self, mock_get_version: MagicMock) -> None:
        """Test initializing AppSettings."""
        with patch("acb.config.Settings._settings_build_values", return_value={}):
            settings = AppSettings()
            settings.name = "myapp"
            settings.timezone = "US/Pacific"
            settings.secret_key = SecretStr("test-key")
            settings.secure_salt = SecretStr("test-salt")

            assert settings.name == "myapp"
            assert isinstance(settings.secret_key, SecretStr)
            assert isinstance(settings.secure_salt, SecretStr)
            assert settings.timezone == "US/Pacific"

    @patch("acb.config._testing", True)
    async def test_app_settings_title_generation(self) -> None:
        """Test that title is generated from name if not provided."""
        settings = AppSettings()
        settings.name = "test-app"
        settings.title = None
        settings.model_post_init(None)
        assert settings.title == "Test App"

    @patch("acb.config._testing", True)
    async def test_app_settings_custom_title(self) -> None:
        """Test that custom title is used if provided."""
        settings = AppSettings()
        settings.name = "test-app"
        settings.title = "Custom Title"
        settings.model_post_init(None)
        assert settings.title == "Custom Title"


class TestVersionFunctions:
    """Test the version-related functions."""

    async def test_get_version_from_pyproject(self) -> None:
        """Test getting version from pyproject.toml."""
        mock_root_path = MagicMock()
        mock_pyproject = MagicMock()
        mock_version_file = MagicMock()

        async def mock_pyproject_exists() -> bool:
            return True

        async def mock_version_file_exists() -> bool:
            return False

        async def mock_write_text(content: str) -> None:
            pass

        async def mock_load_toml(path: Any) -> dict[str, dict[str, str]]:
            return {"project": {"version": "1.2.3"}}

        with patch("acb.config.root_path", mock_root_path):
            mock_root_path.parent = MagicMock()
            mock_root_path.parent.__truediv__ = MagicMock(return_value=mock_pyproject)
            mock_root_path.__truediv__ = MagicMock(return_value=mock_version_file)

            mock_pyproject.exists = mock_pyproject_exists
            mock_version_file.exists = mock_version_file_exists
            mock_version_file.write_text = mock_write_text

            with patch("acb.actions.encode.load.toml", mock_load_toml):
                version = await get_version()

                assert version == "1.2.3"

    async def test_get_version_from_version_file(self) -> None:
        """Test getting version from _version file."""
        mock_root_path = MagicMock()
        mock_pyproject = MagicMock()
        mock_version_file = MagicMock()

        async def mock_pyproject_exists() -> bool:
            return False

        async def mock_version_file_exists() -> bool:
            return True

        async def mock_read_text() -> str:
            return "1.2.3"

        with patch("acb.config.root_path", mock_root_path):
            mock_root_path.parent = MagicMock()
            mock_root_path.parent.__truediv__ = MagicMock(return_value=mock_pyproject)
            mock_root_path.__truediv__ = MagicMock(return_value=mock_version_file)

            mock_pyproject.exists = mock_pyproject_exists
            mock_version_file.exists = mock_version_file_exists
            mock_version_file.read_text = mock_read_text

            version = await get_version()

            assert version == "1.2.3"

    async def test_get_version_default_value(self) -> None:
        """Test getting default version when no files exist."""
        mock_root_path = MagicMock()
        mock_pyproject = MagicMock()
        mock_version_file = MagicMock()

        async def mock_exists() -> bool:
            return False

        with patch("acb.config.root_path", mock_root_path):
            mock_root_path.parent = MagicMock()
            mock_root_path.parent.__truediv__ = MagicMock(return_value=mock_pyproject)
            mock_root_path.__truediv__ = MagicMock(return_value=mock_version_file)

            mock_pyproject.exists = mock_exists
            mock_version_file.exists = mock_exists

            version = await get_version()

            assert version == "0.0.1"

    async def test_get_version_default(self) -> None:
        """Test the get_version_default function."""

        async def mock_get_version_func() -> str:
            return "1.2.3"

        with patch("acb.config.get_version", mock_get_version_func):
            version = get_version_default()

            assert version == "1.2.3"


class TestConfig:
    """Test the Config class."""

    @patch("acb.config._testing", True)
    async def test_config_init(self) -> None:
        """Test initializing Config and calling init method."""
        with patch("acb.config.DebugSettings"):
            with patch("acb.config.AppSettings"):
                config = Config()
                config.init()
                assert not config.deployed
                assert hasattr(config, "debug")
                assert hasattr(config, "app")
