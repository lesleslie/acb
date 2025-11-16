"""Tests for ArangoDB graph adapter."""

from unittest.mock import MagicMock, patch

import pytest

from acb.adapters.graph._base import (
    GraphEdgeModel,
    GraphNodeModel,
    GraphQueryLanguage,
)
from acb.adapters.graph.arangodb import MODULE_METADATA, ArangoDBSettings, Graph


class MockArangoClient:
    """Mock ArangoDB client."""

    def __init__(self, hosts=None, **kwargs):
        self.hosts = hosts
        self.kwargs = kwargs

    def db(self, name, username=None, password=None):
        """Mock database connection."""
        return MockArangoDatabase(name, username, password)


class MockArangoDatabase:
    """Mock ArangoDB database."""

    def __init__(self, name, username=None, password=None):
        self.name = name
        self.username = username
        self.password = password
        self._collections = {}
        self._graphs = {}

    def has_graph(self, graph_name):
        """Mock graph existence check."""
        return graph_name in self._graphs

    def create_graph(self, name, edge_definitions):
        """Mock graph creation."""
        self._graphs[name] = {
            "name": name,
            "edge_definitions": edge_definitions,
        }

    def graph(self, name):
        """Mock graph retrieval."""
        return MockArangoGraph(name, self)

    def has_collection(self, collection_name):
        """Mock collection existence check."""
        return collection_name in self._collections

    def create_collection(self, collection_name, edge=False):
        """Mock collection creation."""
        self._collections[collection_name] = MockArangoCollection(collection_name, edge)

    def collection(self, collection_name):
        """Mock collection retrieval."""
        return self._collections.get(
            collection_name, MockArangoCollection(collection_name)
        )

    def collections(self):
        """Mock collections listing."""
        return [
            {"name": name, "type": 3 if coll.is_edge else 2}
            for name, coll in self._collections.items()
        ]

    def begin_transaction(self, read=None, write=None):
        """Mock transaction begin."""
        return MockArangoTransaction(read, write)

    @property
    def aql(self):
        """Mock AQL interface."""
        return MockArangoAQL()


class MockArangoGraph:
    """Mock ArangoDB graph."""

    def __init__(self, name, database):
        self.name = name
        self.database = database


class MockArangoCollection:
    """Mock ArangoDB collection."""

    def __init__(self, name, is_edge=False):
        self.name = name
        self.is_edge = is_edge
        self._documents = {}

    def insert(self, document, return_new=False):
        """Mock document insertion."""
        doc_key = document.get("_key", f"doc_{len(self._documents)}")
        doc_id = f"{self.name}/{doc_key}"
        document["_id"] = doc_id
        document["_key"] = doc_key
        self._documents[doc_key] = document

        result = {"_id": doc_id, "_key": doc_key}
        if return_new:
            result["new"] = document
        return result

    def insert_many(self, documents, return_new=False):
        """Mock bulk document insertion."""
        results = []
        for doc in documents:
            result = self.insert(doc, return_new)
            results.append(result)
        return results

    def get(self, doc_key):
        """Mock document retrieval."""
        return self._documents.get(doc_key)

    def has(self, doc_key):
        """Mock document existence check."""
        return doc_key in self._documents

    def update(self, doc_key, update_data, return_new=False):
        """Mock document update."""
        if doc_key in self._documents:
            doc = self._documents[doc_key]
            doc.update(update_data)
            result = {"_id": doc["_id"], "_key": doc_key}
            if return_new:
                result["new"] = doc
            return result
        raise KeyError(f"Document {doc_key} not found")

    def delete(self, doc_key):
        """Mock document deletion."""
        if doc_key in self._documents:
            del self._documents[doc_key]
            return True
        return False

    def truncate(self):
        """Mock collection truncation."""
        self._documents.clear()

    def indexes(self):
        """Mock indexes listing."""
        return [
            {"id": "primary", "type": "primary", "name": "primary", "fields": ["_key"]},
        ]

    def add_index(self, index_def):
        """Mock index creation."""
        return {"id": f"idx_{len(self.indexes())}", **index_def}

    def delete_index(self, index_id):
        """Mock index deletion."""
        return True


