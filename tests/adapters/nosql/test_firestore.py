"""Tests for the Firestore NoSQL adapter."""

from typing import Any, Callable, Optional, Type
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from google.cloud import firestore
from acb.adapters.nosql.firestore import Nosql as FirestoreNosql
from acb.adapters.nosql.firestore import NosqlSettings as FirestoreSettings


@pytest.fixture
async def mock_async_context_manager(self: Any) -> Callable[[Optional[Any]], Any]:
    class MockAsyncContextManager:
        def __init__(self, mock_obj: Optional[Any] = None) -> None:
            self.mock_obj = mock_obj or MagicMock()

        async def __aenter__(self) -> Any:
            return self.mock_obj

        async def __aexit__(
            self,
            exc_type: Optional[Type[BaseException]],
            exc_val: Optional[BaseException],
            exc_tb: Optional[Any],
        ) -> None:
            pass

    def _mock_async_context_manager(
        mock_obj: Optional[Any] = None,
    ) -> MockAsyncContextManager:
        return MockAsyncContextManager(mock_obj)

    return _mock_async_context_manager


class TestFirestoreSettings:
    def test_init(self) -> None:
        settings = FirestoreSettings(
            project_id="test-project",
            database="test-db",
            credentials_file="/path/to/credentials.json",
        )

        assert settings.project_id == "test-project"
        assert settings.database == "test-db"
        assert settings.credentials_file == "/path/to/credentials.json"

        settings = FirestoreSettings(
            project_id="test-project",
        )

        assert settings.project_id == "test-project"
        assert settings.database == "(default)"
        assert settings.credentials_file is None


class TestFirestore:
    @pytest.fixture
    def nosql(self, mock_async_context_manager: Any):
        nosql = FirestoreNosql()
        nosql.config = MagicMock()
        nosql.logger = MagicMock()

        mock_client = MagicMock(spec=firestore.AsyncClient)
        type(nosql).client = PropertyMock(return_value=mock_client)

        mock_db = MagicMock()
        type(nosql).db = PropertyMock(return_value=mock_db)

        mock_collection_ref = MagicMock()
        mock_db.collection.return_value = mock_collection_ref
        mock_collection_ref.document.return_value = MagicMock()
        mock_collection_ref.where.return_value = MagicMock()

        mock_client.transaction.return_value = mock_async_context_manager()

        return nosql

    def test_client_property(self, nosql: FirestoreNosql) -> None:
        assert nosql.client is not None

    def test_db_property(self, nosql: FirestoreNosql) -> None:
        assert nosql.db is not None

    @pytest.mark.asyncio
    async def test_init(self, nosql: FirestoreNosql) -> None:
        nosql.config.nosql.get.return_value = FirestoreSettings(
            project_id="test-project",
            database="test-db",
        )

        with patch("google.cloud.firestore.AsyncClient") as mock_client_class:
            await nosql.init()
            mock_client_class.assert_called_once()
            nosql.logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_init_error(self, nosql: FirestoreNosql) -> None:
        nosql.config.nosql.get.return_value = FirestoreSettings(
            project_id="test-project",
            database="test-db",
        )

        with patch(
            "google.cloud.firestore.AsyncClient",
            side_effect=Exception("Connection error"),
        ):
            with pytest.raises(Exception) as excinfo:
                await nosql.init()
            assert "Connection error" in str(excinfo.value)
            nosql.logger.error.assert_called_once()

    def test_get_collection_ref(self, nosql: FirestoreNosql) -> None:
        collection_ref = nosql._get_collection_ref("test_collection")
        assert nosql.db.collection is not None
        assert nosql.db.collection.called  # type: ignore
        assert collection_ref is not None

    def test_convert_to_dict(self, nosql: FirestoreNosql) -> None:
        mock_doc = MagicMock()
        mock_doc.id = "test_id"
        mock_doc.to_dict.return_value = {"name": "test", "age": 30}

        result = nosql._convert_to_dict(mock_doc)

        assert result == {"_id": "test_id", "name": "test", "age": 30}
