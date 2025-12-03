import os
import sys
import tempfile
from contextvars import ContextVar
from enum import Enum
from importlib import import_module, util
from pathlib import Path
from uuid import UUID

import asyncio

# Removed nest_asyncio import - not needed in library code
import typing as t
import yaml
from anyio import Path as AsyncPath
from contextlib import suppress
from inflection import camelize
from pydantic import BaseModel, ConfigDict, Field

from acb.depends import depends

# Declare uuid_utils to handle both import cases
uuid_utils: t.Any = None  # Initialize as None

try:
    import uuid_utils  # type: ignore[no-redef]

    _uuid7_available = True
    uuid_lib: t.Any = uuid_utils  # type: ignore[no-redef]
except ImportError:
    import uuid

    uuid_utils = None  # type: ignore[no-redef]

    _uuid7_available = False
    uuid_lib: t.Any = uuid  # type: ignore[no-redef]


class AdapterStatus(str, Enum):
    ALPHA = "alpha"
    BETA = "beta"
    STABLE = "stable"
    DEPRECATED = "deprecated"
    EXPERIMENTAL = "experimental"


class AdapterCapability(str, Enum):
    CONNECTION_POOLING = "connection_pooling"
    RECONNECTION = "auto_reconnection"
    HEALTH_CHECKS = "health_checks"
    TLS_SUPPORT = "tls_support"

    TRANSACTIONS = "transactions"
    BULK_OPERATIONS = "bulk_operations"
    STREAMING = "streaming"
    COMPRESSION = "compression"
    ENCRYPTION = "encryption"

    CACHING = "caching"
    ASYNC_OPERATIONS = "async_operations"
    BATCHING = "batching"

    METRICS = "metrics"
    TRACING = "tracing"
    LOGGING = "structured_logging"

    SCHEMA_VALIDATION = "schema_validatiorn"
    MIGRATIONS = "migrations"
    BACKUP_RESTORE = "backup_restore"

    # Logger-specific capabilities
    STRUCTURED_OUTPUT = "structured_output"
    ASYNC_LOGGING = "async_logging"
    CONTEXTUAL = "contextual"
    ROTATION = "rotation"
    REMOTE_LOGGING = "remote_logging"
    JSON_OUTPUT = "json_output"
    FILE_LOGGING = "file_logging"
    CORRELATION_ID = "correlation_id"

    # Graph-specific capabilities
    GRAPH_TRAVERSAL = "graph_traversal"
    CYPHER_QUERIES = "cypher_queries"
    GREMLIN_QUERIES = "gremlin_queries"
    AQL_QUERIES = "aql_queries"
    GRAPH_ANALYTICS = "graph_analytics"
    PATHFINDING = "pathfinding"
    SUBGRAPH_OPERATIONS = "subgraph_operations"
    GRAPH_SCHEMA_VALIDATION = "graph_schema_validation"

    # AI/ML-specific capabilities
    HYBRID_DEPLOYMENT = "hybrid_deployment"
    EDGE_INFERENCE = "edge_inference"
    MULTIMODAL_PROCESSING = "multimodal_processing"
    PROMPT_TEMPLATING = "prompt_templating"
    MODEL_CACHING = "model_caching"
    TEXT_GENERATION = "text_generation"
    VISION_PROCESSING = "vision_processing"
    AUDIO_PROCESSING = "audio_processing"
    FALLBACK_MECHANISMS = "fallback_mechanisms"
    ADAPTIVE_ROUTING = "adaptive_routing"

    # Model optimization and deployment
    MODEL_QUANTIZATION = "model_quantization"
    COLD_START_OPTIMIZATION = "cold_start_optimization"
    EDGE_OPTIMIZED = "edge_optimized"

    # Embeddings and vector operations
    BATCH_EMBEDDING = "batch_embedding"
    SEMANTIC_SEARCH = "semantic_search"
    SIMILARITY_COMPUTATION = "similarity_computation"
    POOLING_STRATEGIES = "pooling_strategies"
    MEMORY_EFFICIENT_PROCESSING = "memory_efficient_processing"
    TEXT_PREPROCESSING = "text_preprocessing"
    VECTOR_NORMALIZATION = "vector_normalization"


