from typing import Any, Optional, cast
from unittest.mock import MagicMock, patch

import pytest
from anyio import Path as AsyncPath
from sqlmodel import Field, SQLModel
from acb.adapters.models.sqlmodel import Models, ModelsSettings, imported_models
from acb.config import Config


class TestModel(SQLModel, table=True):
    id: int = Field(primary_key=True)
    name: str
    description: Optional[str] = None


class TestModelsSettings:
    def test_init(self) -> None:
        settings = ModelsSettings()

        assert isinstance(settings, ModelsSettings)


class TestModels:
    @pytest.fixture
    def mock_config(self) -> MagicMock:
        mock_config = MagicMock(spec=Config)
        return mock_config

    @pytest.fixture
    def models_instance(self, mock_config: MagicMock) -> Models:
        imported_models.set([])

        mock_sql = MagicMock()

        models = Models()
        models.config = mock_config
        models.logger = MagicMock()

        models.sql = mock_sql

        return models

    def test_import_models_file(
        self,
        models_instance: Models,
    ) -> None:
        mock_path = MagicMock(spec=AsyncPath)
        mock_path.parts = ["acb", "models", "test_model.py"]

        mock_module = MagicMock()
        mock_module.__dict__ = {"TestModel": TestModel}

        async def mock_import_models(path: AsyncPath) -> None:
            from acb.adapters.models.sqlmodel import debug

            debug(path, -2, "models.test_model")

            setattr(models_instance.sql.__class__, "TestModel", TestModel)
            imported_models.get().append("TestModel")
            models_instance.logger.debug("TestModel model imported")

        models_instance.import_models = mock_import_models

        with (
            patch(
                "acb.adapters.models.sqlmodel.import_module", return_value=mock_module
            ),
            patch("acb.adapters.models.sqlmodel.debug") as mock_debug,
        ):
            import asyncio

            asyncio.run(models_instance.import_models(mock_path))

            mock_debug.assert_called_once_with(mock_path, -2, "models.test_model")

            assert hasattr(models_instance.sql, "TestModel")
            assert cast(Any, models_instance.sql).TestModel == TestModel

            assert "TestModel" in imported_models.get()

            models_instance.logger.debug.assert_called_once_with(
                "TestModel model imported"
            )
