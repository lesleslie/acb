"""Unit tests for QueryOptimizer core logic and helpers."""

from __future__ import annotations

import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typing import Any

from acb.services.performance.query import (
    QueryOptimizer,
    QueryOptimizerSettings,
    QueryPattern,
    QueryType,
)


@pytest.mark.unit
def test_classify_extract_and_hash() -> None:
    qo = QueryOptimizer()

    # Classification
    assert qo._classify_query("select * from t") is QueryType.SELECT  # type: ignore[attr-defined]
    assert qo._classify_query("INSERT INTO t VALUES (1)") is QueryType.INSERT  # type: ignore[attr-defined]
    assert qo._classify_query("update t set a=1") is QueryType.UPDATE  # type: ignore[attr-defined]
    assert qo._classify_query("delete from t") is QueryType.DELETE  # type: ignore[attr-defined]
    assert qo._classify_query("create table x (a int)") is QueryType.CREATE  # type: ignore[attr-defined]
    assert qo._classify_query("drop table x") is QueryType.DROP  # type: ignore[attr-defined]
    assert qo._classify_query("unknown stuff") is QueryType.UNKNOWN  # type: ignore[attr-defined]

    # Table extraction
    tables = qo._extract_table_names("select * from users join orders on 1=1")  # type: ignore[attr-defined]
    assert set(tables) >= {"USERS", "ORDERS"}

    # Hash normalization removes whitespace and literals/digits
    # Keep spacing around '=' consistent to match implementation
    h1 = qo._hash_query(" select  * from users where id=123 and name='x' ")  # type: ignore[attr-defined]
    h2 = qo._hash_query("SELECT *  FROM users WHERE id=456 AND NAME='y'")  # type: ignore[attr-defined]
    assert h1 == h2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_optimized_query_success_and_error() -> None:
    qo = QueryOptimizer()
    qo.logger = MagicMock()

    # Mock SQL adapter
    sql = AsyncMock()
    sql.execute = AsyncMock(side_effect=[{"rowcount": 1}, RuntimeError("boom")])
    qo._sql_adapter = sql

    # Success path
    res = await qo.execute_optimized_query("select * from users where id=1", {})
    assert res == {"rowcount": 1}
    # Pattern should be recorded
    assert len(qo._query_patterns) == 1
    pattern = next(iter(qo._query_patterns.values()))
    assert pattern.query_type is QueryType.SELECT
    assert "USERS" in pattern.table_names

    # Error path: re-raises and records error
    with pytest.raises(RuntimeError, match="boom"):
        await qo.execute_optimized_query("select * from users where id=2", {})
    assert qo.metrics.errors_count >= 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_batch_optimized_disabled_and_enabled() -> None:
    # Disabled batch optimization executes queries individually
    st = QueryOptimizerSettings(batch_optimization_enabled=False)
    qo = QueryOptimizer(settings=st)

    async def fake_exec(query: str, params: dict[str, Any] | None = None) -> Any:
        return {"q": re.sub(r"\s+", " ", query.strip())}

    with patch.object(
        qo, "execute_optimized_query", new=AsyncMock(side_effect=fake_exec)
    ) as mocked:
        results = await qo.execute_batch_optimized(
            ["select 1", "select 2"],
            [{}, {}],
        )
        assert len(results) == 2
        assert mocked.await_count == 2

    # Enabled batch optimization groups similar queries and uses adapter.execute
    qo2 = QueryOptimizer()
    sql = AsyncMock()
    sql.execute = AsyncMock(side_effect=["r1", "r2", "r3"])  # per execution
    qo2._sql_adapter = sql
    res2 = await qo2.execute_batch_optimized(
        [
            "SELECT * FROM users WHERE id=1",
            " select  * from users where id=2 ",  # similar after normalization
            "SELECT * FROM orders WHERE id=3",
        ],
        [{}, {}, {}],
    )
    assert res2 == ["r1", "r2", "r3"]
    assert sql.execute.await_count == 3


@pytest.mark.unit
def test_get_query_patterns_and_slow_queries() -> None:
    qo = QueryOptimizer()

    # Seed patterns
    p1 = QueryPattern(
        query_hash="a",
        query_type=QueryType.SELECT,
        table_names=["T"],
        execution_count=10,
        total_execution_time=2000,
        average_execution_time=200.0,
        min_execution_time=100.0,
        max_execution_time=300.0,
    )
    p2 = QueryPattern(
        query_hash="b",
        query_type=QueryType.INSERT,
        table_names=["T"],
        execution_count=5,
        total_execution_time=6000,
        average_execution_time=1200.0,
        min_execution_time=1100.0,
        max_execution_time=1300.0,
    )
    qo._query_patterns = {"a": p1, "b": p2}

    top = qo.get_query_patterns(limit=1)
    assert len(top) == 1 and top[0].execution_count >= 5

    slows = qo.get_slow_queries(threshold_ms=500)
    assert len(slows) == 1 and slows[0].query_hash == "b"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_suggestions_and_pattern_limits() -> None:
    st = QueryOptimizerSettings(
        minimum_executions_for_analysis=2,
        optimization_confidence_threshold=0.7,
        max_patterns_tracked=3,
    )
    qo = QueryOptimizer(settings=st)

    # Add patterns above analysis threshold
    qo._query_patterns = {
        "s": QueryPattern(
            query_hash="s",
            query_type=QueryType.SELECT,
            table_names=["USERS"],
            execution_count=5,
            total_execution_time=6000,
            average_execution_time=1500.0,
            min_execution_time=1400.0,
            max_execution_time=1600.0,
        ),
        "w": QueryPattern(
            query_hash="w",
            query_type=QueryType.INSERT,
            table_names=["ORDERS"],
            execution_count=150,
            total_execution_time=15000,
            average_execution_time=100.0,
            min_execution_time=50.0,
            max_execution_time=200.0,
        ),
    }

    # Generate suggestions (both should pass confidence threshold)
    await qo._generate_optimization_suggestions()  # type: ignore[attr-defined]
    suggestions = qo.get_optimization_suggestions()
    types = {s.suggestion_type for s in suggestions}
    assert {"index_recommendation", "batch_processing"} <= types

    # Add many patterns to exceed max_patterns_tracked and trigger pruning
    for i in range(12):
        q = f"SELECT * FROM t{i}"
        h = qo._hash_query(q)  # type: ignore[attr-defined]
        await qo._record_query_execution(q, h, execution_time=10.0, success=True)  # type: ignore[attr-defined]

    assert len(qo._query_patterns) <= 12  # pruning removes at least bottom 10%


@pytest.mark.unit
def test_apply_query_optimizations_whitespace_only() -> None:
    qo = QueryOptimizer()
    q = "  SELECT   *   FROM   users  "
    optimized = qo._apply_query_optimizations(q)  # type: ignore[attr-defined]
    assert optimized == "SELECT * FROM users"
