"""Tests for Weaviate vector adapter."""

from unittest.mock import MagicMock, patch

import pytest

from acb.adapters.vector._base import VectorDocument, VectorSearchResult
from acb.adapters.vector.weaviate import Vector, VectorSettings


class TestVectorSettings:
    """Test Weaviate VectorSettings."""

    @patch("acb.depends.depends.get")
    def test_vector_settings_defaults(self, mock_depends):
        """Test VectorSettings with default values."""
        mock_config = MagicMock()
        mock_depends.return_value = mock_config

        settings = VectorSettings()

        assert settings.url == "http://localhost:8080"
        assert settings.api_key is None
        assert settings.use_auth is False
        assert settings.default_class == "Document"
        assert settings.vectorizer == "none"
        assert settings.query_timeout == 30.0
        assert settings.auto_create_schema is True
        assert settings.distance_metric == "cosine"

    @patch("acb.depends.depends.get")
    def test_vector_settings_custom_values(self, mock_depends):
        """Test VectorSettings with custom values."""
        mock_config = MagicMock()
        mock_depends.return_value = mock_config

        settings = VectorSettings(
            url="https://custom-cluster.weaviate.cloud",
            api_key="test-api-key",
            use_auth=True,
            default_class="CustomDocument",
            vectorizer="text2vec-openai",
            distance_metric="dot",
        )

        assert settings.url == "https://custom-cluster.weaviate.cloud"
        assert settings.api_key.get_secret_value() == "test-api-key"
        assert settings.use_auth is True
        assert settings.default_class == "CustomDocument"
        assert settings.vectorizer == "text2vec-openai"
        assert settings.distance_metric == "dot"


