"""Tests for Neo4j graph adapter."""

from unittest.mock import MagicMock, patch

import pytest
from datetime import datetime

from acb.adapters.graph._base import (
    GraphEdgeModel,
    GraphNodeModel,
    GraphQueryLanguage,
)
from acb.adapters.graph.neo4j import MODULE_METADATA, Graph, Neo4jSettings


class MockNeo4jDriver:
    """Mock Neo4j driver for testing."""

    def __init__(self):
        self.closed = False

    async def verify_connectivity(self):
        """Mock connectivity verification."""
        pass

    def session(self, database=None):
        """Mock session creation."""
        return MockNeo4jSession()

    async def close(self):
        """Mock driver close."""
        self.closed = True


class MockNeo4jSession:
    """Mock Neo4j session for testing."""

    def __init__(self):
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def run(self, query, parameters=None):
        """Mock query execution."""
        return MockNeo4jResult()

    async def begin_transaction(self):
        """Mock transaction begin."""
        return MockNeo4jTransaction()

    async def close(self):
        """Mock session close."""
        self.closed = True


class MockNeo4jTransaction:
    """Mock Neo4j transaction for testing."""

    def __init__(self):
        self.closed = False

    async def run(self, query, parameters=None):
        """Mock query execution in transaction."""
        return MockNeo4jResult()

    async def commit(self):
        """Mock transaction commit."""
        pass

    async def rollback(self):
        """Mock transaction rollback."""
        pass

    async def close(self):
        """Mock transaction close."""
        self.closed = True


class MockNeo4jResult:
    """Mock Neo4j result for testing."""

    def __init__(self):
        self._records = []

    async def __aiter__(self):
        for record in self._records:
            yield record

    def statistics(self):
        """Mock result statistics."""
        return {"nodes_created": 1, "relationships_created": 0}


class MockNeo4jRecord:
    """Mock Neo4j record for testing."""

    def __init__(self, data):
        self._data = data

    def __iter__(self):
        return iter(self._data.items())

    def __getitem__(self, key):
        return self._data[key]

    def values(self):
        """Mock record values."""
        return self._data.values()

    def dict(self):
        """Mock record as dict."""
        return self._data


class MockNeo4jNode:
    """Mock Neo4j node for testing."""

    def __init__(self, element_id="1", labels=None, properties=None):
        self.element_id = element_id
        self.labels = labels or []
        self._properties = properties or {}

    def __iter__(self):
        return iter(self._properties.items())

    def __getitem__(self, key):
        return self._properties[key]

    def get(self, key, default=None):
        return self._properties.get(key, default)


class MockNeo4jRelationship:
    """Mock Neo4j relationship for testing."""

    def __init__(
        self,
        element_id="1",
        type="RELATES_TO",
        start_node=None,
        end_node=None,
        properties=None,
    ):
        self.element_id = element_id
        self.type = type
        self.start_node = start_node or MockNeo4jNode("start")
        self.end_node = end_node or MockNeo4jNode("end")
        self._properties = properties or {}

    def __iter__(self):
        return iter(self._properties.items())

    def __getitem__(self, key):
        return self._properties[key]

    def get(self, key, default=None):
        return self._properties.get(key, default)


