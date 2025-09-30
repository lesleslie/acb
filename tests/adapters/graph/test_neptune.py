"""Tests for Neptune graph adapter."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from acb.adapters.graph.neptune import Graph, NeptuneSettings, MODULE_METADATA
from acb.adapters.graph._base import (
    GraphQueryLanguage,
    GraphNodeModel,
    GraphEdgeModel,
)


class MockDriverRemoteConnection:
    """Mock Gremlin driver remote connection."""

    def __init__(self, endpoint, **kwargs):
        self.endpoint = endpoint
        self.kwargs = kwargs
        self.closed = False

    async def close(self):
        """Mock connection close."""
        self.closed = True


class MockGraphTraversalSource:
    """Mock Gremlin graph traversal source."""

    def __init__(self):
        self.traversals = []

    def addV(self, label=None):
        """Mock add vertex traversal."""
        traversal = MockGremlinTraversal("addV", label)
        self.traversals.append(traversal)
        return traversal

    def V(self, *ids):
        """Mock vertex traversal."""
        traversal = MockGremlinTraversal("V", ids)
        self.traversals.append(traversal)
        return traversal

    def E(self, *ids):
        """Mock edge traversal."""
        traversal = MockGremlinTraversal("E", ids)
        self.traversals.append(traversal)
        return traversal

    def out(self, *edge_labels):
        """Mock outgoing edge traversal."""
        return MockGremlinTraversal("out", edge_labels)

    def in_(self, *edge_labels):
        """Mock incoming edge traversal."""
        return MockGremlinTraversal("in", edge_labels)

    def both(self, *edge_labels):
        """Mock bidirectional edge traversal."""
        return MockGremlinTraversal("both", edge_labels)


class MockGremlinTraversal:
    """Mock Gremlin traversal."""

    def __init__(self, step_type, args=None):
        self.step_type = step_type
        self.args = args or []
        self.steps = [(step_type, args)]

    def property(self, key, value=None):
        """Mock property step."""
        self.steps.append(("property", [key, value]))
        return self

    def has(self, key, value=None):
        """Mock has step."""
        self.steps.append(("has", [key, value]))
        return self

    def addE(self, label):
        """Mock add edge step."""
        self.steps.append(("addE", [label]))
        return self

    def to(self, traversal):
        """Mock to step."""
        self.steps.append(("to", [traversal]))
        return self

    def drop(self):
        """Mock drop step."""
        self.steps.append(("drop", []))
        return self

    def iterate(self):
        """Mock iterate step."""
        pass

    def next(self):
        """Mock next step."""
        if self.step_type == "addV":
            return MockGremlinVertex("v1", {"id": "test_vertex"})
        elif self.step_type == "addE":
            return MockGremlinEdge("e1", "TestEdge", "v1", "v2")
        elif self.step_type == "V":
            return MockGremlinVertex("v1", {"id": "test_vertex"})
        elif self.step_type == "E":
            return MockGremlinEdge("e1", "TestEdge", "v1", "v2")
        else:
            return None

    def toList(self):
        """Mock toList step."""
        if self.step_type == "V":
            return [MockGremlinVertex("v1"), MockGremlinVertex("v2")]
        elif self.step_type == "E":
            return [MockGremlinEdge("e1", "TestEdge", "v1", "v2")]
        else:
            return []

    def count(self):
        """Mock count step."""
        return MockGremlinTraversal("count")

    def label(self):
        """Mock label step."""
        return MockGremlinTraversal("label")

    def dedup(self):
        """Mock dedup step."""
        return MockGremlinTraversal("dedup")

    def valueMap(self, *args):
        """Mock valueMap step."""
        return MockGremlinTraversal("valueMap")

    def repeat(self, traversal):
        """Mock repeat step."""
        return MockGremlinTraversal("repeat")

    def until(self, condition):
        """Mock until step."""
        return MockGremlinTraversal("until")

    def times(self, count):
        """Mock times step."""
        return MockGremlinTraversal("times")

    def path(self):
        """Mock path step."""
        return MockGremlinTraversal("path")

    def shortestPath(self):
        """Mock shortestPath step."""
        return MockGremlinTraversal("shortestPath")

    def by(self, *args):
        """Mock by step."""
        return MockGremlinTraversal("by")

    def hasLabel(self, *labels):
        """Mock hasLabel step."""
        return MockGremlinTraversal("hasLabel")

    def outE(self, *labels):
        """Mock outE step."""
        return MockGremlinTraversal("outE")

    def inE(self, *labels):
        """Mock inE step."""
        return MockGremlinTraversal("inE")

    def bothE(self, *labels):
        """Mock bothE step."""
        return MockGremlinTraversal("bothE")

    def inV(self):
        """Mock inV step."""
        return MockGremlinTraversal("inV")

    def outV(self):
        """Mock outV step."""
        return MockGremlinTraversal("outV")

    def otherV(self):
        """Mock otherV step."""
        return MockGremlinTraversal("otherV")


class MockGremlinVertex:
    """Mock Gremlin vertex."""

    def __init__(self, id="v1", properties=None):
        self.id = id
        self.label = "Vertex"
        self.properties = properties or {}

    def __str__(self):
        return self.id


class MockGremlinEdge:
    """Mock Gremlin edge."""

    def __init__(self, id="e1", label="Edge", outV="v1", inV="v2", properties=None):
        self.id = id
        self.label = label
        self.outV_id = outV
        self.inV_id = inV
        self.properties = properties or {}

    def outV(self):
        """Mock outgoing vertex."""
        return MockGremlinTraversal("outV")

    def inV(self):
        """Mock incoming vertex."""
        return MockGremlinTraversal("inV")

    def __str__(self):
        return self.id


class MockGremlinPath:
    """Mock Gremlin path."""

    def __init__(self, elements=None):
        self.elements = elements or [MockGremlinVertex("v1"), MockGremlinEdge("e1", "Edge", "v1", "v2"), MockGremlinVertex("v2")]

    def __iter__(self):
        return iter(self.elements)

    def __len__(self):
        return len(self.elements)


@pytest.mark.asyncio
class TestNeptuneAdapter:
    """Test Neptune adapter functionality."""

    @pytest.fixture
    def neptune_settings(self):
        """Create Neptune settings for testing."""
        return NeptuneSettings(
            cluster_endpoint="neptune.us-east-1.amazonaws.com",
            port=8182,
            region="us-east-1",
            use_iam_auth=False,
        )

    @pytest.fixture
    def neptune_adapter(self, neptune_settings):
        """Create Neptune adapter for testing."""
        return Graph(**neptune_settings.model_dump())

    async def test_module_metadata(self):
        """Test module metadata."""
        assert MODULE_METADATA.name == "Amazon Neptune Graph Database"
        assert MODULE_METADATA.category == "graph"
        assert MODULE_METADATA.provider == "neptune"
        assert "boto3>=1.26.0" in MODULE_METADATA.required_packages
        assert "gremlinpython>=3.6.0" in MODULE_METADATA.required_packages

    async def test_query_language(self, neptune_adapter):
        """Test query language property."""
        assert neptune_adapter.query_language == GraphQueryLanguage.GREMLIN

    async def test_supported_features(self, neptune_adapter):
        """Test supported features."""
        features = neptune_adapter.supported_features
        assert "gremlin_queries" in features
        assert "property_graphs" in features
        assert "aws_integration" in features
        assert "iam_authentication" in features

    @patch('acb.adapters.graph.neptune.DriverRemoteConnection')
    @patch('acb.adapters.graph.neptune.traversal')
    async def test_create_client(self, mock_traversal, mock_connection, neptune_adapter):
        """Test Neptune client creation."""
        mock_conn = MockDriverRemoteConnection("ws://test:8182/gremlin")
        mock_connection.return_value = mock_conn

        mock_g = MockGraphTraversalSource()
        mock_traversal.return_value.withRemote.return_value = mock_g

        client = await neptune_adapter._create_client()

        assert client is mock_g
        mock_connection.assert_called_once()

    @patch('acb.adapters.graph.neptune.DriverRemoteConnection')
    @patch('acb.adapters.graph.neptune.traversal')
    async def test_execute_query(self, mock_traversal, mock_connection, neptune_adapter):
        """Test query execution."""
        mock_conn = MockDriverRemoteConnection("ws://test:8182/gremlin")
        mock_connection.return_value = mock_conn

        mock_g = MockGraphTraversalSource()
        mock_traversal.return_value.withRemote.return_value = mock_g

        with patch.object(neptune_adapter, '_execute_gremlin_traversal', return_value={"result": "success"}):
            result = await neptune_adapter._execute_query("g.V().count()")

        assert result.query_language == GraphQueryLanguage.GREMLIN
        assert result.execution_time is not None
        assert len(result.records) == 1

    @patch('acb.adapters.graph.neptune.DriverRemoteConnection')
    @patch('acb.adapters.graph.neptune.traversal')
    async def test_create_node(self, mock_traversal, mock_connection, neptune_adapter):
        """Test node creation."""
        mock_conn = MockDriverRemoteConnection("ws://test:8182/gremlin")
        mock_connection.return_value = mock_conn

        mock_g = MockGraphTraversalSource()
        mock_traversal.return_value.withRemote.return_value = mock_g

        node = await neptune_adapter._create_node(["Person"], {"name": "John"})

        assert isinstance(node, GraphNodeModel)
        assert "Person" in node.labels
        assert node.properties["name"] == "John"

    @patch('acb.adapters.graph.neptune.DriverRemoteConnection')
    @patch('acb.adapters.graph.neptune.traversal')
    async def test_get_node(self, mock_traversal, mock_connection, neptune_adapter):
        """Test node retrieval."""
        mock_conn = MockDriverRemoteConnection("ws://test:8182/gremlin")
        mock_connection.return_value = mock_conn

        mock_g = MockGraphTraversalSource()
        mock_traversal.return_value.withRemote.return_value = mock_g

        # Mock successful vertex retrieval
        with patch.object(mock_g, 'V') as mock_v:
            mock_traversal_chain = MagicMock()
            mock_traversal_chain.has.return_value.next.return_value = MockGremlinVertex("test_id", {"name": "John"})
            mock_traversal_chain.has.return_value.valueMap.return_value.next.return_value = {
                "id": ["test_id"],
                "name": ["John"],
                "label": ["Person"]
            }
            mock_v.return_value = mock_traversal_chain

            node = await neptune_adapter._get_node("test_id")

        assert node is not None
        assert isinstance(node, GraphNodeModel)

    @patch('acb.adapters.graph.neptune.DriverRemoteConnection')
    @patch('acb.adapters.graph.neptune.traversal')
    async def test_get_node_not_found(self, mock_traversal, mock_connection, neptune_adapter):
        """Test node retrieval when not found."""
        mock_conn = MockDriverRemoteConnection("ws://test:8182/gremlin")
        mock_connection.return_value = mock_conn

        mock_g = MockGraphTraversalSource()
        mock_traversal.return_value.withRemote.return_value = mock_g

        # Mock StopIteration (no results)
        with patch.object(mock_g, 'V') as mock_v:
            mock_traversal_chain = MagicMock()
            mock_traversal_chain.has.return_value.next.side_effect = StopIteration
            mock_v.return_value = mock_traversal_chain

            node = await neptune_adapter._get_node("non_existent")

        assert node is None

    @patch('acb.adapters.graph.neptune.DriverRemoteConnection')
    @patch('acb.adapters.graph.neptune.traversal')
    async def test_create_edge(self, mock_traversal, mock_connection, neptune_adapter):
        """Test edge creation."""
        mock_conn = MockDriverRemoteConnection("ws://test:8182/gremlin")
        mock_connection.return_value = mock_conn

        mock_g = MockGraphTraversalSource()
        mock_traversal.return_value.withRemote.return_value = mock_g

        edge = await neptune_adapter._create_edge("KNOWS", "node1", "node2", {"since": "2020"})

        assert isinstance(edge, GraphEdgeModel)
        assert edge.type == "KNOWS"
        assert edge.from_node == "node1"
        assert edge.to_node == "node2"
        assert edge.properties["since"] == "2020"

    @patch('acb.adapters.graph.neptune.DriverRemoteConnection')
    @patch('acb.adapters.graph.neptune.traversal')
    async def test_delete_node(self, mock_traversal, mock_connection, neptune_adapter):
        """Test node deletion."""
        mock_conn = MockDriverRemoteConnection("ws://test:8182/gremlin")
        mock_connection.return_value = mock_conn

        mock_g = MockGraphTraversalSource()
        mock_traversal.return_value.withRemote.return_value = mock_g

        # Mock successful deletion
        with patch.object(mock_g, 'V') as mock_v:
            mock_traversal_chain = MagicMock()
            mock_traversal_chain.has.return_value.drop.return_value.iterate.return_value = None
            mock_v.return_value = mock_traversal_chain

            result = await neptune_adapter._delete_node("test_id")

        assert result is True

    @patch('acb.adapters.graph.neptune.DriverRemoteConnection')
    @patch('acb.adapters.graph.neptune.traversal')
    async def test_delete_edge(self, mock_traversal, mock_connection, neptune_adapter):
        """Test edge deletion."""
        mock_conn = MockDriverRemoteConnection("ws://test:8182/gremlin")
        mock_connection.return_value = mock_conn

        mock_g = MockGraphTraversalSource()
        mock_traversal.return_value.withRemote.return_value = mock_g

        # Mock successful deletion
        with patch.object(mock_g, 'E') as mock_e:
            mock_traversal_chain = MagicMock()
            mock_traversal_chain.has.return_value.drop.return_value.iterate.return_value = None
            mock_e.return_value = mock_traversal_chain

            result = await neptune_adapter._delete_edge("edge_id")

        assert result is True

    @patch('acb.adapters.graph.neptune.DriverRemoteConnection')
    @patch('acb.adapters.graph.neptune.traversal')
    async def test_find_path(self, mock_traversal, mock_connection, neptune_adapter):
        """Test path finding."""
        mock_conn = MockDriverRemoteConnection("ws://test:8182/gremlin")
        mock_connection.return_value = mock_conn

        mock_g = MockGraphTraversalSource()
        mock_traversal.return_value.withRemote.return_value = mock_g

        # Mock path finding
        with patch.object(mock_g, 'V') as mock_v:
            mock_traversal_chain = MagicMock()
            mock_path = MockGremlinPath()
            mock_traversal_chain.has.return_value.repeat.return_value.until.return_value.path.return_value.toList.return_value = [mock_path]
            mock_v.return_value = mock_traversal_chain

            paths = await neptune_adapter._find_path("node1", "node2", max_depth=5, direction="both")

        assert isinstance(paths, list)

    @patch('acb.adapters.graph.neptune.DriverRemoteConnection')
    @patch('acb.adapters.graph.neptune.traversal')
    async def test_get_schema(self, mock_traversal, mock_connection, neptune_adapter):
        """Test schema retrieval."""
        mock_conn = MockDriverRemoteConnection("ws://test:8182/gremlin")
        mock_connection.return_value = mock_conn

        mock_g = MockGraphTraversalSource()
        mock_traversal.return_value.withRemote.return_value = mock_g

        # Mock schema queries
        with patch.object(mock_g, 'V') as mock_v, patch.object(mock_g, 'E') as mock_e:
            mock_v_chain = MagicMock()
            mock_v_chain.label.return_value.dedup.return_value.toList.return_value = ["Person", "Company"]
            mock_v.return_value = mock_v_chain

            mock_e_chain = MagicMock()
            mock_e_chain.label.return_value.dedup.return_value.toList.return_value = ["WORKS_FOR", "KNOWS"]
            mock_e.return_value = mock_e_chain

            schema = await neptune_adapter._get_schema()

        assert "Person" in schema.node_types
        assert "Company" in schema.node_types
        assert "WORKS_FOR" in schema.edge_types
        assert "KNOWS" in schema.edge_types

    @patch('acb.adapters.graph.neptune.DriverRemoteConnection')
    @patch('acb.adapters.graph.neptune.traversal')
    async def test_count_operations(self, mock_traversal, mock_connection, neptune_adapter):
        """Test count operations."""
        mock_conn = MockDriverRemoteConnection("ws://test:8182/gremlin")
        mock_connection.return_value = mock_conn

        mock_g = MockGraphTraversalSource()
        mock_traversal.return_value.withRemote.return_value = mock_g

        # Mock count queries
        with patch.object(mock_g, 'V') as mock_v, patch.object(mock_g, 'E') as mock_e:
            mock_v_chain = MagicMock()
            mock_v_chain.hasLabel.return_value.count.return_value.next.return_value = 10
            mock_v.return_value = mock_v_chain

            mock_e_chain = MagicMock()
            mock_e_chain.hasLabel.return_value.count.return_value.next.return_value = 5
            mock_e.return_value = mock_e_chain

            node_count = await neptune_adapter._count_nodes(["Person"])
            edge_count = await neptune_adapter._count_edges(["KNOWS"])

        assert node_count == 10
        assert edge_count == 5

    @patch('acb.adapters.graph.neptune.DriverRemoteConnection')
    @patch('acb.adapters.graph.neptune.traversal')
    async def test_clear_graph(self, mock_traversal, mock_connection, neptune_adapter):
        """Test graph clearing."""
        mock_conn = MockDriverRemoteConnection("ws://test:8182/gremlin")
        mock_connection.return_value = mock_conn

        mock_g = MockGraphTraversalSource()
        mock_traversal.return_value.withRemote.return_value = mock_g

        # Mock clear operation
        with patch.object(mock_g, 'V') as mock_v:
            mock_traversal_chain = MagicMock()
            mock_traversal_chain.drop.return_value.iterate.return_value = None
            mock_v.return_value = mock_traversal_chain

            result = await neptune_adapter._clear_graph()

        assert result is True

    async def test_transaction_operations(self, neptune_adapter):
        """Test transaction operations."""
        # Neptune auto-commits, so these are mostly no-ops
        await neptune_adapter.begin_transaction()
        assert neptune_adapter._transaction is not None

        await neptune_adapter.commit_transaction()
        # Transaction should still exist as Neptune doesn't have explicit transactions

        await neptune_adapter.rollback_transaction()

    @patch('acb.adapters.graph.neptune.DriverRemoteConnection')
    @patch('acb.adapters.graph.neptune.traversal')
    async def test_bulk_operations(self, mock_traversal, mock_connection, neptune_adapter):
        """Test bulk operations."""
        mock_conn = MockDriverRemoteConnection("ws://test:8182/gremlin")
        mock_connection.return_value = mock_conn

        mock_g = MockGraphTraversalSource()
        mock_traversal.return_value.withRemote.return_value = mock_g

        # Mock bulk node creation
        def mock_create_node(labels, properties):
            return GraphNodeModel(
                id=f"bulk_{properties.get('name', 'node')}",
                labels=labels,
                properties=properties,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

        with patch.object(neptune_adapter, '_create_node', side_effect=mock_create_node):
            nodes_data = [
                {"labels": ["Person"], "properties": {"name": "John"}},
                {"labels": ["Person"], "properties": {"name": "Jane"}},
            ]
            nodes = await neptune_adapter._bulk_create_nodes(nodes_data)

        assert len(nodes) == 2
        assert all(isinstance(n, GraphNodeModel) for n in nodes)

    async def test_execute_gremlin_traversal(self, neptune_adapter):
        """Test Gremlin traversal execution."""
        mock_g = MockGraphTraversalSource()

        # Test placeholder implementation
        result = await neptune_adapter._execute_gremlin_traversal(mock_g, "g.V().count()", {})

        assert result["message"] == "Gremlin query executed"
        assert result["query"] == "g.V().count()"


class TestNeptuneSettings:
    """Test Neptune settings."""

    def test_default_settings(self):
        """Test default Neptune settings."""
        settings = NeptuneSettings()

        assert settings.cluster_endpoint == ""
        assert settings.port == 8182
        assert settings.region == "us-east-1"
        assert settings.use_iam_auth is True
        assert settings.enable_ssl is True

    def test_custom_settings(self):
        """Test custom Neptune settings."""
        settings = NeptuneSettings(
            cluster_endpoint="neptune.custom.amazonaws.com",
            port=8183,
            region="us-west-2",
            use_iam_auth=False,
            enable_ssl=False,
            websocket_protocol="wss",
        )

        assert settings.cluster_endpoint == "neptune.custom.amazonaws.com"
        assert settings.port == 8183
        assert settings.region == "us-west-2"
        assert settings.use_iam_auth is False
        assert settings.enable_ssl is False
        assert settings.websocket_protocol == "wss"