class TestWeaviateVector:
    """Test Weaviate vector adapter implementation."""

    @pytest.fixture
    def mock_weaviate_client(self):
        """Mock Weaviate client."""
        mock_client = MagicMock()
        mock_collection = MagicMock()

        # Mock search response
        mock_obj = MagicMock()
        mock_obj.uuid = "doc1"
        mock_obj.properties = {"title": "Test Document"}
        mock_obj.metadata = MagicMock()
        mock_obj.metadata.distance = 0.05
        mock_obj.vector = {"default": [0.1, 0.2, 0.3]}

        mock_collection.query.near_vector.return_value.objects = [mock_obj]
        mock_collection.query.bm25.return_value.objects = [mock_obj]
        mock_collection.query.fetch_object_by_id.return_value = mock_obj

        # Mock batch operations
        mock_batch_context = MagicMock()
        mock_collection.batch.dynamic.return_value.__enter__.return_value = (
            mock_batch_context
        )
        mock_collection.batch.dynamic.return_value.__exit__.return_value = None

        # Mock aggregate response
        mock_aggregate_result = MagicMock()
        mock_aggregate_result.total_count = 10
        mock_collection.aggregate.over_all.return_value = mock_aggregate_result

        # Mock collections list
        mock_col_info = MagicMock()
        mock_col_info.name = "Document"
        mock_client.collections.list_all.return_value = [mock_col_info]
        mock_client.collections.get.return_value = mock_collection
        mock_client.collections.create.return_value = None
        mock_client.collections.delete.return_value = None

        mock_client.is_ready.return_value = True

        return mock_client

    @pytest.fixture
    def mock_vector_settings(self):
        """Mock Weaviate vector settings."""
        with patch("acb.depends.depends.get") as mock_depends:
            mock_config = MagicMock()
            mock_depends.return_value = mock_config

            settings = VectorSettings()
            return settings

    @pytest.fixture
    def weaviate_adapter(self, mock_vector_settings):
        """Weaviate vector adapter instance."""
        with patch.object(Vector, "config") as mock_config:
            mock_config.vector = mock_vector_settings
            adapter = Vector()
            adapter.logger = MagicMock()
            return adapter

    @pytest.mark.asyncio
    async def test_create_client(self, weaviate_adapter, mock_weaviate_client):
        """Test Weaviate client creation."""
        with patch("acb.adapters.vector.weaviate.weaviate") as mock_weaviate:
            mock_weaviate.connect_to_custom.return_value = mock_weaviate_client

            client = await weaviate_adapter._create_client()

            mock_weaviate.connect_to_custom.assert_called_once_with(
                url="http://localhost:8080", startup_period=60.0
            )
            assert client == mock_weaviate_client

    @pytest.mark.asyncio
    async def test_create_client_with_auth(
        self, weaviate_adapter, mock_weaviate_client
    ):
        """Test Weaviate client creation with authentication."""
        weaviate_adapter.config.vector.use_auth = True
        weaviate_adapter.config.vector.api_key = MagicMock()
        weaviate_adapter.config.vector.api_key.get_secret_value.return_value = (
            "test-key"
        )

        with patch("acb.adapters.vector.weaviate.weaviate") as mock_weaviate:
            mock_weaviate.connect_to_custom.return_value = mock_weaviate_client

            await weaviate_adapter._create_client()

            # Check that auth_client_secret was provided
            call_args = mock_weaviate.connect_to_custom.call_args[1]
            assert "auth_client_secret" in call_args

    @pytest.mark.asyncio
    async def test_init(self, weaviate_adapter, mock_weaviate_client):
        """Test initialization."""
        weaviate_adapter._client = mock_weaviate_client

        await weaviate_adapter.init()

        mock_weaviate_client.is_ready.assert_called_once()
        weaviate_adapter.logger.info.assert_called_with(
            "Weaviate vector adapter initialized successfully"
        )

    def test_collection_to_class_name(self, weaviate_adapter):
        """Test collection name to class name conversion."""
        assert weaviate_adapter._collection_to_class_name("document") == "Document"
        assert weaviate_adapter._collection_to_class_name("") == "Document"
        assert (
            weaviate_adapter._collection_to_class_name("myCollection") == "Mycollection"
        )

    @pytest.mark.asyncio
    async def test_ensure_class_exists_existing(
        self, weaviate_adapter, mock_weaviate_client
    ):
        """Test ensuring class exists when it already exists."""
        weaviate_adapter._client = mock_weaviate_client

        result = await weaviate_adapter._ensure_class_exists("Document")

        assert result is True
        mock_weaviate_client.collections.list_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_search(self, weaviate_adapter, mock_weaviate_client):
        """Test vector search."""
        weaviate_adapter._client = mock_weaviate_client

        query_vector = [0.1, 0.2, 0.3]
        results = await weaviate_adapter.search(
            collection="document",
            query_vector=query_vector,
            limit=5,
            include_vectors=True,
        )

        mock_collection = mock_weaviate_client.collections.get.return_value
        mock_collection.query.near_vector.assert_called_once_with(
            near_vector=query_vector, limit=5, return_metadata=["distance", "certainty"]
        )

        assert len(results) == 1
        assert isinstance(results[0], VectorSearchResult)
        assert results[0].id == "doc1"
        assert results[0].score == 0.95  # 1.0 - 0.05 distance
        assert results[0].metadata == {"title": "Test Document"}
        assert results[0].vector == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_search_with_filter(self, weaviate_adapter, mock_weaviate_client):
        """Test vector search with metadata filter."""
        weaviate_adapter._client = mock_weaviate_client

        query_vector = [0.1, 0.2, 0.3]
        filter_expr = {"category": "test"}

        with patch.object(weaviate_adapter, "_build_where_filter") as mock_build_filter:
            mock_filter = MagicMock()
            mock_build_filter.return_value = mock_filter

            await weaviate_adapter.search(
                collection="document",
                query_vector=query_vector,
                filter_expr=filter_expr,
            )

            mock_build_filter.assert_called_once_with(filter_expr)

    @pytest.mark.asyncio
    async def test_upsert(self, weaviate_adapter, mock_weaviate_client):
        """Test document upsert."""
        weaviate_adapter._client = mock_weaviate_client

        documents = [
            VectorDocument(
                id="doc1", vector=[0.1, 0.2, 0.3], metadata={"title": "Test Document"}
            )
        ]

        with patch.object(weaviate_adapter, "_ensure_class_exists") as mock_ensure:
            mock_ensure.return_value = True

            ids = await weaviate_adapter.upsert("document", documents)

            mock_ensure.assert_called_once_with("Document", 3)
            assert ids == ["doc1"]

    @pytest.mark.asyncio
    async def test_upsert_without_id(self, weaviate_adapter, mock_weaviate_client):
        """Test document upsert without ID."""
        weaviate_adapter._client = mock_weaviate_client

        documents = [
            VectorDocument(vector=[0.1, 0.2, 0.3], metadata={"title": "Test Document"})
        ]

        with patch.object(weaviate_adapter, "_ensure_class_exists") as mock_ensure:
            mock_ensure.return_value = True

            ids = await weaviate_adapter.upsert("document", documents)

            # Should generate a UUID
            assert len(ids) == 1
            assert len(ids[0]) == 36  # UUID length

    @pytest.mark.asyncio
    async def test_delete(self, weaviate_adapter, mock_weaviate_client):
        """Test document deletion."""
        weaviate_adapter._client = mock_weaviate_client
        mock_collection = mock_weaviate_client.collections.get.return_value

        result = await weaviate_adapter.delete("document", ["doc1", "doc2"])

        # Should call delete_by_id for each document
        assert mock_collection.data.delete_by_id.call_count == 2
        assert result is True

    @pytest.mark.asyncio
    async def test_get(self, weaviate_adapter, mock_weaviate_client):
        """Test document retrieval."""
        weaviate_adapter._client = mock_weaviate_client
        mock_collection = mock_weaviate_client.collections.get.return_value

        documents = await weaviate_adapter.get(
            "document", ["doc1"], include_vectors=True
        )

        mock_collection.query.fetch_object_by_id.assert_called_once_with(
            "doc1", include_vector=True
        )

        assert len(documents) == 1
        assert isinstance(documents[0], VectorDocument)
        assert documents[0].id == "doc1"
        assert documents[0].vector == [0.1, 0.2, 0.3]
        assert documents[0].metadata == {"title": "Test Document"}

    @pytest.mark.asyncio
    async def test_count(self, weaviate_adapter, mock_weaviate_client):
        """Test document count."""
        weaviate_adapter._client = mock_weaviate_client
        mock_collection = mock_weaviate_client.collections.get.return_value

        count = await weaviate_adapter.count("document")

        mock_collection.aggregate.over_all.assert_called_once_with(total_count=True)
        assert count == 10

    @pytest.mark.asyncio
    async def test_create_collection(self, weaviate_adapter):
        """Test collection creation."""
        with patch.object(weaviate_adapter, "_ensure_class_exists") as mock_ensure:
            mock_ensure.return_value = True

            result = await weaviate_adapter.create_collection("test", 768)

            mock_ensure.assert_called_once_with("Test", 768)
            assert result is True

    @pytest.mark.asyncio
    async def test_delete_collection(self, weaviate_adapter, mock_weaviate_client):
        """Test collection deletion."""
        weaviate_adapter._client = mock_weaviate_client

        result = await weaviate_adapter.delete_collection("test")

        mock_weaviate_client.collections.delete.assert_called_once_with("Test")
        assert result is True

    @pytest.mark.asyncio
    async def test_list_collections(self, weaviate_adapter, mock_weaviate_client):
        """Test listing collections."""
        weaviate_adapter._client = mock_weaviate_client

        collections = await weaviate_adapter.list_collections()

        mock_weaviate_client.collections.list_all.assert_called_once()
        assert collections == ["document"]

    @pytest.mark.asyncio
    async def test_text_search(self, weaviate_adapter, mock_weaviate_client):
        """Test text-based search."""
        weaviate_adapter._client = mock_weaviate_client
        mock_collection = mock_weaviate_client.collections.get.return_value

        # Mock BM25 result
        mock_obj = MagicMock()
        mock_obj.uuid = "doc1"
        mock_obj.properties = {"title": "Test Document"}
        mock_obj.metadata = MagicMock()
        mock_obj.metadata.score = 0.85

        mock_collection.query.bm25.return_value.objects = [mock_obj]

        results = await weaviate_adapter.text_search(
            collection="document", query_text="test query", limit=5
        )

        mock_collection.query.bm25.assert_called_once_with(
            query="test query", limit=5, return_metadata=["score"]
        )

        assert len(results) == 1
        assert results[0].id == "doc1"
        assert results[0].score == 0.85
        assert results[0].vector is None  # Text search doesn't return vectors

    def test_has_capability(self, weaviate_adapter):
        """Test capability checking."""
        assert weaviate_adapter.has_capability("vector_search")
        assert weaviate_adapter.has_capability("text_search")
        assert weaviate_adapter.has_capability("hybrid_search")
        assert weaviate_adapter.has_capability("batch_operations")
        assert weaviate_adapter.has_capability("metadata_filtering")
        assert not weaviate_adapter.has_capability("unsupported_feature")

    @pytest.mark.asyncio
    async def test_search_error_handling(self, weaviate_adapter, mock_weaviate_client):
        """Test search error handling."""
        mock_collection = mock_weaviate_client.collections.get.return_value
        mock_collection.query.near_vector.side_effect = Exception("Search failed")
        weaviate_adapter._client = mock_weaviate_client

        results = await weaviate_adapter.search("document", [0.1, 0.2, 0.3])

        assert results == []
        weaviate_adapter.logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_upsert_error_handling(self, weaviate_adapter, mock_weaviate_client):
        """Test upsert error handling."""
        mock_weaviate_client.collections.get.side_effect = Exception("Upsert failed")
        weaviate_adapter._client = mock_weaviate_client

        documents = [VectorDocument(vector=[0.1, 0.2, 0.3])]

        with patch.object(weaviate_adapter, "_ensure_class_exists") as mock_ensure:
            mock_ensure.return_value = True

            ids = await weaviate_adapter.upsert("document", documents)

            assert ids == []
            weaviate_adapter.logger.error.assert_called()

    def test_build_where_filter(self, weaviate_adapter):
        """Test building Weaviate where filters."""
        with patch("acb.adapters.vector.weaviate.Filter") as mock_filter:
            mock_property_filter = MagicMock()
            mock_filter.by_property.return_value.equal.return_value = (
                mock_property_filter
            )

            filter_expr = {"category": "test", "status": "active"}
            weaviate_adapter._build_where_filter(filter_expr)

            # Should create filters for each condition
            assert mock_filter.by_property.call_count == 2
