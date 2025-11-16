"""Tests for Pinecone vector adapter."""

from unittest.mock import MagicMock, patch

import pytest

from acb.adapters.vector._base import VectorDocument, VectorSearchResult
from acb.adapters.vector.pinecone import Vector, VectorSettings


class TestVectorSettings:
    """Test Pinecone VectorSettings."""

    @patch("acb.depends.depends.get")
    def test_vector_settings_defaults(self, mock_depends):
        """Test VectorSettings with default values."""
        mock_config = MagicMock()
        mock_depends.return_value = mock_config

        settings = VectorSettings(api_key="test-api-key")

        assert settings.api_key.get_secret_value() == "test-api-key"
        assert settings.environment == "us-west1-gcp-free"
        assert settings.index_name == "default"
        assert settings.serverless is True
        assert settings.cloud == "aws"
        assert settings.region == "us-east-1"
        assert settings.metric == "cosine"
        assert settings.upsert_batch_size == 100

    @patch("acb.depends.depends.get")
    def test_vector_settings_custom_values(self, mock_depends):
        """Test VectorSettings with custom values."""
        mock_config = MagicMock()
        mock_depends.return_value = mock_config

        settings = VectorSettings(
            api_key="custom-key",
            environment="us-east1-gcp",
            index_name="custom-index",
            serverless=False,
            cloud="gcp",
            region="us-central1",
            metric="euclidean",
        )

        assert settings.api_key.get_secret_value() == "custom-key"
        assert settings.environment == "us-east1-gcp"
        assert settings.index_name == "custom-index"
        assert settings.serverless is False
        assert settings.cloud == "gcp"
        assert settings.region == "us-central1"
        assert settings.metric == "euclidean"


