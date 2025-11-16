"""Event Handler Discovery and Registration System.

Provides event handler discovery, registration, and dynamic import capabilities
that mirror ACB's adapter and service patterns. This enables event handlers to be
discoverable, registerable, and overridable through configuration.

Features:
- Dynamic event handler loading via import_event_handler()
- Event handler registry with metadata support
- Auto-discovery and configuration
- Override capability through settings/events.yaml
- Thread-safe registry using ContextVar
- Capability-based event processing detection
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

# Event discovery system imports
uuid_lib: t.Any
try:
    import uuid_utils

    _uuid7_available = True
    uuid_lib = uuid_utils
except ImportError:
    import uuid

    _uuid7_available = False
    uuid_lib = uuid


class EventHandlerStatus(Enum):
    """Event handler development/stability status."""

    ALPHA = "alpha"
    BETA = "beta"
    STABLE = "stable"
    DEPRECATED = "deprecated"
    EXPERIMENTAL = "experimental"


class EventCapability(Enum):
    """Event processing capability enumeration."""

    # Core event capabilities
    SYNC_PROCESSING = "sync_processing"
    ASYNC_PROCESSING = "async_processing"
    BATCH_PROCESSING = "batch_processing"
    STREAMING_PROCESSING = "streaming_processing"

    # Event routing capabilities
    TYPE_FILTERING = "type_filtering"
    CONTENT_FILTERING = "content_filtering"
    PRIORITY_HANDLING = "priority_handling"
    ROUTING_KEY_SUPPORT = "routing_key_support"

    # Delivery capabilities
    AT_LEAST_ONCE = "at_least_once"
    EXACTLY_ONCE = "exactly_once"
    FIRE_AND_FORGET = "fire_and_forget"
    ORDERED_DELIVERY = "ordered_delivery"

    # Performance capabilities
    HIGH_THROUGHPUT = "high_throughput"
    LOW_LATENCY = "low_latency"
    BACKPRESSURE_HANDLING = "backpressure_handling"
    LOAD_BALANCING = "load_balancing"

    # Integration capabilities
    MESSAGE_QUEUE_INTEGRATION = "message_queue_integration"
    STREAMING_PLATFORM_INTEGRATION = "streaming_platform_integration"
    WEBHOOK_DELIVERY = "webhook_delivery"
    DATABASE_PERSISTENCE = "database_persistence"

    # Monitoring capabilities
    METRICS_COLLECTION = "metrics_collection"
    HEALTH_MONITORING = "health_monitoring"
    TRACING = "tracing"
    LOGGING = "structured_logging"

    # Error handling capabilities
    RETRY_LOGIC = "retry_logic"
    DEAD_LETTER_QUEUE = "dead_letter_queue"
    CIRCUIT_BREAKER = "circuit_breaker"
    FALLBACK_HANDLING = "fallback_handling"

    # Security capabilities
    EVENT_ENCRYPTION = "event_encryption"
    ACCESS_CONTROL = "access_control"
    AUDIT_LOGGING = "audit_logging"
    RATE_LIMITING = "rate_limiting"


class EventMetadata(BaseModel):
    """Event handler metadata for discovery and registration."""

    handler_id: UUID = Field(description="UUID7 identifier for this event handler")

    name: str = Field(description="Human-readable handler name")
    category: str = Field(
        description="Handler category (publisher, subscriber, processor, etc.)",
    )
    handler_type: str = Field(
        description="Handler type (in_memory, redis, kafka, etc.)",
    )

    version: str = Field(description="Semantic version of this handler")
    acb_min_version: str = Field(description="Minimum ACB version required")
    acb_max_version: str | None = Field(
        default=None,
        description="Maximum ACB version supported",
    )

    author: str = Field(description="Primary author/maintainer")
    created_date: str = Field(description="ISO date when handler was created")
    last_modified: str = Field(description="ISO date of last significant update")

    status: EventHandlerStatus = Field(description="Development/stability status")
    capabilities: list[EventCapability] = Field(
        default_factory=list,
        description="List of features this handler supports",
    )

    required_packages: list[str] = Field(
        default_factory=list,
        description="External packages required for this handler",
    )
    optional_packages: dict[str, str] = Field(
        default_factory=dict,
        description="Optional packages and their purpose",
    )

    description: str = Field(description="Brief description of handler functionality")
    documentation_url: str | None = Field(
        default=None,
        description="Link to detailed documentation",
    )
    repository_url: str | None = Field(
        default=None,
        description="Source code repository",
    )

    # Event-specific metadata
    supported_event_types: list[str] = Field(
        default_factory=list,
        description="Event types this handler can process",
    )
    event_patterns: list[str] = Field(
        default_factory=list,
        description="Event patterns this handler matches",
    )
    max_concurrent: int = Field(
        default=1,
        description="Maximum concurrent event processing",
    )
    priority_levels: list[str] = Field(
        default_factory=list,
        description="Supported priority levels",
    )

    settings_class: str = Field(description="Name of the settings class")
    config_example: dict[str, t.Any] | None = Field(
        default=None,
        description="Example configuration for this handler",
    )

    custom: dict[str, t.Any] = Field(
        default_factory=dict,
        description="Custom metadata fields",
    )

    model_config = ConfigDict(use_enum_values=True, extra="forbid")


def generate_event_handler_id() -> UUID:
    """Generate a UUID for event handler identification."""
    if _uuid7_available:
        uuid_obj = uuid_lib.uuid7()
        return UUID(str(uuid_obj))
    uuid_obj = uuid_lib.uuid4()
    return UUID(str(uuid_obj))


def create_event_metadata_template(
    name: str,
    category: str,
    handler_type: str,
    author: str,
    description: str,
    **kwargs: t.Any,
) -> EventMetadata:
    """Create event handler metadata template."""
    now = datetime.now().isoformat()

    return EventMetadata(
        handler_id=generate_event_handler_id(),
        name=name,
        category=category,
        handler_type=handler_type,
        version=kwargs.get("version", "1.0.0"),
        acb_min_version=kwargs.get("acb_min_version", "0.19.1"),
        author=author,
        created_date=now,
        last_modified=now,
        status=kwargs.get("status", EventHandlerStatus.STABLE),
        description=description,
        settings_class=kwargs.get("settings_class", f"{name}Settings"),
        **{
            k: v
            for k, v in kwargs.items()
            if k not in {"version", "acb_min_version", "status", "settings_class"}
        },
    )


class EventHandlerNotFound(Exception):
    """Raised when an event handler cannot be found."""


class EventHandlerNotInstalled(Exception):
    """Raised when an event handler is not installed."""


class EventHandlerDescriptor(BaseModel):
    """Event handler descriptor for discovery and registration."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    class_name: str
    category: str
    module: str
    enabled: bool = False
    installed: bool = False

    metadata: EventMetadata | None = None
    runtime_id: str | None = None

    def __hash__(self) -> int:
        base_hash = (self.name, self.class_name, self.category, self.module)
        if self.metadata:
            return hash((*base_hash, str(self.metadata.handler_id)))
        return hash(base_hash)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, EventHandlerDescriptor):
            return False
        return (
            self.name == other.name
            and self.class_name == other.class_name
            and self.category == other.category
            and self.module == other.module
        )


