"""Tests for the NoSQL Base adapter."""

import typing as t
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr
from acb.adapters.nosql._base import NosqlBase, NosqlBaseSettings, NosqlCollection


class MockNosqlBase(NosqlBase):
    def __init__(self) -> None:
        super().__init__()
        self.config = MagicMock()
        self.logger = MagicMock()
        self._collections = {}
        self._client = None
        self._db = None
        self._transaction = None
        self._data: dict[str, dict[str, dict[str, t.Any]]] = {}


class TestNosqlBaseSettings:
    def test_init(self) -> None:
        settings = NosqlBaseSettings(
            host=SecretStr("127.0.0.1"),
            collection_prefix="",
            database="test_app",
        )

        assert settings.host.get_secret_value() == "127.0.0.1"
        assert settings.collection_prefix == ""
        assert settings.database == "test_app"

        custom_settings = NosqlBaseSettings(
            host=SecretStr("custom_host"),
            port=1234,
            database="custom_db",
            collection_prefix="prefix_",
        )

        assert custom_settings.host.get_secret_value() == "custom_host"
        assert custom_settings.port == 1234
        assert custom_settings.database == "custom_db"
        assert custom_settings.collection_prefix == "prefix_"


class TestNosqlCollection:
    @pytest.fixture
    def nosql_base(self) -> MockNosqlBase:
        return MockNosqlBase()

    @pytest.fixture
    def collection(self, nosql_base: MockNosqlBase) -> NosqlCollection:
        return NosqlCollection(nosql_base, "test_collection")

    @pytest.mark.asyncio
    async def test_find(
        self,
        nosql_base: MockNosqlBase,
        collection: NosqlCollection,
    ) -> None:
        with patch.object(nosql_base, "find", AsyncMock()) as mock_find:
            mock_find.return_value = [{"_id": "1", "name": "Test"}]

            result = await collection.find({"name": "Test"})

            mock_find.assert_called_once_with("test_collection", {"name": "Test"})
            assert result == [{"_id": "1", "name": "Test"}]

    @pytest.mark.asyncio
    async def test_find_one(
        self,
        nosql_base: MockNosqlBase,
        collection: NosqlCollection,
    ) -> None:
        with patch.object(nosql_base, "find_one", AsyncMock()) as mock_find_one:
            mock_find_one.return_value = {"_id": "1", "name": "Test"}

            result = await collection.find_one({"name": "Test"})

            mock_find_one.assert_called_once_with("test_collection", {"name": "Test"})
            assert result == {"_id": "1", "name": "Test"}

    @pytest.mark.asyncio
    async def test_insert_one(
        self,
        nosql_base: MockNosqlBase,
        collection: NosqlCollection,
    ) -> None:
        with patch.object(nosql_base, "insert_one", AsyncMock()) as mock_insert_one:
            mock_insert_one.return_value = {"_id": "1", "name": "Test"}

            result = await collection.insert_one({"name": "Test"})

            mock_insert_one.assert_called_once_with("test_collection", {"name": "Test"})
            assert result == {"_id": "1", "name": "Test"}

    @pytest.mark.asyncio
    async def test_update_one(
        self,
        nosql_base: MockNosqlBase,
        collection: NosqlCollection,
    ) -> None:
        with patch.object(nosql_base, "update_one", AsyncMock()) as mock_update_one:
            mock_update_one.return_value = {"modified_count": 1}

            result = await collection.update_one(
                {"name": "Test"},
                {"$set": {"active": True}},
            )

            mock_update_one.assert_called_once_with(
                "test_collection",
                {"name": "Test"},
                {"$set": {"active": True}},
            )
            assert result == {"modified_count": 1}

    @pytest.mark.asyncio
    async def test_delete_one(
        self,
        nosql_base: MockNosqlBase,
        collection: NosqlCollection,
    ) -> None:
        with patch.object(nosql_base, "delete_one", AsyncMock()) as mock_delete_one:
            mock_delete_one.return_value = {"deleted_count": 1}

            result = await collection.delete_one({"name": "Test"})

            mock_delete_one.assert_called_once_with("test_collection", {"name": "Test"})
            assert result == {"deleted_count": 1}

    @pytest.mark.asyncio
    async def test_delete_many(
        self,
        nosql_base: MockNosqlBase,
        collection: NosqlCollection,
    ) -> None:
        with patch.object(nosql_base, "delete_many", AsyncMock()) as mock_delete_many:
            mock_delete_many.return_value = {"deleted_count": 2}

            result = await collection.delete_many({"active": False})

            mock_delete_many.assert_called_once_with(
                "test_collection",
                {"active": False},
            )
            assert result == {"deleted_count": 2}

    @pytest.mark.asyncio
    async def test_count(
        self,
        nosql_base: MockNosqlBase,
        collection: NosqlCollection,
    ) -> None:
        with patch.object(nosql_base, "count", AsyncMock()) as mock_count:
            mock_count.return_value = 5

            result = await collection.count({"active": True})

            mock_count.assert_called_once_with("test_collection", {"active": True})
            assert result == 5
