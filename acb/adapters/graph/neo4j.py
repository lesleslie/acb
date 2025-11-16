"""Neo4j graph database adapter."""

from uuid import uuid4

import typing as t
from datetime import datetime
from pydantic import SecretStr
from typing import Any

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
    from neo4j import AsyncDriver, AsyncTransaction  # type: ignore[import-not-found]


MODULE_METADATA = AdapterMetadata(
    module_id=generate_adapter_id(),
    name="Neo4j Graph Database",
    category="graph",
    provider="neo4j",
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
        AdapterCapability.CYPHER_QUERIES,
        AdapterCapability.GRAPH_ANALYTICS,
        AdapterCapability.PATHFINDING,
        AdapterCapability.SUBGRAPH_OPERATIONS,
        AdapterCapability.GRAPH_SCHEMA_VALIDATION,
        AdapterCapability.BULK_OPERATIONS,
        AdapterCapability.METRICS,
    ],
    required_packages=["neo4j>=5.0.0"],
    description="High-performance Neo4j graph database adapter with full Cypher query support",
    settings_class="Neo4jSettings",
)


class Neo4jSettings(GraphBaseSettings):
    """Neo4j-specific settings."""

    # Neo4j connection settings
    host: SecretStr = SecretStr("127.0.0.1")
    port: int | None = 7687
    scheme: str = "bolt"
    database: str = "neo4j"

    # Neo4j-specific settings
    max_connection_lifetime: float = 3600.0
    connection_acquisition_timeout: float = 60.0
    max_transaction_retry_time: float = 30.0
    initial_retry_delay: float = 1.0
    retry_delay_multiplier: float = 2.0
    retry_delay_jitter_factor: float = 0.2

    # Cypher query settings
    explain_queries: bool = False
    profile_queries: bool = False


