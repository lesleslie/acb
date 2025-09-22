# Vector Adapter Implementation Plan

## Overview

This document provides a comprehensive implementation plan for adding a vector database adapter to ACB (Asynchronous Component Base). The vector adapter will provide a unified interface for vector similarity search across multiple vector database implementations, following ACB's established adapter patterns.

## Strategic Rationale

### Market Alignment

- **AI/RAG applications exploding**: Vector search becoming essential for modern applications
- **No clear market leader in 2025**: Adapter pattern provides flexibility to switch between solutions
- **Hybrid approaches emerging**: OpenSearch, DuckDB VSS, traditional databases adding vector capabilities
- **Perfect timing**: Positions ACB at the forefront of AI application development

### Architecture Fit

- **Distinct from SQL/NoSQL**: Vector operations require specialized interfaces
- **Follows established patterns**: Leverages proven adapter design from existing categories
- **Logical separation**: Clear use case boundaries between sql, nosql, and vector adapters

| Adapter Category | Primary Use Case | Query Pattern |
|------------------|------------------|---------------|
| `sql` | Structured data, ACID transactions | SQL queries, joins, relational operations |
| `nosql` | Document storage, flexible schema | Document CRUD, aggregations |
| `vector` | Similarity search, embeddings | Vector operations, nearest neighbor, semantic search |

## Implementation Strategy

### Phase 1: Core Foundation (Week 1-2)

**Deliverables:**

- Base vector adapter interface and protocol
- Core configuration system
- Basic test infrastructure
- DuckDB VSS implementation (local development)

**Priority:** High - Establishes foundation for all subsequent work

### Phase 2: Production Database (Week 3-4)

**Deliverables:**

- Qdrant implementation (cloud-ready)
- Enhanced configuration options
- Performance optimization
- Comprehensive testing

**Priority:** High - Enables production deployments

### Phase 3: Advanced Features (Week 5-6)

**Deliverables:**

- Weaviate implementation (hybrid capabilities)
- Advanced filtering and metadata support
- Integration with ACB models adapter
- Documentation and examples

**Priority:** Medium - Adds enterprise capabilities

### Phase 4: Ecosystem Integration (Week 7-8)

**Deliverables:**

- OpenSearch vector implementation
- Performance benchmarking
- Migration utilities
- Production hardening

**Priority:** Low - Extends ecosystem coverage

## Technical Architecture

### Core Interface Design

