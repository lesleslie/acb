"""Tests for the MongoDB NoSQL adapter."""

from types import TracebackType
from typing import Any, Callable, Optional, Type
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pydantic import SecretStr
from acb.adapters.nosql.mongodb import Nosql as MongoDBNosql
from acb.adapters.nosql.mongodb import NosqlSettings as MongoDBSettings


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
            connection_string="mongodb://localhost:27017",
            database="test_db",
            username="test_user",
            password=SecretStr("test_password"),
        )

        assert settings.connection_string == "mongodb://localhost:27017"
        assert settings.database == "test_db"
        assert settings.username == "test_user"
        assert settings.password.get_secret_value() == "test_password"

        settings = MongoDBSettings(
            connection_string="mongodb://localhost:27017",
            database="test_db",
        )

        assert settings.connection_string == "mongodb://localhost:27017"
        assert settings.database == "test_db"
        assert settings.username is None
        assert settings.password is None


class TestMongoDB:
    @pytest.fixture
    def nosql(self, mock_async_context_manager: Any):
        nosql = MongoDBNosql()
        nosql.config = MagicMock()
        nosql.logger = MagicMock()

        mock_client = MagicMock(spec=AsyncIOMotorClient)
        mock_db = MagicMock(spec=AsyncIOMotorDatabase)
        mock_collection = MagicMock()

        type(nosql).client = PropertyMock(return_value=mock_client)
        type(nosql).db = PropertyMock(return_value=mock_db)

        mock_db.__getitem__.side_effect = lambda name: mock_collection
        mock_collection.find.return_value.to_list.return_value = [
            {"_id": "test_id", "data": "test_data"}
        ]
        mock_collection.find_one.return_value = {"_id": "test_id", "data": "test_data"}
        mock_collection.insert_one.return_value.inserted_id = "test_id"
        mock_client.start_session.return_value = mock_async_context_manager()

        return nosql

    def test_client_property(self, nosql: MongoDBNosql) -> None:
        assert nosql.client is not None

    def test_db_property(self, nosql: MongoDBNosql) -> None:
        assert nosql.db is not None

    @pytest.mark.asyncio
    async def test_init(self, nosql: MongoDBNosql) -> None:
        nosql.config.nosql.get.return_value = MongoDBSettings(
            connection_string="mongodb://localhost:27017",
            database="test_db",
        )

        with patch("motor.motor_asyncio.AsyncIOMotorClient") as mock_client_class:
            await nosql.init()
            assert mock_client_class.call_count == 1
            assert nosql.logger.info.call_count == 1

    @pytest.mark.asyncio
    async def test_init_error(self, nosql: MongoDBNosql) -> None:
        nosql.config.nosql.get.return_value = MongoDBSettings(
            connection_string="mongodb://localhost:27017",
            database="test_db",
        )

        with patch(
            "motor.motor_asyncio.AsyncIOMotorClient",
            side_effect=Exception("Connection error"),
        ):
            with pytest.raises(Exception) as excinfo:
                await nosql.init()
            assert "Connection error" in str(excinfo.value)
            assert nosql.logger.error.call_count == 1

    @pytest.mark.asyncio
    async def test_find(self, nosql: MongoDBNosql) -> None:
        result = await nosql.find("test_collection", {"key": "value"})

        assert nosql.db["test_collection"].find.call_count == 1
        assert len(result) == 1
        assert result[0]["data"] == "test_data"

    @pytest.mark.asyncio
    async def test_find_one(self, nosql: MongoDBNosql) -> None:
        result = await nosql.find_one("test_collection", {"key": "value"})

        assert nosql.db["test_collection"].find_one.call_count == 1
        assert result is not None
        assert result["data"] == "test_data"

    @pytest.mark.asyncio
    async def test_insert_one(self, nosql: MongoDBNosql) -> None:
        result = await nosql.insert_one("test_collection", {"data": "test_data"})

        assert nosql.db["test_collection"].insert_one.call_count == 1
        assert result == "test_id"

    @pytest.mark.asyncio
    async def test_transaction(self, nosql: MongoDBNosql) -> None:
        async with nosql.transaction():
            pass

        assert nosql.client.start_session is not None
        assert nosql.client.start_session.called  # type: ignore
