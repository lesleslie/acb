"""Test Provider Discovery and Dynamic Import System.

Provides test provider discovery, registration, and dynamic import capabilities
that mirror the adapter and service patterns in ACB. This enables test providers
to be discoverable, registerable, and overridable through configuration.

Features:
- Dynamic test provider loading via import_test_provider()
- Test provider registry with metadata support
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

# Test provider discovery system imports
uuid_lib: t.Any
try:
    import uuid_utils

    _uuid7_available = True
    uuid_lib = uuid_utils
except ImportError:
    import uuid

    _uuid7_available = False
    uuid_lib = uuid


class TestProviderStatus(Enum):
    """Test provider development/stability status."""

    ALPHA = "alpha"
    BETA = "beta"
    STABLE = "stable"
    DEPRECATED = "deprecated"
    EXPERIMENTAL = "experimental"


class TestProviderCapability(Enum):
    """Test provider capability enumeration."""

    # Core testing capabilities
    UNIT_TESTING = "unit_testing"
    INTEGRATION_TESTING = "integration_testing"
    PERFORMANCE_TESTING = "performance_testing"
    LOAD_TESTING = "load_testing"

    # Mock capabilities
    ADAPTER_MOCKING = "adapter_mocking"
    SERVICE_MOCKING = "service_mocking"
    ACTION_MOCKING = "action_mocking"
    ASYNC_MOCKING = "async_mocking"

    # Database testing
    DATABASE_FIXTURES = "database_fixtures"
    TRANSACTION_ROLLBACK = "transaction_rollback"
    SCHEMA_MIGRATION = "schema_migration"
    DATA_SEEDING = "data_seeding"

    # Performance capabilities
    BENCHMARKING = "benchmarking"
    PROFILING = "profiling"
    MEMORY_TESTING = "memory_testing"
    CONCURRENT_TESTING = "concurrent_testing"

    # Security testing
    SECURITY_SCANNING = "security_scanning"
    VULNERABILITY_TESTING = "vulnerability_testing"
    AUTH_TESTING = "auth_testing"

    # Configuration and environment
    CONFIG_TESTING = "config_testing"
    ENVIRONMENT_ISOLATION = "environment_isolation"
    TEMP_RESOURCE_MANAGEMENT = "temp_resource_management"


class TestProviderMetadata(BaseModel):
    """Test provider metadata for discovery and registration."""

    provider_id: UUID = Field(description="UUID7 identifier for this test provider")

    name: str = Field(description="Human-readable test provider name")
    category: str = Field(
        description="Test provider category (unit, integration, performance, etc.)",
    )
    provider_type: str = Field(
        description="Provider type (mock, fixture, runner, etc.)",
    )

    version: str = Field(description="Semantic version of this test provider")
    acb_min_version: str = Field(description="Minimum ACB version required")
    acb_max_version: str | None = Field(
        default=None,
        description="Maximum ACB version supported",
    )

    author: str = Field(description="Primary author/maintainer")
    created_date: str = Field(description="ISO date when provider was created")
    last_modified: str = Field(description="ISO date of last significant update")

    status: TestProviderStatus = Field(description="Development/stability status")
    capabilities: list[TestProviderCapability] = Field(
        default_factory=list,
        description="List of features this provider supports",
    )

    required_packages: list[str] = Field(
        default_factory=list,
        description="External packages required for this provider",
    )
    optional_packages: dict[str, str] = Field(
        default_factory=dict,
        description="Optional packages and their purpose",
    )

    description: str = Field(description="Brief description of provider functionality")
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
        description="Example configuration for this provider",
    )

    custom: dict[str, t.Any] = Field(
        default_factory=dict,
        description="Custom metadata fields",
    )

    model_config = ConfigDict(use_enum_values=True, extra="forbid")


def generate_test_provider_id() -> UUID:
    """Generate a UUID for test provider identification."""
    if _uuid7_available:
        uuid_obj = uuid_lib.uuid7()
        return UUID(str(uuid_obj))
    uuid_obj = uuid_lib.uuid4()
    return UUID(str(uuid_obj))


def create_test_provider_metadata_template(
    name: str,
    category: str,
    provider_type: str,
    author: str,
    description: str,
    **kwargs: t.Any,
) -> TestProviderMetadata:
    """Create a test provider metadata template."""
    now = datetime.now().isoformat()

    return TestProviderMetadata(
        provider_id=generate_test_provider_id(),
        name=name,
        category=category,
        provider_type=provider_type,
        version=kwargs.get("version", "1.0.0"),
        acb_min_version=kwargs.get("acb_min_version", "0.19.1"),
        author=author,
        created_date=now,
        last_modified=now,
        status=kwargs.get("status", TestProviderStatus.STABLE),
        description=description,
        settings_class=kwargs.get("settings_class", f"{name}Settings"),
        **{
            k: v
            for k, v in kwargs.items()
            if k
            not in {
                "version",
                "acb_min_version",
                "status",
                "settings_class",
            }
        },
    )


class TestNotFound(Exception):
    """Raised when a test provider cannot be found."""


class TestNotInstalled(Exception):
    """Raised when a test provider is not installed."""


class TestProvider(BaseModel):
    """Test provider descriptor for discovery and registration."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    class_name: str
    category: str
    module: str
    enabled: bool = False
    installed: bool = False

    metadata: TestProviderMetadata | None = None
    runtime_id: str | None = None

    def __hash__(self) -> int:
        base_hash = (self.name, self.class_name, self.category, self.module)
        if self.metadata:
            return hash((*base_hash, str(self.metadata.provider_id)))
        return hash(base_hash)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TestProvider):
            return False
        return (
            self.name == other.name
            and self.class_name == other.class_name
            and self.category == other.category
            and self.module == other.module
        )


