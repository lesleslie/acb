import os
import sys
import tempfile
from contextvars import ContextVar
from enum import Enum
from functools import lru_cache
from importlib import import_module, util
from inspect import stack
from pathlib import Path
from uuid import UUID

import asyncio

# Removed nest_asyncio import - not needed in library code
import rich.repr
import typing as t
from anyio import Path as AsyncPath
from datetime import datetime
from inflection import camelize
from msgspec.yaml import decode as yaml_decode
from pydantic import BaseModel, ConfigDict, Field

from acb.actions.encode import yaml_encode
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

    SCHEMA_VALIDATION = "schema_validation"
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
    ADAPTIVE_ROUTING = "adaptive_routing"
    FALLBACK_MECHANISMS = "fallback_mechanisms"
    TEXT_GENERATION = "text_generation"
    VISION_PROCESSING = "vision_processing"
    AUDIO_PROCESSING = "audio_processing"
    MODEL_QUANTIZATION = "model_quantization"
    COLD_START_OPTIMIZATION = "cold_start_optimization"

    # Embedding-specific capabilities
    BATCH_EMBEDDING = "batch_embedding"
    EDGE_OPTIMIZED = "edge_optimized"
    TEXT_PREPROCESSING = "text_preprocessing"
    VECTOR_NORMALIZATION = "vector_normalization"
    DIMENSION_SCALING = "dimension_scaling"
    SEMANTIC_SEARCH = "semantic_search"
    SIMILARITY_COMPUTATION = "similarity_computation"
    DOCUMENT_CHUNKING = "document_chunking"
    POOLING_STRATEGIES = "pooling_strategies"
    MEMORY_EFFICIENT_PROCESSING = "memory_efficient_processing"


class AdapterMetadata(BaseModel):
    module_id: UUID = Field(
        description="UUID7 identifier for this specific adapter module",
    )

    name: str = Field(description="Human-readable adapter name")
    category: str = Field(description="Adapter category (cache, sql, storage, etc.)")
    provider: str = Field(description="Technology provider (redis, mysql, s3, etc.)")

    version: str = Field(
        description="Semantic version of this adapter (independent of ACB version)",
    )
    acb_min_version: str = Field(description="Minimum ACB version required")
    acb_max_version: str | None = Field(
        default=None,
        description="Maximum ACB version supported (None = no limit)",
    )

    author: str = Field(description="Primary author/maintainer")
    created_date: str = Field(description="ISO date when adapter was created")
    last_modified: str = Field(description="ISO date of last significant update")

    status: AdapterStatus = Field(description="Development/stability status")
    capabilities: list[AdapterCapability] = Field(
        default_factory=list,
        description="List of features this adapter supports",
    )

    required_packages: list[str] = Field(
        default_factory=list,
        description="External packages required for this adapter",
    )
    optional_packages: dict[str, str] = Field(
        default_factory=dict,
        description="Optional packages and their purpose",
    )

    description: str = Field(description="Brief description of adapter functionality")
    documentation_url: str | None = Field(
        default=None,
        description="Link to detailed documentation",
    )
    repository_url: str | None = Field(
        default=None,
        description="Source code repository for this adapter",
    )

    settings_class: str = Field(description="Name of the settings class")
    config_example: dict[str, t.Any] | None = Field(
        default=None,
        description="Example configuration for this adapter",
    )

    custom: dict[str, t.Any] = Field(
        default_factory=dict,
        description="Custom metadata fields for specific requirements",
    )

    model_config = ConfigDict(use_enum_values=True, extra="forbid")


def generate_adapter_id() -> UUID:
    if _uuid7_available:
        uuid_obj = uuid_lib.uuid7()  # type: ignore[attr-defined]
        return (
            UUID(str(uuid_obj))
            if not isinstance(uuid_obj, UUID)
            else UUID(str(uuid_obj))
        )
    uuid_obj = uuid_lib.uuid4()
    # Explicitly cast to UUID to satisfy type checker
    return UUID(str(uuid_obj))


