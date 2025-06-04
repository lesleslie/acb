import typing as t
from unittest.mock import AsyncMock, MagicMock

from acb.adapters.nosql._base import NosqlBase, NosqlCollection


class MockCollection:
    def __init__(self, name: str, nosql: "MockNoSQL") -> None:
        self.name = name
        self.nosql = nosql
        self.data: list[dict[str, t.Any]] = []

    async def find(
        self, filter: dict[str, t.Any] | None = None, **kwargs: t.Any
    ) -> "MockCursor":
        filter = filter or {}

        result = []
        for doc in self.data:
            match = True
            for key, value in filter.items():
                if key not in doc or doc[key] != value:
                    match = False
                    break
            if match:
                result.append(doc)

        if "sort" in kwargs:
            sort_fields = kwargs["sort"]
            for field, direction in reversed(sort_fields):
                result.sort(key=lambda x: x.get(field, ""), reverse=(direction == -1))

        if "limit" in kwargs:
            result = result[: kwargs["limit"]]

        return MockCursor(result)

    async def find_one(
        self, filter: dict[str, t.Any] | None = None, **kwargs: t.Any
    ) -> dict[str, t.Any] | None:
        filter = filter or {}
        cursor = await self.find(filter, **kwargs)
        results = await cursor.to_list(1)
        return results[0] if results else None

    async def insert_one(
        self, document: dict[str, t.Any], **kwargs: t.Any
    ) -> MagicMock:
        self.data.append(document)
        result = MagicMock()
        result.inserted_id = document.get("_id", "test_id")
        return result

    async def insert_many(
        self, documents: list[dict[str, t.Any]], **kwargs: t.Any
    ) -> MagicMock:
        for doc in documents:
            self.data.append(doc)
        result = MagicMock()
        result.inserted_ids = [
            doc.get("_id", f"test_id_{i}") for i, doc in enumerate(documents)
        ]
        return result

    async def update_one(
        self, filter: dict[str, t.Any], update: dict[str, t.Any], **kwargs: t.Any
    ) -> MagicMock:
        doc = await self.find_one(filter)
        if doc:
            if "$set" in update:
                for key, value in update["$set"].items():
                    doc[key] = value

            for key, value in update.items():
                if not key.startswith("$"):
                    doc[key] = value

            result = MagicMock()
            result.modified_count = 1
            return result

        result = MagicMock()
        result.modified_count = 0
        return result

    async def update_many(
        self, filter: dict[str, t.Any], update: dict[str, t.Any], **kwargs: t.Any
    ) -> MagicMock:
        cursor = await self.find(filter)
        docs = await cursor.to_list()
        modified_count = 0

        for doc in docs:
            if "$set" in update:
                for key, value in update["$set"].items():
                    doc[key] = value

            for key, value in update.items():
                if not key.startswith("$"):
                    doc[key] = value

            modified_count += 1

        result = MagicMock()
        result.modified_count = modified_count
        return result

    async def delete_one(self, filter: dict[str, t.Any], **kwargs: t.Any) -> MagicMock:
        doc = await self.find_one(filter)
        if doc:
            self.data.remove(doc)
            result = MagicMock()
            result.deleted_count = 1
            return result

        result = MagicMock()
        result.deleted_count = 0
        return result

    async def delete_many(self, filter: dict[str, t.Any], **kwargs: t.Any) -> MagicMock:
        cursor = await self.find(filter)
        docs = await cursor.to_list()
        deleted_count = 0

        for doc in docs:
            self.data.remove(doc)
            deleted_count += 1

        result = MagicMock()
        result.deleted_count = deleted_count
        return result

    async def count(
        self, filter: dict[str, t.Any] | None = None, **kwargs: t.Any
    ) -> int:
        filter = filter or {}
        cursor = await self.find(filter)
        docs = await cursor.to_list()
        return len(docs)

    async def aggregate(
        self, pipeline: list[dict[str, t.Any]], **kwargs: t.Any
    ) -> "MockCursor":
        return MockCursor(self.data)

    async def create_index(self, keys: list[tuple[str, int]], **kwargs: t.Any) -> str:
        return "mock_index"


