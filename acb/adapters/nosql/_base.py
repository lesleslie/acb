import typing as t
from abc import abstractmethod
from contextlib import asynccontextmanager
from functools import cached_property

from pydantic import SecretStr
from acb.config import AdapterBase, Config, Settings
from acb.depends import depends


class NosqlBaseSettings(Settings):
    host: SecretStr = SecretStr("127.0.0.1")
    port: t.Optional[int] = None
    user: t.Optional[SecretStr] = None
    password: t.Optional[SecretStr] = None
    database: t.Optional[str] = None
    connection_string: t.Optional[str] = None
    collection_prefix: str = ""

    @depends.inject
    def __init__(self, config: Config = depends(), **values: t.Any) -> None:
        super().__init__(**values)
        if not self.database:
            self.database = config.app.name


class NosqlProtocol(t.Protocol):
    @abstractmethod
    async def find(
        self, collection: str, filter: t.Dict[str, t.Any], **kwargs: t.Any
    ) -> t.List[t.Dict[str, t.Any]]:
        pass

    @abstractmethod
    async def find_one(
        self, collection: str, filter: t.Dict[str, t.Any], **kwargs: t.Any
    ) -> t.Optional[t.Dict[str, t.Any]]:
        pass

    @abstractmethod
    async def insert_one(
        self, collection: str, document: t.Dict[str, t.Any], **kwargs: t.Any
    ) -> t.Any:
        pass

    @abstractmethod
    async def insert_many(
        self, collection: str, documents: t.List[t.Dict[str, t.Any]], **kwargs: t.Any
    ) -> t.List[t.Any]:
        pass

    @abstractmethod
    async def update_one(
        self,
        collection: str,
        filter: t.Dict[str, t.Any],
        update: t.Dict[str, t.Any],
        **kwargs: t.Any,
    ) -> t.Any:
        pass

    @abstractmethod
    async def update_many(
        self,
        collection: str,
        filter: t.Dict[str, t.Any],
        update: t.Dict[str, t.Any],
        **kwargs: t.Any,
    ) -> t.Any:
        pass

    @abstractmethod
    async def delete_one(
        self, collection: str, filter: t.Dict[str, t.Any], **kwargs: t.Any
    ) -> t.Any:
        pass

    @abstractmethod
    async def delete_many(
        self, collection: str, filter: t.Dict[str, t.Any], **kwargs: t.Any
    ) -> t.Any:
        pass

    @abstractmethod
    async def count(
        self,
        collection: str,
        filter: t.Optional[t.Dict[str, t.Any]] = None,
        **kwargs: t.Any,
    ) -> int:
        pass

    @abstractmethod
    async def aggregate(
        self, collection: str, pipeline: t.List[t.Dict[str, t.Any]], **kwargs: t.Any
    ) -> t.List[t.Dict[str, t.Any]]:
        pass


class NosqlCollection:
    def __init__(self, adapter: "NosqlBase", name: str) -> None:
        self.adapter: "NosqlBase" = adapter
        self.name: str = name

    async def find(
        self, filter: t.Optional[t.Dict[str, t.Any]] = None, **kwargs: t.Any
    ) -> t.List[t.Dict[str, t.Any]]:
        return await self.adapter.find(self.name, filter or {}, **kwargs)

    async def find_one(
        self, filter: t.Optional[t.Dict[str, t.Any]] = None, **kwargs: t.Any
    ) -> t.Optional[t.Dict[str, t.Any]]:
        return await self.adapter.find_one(self.name, filter or {}, **kwargs)

    async def insert_one(self, document: t.Dict[str, t.Any], **kwargs: t.Any) -> t.Any:
        return await self.adapter.insert_one(self.name, document, **kwargs)

    async def insert_many(
        self, documents: t.List[t.Dict[str, t.Any]], **kwargs: t.Any
    ) -> t.List[t.Any]:
        return await self.adapter.insert_many(self.name, documents, **kwargs)

    async def update_one(
        self, filter: t.Dict[str, t.Any], update: t.Dict[str, t.Any], **kwargs: t.Any
    ) -> t.Any:
        return await self.adapter.update_one(self.name, filter, update, **kwargs)

    async def update_many(
        self, filter: t.Dict[str, t.Any], update: t.Dict[str, t.Any], **kwargs: t.Any
    ) -> t.Any:
        return await self.adapter.update_many(self.name, filter, update, **kwargs)

    async def delete_one(self, filter: t.Dict[str, t.Any], **kwargs: t.Any) -> t.Any:
        return await self.adapter.delete_one(self.name, filter, **kwargs)

    async def delete_many(self, filter: t.Dict[str, t.Any], **kwargs: t.Any) -> t.Any:
        return await self.adapter.delete_many(self.name, filter, **kwargs)

    async def count(
        self, filter: t.Optional[t.Dict[str, t.Any]] = None, **kwargs: t.Any
    ) -> int:
        return await self.adapter.count(self.name, filter, **kwargs)

    async def aggregate(
        self, pipeline: t.List[t.Dict[str, t.Any]], **kwargs: t.Any
    ) -> t.List[t.Dict[str, t.Any]]:
        return await self.adapter.aggregate(self.name, pipeline, **kwargs)


