from uuid import UUID

import typing as t
from pydantic import SecretStr

from acb.adapters import AdapterCapability, AdapterMetadata, AdapterStatus
from acb.depends import depends

from ._base import VectorBase, VectorBaseSettings, VectorDocument, VectorSearchResult

MODULE_ID = UUID("0197ff50-2345-7891-bcde-ef0123456790")
MODULE_STATUS = AdapterStatus.STABLE

MODULE_METADATA = AdapterMetadata(
    module_id=MODULE_ID,
    name="Pinecone Vector Database",
    category="vector",
    provider="pinecone",
    version="1.0.0",
    acb_min_version="0.19.1",
    author="lesleslie <les@wedgwoodwebworks.com>",
    created_date="2025-01-21",
    last_modified="2025-01-21",
    status=MODULE_STATUS,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.BULK_OPERATIONS,
        AdapterCapability.CONNECTION_POOLING,
        AdapterCapability.CACHING,
        AdapterCapability.METRICS,
        AdapterCapability.ENCRYPTION,
        AdapterCapability.SCHEMA_VALIDATION,
    ],
    required_packages=["pinecone-client>=3.0.0"],
    description="Pinecone managed vector database adapter with enterprise-grade scaling",
    settings_class="VectorSettings",
    config_example={
        "api_key": "your-pinecone-api-key",
        "environment": "us-west1-gcp-free",
        "index_name": "your-index",
        "default_dimension": 1536,
        "default_distance_metric": "cosine",
    },
)


class VectorSettings(VectorBaseSettings):
    """Pinecone vector adapter settings."""

    api_key: SecretStr
    environment: str = "us-west1-gcp-free"
    index_name: str = "default"
    serverless: bool = True
    cloud: str = "aws"
    region: str = "us-east-1"

    # Index configuration
    metric: str = "cosine"  # cosine, euclidean, dotproduct
    pod_type: str = "p1.x1"  # For non-serverless indexes
    replicas: int = 1
    shards: int = 1

    # Upsert configuration
    upsert_batch_size: int = 100
    upsert_max_retries: int = 3
    upsert_timeout: float = 30.0


