"""DuckDB PGQ graph adapter."""

from __future__ import annotations

import json
import re
from pathlib import Path
from uuid import UUID, uuid4

import typing as t
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncTransaction,
    create_async_engine,
)

from acb.adapters import AdapterCapability, AdapterMetadata, AdapterStatus
from acb.adapters.graph._base import (
    GraphBase,
    GraphBaseSettings,
    GraphEdgeModel,
    GraphNodeModel,
    GraphPathModel,
    GraphQueryLanguage,
    GraphQueryResult,
    GraphSchemaModel,
    GraphTraversalDirection,
)
from acb.depends import depends

MODULE_METADATA = AdapterMetadata(
    module_id=UUID("019a1c00-e6f0-7d4a-a749-b305c0b2a4d2"),
    name="DuckDB PGQ",
    category="graph",
    provider="duckdb",
    version="0.1.0",
    acb_min_version="0.19.0",
    author="lesleslie <les@wedgwoodwebworks.com>",
    created_date="2025-02-15",
    last_modified="2025-02-15",
    status=AdapterStatus.BETA,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.TRANSACTIONS,
        AdapterCapability.TLS_SUPPORT,
        AdapterCapability.GRAPH_TRAVERSAL,
        AdapterCapability.BULK_OPERATIONS,
        AdapterCapability.GRAPH_SCHEMA_VALIDATION,
        AdapterCapability.PATHFINDING,
    ],
    required_packages=[
        "duckdb>=0.10.2",
        "duckdb-engine>=0.11.2",
        "sqlalchemy>=2.0.41",
    ],
    optional_packages={
        "duckdb-engine[arrow]": "Enable Arrow acceleration for analytical queries",
    },
    description=(
        "DuckDB graph adapter powered by the DuckPGQ extension. "
        "Suitable for lightweight property graph workloads and embedded analytics."
    ),
    settings_class="DuckDBPGQSettings",
)


def _safe_ident(name: str) -> str:
    """Validate and return a safe SQL identifier.

    Allows only letters, numbers, and underscores, starting with a letter or underscore.
    Raises ValueError if the identifier is unsafe.
    """
    if not re.match(
        r"^[A-Za-z_][A-Za-z0-9_]*$", name
    ):  # REGEX OK: SQL identifier validation - anchored character classes only  # nosec B108
        msg = f"Unsafe SQL identifier: {name!r}"
        raise ValueError(msg)
    return name


def _ensure_directory(target: Path) -> None:
    if target.name == ":memory:":
        return
    if not target.parent.exists():
        target.parent.mkdir(parents=True, exist_ok=True)


class DuckDBPGQSettings(GraphBaseSettings):
    """DuckDB PGQ specific settings."""

    database_url: str = "duckdb:///data/graph.duckdb"
    graph_name: str = "acb_graph"
    nodes_table: str = "acb_graph_nodes"
    edges_table: str = "acb_graph_edges"
    install_extensions: list[str] = Field(default_factory=lambda: ["duckpgq"])
    pragmas: dict[str, str] = Field(default_factory=dict)

    _url: URL | None = None

    def __init__(self, **values: t.Any) -> None:  # type: ignore[override]
        super().__init__(**values)
        self._prepare_url()

    def _prepare_url(self) -> None:
        url = make_url(self.database_url)
        if url.database and url.database != ":memory:":
            _ensure_directory(Path(url.database))
        self._url = url

    @property
    def database_path(self) -> Path | None:
        if not self._url or not self._url.database or self._url.database == ":memory:":
            return None
        return Path(self._url.database)


@dataclass(slots=True)
class _DuckDBTransaction:
    connection: AsyncConnection
    transaction: AsyncTransaction