class NosqlBase(AdapterBase):
    def __init__(self) -> None:
        super().__init__()
        self._collections: t.Dict[str, NosqlCollection] = {}
        self._client: t.Optional[t.Any] = None
        self._db: t.Optional[t.Any] = None

    def __getattr__(self, name: str) -> NosqlCollection:
        if name not in self._collections:
            self._collections[name] = NosqlCollection(self, name)
        return self._collections[name]

    @cached_property
    def client(self) -> t.Any:
        if self._client is None:
            raise ValueError("Client is not initialized. Call init() first.")
        return self._client

    @cached_property
    def db(self) -> t.Any:
        if self._db is None:
            raise ValueError("Database is not initialized. Call init() first.")
        return self._db

    @abstractmethod
    async def init(self) -> None:
        pass

    @abstractmethod
    async def find(
        self, collection: str, filter: t.Dict[str, t.Any], **kwargs: t.Any
    ) -> t.List[t.Dict[str, t.Any]]:
        pass

    @abstractmethod
    async def find_one(
        self, collection: str, filter: t.Dict[str, t.Any], **kwargs: t.Any
    ) -> t.Optional[t.Dict[str, t.Any]]:
        pass

    @abstractmethod
    async def insert_one(
        self, collection: str, document: t.Dict[str, t.Any], **kwargs: t.Any
    ) -> t.Any:
        pass

    @abstractmethod
    async def insert_many(
        self, collection: str, documents: t.List[t.Dict[str, t.Any]], **kwargs: t.Any
    ) -> t.List[t.Any]:
        pass

    @abstractmethod
    async def update_one(
        self,
        collection: str,
        filter: t.Dict[str, t.Any],
        update: t.Dict[str, t.Any],
        **kwargs: t.Any,
    ) -> t.Any:
        pass

    @abstractmethod
    async def update_many(
        self,
        collection: str,
        filter: t.Dict[str, t.Any],
        update: t.Dict[str, t.Any],
        **kwargs: t.Any,
    ) -> t.Any:
        pass

    @abstractmethod
    async def delete_one(
        self, collection: str, filter: t.Dict[str, t.Any], **kwargs: t.Any
    ) -> t.Any:
        pass

    @abstractmethod
    async def delete_many(
        self, collection: str, filter: t.Dict[str, t.Any], **kwargs: t.Any
    ) -> t.Any:
        pass

    @abstractmethod
    async def count(
        self,
        collection: str,
        filter: t.Optional[t.Dict[str, t.Any]] = None,
        **kwargs: t.Any,
    ) -> int:
        pass

    @abstractmethod
    async def aggregate(
        self, collection: str, pipeline: t.List[t.Dict[str, t.Any]], **kwargs: t.Any
    ) -> t.List[t.Dict[str, t.Any]]:
        pass

    @asynccontextmanager
    async def transaction(self) -> t.AsyncGenerator[None, None]:
        yield None
