"""ACB-specific Test Fixtures and Helpers.

Provides pytest fixtures for ACB components, adapters, and services
with proper dependency injection and resource cleanup.

Features:
- ACB adapter mocks with realistic behavior
- Service registry fixtures for testing
- Action testing utilities
- Configuration management for tests
- Automatic resource cleanup
- Database and storage test fixtures
"""

from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import contextlib
import pytest
import typing as t
from typing import Any

from acb.adapters import adapter_registry
from acb.config import Config
from acb.services.discovery import (
    disable_service,
    enable_service,
    initialize_service_registry,
    service_registry,
)

from .discovery import (
    enable_test_provider,
    initialize_test_provider_registry,
)


@pytest.fixture
def acb_config() -> Config:
    """Provide a clean ACB configuration for testing."""
    config = Config()
    # Use in-memory configuration for tests
    config._config_data = {  # type: ignore[attr-defined]
        "app": {
            "name": "test-app",
            "version": "1.0.0",
            "environment": "test",
        },
        "debug": {
            "enabled": True,
            "level": "DEBUG",
        },
    }
    return config


@pytest.fixture
def acb_settings(acb_config: Config) -> dict[str, t.Any]:
    """Provide test settings dictionary."""
    return {
        "app": {
            "name": "test-app",
            "version": "1.0.0",
            "environment": "test",
        },
        "adapters": {
            "cache": "memory",
            "storage": "memory",
            "sql": "sqlite",
        },
        "testing": {
            "mock_external_services": True,
            "use_in_memory_db": True,
            "cleanup_resources": True,
        },
    }


@pytest.fixture
def acb_adapter_mocks() -> dict[str, MagicMock]:
    """Provide mock adapters for testing."""
    cache_mock = AsyncMock()
    cache_mock.get.return_value = None
    cache_mock.set.return_value = True
    cache_mock.delete.return_value = True
    cache_mock.clear.return_value = True

    storage_mock = AsyncMock()
    storage_mock.read.return_value = b"test data"
    storage_mock.write.return_value = True
    storage_mock.exists.return_value = True
    storage_mock.delete.return_value = True

    sql_mock = AsyncMock()
    sql_mock.execute.return_value = MagicMock(rowcount=1)
    sql_mock.fetch_one.return_value = {"id": 1, "name": "test"}
    sql_mock.fetch_all.return_value = [{"id": 1, "name": "test"}]

    return {
        "cache": cache_mock,
        "storage": storage_mock,
        "sql": sql_mock,
    }


@pytest.fixture
def acb_service_mocks() -> dict[str, MagicMock]:
    """Provide mock services for testing."""
    performance_mock = AsyncMock()
    performance_mock.optimize.return_value = {"optimized": True}
    performance_mock.get_metrics.return_value = {"cpu": 50, "memory": 60}

    health_mock = AsyncMock()
    health_mock.check.return_value = {"status": "healthy", "uptime": 3600}
    health_mock.get_status.return_value = "healthy"

    validation_mock = AsyncMock()
    validation_mock.validate.return_value = {"valid": True, "errors": []}
    validation_mock.sanitize.return_value = "clean data"

    return {
        "performance": performance_mock,
        "health": health_mock,
        "validation": validation_mock,
    }


@pytest.fixture
def acb_action_mocks() -> dict[str, MagicMock]:
    """Provide mock actions for testing."""
    compress_mock = MagicMock()
    compress_mock.gzip.return_value = b"compressed"
    compress_mock.decompress.return_value = b"decompressed"

    encode_mock = MagicMock()
    encode_mock.json_encode.return_value = '{"test": true}'
    encode_mock.json_decode.return_value = {"test": True}

    hash_mock = MagicMock()
    hash_mock.blake3.return_value = "hash_value"
    hash_mock.md5.return_value = "md5_hash"

    return {
        "compress": compress_mock,
        "encode": encode_mock,
        "hash": hash_mock,
    }


