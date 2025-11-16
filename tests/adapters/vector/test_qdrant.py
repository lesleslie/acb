"""Tests for Qdrant vector adapter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from acb.adapters.vector._base import VectorDocument, VectorSearchResult
from acb.adapters.vector.qdrant import Vector, VectorSettings


class TestVectorSettings:
    """Test Qdrant VectorSettings."""

    @patch("acb.depends.depends.get")
    def test_vector_settings_defaults(self, mock_depends):
        """Test VectorSettings with default values."""
        mock_config = MagicMock()
        mock_depends.return_value = mock_config

        settings = VectorSettings()

        assert settings.url == "http://localhost:6333"
        assert settings.api_key is None
        assert settings.grpc_port is None
        assert settings.prefer_grpc is True
        assert settings.timeout == 30.0
        assert settings.default_collection == "documents"
        assert settings.on_disk_vectors is False
        assert settings.enable_quantization is False

    @patch("acb.depends.depends.get")
    def test_vector_settings_custom_values(self, mock_depends):
        """Test VectorSettings with custom values."""
        mock_config = MagicMock()
        mock_depends.return_value = mock_config

        settings = VectorSettings(
            url="https://my-cluster.qdrant.cloud:6333",
            api_key="test-api-key",
            grpc_port=6334,
            prefer_grpc=False,
            timeout=60.0,
            default_collection="custom_docs",
            on_disk_vectors=True,
            enable_quantization=True,
        )

        assert settings.url == "https://my-cluster.qdrant.cloud:6333"
        assert settings.api_key.get_secret_value() == "test-api-key"
        assert settings.grpc_port == 6334
        assert settings.prefer_grpc is False
        assert settings.timeout == 60.0
        assert settings.default_collection == "custom_docs"
        assert settings.on_disk_vectors is True
        assert settings.enable_quantization is True


class TestQdrantVector:
    """Test Qdrant vector adapter implementation."""

    @pytest.fixture
    def mock_qdrant_client(self):
        """Mock Qdrant client."""
        mock_client = AsyncMock()

        # Mock search response
        mock_point = MagicMock()
        mock_point.id = "doc1"
        mock_point.score = 0.95
        mock_point.payload = {"title": "Test Document"}
        mock_point.vector = [0.1, 0.2, 0.3]

        mock_client.search.return_value = [mock_point]

        # Mock collections response
        mock_collection_info = MagicMock()
        mock_collection_info.name = "documents"
        mock_collections_response = MagicMock()
        mock_collections_response.collections = [mock_collection_info]
        mock_client.get_collections.return_value = mock_collections_response

        # Mock upsert response
        mock_operation_info = MagicMock()
        mock_operation_info.status.name = "COMPLETED"
        mock_client.upsert.return_value = mock_operation_info
        mock_client.delete.return_value = mock_operation_info

        # Mock retrieve response
        mock_client.retrieve.return_value = [mock_point]

        # Mock count response
        mock_count_result = MagicMock()
        mock_count_result.count = 10
        mock_client.count.return_value = mock_count_result

        # Mock scroll response
        mock_client.scroll.return_value = ([mock_point], "next_offset")

        # Mock cluster info
        mock_client.get_cluster_info.return_value = {"status": "green"}

        return mock_client

    @pytest.fixture
    def mock_vector_settings(self):
        """Mock Qdrant vector settings."""
        with patch("acb.depends.depends.get") as mock_depends:
            mock_config = MagicMock()
            mock_depends.return_value = mock_config

            settings = VectorSettings()
            return settings

    @pytest.fixture
    def qdrant_adapter(self, mock_vector_settings):
        """Qdrant vector adapter instance."""
        with patch.object(Vector, "config") as mock_config:
            mock_config.vector = mock_vector_settings
            adapter = Vector()
            adapter.logger = MagicMock()
            return adapter

    @pytest.mark.asyncio
    async def test_create_client(self, qdrant_adapter, mock_qdrant_client):
        """Test Qdrant client creation."""
        with patch("acb.adapters.vector.qdrant.AsyncQdrantClient") as mock_client_class:
            mock_client_class.return_value = mock_qdrant_client

            client = await qdrant_adapter._create_client()

            mock_client_class.assert_called_once_with(
                url="http://localhost:6333", timeout=30.0, prefer_grpc=True
            )
            assert client == mock_qdrant_client

    @pytest.mark.asyncio
    async def test_create_client_with_auth(self, qdrant_adapter, mock_qdrant_client):
        """Test Qdrant client creation with authentication."""
        qdrant_adapter.config.vector.api_key = MagicMock()
        qdrant_adapter.config.vector.api_key.get_secret_value.return_value = "test-key"
        qdrant_adapter.config.vector.grpc_port = 6334
        qdrant_adapter.config.vector.https = True

        with patch("acb.adapters.vector.qdrant.AsyncQdrantClient") as mock_client_class:
            mock_client_class.return_value = mock_qdrant_client

            await qdrant_adapter._create_client()

            mock_client_class.assert_called_once_with(
                url="http://localhost:6333",
                timeout=30.0,
                prefer_grpc=True,
                api_key="test-key",
                grpc_port=6334,
                https=True,
            )

    @pytest.mark.asyncio
    async def test_init(self, qdrant_adapter, mock_qdrant_client):
        """Test initialization."""
        qdrant_adapter._client = mock_qdrant_client

        await qdrant_adapter.init()

        mock_qdrant_client.get_cluster_info.assert_called_once()
        qdrant_adapter.logger.info.assert_called_with(
            "Qdrant vector adapter initialized successfully"
        )

    @pytest.mark.asyncio
    async def test_ensure_collection_exists_existing(
        self, qdrant_adapter, mock_qdrant_client
    ):
        """Test ensuring collection exists when it already exists."""
        qdrant_adapter._client = mock_qdrant_client

        result = await qdrant_adapter._ensure_collection_exists("documents")

        assert result is True
        mock_qdrant_client.get_collections.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_collection_exists_create(
        self, qdrant_adapter, mock_qdrant_client
    ):
        """Test creating a new collection."""
        # Mock empty collections response
        mock_collections_response = MagicMock()
        mock_collections_response.collections = []
        mock_qdrant_client.get_collections.return_value = mock_collections_response
        qdrant_adapter._client = mock_qdrant_client

        with (
            patch("acb.adapters.vector.qdrant.VectorParams"),
            patch("acb.adapters.vector.qdrant.Distance"),
            patch("acb.adapters.vector.qdrant.HnswConfigDiff"),
        ):
            result = await qdrant_adapter._ensure_collection_exists(
                "new_collection", 768
            )

            assert result is True
            mock_qdrant_client.create_collection.assert_called_once()

    @pytest.mark.asyncio
    async def test_search(self, qdrant_adapter, mock_qdrant_client):
        """Test vector search."""
        qdrant_adapter._client = mock_qdrant_client

        query_vector = [0.1, 0.2, 0.3]
        results = await qdrant_adapter.search(
            collection="documents",
            query_vector=query_vector,
            limit=5,
            include_vectors=True,
        )

        mock_qdrant_client.search.assert_called_once_with(
            collection_name="documents",
            query_vector=query_vector,
            limit=5,
            query_filter=None,
            with_payload=True,
            with_vectors=True,
            score_threshold=None,
        )

        assert len(results) == 1
        assert isinstance(results[0], VectorSearchResult)
        assert results[0].id == "doc1"
        assert results[0].score == 0.95
        assert results[0].metadata == {"title": "Test Document"}
        assert results[0].vector == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_search_with_filter(self, qdrant_adapter, mock_qdrant_client):
        """Test vector search with metadata filter."""
        qdrant_adapter._client = mock_qdrant_client

        query_vector = [0.1, 0.2, 0.3]
        filter_expr = {"category": "test"}

        with patch.object(qdrant_adapter, "_build_qdrant_filter") as mock_build_filter:
            mock_filter = MagicMock()
            mock_build_filter.return_value = mock_filter

            await qdrant_adapter.search(
                collection="documents",
                query_vector=query_vector,
                filter_expr=filter_expr,
            )

            mock_build_filter.assert_called_once_with(filter_expr)
            mock_qdrant_client.search.assert_called_once_with(
                collection_name="documents",
                query_vector=query_vector,
                limit=10,
                query_filter=mock_filter,
                with_payload=True,
                with_vectors=False,
                score_threshold=None,
            )

    @pytest.mark.asyncio
    async def test_upsert(self, qdrant_adapter, mock_qdrant_client):
        """Test document upsert."""
        qdrant_adapter._client = mock_qdrant_client

        documents = [
            VectorDocument(
                id="doc1", vector=[0.1, 0.2, 0.3], metadata={"title": "Test Document"}
            )
        ]

        with patch.object(qdrant_adapter, "_ensure_collection_exists") as mock_ensure:
            mock_ensure.return_value = True

            ids = await qdrant_adapter.upsert("documents", documents)

            mock_ensure.assert_called_once_with("documents", 3)
            mock_qdrant_client.upsert.assert_called_once()
            assert ids == ["doc1"]

    @pytest.mark.asyncio
    async def test_upsert_without_id(self, qdrant_adapter, mock_qdrant_client):
        """Test document upsert without ID."""
        qdrant_adapter._client = mock_qdrant_client

        documents = [
            VectorDocument(vector=[0.1, 0.2, 0.3], metadata={"title": "Test Document"})
        ]

        with patch.object(qdrant_adapter, "_ensure_collection_exists") as mock_ensure:
            mock_ensure.return_value = True

            ids = await qdrant_adapter.upsert("documents", documents)

            # Should generate a UUID
            assert len(ids) == 1
            assert len(ids[0]) == 36  # UUID length

    @pytest.mark.asyncio
    async def test_delete(self, qdrant_adapter, mock_qdrant_client):
        """Test document deletion."""
        qdrant_adapter._client = mock_qdrant_client

        with patch("acb.adapters.vector.qdrant.PointIdsList") as mock_point_ids:
            result = await qdrant_adapter.delete("documents", ["doc1", "doc2"])

            mock_point_ids.assert_called_once_with(points=["doc1", "doc2"])
            mock_qdrant_client.delete.assert_called_once()
            assert result is True

    @pytest.mark.asyncio
    async def test_get(self, qdrant_adapter, mock_qdrant_client):
        """Test document retrieval."""
        qdrant_adapter._client = mock_qdrant_client

        documents = await qdrant_adapter.get(
            "documents", ["doc1"], include_vectors=True
        )

        mock_qdrant_client.retrieve.assert_called_once_with(
            collection_name="documents",
            ids=["doc1"],
            with_payload=True,
            with_vectors=True,
        )

        assert len(documents) == 1
        assert isinstance(documents[0], VectorDocument)
        assert documents[0].id == "doc1"
        assert documents[0].vector == [0.1, 0.2, 0.3]
        assert documents[0].metadata == {"title": "Test Document"}

    @pytest.mark.asyncio
    async def test_count(self, qdrant_adapter, mock_qdrant_client):
        """Test document count."""
        qdrant_adapter._client = mock_qdrant_client

        count = await qdrant_adapter.count("documents")

        mock_qdrant_client.count.assert_called_once_with(
            collection_name="documents", count_filter=None
        )
        assert count == 10

    @pytest.mark.asyncio
    async def test_count_with_filter(self, qdrant_adapter, mock_qdrant_client):
        """Test document count with filter."""
        qdrant_adapter._client = mock_qdrant_client

        filter_expr = {"category": "test"}

        with patch.object(qdrant_adapter, "_build_qdrant_filter") as mock_build_filter:
            mock_filter = MagicMock()
            mock_build_filter.return_value = mock_filter

            await qdrant_adapter.count("documents", filter_expr)

            mock_build_filter.assert_called_once_with(filter_expr)
            mock_qdrant_client.count.assert_called_once_with(
                collection_name="documents", count_filter=mock_filter
            )

    @pytest.mark.asyncio
    async def test_create_collection(self, qdrant_adapter):
        """Test collection creation."""
        with patch.object(qdrant_adapter, "_ensure_collection_exists") as mock_ensure:
            mock_ensure.return_value = True

            result = await qdrant_adapter.create_collection("test", 768, "euclidean")

            mock_ensure.assert_called_once_with("test", 768, "euclidean")
            assert result is True

    @pytest.mark.asyncio
    async def test_delete_collection(self, qdrant_adapter, mock_qdrant_client):
        """Test collection deletion."""
        qdrant_adapter._client = mock_qdrant_client

        result = await qdrant_adapter.delete_collection("test")

        mock_qdrant_client.delete_collection.assert_called_once_with(
            collection_name="test"
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_list_collections(self, qdrant_adapter, mock_qdrant_client):
        """Test listing collections."""
        qdrant_adapter._client = mock_qdrant_client

        collections = await qdrant_adapter.list_collections()

        mock_qdrant_client.get_collections.assert_called_once()
        assert collections == ["documents"]

    @pytest.mark.asyncio
    async def test_scroll(self, qdrant_adapter, mock_qdrant_client):
        """Test scrolling through documents."""
        qdrant_adapter._client = mock_qdrant_client

        documents, next_offset = await qdrant_adapter.scroll(
            collection="documents", limit=100, include_vectors=True
        )

        mock_qdrant_client.scroll.assert_called_once_with(
            collection_name="documents",
            limit=100,
            offset=None,
            scroll_filter=None,
            with_payload=True,
            with_vectors=True,
        )

        assert len(documents) == 1
        assert isinstance(documents[0], VectorDocument)
        assert documents[0].id == "doc1"
        assert next_offset == "next_offset"

    def test_build_qdrant_filter(self, qdrant_adapter):
        """Test building Qdrant filters."""
        with (
            patch("acb.adapters.vector.qdrant.Filter") as mock_filter,
            patch("acb.adapters.vector.qdrant.FieldCondition") as mock_field_condition,
            patch("acb.adapters.vector.qdrant.MatchValue"),
            patch("acb.adapters.vector.qdrant.MatchAny"),
        ):
            filter_expr = {
                "category": "test",
                "status": "active",
                "tags": ["tag1", "tag2"],
            }

            qdrant_adapter._build_qdrant_filter(filter_expr)

            # Should create FieldConditions for each filter
            assert mock_field_condition.call_count == 3
            # Should create Filter with must conditions
            mock_filter.assert_called_once()

    def test_has_capability(self, qdrant_adapter):
        """Test capability checking."""
        assert qdrant_adapter.has_capability("vector_search")
        assert qdrant_adapter.has_capability("batch_operations")
        assert qdrant_adapter.has_capability("metadata_filtering")
        assert qdrant_adapter.has_capability("indexing")
        assert qdrant_adapter.has_capability("scroll")
        assert qdrant_adapter.has_capability("quantization")
        assert not qdrant_adapter.has_capability("unsupported_feature")

    @pytest.mark.asyncio
    async def test_search_error_handling(self, qdrant_adapter, mock_qdrant_client):
        """Test search error handling."""
        mock_qdrant_client.search.side_effect = Exception("Search failed")
        qdrant_adapter._client = mock_qdrant_client

        results = await qdrant_adapter.search("documents", [0.1, 0.2, 0.3])

        assert results == []
        qdrant_adapter.logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_upsert_error_handling(self, qdrant_adapter, mock_qdrant_client):
        """Test upsert error handling."""
        mock_qdrant_client.upsert.side_effect = Exception("Upsert failed")
        qdrant_adapter._client = mock_qdrant_client

        documents = [VectorDocument(vector=[0.1, 0.2, 0.3])]

        with patch.object(qdrant_adapter, "_ensure_collection_exists") as mock_ensure:
            mock_ensure.return_value = True

            ids = await qdrant_adapter.upsert("documents", documents)

            assert ids == []
            qdrant_adapter.logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_upsert_batch_failure_handling(
        self, qdrant_adapter, mock_qdrant_client
    ):
        """Test upsert batch failure handling."""
        # Mock a failed operation
        mock_operation_info = MagicMock()
        mock_operation_info.status.name = "FAILED"
        mock_qdrant_client.upsert.return_value = mock_operation_info
        qdrant_adapter._client = mock_qdrant_client

        documents = [VectorDocument(id="doc1", vector=[0.1, 0.2, 0.3])]

        with patch.object(qdrant_adapter, "_ensure_collection_exists") as mock_ensure:
            mock_ensure.return_value = True

            ids = await qdrant_adapter.upsert("documents", documents)

            # Should still return IDs even if operation reports failure
            assert ids == ["doc1"]
            qdrant_adapter.logger.warning.assert_called()
