from abc import abstractmethod

import typing as t
from contextlib import asynccontextmanager
from pydantic import BaseModel, Field, SecretStr

from acb.cleanup import CleanupMixin
from acb.config import AdapterBase, Config, Settings
from acb.depends import Inject, depends
from acb.ssl_config import SSLConfigMixin

# Avoid static imports for optional submodules to keep type checkers happy
# when extras are not installed. Use broad aliases for types here; concrete
# implementations are imported dynamically where needed.
VectorCache = t.Any
HybridSearch = t.Any
AutoScaler = t.Any
ConnectionPool = t.Any


class VectorSearchResult(BaseModel):
    """Standard vector search result."""

    id: str
    score: float
    metadata: dict[str, t.Any] = Field(default_factory=dict)
    vector: list[float] | None = None


class VectorDocument(BaseModel):
    """Standard vector document for insertion."""

    id: str | None = None
    vector: list[float]
    metadata: dict[str, t.Any] = Field(default_factory=dict)


class VectorBaseSettings(Settings, SSLConfigMixin):
    """Base settings for vector adapters."""

    host: SecretStr = SecretStr("127.0.0.1")
    port: int | None = None
    collection_prefix: str = ""
    default_dimension: int = 1536  # OpenAI ada-002 default
    default_distance_metric: str = "cosine"  # cosine, euclidean, dot_product

    # Connection settings
    connect_timeout: float = 30.0
    request_timeout: float = 30.0
    max_retries: int = 3

    # Performance settings
    batch_size: int = 100
    max_connections: int = 10

    # Phase 5 feature toggles
    enable_caching: bool = True
    enable_hybrid_search: bool = False
    enable_auto_scaling: bool = False
    enable_connection_pooling: bool = True

    @depends.inject
    def __init__(self, config: Inject[Config], **values: t.Any) -> None:
        super().__init__(**values)


class VectorProtocol(t.Protocol):
    """Protocol defining vector database interface."""

    @abstractmethod
    async def search(
        self,
        collection: str,
        query_vector: list[float],
        limit: int = 10,
        filter_expr: dict[str, t.Any] | None = None,
        include_vectors: bool = False,
        **kwargs: t.Any,
    ) -> list[VectorSearchResult]:
        """Perform vector similarity search."""

    @abstractmethod
    async def insert(
        self,
        collection: str,
        documents: list[VectorDocument],
        **kwargs: t.Any,
    ) -> list[str]:
        """Insert documents with vectors."""

    @abstractmethod
    async def upsert(
        self,
        collection: str,
        documents: list[VectorDocument],
        **kwargs: t.Any,
    ) -> list[str]:
        """Upsert documents with vectors."""

    @abstractmethod
    async def delete(
        self,
        collection: str,
        ids: list[str],
        **kwargs: t.Any,
    ) -> bool:
        """Delete documents by IDs."""

    @abstractmethod
    async def get(
        self,
        collection: str,
        ids: list[str],
        include_vectors: bool = False,
        **kwargs: t.Any,
    ) -> list[VectorDocument]:
        """Retrieve documents by IDs."""

    @abstractmethod
    async def count(
        self,
        collection: str,
        filter_expr: dict[str, t.Any] | None = None,
        **kwargs: t.Any,
    ) -> int:
        """Count documents in collection."""

    @abstractmethod
    async def create_collection(
        self,
        name: str,
        dimension: int,
        distance_metric: str = "cosine",
        **kwargs: t.Any,
    ) -> bool:
        """Create a new collection."""

    @abstractmethod
    async def delete_collection(
        self,
        name: str,
        **kwargs: t.Any,
    ) -> bool:
        """Delete a collection."""

    @abstractmethod
    async def list_collections(self, **kwargs: t.Any) -> list[str]:
        """List all collections."""

    # Optional Phase 5 methods (for adapters that support advanced features)
    async def text_search(
        self,
        collection: str,
        query_text: str,
        limit: int = 10,
        filter_expr: dict[str, t.Any] | None = None,
        **kwargs: t.Any,
    ) -> list[VectorSearchResult]:
        """Text-based search (for hybrid search support)."""
        msg = "Text search not implemented for this adapter"
        raise NotImplementedError(msg)

    def has_capability(self, capability: str) -> bool:
        """Check if adapter supports a specific capability."""
        return False  # Base implementation - override in adapters


