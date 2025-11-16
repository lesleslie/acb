from uuid import UUID

import typing as t
from pydantic import SecretStr

from acb.adapters import AdapterCapability, AdapterMetadata, AdapterStatus
from acb.depends import depends

from ._base import VectorBase, VectorBaseSettings, VectorDocument, VectorSearchResult

MODULE_ID = UUID("0197ff50-4567-7893-defa-ef0123456792")
MODULE_STATUS = AdapterStatus.STABLE

MODULE_METADATA = AdapterMetadata(
    module_id=MODULE_ID,
    name="Qdrant Vector Database",
    category="vector",
    provider="qdrant",
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
        AdapterCapability.STREAMING,
    ],
    required_packages=["qdrant-client>=1.7.0"],
    description="Qdrant high-performance vector similarity search engine",
    settings_class="VectorSettings",
    config_example={
        "url": "http://localhost:6333",
        "api_key": "your-qdrant-api-key",
        "default_collection": "documents",
        "default_dimension": 1536,
        "default_distance_metric": "cosine",
    },
)


class VectorSettings(VectorBaseSettings):
    """Qdrant vector adapter settings."""

    url: str = "http://localhost:6333"
    api_key: SecretStr | None = None

    # Connection settings
    grpc_port: int | None = None
    prefer_grpc: bool = True
    https: bool | None = None

    # Performance settings
    timeout: float = 30.0

    # Collection settings
    default_collection: str = "documents"

    # Vector configuration
    on_disk_vectors: bool = False
    hnsw_config: dict[str, t.Any] = {
        "m": 16,
        "ef_construct": 100,
        "full_scan_threshold": 10000,
        "max_indexing_threads": 0,  # 0 = auto
    }

    # Quantization settings
    enable_quantization: bool = False
    quantization_config: dict[str, t.Any] = {
        "scalar": {
            "type": "int8",
            "quantile": 0.99,
            "always_ram": True,
        },
    }


