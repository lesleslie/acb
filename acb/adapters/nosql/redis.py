import typing as t
from contextlib import asynccontextmanager, suppress
from functools import cached_property
from uuid import UUID

import redis.asyncio as redis
from pydantic import field_validator
from redis_om import HashModel, Migrator, get_redis_connection
from acb.adapters import AdapterStatus
from acb.config import Config
from acb.depends import depends

from ._base import NosqlBase, NosqlBaseSettings

MODULE_ID = UUID("0197ff45-1b4f-7c20-8f3a-6e2d9a8c4b57")
MODULE_STATUS = AdapterStatus.STABLE


class NosqlSettings(NosqlBaseSettings):
    port: int | None = 6379
    db: int = 0
    cache_db: int = 0
    decode_responses: bool = True
    encoding: str = "utf-8"

    @field_validator("cache_db")
    @classmethod
    def cache_db_not_zero(cls, v: int) -> int:
        if v < 3 and v != 0:
            msg = "must be > 3 (0-2 are reserved)"
            raise ValueError(msg)
        return 0

    @depends.inject
    def __init__(self, config: Config = depends(), **values: t.Any) -> None:
        super().__init__(**values)
        if not self.connection_string:
            host = self.host.get_secret_value()
            auth_part = ""
            if self.password:
                auth_part = f":{self.password.get_secret_value()}"
            self.connection_string = f"redis://{auth_part}@{host}:{self.port}/{self.db}"


