from __future__ import annotations

import os
from functools import cached_property
from uuid import UUID

import typing as t
from contextlib import asynccontextmanager

try:
    from google.cloud import firestore
    from google.cloud.firestore_v1.base_query import FieldFilter
except Exception:  # pragma: no cover - allow tests without GCP installed
    import os as _os
    import sys as _sys

    if "pytest" in _sys.modules or _os.getenv("TESTING", "False").lower() == "true":
        from unittest.mock import MagicMock

        firestore = MagicMock()  # type: ignore[assignment, no-redef]
        FieldFilter = MagicMock()  # type: ignore[assignment, no-redef]
    else:
        raise
from acb.adapters import AdapterCapability, AdapterMetadata, AdapterStatus
from acb.depends import Inject, depends

from ._base import NosqlBase, NosqlBaseSettings

if t.TYPE_CHECKING:
    from acb.config import Config

MODULE_ID = UUID("0197ff45-0a82-7e10-bb46-9d3c8f15a7e2")
MODULE_STATUS = AdapterStatus.STABLE

MODULE_METADATA = AdapterMetadata(
    module_id=MODULE_ID,
    name="Firestore",
    category="nosql",
    provider="firestore",
    version="1.1.0",
    acb_min_version="0.18.0",
    author="lesleslie <les@wedgwoodwebworks.com>",
    created_date="2025-01-12",
    last_modified="2025-01-15",
    status=MODULE_STATUS,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.TRANSACTIONS,
        AdapterCapability.TLS_SUPPORT,
        AdapterCapability.BULK_OPERATIONS,
        AdapterCapability.SCHEMA_VALIDATION,
    ],
    required_packages=["google-cloud-firestore"],
    description="Google Firestore adapter with emulator TLS support",
    settings_class="NosqlSettings",
    config_example={
        "project_id": "my-project",
        "credentials_path": "/path/to/service-account.json",
        "emulator_host": "localhost:8080",
        "ssl_enabled": True,
    },
)


class NosqlSettings(NosqlBaseSettings):
    project_id: str | None = None
    credentials_path: str | None = None
    emulator_host: str | None = None

    def _setup_emulator_ssl_environment(self) -> None:
        """Setup SSL environment variables for Firestore emulator."""
        if not self.ssl_enabled:
            os.environ["FIRESTORE_EMULATOR_SSL"] = "false"
        else:
            os.environ["FIRESTORE_EMULATOR_SSL"] = "true"
            if self.ssl_cert_path:
                os.environ["FIRESTORE_EMULATOR_SSL_CERT"] = self.ssl_cert_path
            if self.ssl_key_path:
                os.environ["FIRESTORE_EMULATOR_SSL_KEY"] = self.ssl_key_path
            if self.ssl_ca_path:
                os.environ["FIRESTORE_EMULATOR_SSL_CA"] = self.ssl_ca_path

    @depends.inject
    def __init__(self, config: Inject[Config], **values: t.Any) -> None:
        super().__init__(**values)
        if not self.project_id:
            self.project_id = config.app.project if config.app else ""
        if self.emulator_host:
            os.environ["FIRESTORE_EMULATOR_HOST"] = self.emulator_host
            self._setup_emulator_ssl_environment()