class Vector(VectorBase):
    """Qdrant vector adapter implementation."""

    async def _create_client(self) -> t.Any:
        """Create Qdrant client."""
        from qdrant_client import AsyncQdrantClient

        # Build connection parameters
        connection_params = {
            "url": self.config.vector.url,
            "timeout": self.config.vector.timeout,
            "prefer_grpc": self.config.vector.prefer_grpc,
        }

        # Add API key if provided
        if self.config.vector.api_key:
            connection_params["api_key"] = self.config.vector.api_key.get_secret_value()

        # Add gRPC port if specified
        if self.config.vector.grpc_port:
            connection_params["grpc_port"] = self.config.vector.grpc_port

        # Add HTTPS setting if specified
        if self.config.vector.https is not None:
            connection_params["https"] = self.config.vector.https

        # Create async client
        client = AsyncQdrantClient(**connection_params)

        self.logger.debug("Qdrant client initialized successfully")
        return client

    async def _ensure_client(self) -> t.Any:
        """Ensure Qdrant client is available."""
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def init(self) -> None:
        """Initialize Qdrant vector adapter."""
        self.logger.info("Initializing Qdrant vector adapter")

        client = await self._ensure_client()

        # Check connection
        try:
            health_info = await client.get_cluster_info()
            self.logger.debug(f"Qdrant cluster status: {health_info}")
        except Exception as e:
            self.logger.exception(f"Failed to connect to Qdrant: {e}")
            raise

        self.logger.info("Qdrant vector adapter initialized successfully")

    async def _ensure_collection_exists(
        self,
        collection_name: str,
        dimension: int | None = None,
        distance_metric: str = "Cosine",
    ) -> bool:
        """Ensure Qdrant collection exists, create if needed."""
        client = await self._ensure_client()

        try:
            # Check if collection exists
            collections = await client.get_collections()
            existing_collections = [col.name for col in collections.collections]

            if collection_name in existing_collections:
                return True

            if dimension is None:
                dimension = self.config.vector.default_dimension

            # Import required types
            from qdrant_client.models import Distance, VectorParams

            # Map distance metric
            distance_map = {
                "cosine": Distance.COSINE,
                "euclidean": Distance.EUCLID,
                "dot_product": Distance.DOT,
                "manhattan": Distance.MANHATTAN,
            }

            distance = distance_map.get(distance_metric.lower(), Distance.COSINE)

            # Create vector configuration
            vectors_config = VectorParams(
                size=dimension,
                distance=distance,
                on_disk=self.config.vector.on_disk_vectors,
            )

            # Create HNSW configuration
            from qdrant_client.models import HnswConfigDiff

            hnsw_config = HnswConfigDiff(
                m=self.config.vector.hnsw_config.get("m", 16),
                ef_construct=self.config.vector.hnsw_config.get("ef_construct", 100),
                full_scan_threshold=self.config.vector.hnsw_config.get(
                    "full_scan_threshold",
                    10000,
                ),
                max_indexing_threads=self.config.vector.hnsw_config.get(
                    "max_indexing_threads",
                    0,
                ),
            )

            # Create quantization config if enabled
            quantization_config = None
            if self.config.vector.enable_quantization:
                from qdrant_client.models import (
                    ScalarQuantization,
                    ScalarQuantizationConfig,
                    ScalarType,
                )

                quantization_config = ScalarQuantization(
                    scalar=ScalarQuantizationConfig(
                        type=ScalarType.INT8,
                        quantile=self.config.vector.quantization_config["scalar"].get(
                            "quantile",
                            0.99,
                        ),
                        always_ram=self.config.vector.quantization_config["scalar"].get(
                            "always_ram",
                            True,
                        ),
                    ),
                )

            # Create collection
            await client.create_collection(
                collection_name=collection_name,
                vectors_config=vectors_config,
                hnsw_config=hnsw_config,
                quantization_config=quantization_config,
            )

            self.logger.info(f"Created Qdrant collection: {collection_name}")
            return True

        except Exception as e:
            self.logger.exception(f"Failed to ensure collection {collection_name}: {e}")
            return False

    async def search(
        self,
        collection: str,
        query_vector: list[float],
        limit: int = 10,
        filter_expr: dict[str, t.Any] | None = None,
        include_vectors: bool = False,
        **kwargs: t.Any,
    ) -> list[VectorSearchResult]:
        """Perform vector similarity search in Qdrant."""
        client = await self._ensure_client()
        collection_name = collection or self.config.vector.default_collection

        try:
            # Build filter
            qdrant_filter = None
            if filter_expr:
                qdrant_filter = self._build_qdrant_filter(filter_expr)

            # Perform search
            search_result = await client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=limit,
                query_filter=qdrant_filter,
                with_payload=True,
                with_vectors=include_vectors,
                score_threshold=kwargs.get("score_threshold"),
            )

            # Convert to VectorSearchResult
            results = []
            for point in search_result:
                result = VectorSearchResult(
                    id=str(point.id),
                    score=float(point.score),
                    metadata=point.payload,
                    vector=point.vector if include_vectors else None,
                )
                results.append(result)

            return results

        except Exception as e:
            self.logger.exception(f"Qdrant search failed: {e}")
            return []

    def _build_qdrant_filter(self, filter_expr: dict[str, t.Any]) -> t.Any:
        """Build Qdrant filter from filter expression."""
        try:
            from qdrant_client.models import (
                FieldCondition,
                Filter,
                MatchAny,
                MatchValue,
            )

            conditions = []
            for key, value in filter_expr.items():
                if isinstance(value, str | (int | float | bool)):
                    conditions.append(
                        FieldCondition(key=key, match=MatchValue(value=value)),
                    )
                elif isinstance(value, list):
                    conditions.append(
                        FieldCondition(key=key, match=MatchAny(any=value)),
                    )

            if conditions:
                # Type cast to match Filter union type expectations
                return Filter(must=conditions)  # type: ignore[arg-type]

            return None

        except Exception as e:
            self.logger.warning(f"Failed to build Qdrant filter: {e}")
            return None

    async def insert(
        self,
        collection: str,
        documents: list[VectorDocument],
        **kwargs: t.Any,
    ) -> list[str]:
        """Insert documents with vectors into Qdrant."""
        return await self.upsert(collection, documents, **kwargs)

    async def upsert(
        self,
        collection: str,
        documents: list[VectorDocument],
        **kwargs: t.Any,
    ) -> list[str]:
        """Upsert documents with vectors into Qdrant."""
        client = await self._ensure_client()
        collection_name = collection or self.config.vector.default_collection

        # Ensure collection exists
        dimension = len(documents[0].vector) if documents else None
        await self._ensure_collection_exists(collection_name, dimension)

        try:
            import uuid

            from qdrant_client.models import PointStruct

            # Prepare points for upsert
            points = []
            document_ids = []

            for doc in documents:
                doc_id = doc.id
                if not doc_id:
                    doc_id = str(uuid.uuid4())

                document_ids.append(doc_id)

                point = PointStruct(
                    id=doc_id,
                    vector=doc.vector,
                    payload=doc.metadata,
                )
                points.append(point)

            # Batch upsert
            batch_size = self.config.vector.batch_size
            for i in range(0, len(points), batch_size):
                batch = points[i : i + batch_size]

                operation_info = await client.upsert(
                    collection_name=collection_name,
                    points=batch,
                    wait=True,  # Wait for operation to complete
                )

                if operation_info.status.name != "COMPLETED":
                    self.logger.warning(
                        f"Upsert batch {i // batch_size + 1} failed: {operation_info.status}",
                    )

            return document_ids

        except Exception as e:
            self.logger.exception(f"Qdrant upsert failed: {e}")
            return []

    async def delete(
        self,
        collection: str,
        ids: list[str],
        **kwargs: t.Any,
    ) -> bool:
        """Delete documents by IDs from Qdrant."""
        client = await self._ensure_client()
        collection_name = collection or self.config.vector.default_collection

        try:
            from qdrant_client.models import PointIdsList

            # Delete points (cast ids to satisfy type checker)
            operation_info = await client.delete(
                collection_name=collection_name,
                points_selector=PointIdsList(points=ids),  # type: ignore[arg-type]
                wait=True,
            )

            return operation_info.status.name == "COMPLETED"

        except Exception as e:
            self.logger.exception(f"Qdrant delete failed: {e}")
            return False

    async def get(
        self,
        collection: str,
        ids: list[str],
        include_vectors: bool = False,
        **kwargs: t.Any,
    ) -> list[VectorDocument]:
        """Retrieve documents by IDs from Qdrant."""
        client = await self._ensure_client()
        collection_name = collection or self.config.vector.default_collection

        try:
            # Retrieve points
            points = await client.retrieve(
                collection_name=collection_name,
                ids=ids,
                with_payload=True,
                with_vectors=include_vectors,
            )

            documents = []
            for point in points:
                doc = VectorDocument(
                    id=str(point.id),
                    vector=point.vector if include_vectors else [],
                    metadata=point.payload,
                )
                documents.append(doc)

            return documents

        except Exception as e:
            self.logger.exception(f"Qdrant retrieve failed: {e}")
            return []

    async def count(
        self,
        collection: str,
        filter_expr: dict[str, t.Any] | None = None,
        **kwargs: t.Any,
    ) -> int:
        """Count documents in Qdrant collection."""
        client = await self._ensure_client()
        collection_name = collection or self.config.vector.default_collection

        try:
            # Build filter
            qdrant_filter = None
            if filter_expr:
                qdrant_filter = self._build_qdrant_filter(filter_expr)

            # Count points
            count_result = await client.count(
                collection_name=collection_name,
                count_filter=qdrant_filter,
            )

            return count_result.count

        except Exception as e:
            self.logger.exception(f"Qdrant count failed: {e}")
            return 0

    async def create_collection(
        self,
        name: str,
        dimension: int,
        distance_metric: str = "cosine",
        **kwargs: t.Any,
    ) -> bool:
        """Create a new collection in Qdrant."""
        return await self._ensure_collection_exists(name, dimension, distance_metric)

    async def delete_collection(
        self,
        name: str,
        **kwargs: t.Any,
    ) -> bool:
        """Delete a collection in Qdrant."""
        client = await self._ensure_client()

        try:
            await client.delete_collection(collection_name=name)
            return True

        except Exception as e:
            self.logger.exception(f"Qdrant collection delete failed: {e}")
            return False

    async def list_collections(self, **kwargs: t.Any) -> list[str]:
        """List all collections in Qdrant."""
        client = await self._ensure_client()

        try:
            collections = await client.get_collections()
            return [col.name for col in collections.collections]

        except Exception as e:
            self.logger.exception(f"Qdrant list collections failed: {e}")
            return []

    async def scroll(
        self,
        collection: str,
        limit: int = 100,
        offset: str | None = None,
        filter_expr: dict[str, t.Any] | None = None,
        include_vectors: bool = False,
        **kwargs: t.Any,
    ) -> tuple[list[VectorDocument], str | None]:
        """Scroll through documents in Qdrant collection."""
        client = await self._ensure_client()
        collection_name = collection or self.config.vector.default_collection

        try:
            # Build filter
            qdrant_filter = None
            if filter_expr:
                qdrant_filter = self._build_qdrant_filter(filter_expr)

            # Scroll through points
            scroll_result = await client.scroll(
                collection_name=collection_name,
                limit=limit,
                offset=offset,
                scroll_filter=qdrant_filter,
                with_payload=True,
                with_vectors=include_vectors,
            )

            # Convert to VectorDocument
            documents = []
            for point in scroll_result[0]:  # First element is the list of points
                doc = VectorDocument(
                    id=str(point.id),
                    vector=point.vector if include_vectors else [],
                    metadata=point.payload,
                )
                documents.append(doc)

            next_offset = scroll_result[1]  # Second element is the next offset
            return documents, next_offset

        except Exception as e:
            self.logger.exception(f"Qdrant scroll failed: {e}")
            return [], None

    def has_capability(self, capability: str) -> bool:
        """Check if Qdrant adapter supports a specific capability."""
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
            "streaming",
            "scroll",
            "quantization",
        }
        return capability in supported_capabilities


depends.set(Vector, "qdrant")