class Graph(GraphBase):
    """DuckDB PGQ graph adapter."""

    def __init__(
        self,
        settings: DuckDBPGQSettings | None = None,
        **kwargs: t.Any,
    ) -> None:
        super().__init__(**kwargs)
        if settings is not None:
            self._settings = settings
        else:
            self._settings = DuckDBPGQSettings(**kwargs)
        self._engine: AsyncEngine | None = None

    @property
    def query_language(self) -> GraphQueryLanguage:
        return GraphQueryLanguage.PGQ

    @property
    def supported_features(self) -> list[str]:
        return [
            "pgq_queries",
            "transactions",
            "bulk_ingest",
            "json_properties",
            "in_memory_mode",
            "analytics",
        ]

    async def _create_client(self) -> AsyncEngine:
        assert self._settings._url is not None
        engine = create_async_engine(
            str(self._settings._url),
            pool_pre_ping=False,
            future=True,
        )
        async with engine.begin() as conn:
            await self._install_extensions(conn)
            await self._configure_pragmas(conn)
            await self._ensure_tables(conn)
            await self._register_graph(conn)
        self._engine = engine
        return engine

    async def _install_extensions(self, conn: AsyncConnection) -> None:
        for extension in self._settings.install_extensions:
            safe_extension = _safe_ident(extension)
            stmt = text(f"INSTALL {safe_extension}")  # nosec B608
            with suppress(Exception):
                await conn.execute(stmt)
            stmt = text(f"LOAD {safe_extension}")  # nosec B608
            with suppress(Exception):
                await conn.execute(stmt)

    async def _configure_pragmas(self, conn: AsyncConnection) -> None:
        for pragma, value in self._settings.pragmas.items():
            value_str = value if isinstance(value, str) else format(value)
            numeric_check = value_str.lstrip("-+").replace(".", "", 1).isdigit()
            if numeric_check:
                clause = value_str
            else:
                escaped = value_str.replace("'", "''")
                clause = f"'{escaped}'"
            safe_pragma = _safe_ident(pragma)
            stmt = text(f"PRAGMA {safe_pragma}={clause}")  # nosec B608
            await conn.execute(stmt)

    async def _ensure_tables(self, conn: AsyncConnection) -> None:
        nodes_table = _safe_ident(self._settings.nodes_table)
        edges_table = _safe_ident(self._settings.edges_table)
        sql_nodes = f"""
                CREATE TABLE IF NOT EXISTS {nodes_table} (
                    id TEXT PRIMARY KEY,
                    labels JSON,
                    properties JSON,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
                """  # nosec B608
        await conn.execute(text(sql_nodes))
        await conn.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {edges_table} (
                    id TEXT PRIMARY KEY,
                    type TEXT,
                    from_node TEXT,
                    to_node TEXT,
                    properties JSON,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
                """
                # nosec B608
            )
        )
        await conn.execute(
            text(
                f"CREATE INDEX IF NOT EXISTS idx_{edges_table}_from ON {edges_table}(from_node)"
                # nosec B608
            )
        )
        await conn.execute(
            text(
                f"CREATE INDEX IF NOT EXISTS idx_{edges_table}_to ON {edges_table}(to_node)"
                # nosec B608
            )
        )

    async def _register_graph(self, conn: AsyncConnection) -> None:
        graph_name = self._settings.graph_name
        nodes_table = self._settings.nodes_table
        edges_table = self._settings.edges_table
        create_stmt = text(
            """
            CALL pgq.create_graph(
                graph_name => :graph_name,
                nodes_table => :nodes_table,
                edges_table => :edges_table,
                node_id => 'id',
                from_node => 'from_node',
                to_node => 'to_node'
            )
            """
        )
        with suppress(Exception):
            await conn.execute(
                create_stmt,
                {
                    "graph_name": graph_name,
                    "nodes_table": nodes_table,
                    "edges_table": edges_table,
                },
            )

    @asynccontextmanager
    async def _connection(self) -> t.AsyncIterator[AsyncConnection]:
        if isinstance(self._transaction, _DuckDBTransaction):
            yield self._transaction.connection
            return
        engine = await self._ensure_client()
        async with engine.begin() as conn:
            yield conn

    async def _begin_transaction(self, client: AsyncEngine) -> _DuckDBTransaction:
        conn = await client.connect()
        transaction = await conn.begin()
        return _DuckDBTransaction(connection=conn, transaction=transaction)

    async def _commit_transaction(self, transaction: _DuckDBTransaction) -> None:
        await transaction.transaction.commit()
        await transaction.connection.close()

    async def _rollback_transaction(self) -> None:
        if isinstance(self._transaction, _DuckDBTransaction):
            await self._transaction.transaction.rollback()
            await self._transaction.connection.close()

    async def _execute_query(
        self,
        query: str,
        parameters: dict[str, t.Any] | None = None,
        timeout: float | None = None,
    ) -> GraphQueryResult:
        params = parameters or {}
        async with self._connection() as conn:
            if timeout:
                await conn.execute(
                    text(f"PRAGMA statement_timeout={int(timeout * 1000)}")
                )
            stripped = query.lstrip()
            if stripped.upper().startswith("MATCH"):
                stmt = text("SELECT * FROM GRAPH_QUERY(:graph_name, :pgq_query)")
                result = await conn.execute(
                    stmt,
                    {
                        "graph_name": self._settings.graph_name,
                        "pgq_query": query,
                    },
                )
            else:
                stmt = text(query)
                result = await conn.execute(stmt, params)
            rows = result.mappings().all()
        records = [dict(row) for row in rows]
        return GraphQueryResult(
            nodes=[],
            edges=[],
            paths=[],
            records=records,
            metadata={
                "graph": self._settings.graph_name,
                "rowcount": len(records),
            },
            query_language=GraphQueryLanguage.PGQ
            if stripped.upper().startswith("MATCH")
            else None,
        )

    async def _create_node(
        self,
        labels: list[str],
        properties: dict[str, t.Any],
    ) -> GraphNodeModel:
        node_id = str(uuid4())
        now = datetime.now(tz=UTC)
        async with self._connection() as conn:
            sql = (
                "INSERT INTO "
                + _safe_ident(self._settings.nodes_table)
                + " (id, labels, properties, created_at, updated_at) "
                + "VALUES (:id, :labels, :properties, :created_at, :updated_at)"
            )  # nosec B608
            await conn.execute(
                text(sql),
                {
                    "id": node_id,
                    "labels": json.dumps(labels),
                    "properties": json.dumps(properties),
                    "created_at": now,
                    "updated_at": now,
                },
            )
        return GraphNodeModel(
            id=node_id,
            labels=labels,
            properties=properties,
            created_at=now,
            updated_at=now,
        )

    async def _get_node(self, node_id: str) -> GraphNodeModel | None:
        async with self._connection() as conn:
            sql = (
                "SELECT id, labels, properties, created_at, updated_at FROM "
                + _safe_ident(self._settings.nodes_table)
                + " WHERE id = :id"
            )  # nosec B608
            result = await conn.execute(
                text(sql),
                {"id": node_id},
            )
            row = result.mappings().first()
        if not row:
            return None
        return GraphNodeModel(
            id=row["id"],
            labels=json.loads(row["labels"]) if row["labels"] else [],
            properties=json.loads(row["properties"]) if row["properties"] else {},
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def _update_node(
        self,
        node_id: str,
        properties: dict[str, t.Any],
    ) -> GraphNodeModel:
        now = datetime.now(tz=UTC)
        async with self._connection() as conn:
            sql = (
                "UPDATE "
                + _safe_ident(self._settings.nodes_table)
                + " SET properties = :properties, updated_at = :updated_at WHERE id = :id"
            )  # nosec B608
            await conn.execute(
                text(sql),
                {
                    "id": node_id,
                    "properties": json.dumps(properties),
                    "updated_at": now,
                },
            )
        node = await self._get_node(node_id)
        if node is None:
            msg = f"Node {node_id} not found after update"
            raise RuntimeError(msg)
        return node

    async def _delete_node(self, node_id: str) -> bool:
        async with self._connection() as conn:
            sql = (
                "DELETE FROM "
                + _safe_ident(self._settings.edges_table)
                + " WHERE from_node = :id OR to_node = :id"
            )  # nosec B608
            await conn.execute(
                text(sql),
                {"id": node_id},
            )
            sql2 = (
                "DELETE FROM "
                + _safe_ident(self._settings.nodes_table)
                + " WHERE id = :id"
            )  # nosec B608
            result = await conn.execute(
                text(sql2),
                {"id": node_id},
            )
        return result.rowcount > 0

    async def _create_edge(
        self,
        edge_type: str,
        from_node_id: str,
        to_node_id: str,
        properties: dict[str, t.Any],
    ) -> GraphEdgeModel:
        edge_id = str(uuid4())
        now = datetime.now(tz=UTC)
        async with self._connection() as conn:
            sql = (
                "INSERT INTO "
                + _safe_ident(self._settings.edges_table)
                + (
                    " (id, type, from_node, to_node, properties, created_at, updated_at) "
                    "VALUES (:id, :type, :from_node, :to_node, :properties, :created_at, :updated_at)"
                )
            )  # nosec B608
            await conn.execute(
                text(sql),
                {
                    "id": edge_id,
                    "type": edge_type,
                    "from_node": from_node_id,
                    "to_node": to_node_id,
                    "properties": json.dumps(properties),
                    "created_at": now,
                    "updated_at": now,
                },
            )
        return GraphEdgeModel(
            id=edge_id,
            type=edge_type,
            from_node=from_node_id,
            to_node=to_node_id,
            properties=properties,
            created_at=now,
            updated_at=now,
        )

    async def _get_edge(self, edge_id: str) -> GraphEdgeModel | None:
        async with self._connection() as conn:
            sql = (
                "SELECT id, type, from_node, to_node, properties, created_at, updated_at FROM "
                + _safe_ident(self._settings.edges_table)
                + " WHERE id = :id"
            )  # nosec B608
            result = await conn.execute(
                text(sql),
                {"id": edge_id},
            )
            row = result.mappings().first()
        if not row:
            return None
        return GraphEdgeModel(
            id=row["id"],
            type=row["type"],
            from_node=row["from_node"],
            to_node=row["to_node"],
            properties=json.loads(row["properties"]) if row["properties"] else {},
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def _update_edge(
        self,
        edge_id: str,
        properties: dict[str, t.Any],
    ) -> GraphEdgeModel:
        now = datetime.now(tz=UTC)
        async with self._connection() as conn:
            sql = (
                "UPDATE "
                + _safe_ident(self._settings.edges_table)
                + " SET properties = :properties, updated_at = :updated_at WHERE id = :id"
            )  # nosec B608
            await conn.execute(
                text(sql),
                {
                    "id": edge_id,
                    "properties": json.dumps(properties),
                    "updated_at": now,
                },
            )
        edge = await self._get_edge(edge_id)
        if edge is None:
            msg = f"Edge {edge_id} not found after update"
            raise RuntimeError(msg)
        return edge

    async def _delete_edge(self, edge_id: str) -> bool:
        async with self._connection() as conn:
            sql = (
                "DELETE FROM "
                + _safe_ident(self._settings.edges_table)
                + " WHERE id = :id"
            )  # nosec B608
            result = await conn.execute(
                text(sql),
                {"id": edge_id},
            )
        return result.rowcount > 0

    async def _find_path(
        self,
        from_node_id: str,
        to_node_id: str,
        max_depth: int | None,
        direction: GraphTraversalDirection,
    ) -> list[GraphPathModel]:
        paths = await self._search_paths(
            from_node_id,
            to_node_id,
            max_depth=max_depth,
            direction=direction,
            shortest_only=False,
        )
        return paths

    async def _find_shortest_path(
        self,
        from_node_id: str,
        to_node_id: str,
        weight_property: str | None,
    ) -> GraphPathModel | None:
        paths = await self._search_paths(
            from_node_id,
            to_node_id,
            max_depth=None,
            direction=GraphTraversalDirection.BOTH,
            weight_property=weight_property,
            shortest_only=True,
        )
        return paths[0] if paths else None

    async def _get_neighbors(
        self,
        node_id: str,
        direction: GraphTraversalDirection,
        edge_types: list[str] | None,
    ) -> list[GraphNodeModel]:
        edges = await self._fetch_edges()
        neighbors: set[str] = set()
        for edge in edges:
            if edge_types and edge["type"] not in edge_types:
                continue
            if direction in (GraphTraversalDirection.OUT, GraphTraversalDirection.BOTH):
                if edge["from_node"] == node_id:
                    neighbors.add(edge["to_node"])
            if direction in (GraphTraversalDirection.IN, GraphTraversalDirection.BOTH):
                if edge["to_node"] == node_id:
                    neighbors.add(edge["from_node"])
        return [
            node
            for node in (await self._get_node_list(list(neighbors)))
            if node is not None
        ]

    async def _get_node_list(self, node_ids: list[str]) -> list[GraphNodeModel | None]:
        if not node_ids:
            return []
        placeholders = ", ".join(f":id_{index}" for index in range(len(node_ids)))
        params = {f"id_{index}": value for index, value in enumerate(node_ids)}
        async with self._connection() as conn:
            sql = (
                "SELECT id, labels, properties, created_at, updated_at FROM "
                + _safe_ident(self._settings.nodes_table)
                + f" WHERE id IN ({placeholders})"
            )  # nosec B608
            result = await conn.execute(
                text(sql),
                params,
            )
            rows = result.mappings().all()
        mapping = {
            row["id"]: GraphNodeModel(
                id=row["id"],
                labels=json.loads(row["labels"]) if row["labels"] else [],
                properties=json.loads(row["properties"]) if row["properties"] else {},
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        }
        return [mapping.get(node_id) for node_id in node_ids]

    async def _get_schema(self) -> GraphSchemaModel:
        async with self._connection() as conn:
            sql_nodes = (
                "SELECT DISTINCT labels FROM "
                + _safe_ident(self._settings.nodes_table)
                + " WHERE labels IS NOT NULL"
            )  # nosec B608
            node_rows = await conn.execute(text(sql_nodes))
            sql_edges = "SELECT DISTINCT type FROM " + _safe_ident(
                self._settings.edges_table
            )  # nosec B608
            edge_rows = await conn.execute(text(sql_edges))
        node_labels: set[str] = set()
        for row in node_rows.fetchall():
            if row[0]:
                node_labels.update(json.loads(row[0]))
        edge_types = [row[0] for row in edge_rows.fetchall() if row[0]]
        return GraphSchemaModel(
            node_types=sorted(node_labels),
            edge_types=sorted(set(edge_types)),
            constraints=[],
            indexes=[],
        )

    async def _create_index(
        self,
        labels: list[str],
        properties: list[str],
        index_type: str,
    ) -> bool:
        self.logger.warning(
            "Custom index creation is not supported for DuckDB PGQ adapter"
        )
        return False

    async def _drop_index(self, index_name: str) -> bool:
        self.logger.warning(
            "Custom index removal is not supported for DuckDB PGQ adapter"
        )
        return False

    async def _bulk_create_nodes(
        self,
        nodes: list[dict[str, t.Any]],
    ) -> list[GraphNodeModel]:
        return [
            await self._create_node(
                node.get("labels", []),
                node.get("properties", {}),
            )
            for node in nodes
        ]

    async def _bulk_create_edges(
        self,
        edges: list[dict[str, t.Any]],
    ) -> list[GraphEdgeModel]:
        return [
            await self._create_edge(
                edge.get("type", "RELATES"),
                edge["from_node"],
                edge["to_node"],
                edge.get("properties", {}),
            )
            for edge in edges
        ]

    async def _count_nodes(self, labels: list[str] | None) -> int:
        async with self._connection() as conn:
            result = await conn.execute(
                text(f"SELECT labels FROM {self._settings.nodes_table}")
            )
            rows = result.fetchall()
        if not labels:
            return len(rows)
        label_set = set(labels)
        count = 0
        for row in rows:
            raw = row[0]
            if not raw:
                continue
            node_labels = set(json.loads(raw))
            if label_set.issubset(node_labels):
                count += 1
        return count

    async def _count_edges(self, edge_types: list[str] | None) -> int:
        edges = await self._fetch_edges()
        if not edge_types:
            return len(edges)
        edge_type_set = set(edge_types)
        return sum(1 for edge in edges if edge["type"] in edge_type_set)

    async def _clear_graph(self) -> bool:
        async with self._connection() as conn:
            sql_edges = "DELETE FROM " + _safe_ident(self._settings.edges_table)  # nosec B608
            sql_nodes = "DELETE FROM " + _safe_ident(self._settings.nodes_table)  # nosec B608
            await conn.execute(text(sql_edges))
            await conn.execute(text(sql_nodes))
        return True

    async def _search_paths(
        self,
        start: str,
        goal: str,
        *,
        max_depth: int | None,
        direction: GraphTraversalDirection,
        weight_property: str | None = None,
        shortest_only: bool = False,
    ) -> list[GraphPathModel]:
        if start == goal:
            node = await self._get_node(start)
            if node is None:
                return []
            return [
                GraphPathModel(
                    nodes=[node],
                    edges=[],
                    length=0,
                    weight=0.0,
                )
            ]

        edges = await self._fetch_edges()
        adjacency = self._build_adjacency_list(edges, direction)
        found_paths = self._bfs_paths(adjacency, start, goal, max_depth, shortest_only)
        return await self._paths_to_models(found_paths, weight_property)

    def _build_adjacency_list(
        self, edges: list[dict[str, t.Any]], direction: GraphTraversalDirection
    ) -> dict[str, list[dict[str, t.Any]]]:
        adjacency: dict[str, list[dict[str, t.Any]]] = {}
        for edge in edges:
            adjacency.setdefault(edge["from_node"], []).append(edge)
            if direction in (GraphTraversalDirection.IN, GraphTraversalDirection.BOTH):
                reverse = edge.copy()
                reverse["from_node"] = edge["to_node"]
                reverse["to_node"] = edge["from_node"]
                adjacency.setdefault(reverse["from_node"], []).append(reverse)
        return adjacency

    def _bfs_paths(
        self,
        adjacency: dict[str, list[dict[str, t.Any]]],
        start: str,
        goal: str,
        max_depth: int | None,
        shortest_only: bool,
    ) -> list[list[dict[str, str | None]]]:
        queue: list[list[dict[str, str | None]]] = [[{"node": start, "edge": None}]]
        visited: set[str] = {start}
        found_paths: list[list[dict[str, str | None]]] = []
        while queue:
            path = queue.pop(0)
            current: str = path[-1]["node"]  # type: ignore[assignment]
            if current == goal:
                found_paths.append(path)
                if shortest_only:
                    break
                continue
            if max_depth is not None and len(path) - 1 >= max_depth:
                continue
            for edge in adjacency.get(current, []):
                neighbor = edge["to_node"]
                if neighbor not in visited or neighbor == goal:
                    new_path = path + [{"node": neighbor, "edge": edge["id"]}]
                    queue.append(new_path)
                    visited.add(neighbor)
        return found_paths

    async def _paths_to_models(
        self,
        found_paths: list[list[dict[str, str | None]]],
        weight_property: str | None,
    ) -> list[GraphPathModel]:
        graph_paths: list[GraphPathModel] = []
        for raw_path in found_paths:
            node_ids = [step["node"] for step in raw_path if step["node"] is not None]
            nodes = await self._get_node_list(node_ids)
            edge_ids = [step["edge"] for step in raw_path if step["edge"]]
            edge_models = [
                await self._get_edge(edge_id) for edge_id in edge_ids if edge_id
            ]
            weight = None
            if weight_property and edge_models:
                weight = sum(
                    e.properties.get(weight_property, 1)
                    for e in edge_models
                    if e is not None
                )
            graph_paths.append(
                GraphPathModel(
                    nodes=[n for n in nodes if n is not None],
                    edges=[e for e in edge_models if e is not None],
                    length=len(edge_models),
                    weight=weight,
                )
            )
        return graph_paths

    async def _fetch_edges(self) -> list[dict[str, t.Any]]:
        async with self._connection() as conn:
            sql = "SELECT id, type, from_node, to_node, properties FROM " + _safe_ident(
                self._settings.edges_table
            )  # nosec B608
            result = await conn.execute(text(sql))
            rows = result.mappings().all()
        return [
            {
                "id": row["id"],
                "type": row["type"],
                "from_node": row["from_node"],
                "to_node": row["to_node"],
                "properties": json.loads(row["properties"])
                if row["properties"]
                else {},
            }
            for row in rows
        ]


depends.set(Graph, "duckpgq")
