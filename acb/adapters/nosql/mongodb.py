import typing as t
from contextlib import asynccontextmanager
from functools import cached_property
from uuid import UUID

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from acb.adapters import AdapterStatus
from acb.config import Config
from acb.depends import depends

from ._base import NosqlBase, NosqlBaseSettings

MODULE_ID = UUID("0197ff44-f2c7-7af0-9138-5e6a2b4d8c91")
MODULE_STATUS = AdapterStatus.STABLE


class NosqlSettings(NosqlBaseSettings):
    port: int | None = 27017
    connection_options: dict[str, t.Any] = {}

    @depends.inject
    def __init__(self, config: Config = depends(), **values: t.Any) -> None:
        super().__init__(**values)
        if not self.connection_string:
            host = self.host.get_secret_value()
            auth_part = ""
            if self.user and self.password:
                auth_part = f"{self.user.get_secret_value()}:{self.password.get_secret_value()}@"
            self.connection_string = (
                f"mongodb://{auth_part}{host}:{self.port}/{self.database}"
            )


class Nosql(NosqlBase):
    _transaction = None

    def __init__(self, **kwargs: t.Any) -> None:
        super().__init__(**kwargs)
        self._client = None
        self._db = None

    @cached_property
    def client(self) -> AsyncIOMotorClient[t.Any]:
        if self._client is None:
            self._client = AsyncIOMotorClient(
                self.config.nosql.connection_string,
                **self.config.nosql.connection_options,
            )
        return self._client

    @cached_property
    def db(self) -> t.Any:
        if self._db is None:
            self._db = self.client[self.config.nosql.database]
        return self._db

    async def init(self) -> None:
        self.logger.info(
            f"Initializing MongoDB connection to {self.config.nosql.connection_string}",
        )
        try:
            await init_beanie(database=self.db, document_models=[])
            self.logger.info("MongoDB connection initialized successfully")
        except Exception as e:
            self.logger.exception(f"Failed to initialize MongoDB connection: {e}")
            raise

    async def find(
        self,
        collection: str,
        filter: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> list[dict[str, t.Any]]:
        cursor = self.db[collection].find(filter, **kwargs)
        return await cursor.to_list(length=None)

    async def find_one(
        self,
        collection: str,
        filter: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> dict[str, t.Any] | None:
        return await self.db[collection].find_one(filter, **kwargs)

    async def insert_one(
        self,
        collection: str,
        document: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> t.Any:
        result = await self.db[collection].insert_one(document, **kwargs)
        return result.inserted_id

    async def insert_many(
        self,
        collection: str,
        documents: list[dict[str, t.Any]],
        **kwargs: t.Any,
    ) -> list[t.Any]:
        result = await self.db[collection].insert_many(documents, **kwargs)
        return result.inserted_ids

    async def update_one(
        self,
        collection: str,
        filter: dict[str, t.Any],
        update: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> t.Any:
        return await self.db[collection].update_one(filter, update, **kwargs)

    async def update_many(
        self,
        collection: str,
        filter: dict[str, t.Any],
        update: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> t.Any:
        return await self.db[collection].update_many(filter, update, **kwargs)

    async def delete_one(
        self,
        collection: str,
        filter: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> t.Any:
        return await self.db[collection].delete_one(filter, **kwargs)

    async def delete_many(
        self,
        collection: str,
        filter: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> t.Any:
        return await self.db[collection].delete_many(filter, **kwargs)

    async def count(
        self,
        collection: str,
        filter: dict[str, t.Any] | None = None,
        **kwargs: t.Any,
    ) -> int:
        return await self.db[collection].count_documents(filter or {}, **kwargs)

    async def aggregate(
        self,
        collection: str,
        pipeline: list[dict[str, t.Any]],
        **kwargs: t.Any,
    ) -> list[dict[str, t.Any]]:
        cursor = self.db[collection].aggregate(pipeline, **kwargs)
        return await cursor.to_list(length=None)

    @asynccontextmanager
    async def transaction(self) -> t.AsyncGenerator[None]:
        session = await self.client.start_session()
        try:
            async with session.start_transaction():
                self._transaction = session
                yield None
        except Exception as e:
            self.logger.exception(f"Transaction failed: {e}")
            try:
                if getattr(session, "has_ended", False) is False and getattr(
                    session,
                    "in_transaction",
                    False,
                ):
                    await session.abort_transaction()
            except Exception as abort_error:
                self.logger.exception(f"Failed to abort transaction: {abort_error}")
            raise
        finally:
            self._transaction = None
            try:
                await session.end_session()
            except Exception as close_error:
                self.logger.exception(f"Failed to close session: {close_error}")


depends.set(Nosql)
