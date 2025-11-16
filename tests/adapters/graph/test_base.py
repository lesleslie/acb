"""Tests for graph adapter base classes."""

from unittest.mock import MagicMock

import pytest
from datetime import datetime

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


class MockGraphAdapter(GraphBase):
    """Mock graph adapter for testing."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._mock_client = MagicMock()

    @property
    def query_language(self) -> GraphQueryLanguage:
        return GraphQueryLanguage.CYPHER

    @property
    def supported_features(self) -> list[str]:
        return ["mock_feature"]

    async def _create_client(self):
        return self._mock_client

    async def _begin_transaction(self, client):
        return MagicMock()

    async def _commit_transaction(self, transaction):
        pass

    async def _rollback_transaction(self):
        pass

    async def _execute_query(self, query, parameters=None, timeout=None):
        return GraphQueryResult(
            query_language=GraphQueryLanguage.CYPHER,
            execution_time=0.1,
        )

    async def _create_node(self, labels, properties):
        return GraphNodeModel(
            id="test_node",
            labels=labels,
            properties=properties,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    async def _get_node(self, node_id):
        if node_id == "test_node":
            return GraphNodeModel(
                id=node_id,
                labels=["TestLabel"],
                properties={"name": "test"},
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
        return None

    async def _update_node(self, node_id, properties):
        return GraphNodeModel(
            id=node_id,
            labels=["TestLabel"],
            properties=properties,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    async def _delete_node(self, node_id):
        return True

    async def _create_edge(self, edge_type, from_node_id, to_node_id, properties):
        return GraphEdgeModel(
            id="test_edge",
            type=edge_type,
            from_node=from_node_id,
            to_node=to_node_id,
            properties=properties,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    async def _get_edge(self, edge_id):
        if edge_id == "test_edge":
            return GraphEdgeModel(
                id=edge_id,
                type="TestEdge",
                from_node="node1",
                to_node="node2",
                properties={"weight": 1.0},
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
        return None

    async def _update_edge(self, edge_id, properties):
        return GraphEdgeModel(
            id=edge_id,
            type="TestEdge",
            from_node="node1",
            to_node="node2",
            properties=properties,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    async def _delete_edge(self, edge_id):
        return True

    async def _find_path(self, from_node_id, to_node_id, max_depth, direction):
        return [
            GraphPathModel(
                nodes=[
                    GraphNodeModel(id=from_node_id, labels=[], properties={}),
                    GraphNodeModel(id=to_node_id, labels=[], properties={}),
                ],
                edges=[
                    GraphEdgeModel(
                        id="path_edge",
                        type="PathEdge",
                        from_node=from_node_id,
                        to_node=to_node_id,
                        properties={},
                    )
                ],
                length=1,
            )
        ]

    async def _find_shortest_path(self, from_node_id, to_node_id, weight_property):
        return GraphPathModel(
            nodes=[
                GraphNodeModel(id=from_node_id, labels=[], properties={}),
                GraphNodeModel(id=to_node_id, labels=[], properties={}),
            ],
            edges=[
                GraphEdgeModel(
                    id="shortest_edge",
                    type="ShortestEdge",
                    from_node=from_node_id,
                    to_node=to_node_id,
                    properties={},
                )
            ],
            length=1,
        )

    async def _get_neighbors(self, node_id, direction, edge_types):
        return [
            GraphNodeModel(
                id="neighbor1",
                labels=["Neighbor"],
                properties={"name": "neighbor"},
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
        ]

    async def _get_schema(self):
        return GraphSchemaModel(
            node_types=["TestNode"],
            edge_types=["TestEdge"],
            constraints=[],
            indexes=[],
        )

    async def _create_index(self, labels, properties, index_type):
        return True

    async def _drop_index(self, index_name):
        return True

    async def _bulk_create_nodes(self, nodes):
        return [
            GraphNodeModel(
                id=f"bulk_node_{i}",
                labels=node.get("labels", []),
                properties=node.get("properties", {}),
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            for i, node in enumerate(nodes)
        ]

    async def _bulk_create_edges(self, edges):
        return [
            GraphEdgeModel(
                id=f"bulk_edge_{i}",
                type=edge["type"],
                from_node=edge["from_node"],
                to_node=edge["to_node"],
                properties=edge.get("properties", {}),
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            for i, edge in enumerate(edges)
        ]

    async def _count_nodes(self, labels):
        return 10

    async def _count_edges(self, edge_types):
        return 5

    async def _clear_graph(self):
        return True


@pytest.mark.asyncio
class TestGraphBase:
    """Test GraphBase functionality."""

    @pytest.fixture
    def graph_adapter(self):
        """Create a mock graph adapter."""
        return MockGraphAdapter()

    async def test_query_language_property(self, graph_adapter):
        """Test query language property."""
        assert graph_adapter.query_language == GraphQueryLanguage.CYPHER

    async def test_supported_features_property(self, graph_adapter):
        """Test supported features property."""
        features = graph_adapter.supported_features
        assert isinstance(features, list)
        assert "mock_feature" in features

    async def test_ensure_client(self, graph_adapter):
        """Test client initialization."""
        client = await graph_adapter._ensure_client()
        assert client is not None

        # Second call should return same client
        client2 = await graph_adapter._ensure_client()
        assert client is client2

    async def test_transaction_lifecycle(self, graph_adapter):
        """Test transaction begin, commit, rollback."""
        # Begin transaction
        await graph_adapter.begin_transaction()
        assert graph_adapter._transaction is not None

        # Commit transaction
        await graph_adapter.commit_transaction()
        assert graph_adapter._transaction is None

        # Begin new transaction for rollback test
        await graph_adapter.begin_transaction()
        await graph_adapter.rollback_transaction()
        assert graph_adapter._transaction is None

    async def test_execute_query(self, graph_adapter):
        """Test query execution."""
        result = await graph_adapter.execute_query("MATCH (n) RETURN n")
        assert isinstance(result, GraphQueryResult)
        assert result.query_language == GraphQueryLanguage.CYPHER
        assert result.execution_time is not None

    async def test_execute_batch_queries(self, graph_adapter):
        """Test batch query execution."""
        queries = [
            ("MATCH (n) RETURN n", None),
            ("CREATE (n:Test) RETURN n", {"name": "test"}),
        ]
        results = await graph_adapter.execute_batch_queries(queries)
        assert len(results) == 2
        assert all(isinstance(r, GraphQueryResult) for r in results)

    async def test_node_operations(self, graph_adapter):
        """Test node CRUD operations."""
        # Create node
        node = await graph_adapter.create_node(["TestLabel"], {"name": "test"})
        assert isinstance(node, GraphNodeModel)
        assert node.id == "test_node"
        assert "TestLabel" in node.labels

        # Get node
        retrieved_node = await graph_adapter.get_node("test_node")
        assert retrieved_node is not None
        assert retrieved_node.id == "test_node"

        # Update node
        updated_node = await graph_adapter.update_node("test_node", {"name": "updated"})
        assert isinstance(updated_node, GraphNodeModel)
        assert updated_node.properties.get("name") == "updated"

        # Delete node
        deleted = await graph_adapter.delete_node("test_node")
        assert deleted is True

        # Get non-existent node
        missing_node = await graph_adapter.get_node("non_existent")
        assert missing_node is None

    async def test_edge_operations(self, graph_adapter):
        """Test edge CRUD operations."""
        # Create edge
        edge = await graph_adapter.create_edge(
            "TestEdge", "node1", "node2", {"weight": 1.0}
        )
        assert isinstance(edge, GraphEdgeModel)
        assert edge.id == "test_edge"
        assert edge.type == "TestEdge"

        # Get edge
        retrieved_edge = await graph_adapter.get_edge("test_edge")
        assert retrieved_edge is not None
        assert retrieved_edge.id == "test_edge"

        # Update edge
        updated_edge = await graph_adapter.update_edge("test_edge", {"weight": 2.0})
        assert isinstance(updated_edge, GraphEdgeModel)
        assert updated_edge.properties.get("weight") == 2.0

        # Delete edge
        deleted = await graph_adapter.delete_edge("test_edge")
        assert deleted is True

        # Get non-existent edge
        missing_edge = await graph_adapter.get_edge("non_existent")
        assert missing_edge is None

    async def test_path_operations(self, graph_adapter):
        """Test path finding operations."""
        # Find paths
        paths = await graph_adapter.find_path("node1", "node2")
        assert isinstance(paths, list)
        assert len(paths) > 0
        assert all(isinstance(p, GraphPathModel) for p in paths)

        # Find shortest path
        shortest_path = await graph_adapter.find_shortest_path("node1", "node2")
        assert isinstance(shortest_path, GraphPathModel)
        assert shortest_path.length == 1

        # Find path with direction
        out_paths = await graph_adapter.find_path(
            "node1", "node2", direction=GraphTraversalDirection.OUT
        )
        assert isinstance(out_paths, list)

    async def test_neighbor_operations(self, graph_adapter):
        """Test neighbor retrieval."""
        neighbors = await graph_adapter.get_neighbors("node1")
        assert isinstance(neighbors, list)
        assert len(neighbors) > 0
        assert all(isinstance(n, GraphNodeModel) for n in neighbors)

        # Test with direction
        out_neighbors = await graph_adapter.get_neighbors(
            "node1", direction=GraphTraversalDirection.OUT
        )
        assert isinstance(out_neighbors, list)

        # Test with edge types
        typed_neighbors = await graph_adapter.get_neighbors(
            "node1", edge_types=["TestEdge"]
        )
        assert isinstance(typed_neighbors, list)

    async def test_schema_operations(self, graph_adapter):
        """Test schema operations."""
        # Get schema
        schema = await graph_adapter.get_schema()
        assert isinstance(schema, GraphSchemaModel)
        assert "TestNode" in schema.node_types
        assert "TestEdge" in schema.edge_types

        # Create index
        created = await graph_adapter.create_index(["TestNode"], ["name"])
        assert created is True

        # Drop index
        dropped = await graph_adapter.drop_index("test_index")
        assert dropped is True

    async def test_bulk_operations(self, graph_adapter):
        """Test bulk operations."""
        # Bulk create nodes
        node_data = [
            {"labels": ["Bulk"], "properties": {"name": "bulk1"}},
            {"labels": ["Bulk"], "properties": {"name": "bulk2"}},
        ]
        nodes = await graph_adapter.bulk_create_nodes(node_data)
        assert len(nodes) == 2
        assert all(isinstance(n, GraphNodeModel) for n in nodes)

        # Bulk create edges
        edge_data = [
            {
                "type": "BulkEdge",
                "from_node": "node1",
                "to_node": "node2",
                "properties": {},
            },
            {
                "type": "BulkEdge",
                "from_node": "node2",
                "to_node": "node3",
                "properties": {},
            },
        ]
        edges = await graph_adapter.bulk_create_edges(edge_data)
        assert len(edges) == 2
        assert all(isinstance(e, GraphEdgeModel) for e in edges)

    async def test_utility_operations(self, graph_adapter):
        """Test utility operations."""
        # Count nodes
        node_count = await graph_adapter.count_nodes()
        assert isinstance(node_count, int)
        assert node_count == 10

        # Count edges
        edge_count = await graph_adapter.count_edges()
        assert isinstance(edge_count, int)
        assert edge_count == 5

        # Clear graph
        cleared = await graph_adapter.clear_graph()
        assert cleared is True

    async def test_cleanup_resources(self, graph_adapter):
        """Test resource cleanup."""
        # Ensure client is created
        await graph_adapter._ensure_client()

        # Begin transaction
        await graph_adapter.begin_transaction()

        # Cleanup should handle transaction and client
        await graph_adapter._cleanup_resources()
        assert graph_adapter._transaction is None
        assert graph_adapter._client is None


class TestGraphModels:
    """Test graph model classes."""

    def test_graph_node_model(self):
        """Test GraphNodeModel."""
        now = datetime.now()
        node = GraphNodeModel(
            id="test_id",
            labels=["Person", "User"],
            properties={"name": "John", "age": 30},
            created_at=now,
            updated_at=now,
        )

        assert node.id == "test_id"
        assert node.labels == ["Person", "User"]
        assert node.properties["name"] == "John"
        assert node.created_at == now

    def test_graph_edge_model(self):
        """Test GraphEdgeModel."""
        now = datetime.now()
        edge = GraphEdgeModel(
            id="edge_id",
            type="KNOWS",
            from_node="node1",
            to_node="node2",
            properties={"since": "2020"},
            created_at=now,
            updated_at=now,
        )

        assert edge.id == "edge_id"
        assert edge.type == "KNOWS"
        assert edge.from_node == "node1"
        assert edge.to_node == "node2"

    def test_graph_path_model(self):
        """Test GraphPathModel."""
        nodes = [
            GraphNodeModel(id="node1", labels=[], properties={}),
            GraphNodeModel(id="node2", labels=[], properties={}),
        ]
        edges = [
            GraphEdgeModel(
                id="edge1",
                type="CONNECTS",
                from_node="node1",
                to_node="node2",
                properties={},
            )
        ]

        path = GraphPathModel(
            nodes=nodes,
            edges=edges,
            length=1,
            weight=5.0,
        )

        assert len(path.nodes) == 2
        assert len(path.edges) == 1
        assert path.length == 1
        assert path.weight == 5.0

    def test_graph_query_result(self):
        """Test GraphQueryResult."""
        result = GraphQueryResult(
            nodes=[],
            edges=[],
            paths=[],
            records=[{"count": 5}],
            execution_time=0.1,
            query_language=GraphQueryLanguage.CYPHER,
            metadata={"query": "MATCH (n) RETURN count(n)"},
        )

        assert result.query_language == GraphQueryLanguage.CYPHER
        assert result.execution_time == 0.1
        assert len(result.records) == 1

    def test_graph_schema_model(self):
        """Test GraphSchemaModel."""
        schema = GraphSchemaModel(
            node_types=["Person", "Company"],
            edge_types=["WORKS_FOR", "KNOWS"],
            constraints=[{"type": "unique", "property": "email"}],
            indexes=[{"type": "btree", "properties": ["name"]}],
        )

        assert "Person" in schema.node_types
        assert "WORKS_FOR" in schema.edge_types
        assert len(schema.constraints) == 1
        assert len(schema.indexes) == 1


class TestGraphBaseSettings:
    """Test GraphBaseSettings."""

    def test_default_settings(self):
        """Test default settings values."""
        settings = GraphBaseSettings()

        assert settings.host.get_secret_value() == "127.0.0.1"
        assert settings.max_connections == 50
        assert settings.query_timeout == 300.0
        assert settings.ssl_enabled is False

    def test_custom_settings(self):
        """Test custom settings values."""
        settings = GraphBaseSettings(
            host="192.168.1.100",
            port=9999,
            max_connections=100,
            query_timeout=600.0,
            ssl_enabled=True,
        )

        assert settings.host.get_secret_value() == "192.168.1.100"
        assert settings.port == 9999
        assert settings.max_connections == 100
        assert settings.query_timeout == 600.0
        assert settings.ssl_enabled is True


class TestGraphEnums:
    """Test graph enumeration classes."""

    def test_graph_query_language(self):
        """Test GraphQueryLanguage enum."""
        assert GraphQueryLanguage.CYPHER == "cypher"
        assert GraphQueryLanguage.GREMLIN == "gremlin"
        assert GraphQueryLanguage.AQL == "aql"
        assert GraphQueryLanguage.SPARQL == "sparql"

    def test_graph_traversal_direction(self):
        """Test GraphTraversalDirection enum."""
        assert GraphTraversalDirection.OUT == "out"
        assert GraphTraversalDirection.IN == "in"
        assert GraphTraversalDirection.BOTH == "both"