class Vector(VectorBase):
    """Pinecone vector adapter implementation."""

    async def _create_client(self) -> t.Any:
        """Create Pinecone client."""
        import pinecone

        # Initialize Pinecone client
        pc = pinecone.Pinecone(
            api_key=self.config.vector.api_key.get_secret_value(),
        )

        self.logger.debug("Pinecone client initialized successfully")
        return pc

    async def _ensure_client(self) -> t.Any:
        """Ensure Pinecone client is available."""
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _get_index(self) -> t.Any:
        """Get Pinecone index instance."""
        client = await self._ensure_client()
        return client.Index(self.config.vector.index_name)

    async def init(self) -> None:
        """Initialize Pinecone vector adapter."""
        self.logger.info("Initializing Pinecone vector adapter")

        client = await self._ensure_client()

        # Check if index exists, create if needed
        try:
            client.describe_index(self.config.vector.index_name)
            self.logger.debug(f"Using existing index: {self.config.vector.index_name}")
        except Exception:
            self.logger.info(
                f"Index {self.config.vector.index_name} not found, creating...",
            )
            await self._create_default_index()

        self.logger.info("Pinecone vector adapter initialized successfully")

    async def _create_default_index(self) -> None:
        """Create default index if it doesn't exist."""
        client = await self._ensure_client()

        if self.config.vector.serverless:
            spec = {
                "serverless": {
                    "cloud": self.config.vector.cloud,
                    "region": self.config.vector.region,
                },
            }
        else:
            spec = {
                "pod": {
                    "environment": self.config.vector.environment,
                    "pod_type": self.config.vector.pod_type,
                    "pods": 1,
                    "replicas": self.config.vector.replicas,
                    "shards": self.config.vector.shards,
                },
            }

        client.create_index(
            name=self.config.vector.index_name,
            dimension=self.config.vector.default_dimension,
            metric=self.config.vector.metric,
            spec=spec,
        )

        self.logger.info(f"Created index: {self.config.vector.index_name}")

    async def search(
        self,
        collection: str,  # In Pinecone, this is namespace
        query_vector: list[float],
        limit: int = 10,
        filter_expr: dict[str, t.Any] | None = None,
        include_vectors: bool = False,
        **kwargs: t.Any,
    ) -> list[VectorSearchResult]:
        """Perform vector similarity search in Pinecone."""
        index = await self._get_index()

        try:
            # Build query parameters
            query_params = {
                "vector": query_vector,
                "top_k": limit,
                "include_metadata": True,
                "include_values": include_vectors,
            }

            # Add namespace if collection is specified
            if collection and collection != "default":
                query_params["namespace"] = collection

            # Add filter if provided
            if filter_expr:
                query_params["filter"] = filter_expr

            # Perform query
            response = index.query(**query_params)

            # Convert to VectorSearchResult
            results = []
            for match in response.get("matches", []):
                result = VectorSearchResult(
                    id=match["id"],
                    score=float(match["score"]),
                    metadata=match.get("metadata", {}),
                    vector=match.get("values") if include_vectors else None,
                )
                results.append(result)

            return results

        except Exception as e:
            self.logger.exception(f"Pinecone search failed: {e}")
            return []

    async def insert(
        self,
        collection: str,
        documents: list[VectorDocument],
        **kwargs: t.Any,
    ) -> list[str]:
        """Insert documents with vectors into Pinecone."""
        return await self.upsert(collection, documents, **kwargs)

    def _prepare_pinecone_vector(
        self,
        doc: VectorDocument,
        index: int,
    ) -> tuple[str, dict[str, t.Any]]:
        """Prepare a single document as Pinecone vector. Returns (doc_id, vector_data)."""
        doc_id = doc.id or f"vec_{index}"

        vector_data: dict[str, t.Any] = {
            "id": doc_id,
            "values": doc.vector,
        }

        if doc.metadata:
            vector_data["metadata"] = doc.metadata  # type: ignore[assignment]

        return doc_id, vector_data

    def _prepare_all_vectors(
        self,
        documents: list[VectorDocument],
    ) -> tuple[list[str], list[dict[str, t.Any]]]:
        """Prepare all documents as Pinecone vectors. Returns (doc_ids, vectors)."""
        document_ids: list[str] = []
        vectors: list[dict[str, t.Any]] = []

        for idx, doc in enumerate(documents):
            doc_id, vector_data = self._prepare_pinecone_vector(doc, idx)
            document_ids.append(doc_id)
            vectors.append(vector_data)

        return document_ids, vectors

    async def _upsert_batch(
        self,
        index: t.Any,
        batch: list[dict[str, t.Any]],
        namespace: str | None,
        batch_num: int,
    ) -> None:
        """Upsert a single batch to Pinecone."""
        upsert_params: dict[str, t.Any] = {"vectors": batch}
        if namespace:
            upsert_params["namespace"] = namespace  # type: ignore[assignment]

        response = index.upsert(**upsert_params)

        if not response.get("upserted_count"):
            self.logger.warning(f"Upsert batch {batch_num} failed")

    async def upsert(
        self,
        collection: str,
        documents: list[VectorDocument],
        **kwargs: t.Any,
    ) -> list[str]:
        """Upsert documents with vectors into Pinecone."""
        index = await self._get_index()

        try:
            # Prepare vectors for upsert
            document_ids, vectors = self._prepare_all_vectors(documents)

            # Batch upsert
            batch_size = self.config.vector.upsert_batch_size
            namespace = collection if collection != "default" else None

            for i in range(0, len(vectors), batch_size):
                batch = vectors[i : i + batch_size]
                await self._upsert_batch(index, batch, namespace, i // batch_size + 1)

            return document_ids

        except Exception as e:
            self.logger.exception(f"Pinecone upsert failed: {e}")
            return []

    async def delete(
        self,
        collection: str,
        ids: list[str],
        **kwargs: t.Any,
    ) -> bool:
        """Delete documents by IDs from Pinecone."""
        index = await self._get_index()

        try:
            delete_params = {"ids": ids}
            if collection and collection != "default":
                delete_params["namespace"] = collection  # type: ignore[assignment]

            index.delete(**delete_params)
            return True  # Pinecone delete doesn't return detailed status

        except Exception as e:
            self.logger.exception(f"Pinecone delete failed: {e}")
            return False

    async def get(
        self,
        collection: str,
        ids: list[str],
        include_vectors: bool = False,
        **kwargs: t.Any,
    ) -> list[VectorDocument]:
        """Retrieve documents by IDs from Pinecone."""
        index = await self._get_index()

        try:
            fetch_params = {
                "ids": ids,
                "include_metadata": True,
                "include_values": include_vectors,
            }

            if collection and collection != "default":
                fetch_params["namespace"] = collection

            response = index.fetch(**fetch_params)

            documents = []
            for doc_id, vector_data in response.get("vectors", {}).items():
                doc = VectorDocument(
                    id=doc_id,
                    vector=vector_data.get("values", []) if include_vectors else [],
                    metadata=vector_data.get("metadata", {}),
                )
                documents.append(doc)

            return documents

        except Exception as e:
            self.logger.exception(f"Pinecone fetch failed: {e}")
            return []

    async def count(
        self,
        collection: str,
        filter_expr: dict[str, t.Any] | None = None,
        **kwargs: t.Any,
    ) -> int:
        """Count documents in Pinecone namespace."""
        index = await self._get_index()

        try:
            # Pinecone doesn't have a direct count method
            # We need to use describe_index_stats
            describe_params = {}
            if filter_expr:
                describe_params["filter"] = filter_expr

            stats = index.describe_index_stats(**describe_params)

            if collection and collection != "default":
                namespace_stats = stats.get("namespaces", {}).get(collection, {})
                return namespace_stats.get("vector_count", 0)
            return stats.get("total_vector_count", 0)

        except Exception as e:
            self.logger.exception(f"Pinecone count failed: {e}")
            return 0

    async def create_collection(
        self,
        name: str,
        dimension: int,
        distance_metric: str = "cosine",
        **kwargs: t.Any,
    ) -> bool:
        """Create a new collection (namespace) in Pinecone."""
        # In Pinecone, namespaces are created implicitly when inserting vectors
        # The index itself needs to be created at the account level
        # This method is mainly for compatibility with the base interface
        self.logger.info(
            f"Namespace '{name}' will be created implicitly on first insert",
        )
        return True

    async def delete_collection(
        self,
        name: str,
        **kwargs: t.Any,
    ) -> bool:
        """Delete a collection (namespace) in Pinecone."""
        index = await self._get_index()

        try:
            # Delete all vectors in the namespace
            if name and name != "default":
                index.delete(delete_all=True, namespace=name)
            else:
                index.delete(delete_all=True)

            return True

        except Exception as e:
            self.logger.exception(f"Pinecone namespace delete failed: {e}")
            return False

    async def list_collections(self, **kwargs: t.Any) -> list[str]:
        """List all collections (namespaces) in Pinecone."""
        index = await self._get_index()

        try:
            stats = index.describe_index_stats()
            namespaces = list(stats.get("namespaces", {}).keys())

            # Include default namespace if it has vectors
            if stats.get("total_vector_count", 0) > sum(
                ns.get("vector_count", 0) for ns in stats.get("namespaces", {}).values()
            ):
                namespaces.append("default")

            return namespaces

        except Exception as e:
            self.logger.exception(f"Pinecone list namespaces failed: {e}")
            return []

    def has_capability(self, capability: str) -> bool:
        """Check if Pinecone adapter supports a specific capability."""
        supported_capabilities = {
            "vector_search",
            "batch_operations",
            "metadata_filtering",
            "indexing",
            "connection_pooling",
            "async_operations",
            "caching",
            "metrics",
            "encryption",
            "schema_validation",
        }
        return capability in supported_capabilities


depends.set(Vector, "pinecone")
