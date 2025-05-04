import typing as t
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.cloud import firestore
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pydantic import SecretStr
from redis.asyncio import Redis
from acb.adapters.nosql._base import NosqlBase, NosqlBaseSettings, NosqlCollection
from acb.adapters.nosql.firestore import (
    Nosql as FirestoreNosql,
)
from acb.adapters.nosql.firestore import (
    NosqlSettings as FirestoreSettings,
)
from acb.adapters.nosql.mongodb import (
    Nosql as MongoDBNosql,
)
from acb.adapters.nosql.mongodb import (
    NosqlSettings as MongoDBSettings,
)
from acb.adapters.nosql.redis import Nosql as RedisNosql
from acb.adapters.nosql.redis import NosqlSettings as RedisSettings


class MockNosqlBase(NosqlBase):
    def __init__(self) -> None:
        super().__init__()
        self.config = MagicMock()
        self.logger = MagicMock()
        self._collections = {}
        self._client = None
        self._db = None
        self._transaction = None
        self._data: t.Dict[str, t.Dict[str, t.Dict[str, t.Any]]] = {}

    async def init(self) -> None:
        self.logger.info("Initializing mock NoSQL adapter")

    async def find(
        self, collection: str, filter: t.Dict[str, t.Any], **kwargs: t.Any
    ) -> t.List[t.Dict[str, t.Any]]:
        if collection not in self._data:
            return []

        results = []
        for doc_id, doc in self._data[collection].items():
            if self._matches_filter(doc, filter):
                doc_with_id = doc.copy()
                doc_with_id["_id"] = doc_id
                results.append(doc_with_id)

        limit = kwargs.get("limit")
        if limit is not None:
            results = results[:limit]

        return results

    async def find_one(
        self, collection: str, filter: t.Dict[str, t.Any], **kwargs: t.Any
    ) -> t.Optional[t.Dict[str, t.Any]]:
        results = await self.find(collection, filter, **kwargs, limit=1)
        return next(iter(results), None)

    async def insert_one(
        self, collection: str, document: t.Dict[str, t.Any], **kwargs: t.Any
    ) -> t.Any:
        if collection not in self._data:
            self._data[collection] = {}

        doc_id = document.get("_id", f"id_{len(self._data[collection]) + 1}")

        if "_id" in document:
            document = document.copy()
            del document["_id"]

        self._data[collection][doc_id] = document

        return doc_id

    async def insert_many(
        self, collection: str, documents: t.List[t.Dict[str, t.Any]], **kwargs: t.Any
    ) -> t.List[t.Any]:
        ids = []
        for doc in documents:
            doc_id = await self.insert_one(collection, doc, **kwargs)
            ids.append(doc_id)
        return ids

    async def update_one(
        self,
        collection: str,
        filter: t.Dict[str, t.Any],
        update: t.Dict[str, t.Any],
        **kwargs: t.Any,
    ) -> t.Any:
        doc = await self.find_one(collection, filter)
        if not doc:
            return {"modified_count": 0}

        doc_id = doc["_id"]

        if "$set" in update:
            for key, value in update["$set"].items():
                self._data[collection][doc_id][key] = value
        else:
            for key, value in update.items():
                self._data[collection][doc_id][key] = value

        return {"modified_count": 1}

    async def update_many(
        self,
        collection: str,
        filter: t.Dict[str, t.Any],
        update: t.Dict[str, t.Any],
        **kwargs: t.Any,
    ) -> t.Any:
        docs = await self.find(collection, filter)
        if not docs:
            return {"modified_count": 0}

        modified_count = 0
        for doc in docs:
            doc_id = doc["_id"]

            if "$set" in update:
                for key, value in update["$set"].items():
                    self._data[collection][doc_id][key] = value
            else:
                for key, value in update.items():
                    self._data[collection][doc_id][key] = value

            modified_count += 1

        return {"modified_count": modified_count}

    async def delete_one(
        self, collection: str, filter: t.Dict[str, t.Any], **kwargs: t.Any
    ) -> t.Any:
        doc = await self.find_one(collection, filter)
        if not doc:
            return {"deleted_count": 0}

        doc_id = doc["_id"]
        del self._data[collection][doc_id]

        return {"deleted_count": 1}

    async def delete_many(
        self, collection: str, filter: t.Dict[str, t.Any], **kwargs: t.Any
    ) -> t.Any:
        docs = await self.find(collection, filter)
        if not docs:
            return {"deleted_count": 0}

        deleted_count = 0
        for doc in docs:
            doc_id = doc["_id"]
            del self._data[collection][doc_id]
            deleted_count += 1

        return {"deleted_count": deleted_count}

    async def count(
        self,
        collection: str,
        filter: t.Optional[t.Dict[str, t.Any]] = None,
        **kwargs: t.Any,
    ) -> int:
        docs = await self.find(collection, filter or {})
        return len(docs)

    async def aggregate(
        self,
        collection: str,
        pipeline: t.List[t.Dict[str, t.Any]],
        **kwargs: t.Any,
    ) -> t.List[t.Dict[str, t.Any]]:
        docs = await self.find(collection, {})

        for stage in pipeline:
            if "$match" in stage:
                docs = [
                    doc for doc in docs if self._matches_filter(doc, stage["$match"])
                ]
            elif "$project" in stage:
                projection = stage["$project"]
                docs = [{k: doc[k] for k in projection if k in doc} for doc in docs]
            elif "$limit" in stage:
                docs = docs[: stage["$limit"]]
            elif "$skip" in stage:
                docs = docs[stage["$skip"] :]

        return docs

    @asynccontextmanager
    async def transaction(self) -> t.AsyncGenerator[None, None]:
        self._transaction = {}
        try:
            yield
        except Exception as e:
            self.logger.error(f"Transaction failed: {e}")
            raise
        finally:
            self._transaction = None

    def _matches_filter(
        self, doc: t.Dict[str, t.Any], filter: t.Dict[str, t.Any]
    ) -> bool:
        if not filter:
            return True

        for key, value in filter.items():
            if key not in doc or doc[key] != value:
                return False
        return True


