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

import typing as t
from contextvars import ContextVar
from datetime import datetime
from enum import Enum
from functools import lru_cache
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# Test provider discovery system imports
try:
    import uuid_utils
    _uuid7_available = True
    uuid_lib: t.Any = uuid_utils
except ImportError:
    import uuid
    _uuid7_available = False
    uuid_lib: t.Any = uuid


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
    category: str = Field(description="Test provider category (unit, integration, performance, etc.)")
    provider_type: str = Field(description="Provider type (mock, fixture, runner, etc.)")

    version: str = Field(description="Semantic version of this test provider")
    acb_min_version: str = Field(description="Minimum ACB version required")
    acb_max_version: str | None = Field(default=None, description="Maximum ACB version supported")

    author: str = Field(description="Primary author/maintainer")
    created_date: str = Field(description="ISO date when provider was created")
    last_modified: str = Field(description="ISO date of last significant update")

    status: TestProviderStatus = Field(description="Development/stability status")
    capabilities: list[TestProviderCapability] = Field(
        default_factory=list, description="List of features this provider supports",
    )

    required_packages: list[str] = Field(
        default_factory=list, description="External packages required for this provider",
    )
    optional_packages: dict[str, str] = Field(
        default_factory=dict, description="Optional packages and their purpose",
    )

    description: str = Field(description="Brief description of provider functionality")
    documentation_url: str | None = Field(default=None, description="Link to detailed documentation")
    repository_url: str | None = Field(default=None, description="Source code repository")

    settings_class: str = Field(description="Name of the settings class")
    config_example: dict[str, t.Any] | None = Field(
        default=None, description="Example configuration for this provider",
    )

    custom: dict[str, t.Any] = Field(
        default_factory=dict, description="Custom metadata fields",
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
        **{k: v for k, v in kwargs.items() if k not in {
            "version", "acb_min_version", "status", "settings_class",
        }},
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
test_provider_registry: ContextVar[list[TestProvider]] = ContextVar("test_provider_registry", default=[])
_enabled_test_providers_cache: ContextVar[dict[str, TestProvider]] = ContextVar(
    "_enabled_test_providers_cache", default={},
)
_installed_test_providers_cache: ContextVar[dict[str, TestProvider]] = ContextVar(
    "_installed_test_providers_cache", default={},
)

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
    providers = test_provider_registry.get()
    for provider in providers:
        if provider.category == category and provider.enabled:
            return provider
    return None


def list_test_providers() -> list[TestProvider]:
    """List all registered test providers."""
    return test_provider_registry.get().copy()


def list_available_test_providers() -> list[TestProvider]:
    """List all available (installed) test providers."""
    return [p for p in test_provider_registry.get() if p.installed]


def list_enabled_test_providers() -> list[TestProvider]:
    """List all enabled test providers."""
    return [p for p in test_provider_registry.get() if p.enabled]


def get_test_provider_class(category: str, name: str | None = None) -> type[t.Any]:
    """Get test provider class by category and optional name."""
    from importlib import import_module

    provider = get_test_provider_descriptor(category)
    if not provider:
        msg = f"Test provider not found: {category}"
        raise TestNotFound(msg)

    if name and provider.name != name:
        # Look for specific named provider
        providers = test_provider_registry.get()
        for p in providers:
            if p.category == category and p.name == name:
                provider = p
                break
        else:
            msg = f"Test provider not found: {category}/{name}"
            raise TestNotFound(msg)

    try:
        module = import_module(provider.module)
        return getattr(module, provider.class_name)
    except (ImportError, AttributeError) as e:
        msg = f"Test provider not available: {provider.module}.{provider.class_name}"
        raise TestNotInstalled(msg) from e


def try_import_test_provider(category: str, name: str | None = None) -> type[t.Any] | None:
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
    """
    if isinstance(provider_categories, str):
        provider = get_test_provider_descriptor(provider_categories)
        provider_name = provider.name if provider else None
        provider_class = try_import_test_provider(provider_categories, provider_name)
        if provider_class:
            return provider_class
        msg = f"Test provider not found or not enabled: {provider_categories}"
        raise TestNotFound(msg)

    if provider_categories is None:
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
                            # Try to match variable name to provider category
                            for provider in test_provider_registry.get():
                                if provider.category in var_name or provider.name in var_name:
                                    return try_import_test_provider(provider.category)
            except (OSError, IndexError):
                pass

        msg = "Could not determine provider category from context"
        raise ValueError(msg)

    if isinstance(provider_categories, list):
        results = []
        for category in provider_categories:
            provider_class = try_import_test_provider(category)
            if not provider_class:
                msg = f"Test provider not found or not enabled: {category}"
                raise TestNotFound(msg)
            results.append(provider_class)
        return tuple(results) if len(results) > 1 else results[0]

    msg = f"Invalid provider_categories type: {type(provider_categories)}"
    raise ValueError(msg)


def register_test_providers(providers_path: str | None = None) -> None:
    """Register test providers from a path (for discovery)."""
    # Implementation for auto-discovery could be added here
    # For now, we rely on static registration


def get_test_provider_info(provider_class: type) -> dict[str, t.Any]:
    """Get information about a test provider class."""
    info = {
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
    providers = test_provider_registry.get()

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
    providers = test_provider_registry.get()
    for provider in providers:
        if provider.category == category:
            if name is None or provider.name == name:
                provider.enabled = True
                break
    _update_test_provider_caches()


def disable_test_provider(category: str) -> None:
    """Disable a test provider by category."""
    providers = test_provider_registry.get()
    for provider in providers:
        if provider.category == category:
            provider.enabled = False
    _update_test_provider_caches()


@lru_cache(maxsize=1)
def _load_test_provider_settings() -> dict[str, t.Any]:
    """Load test provider configuration from settings/testing.yml.

    Returns:
        Dictionary with test provider configuration overrides
    """
    try:
        import yaml

        # Look for testing.yml in common locations
        settings_paths = [
            Path("settings/testing.yml"),
            Path("testing.yml"),
            Path.cwd() / "settings" / "testing.yml",
            Path.cwd() / "testing.yml",
        ]

        for settings_path in settings_paths:
            if settings_path.exists():
                content = settings_path.read_text()
                return yaml.safe_load(content) or {}

    except (ImportError, FileNotFoundError, Exception):
        # Silently ignore if settings can't be loaded
        pass

    return {}


def get_test_provider_override(category: str) -> str | None:
    """Get test provider implementation override from configuration.

    Args:
        category: Provider category (e.g., 'mocking', 'performance')

    Returns:
        Override provider name or None if no override

    Example:
        # In settings/testing.yml:
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
    if not test_provider_registry.get():
        test_provider_registry.set(core_test_providers.copy())
        _update_test_provider_caches()
        # Apply any configuration overrides
        apply_test_provider_overrides()


# Initialize on import
initialize_test_provider_registry()
