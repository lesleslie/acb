"""Query optimization service for ACB performance layer.

Provides SQL query optimization, analysis, and performance monitoring
with integration to ACB's SQL adapters.
"""

import hashlib
import re
import time
from enum import Enum

import asyncio
import contextlib
import typing as t
from dataclasses import dataclass, field

from acb.adapters import import_adapter
from acb.config import Config
from acb.depends import Inject, depends
from acb.services._base import ServiceBase, ServiceConfig, ServiceSettings

# Service metadata for discovery system
SERVICE_METADATA: t.Any = None

try:
    from acb.services.discovery import (
        ServiceCapability,
        ServiceMetadata,
        ServiceStatus,
        generate_service_id,
    )

    SERVICE_METADATA = ServiceMetadata(
        service_id=generate_service_id(),
        name="Query Optimizer",
        category="performance",
        service_type="query_optimizer",
        version="1.0.0",
        acb_min_version="0.19.1",
        author="ACB Framework Team",
        created_date="2024-01-01T00:00:00",
        last_modified="2024-01-01T00:00:00",
        status=ServiceStatus.STABLE,
        capabilities=[
            ServiceCapability.OPTIMIZATION,
            ServiceCapability.ASYNC_OPERATIONS,
            ServiceCapability.METRICS_COLLECTION,
            ServiceCapability.BATCHING,
        ],
        description="SQL query optimization and performance analysis service",
        settings_class="QueryOptimizerSettings",
        config_example={
            "enable_query_analysis": True,
            "cache_query_plans": True,
            "optimization_interval": 600.0,
            "slow_query_threshold_ms": 1000.0,
        },
    )
except ImportError:
    # Discovery system not available
    SERVICE_METADATA = None


class QueryType(str, Enum):
    """SQL query types."""

    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    CREATE = "CREATE"
    ALTER = "ALTER"
    DROP = "DROP"
    UNKNOWN = "UNKNOWN"


@dataclass
class QueryPattern:
    """SQL query pattern analysis."""

    query_hash: str
    query_type: QueryType
    table_names: list[str] = field(default_factory=list)
    execution_count: int = 0
    total_execution_time: float = 0.0
    average_execution_time: float = 0.0
    min_execution_time: float = float("inf")
    max_execution_time: float = 0.0
    last_executed: float = 0.0
    optimization_applied: bool = False


@dataclass
class QueryOptimizationSuggestion:
    """Query optimization suggestion."""

    query_hash: str
    suggestion_type: str
    description: str
    estimated_improvement_percent: float
    confidence: float  # 0.0 to 1.0


class QueryOptimizerSettings(ServiceSettings):
    """Settings for query optimizer service."""

    analysis_enabled: bool = True
    slow_query_threshold_ms: float = 1000.0  # 1 second
    pattern_analysis_interval_seconds: float = 300.0  # 5 minutes
    max_patterns_tracked: int = 1000

    # Optimization features
    connection_pooling_enabled: bool = True
    query_caching_enabled: bool = True
    batch_optimization_enabled: bool = True

    # Analysis parameters
    minimum_executions_for_analysis: int = 5
    optimization_confidence_threshold: float = 0.7

    @depends.inject
    def __init__(self, config: Inject[Config], **values: t.Any) -> None:
        super().__init__(**values)