def create_metadata_template(
    name: str,
    category: str,
    provider: str,
    author: str,
    description: str,
    **kwargs: t.Any,
) -> AdapterMetadata:
    now = datetime.now().isoformat()

    return AdapterMetadata(
        module_id=generate_adapter_id(),
        name=name,
        category=category,
        provider=provider,
        version="1.0.0",
        acb_min_version="0.18.0",
        author=author,
        created_date=now,
        last_modified=now,
        status=AdapterStatus.ALPHA,
        description=description,
        settings_class=f"{category.title()}Settings",
        **kwargs,
    )


def validate_version_compatibility(
    adapter_metadata: AdapterMetadata,
    current_acb_version: str,
) -> bool:
    try:
        from packaging import version

        current = version.parse(current_acb_version)
        min_version = version.parse(adapter_metadata.acb_min_version)

        if current < min_version:
            return False

        if adapter_metadata.acb_max_version:
            max_version = version.parse(adapter_metadata.acb_max_version)
            if current > max_version:
                return False

        return True
    except ImportError:
        return current_acb_version >= adapter_metadata.acb_min_version


def extract_metadata_from_module(module: t.Any) -> AdapterMetadata | None:
    if hasattr(module, "MODULE_METADATA"):
        metadata = module.MODULE_METADATA
        if isinstance(metadata, AdapterMetadata):
            return metadata
        if isinstance(metadata, dict):
            return AdapterMetadata(**metadata)
    return None


def extract_metadata_from_class(adapter_class: type) -> AdapterMetadata | None:
    if hasattr(adapter_class, "__module_metadata__"):
        metadata = adapter_class.__module_metadata__
        if isinstance(metadata, AdapterMetadata):
            return metadata
        if isinstance(metadata, dict):
            return AdapterMetadata(**metadata)
    return None


def get_adapter_info(adapter_class: type) -> dict[str, t.Any]:
    info: dict[str, t.Any] = {
        "class_name": adapter_class.__name__,
        "module_path": adapter_class.__module__,
        "has_metadata": False,
    }
    metadata = extract_metadata_from_class(adapter_class)
    if metadata:
        info["has_metadata"] = True
        info["module_id"] = str(metadata.module_id)
        info["name"] = metadata.name
        info["category"] = metadata.category
        info["provider"] = metadata.provider
        info["version"] = metadata.version
        info["status"] = (
            metadata.status.value
            if hasattr(metadata.status, "value")
            else metadata.status
        )
        info["author"] = metadata.author
        info["capabilities"] = [
            cap.value if hasattr(cap, "value") else cap for cap in metadata.capabilities
        ]
        info["required_packages"] = metadata.required_packages
        info["description"] = metadata.description
        info["acb_min_version"] = metadata.acb_min_version
        info["acb_max_version"] = metadata.acb_max_version

    return info


def check_adapter_capability(
    adapter_class: type,
    capability: AdapterCapability,
) -> bool:
    metadata = extract_metadata_from_class(adapter_class)
    if metadata:
        return capability in metadata.capabilities
    return False


def list_adapter_capabilities(adapter_class: type) -> list[str]:
    metadata = extract_metadata_from_class(adapter_class)
    if metadata:
        return [
            cap.value if hasattr(cap, "value") else cap for cap in metadata.capabilities
        ]
    return []


def generate_adapter_report(adapter_class: type) -> str:
    info = get_adapter_info(adapter_class)
    if not info["has_metadata"]:
        return f"Adapter: {info['class_name']} (No metadata available)"

    return f"""
Adapter Report: {info["name"]}
{"=" * (16 + len(info["name"]))}

Basic Information:
  Module ID: {info["module_id"]}
  Category: {info["category"]}
  Provider: {info["provider"]}
  Version: {info["version"]}
  Status: {info["status"]}
  Author: {info["author"]}

Compatibility:
  ACB Min Version: {info["acb_min_version"]}
  ACB Max Version: {info["acb_max_version"] or "No limit"}

Capabilities ({len(info["capabilities"])}):
  {chr(10).join("- " + cap for cap in info["capabilities"])}

Dependencies ({len(info["required_packages"])}):
  {chr(10).join("- " + pkg for pkg in info["required_packages"])}

Description:
  {info["description"]}

Module: {info["module_path"]}
Class: {info["class_name"]}
""".strip()


