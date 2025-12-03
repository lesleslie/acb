"""Mock Service Provider for ACB Testing.

Provides mock implementations of ACB services with realistic behavior
patterns for comprehensive testing scenarios.

Features:
- Realistic mock behavior for all service types
- Configurable response patterns
- Error simulation capabilities
- Performance metrics simulation
- Health check simulation
"""

from unittest.mock import AsyncMock

import typing as t
from contextlib import asynccontextmanager
from typing import Any

from acb.testing.discovery import (
    TestProviderCapability,
    create_test_provider_metadata_template,
)

# Provider metadata
PROVIDER_METADATA = create_test_provider_metadata_template(
    name="Mock Service Provider",
    category="mocking",
    provider_type="service_mock",
    author="ACB Testing Team",
    description="Mock implementations of ACB services with realistic behavior",
    version="1.0.0",
    capabilities=[
        TestProviderCapability.SERVICE_MOCKING,
        TestProviderCapability.ASYNC_MOCKING,
        TestProviderCapability.PERFORMANCE_TESTING,
    ],
    settings_class="MockServiceProviderSettings",
)


class MockServiceProvider:
    """Provider for mock ACB services."""

    PROVIDER_METADATA = PROVIDER_METADATA

    def __init__(self) -> None:
        self._mock_instances: dict[str, t.Any] = {}
        self._metrics: dict[str, t.Any] = {}

    def create_performance_service_mock(
        self,
        behavior: dict[str, t.Any] | None = None,
    ) -> AsyncMock:
        """Create a realistic performance service mock."""
        perf_mock = AsyncMock()
        perf_mock._metrics = {
            "cpu_usage": 45.0,
            "memory_usage": 60.0,
            "disk_usage": 75.0,
            "network_latency": 25.0,
        }

        default_behavior = {
            "optimization_delay": 0.1,  # 100ms optimization time
            "metrics_delay": 0.01,  # 10ms metrics collection
            "optimization_success_rate": 0.95,  # 95% success rate
        }

        if behavior:
            default_behavior.update(behavior)

        async def mock_optimize(
            target: str,
            parameters: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            import asyncio

            await asyncio.sleep(default_behavior["optimization_delay"])

            import random

            if random.random() > default_behavior["optimization_success_rate"]:
                msg = f"Optimization failed for {target}"
                raise RuntimeError(msg)

            # Simulate optimization results
            return {
                "target": target,
                "optimized": True,
                "improvement": random.uniform(5.0, 25.0),  # 5-25% improvement
                "time_taken": default_behavior["optimization_delay"],
                "parameters_applied": parameters or {},
            }

        async def mock_get_metrics(category: str | None = None) -> dict[str, Any]:
            import asyncio

            await asyncio.sleep(default_behavior["metrics_delay"])

            if category:
                return {category: perf_mock._metrics.get(category, 0.0)}
            return dict(perf_mock._metrics)

        async def mock_benchmark(
            operation: str,
            iterations: int = 10,
        ) -> dict[str, Any]:
            import random

            import asyncio

            results = []
            for _ in range(iterations):
                # Simulate varying performance
                execution_time = random.uniform(0.001, 0.01)  # 1-10ms
                await asyncio.sleep(execution_time)
                results.append(execution_time)

            return {
                "operation": operation,
                "iterations": iterations,
                "avg_time": sum(results) / len(results),
                "min_time": min(results),
                "max_time": max(results),
                "total_time": sum(results),
            }

        # Assign behaviors
        perf_mock.optimize.side_effect = mock_optimize
        perf_mock.get_metrics.side_effect = mock_get_metrics
        perf_mock.benchmark.side_effect = mock_benchmark

        self._mock_instances["performance"] = perf_mock
        return perf_mock

    def create_health_service_mock(
        self,
        behavior: dict[str, t.Any] | None = None,
    ) -> AsyncMock:
        """Create a realistic health service mock."""
        health_mock = AsyncMock()
        health_mock._status = "healthy"
        health_mock._uptime = 3600  # 1 hour

        default_behavior = {
            "check_delay": 0.005,  # 5ms health check
            "failure_rate": 0.02,  # 2% failure rate
            "degraded_rate": 0.05,  # 5% degraded rate
        }

        if behavior:
            default_behavior.update(behavior)

        async def mock_check_health(component: str | None = None) -> dict[str, Any]:
            import asyncio

            await asyncio.sleep(default_behavior["check_delay"])

            import random

            rand = random.random()

            if rand < default_behavior["failure_rate"]:
                status = "unhealthy"
                details = {"error": "Component failure detected"}
            elif (
                rand
                < default_behavior["failure_rate"] + default_behavior["degraded_rate"]
            ):
                status = "degraded"
                details = {"warning": "Performance degradation detected"}
            else:
                status = "healthy"
                details = {"message": "All systems operational"}

            result = {
                "status": status,
                "timestamp": "2024-01-01T12:00:00Z",
                "uptime": health_mock._uptime,
                "details": details,
            }

            if component:
                result["component"] = component

            return result

        async def mock_get_status() -> str:
            return str(health_mock._status)

        async def mock_get_uptime() -> int:
            return int(health_mock._uptime)

        # Assign behaviors
        health_mock.check.side_effect = mock_check_health
        health_mock.get_status.side_effect = mock_get_status
        health_mock.get_uptime.side_effect = mock_get_uptime

        self._mock_instances["health"] = health_mock
        return health_mock

    def create_validation_service_mock(
        self,
        behavior: dict[str, t.Any] | None = None,
    ) -> AsyncMock:
        """Create a realistic validation service mock."""
        validation_mock = AsyncMock()

        default_behavior = {
            "validation_delay": 0.002,  # 2ms validation time
            "error_rate": 0.1,  # 10% validation errors
            "sanitization_enabled": True,
        }

        if behavior:
            default_behavior.update(behavior)

        async def mock_validate(
            data: t.Any,
            schema: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            import asyncio

            await asyncio.sleep(default_behavior["validation_delay"])

            import random

            errors = []

            # Simulate validation errors
            if random.random() < default_behavior["error_rate"]:
                errors.append(
                    {
                        "field": "test_field",
                        "message": "Validation failed",
                        "code": "INVALID_FORMAT",
                    },
                )

            return {
                "valid": len(errors) == 0,
                "errors": errors,
                "data": data,
                "schema": schema,
            }

        async def mock_sanitize(data: str) -> str:
            if not default_behavior["sanitization_enabled"]:
                return data

            import asyncio

            await asyncio.sleep(default_behavior["validation_delay"] / 2)

            # Simple sanitization simulation
            sanitized = data.replace("<script>", "&lt;script&gt;")
            sanitized = sanitized.replace("javascript:", "")
            return sanitized.strip()

        async def mock_validate_schema(
            data: dict[str, Any],
            schema_name: str,
        ) -> dict[str, Any]:
            import asyncio

            await asyncio.sleep(default_behavior["validation_delay"])

            # Mock schema validation
            return {
                "valid": True,
                "schema": schema_name,
                "data": data,
                "errors": [],
            }

        # Assign behaviors
        validation_mock.validate.side_effect = mock_validate
        validation_mock.sanitize.side_effect = mock_sanitize
        validation_mock.validate_schema.side_effect = mock_validate_schema

        self._mock_instances["validation"] = validation_mock
        return validation_mock

    def create_repository_service_mock(
        self,
        behavior: dict[str, t.Any] | None = None,
    ) -> AsyncMock:
        """Create a realistic repository service mock."""
        repo_mock = AsyncMock()
        repo_mock._repositories = {}

        default_behavior = {
            "operation_delay": 0.005,  # 5ms operation time
            "transaction_delay": 0.010,  # 10ms transaction time
            "rollback_rate": 0.01,  # 1% rollback rate
        }

        if behavior:
            default_behavior.update(behavior)

        async def mock_get_repository(entity_type: str) -> AsyncMock:
            import asyncio

            await asyncio.sleep(default_behavior["operation_delay"])

            if entity_type not in repo_mock._repositories:
                # Create mock repository
                mock_repo = AsyncMock()
                mock_repo._entities = {}
                mock_repo._next_id = 1

                async def repo_find(entity_id: int) -> dict[str, Any] | None:
                    result = mock_repo._entities.get(entity_id)
                    return dict(result) if result else None

                async def repo_save(entity: dict[str, Any]) -> dict[str, Any]:
                    if "id" not in entity:
                        entity["id"] = mock_repo._next_id
                        mock_repo._next_id += 1
                    mock_repo._entities[entity["id"]] = entity
                    return entity

                async def repo_delete(entity_id: int) -> bool:
                    return mock_repo._entities.pop(entity_id, None) is not None

                mock_repo.find.side_effect = repo_find
                mock_repo.save.side_effect = repo_save
                mock_repo.delete.side_effect = repo_delete

                repo_mock._repositories[entity_type] = mock_repo

            return t.cast("AsyncMock", repo_mock._repositories[entity_type])

        async def mock_begin_transaction() -> AsyncMock:
            import asyncio

            await asyncio.sleep(default_behavior["transaction_delay"])

            transaction_mock = AsyncMock()
            transaction_mock._committed = False
            transaction_mock._rolled_back = False

            async def commit() -> None:
                import random

                if random.random() < default_behavior["rollback_rate"]:
                    msg = "Transaction failed to commit"
                    raise RuntimeError(msg)
                transaction_mock._committed = True

            async def rollback() -> None:
                transaction_mock._rolled_back = True

            transaction_mock.commit.side_effect = commit
            transaction_mock.rollback.side_effect = rollback

            return transaction_mock

        # Assign behaviors
        repo_mock.get_repository.side_effect = mock_get_repository
        repo_mock.begin_transaction.side_effect = mock_begin_transaction

        self._mock_instances["repository"] = repo_mock
        return repo_mock

    def get_mock_instance(self, service_type: str) -> AsyncMock | None:
        """Get a previously created mock instance."""
        return self._mock_instances.get(service_type)

    def reset_mocks(self) -> None:
        """Reset all mock instances."""
        for mock in self._mock_instances.values():
            mock.reset_mock()

    def update_metrics(self, service_type: str, metrics: dict[str, t.Any]) -> None:
        """Update metrics for a service type."""
        if service_type in self._mock_instances:
            mock = self._mock_instances[service_type]
            if hasattr(mock, "_metrics"):
                mock._metrics.update(metrics)

    @asynccontextmanager
    async def mock_service_context(
        self,
        service_type: str,
        behavior: dict[str, t.Any] | None = None,
    ) -> t.AsyncGenerator[AsyncMock]:
        """Context manager for temporary mock service."""
        # Create mock based on type
        if service_type == "performance":
            mock = self.create_performance_service_mock(behavior)
        elif service_type == "health":
            mock = self.create_health_service_mock(behavior)
        elif service_type == "validation":
            mock = self.create_validation_service_mock(behavior)
        elif service_type == "repository":
            mock = self.create_repository_service_mock(behavior)
        else:
            msg = f"Unknown service type: {service_type}"
            raise ValueError(msg)

        try:
            yield mock
        finally:
            # Cleanup if needed
            if hasattr(mock, "_cleanup"):
                await mock._cleanup()
