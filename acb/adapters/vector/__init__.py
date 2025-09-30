"""Vector database adapters for ACB."""

# Import implementations for registration
from . import duckdb, pinecone, qdrant, weaviate
from ._base import (
    VectorBase,
    VectorBaseSettings,
    VectorCollection,
    VectorDocument,
    VectorProtocol,
    VectorSearchResult,
)

__all__ = [
    "VectorBase",
    "VectorBaseSettings",
    "VectorCollection",
    "VectorDocument",
    "VectorProtocol",
    "VectorSearchResult",
    "duckdb",
    "pinecone",
    "qdrant",
    "weaviate",
]