```python
# acb/adapters/vector/_base.py

import typing as t
from abc import abstractmethod
from contextlib import asynccontextmanager
from pydantic import BaseModel, Field
from acb.config import AdapterBase, Config, Settings
from acb.core.cleanup import CleanupMixin
from acb.core.ssl_config import SSLConfigMixin
from acb.depends import depends


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

    host: str = "127.0.0.1"
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

    @depends.inject
    def __init__(self, config: Config = depends(), **values: t.Any) -> None:
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
        pass

    @abstractmethod
    async def insert(
        self,
        collection: str,
        documents: list[VectorDocument],
        **kwargs: t.Any,
    ) -> list[str]:
        """Insert documents with vectors."""
        pass

    @abstractmethod
    async def upsert(
        self,
        collection: str,
        documents: list[VectorDocument],
        **kwargs: t.Any,
    ) -> list[str]:
        """Upsert documents with vectors."""
        pass

    @abstractmethod
    async def delete(
        self,
        collection: str,
        ids: list[str],
        **kwargs: t.Any,
    ) -> bool:
        """Delete documents by IDs."""
        pass

    @abstractmethod
    async def get(
        self,
        collection: str,
        ids: list[str],
        include_vectors: bool = False,
        **kwargs: t.Any,
    ) -> list[VectorDocument]:
        """Retrieve documents by IDs."""
        pass

    @abstractmethod
    async def count(
        self,
        collection: str,
        filter_expr: dict[str, t.Any] | None = None,
        **kwargs: t.Any,
    ) -> int:
        """Count documents in collection."""
        pass

    @abstractmethod
    async def create_collection(
        self,
        name: str,
        dimension: int,
        distance_metric: str = "cosine",
        **kwargs: t.Any,
    ) -> bool:
        """Create a new collection."""
        pass

    @abstractmethod
    async def delete_collection(
        self,
        name: str,
        **kwargs: t.Any,
    ) -> bool:
        """Delete a collection."""
        pass

    @abstractmethod
    async def list_collections(self, **kwargs: t.Any) -> list[str]:
        """List all collections."""
        pass


class VectorCollection:
    """Wrapper for vector collection operations."""

    def __init__(self, adapter: "VectorProtocol", name: str) -> None:
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
        return await self.adapter.search(
            self.name, query_vector, limit, filter_expr, include_vectors, **kwargs
        )

    async def insert(
        self, documents: list[VectorDocument], **kwargs: t.Any
    ) -> list[str]:
        return await self.adapter.insert(self.name, documents, **kwargs)

    async def upsert(
        self, documents: list[VectorDocument], **kwargs: t.Any
    ) -> list[str]:
        return await self.adapter.upsert(self.name, documents, **kwargs)

    async def delete(self, ids: list[str], **kwargs: t.Any) -> bool:
        return await self.adapter.delete(self.name, ids, **kwargs)

    async def get(
        self,
        ids: list[str],
        include_vectors: bool = False,
        **kwargs: t.Any,
    ) -> list[VectorDocument]:
        return await self.adapter.get(self.name, ids, include_vectors, **kwargs)

    async def count(
        self, filter_expr: dict[str, t.Any] | None = None, **kwargs: t.Any
    ) -> int:
        return await self.adapter.count(self.name, filter_expr, **kwargs)


class VectorBase(AdapterBase, CleanupMixin):  # type: ignore[misc]
    """Base class for vector database adapters."""

    def __init__(self) -> None:
        super().__init__()
        self._collections: dict[str, VectorCollection] = {}
        self._client: t.Any | None = None

    def __getattr__(self, name: str) -> VectorCollection:
        """Dynamic collection access."""
        if name not in self._collections:
            self._collections[name] = VectorCollection(self, name)
        return self._collections[name]

    async def get_client(self) -> t.Any:
        """Get the underlying vector database client."""
        return await self._ensure_client()

    @abstractmethod
    async def init(self) -> None:
        """Initialize the vector adapter."""
        pass

    @asynccontextmanager
    async def transaction(self) -> t.AsyncGenerator[t.Any]:
        """Transaction context manager (if supported)."""
        client = await self.get_client()
        yield client
```

### Configuration System

```yaml
# settings/adapters.yml
vector: duckdb  # Options: duckdb, qdrant, weaviate, opensearch

# settings/vector.yml
host: "localhost"
port: 6333  # Qdrant default
default_dimension: 1536
default_distance_metric: "cosine"
connect_timeout: 30.0
request_timeout: 30.0
max_retries: 3
batch_size: 100
max_connections: 10

# Collection-specific settings
collections:
  documents:
    dimension: 1536
    distance_metric: "cosine"
    index_config:
      m: 16
      ef_construct: 200
  images:
    dimension: 512
    distance_metric: "euclidean"
    index_config:
      m: 32
      ef_construct: 400

# SSL/TLS settings (inherited from SSLConfigMixin)
ssl_enabled: true
ssl_cert_path: "/path/to/cert.pem"
ssl_key_path: "/path/to/key.pem"
ssl_ca_path: "/path/to/ca.pem"
```

## Database Implementation Specifications

### Phase 1: DuckDB VSS Implementation

