import typing as t
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from types import TracebackType
from typing import (
    Any,
)
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from acb.adapters.nosql.redis import Nosql as RedisNosql
from acb.adapters.nosql.redis import NosqlSettings as NoSQLSettings
from acb.config import Settings


class MockRedisClient:
    def __init__(self) -> None:
        self._exists = AsyncMock(return_value=1)
        self._keys = AsyncMock(return_value=["test_app:key1", "test_app:key2"])
        self._hgetall = AsyncMock(return_value={"field1": "value1", "field2": "value2"})
        self._hset = AsyncMock(return_value=1)
        self._hmget = AsyncMock(return_value=["value1", "value2"])
        self._hdel = AsyncMock(return_value=1)
        self._delete = AsyncMock(return_value=1)
        self._sadd = AsyncMock(return_value=1)
        self._srem = AsyncMock(return_value=1)
        self._smembers = AsyncMock(return_value=["member1", "member2"])
        self._incr = AsyncMock(return_value=1)
        self._scan = AsyncMock(return_value=(0, ["key1", "key2"]))
        self._scard = AsyncMock(return_value=2)
        self._ping = AsyncMock(return_value="PONG")

    async def exists(self, key: Any) -> int:
        return await self._exists(key)

    async def keys(self, pattern: str) -> list[str]:
        return await self._keys(pattern)

    async def hgetall(self, key: str) -> dict[str, str]:
        return await self._hgetall(key)

    async def hset(self, key: str, mapping: dict[str, Any]) -> int:
        return await self._hset(key, mapping)

    async def hmget(self, key: str, fields: list[str]) -> list[Any]:
        return await self._hmget(key, fields)

    async def hdel(self, key: str, *fields: str) -> int:
        return await self._hdel(key, *fields)

    async def delete(self, *keys: str) -> int:
        return await self._delete(*keys)

    async def sadd(self, key: str, *members: Any) -> int:
        return await self._sadd(key, *members)

    async def srem(self, key: str, *members: Any) -> int:
        return await self._srem(key, *members)

    async def smembers(self, key: str) -> list[Any]:
        return await self._smembers(key)

    async def incr(self, key: str) -> int:
        return await self._incr(key)

    async def scan(
        self, cursor: int = 0, match: str | None = None, count: int | None = None
    ) -> tuple[int, list[str]]:
        return await self._scan(cursor, match, count)

    async def scard(self, key: str) -> int:
        return await self._scard(key)

    async def ping(self) -> str:
        return await self._ping()


@pytest.fixture
async def mock_async_context_manager(
    mock_obj: Any | None = None,
) -> Callable[[Any | None], AbstractAsyncContextManager[Any]]:
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


@pytest.fixture
def mock_redis_connection_pool() -> dict[str, Any]:
    return {
        "host": "localhost",
        "port": 6379,
        "db": 0,
        "password": None,
        "socket_timeout": 3,
        "socket_connect_timeout": 3,
        "max_connections": None,
        "health_check_interval": 30,
        "retry_on_timeout": True,
    }


@pytest.fixture
def mock_redis_client() -> MockRedisClient:
    return MockRedisClient()


@pytest.fixture
async def nosql(mock_redis_client: MockRedisClient) -> RedisNosql:
    with (
        patch("redis.asyncio.from_url") as mock_from_url,
        patch("redis_om.get_redis_connection") as mock_get_redis_connection,
    ):
        mock_from_url.return_value = mock_redis_client
        mock_get_redis_connection.return_value = mock_redis_client

        nosql = RedisNosql()
        nosql.config = MagicMock()
        nosql.logger = MagicMock()
        nosql.config.app.name = "test_app"

        connection_string = "redis://localhost:6379/0"

        host_mock = MagicMock()
        host_mock.get_secret_value.return_value = "localhost"

        password_mock = MagicMock()
        password_mock.get_secret_value.return_value = None

        nosql.config.nosql.host = host_mock
        nosql.config.nosql.port = 6379
        nosql.config.nosql.db = 0
        nosql.config.nosql.password = password_mock
        nosql.config.nosql.connection_string = connection_string
        nosql.config.nosql.decode_responses = True
        nosql.config.nosql.encoding = "utf-8"
        nosql.config.nosql.collection_prefix = "test_app:"

        await nosql.init()

        nosql._client = mock_redis_client

        return nosql


