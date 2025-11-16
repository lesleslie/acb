"""Tests for the DuckDB PGQ graph adapter."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from contextlib import asynccontextmanager
from datetime import datetime
from sqlalchemy.pool import NullPool

from acb.adapters.graph._base import (
    GraphEdgeModel,
    GraphNodeModel,
    GraphQueryLanguage,
    GraphTraversalDirection,
)
from acb.adapters.graph.duckdb_pgq import (
    MODULE_METADATA,
    DuckDBPGQSettings,
    Graph,
)


@pytest.fixture
def duckdb_graph_adapter() -> Graph:
    settings = DuckDBPGQSettings.model_construct(
        graph_name="acb_graph",
        nodes_table="acb_graph_nodes",
        edges_table="acb_graph_edges",
        install_extensions=[],
        pragmas={},
    )
    settings.engine_kwargs = {"poolclass": NullPool, "pool_pre_ping": False}
    adapter = Graph(settings=settings)
    adapter.config = SimpleNamespace()
    adapter.logger = MagicMock()
    return adapter


def _mapping_result(rows: list[dict[str, object]]) -> MagicMock:
    class _Mappings:
        def __init__(self, rows: list[dict[str, object]]) -> None:
            self._rows = rows

        def first(self) -> dict[str, object] | None:
            return self._rows[0] if self._rows else None

        def all(self) -> list[dict[str, object]]:
            return self._rows

    result = MagicMock()
    result.mappings.return_value = _Mappings(rows)
    return result


def _connection_context(result: MagicMock | None = None) -> tuple:
    connection = AsyncMock()
    connection.execute = AsyncMock(return_value=result or AsyncMock())

    @asynccontextmanager
    async def ctx():
        yield connection

    return ctx, connection


@pytest.mark.asyncio
async def test_module_metadata() -> None:
    assert MODULE_METADATA.provider == "duckdb"
    assert MODULE_METADATA.category == "graph"
    assert "duckdb>=0.10.2" in MODULE_METADATA.required_packages


@pytest.mark.asyncio
async def test_query_language_and_features(duckdb_graph_adapter: Graph) -> None:
    assert duckdb_graph_adapter.query_language == GraphQueryLanguage.PGQ
    features = duckdb_graph_adapter.supported_features
    assert "pgq_queries" in features
    assert "transactions" in features


@pytest.mark.asyncio
async def test_create_node_serializes_json(duckdb_graph_adapter: Graph) -> None:
    ctx, connection = _connection_context()
    with patch.object(duckdb_graph_adapter, "_connection", ctx):
        node = await duckdb_graph_adapter.create_node(["User"], {"name": "Alice"})

    stmt = connection.execute.await_args.args[0]
    params = connection.execute.await_args.args[1]
    assert stmt.text.strip().startswith("INSERT INTO acb_graph_nodes")
    assert json.loads(params["labels"]) == ["User"]
    assert json.loads(params["properties"]) == {"name": "Alice"}
    assert node.labels == ["User"]
    assert node.properties["name"] == "Alice"


@pytest.mark.asyncio
async def test_get_node_deserializes_json(duckdb_graph_adapter: Graph) -> None:
    now = datetime.utcnow()
    row = {
        "id": "node-1",
        "labels": json.dumps(["User"]),
        "properties": json.dumps({"name": "Bob"}),
        "created_at": now,
        "updated_at": now,
    }
    result = _mapping_result([row])
    ctx, _ = _connection_context(result)

    with patch.object(duckdb_graph_adapter, "_connection", ctx):
        node = await duckdb_graph_adapter.get_node(row["id"])

    assert node is not None
    assert node.id == "node-1"
    assert node.labels == ["User"]
    assert node.properties["name"] == "Bob"


@pytest.mark.asyncio
async def test_create_edge_persists_properties(duckdb_graph_adapter: Graph) -> None:
    ctx, connection = _connection_context()
    with patch.object(duckdb_graph_adapter, "_connection", ctx):
        edge = await duckdb_graph_adapter.create_edge(
            "FOLLOWS",
            "node-a",
            "node-b",
            {"weight": 2},
        )

    stmt = connection.execute.await_args.args[0]
    params = connection.execute.await_args.args[1]
    assert stmt.text.strip().startswith("INSERT INTO acb_graph_edges")
    assert params["type"] == "FOLLOWS"
    assert params["from_node"] == "node-a"
    assert params["to_node"] == "node-b"
    assert json.loads(params["properties"]) == {"weight": 2}
    assert edge.type == "FOLLOWS"


@pytest.mark.asyncio
async def test_get_edge_returns_model(duckdb_graph_adapter: Graph) -> None:
    now = datetime.utcnow()
    row = {
        "id": "edge-1",
        "type": "FOLLOWS",
        "from_node": "node-a",
        "to_node": "node-b",
        "properties": json.dumps({"weight": 2}),
        "created_at": now,
        "updated_at": now,
    }
    result = _mapping_result([row])
    ctx, _ = _connection_context(result)

    with patch.object(duckdb_graph_adapter, "_connection", ctx):
        edge = await duckdb_graph_adapter.get_edge("edge-1")

    assert edge is not None
    assert edge.type == "FOLLOWS"
    assert edge.from_node == "node-a"
    assert edge.to_node == "node-b"
    assert edge.properties["weight"] == 2


@pytest.mark.asyncio
async def test_get_neighbors_uses_fetch_edges(duckdb_graph_adapter: Graph) -> None:
    with (
        patch.object(
            duckdb_graph_adapter,
            "_fetch_edges",
            AsyncMock(
                return_value=[
                    {
                        "id": "edge-1",
                        "type": "REL",
                        "from_node": "node-a",
                        "to_node": "node-b",
                        "properties": {},
                    }
                ],
            ),
        ),
        patch.object(
            duckdb_graph_adapter,
            "_get_node_list",
            AsyncMock(
                return_value=[
                    GraphNodeModel(id="node-b", labels=["User"], properties={}),
                ],
            ),
        ),
    ):
        neighbors = await duckdb_graph_adapter.get_neighbors(
            "node-a",
            GraphTraversalDirection.OUT,
            None,
        )

    ids = [node.id for node in neighbors]
    assert ids == ["node-b"]


@pytest.mark.asyncio
async def test_find_shortest_path_uses_weight(duckdb_graph_adapter: Graph) -> None:
    with (
        patch.object(
            duckdb_graph_adapter,
            "_fetch_edges",
            AsyncMock(
                return_value=[
                    {
                        "id": "edge-1",
                        "type": "REL",
                        "from_node": "node-a",
                        "to_node": "node-b",
                        "properties": {"weight": 3},
                    }
                ],
            ),
        ),
        patch.object(
            duckdb_graph_adapter,
            "_get_node_list",
            AsyncMock(
                return_value=[
                    GraphNodeModel(id="node-a", labels=[], properties={}),
                    GraphNodeModel(id="node-b", labels=[], properties={}),
                ],
            ),
        ),
        patch.object(
            duckdb_graph_adapter,
            "_get_edge",
            AsyncMock(
                side_effect=[
                    GraphEdgeModel(
                        id="edge-1",
                        type="REL",
                        from_node="node-a",
                        to_node="node-b",
                        properties={"weight": 3},
                    )
                ],
            ),
        ),
    ):
        path = await duckdb_graph_adapter.find_shortest_path(
            "node-a",
            "node-b",
            weight_property="weight",
        )

    assert path is not None
    assert path.length == 1
    assert path.weight == 3


@pytest.mark.asyncio
async def test_execute_query_returns_records(duckdb_graph_adapter: Graph) -> None:
    result = _mapping_result([{"total": 1}])
    ctx, _ = _connection_context(result)

    with patch.object(duckdb_graph_adapter, "_connection", ctx):
        query_result = await duckdb_graph_adapter.execute_query("SELECT 1 AS total")

    assert query_result.records == [{"total": 1}]
    assert query_result.metadata["rowcount"] == 1


@pytest.mark.asyncio
async def test_clear_graph_executes_deletes(duckdb_graph_adapter: Graph) -> None:
    ctx, connection = _connection_context()
    with patch.object(duckdb_graph_adapter, "_connection", ctx):
        cleared = await duckdb_graph_adapter.clear_graph()

    assert cleared
    assert connection.execute.await_count == 2
