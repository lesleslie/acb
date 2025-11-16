from typing import Any

"""Integration Test Provider for ACB Testing.

Provides integration testing utilities for end-to-end testing
of ACB applications with external systems and services.

Features:
- End-to-end test orchestration
- External service mocking and simulation
- API integration testing
- Database integration testing
- Configuration testing across environments
"""

from unittest.mock import AsyncMock, MagicMock

import asyncio
import typing as t
from contextlib import asynccontextmanager

from acb.testing.discovery import (
    TestProviderCapability,
    create_test_provider_metadata_template,
)

# Provider metadata
PROVIDER_METADATA = create_test_provider_metadata_template(
    name="Integration Test Provider",
    category="integration",
    provider_type="integration_test",
    author="ACB Testing Team",
    description="Integration testing utilities for end-to-end ACB application testing",
    version="1.0.0",
    capabilities=[
        TestProviderCapability.INTEGRATION_TESTING,
        TestProviderCapability.CONFIG_TESTING,
        TestProviderCapability.ENVIRONMENT_ISOLATION,
        TestProviderCapability.TEMP_RESOURCE_MANAGEMENT,
    ],
    settings_class="IntegrationTestProviderSettings",
)


class IntegrationTestProvider:
    """Provider for integration testing utilities."""

    PROVIDER_METADATA = PROVIDER_METADATA

    def __init__(self) -> None:
        self._test_environments: dict[str, t.Any] = {}
        self._external_services: dict[str, t.Any] = {}
        self._integration_results: dict[str, t.Any] = {}

    async def setup_test_environment(
        self,
        environment_name: str,
        config: dict[str, Any],
    ) -> dict[str, t.Any]:
        """Setup an isolated test environment."""
        test_env: dict[str, t.Any] = {
            "name": environment_name,
            "config": config,
            "services": {},
            "adapters": {},
            "status": "initializing",
            "created_at": "2024-01-01T12:00:00Z",
        }

        # Simulate environment setup
        await asyncio.sleep(0.1)  # Setup delay

        # Initialize mock services based on config
        adapters = t.cast(dict[str, t.Any], test_env["adapters"])
        services = t.cast(dict[str, t.Any], test_env["services"])

        if "cache" in config.get("adapters", {}):
            adapters["cache"] = self._create_mock_cache()

        if "database" in config.get("adapters", {}):
            adapters["database"] = self._create_mock_database()

        if "storage" in config.get("adapters", {}):
            adapters["storage"] = self._create_mock_storage()

        # Initialize external services
        if "external_apis" in config:
            for api_name in config["external_apis"]:
                services[api_name] = self._create_mock_external_api(
                    api_name,
                )

        test_env["status"] = "ready"
        self._test_environments[environment_name] = test_env

        return test_env

    def _create_mock_cache(self) -> AsyncMock:
        """Create a mock cache for integration testing."""
        cache_mock = AsyncMock()
        cache_mock._data = {}

        async def get(key: str) -> t.Any | None:
            await asyncio.sleep(0.001)  # Simulate network delay
            return cache_mock._data.get(key)

        async def set(key: str, value: t.Any, ttl: int | None = None) -> bool:
            await asyncio.sleep(0.002)  # Simulate network delay
            cache_mock._data[key] = value
            return True

        async def delete(key: str) -> bool:
            return cache_mock._data.pop(key, None) is not None

        cache_mock.get.side_effect = get
        cache_mock.set.side_effect = set
        cache_mock.delete.side_effect = delete

        return cache_mock

    def _create_mock_database(self) -> AsyncMock:
        """Create a mock database for integration testing."""
        db_mock = AsyncMock()
        db_mock._tables = {}

        async def execute(
            query: str, params: tuple[Any, ...] | None = None
        ) -> MagicMock:
            await asyncio.sleep(0.005)  # Simulate query execution
            result = MagicMock()
            result.rowcount = 1
            return result

        async def fetch_one(
            query: str, params: tuple[Any, ...] | None = None
        ) -> dict[str, Any]:
            await asyncio.sleep(0.005)
            return {"id": 1, "data": "test_data"}

        async def fetch_all(
            query: str, params: tuple[Any, ...] | None = None
        ) -> list[dict[str, Any]]:
            await asyncio.sleep(0.01)
            return [{"id": i, "data": f"test_data_{i}"} for i in range(1, 4)]

        db_mock.execute.side_effect = execute
        db_mock.fetch_one.side_effect = fetch_one
        db_mock.fetch_all.side_effect = fetch_all

        return db_mock

    def _create_mock_storage(self) -> AsyncMock:
        """Create a mock storage for integration testing."""
        storage_mock = AsyncMock()
        storage_mock._files = {}

        async def read(path: str) -> bytes:
            await asyncio.sleep(0.01)  # Simulate file I/O
            if path not in storage_mock._files:
                msg = f"File not found: {path}"
                raise FileNotFoundError(msg)
            return bytes(storage_mock._files[path])

        async def write(path: str, data: bytes) -> bool:
            await asyncio.sleep(0.02)  # Simulate file I/O
            storage_mock._files[path] = data
            return True

        async def exists(path: str) -> bool:
            return path in storage_mock._files

        storage_mock.read.side_effect = read
        storage_mock.write.side_effect = write
        storage_mock.exists.side_effect = exists

        return storage_mock

    def _create_mock_external_api(self, api_name: str) -> AsyncMock:
        """Create a mock external API for integration testing."""
        api_mock = AsyncMock()

        async def make_request(
            method: str, endpoint: str, data: dict[str, Any] | None = None
        ) -> dict[str, Any] | None:
            # Simulate network latency
            await asyncio.sleep(0.1)

            # Mock different responses based on endpoint
            if endpoint.startswith("/health"):
                return {"status": "ok", "timestamp": "2024-01-01T12:00:00Z"}
            if endpoint.startswith("/api/users"):
                if method == "GET":
                    return {"users": [{"id": 1, "name": "Test User"}]}
                if method == "POST":
                    return {
                        "id": 2,
                        "name": data.get("name", "New User") if data else "New User",
                        "created": True,
                    }
            elif endpoint.startswith("/api/error"):
                msg = "Simulated API error"
                raise Exception(msg)
            else:
                return {
                    "message": "Mock response",
                    "endpoint": endpoint,
                    "method": method,
                }
            return None

        api_mock.request.side_effect = make_request
        return api_mock

    async def run_integration_test(
        self,
        test_name: str,
        environment_name: str,
        test_function: t.Callable[..., t.Any],
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, t.Any]:
        """Run an integration test in a specific environment."""
        if environment_name not in self._test_environments:
            msg = f"Test environment not found: {environment_name}"
            raise ValueError(msg)

        env = self._test_environments[environment_name]
        start_time = asyncio.get_event_loop().time()

        try:
            # Inject environment into test function if it accepts it
            import inspect

            sig = inspect.signature(test_function)
            if "test_env" in sig.parameters:
                kwargs["test_env"] = env

            # Run the test
            if asyncio.iscoroutinefunction(test_function):
                result = await test_function(*args, **kwargs)
            else:
                result = test_function(*args, **kwargs)

            end_time = asyncio.get_event_loop().time()
            execution_time = end_time - start_time

            test_result = {
                "test_name": test_name,
                "environment": environment_name,
                "status": "passed",
                "execution_time": execution_time,
                "result": result,
                "timestamp": "2024-01-01T12:00:00Z",
            }

        except Exception as e:
            end_time = asyncio.get_event_loop().time()
            execution_time = end_time - start_time

            test_result = {
                "test_name": test_name,
                "environment": environment_name,
                "status": "failed",
                "execution_time": execution_time,
                "error": str(e),
                "error_type": type(e).__name__,
                "timestamp": "2024-01-01T12:00:00Z",
            }

        self._integration_results[test_name] = test_result
        return test_result

    async def test_adapter_integration(
        self,
        adapter_type: str,
        environment_name: str,
    ) -> dict[str, t.Any]:
        """Test adapter integration with external systems."""
        if environment_name not in self._test_environments:
            msg = f"Test environment not found: {environment_name}"
            raise ValueError(msg)

        env = self._test_environments[environment_name]
        adapter = env["adapters"].get(adapter_type)

        if not adapter:
            return {
                "adapter_type": adapter_type,
                "status": "not_configured",
                "message": f"Adapter {adapter_type} not configured in environment {environment_name}",
            }

        test_results = []

        # Test basic operations based on adapter type
        try:
            if adapter_type == "cache":
                # Test cache operations
                await adapter.set("test_key", "test_value")
                value = await adapter.get("test_key")
                assert value == "test_value"
                await adapter.delete("test_key")
                test_results.append(
                    {"operation": "cache_operations", "status": "passed"},
                )

            elif adapter_type == "database":
                # Test database operations
                result = await adapter.execute("SELECT 1")
                assert result.rowcount >= 0
                row = await adapter.fetch_one("SELECT 1 as test")
                assert row is not None
                test_results.append(
                    {"operation": "database_operations", "status": "passed"},
                )

            elif adapter_type == "storage":
                # Test storage operations
                test_data = b"integration test data"
                await adapter.write("/test/file.txt", test_data)
                exists = await adapter.exists("/test/file.txt")
                assert exists
                read_data = await adapter.read("/test/file.txt")
                assert read_data == test_data
                test_results.append(
                    {"operation": "storage_operations", "status": "passed"},
                )

            return {
                "adapter_type": adapter_type,
                "environment": environment_name,
                "status": "passed",
                "tests": test_results,
                "timestamp": "2024-01-01T12:00:00Z",
            }

        except Exception as e:
            return {
                "adapter_type": adapter_type,
                "environment": environment_name,
                "status": "failed",
                "error": str(e),
                "error_type": type(e).__name__,
                "tests": test_results,
                "timestamp": "2024-01-01T12:00:00Z",
            }

    async def test_api_integration(
        self,
        api_name: str,
        environment_name: str,
    ) -> dict[str, t.Any]:
        """Test external API integration."""
        if environment_name not in self._test_environments:
            msg = f"Test environment not found: {environment_name}"
            raise ValueError(msg)

        env = self._test_environments[environment_name]
        api = env["services"].get(api_name)

        if not api:
            return {
                "api_name": api_name,
                "status": "not_configured",
                "message": f"API {api_name} not configured in environment {environment_name}",
            }

        test_results = []

        try:
            # Test health check
            health_response = await api.request("GET", "/health")
            assert health_response["status"] == "ok"
            test_results.append(
                {"endpoint": "/health", "method": "GET", "status": "passed"},
            )

            # Test data retrieval
            users_response = await api.request("GET", "/api/users")
            assert "users" in users_response
            test_results.append(
                {"endpoint": "/api/users", "method": "GET", "status": "passed"},
            )

            # Test data creation
            create_response = await api.request(
                "POST",
                "/api/users",
                {"name": "Integration Test User"},
            )
            assert create_response.get("created") is True
            test_results.append(
                {"endpoint": "/api/users", "method": "POST", "status": "passed"},
            )

            return {
                "api_name": api_name,
                "environment": environment_name,
                "status": "passed",
                "tests": test_results,
                "timestamp": "2024-01-01T12:00:00Z",
            }

        except Exception as e:
            return {
                "api_name": api_name,
                "environment": environment_name,
                "status": "failed",
                "error": str(e),
                "error_type": type(e).__name__,
                "tests": test_results,
                "timestamp": "2024-01-01T12:00:00Z",
            }

    async def cleanup_test_environment(self, environment_name: str) -> None:
        """Clean up a test environment."""
        if environment_name in self._test_environments:
            env = self._test_environments[environment_name]

            # Cleanup adapters
            for adapter in env["adapters"].values():
                if hasattr(adapter, "cleanup"):
                    await adapter.cleanup()

            # Cleanup external services
            for service in env["services"].values():
                if hasattr(service, "cleanup"):
                    await service.cleanup()

            # Remove from registry
            del self._test_environments[environment_name]

    @asynccontextmanager
    async def integration_test_context(
        self, environment_name: str, config: dict[str, Any]
    ) -> t.AsyncGenerator[dict[str, t.Any]]:
        """Context manager for integration testing."""
        # Setup environment
        env = await self.setup_test_environment(environment_name, config)

        try:
            yield env
        finally:
            # Cleanup environment
            await self.cleanup_test_environment(environment_name)

    def get_test_environment(self, environment_name: str) -> dict[str, t.Any] | None:
        """Get a test environment."""
        return self._test_environments.get(environment_name)

    def get_integration_results(self, test_name: str) -> dict[str, t.Any] | None:
        """Get integration test results."""
        return self._integration_results.get(test_name)

    def get_all_integration_results(self) -> dict[str, dict[str, t.Any]]:
        """Get all integration test results."""
        return self._integration_results.copy()

    def reset_integration_results(self) -> None:
        """Reset all integration test data."""
        self._integration_results.clear()
