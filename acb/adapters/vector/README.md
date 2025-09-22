# Vector Database Adapters

Vector database adapters provide interfaces for working with vector databases for similarity search and AI applications.

## Available Implementations

| Implementation | Description | Status |
| -------------- | ----------- | ------ |
| DuckDB | Local vector database with VSS extension | Stable |

## Installation

To use vector database adapters, install the optional dependencies:

```bash
uv add "acb[vector]"
```

## Configuration

Configure your vector database in `settings/adapters.yml`:

```yaml
# Use DuckDB vector adapter
vector: duckdb
```

And in `settings/vector.yml`:

```yaml
vector:
  database_path: "data/vectors.db"
  default_dimension: 1536
  default_distance_metric: "cosine"
  memory_limit: "2GB"
  threads: 4
  enable_vss: true
```

## Usage

```python
from acb.depends import depends
from acb.adapters import import_adapter

# Import the vector adapter
Vector = import_adapter("vector")
vector = depends.get(Vector)

# Create a collection
await vector.create_collection("documents", dimension=1536)

# Insert vector documents
from acb.adapters.vector._base import VectorDocument

documents = [
    VectorDocument(
        id="doc1",
        vector=[0.1, 0.2, 0.3, ...],  # 1536-dimensional vector
        metadata={"title": "Document 1", "category": "example"},
    )
]

await vector.documents.insert(documents)

# Perform similarity search
from acb.adapters.vector._base import VectorSearchResult

results = await vector.documents.search(
    query_vector=[0.1, 0.2, 0.3, ...],  # Query vector
    limit=10,
)

for result in results:
    print(f"ID: {result.id}, Score: {result.score}, Metadata: {result.metadata}")
```

## DuckDB Vector Adapter

The DuckDB vector adapter provides a local vector database implementation using DuckDB with the VSS extension.

### Features

- Local vector storage
- Similarity search with cosine, euclidean, and dot product metrics
- Automatic HNSW indexing when VSS extension is available
- Schema validation and SQL injection protection
- Collection management (create, list, delete)
- Bulk operations (insert, upsert, delete)
- Filtering support
- Connection pooling

### Requirements

- DuckDB >= 0.10.2
- VSS extension (optional but recommended for similarity search)

### Configuration Options

| Option | Description | Default |
| ------ | ----------- | ------- |
| `database_path` | Path to the DuckDB database file | `"data/vectors.db"` |
| `default_dimension` | Default vector dimension | `1536` |
| `default_distance_metric` | Default distance metric (cosine, euclidean, dot_product) | `"cosine"` |
| `memory_limit` | Memory limit for DuckDB | `"2GB"` |
| `threads` | Number of threads for DuckDB | `4` |
| `enable_vss` | Enable VSS extension for similarity search | `true` |
