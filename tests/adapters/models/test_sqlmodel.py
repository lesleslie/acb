"""Tests for the SQLModel adapter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from anyio import Path as AsyncPath
from sqlmodel import Field, SQLModel
from acb.adapters.models._sqlmodel import ModelsSettings


class SampleModel(SQLModel, table=True):  # type: ignore
    id: int | None = Field(default=None, primary_key=True)
    name: str
    value: int


class TestModelsSettings:
    def test_init(self) -> None:
        settings = ModelsSettings()
        settings.path = AsyncPath("/test/models")  # type: ignore
        assert settings.path == AsyncPath("/test/models")  # type: ignore


class TestModels:
    @pytest.fixture(autouse=True)
    def setup_method(self) -> None:
        self.config = MagicMock()
        self.logger = MagicMock()
        self.models = []
        self.settings: ModelsSettings | None = None
        self.sql = MagicMock()

    async def _import_models_file(self, path: AsyncPath) -> None:
        pass

    async def _import_models_directory(self, path: AsyncPath) -> None:
        pass

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        mock_config: MagicMock = MagicMock()
        mock_config.get_path.return_value = "/path/to/models"
        return mock_config

    @pytest.fixture
    def models_settings(self) -> ModelsSettings:
        return ModelsSettings()

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

            with patch.object(
                models_instance,
                "_import_models_file",
                wraps=models_instance._import_models_file,
            ) as mock_import_file:
                await models_instance.import_models(path)
                mock_import_file.assert_called_once_with(path)

    @pytest.mark.asyncio
    async def test_import_models_directory(
        self,
        models_instance: "TestModels",
    ) -> None:
        path = AsyncPath("/path/to/models")
        with patch.object(AsyncPath, "is_dir", new_callable=AsyncMock) as mock_is_dir:
            mock_is_dir.return_value = True

            with patch.object(
                models_instance,
                "_import_models_directory",
                wraps=models_instance._import_models_directory,
            ) as mock_import_dir:
                await models_instance.import_models(path)
                mock_import_dir.assert_called_once_with(path)

    @pytest.mark.asyncio
    async def test_import_models_directory_not_found(
        self,
        models_instance: "TestModels",
    ) -> None:
        path = AsyncPath("/path/to/models")
        with (
            patch.object(AsyncPath, "is_dir", new_callable=AsyncMock) as mock_is_dir,
            patch.object(AsyncPath, "exists", new_callable=AsyncMock) as mock_exists,
        ):
            mock_is_dir.return_value = True
            mock_exists.return_value = False

            with (
                patch.object(
                    models_instance,
                    "_import_models_directory",
                    side_effect=FileNotFoundError("Directory not found"),
                ),
                pytest.raises(FileNotFoundError),
            ):
                await models_instance.import_models(path)

    @pytest.mark.asyncio
    async def test_init(self) -> None:
        models = TestModels()
        settings = ModelsSettings()
        await models.init(settings)
        assert models.settings == settings
