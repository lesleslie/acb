from abc import abstractmethod

import typing as t
from contextlib import asynccontextmanager
from pydantic import SecretStr

from acb.cleanup import CleanupMixin
from acb.config import AdapterBase, Config, Settings
from acb.depends import Inject, depends
from acb.ssl_config import SSLConfigMixin


class NosqlBaseSettings(Settings, SSLConfigMixin):
    host: SecretStr = SecretStr("127.0.0.1")
    port: int | None = None
    user: SecretStr | None = None
    password: SecretStr | None = None
    database: str | None = None
    connection_string: str | None = None
    collection_prefix: str = ""

    auth_token: SecretStr | None = None
    token_type: str = "Bearer"

    ssl_cert_path: str | None = None
    ssl_key_path: str | None = None
    ssl_ca_path: str | None = None
    ssl_verify_mode: str = "required"
    tls_version: str = "TLSv1.2"

    connect_timeout: float | None = 30.0
    command_timeout: float | None = 30.0
    pool_timeout: float | None = 30.0

    @depends.inject
    def __init__(self, config: Inject[Config], **values: t.Any) -> None:
        super().__init__(**values)
        if not self.database:
            self.database = config.app.name if config.app else "default"


class NosqlProtocol(t.Protocol):
    @abstractmethod
    async def find(
        self,
        collection: str,
        filter: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> list[dict[str, t.Any]]:
        pass

    @abstractmethod
    async def find_one(
        self,
        collection: str,
        filter: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> dict[str, t.Any] | None:
        pass

    @abstractmethod
    async def insert_one(
        self,
        collection: str,
        document: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> t.Any:
        pass

    @abstractmethod
    async def insert_many(
        self,
        collection: str,
        documents: list[dict[str, t.Any]],
        **kwargs: t.Any,
    ) -> list[t.Any]:
        pass

    @abstractmethod
    async def update_one(
        self,
        collection: str,
        filter: dict[str, t.Any],
        update: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> t.Any:
        pass

    @abstractmethod
    async def update_many(
        self,
        collection: str,
        filter: dict[str, t.Any],
        update: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> t.Any:
        pass

    @abstractmethod
    async def delete_one(
        self,
        collection: str,
        filter: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> bool:
        pass

    @abstractmethod
    async def delete_many(
        self,
        collection: str,
        filter: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> int:
        pass

    @abstractmethod
    async def count(
        self,
        collection: str,
        filter: dict[str, t.Any] | None = None,
        **kwargs: t.Any,
    ) -> int:
        pass

    @abstractmethod
    async def aggregate(
        self,
        collection: str,
        pipeline: list[dict[str, t.Any]],
        **kwargs: t.Any,
    ) -> list[dict[str, t.Any]]:
        pass


class NosqlCollection:
    """Wrapper for NoSQL collection operations."""

    def __init__(self, adapter: "NosqlProtocol", name: str) -> None:
        self.adapter = adapter
        self.name = name

    async def find(
        self,
        filter: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> list[dict[str, t.Any]]:
        return await self.adapter.find(self.name, filter, **kwargs)

    async def find_one(
        self,
        filter: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> dict[str, t.Any] | None:
        return await self.adapter.find_one(self.name, filter, **kwargs)

    async def insert_one(self, document: dict[str, t.Any], **kwargs: t.Any) -> t.Any:
        return await self.adapter.insert_one(self.name, document, **kwargs)

    async def insert_many(
        self,
        documents: list[dict[str, t.Any]],
        **kwargs: t.Any,
    ) -> list[t.Any]:
        return await self.adapter.insert_many(self.name, documents, **kwargs)

    async def update_one(
        self,
        filter: dict[str, t.Any],
        update: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> t.Any:
        return await self.adapter.update_one(self.name, filter, update, **kwargs)

    async def update_many(
        self,
        filter: dict[str, t.Any],
        update: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> t.Any:
        return await self.adapter.update_many(self.name, filter, update, **kwargs)

    async def delete_one(self, filter: dict[str, t.Any], **kwargs: t.Any) -> bool:
        return await self.adapter.delete_one(self.name, filter, **kwargs)

    async def delete_many(self, filter: dict[str, t.Any], **kwargs: t.Any) -> int:
        return await self.adapter.delete_many(self.name, filter, **kwargs)

    async def count(
        self,
        filter: dict[str, t.Any] | None = None,
        **kwargs: t.Any,
    ) -> int:
        return await self.adapter.count(self.name, filter, **kwargs)

    async def aggregate(
        self,
        pipeline: list[dict[str, t.Any]],
        **kwargs: t.Any,
    ) -> list[dict[str, t.Any]]:
        return await self.adapter.aggregate(self.name, pipeline, **kwargs)


class NosqlBase(AdapterBase, CleanupMixin):  # type: ignore[misc]
    def __init__(self) -> None:
        super().__init__()
        self._collections: dict[str, NosqlCollection] = {}
        self._db: t.Any | None = None

    def __getattr__(self, name: str) -> NosqlCollection:
        if name not in self._collections:
            self._collections[name] = NosqlCollection(self, name)
        return self._collections[name]

    async def get_client(self) -> t.Any:
        return await self._ensure_client()

    async def get_db(self) -> t.Any:
        return await self._ensure_resource("db", self._create_db)

    async def _create_db(self) -> t.Any:
        msg = "Subclasses must implement _create_db()"
        raise NotImplementedError(msg)

    @abstractmethod
    async def init(self) -> None:
        pass

    @abstractmethod
    async def find(
        self,
        collection: str,
        filter: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> list[dict[str, t.Any]]:
        pass

    @abstractmethod
    async def find_one(
        self,
        collection: str,
        filter: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> dict[str, t.Any] | None:
        pass

    @abstractmethod
    async def insert_one(
        self,
        collection: str,
        document: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> t.Any:
        pass

    @abstractmethod
    async def insert_many(
        self,
        collection: str,
        documents: list[dict[str, t.Any]],
        **kwargs: t.Any,
    ) -> list[t.Any]:
        pass

    @abstractmethod
    async def update_one(
        self,
        collection: str,
        filter: dict[str, t.Any],
        update: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> t.Any:
        pass

    @abstractmethod
    async def update_many(
        self,
        collection: str,
        filter: dict[str, t.Any],
        update: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> t.Any:
        pass

    @abstractmethod
    async def delete_one(
        self,
        collection: str,
        filter: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> bool:
        pass

    @abstractmethod
    async def delete_many(
        self,
        collection: str,
        filter: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> int:
        pass

    @abstractmethod
    async def count(
        self,
        collection: str,
        filter: dict[str, t.Any] | None = None,
        **kwargs: t.Any,
    ) -> int:
        pass

    @abstractmethod
    async def aggregate(
        self,
        collection: str,
        pipeline: list[dict[str, t.Any]],
        **kwargs: t.Any,
    ) -> list[dict[str, t.Any]]:
        pass

    @asynccontextmanager
    async def transaction(self) -> t.AsyncGenerator[t.Any]:
        db = await self.get_db()
        yield db