# Test provider registry using ContextVar for thread safety
test_provider_registry: ContextVar[list[TestProvider] | None] = ContextVar(
    "test_provider_registry",
    default=None,
)
_enabled_test_providers_cache: ContextVar[dict[str, TestProvider] | None] = ContextVar(
    "_enabled_test_providers_cache",
    default=None,
)
_installed_test_providers_cache: ContextVar[dict[str, TestProvider] | None] = (
    ContextVar(
        "_installed_test_providers_cache",
        default=None,
    )
)


def _ensure_test_provider_registry_initialized() -> list[TestProvider]:
    """Ensure the test provider registry is initialized with an empty list if needed."""
    registry = test_provider_registry.get(None)
    if registry is None:
        registry = []
        test_provider_registry.set(registry)
    return registry


def _ensure_enabled_test_providers_cache_initialized() -> dict[str, TestProvider]:
    """Ensure the enabled test providers cache is initialized with an empty dict if needed."""
    cache = _enabled_test_providers_cache.get(None)
    if cache is None:
        cache = {}
        _enabled_test_providers_cache.set(cache)
    return cache


def _ensure_installed_test_providers_cache_initialized() -> dict[str, TestProvider]:
    """Ensure the installed test providers cache is initialized with an empty dict if needed."""
    cache = _installed_test_providers_cache.get(None)
    if cache is None:
        cache = {}
        _installed_test_providers_cache.set(cache)
    return cache


# Core test providers registry - static mappings like adapters
core_test_providers = [
    TestProvider(
        name="mock_adapter_provider",
        module="acb.testing.providers.adapters",
        class_name="MockAdapterProvider",
        category="mocking",
        enabled=False,
        installed=True,
    ),
    TestProvider(
        name="mock_service_provider",
        module="acb.testing.providers.services",
        class_name="MockServiceProvider",
        category="mocking",
        enabled=False,
        installed=True,
    ),
    TestProvider(
        name="mock_action_provider",
        module="acb.testing.providers.actions",
        class_name="MockActionProvider",
        category="mocking",
        enabled=False,
        installed=True,
    ),
    TestProvider(
        name="database_test_provider",
        module="acb.testing.providers.database",
        class_name="DatabaseTestProvider",
        category="integration",
        enabled=False,
        installed=True,
    ),
    TestProvider(
        name="performance_test_provider",
        module="acb.testing.providers.performance",
        class_name="PerformanceTestProvider",
        category="performance",
        enabled=False,
        installed=True,
    ),
    TestProvider(
        name="security_test_provider",
        module="acb.testing.providers.security",
        class_name="SecurityTestProvider",
        category="security",
        enabled=False,
        installed=True,
    ),
    TestProvider(
        name="integration_test_provider",
        module="acb.testing.providers.integration",
        class_name="IntegrationTestProvider",
        category="integration",
        enabled=False,
        installed=True,
    ),
]


# Test provider Discovery Functions (mirrors adapter pattern)
def get_test_provider_descriptor(category: str) -> TestProvider | None:
    """Get test provider descriptor by category."""
    providers = _ensure_test_provider_registry_initialized()
    for provider in providers:
        if provider.category == category and provider.enabled:
            return provider
    return None


def list_test_providers() -> list[TestProvider]:
    """List all registered test providers."""
    return _ensure_test_provider_registry_initialized().copy()


def list_available_test_providers() -> list[TestProvider]:
    """List all available (installed) test providers."""
    return [p for p in _ensure_test_provider_registry_initialized() if p.installed]


def list_enabled_test_providers() -> list[TestProvider]:
    """List all enabled test providers."""
    return [p for p in _ensure_test_provider_registry_initialized() if p.enabled]


def get_test_provider_class(category: str, name: str | None = None) -> type[t.Any]:
    """Get test provider class by category and optional name."""
    from importlib import import_module

    provider = get_test_provider_descriptor(category)
    if not provider:
        msg = f"Test provider not found: {category}"
        raise TestNotFound(msg)

    if name and provider.name != name:
        # Look for specific named provider
        providers = _ensure_test_provider_registry_initialized()
        for p in providers:
            if p.category == category and p.name == name:
                provider = p
                break
        else:
            msg = f"Test provider not found: {category}/{name}"
            raise TestNotFound(msg)

    try:
        module = import_module(provider.module)
        cls: type[t.Any] = getattr(module, provider.class_name)
        return cls
    except (ImportError, AttributeError) as e:
        msg = f"Test provider not available: {provider.module}.{provider.class_name}"
        raise TestNotInstalled(msg) from e