# Removed nest_asyncio.apply() - not needed in library code
_deployed: bool = os.getenv("DEPLOYED", "False").lower() == "true"
_testing: bool = os.getenv("TESTING", "False").lower() == "true"
root_path: AsyncPath = AsyncPath(Path.cwd())
tmp_path: AsyncPath = root_path / "tmp"
adapters_path: AsyncPath = root_path / "adapters"
actions_path: AsyncPath = root_path / "actions"
settings_path: AsyncPath = root_path / "settings"
app_settings_path: AsyncPath = settings_path / "app.yaml"
debug_settings_path: AsyncPath = settings_path / "debug.yaml"
adapter_settings_path: AsyncPath = settings_path / "adapters.yaml"
secrets_path: AsyncPath = (
    AsyncPath(Path(tempfile.mkdtemp(prefix="mock_secrets_")))
    if _testing or "pytest" in sys.modules
    else tmp_path / "secrets"
)
_install_lock: ContextVar[list[str] | None] = ContextVar("install_lock", default=None)
_adapter_import_locks: ContextVar[dict[str, asyncio.Lock] | None] = ContextVar(
    "_adapter_import_locks",
    default=None,
)


class AdapterNotFound(Exception): ...


class AdapterNotInstalled(Exception): ...


class StaticImportError(ImportError): ...


AdapterClass = t.TypeVar("AdapterClass")


@t.runtime_checkable
class AdapterProtocol(t.Protocol):
    config: t.Any = None
    logger: t.Any = None

    async def init(self) -> None: ...


@rich.repr.auto
class Adapter(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

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


adapter_registry: ContextVar[list[Adapter] | None] = ContextVar(
    "adapter_registry", default=None
)
_enabled_adapters_cache: ContextVar[dict[str, Adapter] | None] = ContextVar(
    "_enabled_adapters_cache",
    default=None,
)
_installed_adapters_cache: ContextVar[dict[str, Adapter] | None] = ContextVar(
    "_installed_adapters_cache",
    default=None,
)
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
]


def _ensure_adapter_registry_initialized() -> list[Adapter]:
    """Ensure the adapter registry is initialized with an empty list if needed."""
    registry = adapter_registry.get()
    if registry is None:
        registry = []
        adapter_registry.set(registry)
    return registry


def _ensure_enabled_adapters_cache_initialized() -> dict[str, Adapter]:
    """Ensure the enabled adapters cache is initialized with an empty dict if needed."""
    cache = _enabled_adapters_cache.get()
    if cache is None:
        cache = {}
        _enabled_adapters_cache.set(cache)
    return cache


def _ensure_installed_adapters_cache_initialized() -> dict[str, Adapter]:
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
    enabled_cache = {}
    installed_cache = {}
    for adapter in _ensure_adapter_registry_initialized():
        if adapter.enabled:
            enabled_cache[adapter.category] = adapter
        if adapter.installed:
            installed_cache[adapter.category] = adapter
    _enabled_adapters_cache.set(enabled_cache)
    _installed_adapters_cache.set(installed_cache)


# Initialize the registry with core adapters
_ensure_adapter_registry_initialized().extend([*core_adapters])
_update_adapter_caches()


def get_adapter(category: str) -> Adapter | None:
    cache = _ensure_enabled_adapters_cache_initialized()
    return cache.get(category)


def get_adapters() -> list[Adapter]:
    cache = _ensure_enabled_adapters_cache_initialized()
    return list(cache.values())


def get_installed_adapter(category: str) -> Adapter | None:
    cache = _ensure_installed_adapters_cache_initialized()
    return cache.get(category)


def get_installed_adapters() -> list[Adapter]:
    cache = _ensure_installed_adapters_cache_initialized()
    return list(cache.values())


