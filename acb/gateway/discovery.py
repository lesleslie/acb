"""Gateway Discovery and Dynamic Import System.

Provides gateway discovery, registration, and dynamic import capabilities
that mirror the adapter pattern in ACB. This enables gateways to be
discoverable, registerable, and overridable through configuration.

Features:
- Dynamic gateway loading via import_gateway()
- Gateway registry with metadata support
- Auto-discovery and configuration
- Override capability through settings
- Thread-safe registry using ContextVar
"""

import typing as t
from contextvars import ContextVar
from datetime import datetime
from enum import Enum
from functools import lru_cache
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# Gateway discovery system imports
uuid_lib: t.Any
try:
    import uuid_utils

    _uuid7_available = True
    uuid_lib = uuid_utils
except ImportError:
    import uuid

    _uuid7_available = False
    uuid_lib = uuid


class GatewayStatus(Enum):
    """Gateway development/stability status."""

    ALPHA = "alpha"
    BETA = "beta"
    STABLE = "stable"
    DEPRECATED = "deprecated"
    EXPERIMENTAL = "experimental"


class GatewayCapability(Enum):
    """Gateway capability enumeration."""

    # Core gateway capabilities
    RATE_LIMITING = "rate_limiting"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    REQUEST_VALIDATION = "request_validation"
    RESPONSE_VALIDATION = "response_validation"
    ROUTING = "routing"
    LOAD_BALANCING = "load_balancing"

    # Security capabilities
    API_KEY_MANAGEMENT = "api_key_management"
    JWT_VALIDATION = "jwt_validation"
    OAUTH_INTEGRATION = "oauth_integration"
    CORS_HANDLING = "cors_handling"
    SECURITY_HEADERS = "security_headers"
    IP_FILTERING = "ip_filtering"
    DDoS_PROTECTION = "ddos_protection"

    # Analytics and monitoring
    USAGE_TRACKING = "usage_tracking"
    ANALYTICS_COLLECTION = "analytics_collection"
    METRICS_REPORTING = "metrics_reporting"
    REQUEST_LOGGING = "request_logging"
    ERROR_TRACKING = "error_tracking"
    PERFORMANCE_MONITORING = "performance_monitoring"

    # Caching and optimization
    RESPONSE_CACHING = "response_caching"
    COMPRESSION = "compression"
    CDN_INTEGRATION = "cdn_integration"
    CONNECTION_POOLING = "connection_pooling"

    # Multi-tenancy
    TENANT_ISOLATION = "tenant_isolation"
    TENANT_ROUTING = "tenant_routing"
    QUOTA_ENFORCEMENT = "quota_enforcement"
    BILLING_INTEGRATION = "billing_integration"

    # Advanced features
    CIRCUIT_BREAKER = "circuit_breaker"
    RETRY_LOGIC = "retry_logic"
    HEALTH_CHECKS = "health_checks"
    SERVICE_DISCOVERY = "service_discovery"
    WEBSOCKET_SUPPORT = "websocket_support"
    GRAPHQL_SUPPORT = "graphql_support"
    STREAMING_SUPPORT = "streaming_support"

    # Integration capabilities
    WEBHOOK_HANDLING = "webhook_handling"
    EVENT_STREAMING = "event_streaming"
    MESSAGE_QUEUING = "message_queuing"
    DATABASE_INTEGRATION = "database_integration"


