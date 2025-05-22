"""Tests for the SQLModel adapter."""

import typing as t
from contextlib import suppress
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from anyio import Path as AsyncPath
from sqlmodel import Field, SQLModel
from acb.adapters.models.sqlmodel import ModelsSettings


class TestModel(SQLModel, table=True):  # type: ignore
    id: t.Optional[int] = Field(default=None, primary_key=True)
    name: str
    value: int


class TestModelsSettings:
    def test_init(self) -> None:
        settings = ModelsSettings()
        settings.path = AsyncPath("/test/models")  # type: ignore
        assert settings.path == AsyncPath("/test/models")


class TestModels:
    def __init__(self) -> None:
        self.config = MagicMock()
        self.logger = MagicMock()
        self.models = []
        self.settings: ModelsSettings | None = None
        self.sql = MagicMock()
        self._import_models_directory = AsyncMock()  # type: ignore
        self._import_models_file = AsyncMock()  # type: ignore

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        mock_config: MagicMock = MagicMock()
        mock_config.get_path.return_value = "/path/to/models"
        return mock_config

    @pytest.fixture
    def models_settings(self) -> ModelsSettings:
        settings = ModelsSettings()
        return settings

    @pytest.fixture
    def models_instance(self, mock_config: MagicMock) -> "TestModels":
        instance = TestModels()
        instance.config = mock_config
        return instance

    async def import_models(self, path: AsyncPath) -> None:
        if await path.is_dir():
            await self._import_models_directory(path)
        else:
            await self._import_models_file(path)

    async def init(self, settings: ModelsSettings | None = None) -> None:
        self.settings = settings

    @pytest.mark.asyncio
    async def test_import_models_file(self, models_instance: "TestModels") -> None:
        path = AsyncPath("/path/to/models/model.py")
        with (
            patch.object(AsyncPath, "is_dir", new_callable=AsyncMock) as mock_is_dir,
            patch.object(AsyncPath, "is_file", new_callable=AsyncMock) as mock_is_file,
        ):
            mock_is_dir.return_value = False
            mock_is_file.return_value = True
            await models_instance.import_models(path)
            models_instance._import_models_file.assert_called_once_with(path)

    @pytest.mark.asyncio
    async def test_import_models_directory(
        self,
        models_instance: "TestModels",
    ) -> None:
        path = AsyncPath("/path/to/models")
        with patch.object(AsyncPath, "is_dir", new_callable=AsyncMock) as mock_is_dir:
            mock_is_dir.return_value = True
            await models_instance.import_models(path)
            models_instance._import_models_directory.assert_called_once_with(path)

    @pytest.mark.asyncio
    async def test_import_models_file_not_found(
        self, models_instance: "TestModels"
    ) -> None:
        path = AsyncPath("/path/to/models/model.py")
        with (
            patch.object(AsyncPath, "is_dir", new_callable=AsyncMock) as mock_is_dir,
            patch.object(AsyncPath, "is_file", new_callable=AsyncMock) as mock_is_file,
        ):
            mock_is_dir.return_value = False
            mock_is_file.return_value = True
            models_instance._import_models_file.side_effect = FileNotFoundError
            models_instance.logger = MagicMock()
            with suppress(FileNotFoundError):
                await models_instance.import_models(path)
            models_instance._import_models_file.assert_called_once_with(path)

    @pytest.mark.asyncio
    async def test_import_models_directory_not_found(
        self, models_instance: "TestModels"
    ) -> None:
        path = AsyncPath("/path/to/models")
        with patch.object(AsyncPath, "is_dir", new_callable=AsyncMock) as mock_is_dir:
            mock_is_dir.return_value = True
            models_instance._import_models_directory.side_effect = FileNotFoundError
            models_instance.logger = MagicMock()
            with suppress(FileNotFoundError):
                await models_instance.import_models(path)
            models_instance._import_models_directory.assert_called_once_with(path)

    @pytest.mark.asyncio
    async def test_init(
        self,
        models_instance: "TestModels",
    ) -> None:
        models_instance.import_models = AsyncMock()  # type: ignore

        settings = ModelsSettings()
        settings.path = AsyncPath("/path/to/models")  # type: ignore

        await models_instance.init(settings)

        assert models_instance.settings == settings

    def test_init_settings(self) -> None:
        settings = ModelsSettings()
        settings.path = AsyncPath("/path/to/models")  # type: ignore
        assert settings.path == AsyncPath("/path/to/models")