def generate_adapter_id() -> UUID:
    """Generate a stable module UUID.

    Uses `uuid7` when available (via optional `uuid_utils`) for monotonicity,
    falling back to `uuid4` otherwise.
    """
    value = uuid_lib.uuid7() if hasattr(uuid_lib, "uuid7") else uuid_lib.uuid4()
    # Normalize to stdlib UUID object in case a third-party uuid7 returns a custom type
    import uuid as _uuid

    return _uuid.UUID(str(value))


class AdapterMetadata(BaseModel):
    module_id: UUID
    name: str
    category: str
    provider: str | None = None
    version: str = "1.0.0"
    acb_min_version: str = "0.19.0"
    author: str | None = None
    created_date: str | None = None
    last_modified: str | None = None
    status: AdapterStatus = AdapterStatus.STABLE
    description: str | None = None
    settings_class: str | None = None
    config_example: dict[str, t.Any] | None = None
    capabilities: list[AdapterCapability] = Field(default_factory=list)
    required_packages: list[str] = Field(default_factory=list)
    deprecated: bool = False
    deprecation_message: str | None = None
    documentation_url: str | None = None
    issue_tracker_url: str | None = None
    source_repository_url: str | None = None
    license: str | None = None
    stability: str | None = "stable"
    tags: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)


# ---- Metadata Utilities ----------------------------------------------------
def extract_metadata_from_class(obj: t.Any) -> AdapterMetadata | None:
    """Extract AdapterMetadata attached to a class via '__module_metadata__'."""
    meta = getattr(obj, "__module_metadata__", None)
    if meta is None:
        return None
    if isinstance(meta, AdapterMetadata):
        return meta
    if isinstance(meta, dict):
        # Best-effort parsing if a plain dict is attached
        return AdapterMetadata.model_validate(meta)
    return None


def list_adapter_capabilities(obj: t.Any) -> list[str]:
    """List capability values for the adapter class metadata."""
    meta = extract_metadata_from_class(obj)
    if not meta:
        return []
    return [c.value for c in meta.capabilities]


def get_adapter_info(obj: t.Any) -> dict[str, t.Any]:
    """Return a dictionary of adapter info for debugging/reporting."""
    meta = extract_metadata_from_class(obj)
    info: dict[str, t.Any] = {"has_metadata": meta is not None}
    if meta:
        info.update(
            {
                "name": meta.name,
                "category": meta.category,
                "provider": meta.provider,
                "version": meta.version,
                "capabilities": list_adapter_capabilities(obj),
            },
        )
    return info


def generate_adapter_report(obj: t.Any) -> str:
    """Generate a simple human-readable report for an adapter class."""
    meta = extract_metadata_from_class(obj)
    if not meta:
        return "Adapter Report: <unknown>\nNo metadata available."

    caps = list_adapter_capabilities(obj)
    required = meta.required_packages or []
    lines = [
        f"Adapter Report: {meta.name}",
        f"Provider: {meta.provider}",
        f"Category: {meta.category}",
        f"Version: {meta.version}",
        f"Capabilities ({len(caps)}): {', '.join(caps)}",
        f"Dependencies ({len(required)}): {', '.join(required)}",
    ]
    return "\n".join(lines)


def _parse_version(v: str) -> tuple[int, ...]:
    parts = []
    for p in v.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            # Strip any non-numeric suffixes like 'rc1' for simple compare
            num = "".join(ch for ch in p if ch.isdigit())
            parts.append(int(num) if num else 0)
    return tuple(parts)


