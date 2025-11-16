"""Comprehensive tests for Firestore NoSQL adapter."""

from unittest.mock import MagicMock, patch

import pytest
import typing as t

from acb.adapters.nosql.firestore import Nosql, NosqlSettings
from acb.config import Config


class MockDocument(MagicMock):
    """Mock for Firestore Document."""

    def __init__(
        self,
        doc_id: str,
        data: dict[str, t.Any] | None = None,
        exists: bool = True,
        *args: t.Any,
        **kwargs: t.Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.id = doc_id
        self._data = data or {}
        self.exists = exists

    def to_dict(self) -> dict[str, t.Any] | None:
        return self._data if self.exists else None


class MockDocumentReference(MagicMock):
    """Mock for Firestore DocumentReference."""

    def __init__(self, doc_id: str, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self.id = doc_id
        self.get = MagicMock()
        self.set = MagicMock()
        self.update = MagicMock()
        self.delete = MagicMock()


class MockCollectionReference(MagicMock):
    """Mock for Firestore CollectionReference."""

    def __init__(self, collection_name: str, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self.collection_name = collection_name
        self.document = MagicMock()
        self.add = MagicMock()
        self.where = MagicMock(return_value=self)
        self.limit = MagicMock(return_value=self)
        self.order_by = MagicMock(return_value=self)
        self.stream = MagicMock()


class MockQuery(MagicMock):
    """Mock for Firestore Query."""

    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self.where = MagicMock(return_value=self)
        self.limit = MagicMock(return_value=self)
        self.order_by = MagicMock(return_value=self)
        self.stream = MagicMock()


class MockBatch(MagicMock):
    """Mock for Firestore Batch."""

    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self.set = MagicMock()
        self.update = MagicMock()
        self.delete = MagicMock()
        self.commit = MagicMock()


class MockTransaction(MagicMock):
    """Mock for Firestore Transaction."""

    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self.__enter__ = MagicMock(return_value=self)
        self.__exit__ = MagicMock(return_value=None)


class MockFirestoreClient(MagicMock):
    """Mock for Firestore Client."""

    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self.collection = MagicMock()
        self.batch = MagicMock()
        self.transaction = MagicMock()


class TestFirestoreSettings:
    """Test Firestore NoSQL settings."""

    @pytest.fixture
    def mock_config(self):
        """Mock config for settings testing."""
        mock_config = MagicMock(spec=Config)
        mock_app = MagicMock()
        mock_app.name = "testapp"
        mock_app.project = "test-project"
        mock_config.app = mock_app
        mock_config.deployed = False

        # Mock logger to avoid logger config issues
        mock_logger = MagicMock()
        mock_logger.verbose = False
        mock_config.logger = mock_logger

        return mock_config

    def test_default_settings(self, mock_config):
        """Test settings initialization with default values."""
        with patch("acb.depends.depends.get", return_value=mock_config):
            settings = NosqlSettings()

        # Test Firestore-specific defaults
        assert settings.project_id == "test-project"  # Uses config.app.project
        assert settings.credentials_path is None
        assert settings.emulator_host is None

        # Test inherited defaults from NosqlBaseSettings
        assert settings.database == "testapp"
        assert settings.collection_prefix == "testapp_"

    def test_custom_settings(self, mock_config):
        """Test settings initialization with custom values."""
        with patch("acb.depends.depends.get", return_value=mock_config):
            settings = NosqlSettings(
                project_id="custom-project",
                credentials_path="/path/to/credentials.json",
                emulator_host="localhost:8080",
                ssl_enabled=True,
                ssl_cert_path="/path/to/cert.pem",
                ssl_key_path="/path/to/key.pem",
                ssl_ca_path="/path/to/ca.pem",
            )

        assert settings.project_id == "custom-project"
        assert settings.credentials_path == "/path/to/credentials.json"
        assert settings.emulator_host == "localhost:8080"
        assert settings.ssl_enabled is True
        assert settings.ssl_cert_path == "/path/to/cert.pem"
        assert settings.ssl_key_path == "/path/to/key.pem"
        assert settings.ssl_ca_path == "/path/to/ca.pem"

    @patch.dict("os.environ", {}, clear=True)
    def test_emulator_settings_without_ssl(self, mock_config):
        """Test emulator settings without SSL."""
        import os

        with patch("acb.depends.depends.get", return_value=mock_config):
            NosqlSettings(
                emulator_host="localhost:8080",
                ssl_enabled=False,
            )

        assert os.environ.get("FIRESTORE_EMULATOR_HOST") == "localhost:8080"
        assert os.environ.get("FIRESTORE_EMULATOR_SSL") == "false"

    @patch.dict("os.environ", {}, clear=True)
    def test_emulator_settings_with_ssl(self, mock_config):
        """Test emulator settings with SSL."""
        import os

        with patch("acb.depends.depends.get", return_value=mock_config):
            NosqlSettings(
                emulator_host="localhost:8080",
                ssl_enabled=True,
                ssl_cert_path="/cert.pem",
                ssl_key_path="/key.pem",
                ssl_ca_path="/ca.pem",
            )

        assert os.environ.get("FIRESTORE_EMULATOR_HOST") == "localhost:8080"
        assert os.environ.get("FIRESTORE_EMULATOR_SSL") == "true"
        assert os.environ.get("FIRESTORE_EMULATOR_SSL_CERT") == "/cert.pem"
        assert os.environ.get("FIRESTORE_EMULATOR_SSL_KEY") == "/key.pem"
        assert os.environ.get("FIRESTORE_EMULATOR_SSL_CA") == "/ca.pem"


class TestFirestoreNosql:
    """Test Firestore NoSQL adapter."""

    @pytest.fixture
    def mock_config(self):
        """Mock config for testing."""
        mock_config = MagicMock(spec=Config)

        # Mock app settings
        mock_app = MagicMock()
        mock_app.name = "testapp"
        mock_app.project = "test-project"
        mock_config.app = mock_app

        # Mock nosql settings
        mock_nosql = MagicMock(spec=NosqlSettings)
        mock_nosql.project_id = "test-project"
        mock_nosql.credentials_path = None
        mock_nosql.emulator_host = None
        mock_nosql.ssl_enabled = False
        mock_nosql.connect_timeout = 5.0
        mock_nosql.collection_prefix = "testapp_"
        mock_config.nosql = mock_nosql

        return mock_config

    @pytest.fixture
    def mock_emulator_config(self):
        """Mock config for emulator testing."""
        mock_config = MagicMock(spec=Config)

        # Mock app settings
        mock_app = MagicMock()
        mock_app.name = "testapp"
        mock_app.project = "test-project"
        mock_config.app = mock_app

        # Mock nosql settings for emulator
        mock_nosql = MagicMock(spec=NosqlSettings)
        mock_nosql.project_id = "test-project"
        mock_nosql.credentials_path = None
        mock_nosql.emulator_host = "localhost:8080"
        mock_nosql.ssl_enabled = True
        mock_nosql.connect_timeout = 5.0
        mock_nosql.collection_prefix = "testapp_"
        mock_config.nosql = mock_nosql

        return mock_config

    @pytest.fixture
    def firestore_adapter(self, mock_config):
        """Firestore NoSQL adapter for testing."""
        adapter = Nosql()
        adapter.config = mock_config
        adapter.logger = MagicMock()
        return adapter

    @pytest.fixture
    def firestore_emulator_adapter(self, mock_emulator_config):
        """Firestore NoSQL adapter with emulator for testing."""
        adapter = Nosql()
        adapter.config = mock_emulator_config
        adapter.logger = MagicMock()
        return adapter

    def test_adapter_initialization(self, firestore_adapter):
        """Test adapter initialization."""
        assert firestore_adapter._client is None
        assert firestore_adapter._transaction is None
        assert hasattr(firestore_adapter, "config")
        assert hasattr(firestore_adapter, "logger")

    def test_client_property(self, firestore_adapter):
        """Test client property creation."""
        with patch(
            "acb.adapters.nosql.firestore.firestore.Client", MockFirestoreClient
        ) as mock_client_class:
            mock_client = MockFirestoreClient()
            mock_client_class.return_value = mock_client

            client = firestore_adapter.client

            # Verify client was created with correct parameters
            mock_client_class.assert_called_once_with(project="test-project")
            assert client == mock_client

            # Test caching
            client2 = firestore_adapter.client
            assert client == client2
            assert mock_client_class.call_count == 1

    def test_client_property_with_credentials(self, firestore_adapter):
        """Test client property with credentials path."""
        firestore_adapter.config.nosql.credentials_path = "/path/to/creds.json"

        with patch(
            "acb.adapters.nosql.firestore.firestore.Client", MockFirestoreClient
        ) as mock_client_class:
            # Verify client was created with credentials
            mock_client_class.assert_called_once_with(
                project="test-project", credentials="/path/to/creds.json"
            )

    def test_db_property(self, firestore_adapter):
        """Test db property."""
        with patch.object(
            firestore_adapter, "client", MockFirestoreClient()
        ) as mock_client:
            db = firestore_adapter.db
            assert db == mock_client

    async def test_init_regular(self, firestore_adapter):
        """Test initialization for regular Firestore."""
        mock_client = MockFirestoreClient()
        mock_collection = MockCollectionReference("test")
        mock_client.collection.return_value = mock_collection

        with patch.object(firestore_adapter, "client", mock_client):
            await firestore_adapter.init()

            mock_client.collection.assert_called_once_with("test")
            firestore_adapter.logger.info.assert_any_call(
                "Initializing Firestore connection for project test-project"
            )
            firestore_adapter.logger.info.assert_any_call(
                "Firestore connection initialized successfully"
            )

    async def test_init_emulator(self, firestore_emulator_adapter):
        """Test initialization for Firestore emulator."""
        mock_client = MockFirestoreClient()
        mock_collection = MockCollectionReference("test")
        mock_client.collection.return_value = mock_collection

        with patch.object(firestore_emulator_adapter, "client", mock_client):
            await firestore_emulator_adapter.init()

            firestore_emulator_adapter.logger.info.assert_any_call(
                "Initializing Firestore emulator connection to localhost:8080 (SSL enabled)"
            )

    async def test_init_failure(self, firestore_adapter):
        """Test initialization failure handling."""
        mock_client = MockFirestoreClient()
        mock_client.collection.side_effect = Exception("Connection failed")

        with patch.object(firestore_adapter, "client", mock_client):
            with pytest.raises(Exception, match="Connection failed"):
                await firestore_adapter.init()

            firestore_adapter.logger.exception.assert_called_once()

    def test_get_collection_ref(self, firestore_adapter):
        """Test collection reference creation."""
        mock_client = MockFirestoreClient()
        mock_collection = MockCollectionReference("testapp_users")
        mock_client.collection.return_value = mock_collection

        with patch.object(firestore_adapter, "client", mock_client):
            collection_ref = firestore_adapter._get_collection_ref("users")

            mock_client.collection.assert_called_once_with("testapp_users")
            assert collection_ref == mock_collection

    def test_convert_to_dict_exists(self, firestore_adapter):
        """Test document conversion when document exists."""
        doc = MockDocument("doc123", {"name": "test", "value": 42}, exists=True)

        result = firestore_adapter._convert_to_dict(doc)

        expected = {"name": "test", "value": 42, "_id": "doc123"}
        assert result == expected

    def test_convert_to_dict_not_exists(self, firestore_adapter):
        """Test document conversion when document doesn't exist."""
        doc = MockDocument("doc123", exists=False)

        result = firestore_adapter._convert_to_dict(doc)

        assert result == {}

    def test_convert_to_dict_empty_data(self, firestore_adapter):
        """Test document conversion with empty data."""
        doc = MockDocument("doc123", None, exists=True)

        result = firestore_adapter._convert_to_dict(doc)

        expected = {"_id": "doc123"}
        assert result == expected

    def test_prepare_document_with_id(self, firestore_adapter):
        """Test document preparation with _id field."""
        document = {"_id": "doc123", "name": "test", "value": 42}

        result = firestore_adapter._prepare_document(document)

        expected = {"name": "test", "value": 42}
        assert result == expected
        # Verify original document is not modified
        assert document["_id"] == "doc123"

    def test_prepare_document_without_id(self, firestore_adapter):
        """Test document preparation without _id field."""
        document = {"name": "test", "value": 42}

        result = firestore_adapter._prepare_document(document)

        assert result == document

    async def test_find_simple(self, firestore_adapter):
        """Test find method with simple filter."""
        mock_client = MockFirestoreClient()
        mock_collection = MockCollectionReference("testapp_users")
        mock_client.collection.return_value = mock_collection

        # Mock query chain
        mock_query = MockQuery()
        mock_collection.where.return_value = mock_query

        # Mock documents
        docs = [
            MockDocument("doc1", {"name": "user1", "age": 25}),
            MockDocument("doc2", {"name": "user2", "age": 30}),
        ]
        mock_query.stream.return_value = docs

        with patch.object(firestore_adapter, "client", mock_client):
            results = await firestore_adapter.find("users", {"name": "user1"})

            # Verify query was built correctly
            mock_client.collection.assert_called_once_with("testapp_users")
            # Note: where() call verification would require mocking FieldFilter
            mock_query.stream.assert_called_once()

            # Verify results
            expected = [
                {"name": "user1", "age": 25, "_id": "doc1"},
                {"name": "user2", "age": 30, "_id": "doc2"},
            ]
            assert results == expected

    async def test_find_with_id_filter(self, firestore_adapter):
        """Test find method with _id filter."""
        mock_client = MockFirestoreClient()
        mock_collection = MockCollectionReference("testapp_users")
        mock_client.collection.return_value = mock_collection

        # Mock query without _id filter initially
        mock_query = MockQuery()
        mock_collection.where.return_value = mock_query

        # Mock documents (all docs first)
        docs = [
            MockDocument("doc1", {"name": "user1", "age": 25}),
            MockDocument("doc2", {"name": "user2", "age": 30}),
        ]
        mock_query.stream.return_value = docs

        with patch.object(firestore_adapter, "client", mock_client):
            results = await firestore_adapter.find(
                "users", {"_id": "doc1", "name": "user1"}
            )

            # Should filter results by _id after query
            expected = [{"name": "user1", "age": 25, "_id": "doc1"}]
            assert results == expected

    async def test_find_with_limit(self, firestore_adapter):
        """Test find method with limit."""
        mock_client = MockFirestoreClient()
        mock_collection = MockCollectionReference("testapp_users")
        mock_client.collection.return_value = mock_collection

        # Mock query chain
        mock_query = MockQuery()
        mock_collection.where.return_value = mock_query
        mock_query.limit.return_value = mock_query

        docs = [MockDocument("doc1", {"name": "user1"})]
        mock_query.stream.return_value = docs

        with patch.object(firestore_adapter, "client", mock_client):
            await firestore_adapter.find("users", {"name": "user1"}, limit=5)

            mock_query.limit.assert_called_once_with(5)

    async def test_find_with_order_by(self, firestore_adapter):
        """Test find method with order_by."""
        mock_client = MockFirestoreClient()
        mock_collection = MockCollectionReference("testapp_users")
        mock_client.collection.return_value = mock_collection

        # Mock query chain
        mock_query = MockQuery()
        mock_collection.where.return_value = mock_query
        mock_query.order_by.return_value = mock_query

        docs = [MockDocument("doc1", {"name": "user1"})]
        mock_query.stream.return_value = docs

        with (
            patch.object(firestore_adapter, "client", mock_client),
            patch("acb.adapters.nosql.firestore.firestore") as mock_firestore,
        ):
            # Mock Query constants
            mock_firestore.Query.ASCENDING = "ASCENDING"
            mock_firestore.Query.DESCENDING = "DESCENDING"

            await firestore_adapter.find(
                "users", {"name": "user1"}, order_by=["age", "-created_at"]
            )

            # Should call order_by twice
            assert mock_query.order_by.call_count == 2

    async def test_find_one_by_id(self, firestore_adapter):
        """Test find_one method with _id filter."""
        mock_client = MockFirestoreClient()
        mock_collection = MockCollectionReference("testapp_users")
        mock_doc_ref = MockDocumentReference("doc1")
        mock_client.collection.return_value = mock_collection
        mock_collection.document.return_value = mock_doc_ref

        # Mock document
        doc = MockDocument("doc1", {"name": "user1", "age": 25})
        mock_doc_ref.get.return_value = doc

        with patch.object(firestore_adapter, "client", mock_client):
            result = await firestore_adapter.find_one("users", {"_id": "doc1"})

            mock_collection.document.assert_called_once_with("doc1")
            mock_doc_ref.get.assert_called_once()

            expected = {"name": "user1", "age": 25, "_id": "doc1"}
            assert result == expected

    async def test_find_one_by_id_not_found(self, firestore_adapter):
        """Test find_one method with _id filter when document doesn't exist."""
        mock_client = MockFirestoreClient()
        mock_collection = MockCollectionReference("testapp_users")
        mock_doc_ref = MockDocumentReference("doc1")
        mock_client.collection.return_value = mock_collection
        mock_collection.document.return_value = mock_doc_ref

        # Mock non-existent document
        doc = MockDocument("doc1", exists=False)
        mock_doc_ref.get.return_value = doc

        with patch.object(firestore_adapter, "client", mock_client):
            result = await firestore_adapter.find_one("users", {"_id": "doc1"})

            assert result is None

    async def test_find_one_by_filter(self, firestore_adapter):
        """Test find_one method with regular filter."""
        with patch.object(firestore_adapter, "find") as mock_find:
            mock_find.return_value = [{"name": "user1", "_id": "doc1"}]

            result = await firestore_adapter.find_one("users", {"name": "user1"})

            mock_find.assert_called_once_with("users", {"name": "user1"}, limit=1)
            assert result == {"name": "user1", "_id": "doc1"}

    async def test_find_one_not_found(self, firestore_adapter):
        """Test find_one method when no documents found."""
        with patch.object(firestore_adapter, "find") as mock_find:
            mock_find.return_value = []

            result = await firestore_adapter.find_one("users", {"name": "nonexistent"})

            assert result is None

    async def test_insert_one_with_id(self, firestore_adapter):
        """Test insert_one method with _id specified."""
        mock_client = MockFirestoreClient()
        mock_collection = MockCollectionReference("testapp_users")
        mock_doc_ref = MockDocumentReference("doc1")
        mock_client.collection.return_value = mock_collection
        mock_collection.document.return_value = mock_doc_ref

        with patch.object(firestore_adapter, "client", mock_client):
            result = await firestore_adapter.insert_one(
                "users", {"_id": "doc1", "name": "user1"}
            )

            mock_collection.document.assert_called_once_with("doc1")
            mock_doc_ref.set.assert_called_once_with({"name": "user1"})
            assert result == "doc1"

    async def test_insert_one_without_id(self, firestore_adapter):
        """Test insert_one method without _id specified."""
        mock_client = MockFirestoreClient()
        mock_collection = MockCollectionReference("testapp_users")
        mock_doc_ref = MockDocumentReference("generated_id")
        mock_client.collection.return_value = mock_collection
        mock_collection.add.return_value = (None, mock_doc_ref)

        with patch.object(firestore_adapter, "client", mock_client):
            result = await firestore_adapter.insert_one("users", {"name": "user1"})

            mock_collection.add.assert_called_once_with({"name": "user1"})
            assert result == "generated_id"

    async def test_insert_many(self, firestore_adapter):
        """Test insert_many method."""
        mock_client = MockFirestoreClient()
        mock_collection = MockCollectionReference("testapp_users")
        mock_batch = MockBatch()
        mock_client.collection.return_value = mock_collection
        mock_client.batch.return_value = mock_batch

        # Mock document references
        mock_doc_ref1 = MockDocumentReference("doc1")
        mock_doc_ref2 = MockDocumentReference("generated_id")
        mock_collection.document.side_effect = [mock_doc_ref1, mock_doc_ref2]

        documents = [{"_id": "doc1", "name": "user1"}, {"name": "user2"}]

        with patch.object(firestore_adapter, "client", mock_client):
            result = await firestore_adapter.insert_many("users", documents)

            # Verify batch operations
            assert mock_batch.set.call_count == 2
            mock_batch.commit.assert_called_once()
            assert result == ["doc1", "generated_id"]

    async def test_update_one_success(self, firestore_adapter):
        """Test update_one method when document found."""
        mock_client = MockFirestoreClient()
        mock_collection = MockCollectionReference("testapp_users")
        mock_doc_ref = MockDocumentReference("doc1")
        mock_client.collection.return_value = mock_collection
        mock_collection.document.return_value = mock_doc_ref

        with patch.object(firestore_adapter, "find_one") as mock_find_one:
            mock_find_one.return_value = {"_id": "doc1", "name": "user1"}

            with patch.object(firestore_adapter, "client", mock_client):
                result = await firestore_adapter.update_one(
                    "users", {"name": "user1"}, {"$set": {"age": 25}}
                )

                mock_collection.document.assert_called_once_with("doc1")
                mock_doc_ref.update.assert_called_once_with({"age": 25})
                assert result == {"modified_count": 1}

    async def test_update_one_not_found(self, firestore_adapter):
        """Test update_one method when document not found."""
        with patch.object(firestore_adapter, "find_one") as mock_find_one:
            mock_find_one.return_value = None

            result = await firestore_adapter.update_one(
                "users", {"name": "nonexistent"}, {"$set": {"age": 25}}
            )

            assert result == {"modified_count": 0}

    async def test_update_one_without_set(self, firestore_adapter):
        """Test update_one method without $set operator."""
        mock_client = MockFirestoreClient()
        mock_collection = MockCollectionReference("testapp_users")
        mock_doc_ref = MockDocumentReference("doc1")
        mock_client.collection.return_value = mock_collection
        mock_collection.document.return_value = mock_doc_ref

        with patch.object(firestore_adapter, "find_one") as mock_find_one:
            mock_find_one.return_value = {"_id": "doc1", "name": "user1"}

            with patch.object(firestore_adapter, "client", mock_client):
                await firestore_adapter.update_one(
                    "users", {"name": "user1"}, {"age": 25}
                )

                mock_doc_ref.update.assert_called_once_with({"age": 25})

    async def test_update_many(self, firestore_adapter):
        """Test update_many method."""
        mock_client = MockFirestoreClient()
        mock_collection = MockCollectionReference("testapp_users")
        mock_batch = MockBatch()
        mock_client.collection.return_value = mock_collection
        mock_client.batch.return_value = mock_batch

        # Mock document references
        mock_doc_ref1 = MockDocumentReference("doc1")
        mock_doc_ref2 = MockDocumentReference("doc2")
        mock_collection.document.side_effect = [mock_doc_ref1, mock_doc_ref2]

        with patch.object(firestore_adapter, "find") as mock_find:
            mock_find.return_value = [
                {"_id": "doc1", "name": "user1"},
                {"_id": "doc2", "name": "user2"},
            ]

            with patch.object(firestore_adapter, "client", mock_client):
                result = await firestore_adapter.update_many(
                    "users", {"active": True}, {"$set": {"status": "verified"}}
                )

                # Verify batch operations
                assert mock_batch.update.call_count == 2
                mock_batch.commit.assert_called_once()
                assert result == {"modified_count": 2}

    async def test_update_many_no_docs(self, firestore_adapter):
        """Test update_many method when no documents found."""
        with patch.object(firestore_adapter, "find") as mock_find:
            mock_find.return_value = []

            result = await firestore_adapter.update_many(
                "users", {"active": False}, {"$set": {"status": "inactive"}}
            )

            assert result == {"modified_count": 0}

    async def test_delete_one_success(self, firestore_adapter):
        """Test delete_one method when document found."""
        mock_client = MockFirestoreClient()
        mock_collection = MockCollectionReference("testapp_users")
        mock_doc_ref = MockDocumentReference("doc1")
        mock_client.collection.return_value = mock_collection
        mock_collection.document.return_value = mock_doc_ref

        with patch.object(firestore_adapter, "find_one") as mock_find_one:
            mock_find_one.return_value = {"_id": "doc1", "name": "user1"}

            with patch.object(firestore_adapter, "client", mock_client):
                result = await firestore_adapter.delete_one("users", {"name": "user1"})

                mock_collection.document.assert_called_once_with("doc1")
                mock_doc_ref.delete.assert_called_once()
                assert result == {"deleted_count": 1}

    async def test_delete_one_not_found(self, firestore_adapter):
        """Test delete_one method when document not found."""
        with patch.object(firestore_adapter, "find_one") as mock_find_one:
            mock_find_one.return_value = None

            result = await firestore_adapter.delete_one(
                "users", {"name": "nonexistent"}
            )

            assert result == {"deleted_count": 0}

    async def test_delete_many(self, firestore_adapter):
        """Test delete_many method."""
        mock_client = MockFirestoreClient()
        mock_collection = MockCollectionReference("testapp_users")
        mock_batch = MockBatch()
        mock_client.collection.return_value = mock_collection
        mock_client.batch.return_value = mock_batch

        # Mock document references
        mock_doc_ref1 = MockDocumentReference("doc1")
        mock_doc_ref2 = MockDocumentReference("doc2")
        mock_collection.document.side_effect = [mock_doc_ref1, mock_doc_ref2]

        with patch.object(firestore_adapter, "find") as mock_find:
            mock_find.return_value = [
                {"_id": "doc1", "name": "user1"},
                {"_id": "doc2", "name": "user2"},
            ]

            with patch.object(firestore_adapter, "client", mock_client):
                result = await firestore_adapter.delete_many("users", {"active": False})

                # Verify batch operations
                assert mock_batch.delete.call_count == 2
                mock_batch.commit.assert_called_once()
                assert result == {"deleted_count": 2}

    async def test_delete_many_no_docs(self, firestore_adapter):
        """Test delete_many method when no documents found."""
        with patch.object(firestore_adapter, "find") as mock_find:
            mock_find.return_value = []

            result = await firestore_adapter.delete_many("users", {"active": False})

            assert result == {"deleted_count": 0}

    async def test_count(self, firestore_adapter):
        """Test count method."""
        with patch.object(firestore_adapter, "find") as mock_find:
            mock_find.return_value = [
                {"_id": "doc1", "name": "user1"},
                {"_id": "doc2", "name": "user2"},
                {"_id": "doc3", "name": "user3"},
            ]

            result = await firestore_adapter.count("users", {"active": True})

            mock_find.assert_called_once_with("users", {"active": True})
            assert result == 3

    async def test_count_no_filter(self, firestore_adapter):
        """Test count method without filter."""
        with patch.object(firestore_adapter, "find") as mock_find:
            mock_find.return_value = [{"_id": "doc1"}]

            result = await firestore_adapter.count("users")

            mock_find.assert_called_once_with("users", {})
            assert result == 1

    async def test_aggregate_match(self, firestore_adapter):
        """Test aggregate method with $match stage."""
        with patch.object(firestore_adapter, "find") as mock_find:
            mock_find.return_value = [
                {"_id": "doc1", "name": "user1", "age": 25, "active": True},
                {"_id": "doc2", "name": "user2", "age": 30, "active": True},
                {"_id": "doc3", "name": "user3", "age": 35, "active": False},
            ]

            pipeline = [{"$match": {"active": True}}]
            result = await firestore_adapter.aggregate("users", pipeline)

            expected = [
                {"_id": "doc1", "name": "user1", "age": 25, "active": True},
                {"_id": "doc2", "name": "user2", "age": 30, "active": True},
            ]
            assert result == expected

    async def test_aggregate_project(self, firestore_adapter):
        """Test aggregate method with $project stage."""
        with patch.object(firestore_adapter, "find") as mock_find:
            mock_find.return_value = [
                {"_id": "doc1", "name": "user1", "age": 25, "email": "user1@test.com"},
                {"_id": "doc2", "name": "user2", "age": 30, "email": "user2@test.com"},
            ]

            pipeline = [{"$project": {"name": 1, "age": 1}}]
            result = await firestore_adapter.aggregate("users", pipeline)

            expected = [{"name": "user1", "age": 25}, {"name": "user2", "age": 30}]
            assert result == expected

    async def test_aggregate_limit_skip(self, firestore_adapter):
        """Test aggregate method with $limit and $skip stages."""
        with patch.object(firestore_adapter, "find") as mock_find:
            mock_find.return_value = [
                {"_id": f"doc{i}", "name": f"user{i}"} for i in range(1, 6)
            ]

            pipeline = [{"$skip": 2}, {"$limit": 2}]
            result = await firestore_adapter.aggregate("users", pipeline)

            expected = [
                {"_id": "doc3", "name": "user3"},
                {"_id": "doc4", "name": "user4"},
            ]
            assert result == expected

    async def test_transaction_success(self, firestore_adapter):
        """Test transaction context manager success."""
        mock_client = MockFirestoreClient()
        mock_transaction = MockTransaction()
        mock_client.transaction.return_value = mock_transaction

        with patch.object(firestore_adapter, "client", mock_client):
            async with firestore_adapter.transaction():
                # Verify transaction was set
                assert firestore_adapter._transaction == mock_transaction

            # Verify transaction was cleaned up
            assert firestore_adapter._transaction is None
            mock_transaction.__enter__.assert_called_once()
            mock_transaction.__exit__.assert_called_once()

    async def test_transaction_failure(self, firestore_adapter):
        """Test transaction context manager with exception."""
        mock_client = MockFirestoreClient()
        mock_transaction = MockTransaction()
        mock_client.transaction.return_value = mock_transaction

        # Make transaction.__exit__ raise an exception
        mock_transaction.__exit__.side_effect = Exception("Transaction failed")

        with patch.object(firestore_adapter, "client", mock_client):
            with pytest.raises(Exception, match="Transaction failed"):
                async with firestore_adapter.transaction():
                    pass

            # Verify transaction was cleaned up even on failure
            assert firestore_adapter._transaction is None
            firestore_adapter.logger.exception.assert_called_once()

    def test_module_metadata(self):
        """Test module metadata constants."""
        from uuid import UUID

        from acb.adapters import AdapterStatus
        from acb.adapters.nosql.firestore import (
            MODULE_ID,
            MODULE_METADATA,
            MODULE_STATUS,
        )

        assert isinstance(MODULE_ID, UUID)
        assert MODULE_STATUS == AdapterStatus.STABLE
        assert MODULE_METADATA.name == "Firestore"
        assert MODULE_METADATA.category == "nosql"
        assert MODULE_METADATA.provider == "firestore"

    def test_depends_registration(self):
        """Test that Nosql class is registered with dependency injection."""
        from acb.depends import depends

        # This should not raise an exception if properly registered
        nosql_class = depends.get(Nosql)
        assert nosql_class is not None

    def test_inheritance_structure(self):
        """Test that Firestore nosql properly inherits from NosqlBase."""
        from acb.adapters.nosql._base import NosqlBase

        adapter = Nosql()

        # Test inheritance
        assert isinstance(adapter, NosqlBase)

        # Test that required methods exist
        assert hasattr(adapter, "client")
        assert hasattr(adapter, "db")
        assert hasattr(adapter, "init")
        assert hasattr(adapter, "find")
        assert hasattr(adapter, "find_one")
        assert hasattr(adapter, "insert_one")
        assert hasattr(adapter, "update_one")
        assert hasattr(adapter, "delete_one")

    async def test_comprehensive_workflow(self, firestore_adapter):
        """Test comprehensive Firestore workflow."""
        mock_client = MockFirestoreClient()
        mock_collection = MockCollectionReference("testapp_users")
        mock_doc_ref = MockDocumentReference("doc1")
        mock_batch = MockBatch()

        mock_client.collection.return_value = mock_collection
        mock_collection.document.return_value = mock_doc_ref
        mock_collection.add.return_value = (None, mock_doc_ref)
        mock_client.batch.return_value = mock_batch

        # Mock documents for find operations
        docs = [MockDocument("doc1", {"name": "user1", "age": 25})]
        mock_collection.stream.return_value = docs

        with patch.object(firestore_adapter, "client", mock_client):
            # Initialize adapter
            await firestore_adapter.init()
            mock_client.collection.assert_called()

            # Insert document
            doc_id = await firestore_adapter.insert_one(
                "users", {"name": "user1", "age": 25}
            )
            assert doc_id == "doc1"
            mock_collection.add.assert_called()

            # Find documents
            with patch.object(firestore_adapter, "find") as mock_find:
                mock_find.return_value = [{"_id": "doc1", "name": "user1", "age": 25}]
                results = await firestore_adapter.find("users", {"name": "user1"})
                assert len(results) == 1

            # Update document
            with patch.object(firestore_adapter, "find_one") as mock_find_one:
                mock_find_one.return_value = {"_id": "doc1", "name": "user1"}
                result = await firestore_adapter.update_one(
                    "users", {"_id": "doc1"}, {"$set": {"age": 26}}
                )
                assert result["modified_count"] == 1

            # Delete document
            with patch.object(firestore_adapter, "find_one") as mock_find_one:
                mock_find_one.return_value = {"_id": "doc1", "name": "user1"}
                result = await firestore_adapter.delete_one("users", {"_id": "doc1"})
                assert result["deleted_count"] == 1

            # Verify all operations completed successfully
            firestore_adapter.logger.info.assert_called()
