> **ACB Documentation**: [Main](<../../../README.md>) | [Core Systems](<../../README.md>) | [Actions](<../../actions/README.md>) | [Adapters](<../README.md>) | [Graph](<./README.md>)

# Graph Adapter

The Graph adapter provides a unified interface for property graph databases such
as Neo4j, Amazon Neptune, and ArangoDB. It normalizes query execution,
traversals, schema inspection, and TLS-aware connection management so services
can swap graph backends with minimal code changes.

## Table of Contents

- [Overview](<#overview>)
- [Core Models](<#core-models>)
- [Query & Traversal Interfaces](<#query--traversal-interfaces>)
- [Settings & Security](<#settings--security>)
- [Built-in Implementations](<#built-in-implementations>)
- [Usage Examples](<#usage-examples>)
- [Schema Inspection Example](<#schema-inspection-example>)
- [Best Practices](<#best-practices>)
- [Related Adapters](<#related-adapters>)

## Overview

All implementations derive from `GraphBase`, which handles lifecycle hooks,
dependency injection, and logging with `acb.logger`. The adapter pattern exposes
protocol-friendly operations (`GraphProtocol`) so downstream code can depend on
type-checked interfaces rather than concrete drivers.

## Core Models

- `GraphNodeModel` & `GraphEdgeModel`: Capture identifiers, labels/types,
  properties, and timestamps.
- `GraphPathModel`: Represents traversal results, including hop count and
  optional weights.
- `GraphSchemaModel`: Describes indexes, constraints, and available node/edge
  types for diagnostics or migration tooling.
- `GraphQueryResult`: Bundles nodes, edges, paths, arbitrary records, and
  metadata from query execution.

## Query & Traversal Interfaces

- `execute_query()` accepts Cypher, Gremlin, AQL, SPARQL, or PGQ (DuckDB), depending on the
  backend, with parameters passed as dictionaries.
- CRUD helpers such as `create_node()`, `create_edge()`, `get_node()`, and
  `find_path()` standardize common graph tasks.
- `GraphTraversalDirection` enumerates `OUT`, `IN`, or `BOTH` to control
  traversal semantics without vendor-specific constants.

## Settings & Security

`GraphBaseSettings` covers:

- Connection details (host, port, credentials, database selection, auth token).
- Connection pooling (`max_connections`, `idle_timeout`, `max_connection_lifetime`)
  for production workloads.
- Query tuning (`query_timeout`, `max_query_size`, logging toggles) and caching
  with TTL controls.
- TLS settings implemented through `SSLConfigMixin`, including certificate paths
  and verify modes (`required`, `optional`, `none`).

These settings are compatible with `settings/adapters.yaml` and integrate with
ACB's dependency injection system.

## Built-in Implementations

| Module | Backend | Highlights |
| ------ | ------- | ---------- |
| `neo4j` | Neo4j Aura / self-managed clusters | Bolt driver support, Cypher queries, TLS options. |
| `neptune` | Amazon Neptune | Gremlin/SPARQL support, IAM integration hooks. |
| `arangodb` | ArangoDB | AQL queries, multi-model features (graph + document). |
| `duckdb_pgq` | DuckDB + DuckPGQ | Embedded PGQ queries, zero-dependency analytics, file-backed or in-memory graphs. |

Each adapter declares `MODULE_METADATA` describing capabilities, health checks,
and discovery identifiers so they plug into the service registry automatically.

### DuckDB PGQ Quick Start

- Set `graph: duckpgq` in `settings/adapters.yaml`; optionally point
  `database_url` to a DuckDB file under `settings/app.yaml`.
- The adapter installs/loads the `duckpgq` extension automatically, maintains
  node/edge tables, and exposes PGQ queries through `GRAPH_QUERY`.
- Use standard CRUD helpers for single-record operations or call
  `execute_query("MATCH ...")` to run PGQ patterns directly inside DuckDB.

## Usage Examples

```python
from acb.adapters import import_adapter
from acb.depends import depends

Graph = import_adapter("graph")


async def fetch_user_graph(user_id: str):
    graph = await depends.get(Graph)
    query = """
    MATCH (u:User {id: $user_id})-[:FOLLOWS]->(other)
    RETURN u, other
    """
    return await graph.execute_query(query, {"user_id": user_id})
```

## Schema Inspection Example

```python
from acb.adapters.graph import GraphSchemaModel


async def describe_graph() -> GraphSchemaModel:
    graph = await depends.get(Graph)
    return await graph.get_schema()
```

Use schema inspection during deployment checks to ensure required indexes,
constraints, and relationship types are available before enabling new features.

## Best Practices

- Keep query text in dedicated modules or action helpers so you can share
  parameterized templates across services.
- Enable query logging only in lower environments; production logging should use
  structured summaries to avoid leaking PII.
- Use `GraphSchemaModel` in combination with migrations to detect drift between
  expected and actual indexes or constraints.
- When running in secure environments, configure TLS certificates through the
  provided settings to align with compliance requirements.

## Related Adapters

- [SQL](<../sql/README.md>)
- [NoSQL](<../nosql/README.md>)
- [Vector](<../vector/README.md>)