def validate_version_compatibility(meta: AdapterMetadata, current_version: str) -> bool:
    """Validate current ACB version against adapter's declared range.

    Rules:
    - current >= acb_min_version
    - if acb_max_version present on the metadata, current <= acb_max_version
    """
    try:
        min_ok = _parse_version(current_version) >= _parse_version(meta.acb_min_version)
        max_ok = True
        acb_max = getattr(meta, "acb_max_version", None)
        if acb_max:
            max_ok = _parse_version(current_version) <= _parse_version(acb_max)
        return bool(min_ok and max_ok)
    except Exception:
        return False


# Context variables for registry and caches
adapter_registry: ContextVar[list["Adapter"] | None] = ContextVar(
    "adapter_registry",
    default=None,
)
_enabled_adapters_cache: ContextVar[dict[str, "Adapter"] | None] = ContextVar(
    "_enabled_adapters_cache",
    default=None,
)
_installed_adapters_cache: ContextVar[dict[str, "Adapter"] | None] = ContextVar(
    "_installed_adapters_cache",
    default=None,
)
_adapter_import_locks: ContextVar[dict[str, asyncio.Lock] | None] = ContextVar(
    "_adapter_import_locks",
    default=None,
)


class Adapter(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    name: str
    class_name: str
    category: str
    pkg: str = "acb"
    module: str = ""
    enabled: bool = False
    installed: bool = False
    path: AsyncPath = AsyncPath(__file__)

    metadata: AdapterMetadata | None = None
    runtime_id: str | None = None

    def __str__(self) -> str:
        return self.__repr__()

    def __hash__(self) -> int:
        base_hash = (self.name, self.class_name, self.category, self.pkg, self.module)
        if self.metadata:
            return hash((*base_hash, str(self.metadata.module_id)))
        return hash(base_hash)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Adapter):
            return False
        return (
            self.name == other.name
            and self.class_name == other.class_name
            and (self.category == other.category)
            and (self.pkg == other.pkg)
            and (self.module == other.module)
        )


# Module level constants
core_adapters = [
    Adapter(
        name="config",
        module="acb.config",
        class_name="Config",
        category="config",
        enabled=True,
        installed=True,
        path=AsyncPath(__file__).parent / "config.py",
    ),
    Adapter(
        name="loguru",
        module="acb.adapters.logger.loguru",
        class_name="Logger",
        category="logger",
        enabled=True,
        installed=True,
        path=AsyncPath(__file__).parent / "logger" / "loguru.py",
    ),
    Adapter(
        name="logly",
        module="acb.adapters.logger.logly",
        class_name="Logger",
        category="logger",
        enabled=True,
        installed=True,
        path=AsyncPath(__file__).parent / "logger" / "logly.py",
    ),
]


class AdapterNotFound(Exception):
    pass


class AdapterNotInstalled(Exception):
    pass


# Global state flags
_testing: bool = "pytest" in sys.modules
_deployed: bool = os.getenv("DEPLOYED", "").lower() in ("1", "true", "yes")


def _get_project_root() -> AsyncPath:
    """Get the project root path based on current working directory when used as a library."""
    search_roots = [Path.cwd(), Path(__file__).resolve()]

    for base in search_roots:
        for candidate in [base] + list(base.parents):
            pyproject = candidate / "pyproject.toml"
            if pyproject.exists():
                return AsyncPath(str(candidate))

    # Fallback to package directory if pyproject not found
    return AsyncPath(__file__).parent.parent


# Path caches
root_path: AsyncPath = _get_project_root()
config_path: AsyncPath = root_path / "settings"
settings_path: AsyncPath = root_path / "settings"  # Alias for backward compatibility
secrets_path: AsyncPath = root_path / ".secrets"
tmp_path: AsyncPath = AsyncPath(tempfile.gettempdir()) / "acb"
_adapters_root_hint: AsyncPath | None = None


async def _resolve_adapters_root() -> AsyncPath:
    """Locate the directory that actually contains the adapters package."""
    global _adapters_root_hint

    if _adapters_root_hint is not None:
        return _adapters_root_hint

    candidates = [
        root_path,
        root_path / "acb",
        AsyncPath(__file__).parent.parent,
    ]

    for candidate in candidates:
        try:
            if await (candidate / "adapters").exists():
                _adapters_root_hint = candidate
                return candidate
        except FileNotFoundError:
            continue

    _adapters_root_hint = root_path
    return root_path


