"""ArangoDB graph database adapter."""

from uuid import uuid4

import typing as t
from contextlib import suppress
from datetime import datetime
from pydantic import SecretStr

from acb.adapters import (
    AdapterCapability,
    AdapterMetadata,
    AdapterStatus,
    generate_adapter_id,
)
from acb.adapters.graph._base import (
    GraphBase,
    GraphBaseSettings,
    GraphEdgeModel,
    GraphNodeModel,
    GraphPathModel,
    GraphQueryLanguage,
    GraphQueryResult,
    GraphSchemaModel,
    GraphTraversalDirection,
)
from acb.config import Config
from acb.depends import Inject, depends

if t.TYPE_CHECKING:
    from arango.database import StandardDatabase  # type: ignore[import-not-found]
    from arango.graph import Graph as ArangoGraph  # type: ignore[import-not-found]

    # For type checking purposes, we define ArangoClient as Any to avoid import errors
    # because arango module doesn't explicitly export ArangoClient
    ArangoClient = t.Any  # type: ignore


MODULE_METADATA = AdapterMetadata(
    module_id=generate_adapter_id(),
    name="ArangoDB Graph Database",
    category="graph",
    provider="arangodb",
    version="1.0.0",
    acb_min_version="0.19.0",
    author="ACB Development Team",
    created_date="2025-09-30",
    last_modified="2025-09-30",
    status=AdapterStatus.STABLE,
    capabilities=[
        AdapterCapability.CONNECTION_POOLING,
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.TRANSACTIONS,
        AdapterCapability.TLS_SUPPORT,
        AdapterCapability.GRAPH_TRAVERSAL,
        AdapterCapability.AQL_QUERIES,
        AdapterCapability.GRAPH_ANALYTICS,
        AdapterCapability.PATHFINDING,
        AdapterCapability.SUBGRAPH_OPERATIONS,
        AdapterCapability.GRAPH_SCHEMA_VALIDATION,
        AdapterCapability.BULK_OPERATIONS,
        AdapterCapability.METRICS,
    ],
    required_packages=["python-arango>=7.0.0"],
    description="High-performance ArangoDB multi-model database adapter with AQL query support",
    settings_class="ArangoDBSettings",
)


class ArangoDBSettings(GraphBaseSettings):
    """ArangoDB-specific settings."""

    # ArangoDB connection settings
    host: SecretStr = SecretStr("127.0.0.1")
    port: int | None = 8529
    protocol: str = "http"
    database: str = "_system"

    # Graph settings
    graph_name: str = "default_graph"
    vertex_collections: list[str] | None = None
    edge_collections: list[str] | None = None

    # ArangoDB-specific settings
    enable_logging: bool = True
    request_timeout: float = 60.0
    max_retries: int = 3
    retry_backoff_factor: float = 2.0

    # Collection settings
    create_collections: bool = True
    replication_factor: int = 1
    write_concern: int = 1