@pytest.fixture
def mock_adapter_registry() -> Generator[Any]:
    """Provide a clean adapter registry for testing."""
    # Save original state
    original_registry = adapter_registry.get()

    # Initialize clean registry
    # initialize_adapter_registry()  # TODO: Function doesn't exist yet

    yield adapter_registry

    # Restore original state
    adapter_registry.set(original_registry)


@pytest.fixture
def mock_service_registry() -> Generator[Any]:
    """Provide a clean service registry for testing."""
    # Save original state
    original_registry = service_registry.get()

    # Initialize clean registry
    initialize_service_registry()

    yield service_registry

    # Restore original state
    service_registry.set(original_registry)


@pytest.fixture
def mock_action_registry() -> dict[str, Any]:
    """Provide a clean action registry for testing."""
    # Actions don't have a registry yet, but this prepares for future implementation
    return {}


@pytest.fixture
async def acb_test_db(acb_config: Config) -> AsyncGenerator[Any]:
    """Provide an in-memory test database."""
    try:
        # Import SQLite adapter for testing
        from acb.adapters.sql.sqlite import Sql as SqliteAdapter

        db = SqliteAdapter()
        # Configure for in-memory database
        db._settings = MagicMock()  # type: ignore[attr-defined]
        db._settings.database = ":memory:"  # type: ignore[attr-defined]
        db._settings.check_same_thread = False  # type: ignore[attr-defined]

        # Initialize connection
        await db._ensure_client()

        yield db

    except ImportError:
        # If SQLite adapter not available, provide mock
        mock_db = AsyncMock()
        mock_db.execute.return_value = MagicMock(rowcount=1)
        mock_db.fetch_one.return_value = {"id": 1}
        mock_db.fetch_all.return_value = [{"id": 1}]
        yield mock_db

    finally:
        # Cleanup is handled by adapter's cleanup methods
        pass


@pytest.fixture
async def acb_temp_storage(tmp_path: Path) -> AsyncGenerator[Any]:
    """Provide temporary storage for testing."""
    try:
        # Import file storage adapter for testing
        from acb.adapters.storage.file import Storage as FileAdapter

        storage = FileAdapter()
        # Configure for temporary directory
        storage._settings = MagicMock()  # type: ignore[attr-defined]
        storage._settings.base_path = str(tmp_path)  # type: ignore[attr-defined]

        # Initialize
        await storage._ensure_client()

        yield storage

    except ImportError:
        # If file adapter not available, provide mock
        mock_storage = AsyncMock()
        mock_storage.read.return_value = b"test data"
        mock_storage.write.return_value = True
        mock_storage.exists.return_value = True
        mock_storage.delete.return_value = True
        yield mock_storage


@pytest.fixture
async def acb_mock_cache() -> AsyncGenerator[Any]:
    """Provide an in-memory cache for testing."""
    try:
        # Import memory cache adapter for testing
        from acb.adapters.cache.memory import Cache as MemoryCache

        cache = MemoryCache()
        # Initialize
        await cache._ensure_client()

        yield cache

    except ImportError:
        # If cache adapter not available, provide mock
        mock_cache = AsyncMock()
        mock_cache.get.return_value = None
        mock_cache.set.return_value = True
        mock_cache.delete.return_value = True
        mock_cache.clear.return_value = True
        yield mock_cache


@pytest.fixture
def acb_mock_logger() -> MagicMock:
    """Provide a mock logger for testing."""
    logger_mock = MagicMock()
    logger_mock.info = MagicMock()
    logger_mock.debug = MagicMock()
    logger_mock.warning = MagicMock()
    logger_mock.error = MagicMock()
    logger_mock.critical = MagicMock()
    return logger_mock