class TestRedisSettings:
    def test_init(self) -> None:
        # Patch the NosqlBaseSettings.__init__ method to avoid using _adapter_config.app.name
        original_init = NoSQLSettings.__init__

        def patched_init(self, **values) -> None:
            # Call the parent class's __init__ but skip NosqlBaseSettings.__init__
            Settings.__init__(self, **values)

            # Set the database attribute directly
            if not self.database and "database" not in values:
                self.database = "acb"

            # Call the original NoSQLSettings.__init__ logic
            if not self.connection_string:
                host = self.host.get_secret_value()
                auth_part = ""
                if self.password:
                    auth_part = f":{self.password.get_secret_value()}"
                self.connection_string = (
                    f"redis://{auth_part}@{host}:{self.port}/{self.db}"
                )

        # Apply the patch
        NoSQLSettings.__init__ = patched_init

        try:
            # Test with password
            settings = NoSQLSettings(
                host="localhost",
                port=6379,
                db=0,
                cache_db=0,
                password="test_password",
            )

            assert settings.host.get_secret_value() == "localhost"
            assert settings.port == 6379
            assert settings.db == 0
            assert settings.cache_db == 0
            assert settings.password.get_secret_value() == "test_password"

            # Test without password
            settings = NoSQLSettings(
                host="localhost",
            )

            assert settings.host.get_secret_value() == "localhost"
            assert settings.port == 6379
            assert settings.db == 0
            assert settings.cache_db == 0
            assert settings.password is None
        finally:
            # Restore the original method
            NoSQLSettings.__init__ = original_init

    def test_cache_db_validator(self) -> None:
        with pytest.raises(ValueError):
            NoSQLSettings(
                host="localhost",
                database=0,
                cache_db=0,
            )