class Graph(GraphBase):
    """ArangoDB graph database adapter."""

    config: Inject[Config]
    logger: Inject[t.Any]

    def __init__(self, **kwargs: t.Any) -> None:
        super().__init__(**kwargs)
        self._settings = ArangoDBSettings(**kwargs)
        self._client: t.Any | None = None
        self._database: StandardDatabase | None = None
        self._graph: ArangoGraph | None = None

    @property
    def query_language(self) -> GraphQueryLanguage:
        """Return AQL as the primary query language."""
        return GraphQueryLanguage.AQL

    @property
    def supported_features(self) -> list[str]:
        """Return ArangoDB supported features."""
        return [
            "aql_queries",
            "multi_model",
            "acid_transactions",
            "sharding",
            "replication",
            "full_text_search",
            "geospatial_queries",
            "graph_algorithms",
            "custom_functions",
            "foxx_services",
            "streaming_cursors",
            "batch_operations",
        ]

    async def _create_client(self) -> "StandardDatabase":
        """Create ArangoDB client and database connection."""
        try:
            from arango import ArangoClient  # type: ignore
        except ImportError as e:
            msg = "python-arango package is required for ArangoDB adapter"
            raise ImportError(msg) from e

        # Build connection URL
        url = f"{self._settings.protocol}://{self._settings.host}:{self._settings.port}"

        # Create client
        self._client = ArangoClient(
            hosts=url,
            request_timeout=self._settings.request_timeout,
        )

        # Connect to database
        auth = None
        if self._settings.user and self._settings.password:
            auth = (
                self._settings.user.get_secret_value(),
                self._settings.password.get_secret_value(),
            )

        # Type checker doesn't know _client is not None after assignment above
        assert self._client is not None
        if auth:
            self._database = self._client.db(
                name=self._settings.database,
                username=auth[0],
                password=auth[1],
            )
        else:
            self._database = self._client.db(
                name=self._settings.database,
            )

        # Ensure graph exists
        await self._ensure_graph()

        self.logger.info(
            "Connected to ArangoDB database",
            extra={"url": url, "database": self._settings.database},
        )

        return self._database

    async def _ensure_graph(self) -> None:
        """Ensure the graph exists in ArangoDB."""
        if not self._database:
            return

        graph_name = self._settings.graph_name

        # Check if graph exists
        if not self._database.has_graph(graph_name):
            # Create graph with edge definitions
            edge_definitions = []

            # Use default collections if not specified
            vertex_collections = self._settings.vertex_collections or ["vertices"]
            edge_collections = self._settings.edge_collections or ["edges"]

            for edge_collection in edge_collections:
                edge_definitions.append(
                    {
                        "edge_collection": edge_collection,
                        "from_vertex_collections": vertex_collections,
                        "to_vertex_collections": vertex_collections,
                    },
                )

            self._database.create_graph(
                name=graph_name,
                edge_definitions=edge_definitions,
            )

            self.logger.info("Created ArangoDB graph", extra={"graph_name": graph_name})

        # Get graph instance
        self._graph = self._database.graph(graph_name)

    async def _begin_transaction(self, client: "StandardDatabase") -> t.Any:
        """Begin an ArangoDB transaction."""
        # ArangoDB transactions are handled through the database instance
        # Return a transaction context
        return client.begin_transaction(
            read=list(self._get_all_collections()),
            write=list(self._get_all_collections()),
        )

    async def _commit_transaction(self, transaction: t.Any) -> None:
        """Commit an ArangoDB transaction."""
        transaction.commit_transaction()

    async def _rollback_transaction(self) -> None:
        """Rollback an ArangoDB transaction."""
        if self._transaction:
            self._transaction.abort_transaction()

    def _get_all_collections(self) -> set[str]:
        """Get all vertex and edge collection names."""
        collections = set()
        if self._settings.vertex_collections:
            collections.update(self._settings.vertex_collections)
        if self._settings.edge_collections:
            collections.update(self._settings.edge_collections)
        if not collections:
            collections.update(["vertices", "edges"])
        return collections

    def _is_vertex_record(self, record: dict[str, t.Any]) -> bool:
        """Check if record is a vertex."""
        if "_id" not in record or "/" not in record["_id"]:
            return False

        collection = record["_id"].split("/", 1)[0]
        vertex_collections = self._settings.vertex_collections or ["vertices"]
        return collection in vertex_collections

    def _is_edge_record(self, record: dict[str, t.Any]) -> bool:
        """Check if record is an edge."""
        return "_from" in record and "_to" in record

    def _parse_query_records(
        self,
        cursor: t.Any,
    ) -> tuple[
        list[dict[str, t.Any]], dict[str, GraphNodeModel], dict[str, GraphEdgeModel]
    ]:
        """Parse cursor records into categorized results using set-based deduplication."""
        records = []
        nodes_by_id: dict[str, GraphNodeModel] = {}
        edges_by_id: dict[str, GraphEdgeModel] = {}

        for record in cursor:
            records.append(record)

            if not isinstance(record, dict):
                continue

            # Check vertex first (more common)
            if self._is_vertex_record(record):
                node = self._arango_doc_to_node(record)
                if node.id is not None:
                    nodes_by_id[node.id] = node
            elif self._is_edge_record(record):
                edge = self._arango_doc_to_edge(record)
                if edge.id is not None:
                    edges_by_id[edge.id] = edge

        return records, nodes_by_id, edges_by_id

    async def _execute_query(
        self,
        query: str,
        parameters: dict[str, t.Any] | None = None,
        timeout: float | None = None,
    ) -> GraphQueryResult:
        """Execute an AQL query."""
        database = await self._ensure_client()
        start_time = datetime.now()

        try:
            # Execute AQL query
            cursor = database.aql.execute(
                query,
                bind_vars=parameters or {},
                count=True,
                batch_size=self._settings.batch_size,
                ttl=timeout or self._settings.query_timeout,
            )

            # Parse records with efficient deduplication
            records, nodes_by_id, edges_by_id = self._parse_query_records(cursor)

            execution_time = (datetime.now() - start_time).total_seconds()

            return GraphQueryResult(
                nodes=list(nodes_by_id.values()),
                edges=list(edges_by_id.values()),
                paths=[],
                records=records,
                execution_time=execution_time,
                query_language=GraphQueryLanguage.AQL,
                metadata={
                    "query": query,
                    "parameters": parameters or {},
                    "statistics": cursor.statistics(),
                },
            )

        except Exception as e:
            self.logger.exception(
                "Failed to execute AQL query",
                extra={"error": str(e), "query": query},
            )
            raise

    async def _create_node(
        self,
        labels: list[str],
        properties: dict[str, t.Any],
    ) -> GraphNodeModel:
        """Create a vertex in ArangoDB."""
        database = await self._ensure_client()

        # Add timestamps and ID
        properties["created_at"] = datetime.now().isoformat()
        properties["updated_at"] = datetime.now().isoformat()
        if "_key" not in properties:
            properties["_key"] = str(uuid4())

        # Use first label as collection name, or default
        collection_name = labels[0] if labels else "vertices"
        if (
            self._settings.vertex_collections
            and collection_name not in self._settings.vertex_collections
        ):
            collection_name = self._settings.vertex_collections[0]

        # Ensure collection exists
        if not database.has_collection(collection_name):
            database.create_collection(collection_name)

        # Insert vertex
        collection = database.collection(collection_name)
        result = collection.insert(properties, return_new=True)

        new_doc = result["new"]
        return GraphNodeModel(
            id=new_doc["_id"],
            labels=labels,
            properties=properties,
            created_at=datetime.fromisoformat(properties["created_at"]),
            updated_at=datetime.fromisoformat(properties["updated_at"]),
        )

    async def _get_node(self, node_id: str) -> GraphNodeModel | None:
        """Get a vertex by ID."""
        database = await self._ensure_client()

        with suppress(Exception):
            # Parse collection and key from ID
            if "/" in node_id:
                return await self._get_node_by_full_id(database, node_id)
            return await self._search_vertex_collections(database, node_id)

        return None

    async def _get_node_by_full_id(
        self,
        database: "StandardDatabase",
        node_id: str,
    ) -> GraphNodeModel | None:
        """Get node by full collection/key ID.

        Args:
            database: ArangoDB database instance
            node_id: Full node ID with collection (e.g., "vertices/123")

        Returns:
            Node if found, None otherwise
        """
        collection_name, doc_key = node_id.split("/", 1)

        if not database.has_collection(collection_name):
            return None

        collection = database.collection(collection_name)
        doc = collection.get(doc_key)
        if doc is not None and isinstance(doc, dict):
            return self._arango_doc_to_node(doc)
        return None

    async def _search_vertex_collections(
        self,
        database: "StandardDatabase",
        node_id: str,
    ) -> GraphNodeModel | None:
        """Search all vertex collections for a node by key.

        Args:
            database: ArangoDB database instance
            node_id: Node key to search for

        Returns:
            Node if found in any collection, None otherwise
        """
        vertex_collections = self._settings.vertex_collections or ["vertices"]

        for collection_name in vertex_collections:
            if not database.has_collection(collection_name):
                continue

            collection = database.collection(collection_name)
            if collection.has(node_id):
                doc = collection.get(node_id)
                if doc is not None and isinstance(doc, dict):
                    return self._arango_doc_to_node(doc)

        return None

    async def _update_node(
        self,
        node_id: str,
        properties: dict[str, t.Any],
    ) -> GraphNodeModel:
        """Update vertex properties."""
        database = await self._ensure_client()
        properties["updated_at"] = datetime.now().isoformat()

        # Parse collection and key from ID
        collection_name, doc_key = node_id.split("/", 1)

        if database.has_collection(collection_name):
            collection = database.collection(collection_name)
            result = collection.update(doc_key, properties, return_new=True)
            new_doc = result["new"]
            return self._arango_doc_to_node(new_doc)

        msg = f"Node with ID {node_id} not found"
        raise ValueError(msg)

    async def _delete_node(self, node_id: str) -> bool:
        """Delete a vertex."""
        database = await self._ensure_client()

        # Parse collection and key from ID
        collection_name, doc_key = node_id.split("/", 1)

        if database.has_collection(collection_name):
            collection = database.collection(collection_name)
            collection.delete(doc_key)
            return True

        return False

    async def _create_edge(
        self,
        edge_type: str,
        from_node_id: str,
        to_node_id: str,
        properties: dict[str, t.Any],
    ) -> GraphEdgeModel:
        """Create an edge between vertices."""
        database = await self._ensure_client()

        # Add timestamps, ID, and ArangoDB edge fields
        properties["created_at"] = datetime.now().isoformat()
        properties["updated_at"] = datetime.now().isoformat()
        properties["_from"] = from_node_id
        properties["_to"] = to_node_id
        if "_key" not in properties:
            properties["_key"] = str(uuid4())

        # Use edge type as collection name, or default
        collection_name = edge_type
        if (
            self._settings.edge_collections
            and collection_name not in self._settings.edge_collections
        ):
            collection_name = self._settings.edge_collections[0]
        elif not self._settings.edge_collections:
            collection_name = "edges"

        # Ensure edge collection exists
        if not database.has_collection(collection_name):
            database.create_collection(collection_name, edge=True)

        # Insert edge
        collection = database.collection(collection_name)
        result = collection.insert(properties, return_new=True)

        new_doc = result["new"]
        return GraphEdgeModel(
            id=new_doc["_id"],
            type=edge_type,
            from_node=from_node_id,
            to_node=to_node_id,
            properties=properties,
            created_at=datetime.fromisoformat(properties["created_at"]),
            updated_at=datetime.fromisoformat(properties["updated_at"]),
        )

    async def _get_edge(self, edge_id: str) -> GraphEdgeModel | None:
        """Get an edge by ID."""
        database = await self._ensure_client()

        with suppress(Exception):
            # Parse collection and key from ID
            collection_name, doc_key = edge_id.split("/", 1)

            if database.has_collection(collection_name):
                collection = database.collection(collection_name)
                doc = collection.get(doc_key)
                return self._arango_doc_to_edge(doc)

        return None

    async def _update_edge(
        self,
        edge_id: str,
        properties: dict[str, t.Any],
    ) -> GraphEdgeModel:
        """Update edge properties."""
        database = await self._ensure_client()
        properties["updated_at"] = datetime.now().isoformat()

        # Parse collection and key from ID
        collection_name, doc_key = edge_id.split("/", 1)

        if database.has_collection(collection_name):
            collection = database.collection(collection_name)
            result = collection.update(doc_key, properties, return_new=True)
            new_doc = result["new"]
            return self._arango_doc_to_edge(new_doc)

        msg = f"Edge with ID {edge_id} not found"
        raise ValueError(msg)

    async def _delete_edge(self, edge_id: str) -> bool:
        """Delete an edge."""
        database = await self._ensure_client()

        # Parse collection and key from ID
        collection_name, doc_key = edge_id.split("/", 1)

        if database.has_collection(collection_name):
            collection = database.collection(collection_name)
            collection.delete(doc_key)
            return True

        return False

    async def _find_path(
        self,
        from_node_id: str,
        to_node_id: str,
        max_depth: int | None,
        direction: GraphTraversalDirection,
    ) -> list[GraphPathModel]:
        """Find paths between vertices using AQL."""
        direction_clause = ""
        if direction == GraphTraversalDirection.OUT:
            direction_clause = "OUTBOUND"
        elif direction == GraphTraversalDirection.IN:
            direction_clause = "INBOUND"
        else:
            direction_clause = "ANY"

        depth_clause = f"1..{max_depth}" if max_depth else "1..10"

        # Get all edge collections
        edge_collections = self._settings.edge_collections or ["edges"]
        edge_collections_str = ", ".join(edge_collections)

        query = f"""
        FOR v, e, p IN {depth_clause} {direction_clause} @start_vertex {edge_collections_str}
        FILTER v._id == @end_vertex
        RETURN p
        """

        result = await self._execute_query(
            query,
            {
                "start_vertex": from_node_id,
                "end_vertex": to_node_id,
            },
        )

        paths = []
        for record in result.records:
            if "vertices" in record and "edges" in record:
                nodes = [self._arango_doc_to_node(v) for v in record["vertices"]]
                edges = [self._arango_doc_to_edge(e) for e in record["edges"]]
                paths.append(
                    GraphPathModel(
                        nodes=nodes,
                        edges=edges,
                        length=len(edges),
                    ),
                )

        return paths

    async def _find_shortest_path(
        self,
        from_node_id: str,
        to_node_id: str,
        weight_property: str | None,
    ) -> GraphPathModel | None:
        """Find shortest path between vertices."""
        # Get all edge collections
        edge_collections = self._settings.edge_collections or ["edges"]
        edge_collections_str = ", ".join(edge_collections)

        if weight_property:
            query = f"""
            FOR v, e IN OUTBOUND SHORTEST_PATH @start_vertex TO @end_vertex {edge_collections_str}
            OPTIONS {{weightAttribute: @weight_property}}
            RETURN {{vertex: v, edge: e}}
            """
            params = {
                "start_vertex": from_node_id,
                "end_vertex": to_node_id,
                "weight_property": weight_property,
            }
        else:
            query = f"""
            FOR v, e IN OUTBOUND SHORTEST_PATH @start_vertex TO @end_vertex {edge_collections_str}
            RETURN {{vertex: v, edge: e}}
            """
            params = {"start_vertex": from_node_id, "end_vertex": to_node_id}

        result = await self._execute_query(query, params)

        if result.records:
            nodes = []
            edges = []

            for record in result.records:
                if record.get("vertex"):
                    nodes.append(self._arango_doc_to_node(record["vertex"]))
                if record.get("edge"):
                    edges.append(self._arango_doc_to_edge(record["edge"]))

            return GraphPathModel(
                nodes=nodes,
                edges=edges,
                length=len(edges),
            )

        return None

    async def _get_neighbors(
        self,
        node_id: str,
        direction: GraphTraversalDirection,
        edge_types: list[str] | None,
    ) -> list[GraphNodeModel]:
        """Get neighboring vertices."""
        direction_clause = ""
        if direction == GraphTraversalDirection.OUT:
            direction_clause = "OUTBOUND"
        elif direction == GraphTraversalDirection.IN:
            direction_clause = "INBOUND"
        else:
            direction_clause = "ANY"

        # Filter by edge types if specified
        edge_collections = edge_types or self._settings.edge_collections or ["edges"]
        edge_collections_str = ", ".join(edge_collections)

        query = f"""
        FOR neighbor IN 1..1 {direction_clause} @vertex {edge_collections_str}
        RETURN neighbor
        """

        result = await self._execute_query(query, {"vertex": node_id})
        return [self._arango_doc_to_node(record) for record in result.records]

    async def _get_schema(self) -> GraphSchemaModel:
        """Get ArangoDB schema information."""
        database = await self._ensure_client()

        # Get all collections
        collections = database.collections()

        vertex_collections = []
        edge_collections = []

        for collection in collections:
            if collection["type"] == 2:  # Document collection (vertex)
                vertex_collections.append(collection["name"])
            elif collection["type"] == 3:  # Edge collection
                edge_collections.append(collection["name"])

        # Get indexes
        indexes = []
        for collection_info in collections:
            collection = database.collection(collection_info["name"])
            collection_indexes = collection.indexes()
            for index in collection_indexes:
                indexes.append(
                    {
                        "collection": collection_info["name"],
                        "type": index.get("type"),
                        "fields": index.get("fields", []),
                        "unique": index.get("unique", False),
                    },
                )

        return GraphSchemaModel(
            node_types=vertex_collections,
            edge_types=edge_collections,
            constraints=[],  # ArangoDB constraints would be extracted here
            indexes=indexes,
        )

    async def _create_index(
        self,
        labels: list[str],
        properties: list[str],
        index_type: str,
    ) -> bool:
        """Create an index on properties."""
        database = await self._ensure_client()

        for label in labels:
            if database.has_collection(label):
                collection = database.collection(label)
                collection.add_index(
                    {
                        "type": index_type,
                        "fields": properties,
                    },
                )

        return True

    async def _drop_index(self, index_name: str) -> bool:
        """Drop an index."""
        database = await self._ensure_client()

        # Find and drop the index across all collections
        collections = database.collections()
        for collection_info in collections:
            collection = database.collection(collection_info["name"])
            indexes = collection.indexes()
            for index in indexes:
                if index.get("name") == index_name:
                    collection.delete_index(index["id"])
                    return True

        return False

    async def _bulk_create_nodes(
        self,
        nodes: list[dict[str, t.Any]],
    ) -> list[GraphNodeModel]:
        """Create multiple vertices in bulk."""
        database = await self._ensure_client()
        collections_data = self._group_nodes_by_collection(nodes)
        return self._insert_node_collections(database, collections_data)

    def _group_nodes_by_collection(
        self,
        nodes: list[dict[str, t.Any]],
    ) -> dict[str, list[dict[str, t.Any]]]:
        collections: dict[str, list[dict[str, t.Any]]] = {}
        for node_data in nodes:
            labels = node_data.get("labels") or ["vertices"]
            properties = self._prepare_node_properties(node_data.get("properties", {}))
            collections.setdefault(labels[0], []).append(properties)
        return collections

    def _prepare_node_properties(
        self, properties: dict[str, t.Any]
    ) -> dict[str, t.Any]:
        prepared = properties.copy()
        timestamp = datetime.now().isoformat()
        prepared.setdefault("_key", str(uuid4()))
        prepared["created_at"] = timestamp
        prepared["updated_at"] = timestamp
        return prepared

    def _insert_node_collections(
        self,
        database: t.Any,
        collections_data: dict[str, list[dict[str, t.Any]]],
    ) -> list[GraphNodeModel]:
        results: list[GraphNodeModel] = []
        for collection_name, docs in collections_data.items():
            if not database.has_collection(collection_name):
                database.create_collection(collection_name)

            collection = database.collection(collection_name)
            bulk_result = collection.insert_many(docs, return_new=True)

            # Handle different return types from insert_many
            if isinstance(bulk_result, list):
                results.extend(
                    self._arango_doc_to_node(item["new"])
                    for item in bulk_result
                    if isinstance(item, dict) and "new" in item
                )

        return results

    async def _bulk_create_edges(
        self,
        edges: list[dict[str, t.Any]],
    ) -> list[GraphEdgeModel]:
        """Create multiple edges in bulk."""
        database = await self._ensure_client()

        # Group edges by collection and prepare properties
        collections_data = self._prepare_edge_collections(edges)

        # Bulk insert into each collection
        return await self._insert_edge_collections(database, collections_data)

    def _prepare_edge_collections(
        self,
        edges: list[dict[str, t.Any]],
    ) -> dict[str, list[dict[str, t.Any]]]:
        """Group edges by collection and add required fields.

        Args:
            edges: List of edge data dictionaries

        Returns:
            Dictionary mapping collection names to edge documents
        """
        collections_data: dict[str, list[dict[str, t.Any]]] = {}

        for edge_data in edges:
            edge_type = edge_data["type"]
            properties = self._prepare_edge_properties(edge_data)

            if edge_type not in collections_data:
                collections_data[edge_type] = []
            collections_data[edge_type].append(properties)

        return collections_data

    def _prepare_edge_properties(self, edge_data: dict[str, t.Any]) -> dict[str, t.Any]:
        """Prepare edge properties with required fields.

        Args:
            edge_data: Raw edge data

        Returns:
            Properties dictionary with required fields added
        """
        properties = edge_data.get("properties", {}).copy()

        # Add required edge fields
        properties["created_at"] = datetime.now().isoformat()
        properties["updated_at"] = datetime.now().isoformat()
        properties["_from"] = edge_data["from_node"]
        properties["_to"] = edge_data["to_node"]

        if "_key" not in properties:
            properties["_key"] = str(uuid4())

        return properties

    async def _insert_edge_collections(
        self,
        database: "StandardDatabase",
        collections_data: dict[str, list[dict[str, t.Any]]],
    ) -> list[GraphEdgeModel]:
        """Insert edges into their respective collections.

        Args:
            database: ArangoDB database instance
            collections_data: Mapping of collection names to edge documents

        Returns:
            List of created edge models
        """
        results = []

        for collection_name, docs in collections_data.items():
            # Ensure collection exists
            if not database.has_collection(collection_name):
                database.create_collection(collection_name, edge=True)

            # Bulk insert
            collection = database.collection(collection_name)
            bulk_result = collection.insert_many(docs, return_new=True)

            # Convert results to edge models
            # Handle different return types from insert_many
            if isinstance(bulk_result, list):
                for item in bulk_result:
                    if isinstance(item, dict) and "new" in item:
                        results.append(self._arango_doc_to_edge(item["new"]))

        return results

    async def _count_nodes(self, labels: list[str] | None) -> int:
        """Count vertices in the graph."""
        if labels:
            total = 0
            for label in labels:
                query = f"RETURN LENGTH({label})"
                result = await self._execute_query(query)
                if result.records and isinstance(result.records[0], int):
                    total += result.records[0]
            return total
        vertex_collections = self._settings.vertex_collections or ["vertices"]
        total = 0
        for collection_name in vertex_collections:
            query = f"RETURN LENGTH({collection_name})"
            result = await self._execute_query(query)
            if result.records and isinstance(result.records[0], int):
                total += result.records[0]
        return total

    async def _count_edges(self, edge_types: list[str] | None) -> int:
        """Count edges in the graph."""
        if edge_types:
            total = 0
            for edge_type in edge_types:
                query = f"RETURN LENGTH({edge_type})"
                result = await self._execute_query(query)
                if result.records and isinstance(result.records[0], int):
                    total += result.records[0]
            return total
        edge_collections = self._settings.edge_collections or ["edges"]
        total = 0
        for collection_name in edge_collections:
            query = f"RETURN LENGTH({collection_name})"
            result = await self._execute_query(query)
            if result.records and isinstance(result.records[0], int):
                total += result.records[0]
        return total

    async def _clear_graph(self) -> bool:
        """Clear all vertices and edges."""
        database = await self._ensure_client()

        # Clear all vertex collections
        vertex_collections = self._settings.vertex_collections or ["vertices"]
        for collection_name in vertex_collections:
            if database.has_collection(collection_name):
                collection = database.collection(collection_name)
                collection.truncate()

        # Clear all edge collections
        edge_collections = self._settings.edge_collections or ["edges"]
        for collection_name in edge_collections:
            if database.has_collection(collection_name):
                collection = database.collection(collection_name)
                collection.truncate()

        return True

    def _arango_doc_to_node(self, doc: dict[str, t.Any]) -> GraphNodeModel:
        """Convert ArangoDB document to GraphNodeModel."""
        # Extract ArangoDB system fields
        doc_id = doc.get("_id", "")
        collection_name = doc_id.split("/")[0] if "/" in doc_id else ""

        # Remove system fields from properties
        properties = {k: v for k, v in doc.items() if not k.startswith("_")}

        return GraphNodeModel(
            id=doc_id,
            labels=[collection_name] if collection_name else [],
            properties=properties,
            created_at=(
                datetime.fromisoformat(properties["created_at"])
                if "created_at" in properties
                else None
            ),
            updated_at=(
                datetime.fromisoformat(properties["updated_at"])
                if "updated_at" in properties
                else None
            ),
        )

    def _arango_doc_to_edge(self, doc: dict[str, t.Any]) -> GraphEdgeModel:
        """Convert ArangoDB edge document to GraphEdgeModel."""
        # Extract ArangoDB system fields
        doc_id = doc.get("_id", "")
        collection_name = doc_id.split("/")[0] if "/" in doc_id else ""
        from_node = doc.get("_from", "")
        to_node = doc.get("_to", "")

        # Remove system fields from properties
        properties = {k: v for k, v in doc.items() if not k.startswith("_")}

        return GraphEdgeModel(
            id=doc_id,
            type=collection_name,
            from_node=from_node,
            to_node=to_node,
            properties=properties,
            created_at=(
                datetime.fromisoformat(properties["created_at"])
                if "created_at" in properties
                else None
            ),
            updated_at=(
                datetime.fromisoformat(properties["updated_at"])
                if "updated_at" in properties
                else None
            ),
        )


depends.set(Graph, "arangodb")