# Registry-related functions (moved to registry module)
def _ensure_adapter_registry_initialized() -> list["Adapter"]:
    """Ensure the adapter registry is initialized with an empty list if needed."""
    registry = adapter_registry.get()
    if registry is None:
        registry = core_adapters.copy()
        adapter_registry.set(registry)
    return registry


def _ensure_enabled_adapters_cache_initialized() -> dict[str, "Adapter"]:
    """Ensure the enabled adapters cache is initialized with an empty dict if needed."""
    cache = _enabled_adapters_cache.get()
    if cache is None:
        cache = {}
        _enabled_adapters_cache.set(cache)
    return cache


def _ensure_installed_adapters_cache_initialized() -> dict[str, "Adapter"]:
    """Ensure the installed adapters cache is initialized with an empty dict if needed."""
    cache = _installed_adapters_cache.get()
    if cache is None:
        cache = {}
        _installed_adapters_cache.set(cache)
    return cache


def _ensure_adapter_import_locks_initialized() -> dict[str, asyncio.Lock]:
    """Ensure the adapter import locks are initialized with an empty dict if needed."""
    locks = _adapter_import_locks.get()
    if locks is None:
        locks = {}
        _adapter_import_locks.set(locks)
    return locks


def _update_adapter_caches() -> None:
    """Update the caches based on the current registry state."""
    registry = _ensure_adapter_registry_initialized()
    enabled_cache = _ensure_enabled_adapters_cache_initialized()
    installed_cache = _ensure_installed_adapters_cache_initialized()

    # Clear caches
    enabled_cache.clear()
    installed_cache.clear()

    # Rebuild caches from registry
    for adapter in registry:
        if adapter.enabled:
            enabled_cache[adapter.category] = adapter
        if adapter.installed:
            installed_cache[adapter.category] = adapter


def get_adapter(adapter_category: str) -> t.Optional["Adapter"]:
    """Get an adapter by its category from the registry.

    Args:
        adapter_category: The category of the adapter to retrieve

    Returns:
        The adapter if found, otherwise None
    """
    enabled_adapters = _ensure_enabled_adapters_cache_initialized()
    if adapter_category in enabled_adapters:
        return enabled_adapters[adapter_category]

    installed_adapters = _ensure_installed_adapters_cache_initialized()
    if adapter_category in installed_adapters:
        return installed_adapters[adapter_category]

    # Fallback to any discovered adapter matching the category
    registry = _ensure_adapter_registry_initialized()
    for adapter in registry:
        if adapter.category == adapter_category:
            return adapter

    return None


def get_enabled_adapters() -> list["Adapter"]:
    """Get a list of all enabled adapters from the registry.

    Returns:
        List of enabled adapters
    """
    enabled_adapters = _ensure_enabled_adapters_cache_initialized()
    return list(enabled_adapters.values())


def get_installed_adapters() -> list["Adapter"]:
    """Get a list of all installed adapters from the registry.

    Returns:
        List of installed adapters
    """
    installed_adapters = _ensure_installed_adapters_cache_initialized()
    return list(installed_adapters.values())


def get_all_adapters() -> list["Adapter"]:
    """Get a list of all adapters from the registry.

    Returns:
        List of all adapters
    """
    from acb.context import get_context

    all_adapters = _ensure_adapter_registry_initialized().copy()
    for pkg in get_context().pkg_registry.get():
        for adapter in pkg.adapters:
            if adapter not in all_adapters:
                _ensure_adapter_registry_initialized().append(adapter)
                all_adapters.append(adapter)

    return all_adapters


def get_adapters() -> list["Adapter"]:
    """Get a list of all adapters from the registry.

    Alias for backward compatibility.

    Returns:
        List of all adapters
    """
    return get_all_adapters()


