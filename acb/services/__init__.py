"""Services layer for ACB framework.

Provides comprehensive service-oriented architecture patterns with lifecycle management,
dependency injection, and performance optimization capabilities.

This module integrates with ACB's complete architecture (v0.20.0+) and
can be extended by web frameworks for additional functionality.

Features service discovery and dynamic import system similar to adapters:
- Dynamic service loading via import_service()
- Service registry with metadata support
- Auto-discovery and configuration
- Override capability through settings
"""

from contextlib import suppress

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

# Protocol interfaces for dependency injection
from .protocols import (
    # Repository
    EntityProtocol,
    # Events
    Event,
    EventHandler,
    EventServiceProtocol,
    # Performance
    PerformanceBudget,
    PerformanceServiceProtocol,
    RepositoryServiceProtocol,
    UnitOfWork,
    ValidationRule,
    ValidationServiceProtocol,
    ValidationSeverity,
    # Workflow
    WorkflowServiceProtocol,
    WorkflowState,
    WorkflowTransition,
)
from .protocols import (
    PerformanceMetrics as PerformanceMetricsProtocol,
)
from .protocols import (
    # Validation
    ValidationResult as ValidationResultProtocol,
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
    "AdapterPreInitializer",
    "CacheOptimizer",
    "ColdStartMetrics",
    "EntityProtocol",
    "Event",
    "EventHandler",
    "EventServiceProtocol",
    "FastDependencies",
    "HealthCheckMixin",
    "HealthCheckResult",
    "HealthCheckType",
    "HealthReporter",
    "HealthReporterSettings",
    "HealthService",
    "HealthServiceSettings",
    # Health monitoring
    "HealthStatus",
    "InMemoryStateManager",
    "LazyInitializer",
    "MetricsCollector",
    "OptimizationConfig",
    "PerformanceBudget",
    "PerformanceMetrics",
    "PerformanceMetricsProtocol",
    # Performance optimization
    "PerformanceOptimizer",
    "PerformanceServiceProtocol",
    "PersistentStateManager",
    "QueryOptimizer",
    # Protocol interfaces for DI
    "RepositoryServiceProtocol",
    # Serverless optimization
    "ServerlessOptimizer",
    "ServerlessOptimizerSettings",
    "ServerlessResourceCleanup",
    "Service",
    # Base service classes
    "ServiceBase",
    "ServiceCapability",
    "ServiceConfig",
    "ServiceDependencyError",
    # Service discovery system
    "ServiceMetadata",
    "ServiceMetrics",
    "ServiceNotFound",
    "ServiceNotFoundError",
    "ServiceNotInstalled",
    # Service registry
    "ServiceRegistry",
    "ServiceSettings",
    "ServiceStatus",
    "StateEntry",
    "StateManager",
    "StateManagerConfig",
    "StateManagerMetrics",
    # State management services
    "StateManagerService",
    "StateManagerSettings",
    "StateStatus",
    "StateType",
    "UnitOfWork",
    "ValidationConfig",
    "ValidationError",
    "ValidationLevel",
    "ValidationReport",
    "ValidationResult",
    "ValidationResultProtocol",
    "ValidationRule",
    # Validation services
    "ValidationService",
    "ValidationServiceProtocol",
    "ValidationSettings",
    "ValidationSeverity",
    "ValidationWarning",
    "WorkflowServiceProtocol",
    "WorkflowState",
    "WorkflowTransition",
    "apply_service_overrides",
    "create_service_metadata_template",
    "delete_state",
    "disable_service",
    "enable_service",
    "generate_service_id",
    "get_registry",
    "get_service",
    "get_service_class",
    "get_service_descriptor",
    "get_service_info",
    "get_service_override",
    "get_state",
    "get_state_service",
    "import_service",
    "initialize_services",
    "lazy_resource",
    "list_available_services",
    "list_enabled_services",
    "list_services",
    "managed_state",
    "optimize_cold_start",
    "register_service",
    "register_services",
    "sanitize_input",
    "set_state",
    "setup_services",
    "shutdown_services",
    "shutdown_services_layer",
    "try_import_service",
    "validate_contracts",
    "validate_input",
    "validate_output",
    "validate_schema",
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
            with suppress(ServiceNotFound, ServiceNotInstalled):
                service_cls = get_service_class("performance", service_name)
                service_instance = service_cls()
                await registry.register_service(service_instance)
        # Skip if not available

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


# Web framework integration helpers
# Note: FastBlocks-specific integration has been moved to the FastBlocks project
# at fastblocks.acb_integration for cleaner architectural separation