class TestNosqlBaseSettings:
    def test_init(self) -> None:
        mock_config = MagicMock()
        mock_config.app.name = "test_app"

        settings = NosqlBaseSettings()
        settings.__init__(config=mock_config)

        assert settings.host == SecretStr("127.0.0.1")
        assert settings.collection_prefix == ""
        assert settings.database == "test_app"

        settings = NosqlBaseSettings(
            host=SecretStr("custom_host"),
            port=1234,
            database="custom_db",
            collection_prefix="prefix_",
        )
        settings.__init__(config=mock_config)

        assert settings.host == SecretStr("custom_host")
        assert settings.port == 1234
        assert settings.database == "custom_db"
        assert settings.collection_prefix == "prefix_"


class TestNosqlCollection:
    @pytest.fixture
    def nosql_base(self) -> MockNosqlBase:
        return MockNosqlBase()

    @pytest.fixture
    def collection(self, nosql_base: MockNosqlBase) -> NosqlCollection:
        return NosqlCollection(nosql_base, "test_collection")

    @pytest.mark.asyncio
    async def test_find(
        self, nosql_base: MockNosqlBase, collection: NosqlCollection
    ) -> None:
        with patch.object(nosql_base, "find", AsyncMock()) as mock_find:
            mock_find.return_value = [{"_id": "1", "name": "Test"}]

            result = await collection.find({"name": "Test"})

            mock_find.assert_called_once_with("test_collection", {"name": "Test"})
            assert result == [{"_id": "1", "name": "Test"}]

    @pytest.mark.asyncio
    async def test_find_one(
        self, nosql_base: MockNosqlBase, collection: NosqlCollection
    ) -> None:
        with patch.object(nosql_base, "find_one", AsyncMock()) as mock_find_one:
            mock_find_one.return_value = {"_id": "1", "name": "Test"}

            result = await collection.find_one({"name": "Test"})

            mock_find_one.assert_called_once_with("test_collection", {"name": "Test"})
            assert result == {"_id": "1", "name": "Test"}

    @pytest.mark.asyncio
    async def test_insert_one(
        self, nosql_base: MockNosqlBase, collection: NosqlCollection
    ) -> None:
        with patch.object(nosql_base, "insert_one", AsyncMock()) as mock_insert_one:
            mock_insert_one.return_value = "1"

            result = await collection.insert_one({"name": "Test"})

            mock_insert_one.assert_called_once_with("test_collection", {"name": "Test"})
            assert result == "1"

    @pytest.mark.asyncio
    async def test_insert_many(
        self, nosql_base: MockNosqlBase, collection: NosqlCollection
    ) -> None:
        with patch.object(nosql_base, "insert_many", AsyncMock()) as mock_insert_many:
            mock_insert_many.return_value = ["1", "2"]

            result = await collection.insert_many(
                [{"name": "Test1"}, {"name": "Test2"}]
            )

            mock_insert_many.assert_called_once_with(
                "test_collection", [{"name": "Test1"}, {"name": "Test2"}]
            )
            assert result == ["1", "2"]

    @pytest.mark.asyncio
    async def test_update_one(
        self, nosql_base: MockNosqlBase, collection: NosqlCollection
    ) -> None:
        with patch.object(nosql_base, "update_one", AsyncMock()) as mock_update_one:
            mock_update_one.return_value = {"modified_count": 1}

            result = await collection.update_one(
                {"_id": "1"}, {"$set": {"name": "Updated"}}
            )

            mock_update_one.assert_called_once_with(
                "test_collection", {"_id": "1"}, {"$set": {"name": "Updated"}}
            )
            assert result == {"modified_count": 1}

    @pytest.mark.asyncio
    async def test_update_many(
        self, nosql_base: MockNosqlBase, collection: NosqlCollection
    ) -> None:
        with patch.object(nosql_base, "update_many", AsyncMock()) as mock_update_many:
            mock_update_many.return_value = {"modified_count": 2}

            result = await collection.update_many(
                {"active": True}, {"$set": {"status": "updated"}}
            )

            mock_update_many.assert_called_once_with(
                "test_collection", {"active": True}, {"$set": {"status": "updated"}}
            )
            assert result == {"modified_count": 2}

    @pytest.mark.asyncio
    async def test_delete_one(
        self, nosql_base: MockNosqlBase, collection: NosqlCollection
    ) -> None:
        with patch.object(nosql_base, "delete_one", AsyncMock()) as mock_delete_one:
            mock_delete_one.return_value = {"deleted_count": 1}

            result = await collection.delete_one({"_id": "1"})

            mock_delete_one.assert_called_once_with("test_collection", {"_id": "1"})
            assert result == {"deleted_count": 1}

    @pytest.mark.asyncio
    async def test_delete_many(
        self, nosql_base: MockNosqlBase, collection: NosqlCollection
    ) -> None:
        with patch.object(nosql_base, "delete_many", AsyncMock()) as mock_delete_many:
            mock_delete_many.return_value = {"deleted_count": 2}

            result = await collection.delete_many({"active": False})

            mock_delete_many.assert_called_once_with(
                "test_collection", {"active": False}
            )
            assert result == {"deleted_count": 2}

    @pytest.mark.asyncio
    async def test_count(
        self, nosql_base: MockNosqlBase, collection: NosqlCollection
    ) -> None:
        with patch.object(nosql_base, "count", AsyncMock()) as mock_count:
            mock_count.return_value = 5

            result = await collection.count({"active": True})

            mock_count.assert_called_once_with("test_collection", {"active": True})
            assert result == 5

    @pytest.mark.asyncio
    async def test_aggregate(
        self, nosql_base: MockNosqlBase, collection: NosqlCollection
    ) -> None:
        with patch.object(nosql_base, "aggregate", AsyncMock()) as mock_aggregate:
            mock_aggregate.return_value = [{"_id": "1", "count": 5}]

            pipeline = [{"$match": {"active": True}}, {"$project": {"count": 1}}]
            result = await collection.aggregate(pipeline)

            mock_aggregate.assert_called_once_with("test_collection", pipeline)
            assert result == [{"_id": "1", "count": 5}]