class VectorCollection:
    """Wrapper for vector collection operations."""

    def __init__(self, adapter: t.Any, name: str) -> None:
        self.adapter = adapter
        self.name = name

    async def search(
        self,
        query_vector: list[float],
        limit: int = 10,
        filter_expr: dict[str, t.Any] | None = None,
        include_vectors: bool = False,
        **kwargs: t.Any,
    ) -> list[VectorSearchResult]:
        return await t.cast("VectorProtocol", self.adapter).search(
            self.name,
            query_vector,
            limit,
            filter_expr,
            include_vectors,
            **kwargs,
        )

    async def insert(
        self,
        documents: list[VectorDocument],
        **kwargs: t.Any,
    ) -> list[str]:
        return await t.cast("VectorProtocol", self.adapter).insert(
            self.name,
            documents,
            **kwargs,
        )

    async def upsert(
        self,
        documents: list[VectorDocument],
        **kwargs: t.Any,
    ) -> list[str]:
        return await t.cast("VectorProtocol", self.adapter).upsert(
            self.name,
            documents,
            **kwargs,
        )

    async def delete(self, ids: list[str], **kwargs: t.Any) -> bool:
        return await t.cast("VectorProtocol", self.adapter).delete(
            self.name,
            ids,
            **kwargs,
        )

    async def get(
        self,
        ids: list[str],
        include_vectors: bool = False,
        **kwargs: t.Any,
    ) -> list[VectorDocument]:
        return await t.cast("VectorProtocol", self.adapter).get(
            self.name,
            ids,
            include_vectors,
            **kwargs,
        )

    async def count(
        self,
        filter_expr: dict[str, t.Any] | None = None,
        **kwargs: t.Any,
    ) -> int:
        return await t.cast("VectorProtocol", self.adapter).count(
            self.name,
            filter_expr,
            **kwargs,
        )


