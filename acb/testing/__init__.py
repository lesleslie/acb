"""ACB Testing Infrastructure with Discovery Pattern.

Provides comprehensive testing utilities, fixtures, and helpers for ACB
applications with full discovery, registration, and override capabilities.

Features:
- ACB-specific test fixtures for adapters, services, and actions
- Mock providers with realistic behavior
- Performance testing utilities
- Async test helpers and lifecycle management
- Configuration testing support
- Service discovery integration for test infrastructure
"""

from .async_helpers import (
    AsyncTestCase,
    async_test_fixture,
    cleanup_async_tasks,
    mock_async_context,
    timeout_async_call,
    wait_for_condition,
)
from .discovery import (
    TestNotFound,
    TestNotInstalled,
    TestProvider,
    TestProviderMetadata,
    apply_test_provider_overrides,
    create_test_provider_metadata_template,
    disable_test_provider,
    enable_test_provider,
    generate_test_provider_id,
    get_test_provider_class,
    get_test_provider_descriptor,
    get_test_provider_info,
    get_test_provider_override,
    import_test_provider,
    list_available_test_providers,
    list_enabled_test_providers,
    list_test_providers,
    try_import_test_provider,
)
from .fixtures import (
    acb_action_mocks,
    acb_adapter_mocks,
    acb_config,
    acb_mock_cache,
    acb_mock_logger,
    acb_service_mocks,
    acb_settings,
    acb_temp_storage,
    acb_test_db,
    cleanup_acb_resources,
    mock_action_registry,
    mock_adapter_registry,
    mock_service_registry,
)
from .performance import (
    BenchmarkRunner,
    LoadTestRunner,
    MetricsCollector,
    PerformanceTimer,
    assert_performance_threshold,
    measure_execution_time,
    profile_memory_usage,
)
from .providers import (
    DatabaseTestProvider,
    IntegrationTestProvider,
    MockActionProvider,
    MockAdapterProvider,
    MockServiceProvider,
    PerformanceTestProvider,
    SecurityTestProvider,
)
from .utils import (
    assert_action_interface,
    assert_adapter_interface,
    assert_service_interface,
    create_test_adapter,
    create_test_config,
    create_test_service,
    run_acb_test_suite,
    setup_test_environment,
    teardown_test_environment,
)

__all__ = [
    # Async helpers
    "AsyncTestCase",
    "BenchmarkRunner",
    "DatabaseTestProvider",
    "IntegrationTestProvider",
    "LoadTestRunner",
    "MetricsCollector",
    "MockActionProvider",
    # Test providers
    "MockAdapterProvider",
    "MockServiceProvider",
    "PerformanceTestProvider",
    # Performance testing
    "PerformanceTimer",
    "SecurityTestProvider",
    "TestNotFound",
    "TestNotInstalled",
    "TestProvider",
    # Discovery system
    "TestProviderMetadata",
    "acb_action_mocks",
    "acb_adapter_mocks",
    # ACB-specific fixtures
    "acb_config",
    "acb_mock_cache",
    "acb_mock_logger",
    "acb_service_mocks",
    "acb_settings",
    "acb_temp_storage",
    "acb_test_db",
    "apply_test_provider_overrides",
    "assert_action_interface",
    # Testing utilities
    "assert_adapter_interface",
    "assert_performance_threshold",
    "assert_service_interface",
    "async_test_fixture",
    "cleanup_acb_resources",
    "cleanup_async_tasks",
    "create_test_adapter",
    "create_test_config",
    "create_test_provider_metadata_template",
    "create_test_service",
    "disable_test_provider",
    "enable_test_provider",
    "generate_test_provider_id",
    "get_test_provider_class",
    "get_test_provider_descriptor",
    "get_test_provider_info",
    "get_test_provider_override",
    "import_test_provider",
    "list_available_test_providers",
    "list_enabled_test_providers",
    "list_test_providers",
    "measure_execution_time",
    "mock_action_registry",
    "mock_adapter_registry",
    "mock_async_context",
    "mock_service_registry",
    "profile_memory_usage",
    "run_acb_test_suite",
    "setup_test_environment",
    "teardown_test_environment",
    "timeout_async_call",
    "try_import_test_provider",
    "wait_for_condition",
]

# Testing layer metadata following ACB patterns
TESTING_LAYER_VERSION = "1.0.0"
ACB_MIN_VERSION = "0.19.1"