class QueryOptimizer(ServiceBase):
    """Service for SQL query optimization and performance analysis.

    Provides intelligent query analysis, optimization suggestions,
    and performance monitoring for database operations.
    """

    def __init__(
        self,
        service_config: ServiceConfig | None = None,
        settings: QueryOptimizerSettings | None = None,
    ) -> None:
        if service_config is None:
            service_config = ServiceConfig(
                service_id="query_optimizer",
                name="Query Optimizer",
                description="SQL query optimization and performance analysis service",
                dependencies=["sql"],
                priority=30,  # Start after SQL adapter
            )

        super().__init__(service_config, settings or QueryOptimizerSettings())
        self._settings: QueryOptimizerSettings = self._settings  # type: ignore

        self._sql_adapter: t.Any = None
        self._query_patterns: dict[str, QueryPattern] = {}
        self._analysis_task: asyncio.Task[t.Any] | None = None
        self._optimization_suggestions: list[QueryOptimizationSuggestion] = []

    async def _initialize(self) -> None:
        """Initialize the query optimizer."""
        # Get SQL adapter
        try:
            Sql = import_adapter("sql")
            self._sql_adapter = depends.get(Sql)
        except Exception as e:
            self.logger.exception(f"Failed to get SQL adapter: {e}")
            raise

        # Start analysis task
        if self._settings.analysis_enabled:
            self._analysis_task = asyncio.create_task(self._analysis_loop())

        self.logger.info("Query optimizer initialized")

    async def _shutdown(self) -> None:
        """Shutdown the query optimizer."""
        if self._analysis_task:
            self._analysis_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._analysis_task

    async def _health_check(self) -> dict[str, t.Any]:
        """Health check for query optimizer."""
        total_queries = sum(p.execution_count for p in self._query_patterns.values())
        slow_queries = sum(
            1
            for p in self._query_patterns.values()
            if p.average_execution_time > self._settings.slow_query_threshold_ms
        )

        return {
            "sql_adapter_available": self._sql_adapter is not None,
            "patterns_tracked": len(self._query_patterns),
            "total_queries_analyzed": total_queries,
            "slow_queries_detected": slow_queries,
            "optimization_suggestions": len(self._optimization_suggestions),
            "analysis_running": (
                self._analysis_task is not None and not self._analysis_task.done()
            ),
        }

    async def execute_optimized_query(
        self,
        query: str,
        parameters: dict[str, t.Any] | None = None,
        enable_caching: bool | None = None,
    ) -> t.Any:
        """Execute query with optimization tracking and suggestions.

        Args:
            query: SQL query to execute
            parameters: Query parameters
            enable_caching: Whether to use query result caching

        Returns:
            Query result
        """
        start_time = time.perf_counter()
        query_hash = self._hash_query(query)

        try:
            # Apply optimizations if available
            optimized_query = self._apply_query_optimizations(query)

            # Execute query
            if parameters:
                result = await self._sql_adapter.execute(optimized_query, parameters)
            else:
                result = await self._sql_adapter.execute(optimized_query)

            # Record execution metrics
            execution_time = (time.perf_counter() - start_time) * 1000
            await self._record_query_execution(query, query_hash, execution_time, True)

            self.increment_requests()
            return result

        except Exception as e:
            execution_time = (time.perf_counter() - start_time) * 1000
            await self._record_query_execution(query, query_hash, execution_time, False)
            self.record_error(str(e))
            raise

    async def execute_batch_optimized(
        self,
        queries: list[str],
        parameters_list: list[dict[str, t.Any]] | None = None,
    ) -> list[t.Any]:
        """Execute multiple queries with batch optimization.

        Args:
            queries: List of SQL queries
            parameters_list: List of parameter dictionaries

        Returns:
            List of query results
        """
        if not self._settings.batch_optimization_enabled:
            # Execute individually if batch optimization is disabled
            results = []
            for i, query in enumerate(queries):
                params = parameters_list[i] if parameters_list else None
                result = await self.execute_optimized_query(query, params)
                results.append(result)
            return results

        start_time = time.perf_counter()

        try:
            # Group similar queries for batch execution
            grouped_queries = self._group_similar_queries(queries, parameters_list)
            results = []

            for query_group in grouped_queries:
                # Execute each group as a batch
                group_results = await self._execute_query_group(query_group)
                results.extend(group_results)

            execution_time = (time.perf_counter() - start_time) * 1000
            self.set_custom_metric("batch_execution_time", execution_time)
            self.set_custom_metric("queries_in_batch", len(queries))

            return results

        except Exception as e:
            self.record_error(str(e))
            raise

    def get_query_patterns(self, limit: int = 100) -> list[QueryPattern]:
        """Get query patterns sorted by execution frequency.

        Args:
            limit: Maximum number of patterns to return

        Returns:
            List of query patterns
        """
        patterns = sorted(
            self._query_patterns.values(),
            key=lambda p: p.execution_count,
            reverse=True,
        )
        return patterns[:limit]

    def get_slow_queries(self, threshold_ms: float | None = None) -> list[QueryPattern]:
        """Get slow query patterns.

        Args:
            threshold_ms: Threshold in milliseconds (uses setting default if None)

        Returns:
            List of slow query patterns
        """
        threshold = threshold_ms or self._settings.slow_query_threshold_ms

        slow_patterns = [
            pattern
            for pattern in self._query_patterns.values()
            if pattern.average_execution_time > threshold
        ]

        return sorted(
            slow_patterns,
            key=lambda p: p.average_execution_time,
            reverse=True,
        )

    def get_optimization_suggestions(self) -> list[QueryOptimizationSuggestion]:
        """Get current optimization suggestions.

        Returns:
            List of optimization suggestions
        """
        return self._optimization_suggestions.copy()

    def _hash_query(self, query: str) -> str:
        """Create a hash for query pattern identification.

        Args:
            query: SQL query

        Returns:
            Query hash string
        """
        # Normalize query for pattern matching
        normalized = re.sub(
            r"\s+",
            " ",
            query.strip().upper(),
        )  # REGEX OK: Query normalization
        # Remove parameter values for pattern matching
        normalized = re.sub(
            r"'[^']*'",
            "'?'",
            normalized,
        )  # REGEX OK: Query normalization
        normalized = re.sub(
            r"\b\d+\b",
            "?",
            normalized,
        )  # REGEX OK: Query normalization

        return hashlib.md5(normalized.encode(), usedforsecurity=False).hexdigest()

    def _classify_query(self, query: str) -> QueryType:
        """Classify query type.

        Args:
            query: SQL query

        Returns:
            Query type classification
        """
        query_upper = query.strip().upper()

        if query_upper.startswith("SELECT"):
            return QueryType.SELECT
        if query_upper.startswith("INSERT"):
            return QueryType.INSERT
        if query_upper.startswith("UPDATE"):
            return QueryType.UPDATE
        if query_upper.startswith("DELETE"):
            return QueryType.DELETE
        if query_upper.startswith("CREATE"):
            return QueryType.CREATE
        if query_upper.startswith("ALTER"):
            return QueryType.ALTER
        if query_upper.startswith("DROP"):
            return QueryType.DROP

        return QueryType.UNKNOWN

    def _extract_table_names(self, query: str) -> list[str]:
        """Extract table names from query.

        Args:
            query: SQL query

        Returns:
            List of table names
        """
        # Simple regex-based table name extraction
        # This could be enhanced with a proper SQL parser
        table_patterns = [
            r"FROM\s+(\w+)",
            r"JOIN\s+(\w+)",
            r"UPDATE\s+(\w+)",
            r"INTO\s+(\w+)",
        ]

        tables = []
        query_upper = query.upper()

        for pattern in table_patterns:
            matches = re.findall(pattern, query_upper)  # REGEX OK: Table extraction
            tables.extend(matches)

        return list(set(tables))  # Remove duplicates

    def _apply_query_optimizations(self, query: str) -> str:
        """Apply basic query optimizations.

        Args:
            query: Original SQL query

        Returns:
            Optimized query
        """
        optimized = query

        # Basic optimizations that can be applied automatically
        # These are conservative optimizations that shouldn't break functionality

        # Remove unnecessary whitespace
        optimized = re.sub(
            r"\s+",
            " ",
            optimized.strip(),
        )  # REGEX OK: Query optimization

        # Add LIMIT if missing on potentially large SELECT queries
        if (
            optimized.upper().startswith("SELECT")
            and "LIMIT" not in optimized.upper()
            and "COUNT(" not in optimized.upper()
        ):
            # This is commented out as it could change query semantics
            # optimized += ' LIMIT 1000'
            pass

        return optimized

    def _group_similar_queries(
        self,
        queries: list[str],
        parameters_list: list[dict[str, t.Any]] | None = None,
    ) -> list[dict[str, t.Any]]:
        """Group similar queries for batch execution.

        Args:
            queries: List of queries
            parameters_list: List of parameter dictionaries

        Returns:
            List of query groups
        """
        groups: dict[str, dict[str, t.Any]] = {}

        for i, query in enumerate(queries):
            query_hash = self._hash_query(query)
            params = parameters_list[i] if parameters_list else None

            if query_hash not in groups:
                groups[query_hash] = {
                    "template_query": query,
                    "query_hash": query_hash,
                    "executions": [],
                }

            groups[query_hash]["executions"].append(
                {"query": query, "parameters": params, "index": i},
            )

        return list(groups.values())

    async def _execute_query_group(self, query_group: dict[str, t.Any]) -> list[t.Any]:
        """Execute a group of similar queries.

        Args:
            query_group: Group of similar queries

        Returns:
            List of results in original order
        """
        results = []

        # For now, execute each query individually
        # This could be enhanced with actual batch execution for supported databases
        for execution in query_group["executions"]:
            query = execution["query"]
            parameters = execution["parameters"]

            if parameters:
                result = await self._sql_adapter.execute(query, parameters)
            else:
                result = await self._sql_adapter.execute(query)

            results.append(result)

        return results

    async def _record_query_execution(
        self,
        query: str,
        query_hash: str,
        execution_time: float,
        success: bool,
    ) -> None:
        """Record query execution metrics.

        Args:
            query: Original SQL query
            query_hash: Query hash for pattern matching
            execution_time: Execution time in milliseconds
            success: Whether execution was successful
        """
        if query_hash not in self._query_patterns:
            self._query_patterns[query_hash] = QueryPattern(
                query_hash=query_hash,
                query_type=self._classify_query(query),
                table_names=self._extract_table_names(query),
            )

        pattern = self._query_patterns[query_hash]
        pattern.execution_count += 1
        pattern.total_execution_time += execution_time
        pattern.average_execution_time = (
            pattern.total_execution_time / pattern.execution_count
        )
        pattern.min_execution_time = min(pattern.min_execution_time, execution_time)
        pattern.max_execution_time = max(pattern.max_execution_time, execution_time)
        pattern.last_executed = time.time()

        # Limit the number of patterns we track
        if len(self._query_patterns) > self._settings.max_patterns_tracked:
            # Remove least frequently used patterns
            sorted_patterns = sorted(
                self._query_patterns.items(),
                key=lambda x: x[1].execution_count,
            )
            # Remove bottom 10%
            remove_count = len(sorted_patterns) // 10
            for query_hash, _ in sorted_patterns[:remove_count]:
                del self._query_patterns[query_hash]

    async def _analysis_loop(self) -> None:
        """Main query analysis loop."""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(self._settings.pattern_analysis_interval_seconds)
                if self._shutdown_event.is_set():
                    break

                await self._analyze_query_patterns()
                await self._generate_optimization_suggestions()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.exception(f"Query analysis loop error: {e}")
                await asyncio.sleep(60)  # Wait before retrying

    async def _analyze_query_patterns(self) -> None:
        """Analyze query patterns for optimization opportunities."""
        patterns_analyzed = 0

        for pattern in self._query_patterns.values():
            if pattern.execution_count < self._settings.minimum_executions_for_analysis:
                continue

            # Identify slow queries
            if pattern.average_execution_time > self._settings.slow_query_threshold_ms:
                self.logger.info(
                    f"Slow query detected: {pattern.query_hash} "
                    f"(avg: {pattern.average_execution_time:.2f}ms)",
                )

            patterns_analyzed += 1

        self.set_custom_metric("patterns_analyzed", patterns_analyzed)

    async def _generate_optimization_suggestions(self) -> None:
        """Generate optimization suggestions based on query patterns."""
        new_suggestions = []

        for pattern in self._query_patterns.values():
            if (
                pattern.execution_count < self._settings.minimum_executions_for_analysis
                or pattern.optimization_applied
            ):
                continue

            # Generate suggestions based on pattern analysis
            if pattern.query_type == QueryType.SELECT:
                if (
                    pattern.average_execution_time
                    > self._settings.slow_query_threshold_ms
                ):
                    suggestion = QueryOptimizationSuggestion(
                        query_hash=pattern.query_hash,
                        suggestion_type="index_recommendation",
                        description=f"Consider adding indexes for tables: {', '.join(pattern.table_names)}",
                        estimated_improvement_percent=30.0,
                        confidence=0.8,
                    )
                    new_suggestions.append(suggestion)

            elif pattern.query_type in (QueryType.INSERT, QueryType.UPDATE):
                if pattern.execution_count > 100:  # Frequent write operations
                    suggestion = QueryOptimizationSuggestion(
                        query_hash=pattern.query_hash,
                        suggestion_type="batch_processing",
                        description="Consider batching these operations for better performance",
                        estimated_improvement_percent=40.0,
                        confidence=0.9,
                    )
                    new_suggestions.append(suggestion)

        # Filter suggestions by confidence threshold
        self._optimization_suggestions = [
            s
            for s in new_suggestions
            if s.confidence >= self._settings.optimization_confidence_threshold
        ]

        if new_suggestions:
            self.logger.info(
                f"Generated {len(new_suggestions)} optimization suggestions",
            )
            self.set_custom_metric(
                "optimization_suggestions_generated",
                len(new_suggestions),
            )