# Event handler registry using ContextVar for thread safety
event_handler_registry: ContextVar[list[EventHandlerDescriptor]] = ContextVar(
    "event_handler_registry",
    default=[],
)
_enabled_handlers_cache: ContextVar[dict[str, EventHandlerDescriptor]] = ContextVar(
    "_enabled_handlers_cache",
    default={},
)
_installed_handlers_cache: ContextVar[dict[str, EventHandlerDescriptor]] = ContextVar(
    "_installed_handlers_cache",
    default={},
)

# Core event handlers registry - static mappings like adapters and services
core_event_handlers = [
    EventHandlerDescriptor(
        name="memory_publisher",
        module="acb.events.publisher",
        class_name="EventPublisher",
        category="publisher",
        enabled=False,
        installed=True,
    ),
    EventHandlerDescriptor(
        name="redis_publisher",
        module="acb.events.backends.redis",
        class_name="RedisEventPublisher",
        category="publisher",
        enabled=False,
        installed=False,  # Requires redis package
    ),
    EventHandlerDescriptor(
        name="kafka_publisher",
        module="acb.events.backends.kafka",
        class_name="KafkaEventPublisher",
        category="publisher",
        enabled=False,
        installed=False,  # Requires kafka package
    ),
    EventHandlerDescriptor(
        name="memory_subscriber",
        module="acb.events.subscriber",
        class_name="EventSubscriber",
        category="subscriber",
        enabled=False,
        installed=True,
    ),
    EventHandlerDescriptor(
        name="webhook_handler",
        module="acb.events.handlers.webhook",
        class_name="WebhookEventHandler",
        category="handler",
        enabled=False,
        installed=True,
    ),
    EventHandlerDescriptor(
        name="database_handler",
        module="acb.events.handlers.database",
        class_name="DatabaseEventHandler",
        category="handler",
        enabled=False,
        installed=True,
    ),
]


