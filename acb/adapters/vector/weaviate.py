from uuid import UUID

import typing as t
from pydantic import SecretStr

from acb.adapters import AdapterCapability, AdapterMetadata, AdapterStatus
from acb.depends import depends

from ._base import VectorBase, VectorBaseSettings, VectorDocument, VectorSearchResult

MODULE_ID = UUID("0197ff50-3456-7892-cdef-ef0123456791")
MODULE_STATUS = AdapterStatus.STABLE

MODULE_METADATA = AdapterMetadata(
    module_id=MODULE_ID,
    name="Weaviate Vector Database",
    category="vector",
    provider="weaviate",
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
        AdapterCapability.SCHEMA_VALIDATION,
        AdapterCapability.STREAMING,
    ],
    required_packages=["weaviate-client>=4.0.0"],
    description="Weaviate open-source vector database with GraphQL and REST APIs",
    settings_class="VectorSettings",
    config_example={
        "url": "http://localhost:8080",
        "api_key": "your-weaviate-api-key",
        "default_class": "Document",
        "default_dimension": 1536,
        "default_distance_metric": "cosine",
    },
)


class VectorSettings(VectorBaseSettings):
    """Weaviate vector adapter settings."""

    url: str = "http://localhost:8080"
    api_key: SecretStr | None = None

    # Authentication settings
    use_auth: bool = False
    auth_client_secret: SecretStr | None = None

    # Additional headers for cloud instances
    additional_headers: dict[str, str] = {}

    # Default class settings
    default_class: str = "Document"
    vectorizer: str = "none"  # none, text2vec-openai, text2vec-cohere, etc.

    # Performance settings
    query_timeout: float = 30.0
    startup_timeout: float = 60.0

    # Schema settings
    auto_create_schema: bool = True
    distance_metric: str = "cosine"  # cosine, dot, l2-squared, manhattan, hamming