def _enable_configured_adapters(
    all_adapters: list["Adapter"],
    enabled_adapters: dict[str, str],
) -> None:
    for adapter in all_adapters:
        if enabled_adapters.get(adapter.category) == adapter.name:
            adapter.enabled = True


# Discovery-related functions (moved to discovery module)
async def _import_adapter_module_for_deps(adapter_category: str) -> None:
    from contextlib import suppress

    if adapter_category == "app":
        for adapter in _ensure_adapter_registry_initialized():
            if adapter.category == adapter_category:
                with suppress(ImportError, AdapterNotFound, AdapterNotInstalled):
                    import_module(adapter.module)
                break


async def _find_adapter(adapter_category: str) -> "Adapter":
    try:
        adapter = get_adapter(adapter_category)
        if adapter is not None:
            return adapter
        from contextlib import suppress

        current_path = AsyncPath(Path.cwd())
        for pkg_path in (current_path, current_path.parent):
            adapters_dir = pkg_path / "adapters"
            if await adapters_dir.exists():
                with suppress(Exception):
                    await register_adapters(pkg_path)
                    adapter = get_adapter(adapter_category)
                    if adapter is not None:
                        return adapter
        msg = f"{adapter_category} adapter not found – check adapters.yaml and ensure package registration"
        raise AdapterNotFound(
            msg,
        )
    except AttributeError:
        msg = f"{adapter_category} adapter not found – check adapters.yaml"
        raise AdapterNotFound(
            msg,
        )


async def _load_module(adapter: "Adapter") -> t.Any:
    try:
        module = import_module(adapter.module)
    except ModuleNotFoundError:
        spec = util.spec_from_file_location(adapter.path.stem, str(adapter.path))
        if spec is None:
            msg = f"Failed to create module spec for {adapter.module}"
            raise AdapterNotFound(msg)
        module = util.module_from_spec(spec)
        if spec.loader is not None:
            spec.loader.exec_module(module)
        sys.modules[adapter.name] = module
    return module


async def _initialize_adapter(
    adapter: "Adapter",
    module: t.Any,
    adapter_category: str,
) -> t.Any:
    from contextlib import suppress

    adapter_class: t.Any = getattr(module, adapter.class_name)
    adapter_settings = None
    adapter_settings_class_name = f"{adapter.class_name}Settings"
    if hasattr(module, adapter_settings_class_name):
        adapter_settings_class = getattr(module, adapter_settings_class_name)
        with suppress(Exception):
            adapter_settings = adapter_settings_class()
    if adapter_settings is not None:
        from acb.config import Config

        config = await depends.get(Config)
        setattr(config, adapter_category, adapter_settings)

    # Retrieve or create adapter instance without leaving placeholder values
    instance: t.Any
    try:
        instance = depends.get_sync(adapter_class)
    except Exception:
        instance = adapter_class()
        depends.set(adapter_class, instance)
    else:
        if isinstance(instance, (str, tuple)):
            instance = adapter_class()
            depends.set(adapter_class, instance)

    if hasattr(instance, "init"):
        init_result = instance.init()
        if hasattr(init_result, "__await__"):
            await init_result
    # Only try to log if the logger is available to avoid circular dependencies
    with suppress(Exception):
        from acb.logger import Logger

        logger = await depends.get(Logger)
        # Check if it's actually a logger instance (not an empty tuple)
        if logger and hasattr(logger, "debug") and callable(logger):
            logger.debug(f"Initialized {adapter_category} adapter: {adapter.name}")
    return instance