@pytest.fixture
async def cleanup_acb_resources() -> AsyncGenerator[Any]:
    """Cleanup ACB resources after tests."""
    # Store resources to cleanup
    resources_to_cleanup = []

    def register_cleanup(resource: Any) -> None:
        """Register a resource for cleanup."""
        resources_to_cleanup.append(resource)

    # Provide the registration function
    yield register_cleanup

    # Cleanup all registered resources
    for resource in resources_to_cleanup:
        with contextlib.suppress(Exception):
            if hasattr(resource, "cleanup"):
                if callable(resource.cleanup):
                    await resource.cleanup()
            elif hasattr(resource, "close"):
                if callable(resource.close):
                    await resource.close()
            elif hasattr(resource, "__aexit__"):
                await resource.__aexit__(None, None, None)


@pytest.fixture(autouse=True)
def reset_dependencies() -> Generator[None]:
    """Reset dependency injection state between tests."""
    # Clear all registered dependencies
    # original_instances = depends._instances.copy()  # type: ignore[attr-defined]
    # depends._instances.clear()  # type: ignore[attr-defined]

    yield

    # Restore original instances
    # depends._instances = original_instances  # type: ignore[attr-defined]


@pytest.fixture
def enable_test_adapter() -> Generator[Any]:
    """Helper to enable adapters for testing."""
    enabled_adapters = []

    def _enable_adapter(category: str, name: str | None = None) -> str:
        # enable_adapter(category, name)  # Function doesn't exist
        enabled_adapters.append(category)
        return category

    yield _enable_adapter

    # Cleanup: disable all enabled adapters
    for _category in enabled_adapters:
        with contextlib.suppress(Exception):
            pass  # disable_adapter(category)  # Function doesn't exist


@pytest.fixture
def enable_test_service() -> Generator[Any]:
    """Helper to enable services for testing."""
    enabled_services = []

    def _enable_service(category: str, name: str | None = None) -> str:
        enable_service(category, name)
        enabled_services.append(category)
        return category

    yield _enable_service

    # Cleanup: disable all enabled services
    for category in enabled_services:
        with contextlib.suppress(Exception):
            disable_service(category)


@pytest.fixture
def enable_test_provider_fixture() -> Any:
    """Helper to enable test providers for testing."""
    enabled_providers = []

    def _enable_provider(category: str, name: str | None = None) -> str:
        enable_test_provider(category, name)
        enabled_providers.append(category)
        return category

    return _enable_provider

    # Cleanup handled by test provider registry reset


@pytest.fixture(scope="session")
def acb_test_environment() -> dict[str, Any]:
    """Setup ACB test environment once per session."""
    # Initialize all registries
    # initialize_adapter_registry()  # Function doesn't exist
    initialize_service_registry()
    initialize_test_provider_registry()

    # Setup test configuration
    return {
        "testing": {
            "enabled": True,
            "mock_external_services": True,
            "cleanup_resources": True,
        },
    }

    # Session cleanup is minimal since each test cleans up


# Async test helpers
@pytest.fixture
def async_test_timeout() -> float:
    """Provide timeout for async tests."""
    return 30.0  # 30 second timeout for async operations


@pytest.fixture
async def async_context_manager() -> Any:
    """Provide async context manager for testing."""

    class TestAsyncContext:
        async def __aenter__(self) -> Any:
            return self

        async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
            pass

    return TestAsyncContext()


# Performance testing fixtures
@pytest.fixture
def performance_threshold() -> dict[str, Any]:
    """Provide performance thresholds for testing."""
    return {
        "execution_time": 1.0,  # Maximum 1 second
        "memory_usage": 100 * 1024 * 1024,  # Maximum 100MB
        "cpu_usage": 80.0,  # Maximum 80% CPU
    }


@pytest.fixture
def benchmark_config() -> dict[str, Any]:
    """Provide benchmark configuration for testing."""
    return {
        "iterations": 10,
        "warmup_rounds": 2,
        "measure_memory": True,
        "measure_cpu": True,
        "collect_gc_stats": True,
    }