class Graph(GraphBase):
    """Neo4j graph database adapter."""

    config: Inject[Config]
    logger: Inject[t.Any]

    def __init__(self, **kwargs: t.Any) -> None:
        super().__init__(**kwargs)
        self._settings = Neo4jSettings(**kwargs)
        self._driver: AsyncDriver | None = None

    @property
    def query_language(self) -> GraphQueryLanguage:
        """Return Cypher as the primary query language."""
        return GraphQueryLanguage.CYPHER

    @property
    def supported_features(self) -> list[str]:
        """Return Neo4j supported features."""
        return [
            "cypher_queries",
            "transactions",
            "apoc_procedures",
            "graph_algorithms",
            "full_text_search",
            "spatial_queries",
            "temporal_queries",
            "multi_tenancy",
            "clustering",
        ]

    async def _create_client(self) -> "AsyncDriver":
        """Create Neo4j driver connection."""
        try:
            from neo4j import AsyncGraphDatabase  # type: ignore[import-not-found]
        except ImportError as e:
            msg = "neo4j package is required for Neo4j adapter"
            raise ImportError(msg) from e

        # Build URI
        uri = f"{self._settings.scheme}://{self._settings.host}:{self._settings.port}"

        # Configure authentication
        auth = None
        if self._settings.user and self._settings.password:
            auth = (
                self._settings.user.get_secret_value(),
                self._settings.password.get_secret_value(),
            )

        # Create driver with configuration
        driver = AsyncGraphDatabase.driver(
            uri,
            auth=auth,
            max_connection_lifetime=self._settings.max_connection_lifetime,
            connection_acquisition_timeout=self._settings.connection_acquisition_timeout,
            max_connection_pool_size=self._settings.max_connections,
            max_transaction_retry_time=self._settings.max_transaction_retry_time,
            initial_retry_delay=self._settings.initial_retry_delay,
            retry_delay_multiplier=self._settings.retry_delay_multiplier,
            retry_delay_jitter_factor=self._settings.retry_delay_jitter_factor,
            encrypted=self._settings.ssl_enabled,
        )

        # Verify connectivity
        await driver.verify_connectivity()
        self.logger.info("Connected to Neo4j database", extra={"uri": uri})

        return driver

    async def _begin_transaction(self, client: "AsyncDriver") -> "AsyncTransaction":
        """Begin a Neo4j transaction."""
        session = client.session(database=self._settings.database)
        return await session.begin_transaction()

    async def _commit_transaction(self, transaction: "AsyncTransaction") -> None:
        """Commit a Neo4j transaction."""
        await transaction.commit()
        await transaction.close()

    async def _rollback_transaction(self) -> None:
        """Rollback a Neo4j transaction."""
        if self._transaction:
            await self._transaction.rollback()
            await self._transaction.close()

    def _categorize_record_value(
        self,
        value: t.Any,
        nodes_by_id: dict[str, GraphNodeModel],
        edges_by_id: dict[str, GraphEdgeModel],
        paths: list[GraphPathModel],
    ) -> None:
        """Categorize a single record value into nodes, edges, or paths."""
        if hasattr(value, "labels"):  # Node
            node = self._neo4j_node_to_model(value)
            if node.id is not None:
                nodes_by_id[node.id] = node
        elif hasattr(value, "type"):  # Relationship
            edge = self._neo4j_relationship_to_model(value)
            if edge.id is not None:
                edges_by_id[edge.id] = edge
        elif hasattr(value, "nodes"):  # Path
            path = self._neo4j_path_to_model(value)
            paths.append(path)

    async def _parse_query_result(
        self,
        result: t.Any,
    ) -> tuple[
        list[dict[str, t.Any]],
        dict[str, GraphNodeModel],
        dict[str, GraphEdgeModel],
        list[GraphPathModel],
    ]:
        """Parse query result with efficient deduplication."""
        records = []
        nodes_by_id: dict[str, GraphNodeModel] = {}
        edges_by_id: dict[str, GraphEdgeModel] = {}
        paths: list[GraphPathModel] = []

        async for record in result:
            record_dict = dict(record)
            records.append(record_dict)

            # Extract graph elements from record values
            for value in record.values():
                self._categorize_record_value(value, nodes_by_id, edges_by_id, paths)

        return records, nodes_by_id, edges_by_id, paths

    async def _run_query(
        self,
        session: t.Any,
        query: str,
        parameters: dict[str, t.Any],
    ) -> t.Any:
        """Run query using transaction if available, otherwise auto-commit."""
        if self._transaction:
            return await self._transaction.run(query, parameters)
        return await session.run(query, parameters)

    async def _execute_query(
        self,
        query: str,
        parameters: dict[str, t.Any] | None = None,
        timeout: float | None = None,
    ) -> GraphQueryResult:
        """Execute a Cypher query."""
        client = await self._ensure_client()
        start_time = datetime.now()

        try:
            async with client.session(database=self._settings.database) as session:
                result = await self._run_query(session, query, parameters or {})

                # Parse result with efficient deduplication
                (
                    records,
                    nodes_by_id,
                    edges_by_id,
                    paths,
                ) = await self._parse_query_result(result)

                execution_time = (datetime.now() - start_time).total_seconds()

                return GraphQueryResult(
                    nodes=list(nodes_by_id.values()),
                    edges=list(edges_by_id.values()),
                    paths=paths,
                    records=records,
                    execution_time=execution_time,
                    query_language=GraphQueryLanguage.CYPHER,
                    metadata={"query": query, "parameters": parameters or {}},
                )

        except Exception as e:
            self.logger.exception(
                "Failed to execute Cypher query",
                extra={"error": str(e), "query": query},
            )
            raise

    async def _create_node(
        self,
        labels: list[str],
        properties: dict[str, t.Any],
    ) -> GraphNodeModel:
        """Create a node in Neo4j."""
        # Add timestamps
        properties["created_at"] = datetime.now().isoformat()
        properties["updated_at"] = datetime.now().isoformat()

        # Generate ID if not provided
        if "id" not in properties:
            properties["id"] = str(uuid4())

        # Build Cypher query
        labels_str = ":".join(labels) if labels else ""
        query = f"CREATE (n:{labels_str} $properties) RETURN n"

        result = await self._execute_query(query, {"properties": properties})
        if result.nodes:
            return result.nodes[0]

        # Fallback - create model from properties
        return GraphNodeModel(
            id=properties["id"],
            labels=labels,
            properties=properties,
            created_at=datetime.fromisoformat(properties["created_at"]),
            updated_at=datetime.fromisoformat(properties["updated_at"]),
        )

    async def _get_node(self, node_id: str) -> GraphNodeModel | None:
        """Get a node by ID."""
        query = "MATCH (n {id: $node_id}) RETURN n"
        result = await self._execute_query(query, {"node_id": node_id})
        return result.nodes[0] if result.nodes else None

    async def _update_node(
        self,
        node_id: str,
        properties: dict[str, t.Any],
    ) -> GraphNodeModel:
        """Update node properties."""
        properties["updated_at"] = datetime.now().isoformat()

        query = "MATCH (n {id: $node_id}) SET n += $properties RETURN n"
        result = await self._execute_query(
            query,
            {"node_id": node_id, "properties": properties},
        )

        if result.nodes:
            return result.nodes[0]

        msg = f"Node with ID {node_id} not found"
        raise ValueError(msg)

    async def _delete_node(self, node_id: str) -> bool:
        """Delete a node."""
        query = "MATCH (n {id: $node_id}) DETACH DELETE n"
        await self._execute_query(query, {"node_id": node_id})
        return True

    async def _create_edge(
        self,
        edge_type: str,
        from_node_id: str,
        to_node_id: str,
        properties: dict[str, t.Any],
    ) -> GraphEdgeModel:
        """Create an edge between nodes."""
        # Add timestamps and ID
        properties["created_at"] = datetime.now().isoformat()
        properties["updated_at"] = datetime.now().isoformat()
        if "id" not in properties:
            properties["id"] = str(uuid4())

        query = (
            """
        MATCH (from {id: $from_id}), (to {id: $to_id})
        CREATE (from)-[r:"""
            + edge_type
            + """ $properties]->(to)
        RETURN r
        """
        )

        result = await self._execute_query(
            query,
            {
                "from_id": from_node_id,
                "to_id": to_node_id,
                "properties": properties,
            },
        )

        if result.edges:
            return result.edges[0]

        # Fallback - create model from properties
        return GraphEdgeModel(
            id=properties["id"],
            type=edge_type,
            from_node=from_node_id,
            to_node=to_node_id,
            properties=properties,
            created_at=datetime.fromisoformat(properties["created_at"]),
            updated_at=datetime.fromisoformat(properties["updated_at"]),
        )

    async def _get_edge(self, edge_id: str) -> GraphEdgeModel | None:
        """Get an edge by ID."""
        query = "MATCH ()-[r {id: $edge_id}]-() RETURN r"
        result = await self._execute_query(query, {"edge_id": edge_id})
        return result.edges[0] if result.edges else None

    async def _update_edge(
        self,
        edge_id: str,
        properties: dict[str, t.Any],
    ) -> GraphEdgeModel:
        """Update edge properties."""
        properties["updated_at"] = datetime.now().isoformat()

        query = "MATCH ()-[r {id: $edge_id}]-() SET r += $properties RETURN r"
        result = await self._execute_query(
            query,
            {"edge_id": edge_id, "properties": properties},
        )

        if result.edges:
            return result.edges[0]

        msg = f"Edge with ID {edge_id} not found"
        raise ValueError(msg)

    async def _delete_edge(self, edge_id: str) -> bool:
        """Delete an edge."""
        query = "MATCH ()-[r {id: $edge_id}]-() DELETE r"
        await self._execute_query(query, {"edge_id": edge_id})
        return True

    async def _find_path(
        self,
        from_node_id: str,
        to_node_id: str,
        max_depth: int | None,
        direction: GraphTraversalDirection,
    ) -> list[GraphPathModel]:
        """Find paths between nodes."""
        direction_str = ""
        if direction == GraphTraversalDirection.OUT:
            direction_str = "->"
        elif direction == GraphTraversalDirection.IN:
            direction_str = "<-"
        else:
            direction_str = "-"

        depth_clause = f"*1..{max_depth}" if max_depth else "*"

        query = f"""
        MATCH p = (from {{id: $from_id}}){direction_str}[{depth_clause}]{direction_str}(to {{id: $to_id}})
        RETURN p
        """

        result = await self._execute_query(
            query,
            {"from_id": from_node_id, "to_id": to_node_id},
        )
        return result.paths

    async def _find_shortest_path(
        self,
        from_node_id: str,
        to_node_id: str,
        weight_property: str | None,
    ) -> GraphPathModel | None:
        """Find shortest path between nodes."""
        if weight_property:
            query = """
            MATCH (from {id: $from_id}), (to {id: $to_id})
            CALL gds.shortestPath.dijkstra.stream({
                sourceNode: from,
                targetNode: to,
                relationshipWeightProperty: $weight_property
            })
            YIELD path
            RETURN path
            """
            params = {
                "from_id": from_node_id,
                "to_id": to_node_id,
                "weight_property": weight_property,
            }
        else:
            query = """
            MATCH p = shortestPath((from {id: $from_id})-[*]-(to {id: $to_id}))
            RETURN p as path
            """
            params = {"from_id": from_node_id, "to_id": to_node_id}

        result = await self._execute_query(query, params)
        return result.paths[0] if result.paths else None

    async def _get_neighbors(
        self,
        node_id: str,
        direction: GraphTraversalDirection,
        edge_types: list[str] | None,
    ) -> list[GraphNodeModel]:
        """Get neighboring nodes."""
        edge_type_clause = ""
        if edge_types:
            edge_type_clause = ":" + "|".join(edge_types)

        if direction == GraphTraversalDirection.OUT:
            query = f"MATCH (n {{id: $node_id}})-[{edge_type_clause}]->(neighbor) RETURN neighbor"
        elif direction == GraphTraversalDirection.IN:
            query = f"MATCH (n {{id: $node_id}})<-[{edge_type_clause}]-(neighbor) RETURN neighbor"
        else:
            query = f"MATCH (n {{id: $node_id}})-[{edge_type_clause}]-(neighbor) RETURN neighbor"

        result = await self._execute_query(query, {"node_id": node_id})
        return result.nodes

    async def _get_schema(self) -> GraphSchemaModel:
        """Get Neo4j schema information."""
        # Get node labels
        node_query = "CALL db.labels() YIELD label RETURN collect(label) as labels"
        node_result = await self._execute_query(node_query)
        node_types: Any = (
            node_result.records[0]["labels"] if node_result.records else []
        )

        # Get relationship types
        edge_query = "CALL db.relationshipTypes() YIELD relationshipType RETURN collect(relationshipType) as types"
        edge_result: Any = await self._execute_query(edge_query)
        edge_types: Any = edge_result.records[0]["types"] if edge_result.records else []

        # Get constraints
        constraints_query = (
            "SHOW CONSTRAINTS YIELD name, labelsOrTypes, properties, type"
        )
        constraints_result = await self._execute_query(constraints_query)
        constraints = constraints_result.records

        # Get indexes
        indexes_query = "SHOW INDEXES YIELD name, labelsOrTypes, properties, type"
        indexes_result = await self._execute_query(indexes_query)
        indexes = indexes_result.records

        return GraphSchemaModel(
            node_types=node_types,
            edge_types=edge_types,
            constraints=constraints,
            indexes=indexes,
        )

    async def _create_index(
        self,
        labels: list[str],
        properties: list[str],
        index_type: str,
    ) -> bool:
        """Create an index on properties."""
        for label in labels:
            for prop in properties:
                query = f"CREATE INDEX FOR (n:{label}) ON (n.{prop})"
                await self._execute_query(query)
        return True

    async def _drop_index(self, index_name: str) -> bool:
        """Drop an index."""
        query = f"DROP INDEX {index_name}"
        await self._execute_query(query)
        return True

    async def _bulk_create_nodes(
        self,
        nodes: list[dict[str, t.Any]],
    ) -> list[GraphNodeModel]:
        """Create multiple nodes in bulk."""
        results = []
        for node_data in nodes:
            labels = node_data.get("labels", [])
            properties = node_data.get("properties", {})
            result = await self._create_node(labels, properties)
            results.append(result)
        return results

    async def _bulk_create_edges(
        self,
        edges: list[dict[str, t.Any]],
    ) -> list[GraphEdgeModel]:
        """Create multiple edges in bulk."""
        results = []
        for edge_data in edges:
            result = await self._create_edge(
                edge_data["type"],
                edge_data["from_node"],
                edge_data["to_node"],
                edge_data.get("properties", {}),
            )
            results.append(result)
        return results

    async def _count_nodes(self, labels: list[str] | None) -> int:
        """Count nodes in the graph."""
        if labels:
            label_clause = ":".join(labels)
            query = f"MATCH (n:{label_clause}) RETURN count(n) as count"
        else:
            query = "MATCH (n) RETURN count(n) as count"

        result = await self._execute_query(query)
        return result.records[0]["count"] if result.records else 0

    async def _count_edges(self, edge_types: list[str] | None) -> int:
        """Count edges in the graph."""
        if edge_types:
            type_clause = "|".join(edge_types)
            query = f"MATCH ()-[r:{type_clause}]-() RETURN count(r) as count"
        else:
            query = "MATCH ()-[r]-() RETURN count(r) as count"

        result = await self._execute_query(query)
        return result.records[0]["count"] if result.records else 0

    async def _clear_graph(self) -> bool:
        """Clear all nodes and edges."""
        query = "MATCH (n) DETACH DELETE n"
        await self._execute_query(query)
        return True

    def _neo4j_node_to_model(self, node: t.Any) -> GraphNodeModel:
        """Convert Neo4j node to GraphNodeModel."""
        properties = dict(node)
        return GraphNodeModel(
            id=properties.get("id", str(node.element_id)),
            labels=list(node.labels),
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

    def _neo4j_relationship_to_model(self, rel: t.Any) -> GraphEdgeModel:
        """Convert Neo4j relationship to GraphEdgeModel."""
        properties = dict(rel)
        return GraphEdgeModel(
            id=properties.get("id", str(rel.element_id)),
            type=rel.type,
            from_node=str(rel.start_node.element_id),
            to_node=str(rel.end_node.element_id),
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

    def _neo4j_path_to_model(self, path: t.Any) -> GraphPathModel:
        """Convert Neo4j path to GraphPathModel."""
        nodes = [self._neo4j_node_to_model(node) for node in path.nodes]
        edges = [self._neo4j_relationship_to_model(rel) for rel in path.relationships]

        return GraphPathModel(
            nodes=nodes,
            edges=edges,
            length=len(path.relationships),
        )


depends.set(Graph, "neo4j")