async def gather_imports(adapter_categories: list[str]) -> list[t.Any]:
    """Gather imports for multiple adapter categories.

    Args:
        adapter_categories: List of adapter categories to import

    Returns:
        List of imported adapter instances
    """
    tasks = []
    for adapter_category in adapter_categories:
        task = asyncio.create_task(_import_adapter(adapter_category))
        tasks.append(task)
    try:
        imported_adapters = await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as e:
        msg = f"Failed to install adapters {adapter_categories}: {e}"
        raise AdapterNotInstalled(msg)

    processed_adapters = []
    for i, imported_adapter in enumerate(imported_adapters):
        if isinstance(imported_adapter, Exception):
            if isinstance(imported_adapter, (AdapterNotFound, AdapterNotInstalled)):
                adapter_category = adapter_categories[i]
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Adapter {adapter_category} not found or installed: {imported_adapter}",
                )
                continue
            raise imported_adapter
        processed_adapters.append(imported_adapter)

    return processed_adapters


async def _import_adapter(adapter_category: str) -> t.Any:
    """Import a single adapter by category.

    Args:
        adapter_category: The category of adapter to import

    Returns:
        The imported adapter instance
    """
    if _testing or "pytest" in sys.modules:
        from unittest.mock import MagicMock

        return MagicMock()

    await _ensure_adapter_configuration()

    adapter = await _find_adapter(adapter_category)
    module = await _load_module(adapter)
    adapter_class = getattr(module, adapter.class_name)

    # Initialize context if needed
    from acb.context import get_context

    context = get_context()
    if not context.adapters.get(adapter_category):
        instance = await _initialize_adapter(adapter, module, adapter_category)
        context.adapters.set({**context.adapters.get(), adapter_category: instance})
        return instance

    existing_instance = context.adapters.get().get(adapter_category)
    if not isinstance(existing_instance, adapter_class):
        instance = await _initialize_adapter(adapter, module, adapter_category)
        context.adapters.set({**context.adapters.get(), adapter_category: instance})
        return instance

    return existing_instance


def _normalize_adapter_categories(
    adapter_categories: str | list[str] | None,
) -> list[str]:
    if adapter_categories is None:
        adapter_categories = []
    if isinstance(adapter_categories, str):
        adapter_categories = [adapter_categories]
    if not isinstance(adapter_categories, list):
        msg = f"adapter_categories must be str, list[str], or None, got {type(adapter_categories)}"
        raise ValueError(
            msg,
        )

    # Normalize adapter category names (e.g. "cache" becomes "caching")
    # Using common mappings for backward compatibility
    normalized = []
    for adapter_category in adapter_categories:
        normalized_name = adapter_category.strip().lower()
        if normalized_name in ("cache", "caching"):
            normalized.append("cache")
        elif normalized_name in ("db", "database", "sql", "nosql"):
            normalized.append(normalized_name)  # Keep the original form
        else:
            normalized.append(normalized_name)
    return normalized


def _handle_testing_mode(adapter_categories: str | list[str] | None) -> t.Any:
    from unittest.mock import MagicMock

    if adapter_categories is None:
        return []
    if isinstance(adapter_categories, str):
        return MagicMock()
    return [MagicMock() for _ in adapter_categories]


async def _ensure_adapter_configuration() -> None:
    """Ensure adapter configuration is loaded and adapters are registered."""
    global _testing, _deployed

    if _testing or "pytest" in sys.modules:
        _testing = True
        return

    # Load configuration and register adapters
    adapters_root = await _resolve_adapters_root()
    # register_adapters expects the project/package root and handles appending
    # the adapters directory itself.
    await register_adapters(adapters_root)
    await _apply_adapter_configuration()


async def _load_adapter_selection_map() -> dict[str, str]:
    """Load adapter selections from settings/adapters.(y)aml."""
    for filename in ("adapters.yaml", "adapters.yml"):
        config_file = settings_path / filename
        normalized = await _read_adapter_config(config_file)
        if normalized:
            return normalized
    return {}


async def _read_adapter_config(config_file: AsyncPath) -> dict[str, str]:
    """Read and normalize adapter configuration from a single file."""
    try:
        if not (await config_file.exists()):
            return {}
        raw = await config_file.read_text()
    except FileNotFoundError:
        return {}
    except Exception:
        return {}
    return _parse_adapter_config(raw)