class MockCursor:
    def __init__(self, data: list[dict[str, t.Any]]) -> None:
        self.data = data

    async def to_list(self, length: int | None = None) -> list[dict[str, t.Any]]:
        if length is None:
            return self.data
        return self.data[:length]


class MockNoSQL(NosqlBase):
    def __init__(self) -> None:
        super().__init__()
        self._mock_collections: dict[str, MockCollection] = {}
        self._initialized = True
        self.config = MagicMock()
        self.config.app.name = "test"

    def __getattr__(self, name: str) -> NosqlCollection:
        if name not in self._mock_collections:
            collection = MockCollection(name, self)
            self._mock_collections[name] = collection
            self._collections[name] = t.cast(NosqlCollection, collection)
        return t.cast(NosqlCollection, self._mock_collections[name])

    async def init(self) -> None:
        self._initialized = True

    async def start_transaction(self, **kwargs: t.Any) -> AsyncMock:
        return AsyncMock()

    async def find(
        self, collection: str, filter: dict[str, t.Any], **kwargs: t.Any
    ) -> list[dict[str, t.Any]]:
        coll = self._mock_collections.get(collection, MockCollection(collection, self))
        cursor = await coll.find(filter, **kwargs)
        return await cursor.to_list()

    async def find_one(
        self, collection: str, filter: dict[str, t.Any], **kwargs: t.Any
    ) -> dict[str, t.Any] | None:
        coll = self._mock_collections.get(collection, MockCollection(collection, self))
        return await coll.find_one(filter, **kwargs)

    async def insert_one(
        self, collection: str, document: dict[str, t.Any], **kwargs: t.Any
    ) -> t.Any:
        coll = self._mock_collections.get(collection, MockCollection(collection, self))
        return await coll.insert_one(document, **kwargs)

    async def insert_many(
        self, collection: str, documents: list[dict[str, t.Any]], **kwargs: t.Any
    ) -> list[t.Any]:
        coll = self._mock_collections.get(collection, MockCollection(collection, self))
        result = await coll.insert_many(documents, **kwargs)
        return result.inserted_ids

    async def update_one(
        self,
        collection: str,
        filter: dict[str, t.Any],
        update: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> t.Any:
        coll = self._mock_collections.get(collection, MockCollection(collection, self))
        return await coll.update_one(filter, update, **kwargs)

    async def update_many(
        self,
        collection: str,
        filter: dict[str, t.Any],
        update: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> t.Any:
        coll = self._mock_collections.get(collection, MockCollection(collection, self))
        return await coll.update_many(filter, update, **kwargs)

    async def delete_one(
        self, collection: str, filter: dict[str, t.Any], **kwargs: t.Any
    ) -> t.Any:
        coll = self._mock_collections.get(collection, MockCollection(collection, self))
        return await coll.delete_one(filter, **kwargs)

    async def delete_many(
        self, collection: str, filter: dict[str, t.Any], **kwargs: t.Any
    ) -> t.Any:
        coll = self._mock_collections.get(collection, MockCollection(collection, self))
        return await coll.delete_many(filter, **kwargs)

    async def count(
        self,
        collection: str,
        filter: dict[str, t.Any] | None = None,
        **kwargs: t.Any,
    ) -> int:
        coll = self._mock_collections.get(collection, MockCollection(collection, self))
        return await coll.count(filter, **kwargs)

    async def aggregate(
        self, collection: str, pipeline: list[dict[str, t.Any]], **kwargs: t.Any
    ) -> list[dict[str, t.Any]]:
        coll = self._mock_collections.get(collection, MockCollection(collection, self))
        cursor = await coll.aggregate(pipeline, **kwargs)
        return await cursor.to_list()