# Event Handler Discovery Functions (mirrors adapter and service patterns)
def get_event_handler_descriptor(
    category: str,
    name: str | None = None,
) -> EventHandlerDescriptor | None:
    """Get event handler descriptor by category and optional name."""
    handlers = event_handler_registry.get()
    for handler in handlers:
        if handler.category == category and handler.enabled:
            if name is None or handler.name == name:
                return handler
    return None


def list_event_handlers() -> list[EventHandlerDescriptor]:
    """List all registered event handlers."""
    return event_handler_registry.get().copy()


def list_available_event_handlers() -> list[EventHandlerDescriptor]:
    """List all available (installed) event handlers."""
    return [h for h in event_handler_registry.get() if h.installed]


def list_enabled_event_handlers() -> list[EventHandlerDescriptor]:
    """List all enabled event handlers."""
    return [h for h in event_handler_registry.get() if h.enabled]


def list_event_handlers_by_capability(
    capability: EventCapability,
) -> list[EventHandlerDescriptor]:
    """List event handlers that support a specific capability."""
    return [
        handler
        for handler in event_handler_registry.get()
        if handler.metadata and capability in handler.metadata.capabilities
    ]


def get_event_handler_class(category: str, name: str | None = None) -> type[t.Any]:
    """Get event handler class by category and optional name."""
    from importlib import import_module

    handler = get_event_handler_descriptor(category, name)
    if not handler:
        raise EventHandlerNotFound(
            f"Event handler not found: {category}" + (f"/{name}" if name else ""),
        )

    try:
        module = import_module(handler.module)
        cls: type[t.Any] = getattr(module, handler.class_name)
        return cls
    except (ImportError, AttributeError) as e:
        msg = f"Event handler not available: {handler.module}.{handler.class_name}"
        raise EventHandlerNotInstalled(
            msg,
        ) from e


def try_import_event_handler(
    category: str,
    name: str | None = None,
) -> type[t.Any] | None:
    """Try to import an event handler class, return None if not available."""
    try:
        return get_event_handler_class(category, name)
    except (EventHandlerNotFound, EventHandlerNotInstalled):
        return None


def import_event_handler(handler_categories: str | list[str] | None = None) -> t.Any:
    """Import event handler(s) dynamically - main entry point for event handler discovery.

    Args:
        handler_categories: Handler category or list of categories

    Returns:
        Handler class or tuple of handler classes

    Examples:
        # Import single handler
        EventPublisher = import_event_handler("publisher")

        # Import multiple handlers
        Publisher, Subscriber = import_event_handler(["publisher", "subscriber"])

        # Auto-detect from context
        event_publisher = import_event_handler()  # Detects from variable name

    Complexity: 2
    """
    from acb.discovery_common import RegistryConfig, import_from_registry

    config = RegistryConfig(
        get_descriptor=get_event_handler_descriptor,
        try_import=try_import_event_handler,
        get_all_descriptors=event_handler_registry.get,
        not_found_exception=EventHandlerNotFound,
    )
    return import_from_registry(handler_categories, config)