class GatewayMetadata(BaseModel):
    """Gateway metadata for discovery and registration."""

    gateway_id: UUID = Field(description="UUID7 identifier for this gateway")

    name: str = Field(description="Human-readable gateway name")
    category: str = Field(
        description="Gateway category (cloud, enterprise, standalone, etc.)",
    )
    gateway_type: str = Field(
        description="Gateway type (kong, istio, envoy, nginx, custom, etc.)",
    )

    version: str = Field(description="Semantic version of this gateway")
    acb_min_version: str = Field(description="Minimum ACB version required")
    acb_max_version: str | None = Field(
        default=None,
        description="Maximum ACB version supported",
    )

    author: str = Field(description="Primary author/maintainer")
    created_date: str = Field(description="ISO date when gateway was created")
    last_modified: str = Field(description="ISO date of last significant update")

    status: GatewayStatus = Field(description="Development/stability status")
    capabilities: list[GatewayCapability] = Field(
        default_factory=list,
        description="List of features this gateway supports",
    )

    required_packages: list[str] = Field(
        default_factory=list,
        description="External packages required for this gateway",
    )
    optional_packages: dict[str, str] = Field(
        default_factory=dict,
        description="Optional packages and their purpose",
    )

    description: str = Field(description="Brief description of gateway functionality")
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
        description="Example configuration for this gateway",
    )

    # Gateway-specific metadata
    default_port: int | None = Field(
        default=None,
        description="Default port for gateway service",
    )
    admin_port: int | None = Field(default=None, description="Admin/management port")
    supported_protocols: list[str] = Field(
        default_factory=list,
        description="Supported protocols (HTTP, HTTPS, gRPC, etc.)",
    )
    deployment_types: list[str] = Field(
        default_factory=list,
        description="Supported deployment types (docker, k8s, standalone)",
    )

    custom: dict[str, t.Any] = Field(
        default_factory=dict,
        description="Custom metadata fields",
    )

    model_config = ConfigDict(use_enum_values=True, extra="forbid")


def generate_gateway_id() -> UUID:
    """Generate a UUID for gateway identification."""
    if _uuid7_available:
        uuid_obj = uuid_lib.uuid7()
        return UUID(str(uuid_obj))
    uuid_obj = uuid_lib.uuid4()
    return UUID(str(uuid_obj))


def create_gateway_metadata_template(
    name: str,
    category: str,
    gateway_type: str,
    author: str,
    description: str,
    **kwargs: t.Any,
) -> GatewayMetadata:
    """Create a gateway metadata template."""
    now = datetime.now().isoformat()

    return GatewayMetadata(
        gateway_id=generate_gateway_id(),
        name=name,
        category=category,
        gateway_type=gateway_type,
        version=kwargs.get("version", "1.0.0"),
        acb_min_version=kwargs.get("acb_min_version", "0.19.1"),
        author=author,
        created_date=now,
        last_modified=now,
        status=kwargs.get("status", GatewayStatus.STABLE),
        description=description,
        settings_class=kwargs.get("settings_class", f"{name}Settings"),
        **{
            k: v
            for k, v in kwargs.items()
            if k not in {"version", "acb_min_version", "status", "settings_class"}
        },
    )


class GatewayNotFound(Exception):
    """Raised when a gateway cannot be found."""


class GatewayNotInstalled(Exception):
    """Raised when a gateway is not installed."""