class Nosql(NosqlBase):
    _transaction = None

    @cached_property
    def client(self) -> firestore.Client:
        if not self._client:
            kwargs = {}
            if self.config.nosql.project_id:
                kwargs["project"] = self.config.nosql.project_id
            if self.config.nosql.credentials_path:
                kwargs["credentials"] = self.config.nosql.credentials_path
            if self.config.nosql.emulator_host:
                pass
            elif self.config.nosql.ssl_enabled:
                if self.config.nosql.connect_timeout:
                    pass
            self._client = firestore.Client(**kwargs)
        return self._client

    @cached_property
    def db(self) -> firestore.Client:
        return self.client

    async def init(self) -> None:
        if self.config.nosql.emulator_host:
            ssl_status = (
                "SSL enabled" if self.config.nosql.ssl_enabled else "SSL disabled"
            )
            self.logger.info(
                f"Initializing Firestore emulator connection to {self.config.nosql.emulator_host} ({ssl_status})",
            )
        else:
            self.logger.info(
                f"Initializing Firestore connection for project {self.config.nosql.project_id}",
            )
        try:
            self.client.collection("test")
            self.logger.info("Firestore connection initialized successfully")
        except Exception as e:
            self.logger.exception(f"Failed to initialize Firestore connection: {e}")
            raise

    def _get_collection_ref(self, collection: str) -> firestore.CollectionReference:
        prefix = self.config.nosql.collection_prefix
        return self.client.collection(f"{prefix}{collection}")

    def _convert_to_dict(self, doc: firestore.DocumentSnapshot) -> dict[str, t.Any]:
        if not doc.exists:
            return {}
        data = doc.to_dict()  # type: ignore[union-attr]
        if data is None:
            data = {}
        data["_id"] = doc.id  # type: ignore[index]
        return t.cast("dict[str, t.Any]", data)  # type: ignore[return-value]

    def _prepare_document(self, document: dict[str, t.Any]) -> dict[str, t.Any]:
        if "_id" in document:
            document = document.copy()
            del document["_id"]
        return document

    async def find(
        self,
        collection: str,
        filter: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> list[dict[str, t.Any]]:
        collection_ref = self._get_collection_ref(collection)
        query = collection_ref
        for key, value in filter.items():
            if key == "_id":
                continue
            query = query.where(filter=FieldFilter(key, "==", value))
        if "limit" in kwargs:
            query = query.limit(kwargs["limit"])
        if "order_by" in kwargs:
            for field in kwargs["order_by"]:
                direction = (
                    firestore.Query.DESCENDING
                    if field.startswith("-")
                    else firestore.Query.ASCENDING
                )
                field_name = field.removeprefix("-")
                query = query.order_by(field_name, direction=direction)
        docs = query.stream()
        results = [self._convert_to_dict(doc) for doc in docs]
        if "_id" in filter:
            results = [doc for doc in results if doc.get("_id") == filter["_id"]]
        return results

    async def find_one(
        self,
        collection: str,
        filter: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> dict[str, t.Any] | None:
        if "_id" in filter:
            doc_ref = self._get_collection_ref(collection).document(filter["_id"])
            doc = doc_ref.get()
            if doc.exists:
                return self._convert_to_dict(doc)
            return None
        results = await self.find(collection, filter, limit=1, **kwargs)
        return results[0] if results else None

    async def insert_one(
        self,
        collection: str,
        document: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> t.Any:
        collection_ref = self._get_collection_ref(collection)
        if "_id" in document:
            doc_id = document["_id"]
            doc_ref = collection_ref.document(doc_id)
            doc_ref.set(self._prepare_document(document))
        else:
            doc_ref = collection_ref.add(document)[1]
            doc_id = doc_ref.id
        return doc_id

    async def insert_many(
        self,
        collection: str,
        documents: list[dict[str, t.Any]],
        **kwargs: t.Any,
    ) -> list[t.Any]:
        ids = []
        batch = self.client.batch()
        collection_ref = self._get_collection_ref(collection)
        for doc in documents:
            if "_id" in doc:
                doc_id = doc["_id"]
                doc_ref = collection_ref.document(doc_id)
                batch.set(doc_ref, self._prepare_document(doc))
            else:
                doc_ref = collection_ref.document()
                batch.set(doc_ref, doc)
                doc_id = doc_ref.id
            ids.append(doc_id)
        batch.commit()
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
            return {"modified_count": 0}
        doc_id = doc["_id"]
        doc_ref = self._get_collection_ref(collection).document(doc_id)
        if "$set" in update:
            doc_ref.update(update["$set"])
        else:
            doc_ref.update(update)
        return {"modified_count": 1}

    async def update_many(
        self,
        collection: str,
        filter: dict[str, t.Any],
        update: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> t.Any:
        docs = await self.find(collection, filter)
        if not docs:
            return {"modified_count": 0}
        batch = self.client.batch()
        collection_ref = self._get_collection_ref(collection)
        for doc in docs:
            doc_id = doc["_id"]
            doc_ref = collection_ref.document(doc_id)
            if "$set" in update:
                batch.update(doc_ref, update["$set"])
            else:
                batch.update(doc_ref, update)
        batch.commit()
        return {"modified_count": len(docs)}

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
        doc_ref = self._get_collection_ref(collection).document(doc_id)
        doc_ref.delete()
        return {"deleted_count": 1}

    async def delete_many(
        self,
        collection: str,
        filter: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> t.Any:
        docs = await self.find(collection, filter)
        if not docs:
            return {"deleted_count": 0}
        batch = self.client.batch()
        collection_ref = self._get_collection_ref(collection)
        for doc in docs:
            doc_id = doc["_id"]
            doc_ref = collection_ref.document(doc_id)
            batch.delete(doc_ref)
        batch.commit()
        return {"deleted_count": len(docs)}

    async def count(
        self,
        collection: str,
        filter: dict[str, t.Any] | None = None,
        **kwargs: t.Any,
    ) -> int:
        docs = await self.find(collection, filter or {})
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
                filter_dict = stage["$match"]
                docs = [
                    doc
                    for doc in docs
                    if all((doc.get(k) == v for k, v in filter_dict.items()))
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
        transaction = self.client.transaction()
        try:
            self._transaction = transaction
            transaction.__enter__()
            try:
                yield None
            finally:
                transaction.__exit__(None, None, None)
        except Exception as e:
            self.logger.exception(f"Transaction failed: {e}")
            raise
        finally:
            self._transaction = None


depends.set(Nosql, "firestore")
