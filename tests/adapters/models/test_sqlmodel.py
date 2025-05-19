"""Tests for the SQLModel adapter."""

import typing as t
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from anyio import Path as AsyncPath
from sqlmodel import Field, SQLModel
from acb.adapters.models.sqlmodel import Models, ModelsSettings


class TestModel(SQLModel, table=True):
    id: t.Optional[int] = Field(default=None, primary_key=True)
    name: str
    value: int


class TestModelsSettings:
    def test_init(self) -> None:
        settings: ModelsSettings = ModelsSettings(path="/test/models")  # type: ignore
        assert settings.path == "/test/models"


class TestModels:
    @pytest.fixture
    def mock_config(self) -> MagicMock:
        mock_config: MagicMock = MagicMock()
        mock_config.get_path.return_value = "/path/to/models"
        return mock_config

    @pytest.fixture
    def models_settings(self) -> ModelsSettings:
        return ModelsSettings()  # type: ignore

    @pytest.fixture
    def models_instance(self, mock_config: MagicMock) -> Models:
        class TestModels(Models):
            def __init__(self) -> None:
                self.config = mock_config
                self.logger = MagicMock()
                self.models = []
                self.settings = None
                self.sql = MagicMock()
                self._import_models_directory = AsyncMock()
                self._import_models_file = AsyncMock()

            async def import_models(self, path: AsyncPath) -> None:
                if await path.is_dir():
                    await self._import_models_directory(path)
                else:
                    await self._import_models_file(path)

            async def init(self, settings=None) -> None:
                self.settings = settings

        models = TestModels()
        return models

    @pytest.mark.asyncio
    async def test_import_models_file(self, models_instance: Models) -> None:
        models_instance._import_models_file = AsyncMock()

        path = AsyncPath("/path/to/models/model.py")
        with (
            patch.object(
                AsyncPath, "is_dir", new_callable=AsyncMock, return_value=False
            ),
            patch.object(
                AsyncPath, "is_file", new_callable=AsyncMock, return_value=True
            ),
        ):
            await models_instance.import_models(path)
            models_instance._import_models_file.assert_called_once_with(path)

    @pytest.mark.asyncio
    async def test_import_models_directory(
        self,
        models_instance: Models,
    ) -> None:
        models_instance._import_models_directory = AsyncMock()

        path = AsyncPath("/path/to/models")
        with (
            patch.object(
                AsyncPath, "is_dir", new_callable=AsyncMock, return_value=True
            ),
            patch.object(
                AsyncPath, "is_file", new_callable=AsyncMock, return_value=False
            ),
        ):
            await models_instance.import_models(path)
            models_instance._import_models_directory.assert_called_once_with(path)

    @pytest.mark.asyncio
    async def test_import_models_file_not_found(self, models_instance: Models) -> None:
        models_instance._import_models_file = AsyncMock(side_effect=FileNotFoundError)
        models_instance.logger = MagicMock()

        path = AsyncPath("/path/to/models/model.py")
        with (
            patch.object(
                AsyncPath, "is_dir", new_callable=AsyncMock, return_value=False
            ),
            patch.object(
                AsyncPath, "is_file", new_callable=AsyncMock, return_value=True
            ),
        ):
            try:
                await models_instance.import_models(path)
            except FileNotFoundError:
                pass
            models_instance._import_models_file.assert_called_once_with(path)

    @pytest.mark.asyncio
    async def test_import_models_directory_not_found(
        self, models_instance: Models
    ) -> None:
        models_instance._import_models_directory = AsyncMock(
            side_effect=FileNotFoundError
        )
        models_instance.logger = MagicMock()

        path = AsyncPath("/path/to/models")
        with (
            patch.object(
                AsyncPath, "is_dir", new_callable=AsyncMock, return_value=True
            ),
            patch.object(
                AsyncPath, "is_file", new_callable=AsyncMock, return_value=False
            ),
        ):
            try:
                await models_instance.import_models(path)
            except FileNotFoundError:
                pass
            models_instance._import_models_directory.assert_called_once_with(path)

    @pytest.mark.asyncio
    async def test_init(
        self,
        models_instance: Models,
    ) -> None:
        settings: ModelsSettings = ModelsSettings(path="/path/to/models")  # type: ignore
        await models_instance.init(settings=settings)
        assert models_instance.settings == settings

    def test_init_settings(self) -> None:
        settings: ModelsSettings = ModelsSettings(path="/path/to/models")  # type: ignore
        assert str(settings.path) == "/path/to/models"
