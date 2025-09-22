"""Shared fixtures and mocks for vector adapter tests."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path

from acb.adapters.vector._base import VectorSearchResult, VectorDocument


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
    mock_result.fetchall.return_value = [
        ("doc1", {"title": "Test Document"}, 0.95)
    ]
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