class MockArangoTransaction:
    """Mock ArangoDB transaction."""

    def __init__(self, read=None, write=None):
        self.read = read or []
        self.write = write or []

    def commit_transaction(self):
        """Mock transaction commit."""
        pass

    def abort_transaction(self):
        """Mock transaction abort."""
        pass


class MockArangoAQL:
    """Mock ArangoDB AQL interface."""

    def execute(self, query, bind_vars=None, **kwargs):
        """Mock AQL query execution."""
        return MockArangoCursor(query, bind_vars)


class MockArangoCursor:
    """Mock ArangoDB cursor."""

    def __init__(self, query, bind_vars=None):
        self.query = query
        self.bind_vars = bind_vars or {}
        self._results = self._mock_results()

    def _mock_results(self):
        """Generate mock results based on query."""
        if "COUNT" in self.query.upper() or "LENGTH" in self.query.upper():
            return [10]
        elif "RETURN" in self.query.upper():
            if "vertices" in self.query.lower():
                return [
                    {
                        "_id": "vertices/test1",
                        "_key": "test1",
                        "name": "Test Node",
                        "created_at": "2023-01-01T00:00:00",
                    }
                ]
            elif "edges" in self.query.lower():
                return [
                    {
                        "_id": "edges/test_edge",
                        "_key": "test_edge",
                        "_from": "vertices/test1",
                        "_to": "vertices/test2",
                        "type": "CONNECTS",
                    }
                ]
            else:
                return [{"result": "mock_data"}]
        return []

    def __iter__(self):
        """Mock cursor iteration."""
        return iter(self._results)

    def statistics(self):
        """Mock cursor statistics."""
        return {
            "writes_executed": 1,
            "writes_ignored": 0,
            "scan_full": 0,
            "scan_index": 1,
            "filtered": 0,
            "execution_time": 0.001,
        }