# Static adapter mappings for improved performance
# This eliminates the need for dynamic string construction and reduces import overhead
STATIC_ADAPTER_MAPPINGS = {
    "cache.memory": ("acb.adapters.cache.memory", "Cache"),
    "cache.redis": ("acb.adapters.cache.redis", "Cache"),
    "logger": ("acb.adapters.logger.loguru", "Logger"),  # Default logger (loguru)
    "logger.loguru": ("acb.adapters.logger.loguru", "Logger"),
    "logger.structlog": ("acb.adapters.logger.structlog", "Logger"),
    "logger.logly": ("acb.adapters.logger.logly", "Logger"),
    "sql.mysql": ("acb.adapters.sql.mysql", "Sql"),
    "sql.pgsql": ("acb.adapters.sql.pgsql", "Sql"),
    "sql.sqlite": ("acb.adapters.sql.sqlite", "Sql"),
    "nosql.mongodb": ("acb.adapters.nosql.mongodb", "Nosql"),
    "nosql.firestore": ("acb.adapters.nosql.firestore", "Nosql"),
    "nosql.redis": ("acb.adapters.nosql.redis", "Nosql"),
    "storage.file": ("acb.adapters.storage.file", "Storage"),
    "storage.s3": ("acb.adapters.storage.s3", "Storage"),
    "storage.azure": ("acb.adapters.storage.azure", "Storage"),
    "storage.cloud_storage": ("acb.adapters.storage.cloud_storage", "Storage"),
    "storage.memory": ("acb.adapters.storage.memory", "Storage"),
    "secret.infisical": ("acb.adapters.secret.infisical", "Secret"),
    "secret.secret_manager": ("acb.adapters.secret.secret_manager", "Secret"),
    "secret.azure": ("acb.adapters.secret.azure", "Secret"),
    "secret.cloudflare": ("acb.adapters.secret.cloudflare", "Secret"),
    "monitoring.sentry": ("acb.adapters.monitoring.sentry", "Monitoring"),
    "monitoring.logfire": ("acb.adapters.monitoring.logfire", "Monitoring"),
    "requests.httpx": ("acb.adapters.requests.httpx", "Requests"),
    "requests.niquests": ("acb.adapters.requests.niquests", "Requests"),
    "smtp.gmail": ("acb.adapters.smtp.gmail", "Smtp"),
    "smtp.mailgun": ("acb.adapters.smtp.mailgun", "Smtp"),
    "dns.cloud_dns": ("acb.adapters.dns.cloud_dns", "Dns"),
    "dns.cloudflare": ("acb.adapters.dns.cloudflare", "Dns"),
    "dns.route53": ("acb.adapters.dns.route53", "Dns"),
    "ftpd.ftp": ("acb.adapters.ftpd.ftp", "Ftpd"),
    "ftpd.sftp": ("acb.adapters.ftpd.sftp", "Ftpd"),
    "models": ("acb.adapters.models", "Models"),
    "vector.duckdb": ("acb.adapters.vector.duckdb", "Vector"),
    "vector.pinecone": ("acb.adapters.vector.pinecone", "Vector"),
    "vector.qdrant": ("acb.adapters.vector.qdrant", "Vector"),
    "vector.weaviate": ("acb.adapters.vector.weaviate", "Vector"),
    "graph.neo4j": ("acb.adapters.graph.neo4j", "Graph"),
    "graph.neptune": ("acb.adapters.graph.neptune", "Graph"),
    "graph.arangodb": ("acb.adapters.graph.arangodb", "Graph"),
    # Pub/Sub adapters for events system
    "pubsub.memory": ("acb.adapters.messaging.memory", "MemoryPubSub"),
    "pubsub.redis": ("acb.adapters.messaging.redis", "RedisPubSub"),
    "pubsub.rabbitmq": ("acb.adapters.messaging.rabbitmq", "RabbitMQPubSub"),
    "pubsub.aiormq": ("acb.adapters.messaging.aiormq", "AioRmqPubSub"),
    # Queue adapters for tasks system
    "queue.memory": ("acb.adapters.messaging.memory", "MemoryQueue"),
    "queue.redis": ("acb.adapters.messaging.redis", "RedisQueue"),
    "queue.rabbitmq": ("acb.adapters.messaging.rabbitmq", "RabbitMQQueue"),
    "queue.aiormq": ("acb.adapters.messaging.aiormq", "AioRmqQueue"),
    # Task system adapters
    "tasks.memory": ("acb.tasks.memory", "TaskSystem"),
    "tasks.redis": ("acb.tasks.redis", "TaskSystem"),
    "tasks.rabbitmq": ("acb.tasks.rabbitmq", "TaskSystem"),
    "tasks.apscheduler": ("acb.tasks.apscheduler", "TaskSystem"),
    "ai.cloud": ("acb.adapters.ai.cloud", "CloudAI"),
    "ai.edge": ("acb.adapters.ai.edge", "EdgeAI"),
    "ai.hybrid": ("acb.adapters.ai.hybrid", "HybridAI"),
    "embedding.openai": ("acb.adapters.embedding.openai", "Embedding"),
    "embedding.huggingface": ("acb.adapters.embedding.huggingface", "Embedding"),
    "embedding.sentence_transformers": (
        "acb.adapters.embedding.sentence_transformers",
        "Embedding",
    ),
    "embedding.onnx": ("acb.adapters.embedding.onnx", "Embedding"),
    "embedding.lfm": ("acb.adapters.embedding.lfm", "Embedding"),
    "reasoning.langchain": ("acb.adapters.reasoning.langchain", "Reasoning"),
    "reasoning.llamaindex": ("acb.adapters.reasoning.llamaindex", "Reasoning"),
    "reasoning.custom": ("acb.adapters.reasoning.custom", "Reasoning"),
    "reasoning.openai_functions": (
        "acb.adapters.reasoning.openai_functions",
        "Reasoning",
    ),
    "type.zuban": ("acb.adapters.type.zuban", "ZubanAdapter"),
}