def _parse_adapter_config(raw: str) -> dict[str, str]:
    """Parse adapters YAML into normalized mapping."""
    try:
        loaded: t.Any = yaml.safe_load(raw) or {}
    except Exception:
        return {}
    if not isinstance(loaded, dict):
        return {}
    normalized: dict[str, str] = {}
    for category, adapter_name in loaded.items():
        if isinstance(category, str) and isinstance(adapter_name, str):
            normalized[category.strip().lower()] = adapter_name.strip().lower()
    return normalized


async def _apply_adapter_configuration() -> None:
    """Enable adapters based on adapters.yaml selections."""
    selection_map = await _load_adapter_selection_map()
    registry = _ensure_adapter_registry_initialized()
    if not registry:
        return

    normalized_selection = selection_map
    categories: dict[str, list[Adapter]] = {}
    for adapter in registry:
        adapter.enabled = False
        adapter.installed = False
        categories.setdefault(adapter.category.lower(), []).append(adapter)

    for category, adapters in categories.items():
        desired_name = normalized_selection.get(category)
        if desired_name:
            for adapter in adapters:
                adapter.enabled = adapter.name.lower() == desired_name
                if adapter.enabled:
                    adapter.installed = True
        elif len(adapters) == 1:
            adapters[0].enabled = True
            adapters[0].installed = True

    _update_adapter_caches()


# Registry and discovery functions to be moved to separate modules
async def register_adapters(path: AsyncPath) -> list["Adapter"]:
    if _testing or "pytest" in sys.modules:
        return []
    _adapters_path = path / "adapters"
    if not (await _adapters_path.exists()):
        return []
    pkg_adapters = await _handle_path_adapters(_adapters_path)
    _adapters: list[Adapter] = []
    for adapter_name, modules in pkg_adapters.items():
        _modules = _extract_adapter_modules(modules, adapter_name)
        _adapters.extend(_modules)
    registry = _ensure_adapter_registry_initialized()
    for a in _adapters:
        module = ".".join(a.module.split(".")[-2:])
        remove = next(
            (_a for _a in registry if ".".join(_a.module.split(".")[-2:]) == module),
            None,
        )
        if remove:
            registry.remove(remove)
        registry.append(a)
        _ensure_adapter_import_locks_initialized()[a.category] = asyncio.Lock()
    _update_adapter_caches()
    return _adapters


async def _handle_path_adapters(path: AsyncPath) -> dict[str, list[AsyncPath]]:
    return {
        a.stem: [
            m
            async for m in a.iterdir()
            if not m.name.startswith("_") and m.suffix == ".py"
        ]
        async for a in path.iterdir()
        if await a.is_dir() and (not a.name.startswith("__"))
    }


def _create_adapter(
    path: AsyncPath,
    name: str | None = None,
    module: str | None = None,
    class_name: str | None = None,
    category: str | None = None,
    pkg: str | None = None,
    enabled: bool = False,
    installed: bool = False,
) -> "Adapter":
    return Adapter(
        path=path,
        name=name or path.stem,
        class_name=class_name or camelize(path.parent.stem),
        category=category or path.parent.stem,
        module=module or ".".join(path.parts[-4:]).removesuffix(".py"),
        pkg=pkg or path.parent.parent.parent.stem,
        enabled=enabled,
        installed=installed,
    )


def _extract_adapter_modules(modules: list[AsyncPath], adapter: str) -> list["Adapter"]:
    adapter_modules = [_create_adapter(p) for p in modules]
    return [a for a in adapter_modules if a.category == adapter]


