"""Service Discovery and Dynamic Import System.

Provides service discovery, registration, and dynamic import capabilities
that mirror the adapter pattern in ACB. This enables services to be
discoverable, registerable, and overridable through configuration.

Features:
- Dynamic service loading via import_service()
- Service registry with metadata support
- Auto-discovery and configuration
- Override capability through settings
- Thread-safe registry using ContextVar
"""

from contextvars import ContextVar
from enum import Enum
from functools import lru_cache
from pathlib import Path
from uuid import UUID

import typing as t
from contextlib import suppress
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

# Service discovery system imports
uuid_lib: t.Any
try:
    import uuid_utils

    _uuid7_available = True
    uuid_lib = uuid_utils
except ImportError:
    import uuid

    _uuid7_available = False
    uuid_lib = uuid


class ServiceStatus(Enum):
    """Service development/stability status."""

    ALPHA = "alpha"
    BETA = "beta"
    STABLE = "stable"
    DEPRECATED = "deprecated"
    EXPERIMENTAL = "experimental"


class ServiceCapability(Enum):
    """Service capability enumeration."""

    # Core capabilities
    LIFECYCLE_MANAGEMENT = "lifecycle_management"
    HEALTH_MONITORING = "health_monitoring"
    METRICS_COLLECTION = "metrics_collection"
    DEPENDENCY_INJECTION = "dependency_injection"

    # Performance capabilities
    CACHING = "caching"
    OPTIMIZATION = "optimization"
    ASYNC_OPERATIONS = "async_operations"
    BATCHING = "batching"
    COLD_START_OPTIMIZATION = "cold_start_optimization"
    LAZY_LOADING = "lazy_loading"
    RESOURCE_MANAGEMENT = "resource_management"

    # Monitoring capabilities
    TRACING = "tracing"
    LOGGING = "structured_logging"
    ERROR_HANDLING = "error_handling"
    CIRCUIT_BREAKER = "circuit_breaker"
    MONITORING = "monitoring"
    RESILIENCE_PATTERNS = "resilience_patterns"

    # Validation capabilities
    SCHEMA_VALIDATION = "schema_validation"
    INPUT_SANITIZATION = "input_sanitization"
    OUTPUT_VALIDATION = "output_validation"
    CONTRACT_VALIDATION = "contract_validation"

    # State management capabilities
    STATE_MANAGEMENT = "state_management"
    PERSISTENT_STORAGE = "persistent_storage"
    STATE_SYNCHRONIZATION = "state_synchronization"
    STATE_CLEANUP = "state_cleanup"


class ServiceMetadata(BaseModel):
    """Service metadata for discovery and registration."""

    service_id: UUID = Field(description="UUID7 identifier for this service")

    name: str = Field(description="Human-readable service name")
    category: str = Field(
        description="Service category (performance, health, validation, etc.)",
    )
    service_type: str = Field(
        description="Service type (optimizer, monitor, validator, etc.)",
    )

    version: str = Field(description="Semantic version of this service")
    acb_min_version: str = Field(description="Minimum ACB version required")
    acb_max_version: str | None = Field(
        default=None,
        description="Maximum ACB version supported",
    )

    author: str = Field(description="Primary author/maintainer")
    created_date: str = Field(description="ISO date when service was created")
    last_modified: str = Field(description="ISO date of last significant update")

    status: ServiceStatus = Field(description="Development/stability status")
    capabilities: list[ServiceCapability] = Field(
        default_factory=list,
        description="List of features this service supports",
    )

    required_packages: list[str] = Field(
        default_factory=list,
        description="External packages required for this service",
    )
    optional_packages: dict[str, str] = Field(
        default_factory=dict,
        description="Optional packages and their purpose",
    )

    description: str = Field(description="Brief description of service functionality")
    documentation_url: str | None = Field(
        default=None,
        description="Link to detailed documentation",
    )
    repository_url: str | None = Field(
        default=None,
        description="Source code repository",
    )

    settings_class: str = Field(description="Name of the settings class")
    config_example: dict[str, t.Any] | None = Field(
        default=None,
        description="Example configuration for this service",
    )

    custom: dict[str, t.Any] = Field(
        default_factory=dict,
        description="Custom metadata fields",
    )

    model_config = ConfigDict(use_enum_values=True, extra="forbid")


def generate_service_id() -> UUID:
    """Generate a UUID for service identification."""
    if _uuid7_available:
        uuid_obj = uuid_lib.uuid7()
        return UUID(str(uuid_obj))
    uuid_obj = uuid_lib.uuid4()
    return UUID(str(uuid_obj))


def create_service_metadata_template(
    name: str,
    category: str,
    service_type: str,
    author: str,
    description: str,
    **kwargs: t.Any,
) -> ServiceMetadata:
    """Create a service metadata template."""
    now = datetime.now().isoformat()

    return ServiceMetadata(
        service_id=generate_service_id(),
        name=name,
        category=category,
        service_type=service_type,
        version=kwargs.get("version", "1.0.0"),
        acb_min_version=kwargs.get("acb_min_version", "0.19.1"),
        author=author,
        created_date=now,
        last_modified=now,
        status=kwargs.get("status", ServiceStatus.STABLE),
        description=description,
        settings_class=kwargs.get("settings_class", f"{name}Settings"),
        **{
            k: v
            for k, v in kwargs.items()
            if k not in {"version", "acb_min_version", "status", "settings_class"}
        },
    )