class TestPineconeVector:
    """Test Pinecone vector adapter implementation."""

    @pytest.fixture
    def mock_pinecone_client(self):
        """Mock Pinecone client."""
        mock_client = MagicMock()
        mock_index = MagicMock()

        # Mock query response
        mock_index.query.return_value = {
            "matches": [
                {
                    "id": "doc1",
                    "score": 0.95,
                    "metadata": {"title": "Test Document"},
                    "values": [0.1, 0.2, 0.3],
                }
            ]
        }

        # Mock upsert response
        mock_index.upsert.return_value = {"upserted_count": 1}

        # Mock fetch response
        mock_index.fetch.return_value = {
            "vectors": {
                "doc1": {
                    "values": [0.1, 0.2, 0.3],
                    "metadata": {"title": "Test Document"},
                }
            }
        }

        # Mock describe_index_stats response
        mock_index.describe_index_stats.return_value = {
            "total_vector_count": 10,
            "namespaces": {"test": {"vector_count": 5}},
        }

        mock_client.Index.return_value = mock_index
        mock_client.describe_index.return_value = {"status": {"ready": True}}

        return mock_client

    @pytest.fixture
    def mock_vector_settings(self):
        """Mock Pinecone vector settings."""
        with patch("acb.depends.depends.get") as mock_depends:
            mock_config = MagicMock()
            mock_depends.return_value = mock_config

            settings = VectorSettings(api_key="test-api-key")
            return settings

    @pytest.fixture
    def pinecone_adapter(self, mock_vector_settings):
        """Pinecone vector adapter instance."""
        with patch.object(Vector, "config") as mock_config:
            mock_config.vector = mock_vector_settings
            adapter = Vector()
            adapter.logger = MagicMock()
            return adapter

    @pytest.mark.asyncio
    async def test_create_client(self, pinecone_adapter, mock_pinecone_client):
        """Test Pinecone client creation."""
        with patch("acb.adapters.vector.pinecone.pinecone") as mock_pinecone:
            mock_pinecone.Pinecone.return_value = mock_pinecone_client

            client = await pinecone_adapter._create_client()

            mock_pinecone.Pinecone.assert_called_once_with(api_key="test-api-key")
            assert client == mock_pinecone_client

    @pytest.mark.asyncio
    async def test_init_existing_index(self, pinecone_adapter, mock_pinecone_client):
        """Test initialization with existing index."""
        pinecone_adapter._client = mock_pinecone_client

        await pinecone_adapter.init()

        mock_pinecone_client.describe_index.assert_called_once_with("default")
        pinecone_adapter.logger.info.assert_called_with(
            "Pinecone vector adapter initialized successfully"
        )

    @pytest.mark.asyncio
    async def test_init_create_index(self, pinecone_adapter, mock_pinecone_client):
        """Test initialization with index creation."""
        mock_pinecone_client.describe_index.side_effect = Exception("Index not found")
        pinecone_adapter._client = mock_pinecone_client

        with patch.object(pinecone_adapter, "_create_default_index") as mock_create:
            await pinecone_adapter.init()

            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_search(self, pinecone_adapter, mock_pinecone_client):
        """Test vector search."""
        mock_index = mock_pinecone_client.Index.return_value
        pinecone_adapter._client = mock_pinecone_client

        query_vector = [0.1, 0.2, 0.3]
        results = await pinecone_adapter.search(
            collection="test", query_vector=query_vector, limit=5, include_vectors=True
        )

        mock_index.query.assert_called_once_with(
            vector=query_vector,
            top_k=5,
            include_metadata=True,
            include_values=True,
            namespace="test",
        )

        assert len(results) == 1
        assert isinstance(results[0], VectorSearchResult)
        assert results[0].id == "doc1"
        assert results[0].score == 0.95
        assert results[0].metadata == {"title": "Test Document"}
        assert results[0].vector == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_search_with_filter(self, pinecone_adapter, mock_pinecone_client):
        """Test vector search with metadata filter."""
        mock_index = mock_pinecone_client.Index.return_value
        pinecone_adapter._client = mock_pinecone_client

        query_vector = [0.1, 0.2, 0.3]
        filter_expr = {"category": "test"}

        await pinecone_adapter.search(
            collection="test", query_vector=query_vector, filter_expr=filter_expr
        )

        mock_index.query.assert_called_once_with(
            vector=query_vector,
            top_k=10,
            include_metadata=True,
            include_values=False,
            namespace="test",
            filter=filter_expr,
        )

    @pytest.mark.asyncio
    async def test_upsert(self, pinecone_adapter, mock_pinecone_client):
        """Test document upsert."""
        mock_index = mock_pinecone_client.Index.return_value
        pinecone_adapter._client = mock_pinecone_client

        documents = [
            VectorDocument(
                id="doc1", vector=[0.1, 0.2, 0.3], metadata={"title": "Test Document"}
            )
        ]

        ids = await pinecone_adapter.upsert("test", documents)

        expected_vectors = [
            {
                "id": "doc1",
                "values": [0.1, 0.2, 0.3],
                "metadata": {"title": "Test Document"},
            }
        ]

        mock_index.upsert.assert_called_once_with(
            vectors=expected_vectors, namespace="test"
        )
        assert ids == ["doc1"]

    @pytest.mark.asyncio
    async def test_upsert_without_id(self, pinecone_adapter, mock_pinecone_client):
        """Test document upsert without ID."""
        mock_index = mock_pinecone_client.Index.return_value
        pinecone_adapter._client = mock_pinecone_client

        documents = [
            VectorDocument(vector=[0.1, 0.2, 0.3], metadata={"title": "Test Document"})
        ]

        ids = await pinecone_adapter.upsert("test", documents)

        # Should generate an ID
        assert len(ids) == 1
        assert ids[0].startswith("vec_")

        # Check the upsert call
        call_args = mock_index.upsert.call_args
        assert call_args[1]["namespace"] == "test"
        vectors = call_args[1]["vectors"]
        assert len(vectors) == 1
        assert vectors[0]["id"] == ids[0]

    @pytest.mark.asyncio
    async def test_delete(self, pinecone_adapter, mock_pinecone_client):
        """Test document deletion."""
        mock_index = mock_pinecone_client.Index.return_value
        pinecone_adapter._client = mock_pinecone_client

        result = await pinecone_adapter.delete("test", ["doc1", "doc2"])

        mock_index.delete.assert_called_once_with(
            ids=["doc1", "doc2"], namespace="test"
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_get(self, pinecone_adapter, mock_pinecone_client):
        """Test document retrieval."""
        mock_index = mock_pinecone_client.Index.return_value
        pinecone_adapter._client = mock_pinecone_client

        documents = await pinecone_adapter.get("test", ["doc1"], include_vectors=True)

        mock_index.fetch.assert_called_once_with(
            ids=["doc1"], include_metadata=True, include_values=True, namespace="test"
        )

        assert len(documents) == 1
        assert isinstance(documents[0], VectorDocument)
        assert documents[0].id == "doc1"
        assert documents[0].vector == [0.1, 0.2, 0.3]
        assert documents[0].metadata == {"title": "Test Document"}

    @pytest.mark.asyncio
    async def test_count(self, pinecone_adapter, mock_pinecone_client):
        """Test document count."""
        mock_index = mock_pinecone_client.Index.return_value
        pinecone_adapter._client = mock_pinecone_client

        count = await pinecone_adapter.count("test")

        mock_index.describe_index_stats.assert_called_once_with()
        assert count == 5  # From namespace 'test'

    @pytest.mark.asyncio
    async def test_count_default_namespace(
        self, pinecone_adapter, mock_pinecone_client
    ):
        """Test document count for default namespace."""
        pinecone_adapter._client = mock_pinecone_client

        count = await pinecone_adapter.count("default")

        assert count == 5  # 10 total - 5 in 'test' namespace = 5 in default

    @pytest.mark.asyncio
    async def test_create_collection(self, pinecone_adapter):
        """Test collection creation."""
        # In Pinecone, this just logs a message
        result = await pinecone_adapter.create_collection("test", 768)
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_collection(self, pinecone_adapter, mock_pinecone_client):
        """Test collection deletion."""
        mock_index = mock_pinecone_client.Index.return_value
        pinecone_adapter._client = mock_pinecone_client

        result = await pinecone_adapter.delete_collection("test")

        mock_index.delete.assert_called_once_with(delete_all=True, namespace="test")
        assert result is True

    @pytest.mark.asyncio
    async def test_list_collections(self, pinecone_adapter, mock_pinecone_client):
        """Test listing collections."""
        mock_index = mock_pinecone_client.Index.return_value
        pinecone_adapter._client = mock_pinecone_client

        collections = await pinecone_adapter.list_collections()

        mock_index.describe_index_stats.assert_called_once()
        assert "test" in collections

    def test_has_capability(self, pinecone_adapter):
        """Test capability checking."""
        assert pinecone_adapter.has_capability("vector_search")
        assert pinecone_adapter.has_capability("batch_operations")
        assert pinecone_adapter.has_capability("metadata_filtering")
        assert pinecone_adapter.has_capability("indexing")
        assert not pinecone_adapter.has_capability("unsupported_feature")

    @pytest.mark.asyncio
    async def test_search_error_handling(self, pinecone_adapter, mock_pinecone_client):
        """Test search error handling."""
        mock_index = mock_pinecone_client.Index.return_value
        mock_index.query.side_effect = Exception("Search failed")
        pinecone_adapter._client = mock_pinecone_client

        results = await pinecone_adapter.search("test", [0.1, 0.2, 0.3])

        assert results == []
        pinecone_adapter.logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_upsert_error_handling(self, pinecone_adapter, mock_pinecone_client):
        """Test upsert error handling."""
        mock_index = mock_pinecone_client.Index.return_value
        mock_index.upsert.side_effect = Exception("Upsert failed")
        pinecone_adapter._client = mock_pinecone_client

        documents = [VectorDocument(vector=[0.1, 0.2, 0.3])]
        ids = await pinecone_adapter.upsert("test", documents)

        assert ids == []
        pinecone_adapter.logger.error.assert_called()
