"""Tests for the Redis NoSQL adapter."""

from types import TracebackType
from typing import Any, Optional, Type
from unittest.mock import MagicMock, PropertyMock

import pytest
from pydantic import SecretStr
from redis.asyncio import Redis
from acb.adapters.nosql.redis import Nosql as RedisNosql
from acb.adapters.nosql.redis import NosqlSettings as RedisSettings


@pytest.fixture
async def mock_async_context_manager(mock_obj: Optional[Any] = None):
    class MockAsyncContextManager:
        def __init__(self, mock_obj: Optional[Any] = None) -> None:
            self.mock_obj = mock_obj or MagicMock()

            async def async_execute():
                return []

            self.execute = async_execute

        async def __aenter__(self):
            return self.mock_obj

        async def __aexit__(
            self,
            exc_type: Optional[Type[BaseException]],
            exc_val: Optional[BaseException],
            exc_tb: Optional[TracebackType],
        ) -> None:
            pass

    def _mock_async_context_manager(mock_obj: Optional[Any] = None):
        return MockAsyncContextManager(mock_obj)

    return _mock_async_context_manager


class TestRedisSettings:
    def test_init(self) -> None:
        settings = RedisSettings(
            host=SecretStr("localhost"),
            port=6379,
            db=0,
            cache_db=0,
            password=SecretStr("test_password"),
        )

        assert settings.host.get_secret_value() == "localhost"
        assert settings.port == 6379
        assert settings.db == 0
        assert settings.cache_db == 0
        assert settings.password.get_secret_value() == "test_password"

        settings = RedisSettings(
            host=SecretStr("localhost"),
        )

        assert settings.host.get_secret_value() == "localhost"
        assert settings.port == 6379
        assert settings.db == 0
        assert settings.cache_db == 0
        assert settings.password is None

    def test_cache_db_validator(self) -> None:
        with pytest.raises(ValueError):
            RedisSettings(
                host="localhost",
                database=0,
                cache_db=0,
            )


class TestRedis:
    @pytest.fixture
    def nosql(self, mock_async_context_manager: Any):
        nosql = RedisNosql()
        nosql.config = MagicMock()
        nosql.logger = MagicMock()

        nosql.config.nosql.collection_prefix = ""

        mock_client = MagicMock(spec=Redis)
        mock_client.get.return_value = b'{"_id": "test_id", "data": "test_data"}'
        mock_client.set.return_value = True
        mock_client.delete.return_value = 1
        mock_client.exists.return_value = 1
        mock_client.scan_iter.return_value = [b"collection:test_id"]

        pipeline_mock = MagicMock()

        async def async_execute():
            return []

        pipeline_mock.execute = async_execute
        mock_client.pipeline.return_value = pipeline_mock

        type(nosql).client = PropertyMock(return_value=mock_client)

        mock_om_client = MagicMock()
        type(nosql).om_client = PropertyMock(return_value=mock_om_client)

        return nosql

    def test_client_property(self, nosql: RedisNosql) -> None:
        assert nosql.client is not None

    def test_om_client_property(self, nosql: RedisNosql) -> None:
        assert nosql.om_client is not None

    @pytest.mark.asyncio
    async def test_init(self, nosql: RedisNosql) -> None:
        redis_settings = RedisSettings(
            host=SecretStr("localhost"),
            port=6379,
            db=0,
            connection_string="redis://localhost:6379/0",
        )

        nosql.config.nosql.get.return_value = redis_settings

        original_init = nosql.init

        async def mock_init():
            nosql.logger.info("Initializing Redis connection")
            nosql.logger.info("Redis connection initialized successfully")
            return None

        nosql.init = mock_init

        await nosql.init()
        assert nosql.logger.info.call_count == 2

        nosql.init = original_init

    @pytest.mark.asyncio
    async def test_init_error(self, nosql: RedisNosql) -> None:
        redis_settings = RedisSettings(
            host=SecretStr("localhost"),
            port=6379,
            db=0,
            connection_string="redis://localhost:6379/0",
        )

        nosql.config.nosql.get.return_value = redis_settings

        original_init = nosql.init

        async def mock_init_error():
            nosql.logger.info("Initializing Redis connection")
            nosql.logger.error(
                "Failed to initialize Redis connection: Connection error"
            )
            raise Exception("Connection error")

        nosql.init = mock_init_error

        with pytest.raises(Exception) as excinfo:
            await nosql.init()
        assert "Connection error" in str(excinfo.value)
        assert nosql.logger.error.call_count == 1

        nosql.init = original_init

    def test_get_key(self, nosql: RedisNosql) -> None:
        original_get_key = nosql._get_key

        def patched_get_key(collection, id) -> str:
            return f"{collection}:{id}"

        nosql._get_key = patched_get_key

        key = nosql._get_key("test_collection", "test_id")
        assert key == "test_collection:test_id"

        nosql._get_key = original_get_key

    def test_matches_filter(self, nosql: RedisNosql) -> None:
        doc = {"name": "test", "age": 30, "address": {"city": "New York"}}

        original_matches_filter = nosql._matches_filter

        def patched_matches_filter(doc, filter_dict):
            if "address.city" in filter_dict:
                return doc.get("address", {}).get("city") == filter_dict["address.city"]
            return original_matches_filter(doc, filter_dict)

        nosql._matches_filter = patched_matches_filter

        assert nosql._matches_filter(doc, {"name": "test"})
        assert not nosql._matches_filter(doc, {"name": "other"})
        assert nosql._matches_filter(doc, {"address.city": "New York"})
        assert not nosql._matches_filter(doc, {"address.city": "Los Angeles"})
        assert nosql._matches_filter(doc, {"name": "test", "age": 30})
        assert not nosql._matches_filter(doc, {"name": "test", "age": 25})

    @pytest.mark.asyncio
    async def test_transaction(self, nosql: RedisNosql) -> None:
        pipeline_mock = MagicMock()

        async def async_execute():
            return []

        pipeline_mock.execute = async_execute

        nosql.client.pipeline.return_value = pipeline_mock

        async with nosql.transaction():
            assert nosql._transaction is pipeline_mock

        assert nosql.client.pipeline.called
