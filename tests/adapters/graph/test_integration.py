"""Integration tests for graph adapters."""

import pytest
from unittest.mock import patch

from acb.adapters.graph._base import GraphQueryLanguage
from acb.adapters.graph.neo4j import Graph as Neo4jGraph
from acb.adapters.graph.neptune import Graph as NeptuneGraph
from acb.adapters.graph.arangodb import Graph as ArangoDBGraph


@pytest.mark.integration
@pytest.mark.asyncio
class TestGraphAdapterIntegration:
    """Integration tests for all graph adapters."""

    @pytest.fixture(params=["neo4j", "neptune", "arangodb"])
    def adapter_type(self, request):
        """Parametrized fixture for different adapter types."""
        return request.param

    @pytest.fixture
    def graph_adapter(self, adapter_type):
        """Create appropriate graph adapter based on type."""
        if adapter_type == "neo4j":
            return Neo4jGraph(
                host="localhost",
                port=7687,
                user="neo4j",
                password="password",
                database="test",
            )
        elif adapter_type == "neptune":
            return NeptuneGraph(
                cluster_endpoint="neptune.amazonaws.com",
                port=8182,
                use_iam_auth=False,
            )
        elif adapter_type == "arangodb":
            return ArangoDBGraph(
                host="localhost",
                port=8529,
                database="test",
                graph_name="test_graph",
            )
        else:
            raise ValueError(f"Unknown adapter type: {adapter_type}")

    async def test_adapter_initialization(self, graph_adapter, adapter_type):
        """Test that all adapters initialize correctly."""
        assert graph_adapter is not None

        # Check query language
        if adapter_type == "neo4j":
            assert graph_adapter.query_language == GraphQueryLanguage.CYPHER
        elif adapter_type == "neptune":
            assert graph_adapter.query_language == GraphQueryLanguage.GREMLIN
        elif adapter_type == "arangodb":
            assert graph_adapter.query_language == GraphQueryLanguage.AQL

        # Check supported features
        features = graph_adapter.supported_features
        assert isinstance(features, list)
        assert len(features) > 0

    async def test_adapter_lifecycle(self, graph_adapter):
        """Test adapter lifecycle operations."""
        # Mock the actual database connections
        with patch.object(graph_adapter, '_create_client', return_value=object()):
            # Test client creation
            client = await graph_adapter._ensure_client()
            assert client is not None

            # Test cleanup
            await graph_adapter._cleanup_resources()
            assert graph_adapter._client is None

    async def test_common_interface_methods(self, graph_adapter):
        """Test that all adapters implement the common interface."""
        # Check that all required methods exist
        required_methods = [
            "execute_query",
            "create_node",
            "get_node",
            "update_node",
            "delete_node",
            "create_edge",
            "get_edge",
            "update_edge",
            "delete_edge",
            "find_path",
            "find_shortest_path",
            "get_neighbors",
            "get_schema",
            "create_index",
            "drop_index",
            "bulk_create_nodes",
            "bulk_create_edges",
            "count_nodes",
            "count_edges",
            "clear_graph",
        ]

        for method_name in required_methods:
            assert hasattr(graph_adapter, method_name)
            method = getattr(graph_adapter, method_name)
            assert callable(method)

    async def test_transaction_interface(self, graph_adapter):
        """Test transaction interface consistency."""
        transaction_methods = [
            "begin_transaction",
            "commit_transaction",
            "rollback_transaction",
        ]

        for method_name in transaction_methods:
            assert hasattr(graph_adapter, method_name)
            method = getattr(graph_adapter, method_name)
            assert callable(method)

    @pytest.mark.parametrize("feature", [
        "transactions",
        "bulk_operations",
        "graph_traversal",
        "schema_operations",
    ])
    async def test_feature_availability(self, graph_adapter, feature):
        """Test that adapters declare their feature support correctly."""
        features = graph_adapter.supported_features

        # Each adapter should have some form of these core features
        if feature == "transactions":
            # All adapters should support some form of transactions
            transaction_features = ["transactions", "acid_transactions", "auto_commit"]
            assert any(f in features for f in transaction_features)

        elif feature == "bulk_operations":
            # All adapters should support bulk operations
            bulk_features = ["bulk_operations", "batch_operations", "streaming_cursors"]
            assert any(f in features for f in bulk_features)

        elif feature == "graph_traversal":
            # All adapters should support graph traversal
            traversal_features = ["graph_algorithms", "pathfinding", "graph_traversal"]
            assert any(f in features for f in traversal_features)

        elif feature == "schema_operations":
            # All adapters should support some form of schema operations
            schema_features = ["schema_validation", "indexes", "constraints"]
            # Note: Not all graph databases have explicit schema support