@pytest.mark.asyncio
class TestNeo4jAdapter:
    """Test Neo4j adapter functionality."""

    @pytest.fixture
    def neo4j_settings(self):
        """Create Neo4j settings for testing."""
        return Neo4jSettings(
            host="localhost",
            port=7687,
            user="neo4j",
            password="password",
            database="test_db",
        )

    @pytest.fixture
    def neo4j_adapter(self, neo4j_settings):
        """Create Neo4j adapter for testing."""
        return Graph(**neo4j_settings.model_dump())

    async def test_module_metadata(self):
        """Test module metadata."""
        assert MODULE_METADATA.name == "Neo4j Graph Database"
        assert MODULE_METADATA.category == "graph"
        assert MODULE_METADATA.provider == "neo4j"
        assert "neo4j>=5.0.0" in MODULE_METADATA.required_packages

    async def test_query_language(self, neo4j_adapter):
        """Test query language property."""
        assert neo4j_adapter.query_language == GraphQueryLanguage.CYPHER

    async def test_supported_features(self, neo4j_adapter):
        """Test supported features."""
        features = neo4j_adapter.supported_features
        assert "cypher_queries" in features
        assert "transactions" in features
        assert "graph_algorithms" in features

    @patch("acb.adapters.graph.neo4j.AsyncGraphDatabase")
    async def test_create_client(self, mock_graph_db, neo4j_adapter):
        """Test Neo4j client creation."""
        mock_driver = MockNeo4jDriver()
        mock_graph_db.driver.return_value = mock_driver

        client = await neo4j_adapter._create_client()

        assert client is mock_driver
        mock_graph_db.driver.assert_called_once()
        assert mock_driver.verify_connectivity.called

    @patch("acb.adapters.graph.neo4j.AsyncGraphDatabase")
    async def test_execute_query(self, mock_graph_db, neo4j_adapter):
        """Test query execution."""
        mock_driver = MockNeo4jDriver()
        mock_graph_db.driver.return_value = mock_driver

        # Mock result with node
        mock_result = MockNeo4jResult()
        mock_record = MockNeo4jRecord(
            {"n": MockNeo4jNode("1", ["Person"], {"name": "John"})}
        )
        mock_result._records = [mock_record]

        with patch.object(MockNeo4jSession, "run", return_value=mock_result):
            result = await neo4j_adapter._execute_query("MATCH (n) RETURN n")

        assert result.query_language == GraphQueryLanguage.CYPHER
        assert result.execution_time is not None
        assert len(result.records) == 1

    @patch("acb.adapters.graph.neo4j.AsyncGraphDatabase")
    async def test_create_node(self, mock_graph_db, neo4j_adapter):
        """Test node creation."""
        mock_driver = MockNeo4jDriver()
        mock_graph_db.driver.return_value = mock_driver

        # Mock successful node creation
        mock_result = MockNeo4jResult()
        mock_node = MockNeo4jNode("1", ["Person"], {"name": "John", "id": "test_id"})
        mock_record = MockNeo4jRecord({"n": mock_node})
        mock_result._records = [mock_record]

        with patch.object(MockNeo4jSession, "run", return_value=mock_result):
            node = await neo4j_adapter._create_node(["Person"], {"name": "John"})

        assert isinstance(node, GraphNodeModel)
        assert "Person" in node.labels
        assert node.properties["name"] == "John"

    @patch("acb.adapters.graph.neo4j.AsyncGraphDatabase")
    async def test_get_node(self, mock_graph_db, neo4j_adapter):
        """Test node retrieval."""
        mock_driver = MockNeo4jDriver()
        mock_graph_db.driver.return_value = mock_driver

        # Mock node found
        mock_result = MockNeo4jResult()
        mock_node = MockNeo4jNode("1", ["Person"], {"name": "John", "id": "test_id"})
        mock_record = MockNeo4jRecord({"n": mock_node})
        mock_result._records = [mock_record]

        with patch.object(MockNeo4jSession, "run", return_value=mock_result):
            node = await neo4j_adapter._get_node("test_id")

        assert node is not None
        assert isinstance(node, GraphNodeModel)

    @patch("acb.adapters.graph.neo4j.AsyncGraphDatabase")
    async def test_get_node_not_found(self, mock_graph_db, neo4j_adapter):
        """Test node retrieval when not found."""
        mock_driver = MockNeo4jDriver()
        mock_graph_db.driver.return_value = mock_driver

        # Mock no results
        mock_result = MockNeo4jResult()
        mock_result._records = []

        with patch.object(MockNeo4jSession, "run", return_value=mock_result):
            node = await neo4j_adapter._get_node("non_existent")

        assert node is None

    @patch("acb.adapters.graph.neo4j.AsyncGraphDatabase")
    async def test_update_node(self, mock_graph_db, neo4j_adapter):
        """Test node update."""
        mock_driver = MockNeo4jDriver()
        mock_graph_db.driver.return_value = mock_driver

        # Mock successful update
        mock_result = MockNeo4jResult()
        mock_node = MockNeo4jNode("1", ["Person"], {"name": "Jane", "id": "test_id"})
        mock_record = MockNeo4jRecord({"n": mock_node})
        mock_result._records = [mock_record]

        with patch.object(MockNeo4jSession, "run", return_value=mock_result):
            node = await neo4j_adapter._update_node("test_id", {"name": "Jane"})

        assert isinstance(node, GraphNodeModel)
        assert node.properties["name"] == "Jane"

    @patch("acb.adapters.graph.neo4j.AsyncGraphDatabase")
    async def test_delete_node(self, mock_graph_db, neo4j_adapter):
        """Test node deletion."""
        mock_driver = MockNeo4jDriver()
        mock_graph_db.driver.return_value = mock_driver

        # Mock successful deletion
        mock_result = MockNeo4jResult()

        with patch.object(MockNeo4jSession, "run", return_value=mock_result):
            result = await neo4j_adapter._delete_node("test_id")

        assert result is True

    @patch("acb.adapters.graph.neo4j.AsyncGraphDatabase")
    async def test_create_edge(self, mock_graph_db, neo4j_adapter):
        """Test edge creation."""
        mock_driver = MockNeo4jDriver()
        mock_graph_db.driver.return_value = mock_driver

        # Mock successful edge creation
        mock_result = MockNeo4jResult()
        start_node = MockNeo4jNode("1")
        end_node = MockNeo4jNode("2")
        mock_relationship = MockNeo4jRelationship(
            "rel1", "KNOWS", start_node, end_node, {"since": "2020", "id": "edge_id"}
        )
        mock_record = MockNeo4jRecord({"r": mock_relationship})
        mock_result._records = [mock_record]

        with patch.object(MockNeo4jSession, "run", return_value=mock_result):
            edge = await neo4j_adapter._create_edge(
                "KNOWS", "node1", "node2", {"since": "2020"}
            )

        assert isinstance(edge, GraphEdgeModel)
        assert edge.type == "KNOWS"
        assert edge.from_node == "node1"
        assert edge.to_node == "node2"

    @patch("acb.adapters.graph.neo4j.AsyncGraphDatabase")
    async def test_get_edge(self, mock_graph_db, neo4j_adapter):
        """Test edge retrieval."""
        mock_driver = MockNeo4jDriver()
        mock_graph_db.driver.return_value = mock_driver

        # Mock edge found
        mock_result = MockNeo4jResult()
        start_node = MockNeo4jNode("1")
        end_node = MockNeo4jNode("2")
        mock_relationship = MockNeo4jRelationship(
            "rel1", "KNOWS", start_node, end_node, {"id": "edge_id"}
        )
        mock_record = MockNeo4jRecord({"r": mock_relationship})
        mock_result._records = [mock_record]

        with patch.object(MockNeo4jSession, "run", return_value=mock_result):
            edge = await neo4j_adapter._get_edge("edge_id")

        assert edge is not None
        assert isinstance(edge, GraphEdgeModel)

    @patch("acb.adapters.graph.neo4j.AsyncGraphDatabase")
    async def test_find_path(self, mock_graph_db, neo4j_adapter):
        """Test path finding."""
        mock_driver = MockNeo4jDriver()
        mock_graph_db.driver.return_value = mock_driver

        # Mock path result
        mock_result = MockNeo4jResult()
        mock_path = MagicMock()
        mock_path.nodes = [MockNeo4jNode("1"), MockNeo4jNode("2")]
        mock_path.relationships = [MockNeo4jRelationship("rel1", "KNOWS")]
        mock_record = MockNeo4jRecord({"p": mock_path})
        mock_result._records = [mock_record]

        with patch.object(MockNeo4jSession, "run", return_value=mock_result):
            paths = await neo4j_adapter._find_path(
                "node1", "node2", max_depth=5, direction="both"
            )

        assert isinstance(paths, list)

    @patch("acb.adapters.graph.neo4j.AsyncGraphDatabase")
    async def test_get_schema(self, mock_graph_db, neo4j_adapter):
        """Test schema retrieval."""
        mock_driver = MockNeo4jDriver()
        mock_graph_db.driver.return_value = mock_driver

        # Mock schema queries
        def mock_run(query, parameters=None):
            mock_result = MockNeo4jResult()
            if "db.labels()" in query:
                mock_result._records = [
                    MockNeo4jRecord({"labels": ["Person", "Company"]})
                ]
            elif "db.relationshipTypes()" in query:
                mock_result._records = [
                    MockNeo4jRecord({"types": ["WORKS_FOR", "KNOWS"]})
                ]
            elif "SHOW CONSTRAINTS" in query:
                mock_result._records = []
            elif "SHOW INDEXES" in query:
                mock_result._records = []
            return mock_result

        with patch.object(MockNeo4jSession, "run", side_effect=mock_run):
            schema = await neo4j_adapter._get_schema()

        assert "Person" in schema.node_types
        assert "Company" in schema.node_types
        assert "WORKS_FOR" in schema.edge_types
        assert "KNOWS" in schema.edge_types

    @patch("acb.adapters.graph.neo4j.AsyncGraphDatabase")
    async def test_transaction_operations(self, mock_graph_db, neo4j_adapter):
        """Test transaction operations."""
        mock_driver = MockNeo4jDriver()
        mock_graph_db.driver.return_value = mock_driver

        # Test transaction lifecycle
        await neo4j_adapter.begin_transaction()
        assert neo4j_adapter._transaction is not None

        await neo4j_adapter.commit_transaction()
        assert neo4j_adapter._transaction is None

        # Test rollback
        await neo4j_adapter.begin_transaction()
        await neo4j_adapter.rollback_transaction()
        assert neo4j_adapter._transaction is None

    @patch("acb.adapters.graph.neo4j.AsyncGraphDatabase")
    async def test_bulk_operations(self, mock_graph_db, neo4j_adapter):
        """Test bulk operations."""
        mock_driver = MockNeo4jDriver()
        mock_graph_db.driver.return_value = mock_driver

        # Mock bulk node creation
        def mock_create_node(labels, properties):
            return GraphNodeModel(
                id=f"bulk_{properties.get('name', 'node')}",
                labels=labels,
                properties=properties,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

        with patch.object(neo4j_adapter, "_create_node", side_effect=mock_create_node):
            nodes_data = [
                {"labels": ["Person"], "properties": {"name": "John"}},
                {"labels": ["Person"], "properties": {"name": "Jane"}},
            ]
            nodes = await neo4j_adapter._bulk_create_nodes(nodes_data)

        assert len(nodes) == 2
        assert all(isinstance(n, GraphNodeModel) for n in nodes)

    @patch("acb.adapters.graph.neo4j.AsyncGraphDatabase")
    async def test_count_operations(self, mock_graph_db, neo4j_adapter):
        """Test count operations."""
        mock_driver = MockNeo4jDriver()
        mock_graph_db.driver.return_value = mock_driver

        # Mock count queries
        def mock_run(query, parameters=None):
            mock_result = MockNeo4jResult()
            if "count(n)" in query:
                mock_result._records = [MockNeo4jRecord({"count": 10})]
            elif "count(r)" in query:
                mock_result._records = [MockNeo4jRecord({"count": 5})]
            return mock_result

        with patch.object(MockNeo4jSession, "run", side_effect=mock_run):
            node_count = await neo4j_adapter._count_nodes(["Person"])
            edge_count = await neo4j_adapter._count_edges(["KNOWS"])

        assert node_count == 10
        assert edge_count == 5

    @patch("acb.adapters.graph.neo4j.AsyncGraphDatabase")
    async def test_clear_graph(self, mock_graph_db, neo4j_adapter):
        """Test graph clearing."""
        mock_driver = MockNeo4jDriver()
        mock_graph_db.driver.return_value = mock_driver

        # Mock clear operation
        mock_result = MockNeo4jResult()

        with patch.object(MockNeo4jSession, "run", return_value=mock_result):
            result = await neo4j_adapter._clear_graph()

        assert result is True

    async def test_neo4j_node_to_model(self, neo4j_adapter):
        """Test Neo4j node to model conversion."""
        mock_node = MockNeo4jNode(
            "1",
            ["Person"],
            {"id": "test_id", "name": "John", "created_at": "2023-01-01T00:00:00"},
        )

        model = neo4j_adapter._neo4j_node_to_model(mock_node)

        assert isinstance(model, GraphNodeModel)
        assert model.id == "test_id"
        assert "Person" in model.labels
        assert model.properties["name"] == "John"

    async def test_neo4j_relationship_to_model(self, neo4j_adapter):
        """Test Neo4j relationship to model conversion."""
        start_node = MockNeo4jNode("1")
        end_node = MockNeo4jNode("2")
        mock_rel = MockNeo4jRelationship(
            "rel1", "KNOWS", start_node, end_node, {"id": "edge_id", "since": "2020"}
        )

        model = neo4j_adapter._neo4j_relationship_to_model(mock_rel)

        assert isinstance(model, GraphEdgeModel)
        assert model.id == "edge_id"
        assert model.type == "KNOWS"


class TestNeo4jSettings:
    """Test Neo4j settings."""

    def test_default_settings(self):
        """Test default Neo4j settings."""
        settings = Neo4jSettings()

        assert settings.host == "127.0.0.1"
        assert settings.port == 7687
        assert settings.scheme == "bolt"
        assert settings.database == "neo4j"

    def test_custom_settings(self):
        """Test custom Neo4j settings."""
        settings = Neo4jSettings(
            host="neo4j.example.com",
            port=7688,
            scheme="bolt+s",
            database="production",
            max_connection_lifetime=7200.0,
        )

        assert settings.host == "neo4j.example.com"
        assert settings.port == 7688
        assert settings.scheme == "bolt+s"
        assert settings.database == "production"
        assert settings.max_connection_lifetime == 7200.0
