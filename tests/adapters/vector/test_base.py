"""Tests for vector adapter base classes."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from acb.adapters.vector._base import (
    VectorBase,
    VectorBaseSettings,
    VectorCollection,
    VectorDocument,
    VectorSearchResult,
)


class TestVectorDocument:
    """Test VectorDocument model."""

    def test_vector_document_creation(self):
        """Test creating a VectorDocument."""
        doc = VectorDocument(
            id="test-id", vector=[0.1, 0.2, 0.3], metadata={"title": "Test Document"}
        )

        assert doc.id == "test-id"
        assert doc.vector == [0.1, 0.2, 0.3]
        assert doc.metadata == {"title": "Test Document"}

    def test_vector_document_without_id(self):
        """Test creating a VectorDocument without ID."""
        doc = VectorDocument(
            vector=[0.1, 0.2, 0.3], metadata={"title": "Test Document"}
        )

        assert doc.id is None
        assert doc.vector == [0.1, 0.2, 0.3]
        assert doc.metadata == {"title": "Test Document"}

    def test_vector_document_empty_metadata(self):
        """Test creating a VectorDocument with empty metadata."""
        doc = VectorDocument(id="test-id", vector=[0.1, 0.2, 0.3])

        assert doc.id == "test-id"
        assert doc.vector == [0.1, 0.2, 0.3]
        assert doc.metadata == {}


class TestVectorSearchResult:
    """Test VectorSearchResult model."""

    def test_vector_search_result_creation(self):
        """Test creating a VectorSearchResult."""
        result = VectorSearchResult(
            id="test-id",
            score=0.95,
            metadata={"title": "Test Result"},
            vector=[0.1, 0.2, 0.3],
        )

        assert result.id == "test-id"
        assert result.score == 0.95
        assert result.metadata == {"title": "Test Result"}
        assert result.vector == [0.1, 0.2, 0.3]

    def test_vector_search_result_without_vector(self):
        """Test creating a VectorSearchResult without vector."""
        result = VectorSearchResult(
            id="test-id", score=0.95, metadata={"title": "Test Result"}
        )

        assert result.id == "test-id"
        assert result.score == 0.95
        assert result.metadata == {"title": "Test Result"}
        assert result.vector is None

    def test_vector_search_result_empty_metadata(self):
        """Test creating a VectorSearchResult with empty metadata."""
        result = VectorSearchResult(id="test-id", score=0.95)

        assert result.id == "test-id"
        assert result.score == 0.95
        assert result.metadata == {}


class TestVectorBaseSettings:
    """Test VectorBaseSettings configuration."""

    @patch("acb.depends.depends.get")
    def test_vector_base_settings_defaults(self, mock_depends):
        """Test VectorBaseSettings with default values."""
        mock_config = MagicMock()
        mock_depends.return_value = mock_config

        settings = VectorBaseSettings()

        assert settings.host.get_secret_value() == "127.0.0.1"
        assert settings.port is None
        assert settings.collection_prefix == ""
        assert settings.default_dimension == 1536
        assert settings.default_distance_metric == "cosine"
        assert settings.connect_timeout == 30.0
        assert settings.request_timeout == 30.0
        assert settings.max_retries == 3
        assert settings.batch_size == 100
        assert settings.max_connections == 10

    @patch("acb.depends.depends.get")
    def test_vector_base_settings_custom_values(self, mock_depends):
        """Test VectorBaseSettings with custom values."""
        mock_config = MagicMock()
        mock_depends.return_value = mock_config

        settings = VectorBaseSettings(
            host="custom-host",
            port=9999,
            default_dimension=512,
            default_distance_metric="euclidean",
            batch_size=50,
        )

        assert settings.host.get_secret_value() == "custom-host"
        assert settings.port == 9999
        assert settings.default_dimension == 512
        assert settings.default_distance_metric == "euclidean"
        assert settings.batch_size == 50


class TestVectorCollection:
    """Test VectorCollection wrapper."""

    @pytest.fixture
    def mock_adapter(self):
        """Mock vector adapter."""
        adapter = AsyncMock()
        adapter.search.return_value = [
            VectorSearchResult(id="doc1", score=0.95, metadata={"title": "Test"})
        ]
        adapter.insert.return_value = ["doc1"]
        adapter.upsert.return_value = ["doc1"]
        adapter.delete.return_value = True
        adapter.get.return_value = [
            VectorDocument(
                id="doc1", vector=[0.1, 0.2, 0.3], metadata={"title": "Test"}
            )
        ]
        adapter.count.return_value = 1
        return adapter

    @pytest.fixture
    def collection(self, mock_adapter):
        """Vector collection instance."""
        return VectorCollection(mock_adapter, "test_collection")

    @pytest.mark.asyncio
    async def test_collection_search(self, collection, mock_adapter):
        """Test collection search method."""
        query_vector = [0.1, 0.2, 0.3]
        results = await collection.search(query_vector, limit=5)

        mock_adapter.search.assert_called_once_with(
            "test_collection", query_vector, 5, None, False
        )
        assert len(results) == 1
        assert results[0].id == "doc1"

    @pytest.mark.asyncio
    async def test_collection_insert(self, collection, mock_adapter):
        """Test collection insert method."""
        documents = [
            VectorDocument(
                id="doc1", vector=[0.1, 0.2, 0.3], metadata={"title": "Test"}
            )
        ]
        ids = await collection.insert(documents)

        mock_adapter.insert.assert_called_once_with("test_collection", documents)
        assert ids == ["doc1"]

    @pytest.mark.asyncio
    async def test_collection_upsert(self, collection, mock_adapter):
        """Test collection upsert method."""
        documents = [
            VectorDocument(
                id="doc1", vector=[0.1, 0.2, 0.3], metadata={"title": "Test"}
            )
        ]
        ids = await collection.upsert(documents)

        mock_adapter.upsert.assert_called_once_with("test_collection", documents)
        assert ids == ["doc1"]

    @pytest.mark.asyncio
    async def test_collection_delete(self, collection, mock_adapter):
        """Test collection delete method."""
        result = await collection.delete(["doc1"])

        mock_adapter.delete.assert_called_once_with("test_collection", ["doc1"])
        assert result is True

    @pytest.mark.asyncio
    async def test_collection_get(self, collection, mock_adapter):
        """Test collection get method."""
        documents = await collection.get(["doc1"], include_vectors=True)

        mock_adapter.get.assert_called_once_with("test_collection", ["doc1"], True)
        assert len(documents) == 1
        assert documents[0].id == "doc1"

    @pytest.mark.asyncio
    async def test_collection_count(self, collection, mock_adapter):
        """Test collection count method."""
        count = await collection.count()

        mock_adapter.count.assert_called_once_with("test_collection", None)
        assert count == 1


class MockVectorBase(VectorBase):
    """Mock implementation of VectorBase for testing."""

    async def init(self):
        """Mock init method."""
        pass

    async def search(
        self,
        collection,
        query_vector,
        limit=10,
        filter_expr=None,
        include_vectors=False,
        **kwargs,
    ):
        return []

    async def insert(self, collection, documents, **kwargs):
        return []

    async def upsert(self, collection, documents, **kwargs):
        return []

    async def delete(self, collection, ids, **kwargs):
        return True

    async def get(self, collection, ids, include_vectors=False, **kwargs):
        return []

    async def count(self, collection, filter_expr=None, **kwargs):
        return 0

    async def create_collection(
        self, name, dimension, distance_metric="cosine", **kwargs
    ):
        return True

    async def delete_collection(self, name, **kwargs):
        return True

    async def list_collections(self, **kwargs):
        return []


class TestVectorBase:
    """Test VectorBase abstract class."""

    @pytest.fixture
    def vector_base(self):
        """Vector base instance."""
        return MockVectorBase()

    def test_vector_base_initialization(self, vector_base):
        """Test VectorBase initialization."""
        assert hasattr(vector_base, "_collections")
        assert hasattr(vector_base, "_client")
        assert vector_base._collections == {}
        assert vector_base._client is None

    def test_vector_base_getattr(self, vector_base):
        """Test dynamic collection access."""
        collection = vector_base.test_collection

        assert isinstance(collection, VectorCollection)
        assert collection.name == "test_collection"
        assert "test_collection" in vector_base._collections

    def test_vector_base_getattr_cached(self, vector_base):
        """Test that collections are cached."""
        collection1 = vector_base.test_collection
        collection2 = vector_base.test_collection

        assert collection1 is collection2

    @pytest.mark.asyncio
    async def test_get_client(self, vector_base):
        """Test get_client method."""
        with patch.object(vector_base, "_ensure_client") as mock_ensure:
            mock_ensure.return_value = "mock_client"
            client = await vector_base.get_client()

            mock_ensure.assert_called_once()
            assert client == "mock_client"

    @pytest.mark.asyncio
    async def test_transaction_context_manager(self, vector_base):
        """Test transaction context manager."""
        with patch.object(vector_base, "get_client") as mock_get_client:
            mock_get_client.return_value = "mock_client"

            async with vector_base.transaction() as client:
                assert client == "mock_client"

            mock_get_client.assert_called_once()
