from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from acb.config import Config


@pytest.mark.unit
class TestAdapterImport:
    def test_import_existing_adapter(self) -> None:
        with patch("acb.adapters.import_adapter") as mock_import_adapter:
            mock_class = MagicMock()
            mock_import_adapter.return_value = mock_class

            adapters = ["storage", "cache", "models", "monitoring"]
            for adapter_name in adapters:
                adapter = mock_import_adapter(adapter_name)
                assert adapter is not None

    def test_import_nonexistent_adapter(self) -> None:
        def mock_import_adapter(*args: Any, **kwargs: Any):
            raise ImportError("Adapter not found")

        with pytest.raises(ImportError):
            mock_import_adapter("nonexistent_adapter")

    def test_import_adapter_with_dependencies(self) -> None:
        mock_config = MagicMock(spec=Config)
        mock_adapter_class = MagicMock()

        with patch("acb.adapters.import_adapter") as mock_import_adapter:
            mock_import_adapter.return_value = mock_adapter_class

            with patch("acb.depends.depends.get", return_value=mock_config):
                adapter = mock_import_adapter("storage")
                assert adapter is not None


@pytest.mark.unit
class TestStorageAdapter:
    @pytest.mark.asyncio
    async def test_storage_operations(self) -> None:
        mock_storage = AsyncMock()
        mock_storage.write = AsyncMock()
        mock_storage.read = AsyncMock()
        mock_storage.delete = AsyncMock()

        test_data = b"test data"
        test_path = Path("test.txt")

        await mock_storage.write(test_path, test_data)
        mock_storage.write.assert_awaited_once_with(test_path, test_data)

        await mock_storage.read(test_path)
        mock_storage.read.assert_awaited_once_with(test_path)

        await mock_storage.delete(test_path)
        mock_storage.delete.assert_awaited_once_with(test_path)


@pytest.mark.unit
class TestMonitoringAdapter:
    def test_monitoring_configuration(self) -> None:
        mock_monitoring = MagicMock()
        mock_config = MagicMock()
        mock_config.monitoring = MagicMock(dsn="test-dsn", environment="test")

        monitoring = mock_monitoring()
        monitoring.configure(mock_config.monitoring)

        mock_monitoring.return_value.configure.assert_called_once_with(
            mock_config.monitoring
        )
