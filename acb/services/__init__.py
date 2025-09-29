"""Services layer for ACB framework.

Provides service-oriented architecture patterns with lifecycle management,
dependency injection, and performance optimization capabilities.

This module integrates with ACB's simplified architecture (v0.19.1+) and
provides seamless integration with FastBlocks web framework.

Features service discovery and dynamic import system similar to adapters:
- Dynamic service loading via import_service()
- Service registry with metadata support
- Auto-discovery and configuration
- Override capability through settings
"""

from ._base import (
    ServiceBase,
    ServiceConfig,
    ServiceMetrics,
    ServiceSettings,
    ServiceStatus,
)

# Service discovery system
from .discovery import (
    Service,
    ServiceCapability,
    ServiceMetadata,
    ServiceNotFound,
    ServiceNotInstalled,
    apply_service_overrides,
    create_service_metadata_template,
    disable_service,
    enable_service,
    generate_service_id,
    get_service_class,
    get_service_descriptor,
    get_service_info,
    get_service_override,
    import_service,
    list_available_services,
    list_enabled_services,
    list_services,
    register_services,
    try_import_service,
)
from .health import (
    HealthCheckMixin,
    HealthCheckResult,
    HealthCheckType,
    HealthReporter,
    HealthReporterSettings,
    HealthService,
    HealthServiceSettings,
    HealthStatus,
)
from .performance import (
    AdapterPreInitializer,
    CacheOptimizer,
    ColdStartMetrics,
    FastDependencies,
    LazyInitializer,
    MetricsCollector,
    OptimizationConfig,
    PerformanceMetrics,
    PerformanceOptimizer,
    QueryOptimizer,
    ServerlessOptimizer,
    ServerlessOptimizerSettings,
    ServerlessResourceCleanup,
    lazy_resource,
    optimize_cold_start,
)
from .registry import (
    ServiceDependencyError,
    ServiceNotFoundError,
    ServiceRegistry,
    get_registry,
    get_service,
    initialize_services,
    register_service,
    shutdown_services,
)
from .state import (
    InMemoryStateManager,
    PersistentStateManager,
    StateEntry,
    StateManager,
    StateManagerConfig,
    StateManagerMetrics,
    StateManagerService,
    StateManagerSettings,
    StateStatus,
    StateType,
    delete_state,
    get_state,
    get_state_service,
    managed_state,
    set_state,
)
from .validation import (
    ValidationConfig,
    ValidationError,
    ValidationLevel,
    ValidationReport,
    ValidationResult,
    ValidationService,
    ValidationSettings,
    ValidationWarning,
    sanitize_input,
    validate_contracts,
    validate_input,
    validate_output,
    validate_schema,
)

__all__ = [
    # Base service classes
    "ServiceBase",
    "ServiceConfig",
    "ServiceSettings",
    "ServiceStatus",
    "ServiceMetrics",
    # Service registry
    "ServiceRegistry",
    "ServiceNotFoundError",
    "ServiceDependencyError",
    "get_registry",
    "register_service",
    "get_service",
    "initialize_services",
    "shutdown_services",
    "setup_services",
    "shutdown_services_layer",
    "setup_fastblocks_services",
    # Performance optimization
    "PerformanceOptimizer",
    "OptimizationConfig",
    "MetricsCollector",
    "PerformanceMetrics",
    "CacheOptimizer",
    "QueryOptimizer",
    # Serverless optimization
    "ServerlessOptimizer",
    "ServerlessOptimizerSettings",
    "ColdStartMetrics",
    "LazyInitializer",
    "AdapterPreInitializer",
    "FastDependencies",
    "ServerlessResourceCleanup",
    "lazy_resource",
    "optimize_cold_start",
    # Health monitoring
    "HealthStatus",
    "HealthCheckType",
    "HealthCheckResult",
    "HealthCheckMixin",
    "HealthReporter",
    "HealthReporterSettings",
    "HealthService",
    "HealthServiceSettings",
    # Validation services
    "ValidationService",
    "ValidationConfig",
    "ValidationSettings",
    "ValidationLevel",
    "ValidationResult",
    "ValidationReport",
    "ValidationError",
    "ValidationWarning",
    "validate_input",
    "validate_output",
    "sanitize_input",
    "validate_schema",
    "validate_contracts",
    # State management services
    "StateManagerService",
    "StateManagerSettings",
    "StateManagerConfig",
    "StateManagerMetrics",
    "StateManager",
    "InMemoryStateManager",
    "PersistentStateManager",
    "StateEntry",
    "StateType",
    "StateStatus",
    "get_state_service",
    "get_state",
    "set_state",
    "delete_state",
    "managed_state",
    # Service discovery system
    "ServiceMetadata",
    "ServiceCapability",
    "Service",
    "ServiceNotFound",
    "ServiceNotInstalled",
    "generate_service_id",
    "create_service_metadata_template",
    "import_service",
    "try_import_service",
    "get_service_class",
    "register_services",
    "list_services",
    "list_available_services",
    "list_enabled_services",
    "get_service_info",
    "enable_service",
    "disable_service",
    "get_service_descriptor",
    "get_service_override",
    "apply_service_overrides",
]


