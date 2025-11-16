"""Tests for the ACB vector base module."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic import SecretStr

from acb.adapters.vector._base import (
    VectorBase,
    VectorBaseSettings,
    VectorCollection,
    VectorDocument,
    VectorSearchResult,
)
from acb.config import AppSettings, Config, DebugSettings


class TestVectorSearchResult:
    """Test the VectorSearchResult model."""

    def test_vector_search_result_defaults(self) -> None:
        """Test VectorSearchResult default values."""
        result = VectorSearchResult(id="test-id", score=0.95)

        assert result.id == "test-id"
        assert result.score == 0.95
        assert result.metadata == {}
        assert result.vector is None

    def test_vector_search_result_with_values(self) -> None:
        """Test VectorSearchResult with custom values."""
        result = VectorSearchResult(
            id="test-id", score=0.85, metadata={"key": "value"}, vector=[1.0, 2.0, 3.0]
        )

        assert result.id == "test-id"
        assert result.score == 0.85
        assert result.metadata == {"key": "value"}
        assert result.vector == [1.0, 2.0, 3.0]


class TestVectorDocument:
    """Test the VectorDocument model."""

    def test_vector_document_defaults(self) -> None:
        """Test VectorDocument default values."""
        doc = VectorDocument(id="test-id", vector=[1.0, 2.0, 3.0])

        assert doc.id == "test-id"
        assert doc.vector == [1.0, 2.0, 3.0]
        assert doc.metadata == {}

    def test_vector_document_with_none_id(self) -> None:
        """Test VectorDocument with None id."""
        doc = VectorDocument(vector=[1.0, 2.0, 3.0])

        assert doc.id is None
        assert doc.vector == [1.0, 2.0, 3.0]
        assert doc.metadata == {}

    def test_vector_document_with_metadata(self) -> None:
        """Test VectorDocument with metadata."""
        doc = VectorDocument(
            id="test-id",
            vector=[1.0, 2.0, 3.0],
            metadata={"key": "value", "category": "test"},
        )

        assert doc.id == "test-id"
        assert doc.vector == [1.0, 2.0, 3.0]
        assert doc.metadata == {"key": "value", "category": "test"}


class TestVectorBaseSettings:
    """Test the VectorBaseSettings model."""

    def test_vector_base_settings_defaults(self) -> None:
        """Test VectorBaseSettings default values."""
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
        assert settings.enable_caching is True
        assert settings.enable_hybrid_search is False
        assert settings.enable_auto_scaling is False
        assert settings.enable_connection_pooling is True

    def test_vector_base_settings_custom_values(self) -> None:
        """Test VectorBaseSettings with custom values."""
        settings = VectorBaseSettings(
            host=SecretStr("vector-db.example.com"),
            port=6379,
            collection_prefix="prod_",
            default_dimension=1024,
            default_distance_metric="euclidean",
            connect_timeout=60.0,
            request_timeout=60.0,
            max_retries=5,
            batch_size=200,
            max_connections=20,
            enable_caching=False,
            enable_hybrid_search=True,
            enable_auto_scaling=True,
            enable_connection_pooling=False,
        )

        assert settings.host.get_secret_value() == "vector-db.example.com"
        assert settings.port == 6379
        assert settings.collection_prefix == "prod_"
        assert settings.default_dimension == 1024
        assert settings.default_distance_metric == "euclidean"
        assert settings.connect_timeout == 60.0
        assert settings.request_timeout == 60.0
        assert settings.max_retries == 5
        assert settings.batch_size == 200
        assert settings.max_connections == 20
        assert settings.enable_caching is False
        assert settings.enable_hybrid_search is True
        assert settings.enable_auto_scaling is True
        assert settings.enable_connection_pooling is False


class TestVectorCollection:
    """Test the VectorCollection class."""

    def test_vector_collection_initialization(self) -> None:
        """Test VectorCollection initialization."""
        mock_adapter = Mock()
        collection = VectorCollection(mock_adapter, "test_collection")

        assert collection.adapter == mock_adapter
        assert collection.name == "test_collection"

    @pytest.mark.asyncio
    async def test_vector_collection_search(self) -> None:
        """Test VectorCollection search method."""
        mock_adapter = Mock()
        mock_adapter.search = AsyncMock(return_value=[Mock()])
        collection = VectorCollection(mock_adapter, "test_collection")

        result = await collection.search([1.0, 2.0, 3.0], limit=5)

        mock_adapter.search.assert_called_once_with(
            "test_collection", [1.0, 2.0, 3.0], 5, None, False
        )
        assert result == [Mock()]

    @pytest.mark.asyncio
    async def test_vector_collection_insert(self) -> None:
        """Test VectorCollection insert method."""
        mock_adapter = Mock()
        mock_adapter.insert = AsyncMock(return_value=["id1", "id2"])
        collection = VectorCollection(mock_adapter, "test_collection")

        mock_documents = [Mock(), Mock()]
        result = await collection.insert(mock_documents)

        mock_adapter.insert.assert_called_once_with("test_collection", mock_documents)
        assert result == ["id1", "id2"]

    @pytest.mark.asyncio
    async def test_vector_collection_upsert(self) -> None:
        """Test VectorCollection upsert method."""
        mock_adapter = Mock()
        mock_adapter.upsert = AsyncMock(return_value=["id1", "id2"])
        collection = VectorCollection(mock_adapter, "test_collection")

        mock_documents = [Mock(), Mock()]
        result = await collection.upsert(mock_documents)

        mock_adapter.upsert.assert_called_once_with("test_collection", mock_documents)
        assert result == ["id1", "id2"]

    @pytest.mark.asyncio
    async def test_vector_collection_delete(self) -> None:
        """Test VectorCollection delete method."""
        mock_adapter = Mock()
        mock_adapter.delete = AsyncMock(return_value=True)
        collection = VectorCollection(mock_adapter, "test_collection")

        result = await collection.delete(["id1", "id2"])

        mock_adapter.delete.assert_called_once_with("test_collection", ["id1", "id2"])
        assert result is True

    @pytest.mark.asyncio
    async def test_vector_collection_get(self) -> None:
        """Test VectorCollection get method."""
        mock_adapter = Mock()
        mock_adapter.get = AsyncMock(return_value=[Mock()])
        collection = VectorCollection(mock_adapter, "test_collection")

        result = await collection.get(["id1", "id2"])

        mock_adapter.get.assert_called_once_with(
            "test_collection", ["id1", "id2"], False
        )
        assert result == [Mock()]

    @pytest.mark.asyncio
    async def test_vector_collection_count(self) -> None:
        """Test VectorCollection count method."""
        mock_adapter = Mock()
        mock_adapter.count = AsyncMock(return_value=42)
        collection = VectorCollection(mock_adapter, "test_collection")

        result = await collection.count()

        mock_adapter.count.assert_called_once_with("test_collection", None)
        assert result == 42


class TestVectorBase:
    """Test the VectorBase class."""

    @pytest.fixture
    def mock_config(self) -> Mock:
        """Create a mock config."""
        mock_config = Mock(spec=Config)
        mock_config.app = Mock(spec=AppSettings)
        mock_config.app.name = "test_app"
        mock_config.debug = Mock(spec=DebugSettings)
        mock_config.debug.sql = False
        return mock_config

    @pytest.fixture
    def vector_base(self, mock_config: Mock) -> VectorBase:
        """Create a VectorBase instance with mock config."""
        with patch("acb.adapters.vector._base.depends.get", return_value=mock_config):
            vector = VectorBase()
            vector.config = mock_config
            vector.settings = VectorBaseSettings()
            vector.logger = Mock()
            return vector

    def test_vector_base_initialization(self, vector_base: VectorBase) -> None:
        """Test VectorBase initialization."""
        assert vector_base._collections == {}
        assert vector_base._client is None
        assert vector_base._cache is None
        assert vector_base._hybrid_search is None
        assert vector_base._auto_scaler is None
        assert vector_base._connection_pool is None

    def test_vector_base_dynamic_collection_access(
        self, vector_base: VectorBase
    ) -> None:
        """Test VectorBase dynamic collection access."""
        # First access should create a new collection
        collection1 = vector_base.test_collection
        assert isinstance(collection1, VectorCollection)
        assert collection1.name == "test_collection"
        assert collection1.adapter == vector_base

        # Second access should return the same collection
        collection2 = vector_base.test_collection
        assert collection1 is collection2

    @pytest.mark.asyncio
    async def test_vector_base_get_client(self, vector_base: VectorBase) -> None:
        """Test VectorBase get_client method."""
        mock_client = Mock()
        with patch.object(
            vector_base, "_ensure_client", AsyncMock(return_value=mock_client)
        ):
            client = await vector_base.get_client()
            assert client == mock_client

    @pytest.mark.asyncio
    async def test_vector_base_get_cache_disabled(
        self, vector_base: VectorBase
    ) -> None:
        """Test VectorBase get_cache when caching is disabled."""
        vector_base.settings.enable_caching = False

        cache = await vector_base.get_cache()
        assert cache is None

    @pytest.mark.asyncio
    async def test_vector_base_get_cache_enabled(self, vector_base: VectorBase) -> None:
        """Test VectorBase get_cache when caching is enabled."""
        vector_base.settings.enable_caching = True
        vector_base._cache = Mock()

        cache = await vector_base.get_cache()
        assert cache == vector_base._cache

    @pytest.mark.asyncio
    async def test_vector_base_get_hybrid_search_disabled(
        self, vector_base: VectorBase
    ) -> None:
        """Test VectorBase get_hybrid_search when disabled."""
        vector_base.settings.enable_hybrid_search = False

        hybrid_search = await vector_base.get_hybrid_search()
        assert hybrid_search is None

    @pytest.mark.asyncio
    async def test_vector_base_get_hybrid_search_enabled(
        self, vector_base: VectorBase
    ) -> None:
        """Test VectorBase get_hybrid_search when enabled."""
        vector_base.settings.enable_hybrid_search = True
        vector_base._hybrid_search = Mock()

        hybrid_search = await vector_base.get_hybrid_search()
        assert hybrid_search == vector_base._hybrid_search

    @pytest.mark.asyncio
    async def test_vector_base_get_auto_scaler_disabled(
        self, vector_base: VectorBase
    ) -> None:
        """Test VectorBase get_auto_scaler when disabled."""
        vector_base.settings.enable_auto_scaling = False

        auto_scaler = await vector_base.get_auto_scaler()
        assert auto_scaler is None

    @pytest.mark.asyncio
    async def test_vector_base_get_auto_scaler_enabled(
        self, vector_base: VectorBase
    ) -> None:
        """Test VectorBase get_auto_scaler when enabled."""
        vector_base.settings.enable_auto_scaling = True
        vector_base._auto_scaler = Mock()

        auto_scaler = await vector_base.get_auto_scaler()
        assert auto_scaler == vector_base._auto_scaler

    @pytest.mark.asyncio
    async def test_vector_base_get_connection_pool_disabled(
        self, vector_base: VectorBase
    ) -> None:
        """Test VectorBase get_connection_pool when disabled."""
        vector_base.settings.enable_connection_pooling = False

        connection_pool = await vector_base.get_connection_pool()
        assert connection_pool is None

    @pytest.mark.asyncio
    async def test_vector_base_get_connection_pool_enabled(
        self, vector_base: VectorBase
    ) -> None:
        """Test VectorBase get_connection_pool when enabled."""
        vector_base.settings.enable_connection_pooling = True
        vector_base._connection_pool = Mock()

        connection_pool = await vector_base.get_connection_pool()
        assert connection_pool == vector_base._connection_pool

    @pytest.mark.asyncio
    async def test_vector_base_search_with_cache(self, vector_base: VectorBase) -> None:
        """Test VectorBase search_with_cache method."""
        # Test with cache disabled - should fallback to regular search
        vector_base.settings.enable_caching = False
        with patch.object(vector_base, "search", AsyncMock(return_value=[Mock()])):
            result = await vector_base.search_with_cache(
                "test_collection", [1.0, 2.0, 3.0], limit=5
            )
            assert len(result) == 1
            vector_base.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_vector_base_hybrid_search(self, vector_base: VectorBase) -> None:
        """Test VectorBase hybrid_search method."""
        # Test with hybrid search disabled - should fallback to regular search
        vector_base.settings.enable_hybrid_search = False
        with patch.object(vector_base, "search", AsyncMock(return_value=[Mock()])):
            result = await vector_base.hybrid_search(
                "test_collection", [1.0, 2.0, 3.0], "test query", limit=5
            )
            assert len(result) == 1
            vector_base.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_vector_base_transaction_context_manager(
        self, vector_base: VectorBase
    ) -> None:
        """Test VectorBase transaction context manager."""
        mock_client = Mock()
        with patch.object(
            vector_base, "get_client", AsyncMock(return_value=mock_client)
        ):
            async with vector_base.transaction() as client:
                assert client == mock_client

    def test_vector_base_abstract_methods(self) -> None:
        """Test that VectorBase has abstract methods."""
        # VectorBase should not be instantiable directly because of abstract methods
        # But we can test that the methods exist
        assert hasattr(VectorBase, "init")
        # The method should be abstract
        import inspect

        assert inspect.iscoroutinefunction(VectorBase.init)


# Additional edge case tests
class TestVectorBaseEdgeCases:
    """Test edge cases for vector base classes."""

    def test_vector_document_id_none_explicit(self) -> None:
        """Test VectorDocument with explicit None id."""
        doc = VectorDocument(id=None, vector=[1.0, 2.0, 3.0])
        assert doc.id is None

    def test_vector_search_result_empty_metadata(self) -> None:
        """Test VectorSearchResult with explicitly empty metadata."""
        result = VectorSearchResult(id="test", score=0.5, metadata={})
        assert result.metadata == {}
        assert result.vector is None

    def test_vector_search_result_with_vector(self) -> None:
        """Test VectorSearchResult with vector data."""
        result = VectorSearchResult(
            id="test", score=0.75, metadata={"category": "test"}, vector=[0.1, 0.2, 0.3]
        )
        assert result.vector == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_vector_collection_search_with_filters(self) -> None:
        """Test VectorCollection search with filters."""
        mock_adapter = Mock()
        mock_adapter.search = AsyncMock(return_value=[])
        collection = VectorCollection(mock_adapter, "test_collection")

        filters = {"category": "test", "status": "active"}
        await collection.search([1.0, 2.0], filter_expr=filters, include_vectors=True)

        mock_adapter.search.assert_called_once_with(
            "test_collection", [1.0, 2.0], 10, filters, True
        )

    @pytest.mark.asyncio
    async def test_vector_collection_get_with_vectors(self) -> None:
        """Test VectorCollection get with include_vectors=True."""
        mock_adapter = Mock()
        mock_adapter.get = AsyncMock(return_value=[])
        collection = VectorCollection(mock_adapter, "test_collection")

        await collection.get(["id1"], include_vectors=True)

        mock_adapter.get.assert_called_once_with("test_collection", ["id1"], True)

    def test_vector_base_settings_ssl_config_mixin(self) -> None:
        """Test that VectorBaseSettings inherits from SSLConfigMixin."""
        from acb.ssl_config import SSLConfigMixin

        assert issubclass(VectorBaseSettings, SSLConfigMixin)

    def test_vector_base_settings_secrets(self) -> None:
        """Test that VectorBaseSettings handles secrets correctly."""
        settings = VectorBaseSettings()
        # Host should be a SecretStr
        assert isinstance(settings.host, SecretStr)
        assert settings.host.get_secret_value() == "127.0.0.1"
