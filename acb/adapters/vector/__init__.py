"""Vector database adapters for ACB."""

# Import implementations for registration
from . import duckdb
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
]
