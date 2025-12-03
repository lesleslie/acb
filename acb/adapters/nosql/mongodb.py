from __future__ import annotations

from functools import cached_property
from uuid import UUID

import typing as t
from contextlib import asynccontextmanager, suppress

try:
    from beanie import init_beanie
    from motor.motor_asyncio import AsyncIOMotorClient
except Exception:  # pragma: no cover - allow tests without Mongo deps
    import os as _os
    import sys as _sys

    if "pytest" in _sys.modules or _os.getenv("TESTING", "False").lower() == "true":
        from unittest.mock import MagicMock

        init_beanie = MagicMock()  # type: ignore[assignment, no-redef]
        AsyncIOMotorClient = MagicMock  # type: ignore[assignment, no-redef]
    else:
        raise
from acb.adapters import AdapterCapability, AdapterMetadata, AdapterStatus
from acb.depends import Inject, depends

from ._base import NosqlBase, NosqlBaseSettings

if t.TYPE_CHECKING:
    from acb.config import Config

MODULE_ID = UUID("0197ff44-f2c7-7af0-9138-5e6a2b4d8c91")
MODULE_STATUS = AdapterStatus.STABLE

MODULE_METADATA = AdapterMetadata(
    module_id=MODULE_ID,
    name="MongoDB",
    category="nosql",
    provider="mongodb",
    version="1.1.0",
    acb_min_version="0.18.0",
    author="lesleslie <les@wedgwoodwebworks.com>",
    created_date="2025-01-12",
    last_modified="2025-01-15",
    status=MODULE_STATUS,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.CONNECTION_POOLING,
        AdapterCapability.TRANSACTIONS,
        AdapterCapability.TLS_SUPPORT,
        AdapterCapability.BULK_OPERATIONS,
        AdapterCapability.SCHEMA_VALIDATION,
    ],
    required_packages=["motor", "beanie"],
    description="MongoDB NoSQL adapter with comprehensive TLS support",
    settings_class="NosqlSettings",
    config_example={
        "host": "localhost",
        "port": 27017,
        "user": "admin",
        "password": "your-db-password",  # pragma: allowlist secret
        "database": "myapp",
        "ssl_enabled": True,
        "ssl_cert_path": "/path/to/cert.pem",
        "ssl_key_path": "/path/to/key.pem",
        "ssl_ca_path": "/path/to/ca.pem",
    },
)


class NosqlSettings(NosqlBaseSettings):
    port: int | None = 27017
    connection_options: dict[str, t.Any] = {}

    def _build_ssl_options(self) -> dict[str, t.Any]:
        """Build connection options including SSL using unified configuration."""
        ssl_options = self._build_connection_timeouts()
        ssl_config = self._get_ssl_config()
        ssl_options.update(ssl_config.to_mongodb_kwargs())
        return ssl_options

    def _build_connection_timeouts(self) -> dict[str, t.Any]:
        timeouts = {}
        timeout_mapping = {
            "connect_timeout": ("connectTimeoutMS", 1000),
            "socket_timeout": ("socketTimeoutMS", 1000),
            "max_pool_size": ("maxPoolSize", 1),
            "min_pool_size": ("minPoolSize", 1),
        }
        for attr, (key, multiplier) in timeout_mapping.items():
            if value := getattr(self, attr):
                timeouts[key] = int(value * multiplier) if multiplier > 1 else value

        return timeouts

    @depends.inject
    def __init__(self, config: Inject[Config], **values: t.Any) -> None:
        super().__init__(**values)
        ssl_options = self._build_ssl_options()
        self.connection_options = ssl_options | self.connection_options
        if not self.connection_string:
            host = self.host.get_secret_value()
            auth_part = ""
            if self.user and self.password:
                auth_part = f"{self.user.get_secret_value()}:{self.password.get_secret_value()}@"
            elif self.auth_token:
                auth_part = f":{self.auth_token.get_secret_value()}@"
            protocol = "mongodb+srv" if self.ssl_enabled else "mongodb"
            self.connection_string = (
                f"{protocol}://{auth_part}{host}:{self.port}/{self.database}"
            )


class Nosql(NosqlBase):
    _transaction = None

    def __init__(self, **kwargs: t.Any) -> None:
        super().__init__(**kwargs)
        self._client: AsyncIOMotorClient[t.Any] | None = None  # type: ignore[assignment]
        self._db: t.Any = None

    @cached_property
    def client(self) -> AsyncIOMotorClient[t.Any]:
        if self._client is None:
            self._client = AsyncIOMotorClient(  # type: ignore[assignment]
                self.config.nosql.connection_string,
                **self.config.nosql.connection_options,
            )
        return self._client  # type: ignore[return-value]

    @cached_property
    def db(self) -> t.Any:
        if self._db is None:
            self._db = self.client[self.config.nosql.database]
        return self._db

    async def _cleanup_resources(self) -> None:
        """Enhanced MongoDB resource cleanup."""
        errors = []

        # Clean up any active transaction
        if self._transaction is not None:
            try:
                if hasattr(self._transaction, "end_session"):
                    await self._transaction.end_session()
                self._transaction = None
                self.logger.debug("Cleaned up MongoDB transaction session")
            except Exception as e:
                errors.append(f"Failed to cleanup transaction: {e}")

        # Clear cached properties
        if hasattr(self, "_db") and self._db is not None:
            self._db = None

        # Clean up MongoDB client
        if self._client is not None:
            try:
                self._client.close()
                self._client = None
                self.logger.debug("Successfully closed MongoDB client")
            except Exception as e:
                errors.append(f"Failed to close MongoDB client: {e}")

        # Clear resource cache manually (parent functionality)
        self._resource_cache.clear()

        if errors:
            self.logger.warning(f"MongoDB resource cleanup errors: {'; '.join(errors)}")

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
        result = await cursor.to_list(length=None)
        return t.cast("list[dict[str, t.Any]]", result)  # type: ignore[no-any-return]

    async def find_one(
        self,
        collection: str,
        filter: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> dict[str, t.Any] | None:
        result = await self.db[collection].find_one(filter, **kwargs)
        return t.cast("dict[str, t.Any] | None", result)  # type: ignore[no-any-return]

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
        return t.cast("list[t.Any]", result.inserted_ids)  # type: ignore[no-any-return]

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
        result = await self.db[collection].count_documents(filter or {}, **kwargs)
        return int(result)  # type: ignore[no-any-return]

    async def aggregate(
        self,
        collection: str,
        pipeline: list[dict[str, t.Any]],
        **kwargs: t.Any,
    ) -> list[dict[str, t.Any]]:
        cursor = self.db[collection].aggregate(pipeline, **kwargs)
        result = await cursor.to_list(length=None)
        return t.cast("list[dict[str, t.Any]]", result)  # type: ignore[no-any-return]

    @asynccontextmanager
    async def transaction(self) -> t.AsyncGenerator[None]:
        session = await self.client.start_session()
        try:
            async with session.start_transaction():
                self._transaction = session  # type: ignore[assignment]
                yield None
        except Exception as e:
            self.logger.exception(f"Transaction failed: {e}")
            with suppress(Exception):
                if getattr(session, "has_ended", False) is False and getattr(
                    session,
                    "end_session",
                    None,
                ):
                    await session.end_session()
            raise
        finally:
            self._transaction = None  # type: ignore[assignment]

    # Health checking removed as part of architectural simplification


depends.set(Nosql, "mongodb")