class ServiceNotFound(Exception):
    """Raised when a service cannot be found."""


class ServiceNotInstalled(Exception):
    """Raised when a service is not installed."""


class Service(BaseModel):
    """Service descriptor for discovery and registration."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    class_name: str
    category: str
    module: str
    enabled: bool = False
    installed: bool = False

    metadata: ServiceMetadata | None = None
    runtime_id: str | None = None

    def __hash__(self) -> int:
        base_hash = (self.name, self.class_name, self.category, self.module)
        if self.metadata:
            return hash((*base_hash, str(self.metadata.service_id)))
        return hash(base_hash)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Service):
            return False
        return (
            self.name == other.name
            and self.class_name == other.class_name
            and self.category == other.category
            and self.module == other.module
        )


# Service registry using ContextVar for thread safety
service_registry: ContextVar[list[Service] | None] = ContextVar(
    "service_registry",
    default=None,
)
_enabled_services_cache: ContextVar[dict[str, Service] | None] = ContextVar(
    "_enabled_services_cache",
    default=None,
)
_installed_services_cache: ContextVar[dict[str, Service] | None] = ContextVar(
    "_installed_services_cache",
    default=None,
)


def _ensure_service_registry_initialized() -> list[Service]:
    """Ensure the service registry is initialized with an empty list if needed."""
    registry = service_registry.get()
    if registry is None:
        registry = []
        service_registry.set(registry)
    return registry


def _ensure_enabled_services_cache_initialized() -> dict[str, Service]:
    """Ensure the enabled services cache is initialized with an empty dict if needed."""
    cache = _enabled_services_cache.get()
    if cache is None:
        cache = {}
        _enabled_services_cache.set(cache)
    return cache


def _ensure_installed_services_cache_initialized() -> dict[str, Service]:
    """Ensure the installed services cache is initialized with an empty dict if needed."""
    cache = _installed_services_cache.get()
    if cache is None:
        cache = {}
        _installed_services_cache.set(cache)
    return cache


# Core services registry - static mappings like adapters
core_services = [
    Service(
        name="performance_optimizer",
        module="acb.services.performance.optimizer",
        class_name="PerformanceOptimizer",
        category="performance",
        enabled=False,
        installed=True,
    ),
    Service(
        name="metrics_collector",
        module="acb.services.performance.metrics",
        class_name="MetricsCollector",
        category="performance",
        enabled=False,
        installed=True,
    ),
    Service(
        name="cache_optimizer",
        module="acb.services.performance.cache",
        class_name="CacheOptimizer",
        category="performance",
        enabled=False,
        installed=True,
    ),
    Service(
        name="query_optimizer",
        module="acb.services.performance.query",
        class_name="QueryOptimizer",
        category="performance",
        enabled=False,
        installed=True,
    ),
    Service(
        name="health_service",
        module="acb.services.health",
        class_name="HealthService",
        category="health",
        enabled=False,
        installed=True,
    ),
    Service(
        name="validation_service",
        module="acb.services.validation.service",
        class_name="ValidationService",
        category="validation",
        enabled=False,
        installed=True,
    ),
    Service(
        name="repository_service",
        module="acb.services.repository.service",
        class_name="RepositoryService",
        category="repository",
        enabled=False,
        installed=True,
    ),
    Service(
        name="error_handling_service",
        module="acb.services.error_handling",
        class_name="ErrorHandlingService",
        category="error_handling",
        enabled=False,
        installed=True,
    ),
    Service(
        name="state_manager_service",
        module="acb.services.state",
        class_name="StateManagerService",
        category="state",
        enabled=False,
        installed=True,
    ),
    Service(
        name="events_service",
        module="acb.events",
        class_name="EventsService",
        category="events",
        enabled=False,
        installed=True,
    ),
]


# Service Discovery Functions (mirrors adapter pattern)
def get_service_descriptor(category: str) -> Service | None:
    """Get service descriptor by category."""
    services = _ensure_service_registry_initialized()
    for service in services:
        if service.category == category and service.enabled:
            return service
    return None


def list_services() -> list[Service]:
    """List all registered services."""
    return _ensure_service_registry_initialized().copy()


def list_available_services() -> list[Service]:
    """List all available (installed) services."""
    return [s for s in _ensure_service_registry_initialized() if s.installed]


def list_enabled_services() -> list[Service]:
    """List all enabled services."""
    return [s for s in _ensure_service_registry_initialized() if s.enabled]


def get_service_class(category: str, name: str | None = None) -> type[t.Any]:
    """Get service class by category and optional name."""
    from importlib import import_module

    service = get_service_descriptor(category)
    if not service:
        msg = f"Service not found: {category}"
        raise ServiceNotFound(msg)

    if name and service.name != name:
        # Look for specific named service
        services = _ensure_service_registry_initialized()
        for s in services:
            if s.category == category and s.name == name:
                service = s
                break
        else:
            msg = f"Service not found: {category}/{name}"
            raise ServiceNotFound(msg)

    try:
        module = import_module(service.module)
        cls: type[t.Any] = getattr(module, service.class_name)
        return cls
    except (ImportError, AttributeError) as e:
        msg = f"Service not available: {service.module}.{service.class_name}"
        raise ServiceNotInstalled(
            msg,
        ) from e


def try_import_service(category: str, name: str | None = None) -> type[t.Any] | None:
    """Try to import a service class, return None if not available."""
    try:
        return get_service_class(category, name)
    except (ServiceNotFound, ServiceNotInstalled):
        return None


def import_service(service_categories: str | list[str] | None = None) -> t.Any:
    """Import service(s) dynamically - main entry point for service discovery.

    Args:
        service_categories: Service category or list of categories

    Returns:
        Service class or tuple of service classes

    Examples:
        # Import single service
        PerformanceOptimizer = import_service("performance")

        # Import multiple services
        Performance, Health = import_service(["performance", "health"])

        # Auto-detect from context
        health_service = import_service()  # Detects from variable name

    Complexity: 2
    """
    from acb.discovery_common import RegistryConfig, import_from_registry

    config = RegistryConfig(
        get_descriptor=get_service_descriptor,
        try_import=try_import_service,
        get_all_descriptors=_ensure_service_registry_initialized,
        not_found_exception=ServiceNotFound,
    )
    return import_from_registry(service_categories, config)


def register_services(services_path: str | None = None) -> None:
    """Register services from a path (for discovery)."""
    # Implementation for auto-discovery could be added here
    # For now, we rely on static registration


def get_service_info(service_class: type) -> dict[str, t.Any]:
    """Get information about a service class."""
    info: dict[str, t.Any] = {
        "class_name": service_class.__name__,
        "module": service_class.__module__,
        "docstring": service_class.__doc__,
    }

    # Check for metadata
    if hasattr(service_class, "SERVICE_METADATA"):
        metadata = service_class.SERVICE_METADATA
        if isinstance(metadata, ServiceMetadata):
            info["metadata"] = metadata.model_dump()

    return info


# Update service cache
def _update_service_caches() -> None:
    """Update service caches for faster lookups."""
    services = _ensure_service_registry_initialized()

    enabled_cache = {}
    installed_cache = {}

    for service in services:
        if service.enabled:
            enabled_cache[service.category] = service
        if service.installed:
            installed_cache[service.category] = service

    _enabled_services_cache.set(enabled_cache)
    _installed_services_cache.set(installed_cache)


# Enable services based on configuration
def enable_service(category: str, name: str | None = None) -> None:
    """Enable a service by category and optional name."""
    services = _ensure_service_registry_initialized()
    for service in services:
        if service.category == category:
            if name is None or service.name == name:
                service.enabled = True
                break
    _update_service_caches()


def disable_service(category: str) -> None:
    """Disable a service by category."""
    services = _ensure_service_registry_initialized()
    for service in services:
        if service.category == category:
            service.enabled = False
    _update_service_caches()


@lru_cache(maxsize=1)
def _load_service_settings() -> dict[str, t.Any]:
    """Load service configuration from settings/services.yaml.

    Returns:
        Dictionary with service configuration overrides
    """
    with suppress(ImportError, FileNotFoundError, Exception):
        import yaml

        # Look for services.yaml in common locations
        settings_paths = [
            Path("settings/services.yaml"),
            Path("services.yaml"),
            Path.cwd() / "settings" / "services.yaml",
            Path.cwd() / "services.yaml",
        ]

        for settings_path in settings_paths:
            if settings_path.exists():
                content = settings_path.read_text()
                loaded = yaml.safe_load(content)
                return dict(loaded) if loaded else {}

    return {}


def get_service_override(category: str) -> str | None:
    """Get service implementation override from configuration.

    Args:
        category: Service category (e.g., 'performance', 'health')

    Returns:
        Override service name or None if no override

    Example:
        # In settings/services.yaml:
        # performance: performance_optimizer
        # health: health_service
        # validation: validation_service
    """
    settings = _load_service_settings()
    return settings.get(category)


def apply_service_overrides() -> None:
    """Apply service configuration overrides from settings."""
    settings = _load_service_settings()

    if not settings:
        return

    # Apply overrides for each configured service
    for category, service_name in settings.items():
        if isinstance(service_name, str):
            # Enable the specified service for this category
            try:
                enable_service(category, service_name)
            except (ServiceNotFound, ServiceNotInstalled):
                # Service not available, continue with defaults
                continue


def initialize_service_registry() -> None:
    """Initialize the service registry with core services."""
    if not _ensure_service_registry_initialized():
        _ensure_service_registry_initialized().extend(core_services)
        _update_service_caches()
        # Apply any configuration overrides
        apply_service_overrides()


# Initialize on import
initialize_service_registry()