def try_import_test_provider(
    category: str,
    name: str | None = None,
) -> type[t.Any] | None:
    """Try to import a test provider class, return None if not available."""
    try:
        return get_test_provider_class(category, name)
    except (TestNotFound, TestNotInstalled):
        return None


def import_test_provider(provider_categories: str | list[str] | None = None) -> t.Any:
    """Import test provider(s) dynamically - main entry point for provider discovery.

    Args:
        provider_categories: Provider category or list of categories

    Returns:
        Provider class or tuple of provider classes

    Examples:
        # Import single provider
        MockAdapterProvider = import_test_provider("mocking")

        # Import multiple providers
        MockProvider, PerformanceProvider = import_test_provider(["mocking", "performance"])

        # Auto-detect from context
        mock_provider = import_test_provider()  # Detects from variable name

    Complexity: 2
    """
    from acb.discovery_common import RegistryConfig, import_from_registry

    config = RegistryConfig(
        get_descriptor=get_test_provider_descriptor,
        try_import=try_import_test_provider,
        get_all_descriptors=_ensure_test_provider_registry_initialized,
        not_found_exception=TestNotFound,
    )
    return import_from_registry(provider_categories, config)


def register_test_providers(providers_path: str | None = None) -> None:
    """Register test providers from a path (for discovery)."""
    # Implementation for auto-discovery could be added here
    # For now, we rely on static registration


def get_test_provider_info(provider_class: type[t.Any]) -> dict[str, t.Any]:
    """Get information about a test provider class."""
    info: dict[str, t.Any] = {
        "class_name": provider_class.__name__,
        "module": provider_class.__module__,
        "docstring": provider_class.__doc__,
    }

    # Check for metadata
    if hasattr(provider_class, "PROVIDER_METADATA"):
        metadata = provider_class.PROVIDER_METADATA
        if isinstance(metadata, TestProviderMetadata):
            info["metadata"] = metadata.model_dump()

    return info


# Update provider cache
def _update_test_provider_caches() -> None:
    """Update test provider caches for faster lookups."""
    providers = _ensure_test_provider_registry_initialized()

    enabled_cache = {}
    installed_cache = {}

    for provider in providers:
        if provider.enabled:
            enabled_cache[provider.category] = provider
        if provider.installed:
            installed_cache[provider.category] = provider

    _enabled_test_providers_cache.set(enabled_cache)
    _installed_test_providers_cache.set(installed_cache)


# Enable providers based on configuration
def enable_test_provider(category: str, name: str | None = None) -> None:
    """Enable a test provider by category and optional name."""
    providers = _ensure_test_provider_registry_initialized()
    for provider in providers:
        if provider.category == category:
            if name is None or provider.name == name:
                provider.enabled = True
                break
    _update_test_provider_caches()


def disable_test_provider(category: str) -> None:
    """Disable a test provider by category."""
    providers = _ensure_test_provider_registry_initialized()
    for provider in providers:
        if provider.category == category:
            provider.enabled = False
    _update_test_provider_caches()


@lru_cache(maxsize=1)
def _load_test_provider_settings() -> dict[str, t.Any]:
    """Load test provider configuration from settings/testing.yaml.

    Returns:
        Dictionary with test provider configuration overrides
    """
    with suppress(ImportError, FileNotFoundError, Exception):
        import yaml

        # Look for testing.yaml in common locations
        settings_paths = [
            Path("settings/testing.yaml"),
            Path("testing.yaml"),
            Path.cwd() / "settings" / "testing.yaml",
            Path.cwd() / "testing.yaml",
        ]

        for settings_path in settings_paths:
            if settings_path.exists():
                content = settings_path.read_text()
                loaded = yaml.safe_load(content)
                return dict(loaded) if loaded else {}

    return {}


def get_test_provider_override(category: str) -> str | None:
    """Get test provider implementation override from configuration.

    Args:
        category: Provider category (e.g., 'mocking', 'performance')

    Returns:
        Override provider name or None if no override

    Example:
        # In settings/testing.yaml:
        # mocking: mock_adapter_provider
        # performance: performance_test_provider
        # integration: database_test_provider
    """
    settings = _load_test_provider_settings()
    return settings.get(category)


def apply_test_provider_overrides() -> None:
    """Apply test provider configuration overrides from settings."""
    settings = _load_test_provider_settings()

    if not settings:
        return

    # Apply overrides for each configured provider
    for category, provider_name in settings.items():
        if isinstance(provider_name, str):
            # Enable the specified provider for this category
            try:
                enable_test_provider(category, provider_name)
            except (TestNotFound, TestNotInstalled):
                # Provider not available, continue with defaults
                continue


def initialize_test_provider_registry() -> None:
    """Initialize the test provider registry with core providers."""
    if not _ensure_test_provider_registry_initialized():
        _ensure_test_provider_registry_initialized().extend(core_test_providers)
        _update_test_provider_caches()
        # Apply any configuration overrides
        apply_test_provider_overrides()


# Initialize on import
initialize_test_provider_registry()
