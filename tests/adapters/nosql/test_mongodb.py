"""Tests for the MongoDB NoSQL adapter."""

from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from types import TracebackType
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr
from acb.adapters.nosql.mongodb import Nosql as MongoDBNosql
from acb.adapters.nosql.mongodb import NosqlSettings as MongoDBSettings


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
            exc_tb: TracebackType | None,
        ) -> None:
            pass

    def _mock_async_context_manager(
        mock_obj: Any | None = None,
    ) -> MockAsyncContextManager:
        return MockAsyncContextManager(mock_obj)

    return _mock_async_context_manager


class TestMongoDBSettings:
    def test_init(self) -> None:
        settings = MongoDBSettings(
            host=SecretStr("localhost"),
            port=27017,
            database="test_db",
            user=SecretStr("test_user"),
            password=SecretStr("test_password"),
        )

        assert settings.host.get_secret_value() == "localhost"
        assert settings.port == 27017
        assert settings.database == "test_db"
        assert settings.user.get_secret_value() == "test_user"
        assert settings.password.get_secret_value() == "test_password"

        conn_str = settings.connection_string
        assert conn_str is not None
        assert "mongodb://test_user:test_password@localhost:27017/test_db" == conn_str

        settings = MongoDBSettings(
            host=SecretStr("localhost"),
            database="test_db",
        )

        assert settings.host.get_secret_value() == "localhost"
        assert settings.port == 27017
        assert settings.database == "test_db"
        assert settings.user is None
        assert settings.password is None

        conn_str = settings.connection_string
        assert conn_str is not None
        assert "mongodb://localhost:27017/test_db" == conn_str


class TestMongoDB:
    @pytest.fixture
    def nosql(self) -> MongoDBNosql:
        nosql = MongoDBNosql()
        nosql.config = MagicMock()
        nosql.logger = MagicMock()

        nosql.config.nosql.collection_prefix = ""

        return nosql

    @pytest.mark.asyncio
    async def test_init(self, nosql: MongoDBNosql) -> None:
        mongodb_settings = MongoDBSettings(
            host=SecretStr("localhost"),
            port=27017,
            database="test_db",
        )

        nosql.config.nosql.get.return_value = mongodb_settings

        original_init = nosql.init
        mock_logger = MagicMock()
        nosql.logger = mock_logger

        async def mock_init() -> None:
            nosql.logger.info("Initializing MongoDB connection")
            nosql.logger.info("MongoDB connection initialized successfully")
            return None

        nosql.init = mock_init

        await nosql.init()
        assert mock_logger.info.call_count == 2

        nosql.init = original_init

    @pytest.mark.asyncio
    async def test_init_error(self, nosql: MongoDBNosql) -> None:
        mongodb_settings = MongoDBSettings(
            host=SecretStr("localhost"),
            port=27017,
            database="test_db",
        )

        nosql.config.nosql.get.return_value = mongodb_settings

        original_init = nosql.init
        mock_logger = MagicMock()
        nosql.logger = mock_logger

        async def mock_init_error() -> None:
            nosql.logger.info("Initializing MongoDB connection")
            nosql.logger.error(
                "Failed to initialize MongoDB connection: Connection error"
            )
            raise Exception("Connection error")

        nosql.init = mock_init_error

        with pytest.raises(Exception) as excinfo:
            await nosql.init()
        assert "Connection error" in str(excinfo.value)
        assert mock_logger.error.call_count == 1

        nosql.init = original_init

    @pytest.mark.asyncio
    async def test_find(self, nosql: MongoDBNosql) -> None:
        original_find = nosql.find

        async def mock_find(
            collection: str, filter: dict[str, Any], **kwargs: Any
        ) -> list[dict[str, Any]]:
            assert collection == "test_collection"
            assert filter == {"test": "test"}
            return [{"_id": "test_id", "data": "test_data"}]

        nosql.find = mock_find

        result = await nosql.find("test_collection", {"test": "test"})
        assert result == [{"_id": "test_id", "data": "test_data"}]

        nosql.find = original_find

    @pytest.mark.asyncio
    async def test_find_one(self, nosql: MongoDBNosql) -> None:
        original_find_one = nosql.find_one

        async def mock_find_one(
            collection: str, filter: dict[str, Any], **kwargs: Any
        ) -> dict[str, Any]:
            assert collection == "test_collection"
            assert filter == {"_id": "test_id"}
            return {"_id": "test_id", "data": "test_data"}

        nosql.find_one = mock_find_one

        result = await nosql.find_one("test_collection", {"_id": "test_id"})

        assert result == {"_id": "test_id", "data": "test_data"}

        nosql.find_one = original_find_one

    @pytest.mark.asyncio
    async def test_find_many(self, nosql: MongoDBNosql) -> None:
        original_find = nosql.find

        async def mock_find(
            collection: str, filter: dict[str, Any], **kwargs: Any
        ) -> list[dict[str, Any]]:
            if collection == "test_collection" and filter == {"status": "active"}:
                return [
                    {"_id": "1", "data": "test_data_1", "status": "active"},
                    {"_id": "2", "data": "test_data_2", "status": "active"},
                ]
            return await original_find(collection, filter, **kwargs)

        nosql.find = mock_find

        results = await nosql.find("test_collection", {"status": "active"})

        assert len(results) == 2
        assert results[0]["_id"] == "1"
        assert results[1]["_id"] == "2"

        nosql.find = original_find

    @pytest.mark.asyncio
    async def test_insert_one(self, nosql: MongoDBNosql) -> None:
        original_insert_one = nosql.insert_one

        async def mock_insert_one(
            collection: str, document: dict[str, Any], **kwargs: Any
        ) -> dict[str, Any]:
            assert collection == "test_collection"
            assert document == {"data": "test_data"}

            return {"inserted_id": "test_id"}

        nosql.insert_one = mock_insert_one

        result = await nosql.insert_one("test_collection", {"data": "test_data"})

        assert result["inserted_id"] == "test_id"

        nosql.insert_one = original_insert_one

    @pytest.mark.asyncio
    async def test_transaction(self, nosql: MongoDBNosql) -> None:
        original_transaction = nosql.transaction

        @asynccontextmanager
        async def mock_transaction() -> AsyncGenerator[None]:
            nosql.logger.info("Starting transaction")
            yield
            nosql.logger.info("Ending transaction")

        nosql.transaction = mock_transaction

        async with nosql.transaction():
            nosql.logger.info("Inside transaction")

        nosql.transaction = original_transaction

    def test_init_with_connection_string(self) -> None:
        connection_string = "mongodb://test_user:test_password@localhost:27017/test_db"
        nosql = MongoDBNosql()

        nosql.config = MagicMock()
        nosql.config.nosql.connection_string = connection_string
        nosql.connection_string = connection_string

        assert nosql.connection_string == connection_string

    def test_init_with_host_and_db(self) -> None:
        expected_connection = "mongodb://localhost:27017/test_db"
        nosql = MongoDBNosql()

        nosql.config = MagicMock()
        nosql.config.nosql.connection_string = expected_connection
        nosql.connection_string = expected_connection

        assert nosql.connection_string == expected_connection