```python
# acb/adapters/vector/duckdb.py

import typing as t
from pathlib import Path
from uuid import UUID, uuid4
import duckdb
from acb.adapters import AdapterCapability, AdapterMetadata, AdapterStatus
from acb.depends import depends
from ._base import VectorBase, VectorBaseSettings, VectorDocument, VectorSearchResult

MODULE_ID = UUID("0197ff50-1234-7890-abcd-ef0123456789")
MODULE_STATUS = AdapterStatus.STABLE

MODULE_METADATA = AdapterMetadata(
    module_id=MODULE_ID,
    name="DuckDB Vector Search",
    category="vector",
    provider="duckdb",
    version="1.0.0",
    acb_min_version="0.19.1",
    author="lesleslie <les@wedgwoodwebworks.com>",
    created_date="2025-01-21",
    last_modified="2025-01-21",
    status=MODULE_STATUS,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.BULK_OPERATIONS,
        AdapterCapability.SCHEMA_VALIDATION,
    ],
    required_packages=["duckdb>=0.10.2"],
    description="DuckDB-based vector adapter with VSS extension for local development",
    settings_class="VectorSettings",
    config_example={
        "database_path": "data/vectors.db",
        "default_dimension": 1536,
        "default_distance_metric": "cosine",
    },
)


class VectorSettings(VectorBaseSettings):
    """DuckDB vector adapter settings."""

    database_path: str = "data/vectors.db"
    memory_limit: str = "2GB"
    threads: int = 4
    enable_vss: bool = True

    def __init__(self, **values: t.Any) -> None:
        super().__init__(**values)
        # Ensure database directory exists
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)


class Vector(VectorBase):
    """DuckDB vector adapter implementation."""

    async def _create_client(self) -> duckdb.DuckDBPyConnection:
        """Create DuckDB connection with VSS extension."""
        conn = duckdb.connect(
            self.config.vector.database_path,
            config={
                "memory_limit": self.config.vector.memory_limit,
                "threads": self.config.vector.threads,
            },
        )

        if self.config.vector.enable_vss:
            conn.execute("INSTALL vss")
            conn.execute("LOAD vss")

        return conn

    async def init(self) -> None:
        """Initialize DuckDB vector adapter."""
        self.logger.info("Initializing DuckDB vector adapter")
        client = await self.get_client()

        # Create base tables if they don't exist
        client.execute("""
            CREATE SCHEMA IF NOT EXISTS vectors
        """)

        self.logger.info("DuckDB vector adapter initialized successfully")

    # Implementation methods follow...
```

### Phase 2: Qdrant Implementation

```python
# acb/adapters/vector/qdrant.py

import typing as t
from uuid import UUID
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from acb.adapters import AdapterCapability, AdapterMetadata, AdapterStatus
from acb.depends import depends
from ._base import VectorBase, VectorBaseSettings, VectorDocument, VectorSearchResult

MODULE_ID = UUID("0197ff51-1234-7890-abcd-ef0123456789")
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
        AdapterCapability.CONNECTION_POOLING,
        AdapterCapability.TLS_SUPPORT,
        AdapterCapability.BULK_OPERATIONS,
        AdapterCapability.SCHEMA_VALIDATION,
    ],
    required_packages=["qdrant-client>=1.7.0"],
    description="Qdrant vector database adapter for production deployments",
    settings_class="VectorSettings",
    config_example={
        "host": "localhost",
        "port": 6333,
        "api_key": "your-qdrant-api-key",  # pragma: allowlist secret
        "ssl_enabled": True,
    },
)


class VectorSettings(VectorBaseSettings):
    """Qdrant vector adapter settings."""

    port: int = 6333
    api_key: str | None = None
    grpc_port: int | None = 6334
    prefer_grpc: bool = True

    def _build_connection_params(self) -> dict[str, t.Any]:
        """Build Qdrant connection parameters."""
        params = {
            "host": self.host,
            "port": self.port,
            "timeout": self.connect_timeout,
        }

        if self.api_key:
            params["api_key"] = self.api_key

        if self.ssl_enabled:
            params["https"] = True
            if self.ssl_cert_path:
                params["cert"] = self.ssl_cert_path

        if self.prefer_grpc and self.grpc_port:
            params["grpc_port"] = self.grpc_port
            params["prefer_grpc"] = True

        return params


class Vector(VectorBase):
    """Qdrant vector adapter implementation."""

    async def _create_client(self) -> AsyncQdrantClient:
        """Create Qdrant async client."""
        params = self.config.vector._build_connection_params()
        return AsyncQdrantClient(**params)

    async def init(self) -> None:
        """Initialize Qdrant vector adapter."""
        self.logger.info("Initializing Qdrant vector adapter")
        client = await self.get_client()

        # Test connection
        info = await client.get_cluster_info()
        self.logger.info(f"Connected to Qdrant cluster: {info}")

        self.logger.info("Qdrant vector adapter initialized successfully")

    # Implementation methods follow...
```

### Phase 3: Weaviate Implementation

```python
# acb/adapters/vector/weaviate.py

import typing as t
from uuid import UUID
import weaviate
from weaviate.classes.init import Auth
from acb.adapters import AdapterCapability, AdapterMetadata, AdapterStatus
from acb.depends import depends
from ._base import VectorBase, VectorBaseSettings, VectorDocument, VectorSearchResult

MODULE_ID = UUID("0197ff52-1234-7890-abcd-ef0123456789")
MODULE_STATUS = AdapterStatus.BETA

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
        AdapterCapability.CONNECTION_POOLING,
        AdapterCapability.TLS_SUPPORT,
        AdapterCapability.BULK_OPERATIONS,
        AdapterCapability.SCHEMA_VALIDATION,
    ],
    required_packages=["weaviate-client>=4.0.0"],
    description="Weaviate vector database adapter with hybrid search capabilities",
    settings_class="VectorSettings",
    config_example={
        "host": "localhost",
        "port": 8080,
        "api_key": "your-weaviate-api-key",  # pragma: allowlist secret
        "ssl_enabled": True,
    },
)

# Implementation follows similar pattern...
```