@lru_cache(maxsize=256)
def get_adapter_class(category: str, name: str) -> type[t.Any]:
    """Get adapter class with optimized static mappings and caching.

    This function uses pre-computed static mappings for better performance
    and falls back to dynamic import for custom adapters.
    """
    # Try static mapping first for maximum performance
    mapping_key = f"{category}.{name}" if name != category else category
    if mapping_key in STATIC_ADAPTER_MAPPINGS:
        module_path, class_name = STATIC_ADAPTER_MAPPINGS[mapping_key]
        return _import_adapter_class_cached(module_path, class_name)

    # Fallback to dynamic import for custom adapters
    module_path = f"acb.adapters.{category}.{name}"
    class_name = camelize(category)
    return _import_adapter_class_cached(module_path, class_name)


@lru_cache(maxsize=512)
def _import_adapter_class_cached(module_path: str, class_name: str) -> type:
    """Cached adapter class import to avoid repeated module loading."""
    try:
        module = import_module(module_path)
        adapter_class = getattr(module, class_name)

        # Attach metadata if available
        if hasattr(module, "MODULE_METADATA"):
            metadata = module.MODULE_METADATA
            if isinstance(metadata, AdapterMetadata):
                adapter_class.__module_metadata__ = metadata
            elif isinstance(metadata, dict):
                adapter_class.__module_metadata__ = AdapterMetadata(**metadata)

        return adapter_class  # type: ignore[no-any-return]
    except (ImportError, AttributeError) as e:
        msg = f"Failed to import {module_path}.{class_name}: {e}"
        raise StaticImportError(msg)


def try_import_adapter(category: str, name: str | None = None) -> type[t.Any] | None:
    if name is None:
        adapter_info = get_adapter(category)
        if adapter_info:
            name = adapter_info.name
        else:
            return None
    try:
        return get_adapter_class(category, name)
    except StaticImportError:
        return None


def import_adapter_fast(category: str, name: str | None = None) -> type[t.Any]:
    adapter_class = try_import_adapter(category, name)
    if adapter_class is None:
        available_adapters = list(_get_available_adapters(category))
        msg = (
            f"Could not import {category} adapter '{name}'. "
            f"Available: {available_adapters}"
        )
        raise ImportError(
            msg,
        )
    return adapter_class


def _get_available_adapters(category: str) -> t.Iterator[str]:
    for adapter in _ensure_adapter_registry_initialized():
        if adapter.category == category:
            yield adapter.name


_adapter_config_loaded: bool = False


async def _ensure_adapter_configuration() -> None:
    global _adapter_config_loaded
    if _adapter_config_loaded or _should_skip_configuration():
        return
    _adapter_config_loaded = True
    try:
        await _setup_adapter_configuration()
    except Exception:
        import traceback

        traceback.print_exc()


def _should_skip_configuration() -> bool:
    from acb.config import _library_usage_mode

    return _testing or "pytest" in sys.modules or _library_usage_mode


async def _setup_adapter_configuration() -> None:
    cwd_path = AsyncPath(Path.cwd())
    if await _should_skip_project_setup(cwd_path):
        return
    cwd_settings_path = cwd_path / "settings"
    cwd_adapter_settings_path = cwd_settings_path / "adapters.yaml"
    await _create_adapter_settings_if_needed(
        cwd_settings_path,
        cwd_adapter_settings_path,
    )
    await _load_and_apply_adapter_settings(cwd_adapter_settings_path)


