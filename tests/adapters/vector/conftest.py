"""Shared fixtures and mocks for vector adapter tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from acb.adapters.vector._base import VectorDocument, VectorSearchResult


@pytest.fixture
def mock_vector_client():
    """Mock vector database client."""
    client = MagicMock()
    client.search.return_value = [
        VectorSearchResult(
            id="doc1",
            score=0.95,
            metadata={"title": "Test Document"},
        )
    ]
    # Create a mock result object
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [("doc1", {"title": "Test Document"}, 0.95)]
    mock_result.fetchone.return_value = (1,)

    # Make execute return the mock result
    client.execute.return_value = mock_result
    client.executemany.return_value = None
    return client


@pytest.fixture
def sample_vectors():
    """Sample vector documents for testing."""
    return [
        VectorDocument(
            id="doc1",
            vector=[0.1, 0.2, 0.3],
            metadata={"title": "Document 1", "category": "test"},
        ),
        VectorDocument(
            id="doc2",
            vector=[0.4, 0.5, 0.6],
            metadata={"title": "Document 2", "category": "test"},
        ),
    ]


@pytest.fixture
def sample_query_vector():
    """Sample query vector for search tests."""
    return [0.1, 0.2, 0.3]


@pytest.fixture
def mock_duckdb_connection(mock_vector_client):
    """Mock DuckDB connection for testing."""
    return mock_vector_client


@pytest.fixture
def temp_db_path(tmp_path):
    """Temporary database path for testing."""
    return tmp_path / "test_vectors.db"


@pytest.fixture
def mock_vector_settings(temp_db_path):
    """Mock vector adapter settings."""
    from acb.adapters.vector.duckdb import VectorSettings

    return VectorSettings(
        database_path=str(temp_db_path),
        default_dimension=3,
        enable_vss=False,  # Disable VSS for testing to avoid extension dependencies
        memory_limit="1GB",
        threads=1,
    )


@pytest.fixture
def mock_pinecone_settings():
    """Mock Pinecone vector adapter settings."""
    from acb.adapters.vector.pinecone import VectorSettings

    return VectorSettings(
        api_key="test-api-key",
        environment="test-env",
        index_name="test-index",
        default_dimension=3,
    )


@pytest.fixture
def mock_weaviate_settings():
    """Mock Weaviate vector adapter settings."""
    from acb.adapters.vector.weaviate import VectorSettings

    return VectorSettings(
        url="http://localhost:8080",
        default_class="TestDocument",
        default_dimension=3,
        auto_create_schema=True,
    )


@pytest.fixture
def mock_qdrant_settings():
    """Mock Qdrant vector adapter settings."""
    from acb.adapters.vector.qdrant import VectorSettings

    return VectorSettings(
        url="http://localhost:6333",
        default_collection="test_documents",
        default_dimension=3,
    )


@pytest.fixture
def mock_pinecone_client():
    """Mock Pinecone client for testing."""
    client = MagicMock()
    index = MagicMock()

    # Mock query response
    index.query.return_value = {
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
    index.upsert.return_value = {"upserted_count": 1}

    # Mock fetch response
    index.fetch.return_value = {
        "vectors": {
            "doc1": {"values": [0.1, 0.2, 0.3], "metadata": {"title": "Test Document"}}
        }
    }

    # Mock describe_index_stats response
    index.describe_index_stats.return_value = {
        "total_vector_count": 10,
        "namespaces": {"test": {"vector_count": 5}},
    }

    client.Index.return_value = index
    client.describe_index.return_value = {"status": {"ready": True}}

    return client


@pytest.fixture
def mock_weaviate_client():
    """Mock Weaviate client for testing."""
    client = MagicMock()
    collection = MagicMock()

    # Mock search response object
    mock_obj = MagicMock()
    mock_obj.uuid = "doc1"
    mock_obj.properties = {"title": "Test Document"}
    mock_obj.metadata = MagicMock()
    mock_obj.metadata.distance = 0.05
    mock_obj.metadata.score = 0.95
    mock_obj.vector = {"default": [0.1, 0.2, 0.3]}

    collection.query.near_vector.return_value.objects = [mock_obj]
    collection.query.bm25.return_value.objects = [mock_obj]
    collection.query.fetch_object_by_id.return_value = mock_obj

    # Mock batch operations
    mock_batch_context = MagicMock()
    collection.batch.dynamic.return_value.__enter__.return_value = mock_batch_context
    collection.batch.dynamic.return_value.__exit__.return_value = None

    # Mock aggregate response
    mock_aggregate_result = MagicMock()
    mock_aggregate_result.total_count = 10
    collection.aggregate.over_all.return_value = mock_aggregate_result

    # Mock collections list
    mock_col_info = MagicMock()
    mock_col_info.name = "TestDocument"
    client.collections.list_all.return_value = [mock_col_info]
    client.collections.get.return_value = collection
    client.collections.create.return_value = None
    client.collections.delete.return_value = None

    client.is_ready.return_value = True

    return client


@pytest.fixture
def mock_qdrant_client():
    """Mock Qdrant client for testing."""
    client = AsyncMock()

    # Mock search response
    mock_point = MagicMock()
    mock_point.id = "doc1"
    mock_point.score = 0.95
    mock_point.payload = {"title": "Test Document"}
    mock_point.vector = [0.1, 0.2, 0.3]

    client.search.return_value = [mock_point]

    # Mock collections response
    mock_collection_info = MagicMock()
    mock_collection_info.name = "test_documents"
    mock_collections_response = MagicMock()
    mock_collections_response.collections = [mock_collection_info]
    client.get_collections.return_value = mock_collections_response

    # Mock operation responses
    mock_operation_info = MagicMock()
    mock_operation_info.status.name = "COMPLETED"
    client.upsert.return_value = mock_operation_info
    client.delete.return_value = mock_operation_info

    # Mock retrieve response
    client.retrieve.return_value = [mock_point]

    # Mock count response
    mock_count_result = MagicMock()
    mock_count_result.count = 10
    client.count.return_value = mock_count_result

    # Mock scroll response
    client.scroll.return_value = ([mock_point], "next_offset")

    # Mock cluster info
    client.get_cluster_info.return_value = {"status": "green"}

    return client