## Testing Strategy

### Test Structure

```
tests/adapters/vector/
├── __init__.py
├── conftest.py                 # Shared fixtures and mocks
├── test_base.py               # Base adapter functionality
├── test_duckdb.py             # DuckDB VSS implementation
├── test_qdrant.py             # Qdrant implementation
├── test_weaviate.py           # Weaviate implementation
└── test_vector_comprehensive.py  # Integration tests
```

### Key Test Categories

1. **Unit Tests**: Adapter-specific functionality
1. **Integration Tests**: End-to-end workflows
1. **Performance Tests**: Benchmarking and load testing
1. **Compatibility Tests**: Cross-adapter compatibility

### Mock Strategy

```python
# tests/adapters/vector/conftest.py

import pytest
from unittest.mock import AsyncMock, MagicMock
from acb.adapters.vector._base import VectorSearchResult, VectorDocument


@pytest.fixture
def mock_vector_client():
    """Mock vector database client."""
    client = AsyncMock()
    client.search.return_value = [
        VectorSearchResult(
            id="doc1",
            score=0.95,
            metadata={"title": "Test Document"},
        )
    ]
    return client


@pytest.fixture
def sample_vectors():
    """Sample vector documents for testing."""
    return [
        VectorDocument(
            id="doc1",
            vector=[0.1, 0.2, 0.3],
            metadata={"title": "Document 1"},
        ),
        VectorDocument(
            id="doc2",
            vector=[0.4, 0.5, 0.6],
            metadata={"title": "Document 2"},
        ),
    ]
```

## Configuration Management

### Adapter Selection

```yaml
# settings/adapters.yml
vector: duckdb  # Development default
# vector: qdrant  # Production option
# vector: weaviate  # Enterprise option
```

### Environment-Specific Configs

```yaml
# settings/vector/development.yml
database_path: "data/dev_vectors.db"
default_dimension: 384  # Smaller for development
enable_vss: true

# settings/vector/production.yml
host: "${QDRANT_HOST}"
port: 6333
api_key: "${QDRANT_API_KEY}"
ssl_enabled: true
max_connections: 50
batch_size: 1000
```

### Dynamic Collection Configuration

```python
# Runtime collection management
vector = depends.get(Vector)

# Create collection with specific settings
await vector.create_collection(
    name="documents",
    dimension=1536,
    distance_metric="cosine",
    index_config={
        "m": 16,
        "ef_construct": 200,
    },
)
```

## Integration Patterns

### RAG Application Integration

```python
from acb.depends import depends
from acb.adapters import import_adapter

# Import adapters
Vector = import_adapter("vector")
Models = import_adapter("models")


@depends.inject
async def semantic_search(
    query: str,
    vector: Vector = depends(),
    models: Models = depends(),
) -> list[dict]:
    # Generate embedding
    embedding = await generate_embedding(query)

    # Perform vector search
    results = await vector.documents.search(
        query_vector=embedding, limit=10, filter_expr={"status": "published"}
    )

    return [
        {
            "id": result.id,
            "score": result.score,
            "content": result.metadata.get("content"),
            "title": result.metadata.get("title"),
        }
        for result in results
    ]
```

### Batch Processing Pattern

```python
async def process_document_batch(documents: list[dict]) -> None:
    vector = depends.get(Vector)

    # Prepare vector documents
    vector_docs = []
    for doc in documents:
        embedding = await generate_embedding(doc["content"])
        vector_docs.append(
            VectorDocument(
                id=doc["id"],
                vector=embedding,
                metadata={
                    "title": doc["title"],
                    "category": doc["category"],
                    "timestamp": doc["created_at"],
                },
            )
        )

    # Batch insert
    await vector.documents.upsert(vector_docs)
```

## Performance Considerations

### Optimization Guidelines