async def _should_skip_project_setup(cwd_path: AsyncPath) -> bool:
    if cwd_path.stem == "acb":
        return True
    has_pyproject = await (cwd_path / "pyproject.toml").exists()
    if has_pyproject:
        has_src = await (cwd_path / "src").exists()
        has_acb_dir = await (cwd_path / "acb").exists()
        is_acb_package = (
            has_acb_dir and await (cwd_path / "acb" / "__init__.py").exists()
        )
        has_settings = await (cwd_path / "settings").exists()
        if has_settings:
            return False
        has_package_dir = await (cwd_path / cwd_path.stem).exists()
        return has_src or has_package_dir or is_acb_package

    return False


async def _create_adapter_settings_if_needed(
    cwd_settings_path: AsyncPath,
    cwd_adapter_settings_path: AsyncPath,
) -> None:
    if _testing or "pytest" in sys.modules:
        return

    from acb.config import _library_usage_mode

    if _library_usage_mode:
        return

    if not await cwd_adapter_settings_path.exists() and not _deployed:
        await cwd_settings_path.mkdir(exist_ok=True)
        categories = {a.category for a in _ensure_adapter_registry_initialized()}
        settings_dict = {
            cat: None for cat in categories if cat not in ("logger", "config")
        }
        await cwd_adapter_settings_path.write_bytes(
            yaml_encode(settings_dict, sort_keys=True),
        )


async def _load_and_apply_adapter_settings(
    cwd_adapter_settings_path: AsyncPath,
) -> None:
    if not await cwd_adapter_settings_path.exists():
        return

    enabled_adapters = await _load_enabled_adapters(cwd_adapter_settings_path)
    await _ensure_package_registration()
    all_adapters = await _collect_all_adapters()
    _enable_configured_adapters(all_adapters, enabled_adapters)
    _update_adapter_caches()


async def _load_enabled_adapters(
    cwd_adapter_settings_path: AsyncPath,
) -> dict[str, str]:
    _adapters = yaml_decode(await cwd_adapter_settings_path.read_text())
    return {a: m for a, m in _adapters.items() if m}


async def _ensure_package_registration() -> None:
    from acb import ensure_registration_async, get_context

    await ensure_registration_async()
    for pkg in get_context().pkg_registry.get():
        if not pkg.adapters:
            from contextlib import suppress

            with suppress(Exception):
                await register_adapters(pkg.path)


async def _collect_all_adapters() -> list[Adapter]:
    from acb import get_context

    all_adapters = _ensure_adapter_registry_initialized().copy()
    for pkg in get_context().pkg_registry.get():
        for adapter in pkg.adapters:
            if adapter not in all_adapters:
                _ensure_adapter_registry_initialized().append(adapter)
                all_adapters.append(adapter)

    return all_adapters


def _enable_configured_adapters(
    all_adapters: list[Adapter],
    enabled_adapters: dict[str, str],
) -> None:
    for adapter in all_adapters:
        if enabled_adapters.get(adapter.category) == adapter.name:
            adapter.enabled = True


async def _import_adapter_module_for_deps(adapter_category: str) -> None:
    from contextlib import suppress

    if adapter_category == "app":
        for adapter in _ensure_adapter_registry_initialized():
            if adapter.category == adapter_category:
                with suppress(ImportError, AdapterNotFound, AdapterNotInstalled):
                    import_module(adapter.module)
                break


async def _find_adapter(adapter_category: str) -> Adapter:
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
                    await _ensure_adapter_configuration()
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


async def _load_module(adapter: Adapter) -> t.Any:
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
    adapter: Adapter,
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
    instance = await depends.get(adapter_class)
    if hasattr(instance, "init"):
        init_result = instance.init()
        if hasattr(init_result, "__await__"):
            await init_result
    from acb.logger import Logger

    logger = await depends.get(Logger)
    logger.info(f"Adapter initialized: {adapter.class_name}")
    return adapter_class


