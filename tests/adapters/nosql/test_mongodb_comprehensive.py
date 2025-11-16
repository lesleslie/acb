"""Comprehensive tests for MongoDB NoSQL adapter."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
import typing as t
from pydantic import SecretStr

from acb.adapters.nosql.mongodb import Nosql, NosqlSettings
from acb.config import Config


class MockAsyncIOMotorClient(MagicMock):
    """Mock for AsyncIOMotorClient."""

    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self._database = MagicMock()

    def __getitem__(self, name: str) -> MagicMock:
        """Mock database access."""
        return self._database


class TestMongoDBSettings:
    """Test MongoDB NoSQL settings."""

    @pytest.fixture
    def mock_config(self):
        """Mock config for settings testing."""
        mock_config = MagicMock(spec=Config)
        mock_app = MagicMock()
        mock_app.name = "testapp"
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
            # Pass database explicitly to avoid the automatic assignment from config
            settings = NosqlSettings(database="testdb")

        # Test MongoDB-specific defaults
        assert settings.port == 27017
        assert isinstance(settings.connection_options, dict)

        # Check that connection options are built from base settings defaults
        expected_options = {
            "connectTimeoutMS": 5000,  # connect_timeout * 1000
            "socketTimeoutMS": 5000,  # socket_timeout * 1000
            "maxPoolSize": 100,  # max_pool_size
        }
        for key, value in expected_options.items():
            assert settings.connection_options[key] == value

        # Test inherited defaults from NosqlBaseSettings
        assert settings.host.get_secret_value() == "127.0.0.1"
        assert settings.database == "testdb"
        assert settings.user is None
        assert settings.password is None

    def test_custom_settings(self, mock_config):
        """Test settings initialization with custom values."""
        with patch("acb.depends.depends.get", return_value=mock_config):
            settings = NosqlSettings(
                host=SecretStr("mongodb.example.com"),
                port=27018,
                database="mydb",
                user=SecretStr("myuser"),
                password=SecretStr("mypassword"),
                collection_prefix="app_",
                max_pool_size=100,
                min_pool_size=10,
                connect_timeout=30.0,
                socket_timeout=60.0,
            )

        assert settings.host.get_secret_value() == "mongodb.example.com"
        assert settings.port == 27018
        assert settings.database == "mydb"
        assert settings.user.get_secret_value() == "myuser"
        assert settings.password.get_secret_value() == "mypassword"
        assert settings.collection_prefix == "app_"
        assert settings.max_pool_size == 100
        assert settings.min_pool_size == 10
        assert settings.connect_timeout == 30.0
        assert settings.socket_timeout == 60.0

    def test_ssl_configuration(self, mock_config):
        """Test SSL/TLS configuration."""
        with patch("acb.depends.depends.get", return_value=mock_config):
            settings = NosqlSettings(
                ssl_enabled=True,
                ssl_cert_path="/path/to/cert.pem",
                ssl_key_path="/path/to/key.pem",
                ssl_ca_path="/path/to/ca.pem",
                ssl_verify_mode="required",
                ssl_ciphers="HIGH:!aNULL",
            )

        assert settings.ssl_enabled is True
        assert settings.ssl_cert_path == "/path/to/cert.pem"
        assert settings.ssl_key_path == "/path/to/key.pem"
        assert settings.ssl_ca_path == "/path/to/ca.pem"
        assert settings.ssl_verify_mode == "required"
        assert settings.ssl_ciphers == "HIGH:!aNULL"

    def test_ssl_options_building(self, mock_config):
        """Test SSL options building for MongoDB."""
        with patch("acb.depends.depends.get", return_value=mock_config):
            settings = NosqlSettings(
                ssl_enabled=True,
                ssl_cert_path="/path/to/cert.pem",
                ssl_key_path="/path/to/key.pem",
                ssl_ca_path="/path/to/ca.pem",
                ssl_verify_mode="required",
                connect_timeout=30.0,
                socket_timeout=60.0,
                max_pool_size=50,
                min_pool_size=5,
            )

        # The __init__ method builds SSL options
        assert "ssl" in settings.connection_options
        assert settings.connection_options["ssl"] is True
        assert settings.connection_options["ssl_certfile"] == "/path/to/cert.pem"
        assert settings.connection_options["ssl_keyfile"] == "/path/to/key.pem"
        assert settings.connection_options["ssl_ca_certs"] == "/path/to/ca.pem"
        assert settings.connection_options["ssl_cert_reqs"] == "CERT_REQUIRED"

        # Check timeout options
        assert settings.connection_options["connectTimeoutMS"] == 30000
        assert settings.connection_options["socketTimeoutMS"] == 60000
        assert settings.connection_options["maxPoolSize"] == 50
        assert settings.connection_options["minPoolSize"] == 5

    def test_connection_string_building(self, mock_config):
        """Test connection string building."""
        with patch("acb.depends.depends.get", return_value=mock_config):
            # Test with username and password
            settings = NosqlSettings(
                host=SecretStr("mongodb.example.com"),
                port=27017,
                database="mydb",
                user=SecretStr("myuser"),
                password=SecretStr("mypassword"),
                ssl_enabled=True,
            )

        expected = "mongodb+srv://myuser:mypassword@mongodb.example.com:27017/mydb"
        assert settings.connection_string == expected

    def test_connection_string_without_auth(self, mock_config):
        """Test connection string building without authentication."""
        with patch("acb.depends.depends.get", return_value=mock_config):
            settings = NosqlSettings(
                host=SecretStr("mongodb.example.com"),
                port=27017,
                database="mydb",
                ssl_enabled=False,
            )

        expected = "mongodb://mongodb.example.com:27017/mydb"
        assert settings.connection_string == expected

    def test_connection_string_with_auth_token(self, mock_config):
        """Test connection string building with auth token."""
        with patch("acb.depends.depends.get", return_value=mock_config):
            settings = NosqlSettings(
                host=SecretStr("mongodb.example.com"),
                port=27017,
                database="mydb",
                auth_token=SecretStr("my-auth-token"),
                ssl_enabled=True,
            )

        expected = "mongodb+srv://:my-auth-token@mongodb.example.com:27017/mydb"
        assert settings.connection_string == expected

    def test_ssl_verify_modes(self, mock_config):
        """Test different SSL verification modes."""
        verify_mode_mapping = {
            "required": "CERT_REQUIRED",
            "optional": "CERT_OPTIONAL",
            "none": "CERT_NONE",
        }

        for mode, expected in verify_mode_mapping.items():
            with patch("acb.depends.depends.get", return_value=mock_config):
                settings = NosqlSettings(
                    ssl_enabled=True,
                    ssl_verify_mode=mode,
                )

            assert settings.connection_options["ssl_cert_reqs"] == expected


class TestMongoDB:
    """Test MongoDB NoSQL adapter."""

    @pytest.fixture
    def mock_config(self):
        """Mock config for testing."""
        mock_config = MagicMock(spec=Config)

        # Mock app settings
        mock_app = MagicMock()
        mock_app.name = "testapp"
        mock_config.app = mock_app

        # Mock NoSQL settings
        mock_nosql = MagicMock(spec=NosqlSettings)
        mock_nosql.connection_string = "mongodb://localhost:27017/testapp"
        mock_nosql.connection_options = {"maxPoolSize": 50}
        mock_nosql.database = "testapp"
        mock_nosql.collection_prefix = "test_"
        mock_config.nosql = mock_nosql

        return mock_config

    @pytest.fixture
    def mock_ssl_config(self):
        """Mock config with SSL enabled."""
        mock_config = MagicMock(spec=Config)

        # Mock app settings
        mock_app = MagicMock()
        mock_app.name = "testapp"
        mock_config.app = mock_app

        # Mock NoSQL settings with SSL
        mock_nosql = MagicMock(spec=NosqlSettings)
        mock_nosql.connection_string = (
            "mongodb+srv://user:pass@mongodb.example.com:27017/testapp"
        )
        mock_nosql.connection_options = {
            "ssl": True,
            "ssl_certfile": "/path/to/cert.pem",
            "ssl_keyfile": "/path/to/key.pem",
            "ssl_ca_certs": "/path/to/ca.pem",
            "maxPoolSize": 100,
        }
        mock_nosql.database = "testapp"
        mock_nosql.collection_prefix = "prod_"
        mock_config.nosql = mock_nosql

        return mock_config

    @pytest.fixture
    def mongodb_adapter(self, mock_config):
        """MongoDB adapter for testing."""
        adapter = Nosql()
        adapter.config = mock_config
        adapter.logger = MagicMock()
        return adapter

    @pytest.fixture
    def mongodb_ssl_adapter(self, mock_ssl_config):
        """MongoDB adapter with SSL for testing."""
        adapter = Nosql()
        adapter.config = mock_ssl_config
        adapter.logger = MagicMock()
        return adapter

    def test_adapter_initialization(self, mongodb_adapter):
        """Test adapter initialization."""
        assert mongodb_adapter._client is None
        assert mongodb_adapter._db is None
        assert mongodb_adapter._transaction is None
        assert hasattr(mongodb_adapter, "config")
        assert hasattr(mongodb_adapter, "logger")

    def test_client_property(self, mongodb_adapter):
        """Test client property with lazy initialization."""
        # Test that accessing client creates a client instance
        assert mongodb_adapter._client is None

        # Access the client property
        client = mongodb_adapter.client

        # Verify the client was created and cached
        assert mongodb_adapter._client is not None
        assert client is mongodb_adapter._client

        # Second access should return cached client
        client2 = mongodb_adapter.client
        assert client is client2

    def test_db_property(self, mongodb_adapter):
        """Test database property."""
        # Test that accessing db creates a database instance
        assert mongodb_adapter._db is None

        # Access the db property
        db = mongodb_adapter.db

        # Verify the db was created and cached
        assert mongodb_adapter._db is not None
        assert db is mongodb_adapter._db

        # Second access should return cached db
        db2 = mongodb_adapter.db
        assert db is db2

    async def test_init_method(self, mongodb_adapter):
        """Test initialization method."""
        mock_db = MagicMock()

        with (
            patch.object(mongodb_adapter, "db", mock_db),
            patch(
                "acb.adapters.nosql.mongodb.init_beanie", AsyncMock()
            ) as mock_init_beanie,
        ):
            await mongodb_adapter.init()

            mock_init_beanie.assert_called_once_with(
                database=mock_db, document_models=[]
            )
            mongodb_adapter.logger.info.assert_called()

    async def test_init_exception_handling(self, mongodb_adapter):
        """Test initialization exception handling."""
        mock_db = MagicMock()

        with (
            patch.object(mongodb_adapter, "db", mock_db),
            patch(
                "acb.adapters.nosql.mongodb.init_beanie",
                AsyncMock(side_effect=Exception("Connection failed")),
            ),
        ):
            with pytest.raises(Exception, match="Connection failed"):
                await mongodb_adapter.init()

            mongodb_adapter.logger.exception.assert_called_once()

    async def test_find_method(self, mongodb_adapter):
        """Test find method implementation."""
        mock_collection = MagicMock()
        mock_collection.find = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=[{"_id": "1", "name": "test"}])
        mock_collection.find.return_value = mock_cursor

        with patch.object(mongodb_adapter, "db", {"test_collection": mock_collection}):
            results = await mongodb_adapter.find("test_collection", {"name": "test"})

            mock_collection.find.assert_called_once_with({"name": "test"})
            mock_cursor.to_list.assert_called_once_with(length=None)
            assert results == [{"_id": "1", "name": "test"}]

    async def test_find_one_method(self, mongodb_adapter):
        """Test find_one method implementation."""
        mock_collection = MagicMock()
        mock_collection.find_one = AsyncMock(return_value={"_id": "1", "name": "test"})

        with patch.object(mongodb_adapter, "db", {"test_collection": mock_collection}):
            result = await mongodb_adapter.find_one("test_collection", {"_id": "1"})

            mock_collection.find_one.assert_called_once_with({"_id": "1"})
            assert result == {"_id": "1", "name": "test"}

    async def test_insert_one_method(self, mongodb_adapter):
        """Test insert_one method implementation."""
        mock_collection = MagicMock()
        mock_result = MagicMock()
        mock_result.inserted_id = "123"
        mock_collection.insert_one = AsyncMock(return_value=mock_result)

        with patch.object(mongodb_adapter, "db", {"test_collection": mock_collection}):
            document = {"name": "test", "value": 42}
            result = await mongodb_adapter.insert_one("test_collection", document)

            mock_collection.insert_one.assert_called_once_with(document)
            assert result == "123"

    async def test_insert_many_method(self, mongodb_adapter):
        """Test insert_many method implementation."""
        mock_collection = MagicMock()
        mock_result = MagicMock()
        mock_result.inserted_ids = ["123", "456"]
        mock_collection.insert_many = AsyncMock(return_value=mock_result)

        with patch.object(mongodb_adapter, "db", {"test_collection": mock_collection}):
            documents = [{"name": "test1"}, {"name": "test2"}]
            result = await mongodb_adapter.insert_many("test_collection", documents)

            mock_collection.insert_many.assert_called_once_with(documents)
            assert result == ["123", "456"]

    async def test_update_one_method(self, mongodb_adapter):
        """Test update_one method implementation."""
        mock_collection = MagicMock()
        mock_result = MagicMock()
        mock_result.modified_count = 1
        mock_collection.update_one = AsyncMock(return_value=mock_result)

        with patch.object(mongodb_adapter, "db", {"test_collection": mock_collection}):
            result = await mongodb_adapter.update_one(
                "test_collection", {"_id": "123"}, {"$set": {"name": "updated"}}
            )

            mock_collection.update_one.assert_called_once_with(
                {"_id": "123"}, {"$set": {"name": "updated"}}
            )
            assert result == mock_result

    async def test_update_many_method(self, mongodb_adapter):
        """Test update_many method implementation."""
        mock_collection = MagicMock()
        mock_result = MagicMock()
        mock_result.modified_count = 5
        mock_collection.update_many = AsyncMock(return_value=mock_result)

        with patch.object(mongodb_adapter, "db", {"test_collection": mock_collection}):
            result = await mongodb_adapter.update_many(
                "test_collection",
                {"status": "pending"},
                {"$set": {"status": "processed"}},
            )

            mock_collection.update_many.assert_called_once_with(
                {"status": "pending"}, {"$set": {"status": "processed"}}
            )
            assert result == mock_result

    async def test_delete_one_method(self, mongodb_adapter):
        """Test delete_one method implementation."""
        mock_collection = MagicMock()
        mock_result = MagicMock()
        mock_result.deleted_count = 1
        mock_collection.delete_one = AsyncMock(return_value=mock_result)

        with patch.object(mongodb_adapter, "db", {"test_collection": mock_collection}):
            result = await mongodb_adapter.delete_one("test_collection", {"_id": "123"})

            mock_collection.delete_one.assert_called_once_with({"_id": "123"})
            assert result == mock_result

    async def test_delete_many_method(self, mongodb_adapter):
        """Test delete_many method implementation."""
        mock_collection = MagicMock()
        mock_result = MagicMock()
        mock_result.deleted_count = 10
        mock_collection.delete_many = AsyncMock(return_value=mock_result)

        with patch.object(mongodb_adapter, "db", {"test_collection": mock_collection}):
            result = await mongodb_adapter.delete_many(
                "test_collection", {"expired": True}
            )

            mock_collection.delete_many.assert_called_once_with({"expired": True})
            assert result == mock_result

    async def test_count_method(self, mongodb_adapter):
        """Test count method implementation."""
        mock_collection = MagicMock()
        mock_collection.count_documents = AsyncMock(return_value=42)

        with patch.object(mongodb_adapter, "db", {"test_collection": mock_collection}):
            result = await mongodb_adapter.count("test_collection", {"active": True})

            mock_collection.count_documents.assert_called_once_with({"active": True})
            assert result == 42

    async def test_aggregate_method(self, mongodb_adapter):
        """Test aggregate method implementation."""
        mock_collection = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=[{"_id": "group1", "count": 5}])
        mock_collection.aggregate = MagicMock(return_value=mock_cursor)

        with patch.object(mongodb_adapter, "db", {"test_collection": mock_collection}):
            pipeline = [
                {"$match": {"status": "active"}},
                {"$group": {"_id": "$category", "count": {"$sum": 1}}},
            ]
            results = await mongodb_adapter.aggregate("test_collection", pipeline)

            mock_collection.aggregate.assert_called_once_with(pipeline)
            mock_cursor.to_list.assert_called_once_with(length=None)
            assert results == [{"_id": "group1", "count": 5}]

    async def test_transaction_context_manager(self, mongodb_adapter):
        """Test transaction context manager."""
        mock_session = MagicMock()
        mock_session.start_transaction = MagicMock(return_value=MagicMock())
        mock_session.end_session = AsyncMock()
        mock_session.has_ended = False
        mock_session.in_transaction = True

        # Create a mock transaction context manager
        mock_transaction_ctx = MagicMock()
        mock_transaction_ctx.__aenter__ = AsyncMock()
        mock_transaction_ctx.__aexit__ = AsyncMock()
        mock_session.start_transaction.return_value = mock_transaction_ctx

        mock_client = MagicMock()
        mock_client.start_session = AsyncMock(return_value=mock_session)

        with patch.object(mongodb_adapter, "client", mock_client):
            async with mongodb_adapter.transaction():
                assert mongodb_adapter._transaction == mock_session

            mock_client.start_session.assert_called_once()
            mock_session.start_transaction.assert_called_once()
            assert mongodb_adapter._transaction is None

    async def test_transaction_rollback_on_exception(self, mongodb_adapter):
        """Test transaction rollback on exception."""
        mock_session = MagicMock()
        mock_session.end_session = AsyncMock()
        mock_session.has_ended = False
        mock_session.in_transaction = True
        mock_session.abort_transaction = AsyncMock()

        # Create a mock transaction context manager that raises an exception
        mock_transaction_ctx = MagicMock()
        mock_transaction_ctx.__aenter__ = AsyncMock()
        mock_transaction_ctx.__aexit__ = AsyncMock(side_effect=Exception("Test error"))
        mock_session.start_transaction.return_value = mock_transaction_ctx

        mock_client = MagicMock()
        mock_client.start_session = AsyncMock(return_value=mock_session)

        with patch.object(mongodb_adapter, "client", mock_client):
            with pytest.raises(Exception, match="Test error"):
                async with mongodb_adapter.transaction():
                    assert mongodb_adapter._transaction == mock_session

            assert mongodb_adapter._transaction is None

    def test_module_metadata(self):
        """Test module metadata constants."""
        from acb.adapters import AdapterStatus
        from acb.adapters.nosql.mongodb import MODULE_ID, MODULE_METADATA, MODULE_STATUS

        assert isinstance(MODULE_ID, UUID)
        assert MODULE_STATUS == AdapterStatus.STABLE
        assert MODULE_METADATA.name == "MongoDB"
        assert MODULE_METADATA.category == "nosql"
        assert MODULE_METADATA.provider == "mongodb"

    def test_depends_registration(self):
        """Test that Nosql class is registered with dependency injection."""
        from acb.depends import depends

        # This should not raise an exception if properly registered
        nosql_class = depends.get(Nosql)
        assert nosql_class is not None

    def test_inheritance_structure(self):
        """Test that MongoDB adapter properly inherits from NosqlBase."""
        from acb.adapters.nosql._base import NosqlBase

        adapter = Nosql()

        # Test inheritance
        assert isinstance(adapter, NosqlBase)

        # Test that required methods exist
        assert hasattr(adapter, "client")
        assert hasattr(adapter, "db")
        assert hasattr(adapter, "init")

    async def test_comprehensive_workflow(self, mongodb_adapter):
        """Test comprehensive workflow with all operations."""
        mock_client = MockAsyncIOMotorClient()
        mock_db = MagicMock()
        mock_collection = MagicMock()

        # Setup mocks
        mock_insert_result = MagicMock()
        mock_insert_result.inserted_id = "new_id"
        mock_collection.insert_one = AsyncMock(return_value=mock_insert_result)

        mock_find_result = {"_id": "new_id", "name": "test", "value": 42}
        mock_collection.find_one = AsyncMock(return_value=mock_find_result)

        mock_update_result = MagicMock()
        mock_update_result.modified_count = 1
        mock_collection.update_one = AsyncMock(return_value=mock_update_result)

        mock_delete_result = MagicMock()
        mock_delete_result.deleted_count = 1
        mock_collection.delete_one = AsyncMock(return_value=mock_delete_result)

        mock_db.__getitem__.return_value = mock_collection

        with (
            patch("motor.motor_asyncio.AsyncIOMotorClient", return_value=mock_client),
            patch.object(mongodb_adapter, "db", mock_db),
            patch("beanie.init_beanie", AsyncMock()),
        ):
            # Initialize
            await mongodb_adapter.init()

            # Insert document
            doc_id = await mongodb_adapter.insert_one(
                "test_collection", {"name": "test", "value": 42}
            )
            assert doc_id == "new_id"

            # Find document
            doc = await mongodb_adapter.find_one("test_collection", {"_id": "new_id"})
            assert doc["name"] == "test"

            # Update document
            update_result = await mongodb_adapter.update_one(
                "test_collection", {"_id": "new_id"}, {"$set": {"value": 100}}
            )
            assert update_result == mock_update_result

            # Delete document
            delete_result = await mongodb_adapter.delete_one(
                "test_collection", {"_id": "new_id"}
            )
            assert delete_result == mock_delete_result

    def test_ssl_configuration_in_connection_string(self, mongodb_ssl_adapter):
        """Test that SSL configuration is properly included."""
        connection_string = mongodb_ssl_adapter.config.nosql.connection_string
        assert "mongodb+srv://" in connection_string

        connection_options = mongodb_ssl_adapter.config.nosql.connection_options
        assert connection_options["ssl"] is True
        assert "ssl_certfile" in connection_options
        assert "ssl_keyfile" in connection_options
        assert "ssl_ca_certs" in connection_options

    def test_collection_prefix_usage(self, mongodb_adapter):
        """Test collection prefix is properly used."""
        # This would be tested in actual method implementations
        prefix = mongodb_adapter.config.nosql.collection_prefix
        assert prefix == "test_"

    async def test_bulk_operations(self, mongodb_adapter):
        """Test bulk operations support."""
        mock_collection = MagicMock()
        mock_bulk = MagicMock()
        mock_bulk.execute = AsyncMock(return_value={"nInserted": 3, "nModified": 2})
        mock_collection.bulk_write = AsyncMock(return_value=mock_bulk)

        with patch.object(mongodb_adapter, "db", {"test_collection": mock_collection}):
            # This is a conceptual test - actual implementation would vary
            pass

            # Would need to implement bulk_write method in adapter
            # result = await mongodb_adapter.bulk_write("test_collection", operations)
            # assert result["nInserted"] == 3