class TestMongoDBSettings:
    def test_init(self) -> None:
        mock_config = MagicMock()
        mock_config.app.name = "test_app"

        settings = MongoDBSettings()
        settings.__init__(config=mock_config)

        assert settings.port == 27017
        assert settings.database == "test_app"

        assert settings.connection_string == "mongodb://127.0.0.1:27017/test_app"

        settings = MongoDBSettings(
            host="custom_host",
            port=27018,
            user="testuser",
            password="testpass",  # nosec B106  # nosec B106
            database="custom_db",
        )
        settings.__init__(config=mock_config)

        assert settings.port == 27018
        assert settings.database == "custom_db"
        assert (
            settings.connection_string
            == "mongodb://testuser:testpass@custom_host:27018/custom_db"
        )


class TestMongoDB:
    @pytest.fixture
    def nosql(self) -> MongoDBNosql:
        instance = MongoDBNosql()
        instance.config = MagicMock()
        instance.logger = MagicMock()
        instance.config.nosql = MagicMock()
        instance.config.nosql.connection_string = "mongodb://localhost:27017/test_db"
        instance.config.nosql.connection_options = {}
        instance.config.nosql.database = "test_db"
        return instance

    def test_client_property(self, nosql: MongoDBNosql) -> None:
        with patch("acb.adapters.nosql.mongodb.AsyncIOMotorClient") as mock_client:
            mock_client.return_value = MagicMock(spec=AsyncIOMotorClient)

            client = nosql.client

            mock_client.assert_called_once_with(
                "mongodb://localhost:27017/test_db", **{}
            )
            assert client == mock_client.return_value

            client2 = nosql.client
            assert client2 is client
            mock_client.assert_called_once()

    def test_db_property(self, nosql: MongoDBNosql) -> None:
        mock_db = MagicMock(spec=AsyncIOMotorDatabase)
        mock_client = MagicMock(spec=AsyncIOMotorClient)
        mock_client.__getitem__.return_value = mock_db

        with patch.object(nosql, "client", mock_client):
            db = nosql.db

            mock_client.__getitem__.assert_called_once_with("test_db")
            assert db == mock_db

            db2 = nosql.db
            assert db2 is db
            mock_client.__getitem__.assert_called_once()

    @pytest.mark.asyncio
    async def test_init(self, nosql: MongoDBNosql) -> None:
        with (
            patch(
                "acb.adapters.nosql.mongodb.init_beanie", AsyncMock()
            ) as mock_init_beanie,
            patch.object(nosql, "db", MagicMock(spec=AsyncIOMotorDatabase)),
        ):
            await nosql.init()

            mock_init_beanie.assert_called_once_with(
                database=nosql.db, document_models=[]
            )
            nosql.logger.info.assert_called_with(
                "MongoDB connection initialized successfully"
            )

    @pytest.mark.asyncio
    async def test_init_error(self, nosql: MongoDBNosql) -> None:
        with (
            patch(
                "acb.adapters.nosql.mongodb.init_beanie", AsyncMock()
            ) as mock_init_beanie,
            patch.object(nosql, "db", MagicMock(spec=AsyncIOMotorDatabase)),
        ):
            mock_init_beanie.side_effect = Exception("Connection error")

            with pytest.raises(Exception) as excinfo:
                await nosql.init()

            assert "Connection error" in str(excinfo.value)
            nosql.logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_find(self, nosql: MongoDBNosql) -> None:
        mock_cursor = AsyncMock()
        mock_cursor.to_list.return_value = [{"_id": "1", "name": "Test"}]

        mock_collection = MagicMock()
        mock_collection.find.return_value = mock_cursor

        mock_db = MagicMock(spec=AsyncIOMotorDatabase)
        mock_db.__getitem__.return_value = mock_collection

        with patch.object(nosql, "db", mock_db):
            result = await nosql.find("users", {"name": "Test"}, limit=10)

            mock_db.__getitem__.assert_called_once_with("users")
            mock_collection.find.assert_called_once_with({"name": "Test"}, limit=10)
            mock_cursor.to_list.assert_called_once_with(length=None)
            assert result == [{"_id": "1", "name": "Test"}]

    @pytest.mark.asyncio
    async def test_find_one(self, nosql: MongoDBNosql) -> None:
        mock_collection = MagicMock()
        mock_collection.find_one.return_value = {"_id": "1", "name": "Test"}

        mock_db = MagicMock(spec=AsyncIOMotorDatabase)
        mock_db.__getitem__.return_value = mock_collection

        with patch.object(nosql, "db", mock_db):
            result = await nosql.find_one("users", {"name": "Test"})

            mock_db.__getitem__.assert_called_once_with("users")
            mock_collection.find_one.assert_called_once_with({"name": "Test"})
            assert result == {"_id": "1", "name": "Test"}

    @pytest.mark.asyncio
    async def test_insert_one(self, nosql: MongoDBNosql) -> None:
        mock_result = MagicMock()
        mock_result.inserted_id = "1"

        mock_collection = MagicMock()
        mock_collection.insert_one.return_value = mock_result

        mock_db = MagicMock(spec=AsyncIOMotorDatabase)
        mock_db.__getitem__.return_value = mock_collection

        with patch.object(nosql, "db", mock_db):
            result = await nosql.insert_one("users", {"name": "Test"})

            mock_db.__getitem__.assert_called_once_with("users")
            mock_collection.insert_one.assert_called_once_with({"name": "Test"})
            assert result == "1"

    @pytest.mark.asyncio
    async def test_transaction(self, nosql: MongoDBNosql) -> None:
        mock_session = AsyncMock()
        mock_session.start_transaction = AsyncMock()
        mock_session.end_session = AsyncMock()

        mock_client = MagicMock(spec=AsyncIOMotorClient)
        mock_client.start_session.return_value = mock_session

        with patch.object(nosql, "client", mock_client):
            assert nosql._transaction is None

            async with nosql.transaction():
                assert nosql._transaction == mock_session

            assert nosql._transaction is None
            mock_client.start_session.assert_called_once()
            mock_session.end_session.assert_called_once()

            mock_client.start_session.reset_mock()
            mock_session.end_session.reset_mock()

            with pytest.raises(ValueError):
                async with nosql.transaction():
                    raise ValueError("Test error")