async def _import_adapter(adapter_category: str) -> t.Any:
    if _testing or "pytest" in sys.modules:
        from unittest.mock import MagicMock

        return MagicMock()
    await _ensure_adapter_configuration()
    await _import_adapter_module_for_deps(adapter_category)
    adapter = await _find_adapter(adapter_category)
    module = await _load_module(adapter)
    adapter_class: t.Any = getattr(module, adapter.class_name)
    if adapter.installed:
        return adapter_class
    locks = _ensure_adapter_import_locks_initialized()
    if adapter_category not in locks:
        locks[adapter_category] = asyncio.Lock()
    async with locks[adapter_category]:
        if adapter.installed:
            return adapter_class
        try:
            adapter.installed = True
            return await _initialize_adapter(adapter, module, adapter_category)
        except Exception as e:
            adapter.installed = False
            msg = f"Failed to install {adapter.class_name} adapter: {e}"
            raise AdapterNotInstalled(
                msg,
            )


async def gather_imports(adapter_categories: list[str]) -> t.Any:
    imports = [_import_adapter(category) for category in adapter_categories]
    _imports = await asyncio.gather(*imports, return_exceptions=True)
    results = []
    for result in _imports:
        if isinstance(result, Exception):
            raise result
        results.append(result)
    return results


def import_adapter(adapter_categories: str | list[str] | None = None) -> t.Any:
    if isinstance(adapter_categories, str):
        adapter_info = get_adapter(adapter_categories)
        adapter_name = adapter_info.name if adapter_info else None
        adapter_class = try_import_adapter(adapter_categories, adapter_name)
        if adapter_class:
            return adapter_class
        return import_adapter_with_context([adapter_categories])

    return import_adapter_with_context(adapter_categories)


def _extract_adapter_categories_from_stack() -> list[str]:
    frame_idx = 1
    for i in range(1, min(4, len(stack()))):
        frame_context = str(stack()[i][4]) if stack()[i][4] else ""
        if "import_adapter_with_context" in frame_context:
            frame_idx = i + 1
            break
    context = stack()[frame_idx][4]
    return [
        c.strip()
        for c in (context[0] if context else "")
        .split("=")[0]
        .strip()
        .lower()
        .split(",")
    ]


def _handle_testing_mode(adapter_categories: str | list[str] | None) -> t.Any:
    from unittest.mock import MagicMock

    if isinstance(adapter_categories, str):
        return MagicMock()
    if not adapter_categories:
        try:
            adapter_categories = _extract_adapter_categories_from_stack()
        except (IndexError, AttributeError, TypeError):
            return MagicMock()

    return tuple(MagicMock() for _ in adapter_categories)


def _normalize_adapter_categories(
    adapter_categories: str | list[str] | None,
) -> list[str]:
    if isinstance(adapter_categories, str):
        return [adapter_categories]

    if not adapter_categories:
        try:
            return _extract_adapter_categories_from_stack()
        except (IndexError, AttributeError, TypeError):
            msg = "Could not determine adapter categories from calling context"
            raise ValueError(
                msg,
            )

    return adapter_categories


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


async def path_adapters(path: AsyncPath) -> dict[str, list[AsyncPath]]:
    return {
        a.stem: [
            m
            async for m in a.iterdir()
            if not m.name.startswith("_") and m.suffix == ".py"
        ]
        async for a in path.iterdir()
        if await a.is_dir() and (not a.name.startswith("__"))
    }


def create_adapter(
    path: AsyncPath,
    name: str | None = None,
    module: str | None = None,
    class_name: str | None = None,
    category: str | None = None,
    pkg: str | None = None,
    enabled: bool = False,
    installed: bool = False,
) -> Adapter:
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


def extract_adapter_modules(modules: list[AsyncPath], adapter: str) -> list[Adapter]:
    adapter_modules = [create_adapter(p) for p in modules]
    return [a for a in adapter_modules if a.category == adapter]


async def register_adapters(path: AsyncPath) -> list[Adapter]:
    if _testing or "pytest" in sys.modules:
        return []
    _adapters_path = path / "adapters"
    if not (await _adapters_path.exists()):
        return []
    pkg_adapters = await path_adapters(_adapters_path)
    _adapters: list[Adapter] = []
    for adapter_name, modules in pkg_adapters.items():
        _modules = extract_adapter_modules(modules, adapter_name)
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


adapters = asyncio.run(register_adapters(AsyncPath(__file__).parent.parent))
