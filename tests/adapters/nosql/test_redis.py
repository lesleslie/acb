"""Tests for the Redis NoSQL adapter."""

from types import TracebackType
from typing import Any, Optional, Type
from unittest.mock import MagicMock, PropertyMock, patch

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
            host="localhost",
            port=6379,
            database=0,
            cache_db=1,
            username="test_user",
            password=SecretStr("test_password"),
        )

        assert settings.host == "localhost"
        assert settings.port == 6379
        assert settings.database == 0
        assert settings.cache_db == 1
        assert settings.username == "test_user"
        assert settings.password.get_secret_value() == "test_password"

        settings = RedisSettings(
            host="localhost",
        )

        assert settings.host == "localhost"
        assert settings.port == 6379
        assert settings.database == 0
        assert settings.cache_db == 1
        assert settings.username is None
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

        mock_client = MagicMock(spec=Redis)
        type(nosql).client = PropertyMock(return_value=mock_client)

        mock_om_client = MagicMock()
        type(nosql).om_client = PropertyMock(return_value=mock_om_client)

        mock_client.get.return_value = b'{"_id": "test_id", "data": "test_data"}'
        mock_client.set.return_value = True
        mock_client.delete.return_value = 1
        mock_client.exists.return_value = 1
        mock_client.scan_iter.return_value = [b"collection:test_id"]
        mock_client.pipeline.return_value = mock_async_context_manager()

        return nosql

    def test_client_property(self, nosql: RedisNosql) -> None:
        assert nosql.client is not None

    def test_om_client_property(self, nosql: RedisNosql) -> None:
        assert nosql.om_client is not None

    @pytest.mark.asyncio
    async def test_init(self, nosql: RedisNosql) -> None:
        nosql.config.nosql.get.return_value = RedisSettings(
            host="localhost",
            port=6379,
            database=0,
        )

        with patch("redis.asyncio.Redis") as mock_client_class:
            await nosql.init()
            mock_client_class.assert_called_once()
            assert nosql.logger.info.call_count == 1

    @pytest.mark.asyncio
    async def test_init_error(self, nosql: RedisNosql) -> None:
        nosql.config.nosql.get.return_value = RedisSettings(
            host="localhost",
            port=6379,
            database=0,
        )

        with patch("redis.asyncio.Redis", side_effect=Exception("Connection error")):
            with pytest.raises(Exception) as excinfo:
                await nosql.init()
            assert "Connection error" in str(excinfo.value)
            assert nosql.logger.error.call_count == 1

    def test_get_key(self, nosql: RedisNosql) -> None:
        key = nosql._get_key("test_collection", "test_id")
        assert key == "test_collection:test_id"

    def test_matches_filter(self, nosql: RedisNosql) -> None:
        doc = {"name": "test", "age": 30, "address": {"city": "New York"}}

        assert nosql._matches_filter(doc, {"name": "test"})
        assert not nosql._matches_filter(doc, {"name": "other"})

        assert nosql._matches_filter(doc, {"address.city": "New York"})
        assert not nosql._matches_filter(doc, {"address.city": "Los Angeles"})

        assert nosql._matches_filter(doc, {"name": "test", "age": 30})
        assert not nosql._matches_filter(doc, {"name": "test", "age": 25})

    @pytest.mark.asyncio
    async def test_transaction(self, nosql: RedisNosql) -> None:
        async with nosql.transaction():
            pass

        assert nosql.client.pipeline is not None
        assert nosql.client.pipeline.called  # type: ignore