class TestRedisSettings:
    def test_init(self) -> None:
        mock_config = MagicMock()
        mock_config.app.name = "test_app"

        settings = RedisSettings()
        settings.__init__(config=mock_config)

        assert settings.port == 6379
        assert settings.db == 0
        assert settings.decode_responses
        assert settings.encoding == "utf-8"

        assert settings.connection_string == "redis://@127.0.0.1:6379/0"

        settings = RedisSettings(
            host="custom_host",
            port=6380,
            password="testpass",  # nosec B106 db=1
        )
        settings.__init__(config=mock_config)

        assert settings.port == 6380
        assert settings.db == 1
        assert settings.connection_string == "redis://:testpass@custom_host:6380/1"

    def test_cache_db_validator(self) -> None:
        settings = RedisSettings(cache_db=0)
        assert settings.cache_db == 0

        settings = RedisSettings(cache_db=3)
        assert settings.cache_db == 0

        with pytest.raises(ValueError):
            RedisSettings(cache_db=1)

        with pytest.raises(ValueError):
            RedisSettings(cache_db=2)


class TestRedis:
    @pytest.fixture
    def nosql(self) -> RedisNosql:
        instance = RedisNosql()
        instance.config = MagicMock()
        instance.logger = MagicMock()
        instance.config.nosql = MagicMock()
        instance.config.nosql.connection_string = "redis://localhost:6379/0"
        instance.config.nosql.decode_responses = True
        instance.config.nosql.encoding = "utf-8"
        instance.config.nosql.collection_prefix = "test:"
        return instance

    def test_client_property(self, nosql: RedisNosql) -> None:
        with patch("acb.adapters.nosql.redis.redis.from_url") as mock_from_url:
            mock_from_url.return_value = MagicMock(spec=Redis)

            client = nosql.client

            mock_from_url.assert_called_once_with(
                "redis://localhost:6379/0", decode_responses=True, encoding="utf-8"
            )
            assert client == mock_from_url.return_value

            client2 = nosql.client
            assert client2 is client
            mock_from_url.assert_called_once()

    def test_om_client_property(self, nosql: RedisNosql) -> None:
        with patch("acb.adapters.nosql.redis.get_redis_connection") as mock_get_redis:
            mock_get_redis.return_value = MagicMock()

            client = nosql.om_client

            mock_get_redis.assert_called_once_with(
                url="redis://localhost:6379/0", decode_responses=True
            )
            assert client == mock_get_redis.return_value

            client2 = nosql.om_client
            assert client2 is client
            mock_get_redis.assert_called_once()

    @pytest.mark.asyncio
    async def test_init(self, nosql: RedisNosql) -> None:
        with (
            patch.object(nosql, "client", MagicMock(spec=Redis)) as mock_client,
            patch("acb.adapters.nosql.redis.Migrator") as mock_migrator_class,
        ):
            mock_client.ping = AsyncMock()
            mock_migrator = MagicMock()
            mock_migrator_class.return_value = mock_migrator

            await nosql.init()

            mock_client.ping.assert_called_once()
            mock_migrator_class.assert_called_once()
            mock_migrator.run.assert_called_once()
            nosql.logger.info.assert_called_with(
                "Redis connection initialized successfully"
            )

    @pytest.mark.asyncio
    async def test_init_error(self, nosql: RedisNosql) -> None:
        with patch.object(nosql, "client", MagicMock(spec=Redis)) as mock_client:
            mock_client.ping = AsyncMock(side_effect=Exception("Connection error"))

            with pytest.raises(Exception) as excinfo:
                await nosql.init()

            assert "Connection error" in str(excinfo.value)
            nosql.logger.error.assert_called_once()

    def test_get_key(self, nosql: RedisNosql) -> None:
        key = nosql._get_key("users", "123")
        assert key == "test:users:123"

        key = nosql._get_key("users")
        assert key == "test:users"

    def test_matches_filter(self, nosql: RedisNosql) -> None:
        assert nosql._matches_filter({"name": "Test"}, {})

        assert nosql._matches_filter({"name": "Test", "age": 30}, {"name": "Test"})

        assert not nosql._matches_filter({"name": "Test"}, {"name": "Other"})

        assert not nosql._matches_filter({"name": "Test"}, {"age": 30})

    @pytest.mark.asyncio
    async def test_transaction(self, nosql: RedisNosql) -> None:
        with patch.object(nosql, "client", MagicMock(spec=Redis)) as mock_client:
            mock_pipeline = AsyncMock()
            mock_client.pipeline.return_value = mock_pipeline

            assert nosql._transaction is None

            async with nosql.transaction():
                assert nosql._transaction == mock_pipeline

            assert nosql._transaction is None
            mock_client.pipeline.assert_called_once()
            mock_pipeline.execute.assert_called_once()

            mock_client.pipeline.reset_mock()
            mock_pipeline.execute.reset_mock()

            with pytest.raises(ValueError):
                async with nosql.transaction():
                    raise ValueError("Test error")


