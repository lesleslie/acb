from unittest.mock import AsyncMock, patch

import pytest
from aiopath import AsyncPath
from pydantic import SecretStr
from acb.config import (
    AppSettings,
    Config,
    FileSecretSource,
    Platform,
    Settings,
    YamlSettingsSource,
    gen_password,
    get_version,
)


@pytest.mark.asyncio
async def test_get_version_with_pyproject(monkeypatch: pytest.MonkeyPatch) -> None:
    AsyncPath("/fake/path/pyproject.toml")
    AsyncPath("/fake/path/_version")

    with (
        patch("acb.config.load.toml", new_callable=AsyncMock) as mock_load_toml,
        patch.object(AsyncPath, "exists", new_callable=AsyncMock) as mock_exists,
        patch.object(AsyncPath, "write_text", new_callable=AsyncMock) as mock_write,
    ):
        mock_exists.return_value = True
        mock_load_toml.return_value = {"project": {"version": "1.2.3"}}

        result = await get_version()

        monkeypatch.setattr("acb.config.root_path", AsyncPath("/fake/path"))

        assert result == "1.2.3"
        mock_load_toml.assert_called_once()
        mock_write.assert_called_once_with("1.2.3")


@pytest.mark.asyncio
async def test_get_version_with_version_file() -> None:
    with (
        patch("acb.config.root_path", AsyncPath("/fake/path")),
        patch.object(AsyncPath, "exists", new_callable=AsyncMock) as mock_exists,
        patch.object(AsyncPath, "read_text", new_callable=AsyncMock) as mock_read,
    ):
        mock_exists.side_effect = [False, True]
        mock_read.return_value = "2.3.4"

        result = await get_version()

        assert result == "2.3.4"
        mock_read.assert_called_once()


@pytest.mark.asyncio
async def test_get_version_fallback() -> None:
    with (
        patch("acb.config.root_path", AsyncPath("/fake/path")),
        patch.object(AsyncPath, "exists", new_callable=AsyncMock) as mock_exists,
    ):
        mock_exists.return_value = False

        result = await get_version()

        assert result == "0.0.1"


def test_platform_enum() -> None:
    assert Platform.aws.value == "aws"
    assert Platform.gcp.value == "gcp"
    assert Platform.azure.value == "azure"

    aws_value = Platform.aws
    gcp_value = Platform.gcp
    azure_value = Platform.azure

    assert aws_value == "aws"
    assert gcp_value == "gcp"
    assert azure_value == "azure"


def test_gen_password() -> None:
    password = gen_password()
    assert isinstance(password, str)
    assert len(password) >= 10

    custom_size = 20
    password = gen_password(custom_size)
    assert isinstance(password, str)
    assert len(password) >= custom_size


@pytest.mark.asyncio
async def test_settings_initialization() -> None:
    with patch(
        "acb.config.Settings._settings_build_values", new_callable=AsyncMock
    ) as mock_build:
        mock_build.return_value = {"test_key": "test_value"}

        settings = Settings()

        mock_build.assert_called_once()
        assert settings.test_key == "test_value"


@pytest.mark.asyncio
async def test_app_settings_validation_valid_name() -> None:
    app_settings = AppSettings(name="valid-app-name")
    assert app_settings.name == "valid-app-name"
    assert app_settings.title == "Valid App Name"


@pytest.mark.asyncio
async def test_app_settings_validation_invalid_name_too_short() -> None:
    with pytest.raises(SystemExit, match="App name to short"):
        AppSettings(name="ab")


@pytest.mark.asyncio
async def test_app_settings_validation_invalid_name_too_long() -> None:
    long_name = "a" * 64
    with pytest.raises(SystemExit, match="App name to long"):
        AppSettings(name=long_name)


@pytest.mark.asyncio
async def test_app_settings_validation_name_with_special_chars() -> None:
    with (
        patch.object(
            AppSettings, "_settings_build_values", new_callable=AsyncMock
        ) as mock_build,
        patch.object(
            AppSettings, "cloud_compliant_app_name", return_value="my-app-name123"
        ),
    ):
        mock_build.return_value = {"name": "my-app-name123"}

        app_settings = AppSettings(name="My App_Name.123!")
        assert app_settings.name == "my-app-name123"


async def test_file_secret_source() -> None:
    class MockSettings(Settings):
        mock_password: SecretStr = SecretStr("default_password")
        mock_api_key: SecretStr = SecretStr("default_api_key")
        normal_field: str = "normal"

    with patch("acb.config._testing", True):
        test_secrets_path = AsyncPath("/tmp/test_secrets")  # nosec B108
        file_source = FileSecretSource(MockSettings, secrets_path=test_secrets_path)

        model_secrets = file_source.get_model_secrets()
        assert "mock_mock_password" in model_secrets
        assert "mock_mock_api_key" in model_secrets
        assert "normal_field" not in model_secrets

        result = await file_source()

        assert isinstance(result.get("mock_password"), SecretStr)
        assert result["mock_password"].get_secret_value() == "default_password"

        assert isinstance(result.get("mock_api_key"), SecretStr)
        assert result["mock_api_key"].get_secret_value() == "default_api_key"


async def test_yaml_settings_source_testing_mode() -> None:
    class MockSettings(Settings):
        field1: str = "default1"
        field2: int = 42
        secret_field: SecretStr = SecretStr("secret")

    with (
        patch("acb.config._testing", True),
        patch("acb.config.debug", {}),
        patch("acb.config.project", ""),
        patch("acb.config.app_name", ""),
    ):
        yaml_source = YamlSettingsSource(MockSettings)

        result = await yaml_source.load_yml_settings()

        assert result["field1"] == "default1"
        assert result["field2"] == 42
        assert "secret_field" not in result

        call_result = await yaml_source()
        assert call_result["field1"] == "default1"
        assert call_result["field2"] == 42


@pytest.mark.asyncio
async def test_config_initialization() -> None:
    with (
        patch("acb.config.DebugSettings", return_value="debug_settings"),
        patch("acb.config.AppSettings", return_value="app_settings"),
    ):
        config = Config()
        config.init()

        assert config.debug == "debug_settings"
        assert config.app == "app_settings"