class VectorBase(AdapterBase, CleanupMixin):  # type: ignore[misc]
    """Base class for vector database adapters."""

    def __init__(self, **kwargs: t.Any) -> None:
        super().__init__(**kwargs)
        self._collections: dict[str, VectorCollection] = {}
        self._client: t.Any | None = None

        # Phase 5 feature instances (lazy-loaded)
        self._cache: VectorCache | None = None
        self._hybrid_search: HybridSearch | None = None
        self._auto_scaler: AutoScaler | None = None
        self._connection_pool: ConnectionPool | None = None

    def __getattr__(self, name: str) -> t.Any:
        """Dynamic collection access."""
        if name not in self._collections:
            self._collections[name] = VectorCollection(self, name)
        return self._collections[name]

    async def get_client(self) -> t.Any:
        """Get the underlying vector database client."""
        return await self._ensure_client()

    # Phase 5 feature access methods
    async def get_cache(self) -> VectorCache | None:
        """Get the cache instance if caching is enabled."""
        if not getattr(self.settings, "enable_caching", True):
            return None

        if self._cache is None:
            try:
                from acb.adapters.vector.cache import (  # type: ignore[import-not-found]
                    VectorCache,
                    VectorCacheSettings,
                )

                cache_settings = VectorCacheSettings()
                self._cache = VectorCache(self, cache_settings)
                self.register_resource(self._cache)
            except ImportError:
                return None

        return self._cache

    async def get_hybrid_search(self) -> HybridSearch | None:
        """Get the hybrid search instance if enabled."""
        if not getattr(self.settings, "enable_hybrid_search", False):
            return None

        if self._hybrid_search is None:
            try:
                from acb.adapters.vector.hybrid import (  # type: ignore[import-not-found]
                    HybridSearch,
                    HybridSearchConfig,
                )

                config = HybridSearchConfig()
                self._hybrid_search = HybridSearch(self, config)
            except ImportError:
                return None

        return self._hybrid_search

    async def get_auto_scaler(self) -> AutoScaler | None:
        """Get the auto scaler instance if enabled."""
        if not getattr(self.settings, "enable_auto_scaling", False):
            return None

        if self._auto_scaler is None:
            try:
                from acb.adapters.vector.scaling import (  # type: ignore[import-not-found]
                    AutoScaler,
                    AutoScalingSettings,
                )

                # Auto scaler needs a connection pool
                connection_pool = await self.get_connection_pool()
                if connection_pool is None:
                    return None

                settings = AutoScalingSettings()
                self._auto_scaler = AutoScaler(connection_pool, settings)
            except ImportError:
                return None

        return self._auto_scaler

    async def get_connection_pool(self) -> ConnectionPool | None:
        """Get the connection pool instance if enabled."""
        if not getattr(self.settings, "enable_connection_pooling", True):
            return None

        if self._connection_pool is None:
            try:
                from acb.adapters.vector.scaling import (  # type: ignore[import-not-found]
                    ConnectionPool,
                    ConnectionPoolSettings,
                )

                settings = ConnectionPoolSettings()
                self._connection_pool = ConnectionPool(self, settings)
                await self._connection_pool.initialize()
                self.register_resource(self._connection_pool)
            except ImportError:
                return None

        return self._connection_pool

    # Enhanced search methods using Phase 5 features
    async def search_with_cache(
        self,
        collection: str,
        query_vector: list[float],
        limit: int = 10,
        filter_expr: dict[str, t.Any] | None = None,
        include_vectors: bool = False,
        **kwargs: t.Any,
    ) -> list[VectorSearchResult]:
        """Search with caching if enabled, fallback to regular search."""
        cache = await self.get_cache()
        if cache:
            # Convert VectorDocuments to VectorSearchResults
            cached_docs = await cache.search(
                collection,
                query_vector,
                limit,
                filter_expr,
                **kwargs,
            )
            return [
                VectorSearchResult(
                    id=doc.id if doc.id is not None else "",
                    score=1.0,  # Cache doesn't preserve scores
                    metadata=doc.metadata,
                    vector=doc.vector if include_vectors else None,
                )
                for doc in cached_docs
            ]

        # Fallback to regular search
        result: list[VectorSearchResult] = await self.search(
            collection,
            query_vector,
            limit,
            filter_expr,
            include_vectors,
            **kwargs,
        )
        return result

    async def hybrid_search(
        self,
        collection: str,
        query_vector: list[float],
        query_text: str,
        limit: int = 10,
        filter_expr: dict[str, t.Any] | None = None,
        **kwargs: t.Any,
    ) -> list[VectorSearchResult]:
        """Perform hybrid search if enabled, fallback to vector search."""
        hybrid = await self.get_hybrid_search()
        if hybrid:
            hybrid_results = await hybrid.search(
                collection,
                query_vector,
                query_text,
                limit,
                filter_expr,
                **kwargs,
            )

            # Convert to VectorSearchResult
            return [
                VectorSearchResult(
                    id=result.document.id if result.document.id is not None else "",
                    score=result.combined_score,
                    metadata=result.document.metadata,
                    vector=result.document.vector,
                )
                for result in hybrid_results
            ]

        # Fallback to regular vector search
        result: list[VectorSearchResult] = await self.search(
            collection,
            query_vector,
            limit,
            filter_expr,
            **kwargs,
        )
        return result

    @abstractmethod
    async def init(self) -> None:
        """Initialize the vector adapter."""

    @asynccontextmanager
    async def transaction(self) -> t.AsyncGenerator[t.Any]:
        """Transaction context manager (if supported)."""
        client = await self.get_client()
        yield client