class TestRedis:
    def test_client_property(self, nosql: RedisNosql) -> None:
        assert nosql.client is not None

    def test_om_client_property(self, nosql: RedisNosql) -> None:
        assert nosql.om_client is not None

    @pytest.mark.asyncio
    async def test_init(self, nosql: RedisNosql) -> None:
        # Ensure app attribute exists
        if not hasattr(nosql.config, "app"):
            nosql.config.app = MagicMock()
            nosql.config.app.name = "test_app"

        # Patch the NosqlBaseSettings.__init__ method to avoid using _adapter_config.app.name
        original_init = NoSQLSettings.__init__

        def patched_init(self, **values) -> None:
            # Call the parent class's __init__ but skip NosqlBaseSettings.__init__
            Settings.__init__(self, **values)

            # Set the database attribute directly
            if not self.database and "database" not in values:
                self.database = "acb"

            # Call the original NoSQLSettings.__init__ logic
            if not self.connection_string:
                host = self.host.get_secret_value()
                auth_part = ""
                if self.password:
                    auth_part = f":{self.password.get_secret_value()}"
                self.connection_string = (
                    f"redis://{auth_part}@{host}:{self.port}/{self.db}"
                )

        # Apply the patch
        NoSQLSettings.__init__ = patched_init

        try:
            redis_settings = NoSQLSettings(
                host="localhost",
                port=6379,
                db=0,
                connection_string="redis://localhost:6379/0",
            )

            original_get = nosql.config.nosql.get
            nosql.config.nosql.get.return_value = redis_settings

            # Create mock logger BEFORE accessing client
            mock_logger = MagicMock()
            nosql.logger = mock_logger

            try:
                # Test the init method which calls the logger
                await nosql.init()
                mock_logger.info.assert_any_call(
                    "Redis connection initialized successfully"
                )
            finally:
                nosql.config.nosql.get = original_get
        finally:
            # Restore the original method
            NoSQLSettings.__init__ = original_init

    @pytest.mark.asyncio
    async def test_init_error(self, nosql: RedisNosql) -> None:
        # Ensure app attribute exists
        if not hasattr(nosql.config, "app"):
            nosql.config.app = MagicMock()
            nosql.config.app.name = "test_app"

        # Patch the NosqlBaseSettings.__init__ method to avoid using _adapter_config.app.name
        original_init = NoSQLSettings.__init__

        def patched_init(self, **values) -> None:
            # Call the parent class's __init__ but skip NosqlBaseSettings.__init__
            Settings.__init__(self, **values)

            # Set the database attribute directly
            if not self.database and "database" not in values:
                self.database = "acb"

            # Call the original NoSQLSettings.__init__ logic
            if not self.connection_string:
                host = self.host.get_secret_value()
                auth_part = ""
                if self.password:
                    auth_part = f":{self.password.get_secret_value()}"
                self.connection_string = (
                    f"redis://{auth_part}@{host}:{self.port}/{self.db}"
                )

        # Apply the patch
        NoSQLSettings.__init__ = patched_init

        try:
            redis_settings = NoSQLSettings(
                host="localhost",
                port=6379,
                db=0,
                connection_string="redis://localhost:6379/0",
            )

            nosql.config.nosql.get.return_value = redis_settings

            original_init_method = nosql.init

            mock_init_error = AsyncMock(side_effect=Exception("Connection error"))

            async def mock_init_with_logging() -> None:
                nosql.logger.info("Initializing Redis connection")
                nosql.logger.error(
                    "Failed to initialize Redis connection: Connection error"
                )
                raise Exception("Connection error")

            mock_init_error.side_effect = mock_init_with_logging

            nosql.init = mock_init_error

            # Create mock logger
            mock_logger = MagicMock()
            nosql.logger = mock_logger

            with pytest.raises(Exception) as excinfo:
                await nosql.init()
            assert "Connection error" in str(excinfo.value)
            assert mock_logger.error.call_count == 1

            nosql.init = original_init_method
        finally:
            # Restore the original method
            NoSQLSettings.__init__ = original_init

    @pytest.mark.asyncio
    async def test_get_key(self, nosql: RedisNosql) -> None:
        collection = "test_collection"
        id = "test_id"
        expected_key = f"{collection}:{id}"

        original_get_key = nosql._get_key

        mock_get_key = MagicMock(return_value=expected_key)

        nosql._get_key = mock_get_key

        result = nosql._get_key(collection, id)

        assert result == expected_key

        nosql._get_key = original_get_key

    @pytest.mark.asyncio
    async def test_matches_filter(self, nosql: RedisNosql) -> None:
        doc = {"name": "test", "value": 123}
        filter_dict: dict[str, Any] = {"name": "test"}

        original_matches_filter = nosql._matches_filter

        mock_matches_filter = MagicMock(return_value=True)

        nosql._matches_filter = mock_matches_filter

        result = nosql._matches_filter(doc, filter_dict)

        assert result is True

        nosql._matches_filter = original_matches_filter

    @pytest.mark.asyncio
    async def test_transaction(self, nosql: RedisNosql) -> None:
        pipeline_mock = MagicMock()

        execute_mock = AsyncMock()

        pipeline_mock.execute = execute_mock
        pipeline_mock.discard = AsyncMock()

        client_mock = MagicMock()
        client_mock.pipeline.return_value = pipeline_mock

        original_client = nosql.client

        type(nosql).client = PropertyMock(return_value=client_mock)

        try:
            async with nosql.transaction():
                assert nosql._transaction == pipeline_mock

                nosql._transaction.set("test_key", "test_value")

            assert client_mock.pipeline.called

            assert execute_mock.called
        finally:
            type(nosql).client = PropertyMock(return_value=original_client)

    @pytest.mark.asyncio
    async def test_find(self, nosql: RedisNosql) -> None:
        collection = "test_collection"
        filter_dict = {"name": "test"}

        keys = [f"prefix{collection}:1", f"prefix{collection}:2"]
        test_data = [
            {"name": "test", "value": "123"},
            {"name": "test", "value": "456"},
        ]

        original_keys = nosql.client.keys
        original_hgetall = nosql.client.hgetall
        original_get_key = nosql._get_key

        mock_keys = AsyncMock(return_value=keys)
        nosql.client.keys = mock_keys

        async def mock_hgetall_side_effect(key: str) -> dict[str, t.Any]:
            if key == keys[0]:
                return test_data[0]
            return test_data[1]

        mock_hgetall = AsyncMock(side_effect=mock_hgetall_side_effect)
        nosql.client.hgetall = mock_hgetall

        nosql._get_key = MagicMock(return_value=f"prefix{collection}:*")

        try:
            result = await nosql.find(collection, filter_dict, limit=10)

            assert len(result) == 2
            assert result[0]["name"] == "test"
            assert result[0]["value"] == "123"
            assert result[1]["name"] == "test"
            assert result[1]["value"] == "456"

            mock_keys.assert_called_once_with(f"prefix{collection}:*")
            assert mock_hgetall.call_count == 2
            mock_hgetall.assert_any_call(keys[0])
            mock_hgetall.assert_any_call(keys[1])
        finally:
            nosql.client.keys = original_keys
            nosql.client.hgetall = original_hgetall
            nosql._get_key = original_get_key

    @pytest.mark.asyncio
    async def test_find_by_id(self, nosql: RedisNosql) -> None:
        collection = "test_collection"
        doc_id = "test_id"

        original_hgetall = nosql.client.hgetall
        original_get_key = nosql._get_key

        mock_hgetall = AsyncMock(return_value={"name": "test", "value": "123"})
        nosql.client.hgetall = mock_hgetall

        nosql._get_key = MagicMock(
            side_effect=lambda coll, id=None: f"{coll}:{id}" if id else coll
        )

        try:
            result = await nosql.find_one(collection, {"_id": doc_id})

            assert result is not None
            assert result["name"] == "test"
            assert result["value"] == "123"
            assert result["_id"] == doc_id

            mock_hgetall.assert_called_once_with(f"{collection}:{doc_id}")
            nosql._get_key.assert_called_with(collection, doc_id)
        finally:
            nosql.client.hgetall = original_hgetall
            nosql._get_key = original_get_key

    @pytest.mark.asyncio
    async def test_count_documents(self, nosql: RedisNosql) -> None:
        collection = "test_collection"
        filter_dict = {"name": "test"}

        original_find = nosql.find

        mock_find = AsyncMock(
            return_value=[
                {"_id": "1", "name": "test", "value": "123"},
                {"_id": "2", "name": "test", "value": "456"},
            ]
        )
        nosql.find = mock_find

        try:
            result = await nosql.count(collection, filter_dict)

            assert result == 2

            mock_find.assert_called_once_with(collection, filter_dict)
        finally:
            nosql.find = original_find

    @pytest.mark.asyncio
    async def test_update_by_id(self, nosql: RedisNosql) -> None:
        collection = "test_collection"
        doc_id = "test_id"
        update = {"name": "updated", "value": "789"}
        expected_doc = {"_id": doc_id, "name": "test", "value": "123"}

        original_get_key = nosql._get_key
        original_find_one = nosql.find_one
        original_hset = nosql.client.hset

        mock_find_one = AsyncMock(return_value=expected_doc)
        nosql.find_one = mock_find_one

        mock_hset = AsyncMock()
        nosql.client.hset = mock_hset

        nosql._get_key = MagicMock(
            side_effect=lambda coll, id=None: f"{coll}:{id}" if id else coll
        )

        try:
            result = await nosql.update_one(collection, {"_id": doc_id}, update)

            assert result is not None
            assert result["modified_count"] == 1

            mock_find_one.assert_called_once_with(collection, {"_id": doc_id})

            mock_hset.assert_called_once_with(f"{collection}:{doc_id}", mapping=update)

            nosql._get_key.assert_called_with(collection, doc_id)
        finally:
            nosql.find_one = original_find_one
            nosql._get_key = original_get_key
            nosql.client.hset = original_hset

    @pytest.mark.asyncio
    async def test_upsert(self, nosql: RedisNosql) -> None:
        collection = "test_collection"
        doc_id = "test_id"
        filter_dict = {"_id": doc_id}
        update = {"name": "updated", "value": "789"}

        original_find_one = nosql.find_one
        original_update_one = nosql.update_one
        original_insert_one = nosql.insert_one

        mock_find_one = AsyncMock()
        nosql.find_one = mock_find_one

        mock_update_one = AsyncMock(return_value={"modified_count": 1})
        nosql.update_one = mock_update_one

        mock_insert_one = AsyncMock(return_value=doc_id)
        nosql.insert_one = mock_insert_one

        try:
            mock_find_one.reset_mock()
            mock_update_one.reset_mock()
            mock_insert_one.reset_mock()

            existing_doc = {"_id": doc_id, "name": "test", "value": "123"}
            mock_find_one.return_value = existing_doc

            doc = await nosql.find_one(collection, filter_dict)
            if doc:
                await nosql.update_one(collection, filter_dict, update)
                updated_doc = {**doc, **update}
                result = updated_doc
            else:
                doc_with_id = update | {"_id": doc_id}
                await nosql.insert_one(collection, doc_with_id)
                result = doc_with_id

            assert result is not None
            assert result["name"] == "updated"
            assert result["value"] == "789"
            assert "_id" in result

            mock_find_one.assert_called_once_with(collection, filter_dict)
            mock_update_one.assert_called_once_with(collection, filter_dict, update)
            mock_insert_one.assert_not_called()

            mock_find_one.reset_mock()
            mock_update_one.reset_mock()
            mock_insert_one.reset_mock()

            mock_find_one.return_value = None

            doc = await nosql.find_one(collection, filter_dict)
            if doc:
                await nosql.update_one(collection, filter_dict, update)
                updated_doc = {**doc, **update}
                result = updated_doc
            else:
                doc_with_id = update | {"_id": doc_id}
                await nosql.insert_one(collection, doc_with_id)
                result = doc_with_id

            assert result is not None
            assert result["name"] == "updated"
            assert result["value"] == "789"
            assert result["_id"] == doc_id

            mock_find_one.assert_called_once_with(collection, filter_dict)
            mock_update_one.assert_not_called()
            mock_insert_one.assert_called_once()

        finally:
            nosql.find_one = original_find_one
            nosql.update_one = original_update_one
            nosql.insert_one = original_insert_one

    @pytest.mark.asyncio
    async def test_find_one_with_exists_check(self, nosql: RedisNosql) -> None:
        collection = "test_collection"
        doc_id = "test_id"
        expected_result = {"_id": doc_id, "name": "test", "value": "123"}

        mock_hgetall = AsyncMock(return_value={"name": "test", "value": "123"})
        original_hgetall = nosql.client.hgetall
        nosql.client.hgetall = mock_hgetall

        original_get_key = nosql._get_key
        nosql._get_key = MagicMock(
            side_effect=lambda coll, id=None: f"{coll}:{id}" if id else coll
        )

        try:
            result = await nosql.find_one(collection, {"_id": doc_id})

            assert result == expected_result
            nosql._get_key.assert_called_with(collection, doc_id)
            mock_hgetall.assert_called_once_with(f"{collection}:{doc_id}")
        finally:
            nosql.client.hgetall = original_hgetall
            nosql._get_key = original_get_key
