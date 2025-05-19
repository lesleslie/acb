"""Tests for the SQLModel adapter."""

import typing as t
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

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
            import_models_directory: t.ClassVar[t.Any] = AsyncMock()
            import_models_file: t.ClassVar[t.Any] = AsyncMock()
            models: t.ClassVar[list[t.Any]] = []
            settings: t.ClassVar[t.Optional[ModelsSettings]] = None

        models: Models = TestModels()
        models.config = mock_config
        models.logger = MagicMock()
        setattr(models, "import_models_directory", AsyncMock())
        return models

    @pytest.mark.asyncio
    async def test_import_models_file(self, models_instance: Models) -> None:
        setattr(models_instance, "import_models_file", AsyncMock())
        path: AsyncPath = AsyncPath("/path/to/models/model.py")
        await models_instance.import_models(path)
        models_instance.import_models_file.assert_called_once_with(path)  # type: ignore

    @pytest.mark.asyncio
    async def test_import_models_directory(
        self,
        models_instance: Models,
        mock_path: AsyncPath,
    ) -> None:
        setattr(models_instance, "import_models_directory", AsyncMock())
        models_instance.models = []  # type: ignore
        await models_instance.import_models_directory(mock_path)  # type: ignore
        models_instance.import_models_directory.assert_called_once_with(mock_path)  # type: ignore

    @pytest.mark.asyncio
    async def test_import_models_file_not_found(self, models_instance: Models) -> None:
        setattr(
            models_instance,
            "import_models_file",
            AsyncMock(side_effect=FileNotFoundError),
        )
        path: AsyncPath = AsyncPath("/path/to/models/model.py")
        await models_instance.import_models(path)
        models_instance.import_models_file.assert_called_once_with(path)  # type: ignore
        models_instance.logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_import_models_directory_not_found(
        self, models_instance: Models, mock_path: AsyncPath
    ) -> None:
        setattr(
            models_instance,
            "import_models_directory",
            AsyncMock(side_effect=FileNotFoundError),
        )
        path: AsyncPath = AsyncPath("/path/to/models")
        await models_instance.import_models(path)
        models_instance.import_models_directory.assert_called_once_with(path)  # type: ignore
        models_instance.logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_init(
        self,
        models_instance: Models,
        mock_path: AsyncPath,
    ) -> None:
        setattr(models_instance, "import_models_directory", AsyncMock())
        models_instance.models = []  # type: ignore
        settings: ModelsSettings = ModelsSettings(path="/path/to/models")  # type: ignore
        await models_instance.init(settings=settings)  # type: ignore
        assert models_instance.settings == settings  # type: ignore
        assert len(models_instance.models) == 1  # type: ignore

    def test_init_settings(self) -> None:
        settings: ModelsSettings = ModelsSettings(path="/path/to/models")  # type: ignore
        assert settings.path == Path("/path/to/models")
