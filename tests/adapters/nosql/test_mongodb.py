"""Tests for the MongoDB NoSQL adapter."""

from contextlib import asynccontextmanager
from types import TracebackType
from typing import Any, Callable, Optional, Type
from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr
from acb.adapters.nosql.mongodb import Nosql as MongoDBNosql
from acb.adapters.nosql.mongodb import NosqlSettings as MongoDBSettings


@pytest.fixture
async def mock_async_context_manager() -> Callable[[Optional[Any]], Any]:
    class MockAsyncContextManager:
        def __init__(self, mock_obj: Optional[Any] = None) -> None:
            self.mock_obj = mock_obj or MagicMock()

        async def __aenter__(self) -> Any:
            return self.mock_obj

        async def __aexit__(
            self,
            exc_type: Optional[Type[BaseException]],
            exc_val: Optional[BaseException],
            exc_tb: Optional[TracebackType],
        ) -> None:
            pass

    def _mock_async_context_manager(
        mock_obj: Optional[Any] = None,
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

        assert (
            "mongodb://test_user:test_password@localhost:27017/test_db"
            in settings.connection_string
        )

        settings = MongoDBSettings(
            host=SecretStr("localhost"),
            database="test_db",
        )

        assert settings.host.get_secret_value() == "localhost"
        assert settings.port == 27017
        assert settings.database == "test_db"
        assert settings.user is None
        assert settings.password is None

        assert "mongodb://localhost:27017/test_db" in settings.connection_string


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

        async def mock_init():
            nosql.logger.info("Initializing MongoDB connection")
            nosql.logger.info("MongoDB connection initialized successfully")
            return None

        nosql.init = mock_init

        await nosql.init()
        assert nosql.logger.info.call_count == 2

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

        async def mock_init_error():
            nosql.logger.info("Initializing MongoDB connection")
            nosql.logger.error(
                "Failed to initialize MongoDB connection: Connection error"
            )
            raise Exception("Connection error")

        nosql.init = mock_init_error

        with pytest.raises(Exception) as excinfo:
            await nosql.init()
        assert "Connection error" in str(excinfo.value)
        assert nosql.logger.error.call_count == 1

        nosql.init = original_init

    @pytest.mark.asyncio
    async def test_find(self, nosql: MongoDBNosql) -> None:
        original_find = nosql.find

        async def mock_find(collection, filter, **kwargs):
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

        async def mock_find_one(collection, filter, **kwargs):
            assert collection == "test_collection"
            assert filter == {"test": "test"}
            return {"_id": "test_id", "data": "test_data"}

        nosql.find_one = mock_find_one

        result = await nosql.find_one("test_collection", {"test": "test"})
        assert result == {"_id": "test_id", "data": "test_data"}

        nosql.find_one = original_find_one

    @pytest.mark.asyncio
    async def test_insert_one(self, nosql: MongoDBNosql) -> None:
        original_insert_one = nosql.insert_one

        async def mock_insert_one(collection, document, **kwargs):
            assert collection == "test_collection"
            assert document == {"data": "test_data"}

            class MockInsertResult:
                @property
                def inserted_id(self) -> str:
                    return "test_id"

            return MockInsertResult()

        nosql.insert_one = mock_insert_one

        result = await nosql.insert_one("test_collection", {"data": "test_data"})
        assert result.inserted_id == "test_id"

        nosql.insert_one = original_insert_one

    @pytest.mark.asyncio
    async def test_transaction(self, nosql: MongoDBNosql) -> None:
        original_transaction = nosql.transaction

        @asynccontextmanager
        async def mock_transaction():
            nosql.logger.info("Starting transaction")
            yield
            nosql.logger.info("Ending transaction")

        nosql.transaction = mock_transaction

        async with nosql.transaction():
            pass

        assert nosql.logger.info.call_count == 2

        nosql.transaction = original_transaction