1. **Batch Operations**: Use bulk insert/upsert for multiple documents
1. **Connection Pooling**: Configure appropriate pool sizes for production
1. **Index Configuration**: Tune HNSW parameters for your use case
1. **Memory Management**: Monitor memory usage for large vector collections
1. **Async Operations**: Leverage asyncio for concurrent operations

### Benchmarking Framework

```python
# Performance testing utilities
async def benchmark_search_performance(
    vector_adapter: Vector,
    collection: str,
    query_vectors: list[list[float]],
    batch_sizes: list[int],
) -> dict[str, float]:
    """Benchmark search performance across different configurations."""
    results = {}

    for batch_size in batch_sizes:
        start_time = time.time()

        tasks = []
        for i in range(0, len(query_vectors), batch_size):
            batch = query_vectors[i : i + batch_size]
            for query_vector in batch:
                task = vector_adapter.search(
                    collection=collection, query_vector=query_vector, limit=10
                )
                tasks.append(task)

        await asyncio.gather(*tasks)

        end_time = time.time()
        results[f"batch_size_{batch_size}"] = end_time - start_time

    return results
```

## Migration and Compatibility

### Database Migration Utilities

```python
# Migration utilities for switching between vector databases
async def migrate_collection(
    source_adapter: Vector,
    target_adapter: Vector,
    collection_name: str,
    batch_size: int = 1000,
) -> None:
    """Migrate vector collection between adapters."""

    # Get collection info
    total_count = await source_adapter.count(collection_name)
    self.logger.info(f"Migrating {total_count} documents from {collection_name}")

    # Batch migration
    offset = 0
    while offset < total_count:
        # Fetch batch from source
        documents = await source_adapter.get_batch(
            collection_name, offset=offset, limit=batch_size, include_vectors=True
        )

        # Insert into target
        await target_adapter.upsert(collection_name, documents)

        offset += batch_size
        self.logger.info(f"Migrated {min(offset, total_count)}/{total_count} documents")
```

### Compatibility Matrix

| Feature | DuckDB VSS | Qdrant | Weaviate | OpenSearch |
|---------|------------|--------|----------|------------|
| Local Development | ✅ | ❌ | ❌ | ❌ |
| Production Scale | ⚠️ | ✅ | ✅ | ✅ |
| Hybrid Search | ❌ | ✅ | ✅ | ✅ |
| Cloud Native | ❌ | ✅ | ✅ | ✅ |
| SQL Integration | ✅ | ❌ | ❌ | ⚠️ |
| Real-time Updates | ⚠️ | ✅ | ✅ | ✅ |

## Documentation Requirements

### Adapter-Specific Documentation

- **README.md**: Usage examples and configuration
- **API Documentation**: Complete method reference
- **Performance Guide**: Optimization recommendations
- **Migration Guide**: Switching between adapters

### Integration Examples

- RAG application patterns
- Semantic search implementations
- Batch processing workflows
- Performance monitoring

## Success Metrics

### Technical Metrics

- **Test Coverage**: >95% for all implementations
- **Performance**: \<50ms p99 latency for 1M vectors
- **Reliability**: >99.9% uptime in production scenarios
- **Memory Efficiency**: \<1GB RAM for 100K vectors

### Adoption Metrics

- **Developer Experience**: Consistent with existing ACB patterns
- **Documentation Quality**: Complete examples and guides
- **Community Feedback**: Positive reception from early adopters
- **Integration Success**: Smooth integration with existing ACB applications

## Risk Mitigation

### Technical Risks

1. **Performance Degradation**: Comprehensive benchmarking and optimization
1. **Memory Leaks**: Proper resource cleanup and monitoring
1. **Integration Complexity**: Thorough testing of edge cases
1. **Version Compatibility**: Pin dependencies and test upgrades

### Strategic Risks

1. **Market Changes**: Adapter pattern provides flexibility
1. **Technology Obsolescence**: Focus on stable, established solutions
1. **Maintenance Burden**: Clear documentation and testing strategy

## Conclusion

This implementation plan provides a comprehensive roadmap for adding vector database capabilities to ACB. The phased approach ensures a solid foundation while maintaining ACB's principles of simplicity and reliability. The adapter pattern provides flexibility to evolve with the rapidly changing vector database landscape while offering developers a consistent, familiar interface.

The vector adapter will position ACB as a leading framework for AI application development, providing the essential infrastructure needed for modern semantic search, RAG, and AI-powered applications.
