"""Graph database adapter base classes."""

from abc import ABC, abstractmethod
from enum import Enum

import typing as t
from datetime import datetime
from pydantic import BaseModel, Field, SecretStr

from acb.cleanup import CleanupMixin
from acb.config import Config, Settings
from acb.depends import Inject, depends
from acb.ssl_config import SSLConfigMixin


class GraphQueryLanguage(str, Enum):
    """Supported graph query languages."""

    CYPHER = "cypher"
    GREMLIN = "gremlin"
    AQL = "aql"
    SPARQL = "sparql"
    PGQ = "pgq"


class GraphTraversalDirection(str, Enum):
    """Graph traversal direction options."""

    OUT = "out"
    IN = "in"
    BOTH = "both"


class GraphNodeModel(BaseModel):
    """Base model for graph nodes."""

    id: str | None = None
    labels: list[str] = Field(default_factory=list)
    properties: dict[str, t.Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class GraphEdgeModel(BaseModel):
    """Base model for graph edges/relationships."""

    id: str | None = None
    type: str
    from_node: str
    to_node: str
    properties: dict[str, t.Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class GraphPathModel(BaseModel):
    """Base model for graph paths."""

    nodes: list[GraphNodeModel]
    edges: list[GraphEdgeModel]
    length: int
    weight: float | None = None


class GraphSchemaModel(BaseModel):
    """Base model for graph schema information."""

    node_types: list[str] = Field(default_factory=list)
    edge_types: list[str] = Field(default_factory=list)
    constraints: list[dict[str, t.Any]] = Field(default_factory=list)
    indexes: list[dict[str, t.Any]] = Field(default_factory=list)


class GraphQueryResult(BaseModel):
    """Base model for graph query results."""

    nodes: list[GraphNodeModel] = Field(default_factory=list)
    edges: list[GraphEdgeModel] = Field(default_factory=list)
    paths: list[GraphPathModel] = Field(default_factory=list)
    records: list[dict[str, t.Any]] = Field(default_factory=list)
    metadata: dict[str, t.Any] = Field(default_factory=dict)
    execution_time: float | None = None
    query_language: GraphQueryLanguage | None = None


class GraphBaseSettings(Settings, SSLConfigMixin):
    """Base settings for graph database adapters.

    Note: SSL configuration fields are defined for documentation purposes but are
    excluded from Pydantic validation to avoid conflicts with SSLConfigMixin properties.
    These fields are handled manually in __init__.
    """

    # Pydantic config to exclude SSL fields from validation (handled in __init__)
    model_config = {
        "extra": "allow",  # Allow extra fields for SSL config
    }

    # Connection settings
    host: SecretStr = SecretStr("127.0.0.1")
    port: int | None = None
    user: SecretStr | None = None
    password: SecretStr | None = None
    database: str | None = None
    auth_token: SecretStr | None = None

    # Connection pooling
    max_connections: int = 50
    min_connections: int = 1
    connection_timeout: float = 30.0
    idle_timeout: float = 600.0
    max_connection_lifetime: float = 3600.0

    # Query settings
    query_timeout: float = 300.0
    max_query_size: int = 1024 * 1024  # 1MB
    enable_query_logging: bool = False

    # Transaction settings
    transaction_timeout: float = 600.0
    auto_commit: bool = True

    # Performance settings
    enable_caching: bool = True
    cache_ttl: int = 300
    batch_size: int = 1000
    parallel_queries: bool = False

    # SSL/TLS Configuration (handled manually in __init__, not validated by Pydantic)
    # These are not Pydantic fields - they are popped in __init__ before validation
    # ssl_enabled: bool = False
    # ssl_cert_path: str | None = None
    # ssl_key_path: str | None = None
    # ssl_ca_path: str | None = None
    # ssl_verify_mode: str = "required"
    # tls_version: str = "TLSv1.2"

    @depends.inject
    def __init__(self, config: Inject[Config], **values: t.Any) -> None:
        # Extract SSL configuration parameters
        ssl_enabled = values.pop("ssl_enabled", False)
        ssl_cert_path = values.pop("ssl_cert_path", None)
        ssl_key_path = values.pop("ssl_key_path", None)
        ssl_ca_path = values.pop("ssl_ca_path", None)
        ssl_verify_mode = values.pop("ssl_verify_mode", "required")
        values.pop("tls_version", "TLSv1.2")

        super().__init__(**values)
        SSLConfigMixin.__init__(self)

        # Configure SSL if enabled
        if ssl_enabled:
            from acb.ssl_config import SSLVerifyMode

            verify_mode_map = {
                "none": SSLVerifyMode.NONE,
                "optional": SSLVerifyMode.OPTIONAL,
                "required": SSLVerifyMode.REQUIRED,
            }
            verify_mode = verify_mode_map.get(ssl_verify_mode, SSLVerifyMode.REQUIRED)

            self.configure_ssl(
                enabled=True,
                cert_path=ssl_cert_path,
                key_path=ssl_key_path,
                ca_path=ssl_ca_path,
                verify_mode=verify_mode,
                check_hostname=verify_mode == SSLVerifyMode.REQUIRED,
            )


class GraphProtocol(t.Protocol):
    """Protocol for graph database operations."""

    async def execute_query(
        self,
        query: str,
        parameters: dict[str, t.Any] | None = None,
    ) -> GraphQueryResult: ...

    async def create_node(
        self,
        labels: list[str] | None = None,
        properties: dict[str, t.Any] | None = None,
    ) -> GraphNodeModel: ...

    async def create_edge(
        self,
        edge_type: str,
        from_node_id: str,
        to_node_id: str,
        properties: dict[str, t.Any] | None = None,
    ) -> GraphEdgeModel: ...

    async def get_node(self, node_id: str) -> GraphNodeModel | None: ...

    async def get_edge(self, edge_id: str) -> GraphEdgeModel | None: ...

    async def find_path(
        self,
        from_node_id: str,
        to_node_id: str,
        max_depth: int | None = None,
        direction: GraphTraversalDirection = GraphTraversalDirection.BOTH,
    ) -> list[GraphPathModel]: ...


class GraphBase(CleanupMixin, ABC):
    """Base class for graph database adapters."""

    config: Inject[Config]
    logger: Inject[t.Any]

    def __init__(self, **kwargs: t.Any) -> None:
        CleanupMixin.__init__(self)
        self._client: t.Any = None
        self._client_lock: t.Any | None = (
            None  # Type as Any | None to satisfy async Lock
        )
        self._transaction: t.Any = None

    @property
    @abstractmethod
    def query_language(self) -> GraphQueryLanguage:
        """Return the primary query language supported by this adapter."""

    @property
    @abstractmethod
    def supported_features(self) -> list[str]:
        """Return list of supported features for this adapter."""

    async def _ensure_client(self) -> t.Any:
        """Ensure client connection with lazy initialization."""
        if self._client is None:
            if self._client_lock is None:
                import asyncio

                self._client_lock = asyncio.Lock()
            async with self._client_lock:
                if self._client is None:
                    self._client = await self._create_client()
        return self._client

    @abstractmethod
    async def _create_client(self) -> t.Any:
        """Create the database client connection."""

    async def _cleanup_resources(self) -> None:
        """Clean up graph-specific resources."""
        if self._transaction is not None:
            await self._rollback_transaction()
            self._transaction = None

        if self._client is not None:
            self.register_resource(self._client)
            self._client = None

        await super().cleanup()

    # Transaction Management
    async def begin_transaction(self) -> None:
        """Begin a new transaction."""
        client = await self._ensure_client()
        self._transaction = await self._begin_transaction(client)

    @abstractmethod
    async def _begin_transaction(self, client: t.Any) -> t.Any:
        """Implementation-specific transaction begin."""

    async def commit_transaction(self) -> None:
        """Commit the current transaction."""
        if self._transaction is None:
            msg = "No active transaction to commit"
            raise RuntimeError(msg)
        await self._commit_transaction(self._transaction)
        self._transaction = None

    @abstractmethod
    async def _commit_transaction(self, transaction: t.Any) -> None:
        """Implementation-specific transaction commit."""

    async def rollback_transaction(self) -> None:
        """Rollback the current transaction."""
        if self._transaction is None:
            msg = "No active transaction to rollback"
            raise RuntimeError(msg)
        await self._rollback_transaction()
        self._transaction = None

    @abstractmethod
    async def _rollback_transaction(self) -> None:
        """Implementation-specific transaction rollback."""

    # Core Graph Operations
    async def execute_query(
        self,
        query: str,
        parameters: dict[str, t.Any] | None = None,
        timeout: float | None = None,
    ) -> GraphQueryResult:
        """Execute a graph query and return results."""
        return await self._execute_query(query, parameters, timeout)

    @abstractmethod
    async def _execute_query(
        self,
        query: str,
        parameters: dict[str, t.Any] | None = None,
        timeout: float | None = None,
    ) -> GraphQueryResult:
        """Implementation-specific query execution."""

    async def execute_batch_queries(
        self,
        queries: list[tuple[str, dict[str, t.Any] | None]],
    ) -> list[GraphQueryResult]:
        """Execute multiple queries in batch."""
        results = []
        for query, params in queries:
            result = await self.execute_query(query, params)
            results.append(result)
        return results

    # Node Operations
    async def create_node(
        self,
        labels: list[str] | None = None,
        properties: dict[str, t.Any] | None = None,
    ) -> GraphNodeModel:
        """Create a new node in the graph."""
        return await self._create_node(labels or [], properties or {})

    @abstractmethod
    async def _create_node(
        self,
        labels: list[str],
        properties: dict[str, t.Any],
    ) -> GraphNodeModel:
        """Implementation-specific node creation."""

    async def get_node(self, node_id: str) -> GraphNodeModel | None:
        """Get a node by ID."""
        return await self._get_node(node_id)

    @abstractmethod
    async def _get_node(self, node_id: str) -> GraphNodeModel | None:
        """Implementation-specific node retrieval."""

    async def update_node(
        self,
        node_id: str,
        properties: dict[str, t.Any],
    ) -> GraphNodeModel:
        """Update node properties."""
        return await self._update_node(node_id, properties)

    @abstractmethod
    async def _update_node(
        self,
        node_id: str,
        properties: dict[str, t.Any],
    ) -> GraphNodeModel:
        """Implementation-specific node update."""

    async def delete_node(self, node_id: str) -> bool:
        """Delete a node from the graph."""
        return await self._delete_node(node_id)

    @abstractmethod
    async def _delete_node(self, node_id: str) -> bool:
        """Implementation-specific node deletion."""

    # Edge Operations
    async def create_edge(
        self,
        edge_type: str,
        from_node_id: str,
        to_node_id: str,
        properties: dict[str, t.Any] | None = None,
    ) -> GraphEdgeModel:
        """Create a new edge between nodes."""
        return await self._create_edge(
            edge_type,
            from_node_id,
            to_node_id,
            properties or {},
        )

    @abstractmethod
    async def _create_edge(
        self,
        edge_type: str,
        from_node_id: str,
        to_node_id: str,
        properties: dict[str, t.Any],
    ) -> GraphEdgeModel:
        """Implementation-specific edge creation."""

    async def get_edge(self, edge_id: str) -> GraphEdgeModel | None:
        """Get an edge by ID."""
        return await self._get_edge(edge_id)

    @abstractmethod
    async def _get_edge(self, edge_id: str) -> GraphEdgeModel | None:
        """Implementation-specific edge retrieval."""

    async def update_edge(
        self,
        edge_id: str,
        properties: dict[str, t.Any],
    ) -> GraphEdgeModel:
        """Update edge properties."""
        return await self._update_edge(edge_id, properties)

    @abstractmethod
    async def _update_edge(
        self,
        edge_id: str,
        properties: dict[str, t.Any],
    ) -> GraphEdgeModel:
        """Implementation-specific edge update."""

    async def delete_edge(self, edge_id: str) -> bool:
        """Delete an edge from the graph."""
        return await self._delete_edge(edge_id)

    @abstractmethod
    async def _delete_edge(self, edge_id: str) -> bool:
        """Implementation-specific edge deletion."""

    # Graph Traversal Operations
    async def find_path(
        self,
        from_node_id: str,
        to_node_id: str,
        max_depth: int | None = None,
        direction: GraphTraversalDirection = GraphTraversalDirection.BOTH,
    ) -> list[GraphPathModel]:
        """Find paths between two nodes."""
        return await self._find_path(from_node_id, to_node_id, max_depth, direction)

    @abstractmethod
    async def _find_path(
        self,
        from_node_id: str,
        to_node_id: str,
        max_depth: int | None,
        direction: GraphTraversalDirection,
    ) -> list[GraphPathModel]:
        """Implementation-specific path finding."""

    async def find_shortest_path(
        self,
        from_node_id: str,
        to_node_id: str,
        weight_property: str | None = None,
    ) -> GraphPathModel | None:
        """Find the shortest path between two nodes."""
        return await self._find_shortest_path(from_node_id, to_node_id, weight_property)

    @abstractmethod
    async def _find_shortest_path(
        self,
        from_node_id: str,
        to_node_id: str,
        weight_property: str | None,
    ) -> GraphPathModel | None:
        """Implementation-specific shortest path finding."""

    async def get_neighbors(
        self,
        node_id: str,
        direction: GraphTraversalDirection = GraphTraversalDirection.BOTH,
        edge_types: list[str] | None = None,
    ) -> list[GraphNodeModel]:
        """Get neighboring nodes."""
        return await self._get_neighbors(node_id, direction, edge_types)

    @abstractmethod
    async def _get_neighbors(
        self,
        node_id: str,
        direction: GraphTraversalDirection,
        edge_types: list[str] | None,
    ) -> list[GraphNodeModel]:
        """Implementation-specific neighbor retrieval."""

    # Schema and Analytics Operations
    async def get_schema(self) -> GraphSchemaModel:
        """Get graph schema information."""
        return await self._get_schema()

    @abstractmethod
    async def _get_schema(self) -> GraphSchemaModel:
        """Implementation-specific schema retrieval."""

    async def create_index(
        self,
        labels: list[str],
        properties: list[str],
        index_type: str = "btree",
    ) -> bool:
        """Create an index on specified properties."""
        return await self._create_index(labels, properties, index_type)

    @abstractmethod
    async def _create_index(
        self,
        labels: list[str],
        properties: list[str],
        index_type: str,
    ) -> bool:
        """Implementation-specific index creation."""

    async def drop_index(self, index_name: str) -> bool:
        """Drop an index."""
        return await self._drop_index(index_name)

    @abstractmethod
    async def _drop_index(self, index_name: str) -> bool:
        """Implementation-specific index deletion."""

    # Bulk Operations
    async def bulk_create_nodes(
        self,
        nodes: list[dict[str, t.Any]],
    ) -> list[GraphNodeModel]:
        """Create multiple nodes in bulk."""
        return await self._bulk_create_nodes(nodes)

    @abstractmethod
    async def _bulk_create_nodes(
        self,
        nodes: list[dict[str, t.Any]],
    ) -> list[GraphNodeModel]:
        """Implementation-specific bulk node creation."""

    async def bulk_create_edges(
        self,
        edges: list[dict[str, t.Any]],
    ) -> list[GraphEdgeModel]:
        """Create multiple edges in bulk."""
        return await self._bulk_create_edges(edges)

    @abstractmethod
    async def _bulk_create_edges(
        self,
        edges: list[dict[str, t.Any]],
    ) -> list[GraphEdgeModel]:
        """Implementation-specific bulk edge creation."""

    # Utility Methods
    async def count_nodes(self, labels: list[str] | None = None) -> int:
        """Count nodes in the graph."""
        return await self._count_nodes(labels)

    @abstractmethod
    async def _count_nodes(self, labels: list[str] | None) -> int:
        """Implementation-specific node counting."""

    async def count_edges(self, edge_types: list[str] | None = None) -> int:
        """Count edges in the graph."""
        return await self._count_edges(edge_types)

    @abstractmethod
    async def _count_edges(self, edge_types: list[str] | None) -> int:
        """Implementation-specific edge counting."""

    async def clear_graph(self) -> bool:
        """Clear all nodes and edges from the graph."""
        return await self._clear_graph()

    @abstractmethod
    async def _clear_graph(self) -> bool:
        """Implementation-specific graph clearing."""
