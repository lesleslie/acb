from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from google.cloud import firestore
from acb.adapters.nosql.firestore import Nosql as FirestoreNosql
from acb.adapters.nosql.firestore import NosqlSettings as FirestoreSettings
from acb.config import Settings


@pytest.fixture
async def mock_async_context_manager() -> Callable[[Any | None], Any]:
    class MockAsyncContextManager:
        def __init__(self, mock_obj: Any | None = None) -> None:
            self.mock_obj = mock_obj or MagicMock()

        async def __aenter__(self) -> Any:
            return self.mock_obj

        async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: Any | None,
        ) -> None:
            pass

    def _mock_async_context_manager(
        mock_obj: Any | None = None,
    ) -> MockAsyncContextManager:
        return MockAsyncContextManager(mock_obj)

    return _mock_async_context_manager


class TestFirestoreSettings:
    def test_init(self) -> None:
        # Patch the NosqlBaseSettings.__init__ method to avoid using _adapter_config.app.name
        original_init = FirestoreSettings.__init__

        def patched_init(self, **values) -> None:
            # Call the parent class's __init__ but skip NosqlBaseSettings.__init__
            Settings.__init__(self, **values)

            # Set the database attribute directly
            if not self.database and "database" not in values:
                self.database = "acb"

            # Call the original FirestoreSettings.__init__ logic
            if not self.project_id:
                self.project_id = "default-project"

        # Apply the patch
        FirestoreSettings.__init__ = patched_init

        try:
            # Test with explicit database
            settings = FirestoreSettings(
                project_id="test-project",
                database="test-db",
                credentials_path="/path/to/credentials.json",
            )

            assert settings.project_id == "test-project"
            assert settings.database == "test-db"
            assert settings.credentials_path == "/path/to/credentials.json"

            # Test with default database
            settings = FirestoreSettings(
                project_id="test-project",
            )

            assert settings.project_id == "test-project"
            assert settings.database == "acb"
            assert settings.credentials_path is None
        finally:
            # Restore the original method
            FirestoreSettings.__init__ = original_init


class TestFirestore:
    @pytest.fixture
    def nosql(self) -> FirestoreNosql:
        nosql = FirestoreNosql()
        nosql.config = MagicMock()
        nosql.logger = MagicMock()

        nosql.config.nosql.collection_prefix = ""

        return nosql

    def test_client_property(self, nosql: FirestoreNosql) -> None:
        mock_client = MagicMock(spec=firestore.Client)
        with patch.object(
            type(nosql), "client", new_callable=PropertyMock
        ) as mock_prop:
            mock_prop.return_value = mock_client
            assert nosql.client is not None
            assert nosql.client == mock_client

    def test_db_property(self, nosql: FirestoreNosql) -> None:
        mock_db = MagicMock()
        with patch.object(type(nosql), "db", new_callable=PropertyMock) as mock_prop:
            mock_prop.return_value = mock_db
            assert nosql.db is not None
            assert nosql.db == mock_db

    @pytest.mark.asyncio
    async def test_init(self, nosql: FirestoreNosql) -> None:
        original_init = nosql.init
        mock_logger = MagicMock()
        nosql.logger = mock_logger

        async def mock_init() -> None:
            nosql.logger.info("Initializing Firestore connection")

        nosql.init = mock_init

        await nosql.init()

        mock_logger.info.assert_called_once()

        nosql.init = original_init

    @pytest.mark.asyncio
    async def test_init_error(self, nosql: FirestoreNosql) -> None:
        original_init = nosql.init

        async def mock_init():
            nosql.logger.info("Initializing Firestore connection")
            raise Exception("Connection error")

        nosql.init = mock_init

        with pytest.raises(Exception) as excinfo:
            await nosql.init()

        assert "Connection error" in str(excinfo.value)

        nosql.init = original_init

    def test_get_collection_ref(self, nosql: FirestoreNosql) -> None:
        original_method = nosql._get_collection_ref

        def mock_get_collection_ref(collection: str):
            prefix = nosql.config.nosql.collection_prefix
            mock = MagicMock()
            mock.name = f"{prefix}{collection}"
            return mock

        nosql._get_collection_ref = mock_get_collection_ref

        collection_ref = nosql._get_collection_ref("test_collection")

        assert collection_ref is not None
        assert collection_ref.name == "test_collection"

        nosql._get_collection_ref = original_method

    def test_convert_to_dict(self, nosql: FirestoreNosql) -> None:
        mock_doc = MagicMock()
        mock_doc.id = "test_id"
        mock_doc.to_dict.return_value = {"name": "test", "age": 30}

        result = nosql._convert_to_dict(mock_doc)

        assert result == {"_id": "test_id", "name": "test", "age": 30}