# Service layer metadata following ACB patterns
SERVICE_LAYER_VERSION = "1.0.0"
ACB_MIN_VERSION = "0.19.1"


# Integration helpers for ACB applications
async def setup_services(enable_health_monitoring: bool = True) -> ServiceRegistry:
    """Setup and initialize the services layer.

    This is a convenience function for ACB applications to quickly
    set up the services layer with common performance services and
    health monitoring using the new service discovery system.

    Args:
        enable_health_monitoring: Whether to enable health monitoring

    Returns:
        Initialized service registry
    """
    from acb.depends import depends

    registry = get_registry()

    # Enable services for auto-discovery
    enable_service("performance", "performance_optimizer")
    enable_service("performance", "metrics_collector")
    enable_service("performance", "cache_optimizer")
    enable_service("performance", "query_optimizer")
    enable_service("validation")

    if enable_health_monitoring:
        enable_service("health")

    # Register services using discovery system
    try:
        # Register performance services using discovery
        performance_services = [
            "performance_optimizer",
            "metrics_collector",
            "cache_optimizer",
            "query_optimizer",
        ]
        for service_name in performance_services:
            try:
                service_cls = get_service_class("performance", service_name)
                service_instance = service_cls()
                await registry.register_service(service_instance)
            except (ServiceNotFound, ServiceNotInstalled):
                pass  # Skip if not available

        # Register validation service
        validation_service_cls = import_service("validation")
        validation_service = validation_service_cls()
        await registry.register_service(validation_service)

        # Register health monitoring service if enabled
        if enable_health_monitoring:
            health_service_cls = import_service("health")
            health_service = health_service_cls()
            await registry.register_service(health_service)

    except (ServiceNotFound, ServiceNotInstalled):
        # Fallback to manual instantiation for compatibility
        performance_optimizer = PerformanceOptimizer()
        metrics_collector = MetricsCollector()
        cache_optimizer = CacheOptimizer()
        query_optimizer = QueryOptimizer()
        validation_service = ValidationService()

        await registry.register_service(performance_optimizer)
        await registry.register_service(metrics_collector)
        await registry.register_service(cache_optimizer)
        await registry.register_service(query_optimizer)
        await registry.register_service(validation_service)

        if enable_health_monitoring:
            health_service = HealthService()
            await registry.register_service(health_service)

    # Initialize all services
    await registry.initialize_all()

    # Register registry itself with ACB dependency injection
    depends.set(ServiceRegistry, registry)

    return registry


async def shutdown_services_layer() -> None:
    """Shutdown the entire services layer.

    This ensures proper cleanup of all services and resources.
    """
    registry = get_registry()
    await registry.shutdown_all()


# FastBlocks integration helpers
def create_fastblocks_service_config() -> dict[str, bool]:
    """Create service configuration optimized for FastBlocks.

    Returns:
        Configuration dictionary for FastBlocks applications
    """
    return {
        "performance_optimizer": True,
        "metrics_collector": True,
        "cache_optimizer": True,
        "query_optimizer": True,
        "health_monitoring": True,
        "htmx_optimization": True,
        "template_caching": True,
        "response_compression": True,
    }


async def setup_fastblocks_services() -> ServiceRegistry:
    """Setup services layer optimized for FastBlocks applications.

    This includes performance optimization and health monitoring
    configured for typical FastBlocks usage patterns.

    Returns:
        Configured service registry for FastBlocks
    """
    registry = await setup_services(enable_health_monitoring=True)

    # Get the health service for FastBlocks-specific configuration
    from contextlib import suppress

    with suppress(Exception):
        health_service = await registry.get_service("health_service")
        # FastBlocks applications typically want health endpoints enabled
        if hasattr(health_service, "_settings"):
            health_service._settings.expose_health_endpoint = True

    return registry