@pytest.mark.asyncio
class TestArangoDBAdapter:
    """Test ArangoDB adapter functionality."""

    @pytest.fixture
    def arangodb_settings(self):
        """Create ArangoDB settings for testing."""
        return ArangoDBSettings(
            host="localhost",
            port=8529,
            database="test_db",
            graph_name="test_graph",
            vertex_collections=["vertices"],
            edge_collections=["edges"],
        )

    @pytest.fixture
    def arangodb_adapter(self, arangodb_settings):
        """Create ArangoDB adapter for testing."""
        return Graph(**arangodb_settings.model_dump())

    async def test_module_metadata(self):
        """Test module metadata."""
        assert MODULE_METADATA.name == "ArangoDB Graph Database"
        assert MODULE_METADATA.category == "graph"
        assert MODULE_METADATA.provider == "arangodb"
        assert "python-arango>=7.0.0" in MODULE_METADATA.required_packages

    async def test_query_language(self, arangodb_adapter):
        """Test query language property."""
        assert arangodb_adapter.query_language == GraphQueryLanguage.AQL

    async def test_supported_features(self, arangodb_adapter):
        """Test supported features."""
        features = arangodb_adapter.supported_features
        assert "aql_queries" in features
        assert "multi_model" in features
        assert "acid_transactions" in features
        assert "full_text_search" in features

    @patch("acb.adapters.graph.arangodb.ArangoClient")
    async def test_create_client(self, mock_arango_client, arangodb_adapter):
        """Test ArangoDB client creation."""
        mock_client = MockArangoClient()
        mock_arango_client.return_value = mock_client

        client = await arangodb_adapter._create_client()

        assert isinstance(client, MockArangoDatabase)
        mock_arango_client.assert_called_once()

    @patch("acb.adapters.graph.arangodb.ArangoClient")
    async def test_ensure_graph(self, mock_arango_client, arangodb_adapter):
        """Test graph creation and retrieval."""
        mock_client = MockArangoClient()
        mock_arango_client.return_value = mock_client

        # Create client which triggers _ensure_graph
        await arangodb_adapter._create_client()

        # Verify graph was created
        assert arangodb_adapter._graph is not None

    @patch("acb.adapters.graph.arangodb.ArangoClient")
    async def test_execute_query(self, mock_arango_client, arangodb_adapter):
        """Test AQL query execution."""
        mock_client = MockArangoClient()
        mock_arango_client.return_value = mock_client

        result = await arangodb_adapter._execute_query("FOR v IN vertices RETURN v")

        assert result.query_language == GraphQueryLanguage.AQL
        assert result.execution_time is not None
        assert len(result.records) >= 0

    @patch("acb.adapters.graph.arangodb.ArangoClient")
    async def test_create_node(self, mock_arango_client, arangodb_adapter):
        """Test node creation."""
        mock_client = MockArangoClient()
        mock_arango_client.return_value = mock_client

        node = await arangodb_adapter._create_node(["Person"], {"name": "John"})

        assert isinstance(node, GraphNodeModel)
        assert "Person" in node.labels
        assert node.properties["name"] == "John"
        assert node.created_at is not None

    @patch("acb.adapters.graph.arangodb.ArangoClient")
    async def test_get_node(self, mock_arango_client, arangodb_adapter):
        """Test node retrieval."""
        mock_client = MockArangoClient()
        mock_arango_client.return_value = mock_client

        # First create the database client
        database = await arangodb_adapter._create_client()

        # Mock document in collection
        collection = database.collection("vertices")
        test_doc = {
            "_id": "vertices/test1",
            "_key": "test1",
            "name": "John",
            "created_at": "2023-01-01T00:00:00",
        }
        collection._documents["test1"] = test_doc

        node = await arangodb_adapter._get_node("vertices/test1")

        assert node is not None
        assert isinstance(node, GraphNodeModel)
        assert node.id == "vertices/test1"

    @patch("acb.adapters.graph.arangodb.ArangoClient")
    async def test_get_node_not_found(self, mock_arango_client, arangodb_adapter):
        """Test node retrieval when not found."""
        mock_client = MockArangoClient()
        mock_arango_client.return_value = mock_client

        node = await arangodb_adapter._get_node("vertices/non_existent")

        assert node is None

    @patch("acb.adapters.graph.arangodb.ArangoClient")
    async def test_update_node(self, mock_arango_client, arangodb_adapter):
        """Test node update."""
        mock_client = MockArangoClient()
        mock_arango_client.return_value = mock_client

        # First create the database client
        database = await arangodb_adapter._create_client()

        # Mock existing document
        collection = database.collection("vertices")
        test_doc = {
            "_id": "vertices/test1",
            "_key": "test1",
            "name": "John",
            "created_at": "2023-01-01T00:00:00",
        }
        collection._documents["test1"] = test_doc

        node = await arangodb_adapter._update_node("vertices/test1", {"name": "Jane"})

        assert isinstance(node, GraphNodeModel)
        assert node.properties["name"] == "Jane"

    @patch("acb.adapters.graph.arangodb.ArangoClient")
    async def test_delete_node(self, mock_arango_client, arangodb_adapter):
        """Test node deletion."""
        mock_client = MockArangoClient()
        mock_arango_client.return_value = mock_client

        result = await arangodb_adapter._delete_node("vertices/test1")

        assert result is True

    @patch("acb.adapters.graph.arangodb.ArangoClient")
    async def test_create_edge(self, mock_arango_client, arangodb_adapter):
        """Test edge creation."""
        mock_client = MockArangoClient()
        mock_arango_client.return_value = mock_client

        edge = await arangodb_adapter._create_edge(
            "KNOWS", "vertices/node1", "vertices/node2", {"since": "2020"}
        )

        assert isinstance(edge, GraphEdgeModel)
        assert edge.type == "KNOWS"
        assert edge.from_node == "vertices/node1"
        assert edge.to_node == "vertices/node2"
        assert edge.properties["since"] == "2020"

    @patch("acb.adapters.graph.arangodb.ArangoClient")
    async def test_get_edge(self, mock_arango_client, arangodb_adapter):
        """Test edge retrieval."""
        mock_client = MockArangoClient()
        mock_arango_client.return_value = mock_client

        # First create the database client
        database = await arangodb_adapter._create_client()

        # Mock edge document in collection
        collection = database.collection("edges")
        collection.is_edge = True
        test_edge = {
            "_id": "edges/test_edge",
            "_key": "test_edge",
            "_from": "vertices/node1",
            "_to": "vertices/node2",
            "type": "KNOWS",
        }
        collection._documents["test_edge"] = test_edge

        edge = await arangodb_adapter._get_edge("edges/test_edge")

        assert edge is not None
        assert isinstance(edge, GraphEdgeModel)
        assert edge.id == "edges/test_edge"

    @patch("acb.adapters.graph.arangodb.ArangoClient")
    async def test_find_path(self, mock_arango_client, arangodb_adapter):
        """Test path finding."""
        mock_client = MockArangoClient()
        mock_arango_client.return_value = mock_client

        # Mock path query result
        with patch.object(arangodb_adapter, "_execute_query") as mock_execute:
            mock_execute.return_value = MagicMock()
            mock_execute.return_value.records = [
                {
                    "vertices": [
                        {"_id": "vertices/node1", "name": "Node1"},
                        {"_id": "vertices/node2", "name": "Node2"},
                    ],
                    "edges": [
                        {
                            "_id": "edges/edge1",
                            "_from": "vertices/node1",
                            "_to": "vertices/node2",
                            "type": "CONNECTS",
                        }
                    ],
                }
            ]

            paths = await arangodb_adapter._find_path(
                "vertices/node1", "vertices/node2", max_depth=5, direction="both"
            )

        assert isinstance(paths, list)
        assert len(paths) == 1

    @patch("acb.adapters.graph.arangodb.ArangoClient")
    async def test_get_schema(self, mock_arango_client, arangodb_adapter):
        """Test schema retrieval."""
        mock_client = MockArangoClient()
        mock_arango_client.return_value = mock_client

        # First create the database client
        database = await arangodb_adapter._create_client()

        # Mock collections
        database._collections["vertices"] = MockArangoCollection(
            "vertices", is_edge=False
        )
        database._collections["edges"] = MockArangoCollection("edges", is_edge=True)

        schema = await arangodb_adapter._get_schema()

        assert "vertices" in schema.node_types
        assert "edges" in schema.edge_types
        assert isinstance(schema.indexes, list)

    @patch("acb.adapters.graph.arangodb.ArangoClient")
    async def test_transaction_operations(self, mock_arango_client, arangodb_adapter):
        """Test transaction operations."""
        mock_client = MockArangoClient()
        mock_arango_client.return_value = mock_client

        # Create client first
        await arangodb_adapter._create_client()

        # Test transaction lifecycle
        await arangodb_adapter.begin_transaction()
        assert arangodb_adapter._transaction is not None

        await arangodb_adapter.commit_transaction()
        assert arangodb_adapter._transaction is None

        # Test rollback
        await arangodb_adapter.begin_transaction()
        await arangodb_adapter.rollback_transaction()
        assert arangodb_adapter._transaction is None

    @patch("acb.adapters.graph.arangodb.ArangoClient")
    async def test_bulk_operations(self, mock_arango_client, arangodb_adapter):
        """Test bulk operations."""
        mock_client = MockArangoClient()
        mock_arango_client.return_value = mock_client

        # Test bulk node creation
        nodes_data = [
            {"labels": ["Person"], "properties": {"name": "John"}},
            {"labels": ["Person"], "properties": {"name": "Jane"}},
        ]
        nodes = await arangodb_adapter._bulk_create_nodes(nodes_data)

        assert len(nodes) == 2
        assert all(isinstance(n, GraphNodeModel) for n in nodes)

        # Test bulk edge creation
        edges_data = [
            {
                "type": "KNOWS",
                "from_node": "vertices/node1",
                "to_node": "vertices/node2",
                "properties": {},
            },
            {
                "type": "KNOWS",
                "from_node": "vertices/node2",
                "to_node": "vertices/node3",
                "properties": {},
            },
        ]
        edges = await arangodb_adapter._bulk_create_edges(edges_data)

        assert len(edges) == 2
        assert all(isinstance(e, GraphEdgeModel) for e in edges)

    @patch("acb.adapters.graph.arangodb.ArangoClient")
    async def test_count_operations(self, mock_arango_client, arangodb_adapter):
        """Test count operations."""
        mock_client = MockArangoClient()
        mock_arango_client.return_value = mock_client

        # Mock count query results
        with patch.object(arangodb_adapter, "_execute_query") as mock_execute:
            mock_execute.return_value = MagicMock()
            mock_execute.return_value.records = [10]

            node_count = await arangodb_adapter._count_nodes(["Person"])
            edge_count = await arangodb_adapter._count_edges(["KNOWS"])

        assert node_count == 10
        assert edge_count == 10

    @patch("acb.adapters.graph.arangodb.ArangoClient")
    async def test_clear_graph(self, mock_arango_client, arangodb_adapter):
        """Test graph clearing."""
        mock_client = MockArangoClient()
        mock_arango_client.return_value = mock_client

        result = await arangodb_adapter._clear_graph()

        assert result is True

    @patch("acb.adapters.graph.arangodb.ArangoClient")
    async def test_create_and_drop_index(self, mock_arango_client, arangodb_adapter):
        """Test index operations."""
        mock_client = MockArangoClient()
        mock_arango_client.return_value = mock_client

        # Create index
        result = await arangodb_adapter._create_index(["vertices"], ["name"], "hash")
        assert result is True

        # Drop index
        result = await arangodb_adapter._drop_index("test_index")
        assert result is True

    async def test_arango_doc_to_node(self, arangodb_adapter):
        """Test ArangoDB document to node conversion."""
        doc = {
            "_id": "vertices/test1",
            "_key": "test1",
            "name": "John",
            "age": 30,
            "created_at": "2023-01-01T00:00:00",
        }

        node = arangodb_adapter._arango_doc_to_node(doc)

        assert isinstance(node, GraphNodeModel)
        assert node.id == "vertices/test1"
        assert "vertices" in node.labels
        assert node.properties["name"] == "John"
        assert node.properties["age"] == 30

    async def test_arango_doc_to_edge(self, arangodb_adapter):
        """Test ArangoDB edge document to edge conversion."""
        doc = {
            "_id": "edges/test_edge",
            "_key": "test_edge",
            "_from": "vertices/node1",
            "_to": "vertices/node2",
            "weight": 1.5,
            "created_at": "2023-01-01T00:00:00",
        }

        edge = arangodb_adapter._arango_doc_to_edge(doc)

        assert isinstance(edge, GraphEdgeModel)
        assert edge.id == "edges/test_edge"
        assert edge.type == "edges"
        assert edge.from_node == "vertices/node1"
        assert edge.to_node == "vertices/node2"
        assert edge.properties["weight"] == 1.5


class TestArangoDBSettings:
    """Test ArangoDB settings."""

    def test_default_settings(self):
        """Test default ArangoDB settings."""
        settings = ArangoDBSettings()

        assert settings.host == "127.0.0.1"
        assert settings.port == 8529
        assert settings.protocol == "http"
        assert settings.database == "_system"
        assert settings.graph_name == "default_graph"

    def test_custom_settings(self):
        """Test custom ArangoDB settings."""
        settings = ArangoDBSettings(
            host="arangodb.example.com",
            port=8530,
            protocol="https",
            database="production",
            graph_name="production_graph",
            vertex_collections=["users", "products"],
            edge_collections=["purchases", "views"],
            create_collections=False,
            replication_factor=3,
        )

        assert settings.host == "arangodb.example.com"
        assert settings.port == 8530
        assert settings.protocol == "https"
        assert settings.database == "production"
        assert settings.graph_name == "production_graph"
        assert settings.vertex_collections == ["users", "products"]
        assert settings.edge_collections == ["purchases", "views"]
        assert settings.create_collections is False
        assert settings.replication_factor == 3