class Gateway(BaseModel):
    """Gateway descriptor for discovery and registration."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    class_name: str
    category: str
    module: str
    enabled: bool = False
    installed: bool = False

    metadata: GatewayMetadata | None = None
    runtime_id: str | None = None

    def __hash__(self) -> int:
        base_hash = (self.name, self.class_name, self.category, self.module)
        if self.metadata:
            return hash((*base_hash, str(self.metadata.gateway_id)))
        return hash(base_hash)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Gateway):
            return False
        return (
            self.name == other.name
            and self.class_name == other.class_name
            and self.category == other.category
            and self.module == other.module
        )


# Gateway registry using ContextVar for thread safety
gateway_registry: ContextVar[list[Gateway]] = ContextVar("gateway_registry", default=[])
_enabled_gateways_cache: ContextVar[dict[str, Gateway]] = ContextVar(
    "_enabled_gateways_cache",
    default={},
)
_installed_gateways_cache: ContextVar[dict[str, Gateway]] = ContextVar(
    "_installed_gateways_cache",
    default={},
)

# Core gateways registry - static mappings like adapters
core_gateways = [
    Gateway(
        name="acb_gateway",
        module="acb.gateway.providers.acb",
        class_name="ACBGateway",
        category="standalone",
        enabled=True,
        installed=True,
    ),
    Gateway(
        name="kong_gateway",
        module="acb.gateway.providers.kong",
        class_name="KongGateway",
        category="enterprise",
        enabled=False,
        installed=False,
    ),
    Gateway(
        name="istio_gateway",
        module="acb.gateway.providers.istio",
        class_name="IstioGateway",
        category="service_mesh",
        enabled=False,
        installed=False,
    ),
    Gateway(
        name="envoy_gateway",
        module="acb.gateway.providers.envoy",
        class_name="EnvoyGateway",
        category="proxy",
        enabled=False,
        installed=False,
    ),
    Gateway(
        name="nginx_gateway",
        module="acb.gateway.providers.nginx",
        class_name="NginxGateway",
        category="reverse_proxy",
        enabled=False,
        installed=False,
    ),
    Gateway(
        name="traefik_gateway",
        module="acb.gateway.providers.traefik",
        class_name="TraefikGateway",
        category="cloud_native",
        enabled=False,
        installed=False,
    ),
    Gateway(
        name="cloudflare_gateway",
        module="acb.gateway.providers.cloudflare",
        class_name="CloudflareGateway",
        category="cloud",
        enabled=False,
        installed=False,
    ),
    Gateway(
        name="aws_api_gateway",
        module="acb.gateway.providers.aws",
        class_name="AWSAPIGateway",
        category="cloud",
        enabled=False,
        installed=False,
    ),
]


# Gateway Discovery Functions (mirrors adapter pattern)
def get_gateway_descriptor(category: str) -> Gateway | None:
    """Get gateway descriptor by category."""
    gateways = gateway_registry.get()
    for gateway in gateways:
        if gateway.category == category and gateway.enabled:
            return gateway
    return None


def list_gateways() -> list[Gateway]:
    """List all registered gateways."""
    return gateway_registry.get().copy()


def list_available_gateways() -> list[Gateway]:
    """List all available (installed) gateways."""
    return [g for g in gateway_registry.get() if g.installed]


def list_enabled_gateways() -> list[Gateway]:
    """List all enabled gateways."""
    return [g for g in gateway_registry.get() if g.enabled]


def get_gateway_class(category: str, name: str | None = None) -> type[t.Any]:
    """Get gateway class by category and optional name."""
    from importlib import import_module

    gateway = get_gateway_descriptor(category)
    if not gateway:
        msg = f"Gateway not found: {category}"
        raise GatewayNotFound(msg)

    if name and gateway.name != name:
        # Look for specific named gateway
        gateways = gateway_registry.get()
        for g in gateways:
            if g.category == category and g.name == name:
                gateway = g
                break
        else:
            msg = f"Gateway not found: {category}/{name}"
            raise GatewayNotFound(msg)

    try:
        module = import_module(gateway.module)
        cls: type[t.Any] = getattr(module, gateway.class_name)
        return cls
    except (ImportError, AttributeError) as e:
        msg = f"Gateway not available: {gateway.module}.{gateway.class_name}"
        raise GatewayNotInstalled(
            msg,
        ) from e


def try_import_gateway(category: str, name: str | None = None) -> type[t.Any] | None:
    """Try to import a gateway class, return None if not available."""
    try:
        return get_gateway_class(category, name)
    except (GatewayNotFound, GatewayNotInstalled):
        return None


def import_gateway(gateway_categories: str | list[str] | None = None) -> t.Any:
    """Import gateway(s) dynamically - main entry point for gateway discovery.

    Args:
        gateway_categories: Gateway category or list of categories

    Returns:
        Gateway class or tuple of gateway classes

    Examples:
        # Import single gateway
        ACBGateway = import_gateway("standalone")

        # Import multiple gateways
        Standalone, Enterprise = import_gateway(["standalone", "enterprise"])

        # Auto-detect from context
        gateway = import_gateway()  # Detects from variable name
    """
    if isinstance(gateway_categories, str):
        gateway = get_gateway_descriptor(gateway_categories)
        gateway_name = gateway.name if gateway else None
        gateway_class = try_import_gateway(gateway_categories, gateway_name)
        if gateway_class:
            return gateway_class
        msg = f"Gateway not found or not enabled: {gateway_categories}"
        raise GatewayNotFound(msg)

    if gateway_categories is None:
        # Try to auto-detect from calling context
        import inspect

        frame = inspect.currentframe()
        if frame and frame.f_back:
            code = frame.f_back.f_code
            # Simple heuristic: look for variable assignment
            try:
                line = frame.f_back.f_lineno
                filename = code.co_filename
                with open(filename) as f:
                    lines = f.readlines()
                    if line <= len(lines):
                        current_line = lines[line - 1].strip()
                        if "=" in current_line:
                            var_name = current_line.split("=")[0].strip().lower()
                            # Try to match variable name to gateway category
                            for gateway in gateway_registry.get():
                                if (
                                    gateway.category in var_name
                                    or gateway.name in var_name
                                ):
                                    return try_import_gateway(gateway.category)
            except (OSError, IndexError):
                pass

        msg = "Could not determine gateway category from context"
        raise ValueError(msg)

    if isinstance(gateway_categories, list):
        results = []
        for category in gateway_categories:
            gateway_class = try_import_gateway(category)
            if not gateway_class:
                msg = f"Gateway not found or not enabled: {category}"
                raise GatewayNotFound(msg)
            results.append(gateway_class)
        return tuple(results) if len(results) > 1 else results[0]

    msg = f"Invalid gateway_categories type: {type(gateway_categories)}"
    raise ValueError(msg)


def register_gateways(gateways_path: str | None = None) -> None:
    """Register gateways from a path (for discovery)."""
    # Implementation for auto-discovery could be added here
    # For now, we rely on static registration


def get_gateway_info(gateway_class: type) -> dict[str, t.Any]:
    """Get information about a gateway class."""
    info: dict[str, t.Any] = {
        "class_name": gateway_class.__name__,
        "module": gateway_class.__module__,
        "docstring": gateway_class.__doc__,
    }

    # Check for metadata
    if hasattr(gateway_class, "GATEWAY_METADATA"):
        metadata = gateway_class.GATEWAY_METADATA
        if isinstance(metadata, GatewayMetadata):
            info["metadata"] = metadata.model_dump()

    return info


# Update gateway cache
def _update_gateway_caches() -> None:
    """Update gateway caches for faster lookups."""
    gateways = gateway_registry.get()

    enabled_cache = {}
    installed_cache = {}

    for gateway in gateways:
        if gateway.enabled:
            enabled_cache[gateway.category] = gateway
        if gateway.installed:
            installed_cache[gateway.category] = gateway

    _enabled_gateways_cache.set(enabled_cache)
    _installed_gateways_cache.set(installed_cache)


# Enable gateways based on configuration
def enable_gateway(category: str, name: str | None = None) -> None:
    """Enable a gateway by category and optional name."""
    gateways = gateway_registry.get()
    for gateway in gateways:
        if gateway.category == category:
            if name is None or gateway.name == name:
                gateway.enabled = True
                break
    _update_gateway_caches()


def disable_gateway(category: str) -> None:
    """Disable a gateway by category."""
    gateways = gateway_registry.get()
    for gateway in gateways:
        if gateway.category == category:
            gateway.enabled = False
    _update_gateway_caches()


@lru_cache(maxsize=1)
def _load_gateway_settings() -> dict[str, t.Any]:
    """Load gateway configuration from settings/gateway.yml.

    Returns:
        Dictionary with gateway configuration overrides
    """
    try:
        import yaml

        # Look for gateway.yml in common locations
        settings_paths = [
            Path("settings/gateway.yml"),
            Path("gateway.yml"),
            Path.cwd() / "settings" / "gateway.yml",
            Path.cwd() / "gateway.yml",
        ]

        for settings_path in settings_paths:
            if settings_path.exists():
                content = settings_path.read_text()
                return yaml.safe_load(content) or {}

    except (ImportError, FileNotFoundError, Exception):
        # Silently ignore if settings can't be loaded
        pass

    return {}


def get_gateway_override(category: str) -> str | None:
    """Get gateway implementation override from configuration.

    Args:
        category: Gateway category (e.g., 'standalone', 'enterprise')

    Returns:
        Override gateway name or None if no override

    Example:
        # In settings/gateway.yml:
        # standalone: acb_gateway
        # enterprise: kong_gateway
        # cloud: aws_api_gateway
    """
    settings = _load_gateway_settings()
    return settings.get(category)


def apply_gateway_overrides() -> None:
    """Apply gateway configuration overrides from settings."""
    settings = _load_gateway_settings()

    if not settings:
        return

    # Apply overrides for each configured gateway
    for category, gateway_name in settings.items():
        if isinstance(gateway_name, str):
            # Enable the specified gateway for this category
            try:
                enable_gateway(category, gateway_name)
            except (GatewayNotFound, GatewayNotInstalled):
                # Gateway not available, continue with defaults
                continue


def initialize_gateway_registry() -> None:
    """Initialize the gateway registry with core gateways."""
    if not gateway_registry.get():
        gateway_registry.set(core_gateways.copy())
        _update_gateway_caches()
        # Apply any configuration overrides
        apply_gateway_overrides()


# Initialize on import
initialize_gateway_registry()