class TestFirestoreSettings:
    def test_init(self) -> None:
        mock_config = MagicMock()
        mock_config.app.name = "test_app"
        mock_config.app.project = "test-project"

        settings = FirestoreSettings()
        settings.__init__(config=mock_config)

        assert settings.project_id == "test-project"

        settings = FirestoreSettings(
            project_id="custom-project",
            credentials_path="/path/to/credentials.json",
            emulator_host="localhost:8080",
        )
        settings.__init__(config=mock_config)

        assert settings.project_id == "custom-project"
        assert settings.credentials_path == "/path/to/credentials.json"
        assert settings.emulator_host == "localhost:8080"


class TestFirestore:
    @pytest.fixture
    def nosql(self) -> FirestoreNosql:
        instance = FirestoreNosql()
        instance.config = MagicMock()
        instance.logger = MagicMock()
        instance.config.nosql = MagicMock()
        instance.config.nosql.project_id = "test-project"
        instance.config.nosql.credentials_path = None
        instance.config.nosql.collection_prefix = "test_"
        return instance

    def test_client_property(self, nosql: FirestoreNosql) -> None:
        with patch(
            "acb.adapters.nosql.firestore.firestore.Client"
        ) as mock_client_class:
            mock_client = MagicMock(spec=firestore.Client)
            mock_client_class.return_value = mock_client

            client = nosql.client

            mock_client_class.assert_called_once_with(project="test-project")
            assert client == mock_client

            client2 = nosql.client
            assert client2 is client
            mock_client_class.assert_called_once()

    def test_db_property(self, nosql: FirestoreNosql) -> None:
        with patch.object(
            nosql, "client", MagicMock(spec=firestore.Client)
        ) as mock_client:
            db = nosql.db

            assert db == mock_client

    @pytest.mark.asyncio
    async def test_init(self, nosql: FirestoreNosql) -> None:
        with patch.object(
            nosql, "client", MagicMock(spec=firestore.Client)
        ) as mock_client:
            mock_client.collection.return_value = MagicMock()

            await nosql.init()

            mock_client.collection.assert_called_once_with("test")
            nosql.logger.info.assert_called_with(
                "Firestore connection initialized successfully"
            )

    @pytest.mark.asyncio
    async def test_init_error(self, nosql: FirestoreNosql) -> None:
        with patch.object(
            nosql, "client", MagicMock(spec=firestore.Client)
        ) as mock_client:
            mock_client.collection.side_effect = Exception("Connection error")

            with pytest.raises(Exception) as excinfo:
                await nosql.init()

            assert "Connection error" in str(excinfo.value)
            nosql.logger.error.assert_called_once()

    def test_get_collection_ref(self, nosql: FirestoreNosql) -> None:
        with patch.object(
            nosql, "client", MagicMock(spec=firestore.Client)
        ) as mock_client:
            mock_collection = MagicMock(spec=firestore.CollectionReference)
            mock_client.collection.return_value = mock_collection

            collection_ref = nosql._get_collection_ref("users")

            mock_client.collection.assert_called_once_with("test_users")
            assert collection_ref == mock_collection

    def test_convert_to_dict(self, nosql: FirestoreNosql) -> None:
        mock_doc = MagicMock(spec=firestore.DocumentSnapshot)
        mock_doc.exists = True
        mock_doc.id = "123"
        mock_doc.to_dict.return_value = {"name": "Test", "age": 30}
