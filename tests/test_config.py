import typing as t
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr
from acb.config import (
    Config,
    DebugSettings,
    InitSettingsSource,
    PydanticSettingsSource,
    gen_password,
    get_version,
)


@pytest.fixture
def config() -> Config:
    config: Config = Config()
    return config


@pytest.mark.asyncio
async def test_get_version() -> None:
    with patch("acb.config.root_path") as mock_root_path:
        mock_path: MagicMock = MagicMock()
        mock_exists_coro: AsyncMock = AsyncMock()
        mock_exists_coro.return_value = True
        mock_path.exists = mock_exists_coro

        mock_pyproject: MagicMock = MagicMock()
        mock_pyproject.exists = mock_exists_coro
        mock_path.__truediv__ = MagicMock(return_value=mock_pyproject)

        mock_root_path.parent = mock_path

        with patch("acb.config.load") as mock_load:
            mock_toml_coro: AsyncMock = AsyncMock()
            mock_toml_coro.return_value = {"project": {"version": "0.1.0"}}
            mock_load.toml = mock_toml_coro

            version: str = await get_version()
            assert version == "0.1.0"

    with patch("acb.config.root_path") as mock_root_path:
        mock_path: MagicMock = MagicMock()
        mock_exists_coro: AsyncMock = AsyncMock()
        mock_exists_coro.return_value = False
        mock_path.exists = mock_exists_coro

        mock_pyproject: MagicMock = MagicMock()
        mock_pyproject.exists = mock_exists_coro
        mock_path.__truediv__ = MagicMock(return_value=mock_pyproject)

        mock_root_path.parent = mock_path

        version: str = await get_version()
        assert version == "0.1.0"


def test_gen_password() -> None:
    password: str = gen_password()
    assert isinstance(password, str)
    assert password

    password = gen_password(size=20)
    assert isinstance(password, str)
    assert password


@pytest.mark.asyncio
async def test_pydantic_settings_source() -> None:
    settings_cls: MagicMock = MagicMock()
    settings_cls.__name__ = "TestSettings"
    settings_cls.model_fields: dict[str, t.Any] = {}

    source: PydanticSettingsSource = PydanticSettingsSource(settings_cls=settings_cls)  # type: ignore
    assert source.adapter_name == "test"
    assert source.settings_cls == settings_cls

    settings_cls.model_fields = {
        "password": MagicMock(annotation=SecretStr),
        "name": MagicMock(annotation=str),
    }
    secrets: list[str] = source.get_model_secrets()  # type: ignore
    assert "test_password" in secrets
    assert "test_name" not in secrets


@pytest.mark.asyncio
async def test_init_settings_source() -> None:
    settings_cls: MagicMock = MagicMock()
    settings_cls.__name__ = "TestSettings"
    settings_cls.model_fields: dict[str, t.Any] = {}

    init_kwargs: dict[str, t.Any] = {"name": "test", "value": 123}
    source: InitSettingsSource = InitSettingsSource(
        settings_cls=settings_cls,  # type: ignore
        init_kwargs=init_kwargs,
    )

    result: dict[str, t.Any] = await source()
    assert result == init_kwargs


@pytest.mark.asyncio
async def test_debug_settings() -> None:
    debug_settings: DebugSettings = DebugSettings()
    assert not debug_settings.production
    assert not debug_settings.secrets
    assert not debug_settings.logger

    debug_settings = DebugSettings(production=True, secrets=True, logger=True)
    assert debug_settings.production is True
    assert debug_settings.secrets is True
    assert debug_settings.logger is True