class Vector(VectorBase):
    """Weaviate vector adapter implementation."""

    async def _create_client(self) -> t.Any:
        """Create Weaviate client."""
        import weaviate
        from weaviate.auth import AuthApiKey

        # Build connection configuration
        connection_params = {
            "url": self.config.vector.url,
            "startup_period": self.config.vector.startup_timeout,
        }

        # Add authentication if configured
        if self.config.vector.use_auth and self.config.vector.api_key:
            auth_config = AuthApiKey(
                api_key=self.config.vector.api_key.get_secret_value(),
            )
            connection_params["auth_client_secret"] = auth_config

        # Add additional headers if configured
        if self.config.vector.additional_headers:
            connection_params["additional_headers"] = (
                self.config.vector.additional_headers
            )

        # Create client
        client = weaviate.connect_to_custom(**connection_params)

        self.logger.debug("Weaviate client initialized successfully")
        return client

    async def _ensure_client(self) -> t.Any:
        """Ensure Weaviate client is available."""
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def init(self) -> None:
        """Initialize Weaviate vector adapter."""
        self.logger.info("Initializing Weaviate vector adapter")

        client = await self._ensure_client()

        # Check if we can connect
        try:
            is_ready = client.is_ready()
            if not is_ready:
                self.logger.warning("Weaviate is not ready")
            else:
                self.logger.debug("Weaviate connection verified")
        except Exception as e:
            self.logger.exception(f"Failed to verify Weaviate connection: {e}")
            raise

        self.logger.info("Weaviate vector adapter initialized successfully")

    def _collection_to_class_name(self, collection: str) -> str:
        """Convert collection name to Weaviate class name (capitalize first letter)."""
        if not collection:
            return self.config.vector.default_class
        return collection.capitalize()

    async def _ensure_class_exists(
        self,
        class_name: str,
        dimension: int | None = None,
    ) -> bool:
        """Ensure Weaviate class exists, create if needed."""
        client = await self._ensure_client()

        try:
            # Check if class exists
            collections = client.collections.list_all()
            existing_classes = [col.name for col in collections]

            if class_name in existing_classes:
                return True

            if not self.config.vector.auto_create_schema:
                return False

            # Create class schema
            from weaviate.classes.config import Configure

            properties = [
                {
                    "name": "content",
                    "dataType": ["text"],
                    "description": "Content text",
                },
                {
                    "name": "source",
                    "dataType": ["text"],
                    "description": "Source information",
                },
            ]

            # Configure vector settings
            vector_config = None
            if dimension:
                vector_config = Configure.VectorIndex.hnsw(
                    distance_metric=self.config.vector.distance_metric,
                    vector_cache_max_objects=100000,
                )

            # Create collection
            collection_config = {
                "name": class_name,
                "description": f"ACB generated class for {class_name}",
                "properties": properties,
            }

            if vector_config:
                collection_config["vector_index_config"] = vector_config  # type: ignore[assignment]

            client.collections.create(**collection_config)
            self.logger.info(f"Created Weaviate class: {class_name}")
            return True

        except Exception as e:
            self.logger.exception(f"Failed to ensure class {class_name}: {e}")
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
        """Perform vector similarity search in Weaviate."""
        client = await self._ensure_client()
        class_name = self._collection_to_class_name(collection)

        try:
            # Get collection
            weaviate_collection = client.collections.get(class_name)

            # Build query
            query_builder = weaviate_collection.query.near_vector(
                near_vector=query_vector,
                limit=limit,
                return_metadata=["distance", "certainty"],
            )

            # Add where filter if provided
            if filter_expr:
                # Convert filter_expr to Weaviate where format
                where_filter = self._build_where_filter(filter_expr)
                if where_filter:
                    query_builder = query_builder.where(where_filter)

            # Execute query
            response = query_builder.objects

            # Convert to VectorSearchResult
            results = []
            for obj in response:
                # Calculate similarity score from distance
                distance = obj.metadata.distance if obj.metadata else 0.0
                score = 1.0 - distance  # Convert distance to similarity

                result = VectorSearchResult(
                    id=str(obj.uuid),
                    score=score,
                    metadata=obj.properties or t.cast(dict[str, t.Any], {}),
                    vector=obj.vector.get("default")
                    if include_vectors and obj.vector
                    else None,
                )
                results.append(result)

            return results

        except Exception as e:
            self.logger.exception(f"Weaviate search failed: {e}")
            return []

    def _build_where_filter(
        self,
        filter_expr: dict[str, t.Any],
    ) -> t.Any:
        """Build Weaviate where filter from filter expression."""
        try:
            from weaviate.classes.query import Filter

            conditions = []
            for key, value in filter_expr.items():
                if isinstance(value, str | (int | float)):
                    conditions.append(Filter.by_property(key).equal(value))
                elif isinstance(value, list):
                    conditions.append(Filter.by_property(key).contains_any(value))

            if len(conditions) == 1:
                return conditions[0]
            if len(conditions) > 1:
                # Combine with AND
                result = conditions[0]
                for condition in conditions[1:]:
                    result = result & condition
                return result

            return None

        except Exception as e:
            self.logger.warning(f"Failed to build where filter: {e}")
            return None

    async def insert(
        self,
        collection: str,
        documents: list[VectorDocument],
        **kwargs: t.Any,
    ) -> list[str]:
        """Insert documents with vectors into Weaviate."""
        return await self.upsert(collection, documents, **kwargs)

    async def upsert(
        self,
        collection: str,
        documents: list[VectorDocument],
        **kwargs: t.Any,
    ) -> list[str]:
        """Upsert documents with vectors into Weaviate."""
        client = await self._ensure_client()
        class_name = self._collection_to_class_name(collection)

        # Ensure class exists
        dimension = len(documents[0].vector) if documents else None
        await self._ensure_class_exists(class_name, dimension)

        try:
            weaviate_collection = client.collections.get(class_name)

            # Prepare documents for batch insertion
            document_ids, objects_to_insert = self._prepare_documents_for_insert(
                documents
            )

            # Perform batch insert
            await self._batch_insert_objects(
                weaviate_collection, objects_to_insert, self.config.vector.batch_size
            )

            return document_ids

        except Exception as e:
            self.logger.exception(f"Weaviate upsert failed: {e}")
            return []

    def _prepare_documents_for_insert(
        self, documents: list[VectorDocument]
    ) -> tuple[list[str], list[dict[str, t.Any]]]:
        """Prepare documents for batch insertion.

        Args:
            documents: Documents to prepare

        Returns:
            Tuple of (document IDs, objects to insert)
        """
        document_ids = []
        objects_to_insert = []

        for doc in documents:
            doc_id = self._get_or_generate_doc_id(doc)
            document_ids.append(doc_id)

            # Prepare object data
            obj_data = self._build_object_data(doc, doc_id)
            objects_to_insert.append(obj_data)

        return document_ids, objects_to_insert

    def _get_or_generate_doc_id(self, doc: VectorDocument) -> str:
        """Get document ID or generate new one.

        Args:
            doc: Vector document

        Returns:
            Document ID
        """
        if doc.id:
            return doc.id

        import uuid

        return str(uuid.uuid4())

    def _build_object_data(self, doc: VectorDocument, doc_id: str) -> dict[str, t.Any]:
        """Build object data for Weaviate insertion.

        Args:
            doc: Vector document
            doc_id: Document ID

        Returns:
            Object data dictionary
        """
        properties = doc.metadata.copy() if doc.metadata else {}
        properties.update(
            {
                "content": properties.get("content", ""),
                "source": properties.get("source", ""),
            },
        )

        return {
            "uuid": doc_id,
            "properties": properties,
            "vector": {"default": doc.vector},
        }

    async def _batch_insert_objects(
        self,
        weaviate_collection: t.Any,
        objects_to_insert: list[dict[str, t.Any]],
        batch_size: int,
    ) -> None:
        """Insert objects in batches.

        Args:
            weaviate_collection: Weaviate collection instance
            objects_to_insert: Objects to insert
            batch_size: Batch size for insertion
        """
        for i in range(0, len(objects_to_insert), batch_size):
            batch = objects_to_insert[i : i + batch_size]

            # Use batch context manager
            with weaviate_collection.batch.dynamic() as batch_context:
                for obj in batch:
                    batch_context.add_object(
                        properties=obj["properties"],
                        uuid=obj["uuid"],
                        vector=obj["vector"],
                    )

    async def delete(
        self,
        collection: str,
        ids: list[str],
        **kwargs: t.Any,
    ) -> bool:
        """Delete documents by IDs from Weaviate."""
        client = await self._ensure_client()
        class_name = self._collection_to_class_name(collection)

        try:
            weaviate_collection = client.collections.get(class_name)

            # Delete objects by UUID
            for doc_id in ids:
                weaviate_collection.data.delete_by_id(doc_id)

            return True

        except Exception as e:
            self.logger.exception(f"Weaviate delete failed: {e}")
            return False

    async def get(
        self,
        collection: str,
        ids: list[str],
        include_vectors: bool = False,
        **kwargs: t.Any,
    ) -> list[VectorDocument]:
        """Retrieve documents by IDs from Weaviate."""
        client = await self._ensure_client()
        class_name = self._collection_to_class_name(collection)

        try:
            weaviate_collection = client.collections.get(class_name)
            documents = []

            for doc_id in ids:
                try:
                    obj = weaviate_collection.query.fetch_object_by_id(
                        doc_id,
                        include_vector=include_vectors,
                    )

                    if obj:
                        doc = VectorDocument(
                            id=str(obj.uuid),
                            vector=obj.vector.get("default", [])
                            if include_vectors and obj.vector
                            else [],
                            metadata=obj.properties or t.cast(dict[str, t.Any], {}),
                        )
                        documents.append(doc)

                except Exception as e:
                    self.logger.warning(f"Failed to fetch object {doc_id}: {e}")
                    continue

            return documents

        except Exception as e:
            self.logger.exception(f"Weaviate fetch failed: {e}")
            return []

    async def count(
        self,
        collection: str,
        filter_expr: dict[str, t.Any] | None = None,
        **kwargs: t.Any,
    ) -> int:
        """Count documents in Weaviate collection."""
        client = await self._ensure_client()
        class_name = self._collection_to_class_name(collection)

        try:
            weaviate_collection = client.collections.get(class_name)

            # Build aggregate query
            if filter_expr:
                where_filter = self._build_where_filter(filter_expr)
                if where_filter:
                    response = weaviate_collection.aggregate.over_all(
                        where=where_filter,
                        total_count=True,
                    )
                else:
                    response = weaviate_collection.aggregate.over_all(total_count=True)
            else:
                response = weaviate_collection.aggregate.over_all(total_count=True)

            return response.total_count or 0

        except Exception as e:
            self.logger.exception(f"Weaviate count failed: {e}")
            return 0

    async def create_collection(
        self,
        name: str,
        dimension: int,
        distance_metric: str = "cosine",
        **kwargs: t.Any,
    ) -> bool:
        """Create a new collection (class) in Weaviate."""
        class_name = self._collection_to_class_name(name)
        return await self._ensure_class_exists(class_name, dimension)

    async def delete_collection(
        self,
        name: str,
        **kwargs: t.Any,
    ) -> bool:
        """Delete a collection (class) in Weaviate."""
        client = await self._ensure_client()
        class_name = self._collection_to_class_name(name)

        try:
            client.collections.delete(class_name)
            return True

        except Exception as e:
            self.logger.exception(f"Weaviate class delete failed: {e}")
            return False

    async def list_collections(self, **kwargs: t.Any) -> list[str]:
        """List all collections (classes) in Weaviate."""
        client = await self._ensure_client()

        try:
            collections = client.collections.list_all()
            return [col.name.lower() for col in collections]

        except Exception as e:
            self.logger.exception(f"Weaviate list collections failed: {e}")
            return []

    async def text_search(
        self,
        collection: str,
        query_text: str,
        limit: int = 10,
        filter_expr: dict[str, t.Any] | None = None,
        **kwargs: t.Any,
    ) -> list[VectorSearchResult]:
        """Text-based search in Weaviate."""
        client = await self._ensure_client()
        class_name = self._collection_to_class_name(collection)

        try:
            weaviate_collection = client.collections.get(class_name)

            # Build text query
            query_builder = weaviate_collection.query.bm25(
                query=query_text,
                limit=limit,
                return_metadata=["score"],
            )

            # Add where filter if provided
            if filter_expr:
                where_filter = self._build_where_filter(filter_expr)
                if where_filter:
                    query_builder = query_builder.where(where_filter)

            # Execute query
            response = query_builder.objects

            # Convert to VectorSearchResult
            results = []
            for obj in response:
                score = obj.metadata.score if obj.metadata else 0.0

                result = VectorSearchResult(
                    id=str(obj.uuid),
                    score=score,
                    metadata=obj.properties or t.cast(dict[str, t.Any], {}),
                    vector=None,  # Text search doesn't return vectors
                )
                results.append(result)

            return results

        except Exception as e:
            self.logger.exception(f"Weaviate text search failed: {e}")
            return []

    def has_capability(self, capability: str) -> bool:
        """Check if Weaviate adapter supports a specific capability."""
        supported_capabilities = {
            "vector_search",
            "text_search",
            "hybrid_search",
            "batch_operations",
            "metadata_filtering",
            "indexing",
            "connection_pooling",
            "async_operations",
            "caching",
            "metrics",
            "schema_validation",
            "streaming",
        }
        return capability in supported_capabilities


depends.set(Vector, "weaviate")