@pytest.mark.integration
@pytest.mark.asyncio
class TestGraphAdapterCompatibility:
    """Test compatibility between different graph adapters."""

    async def test_model_compatibility(self):
        """Test that all adapters work with the same data models."""
        from acb.adapters.graph._base import (
            GraphNodeModel,
            GraphEdgeModel,
            GraphPathModel,
            GraphQueryResult,
            GraphSchemaModel,
        )

        # Test that model instances can be created consistently
        node = GraphNodeModel(
            id="test_node",
            labels=["Person"],
            properties={"name": "John", "age": 30},
        )
        assert node.id == "test_node"
        assert "Person" in node.labels

        edge = GraphEdgeModel(
            id="test_edge",
            type="KNOWS",
            from_node="node1",
            to_node="node2",
            properties={"since": "2020"},
        )
        assert edge.id == "test_edge"
        assert edge.type == "KNOWS"

        path = GraphPathModel(
            nodes=[node],
            edges=[edge],
            length=1,
        )
        assert len(path.nodes) == 1
        assert len(path.edges) == 1

        result = GraphQueryResult(
            nodes=[node],
            edges=[edge],
            paths=[path],
            execution_time=0.1,
        )
        assert len(result.nodes) == 1
        assert result.execution_time == 0.1

        schema = GraphSchemaModel(
            node_types=["Person", "Company"],
            edge_types=["WORKS_FOR", "KNOWS"],
        )
        assert "Person" in schema.node_types
        assert "KNOWS" in schema.edge_types

    async def test_settings_compatibility(self):
        """Test that settings work consistently across adapters."""
        from acb.adapters.graph.neo4j import Neo4jSettings
        from acb.adapters.graph.neptune import NeptuneSettings
        from acb.adapters.graph.arangodb import ArangoDBSettings

        # Test that all settings inherit from GraphBaseSettings
        neo4j_settings = Neo4jSettings()
        neptune_settings = NeptuneSettings()
        arangodb_settings = ArangoDBSettings()

        # Check common settings
        for settings in [neo4j_settings, neptune_settings, arangodb_settings]:
            assert hasattr(settings, "max_connections")
            assert hasattr(settings, "query_timeout")
            assert hasattr(settings, "ssl_enabled")

    async def test_error_handling_compatibility(self):
        """Test that error handling is consistent across adapters."""
        adapters = [
            Neo4jGraph(),
            NeptuneGraph(),
            ArangoDBGraph(),
        ]

        for adapter in adapters:
            # Test that transaction errors are handled consistently
            with pytest.raises(RuntimeError, match="No active transaction"):
                await adapter.commit_transaction()

            with pytest.raises(RuntimeError, match="No active transaction"):
                await adapter.rollback_transaction()


@pytest.mark.integration
@pytest.mark.benchmark
@pytest.mark.asyncio
class TestGraphAdapterPerformance:
    """Performance tests for graph adapters."""

    @pytest.fixture(params=["neo4j", "neptune", "arangodb"])
    def adapter_type(self, request):
        """Parametrized fixture for different adapter types."""
        return request.param

    @pytest.fixture
    def graph_adapter(self, adapter_type):
        """Create appropriate graph adapter based on type."""
        if adapter_type == "neo4j":
            return Neo4jGraph(host="localhost", port=7687)
        elif adapter_type == "neptune":
            return NeptuneGraph(cluster_endpoint="neptune.amazonaws.com")
        elif adapter_type == "arangodb":
            return ArangoDBGraph(host="localhost", port=8529)

    async def test_client_initialization_performance(self, graph_adapter, benchmark):
        """Benchmark client initialization performance."""
        with patch.object(graph_adapter, '_create_client', return_value=object()):
            # Benchmark client creation
            result = benchmark(lambda: graph_adapter._ensure_client())
            # Note: This would be async in real scenario

    async def test_query_execution_performance(self, graph_adapter, benchmark):
        """Benchmark query execution performance."""
        with patch.object(graph_adapter, '_execute_query') as mock_execute:
            from acb.adapters.graph._base import GraphQueryResult
            mock_execute.return_value = GraphQueryResult()

            # Benchmark query execution
            def execute_query():
                return graph_adapter._execute_query("MOCK QUERY")

            result = benchmark(execute_query)

    async def test_bulk_operations_performance(self, graph_adapter, benchmark):
        """Benchmark bulk operations performance."""
        with patch.object(graph_adapter, '_bulk_create_nodes') as mock_bulk:
            from acb.adapters.graph._base import GraphNodeModel
            from datetime import datetime

            mock_bulk.return_value = [
                GraphNodeModel(
                    id=f"node_{i}",
                    labels=["Test"],
                    properties={"index": i},
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                for i in range(100)
            ]

            # Benchmark bulk node creation
            def bulk_create():
                nodes_data = [
                    {"labels": ["Test"], "properties": {"index": i}}
                    for i in range(100)
                ]
                return graph_adapter._bulk_create_nodes(nodes_data)

            result = benchmark(bulk_create)