class Nosql(NosqlBase):
    _models: dict[str, type[HashModel]] = {}
    _client: t.Any = None
    _transaction: t.Any | None = None

    @cached_property
    def client(self) -> t.Any:
        if not self._client:
            self._client = redis.from_url(
                self.config.nosql.connection_string,
                decode_responses=self.config.nosql.decode_responses,
                encoding=self.config.nosql.encoding,
            )
        return self._client

    @cached_property
    def om_client(self) -> t.Any:
        return get_redis_connection(
            url=self.config.nosql.connection_string,
            decode_responses=True,
        )

    async def init(self) -> None:
        self.logger.info(
            f"Initializing Redis connection to {self.config.nosql.connection_string}",
        )
        try:
            await self.client.ping()
            self.logger.info("Redis connection initialized successfully")
            Migrator().run()
        except Exception as e:
            self.logger.exception(f"Failed to initialize Redis connection: {e}")
            raise

    def _get_key(self, collection: str, id: str | None = None) -> str:
        prefix = self.config.nosql.collection_prefix
        if id:
            return f"{prefix}{collection}:{id}"
        return f"{prefix}{collection}"

    async def find(
        self,
        collection: str,
        filter: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> list[dict[str, t.Any]]:
        results = []
        pattern = self._get_key(collection, "*")
        keys = await self.client.keys(pattern)
        limit = kwargs.get("limit")
        if limit is not None:
            keys = keys[:limit]
        for key in keys:
            data = await self.client.hgetall(key)
            if data:
                str_data = {
                    k.decode() if isinstance(k, bytes) else k: v.decode()
                    if isinstance(v, bytes)
                    else v
                    for k, v in data.items()
                }
                if self._matches_filter(str_data, filter):
                    key_str = key.decode() if isinstance(key, bytes) else key
                    str_data["_id"] = key_str.split(":")[-1]
                    results.append(str_data)
        return results

    def _matches_filter(self, data: dict[str, t.Any], filter: dict[str, t.Any]) -> bool:
        if not filter:
            return True
        for key, value in filter.items():
            if key not in data or data[key] != value:
                return False
        return True

    async def find_one(
        self,
        collection: str,
        filter: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> dict[str, t.Any] | None:
        if "_id" in filter:
            key = self._get_key(collection, filter["_id"])
            data = await self.client.hgetall(key)
            if data:
                str_data = {
                    k.decode() if isinstance(k, bytes) else k: v.decode()
                    if isinstance(v, bytes)
                    else v
                    for k, v in data.items()
                }
                str_data["_id"] = filter["_id"]
                return str_data
            return None
        results = await self.find(collection, filter, limit=1, **kwargs)
        return results[0] if results else None

    async def insert_one(
        self,
        collection: str,
        document: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> t.Any:
        doc_id = document.get(
            "_id",
            str(await self.client.incr(f"{collection}:id_counter")),
        )
        if "_id" in document:
            document = document.copy()
            del document["_id"]
        key = self._get_key(collection, doc_id)
        await self.client.hset(key, mapping=t.cast("dict[t.Any, t.Any]", document))
        await self.client.sadd(self._get_key(collection), doc_id)
        return doc_id

    async def insert_many(
        self,
        collection: str,
        documents: list[dict[str, t.Any]],
        **kwargs: t.Any,
    ) -> list[t.Any]:
        ids = []
        for doc in documents:
            doc_id = await self.insert_one(collection, doc, **kwargs)
            ids.append(doc_id)
        return ids

    async def update_one(
        self,
        collection: str,
        filter: dict[str, t.Any],
        update: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> t.Any:
        doc = await self.find_one(collection, filter)
        if not doc:
            return None
        doc_id = doc["_id"]
        key = self._get_key(collection, doc_id)
        if "$set" in update:
            await self.client.hset(
                key,
                mapping=t.cast("dict[t.Any, t.Any]", update["$set"]),
            )
        else:
            await self.client.hset(key, mapping=t.cast("dict[t.Any, t.Any]", update))
        return {"modified_count": 1}

    async def update_many(
        self,
        collection: str,
        filter: dict[str, t.Any],
        update: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> t.Any:
        docs = await self.find(collection, filter)
        modified_count = 0
        for doc in docs:
            doc_id = doc["_id"]
            key = self._get_key(collection, doc_id)
            if "$set" in update:
                await self.client.hset(
                    key,
                    mapping=t.cast("dict[t.Any, t.Any]", update["$set"]),
                )
            else:
                await self.client.hset(
                    key, mapping=t.cast("dict[t.Any, t.Any]", update)
                )
            modified_count += 1
        return {"modified_count": modified_count}

    async def delete_one(
        self,
        collection: str,
        filter: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> t.Any:
        doc = await self.find_one(collection, filter)
        if not doc:
            return {"deleted_count": 0}
        doc_id = doc["_id"]
        key = self._get_key(collection, doc_id)
        await self.client.delete(key)
        await self.client.srem(self._get_key(collection), doc_id)
        return {"deleted_count": 1}

    async def delete_many(
        self,
        collection: str,
        filter: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> t.Any:
        docs = await self.find(collection, filter)
        deleted_count = 0
        for doc in docs:
            doc_id = doc["_id"]
            key = self._get_key(collection, doc_id)
            await self.client.delete(key)
            await self.client.srem(self._get_key(collection), doc_id)
            deleted_count += 1
        return {"deleted_count": deleted_count}

    async def count(
        self,
        collection: str,
        filter: dict[str, t.Any] | None = None,
        **kwargs: t.Any,
    ) -> int:
        if not filter:
            return await self.client.scard(self._get_key(collection))
        docs = await self.find(collection, filter)
        return len(docs)

    async def aggregate(
        self,
        collection: str,
        pipeline: list[dict[str, t.Any]],
        **kwargs: t.Any,
    ) -> list[dict[str, t.Any]]:
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
    async def transaction(self) -> t.AsyncGenerator[None]:
        pipeline = self.client.pipeline()
        try:
            self._transaction = pipeline
            yield None
            await pipeline.execute()
        except Exception as e:
            self.logger.exception(f"Transaction failed: {e}")
            with suppress(Exception):
                await pipeline.discard()
            raise
        finally:
            self._transaction = None


depends.set(Nosql)