def register_event_handlers(handlers_path: str | None = None) -> None:
    """Register event handlers from a path (for discovery)."""
    # Implementation for auto-discovery could be added here
    # For now, we rely on static registration


def get_event_handler_info(handler_class: type) -> dict[str, t.Any]:
    """Get information about an event handler class."""
    info: dict[str, t.Any] = {
        "class_name": handler_class.__name__,
        "module": handler_class.__module__,
        "docstring": handler_class.__doc__,
    }

    # Check for metadata
    if hasattr(handler_class, "HANDLER_METADATA"):
        metadata = handler_class.HANDLER_METADATA
        if isinstance(metadata, EventMetadata):
            info["metadata"] = metadata.model_dump()

    return info


# Update event handler cache
def _update_event_handler_caches() -> None:
    """Update event handler caches for faster lookups."""
    handlers = event_handler_registry.get()

    enabled_cache = {}
    installed_cache = {}

    for handler in handlers:
        cache_key = f"{handler.category}:{handler.name}"
        if handler.enabled:
            enabled_cache[cache_key] = handler
        if handler.installed:
            installed_cache[cache_key] = handler

    _enabled_handlers_cache.set(enabled_cache)
    _installed_handlers_cache.set(installed_cache)


# Enable event handlers based on configuration
def enable_event_handler(category: str, name: str | None = None) -> None:
    """Enable an event handler by category and optional name."""
    handlers = event_handler_registry.get()
    for handler in handlers:
        if handler.category == category:
            if name is None or handler.name == name:
                handler.enabled = True
                break
    _update_event_handler_caches()


def disable_event_handler(category: str, name: str | None = None) -> None:
    """Disable an event handler by category and optional name."""
    handlers = event_handler_registry.get()
    for handler in handlers:
        if handler.category == category:
            if name is None or handler.name == name:
                handler.enabled = False
    _update_event_handler_caches()


@lru_cache(maxsize=1)
def _load_event_settings() -> dict[str, t.Any]:
    """Load event configuration from settings/events.yaml.

    Returns:
        Dictionary with event configuration overrides
    """
    with suppress(ImportError, FileNotFoundError, Exception):
        import yaml

        # Look for events.yaml in common locations
        settings_paths = [
            Path("settings/events.yaml"),
            Path("events.yaml"),
            Path.cwd() / "settings" / "events.yaml",
            Path.cwd() / "events.yaml",
        ]

        for settings_path in settings_paths:
            if settings_path.exists():
                content = settings_path.read_text()
                loaded = yaml.safe_load(content)
                # Ensure we always return dict[str, Any], not Any
                if loaded is None:
                    return {}
                if isinstance(loaded, dict):
                    return loaded
                return {}

    return {}


def get_event_handler_override(category: str) -> str | None:
    """Get event handler implementation override from configuration.

    Args:
        category: Handler category (e.g., 'publisher', 'subscriber')

    Returns:
        Override handler name or None if no override

    Example:
        # In settings/events.yaml:
        # publisher: memory_publisher
        # subscriber: redis_subscriber
        # processor: kafka_processor
    """
    settings = _load_event_settings()
    return settings.get(category)


def apply_event_handler_overrides() -> None:
    """Apply event handler configuration overrides from settings."""
    settings = _load_event_settings()

    if not settings:
        return

    # Apply overrides for each configured handler
    for category, handler_name in settings.items():
        if isinstance(handler_name, str):
            # Enable the specified handler for this category
            try:
                enable_event_handler(category, handler_name)
            except (EventHandlerNotFound, EventHandlerNotInstalled):
                # Handler not available, continue with defaults
                continue


def initialize_event_handler_registry() -> None:
    """Initialize the event handler registry with core handlers."""
    if not event_handler_registry.get():
        event_handler_registry.set(core_event_handlers.copy())
        _update_event_handler_caches()
        # Apply any configuration overrides
        apply_event_handler_overrides()


# Initialize on import
initialize_event_handler_registry()