def import_adapter_with_context(
    adapter_categories: str | list[str] | None = None,
) -> t.Any:
    if _testing or "pytest" in sys.modules:
        return _handle_testing_mode(adapter_categories)

    normalized_categories = _normalize_adapter_categories(adapter_categories)

    try:
        # Check if we're in an async context
        import asyncio

        try:
            asyncio.get_running_loop()
            # We're in an async context - this function shouldn't be called here
            msg = (
                f"import_adapter_with_context() cannot be called from async context. "
                f"Use 'await gather_imports({normalized_categories})' directly."
            )
            raise RuntimeError(msg)
        except RuntimeError as e:
            if "no running event loop" in str(e):
                # No event loop - we need to start one for adapter imports
                # This should only happen in application initialization
                imported_adapters = asyncio.run(gather_imports(normalized_categories))
            else:
                raise
    except Exception as e:
        msg = f"Failed to install adapters {normalized_categories}: {e}"
        raise AdapterNotInstalled(
            msg,
        )
    return (
        imported_adapters[0]
        if len(imported_adapters) == 1
        else tuple(imported_adapters)
    )


def import_adapter(
    adapter_categories: str | list[str] | None = None,
) -> t.Any:
    """Import adapter(s) by category.

    Args:
        adapter_categories: Adapter category or list of categories to import

    Returns:
        Adapter instance(s) for the specified category(ies)
    """
    try:
        import asyncio

        try:
            asyncio.get_running_loop()
            # We're in an async context
            return gather_imports(_normalize_adapter_categories(adapter_categories))
        except RuntimeError as e:
            if "no running event loop" in str(e):
                # No event loop - we need to start one for adapter imports
                normalized_categories = _normalize_adapter_categories(
                    adapter_categories,
                )
                imported_adapters = asyncio.run(gather_imports(normalized_categories))
                return (
                    imported_adapters[0]
                    if len(imported_adapters) == 1
                    else tuple(imported_adapters)
                )
            # Re-raise the error if it's not about missing event loop
            raise
    except RuntimeError:
        # Not in an async context, so use the sync wrapper
        return import_adapter_with_context(adapter_categories)


# Initialize adapters on module load
def _initialize_adapter_registry() -> list["Adapter"]:
    adapters_path = AsyncPath(__file__).parent.parent
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(register_adapters(adapters_path))

    # If we're already in an event loop (e.g., within an ASGI server), run registration in background
    loop.create_task(register_adapters(adapters_path))
    return []


def get_adapter_class(category: str, adapter_name: str | None = None) -> t.Any:
    """Get an adapter class by category and optional name.

    Args:
        category: The category of the adapter
        adapter_name: Optional specific adapter name, if None uses configured adapter

    Returns:
        The adapter class
    """
    import importlib

    # First try to find a configured adapter
    adapter = get_adapter(category)
    if adapter and (adapter_name is None or adapter.name == adapter_name):
        with suppress(ImportError, AttributeError):
            module = importlib.import_module(adapter.module)
            return getattr(module, adapter.class_name)

    # If not found or name doesn't match, search for the named adapter
    if adapter_name:
        registry = _ensure_adapter_registry_initialized()
        for reg_adapter in registry:
            if reg_adapter.category == category and reg_adapter.name == adapter_name:
                try:
                    module = importlib.import_module(reg_adapter.module)
                    return getattr(module, reg_adapter.class_name)
                except (ImportError, AttributeError):
                    continue

    msg = f"No adapter found for category '{category}'{' and name ' + adapter_name if adapter_name else ''}"
    raise AdapterNotFound(
        msg,
    )


def try_import_adapter(category: str, adapter_name: str | None = None) -> t.Any | None:
    """Try to import an adapter, returning None if not found rather than raising an exception.

    Args:
        category: The category of the adapter
        adapter_name: Optional specific adapter name

    Returns:
        The imported adapter or None if not found
    """
    try:
        import asyncio

        # Check if we're in an async context
        with suppress(RuntimeError):
            asyncio.get_running_loop()
            # We're in an async context, need to handle differently
            # For now, return None as proper async handling would require more complex code
            return None
        # No event loop, safe to use asyncio.run

        # Import the adapter
        adapter = asyncio.run(gather_imports([category]))
        if adapter:
            return adapter[0]
        return None
    except (AdapterNotFound, AdapterNotInstalled, Exception):
        return None


adapters = _initialize_adapter_registry()
