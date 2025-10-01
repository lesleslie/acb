"""Data transformer discovery and registration system.

Provides dynamic discovery and loading of data transformer implementations with:
- Capability-based feature detection
- Metadata-driven transformer selection
- Runtime transformer registration
- Performance optimization hints
"""

import importlib
import typing as t
from contextvars import ContextVar
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field
from acb.config import Config
from acb.depends import depends

if t.TYPE_CHECKING:
    from ._base import DataTransformer


def generate_transformer_id() -> UUID:
    """Generate a unique UUID7 identifier for a transformer.

    Returns:
        UUID: UUID7 identifier
    """
    import uuid_utils as uuid

    return uuid.uuid7()


class TransformerCapability(Enum):
    """Capabilities supported by data transformers."""

    # Core transformation capabilities
    BATCH_PROCESSING = "batch_processing"
    STREAMING = "streaming"
    REAL_TIME = "real_time"
    SCHEDULED = "scheduled"

    # Pipeline features
    PIPELINE_PROCESSING = "pipeline_processing"
    STEP_COMPOSITION = "step_composition"
    CONDITIONAL_BRANCHING = "conditional_branching"
    PARALLEL_PROCESSING = "parallel_processing"

    # Data operations
    MAPPING = "mapping"
    FILTERING = "filtering"
    AGGREGATION = "aggregation"
    ENRICHMENT = "enrichment"
    VALIDATION = "validation"
    NORMALIZATION = "normalization"

    # Advanced features
    CUSTOM_OPERATIONS = "custom_operations"
    TEMPLATE_MANAGEMENT = "template_management"
    SCHEMA_VALIDATION = "schema_validation"
    ERROR_HANDLING = "error_handling"
    RETRY_LOGIC = "retry_logic"
    TIMEOUT_MANAGEMENT = "timeout_management"

    # Performance features
    BUFFERING = "buffering"
    BATCHING = "batching"
    COMPRESSION = "compression"
    CACHING = "caching"

    # Integration capabilities
    TASK_QUEUE_INTEGRATION = "task_queue_integration"
    WORKFLOW_INTEGRATION = "workflow_integration"
    EVENT_STREAMING = "event_streaming"
    MONITORING = "monitoring"


class TransformerStatus(Enum):
    """Status of a data transformer implementation."""

    ALPHA = "alpha"
    BETA = "beta"
    STABLE = "stable"
    DEPRECATED = "deprecated"
    EXPERIMENTAL = "experimental"


class TransformerMetadata(BaseModel):
    """Metadata for a data transformer implementation."""

    transformer_id: UUID = Field(default_factory=generate_transformer_id)
    name: str = Field(..., description="Transformer name")
    provider: str = Field(..., description="Provider/vendor name")
    version: str = Field(..., description="Transformer version")
    acb_min_version: str = Field(default="0.19.0", description="Minimum ACB version")
    status: TransformerStatus = Field(
        default=TransformerStatus.STABLE, description="Transformer status",
    )
    capabilities: list[TransformerCapability] = Field(
        default_factory=list, description="Supported capabilities",
    )
    description: str = Field(default="", description="Transformer description")
    performance_hints: dict[str, t.Any] = Field(
        default_factory=dict, description="Performance optimization hints",
    )
    required_packages: list[str] = Field(
        default_factory=list, description="Required Python packages",
    )
    optional_packages: list[str] = Field(
        default_factory=list, description="Optional enhancement packages",
    )


# Transformer registry using ContextVar for thread safety
_transformer_registry: ContextVar[dict[str, type["DataTransformer"]]] = ContextVar(
    "_transformer_registry", default={},
)


def register_transformer(
    transformer_type: str, transformer_class: type["DataTransformer"],
) -> None:
    """Register a data transformer implementation.

    Args:
        transformer_type: Transformer type identifier
        transformer_class: Transformer class to register
    """
    registry = _transformer_registry.get().copy()
    registry[transformer_type] = transformer_class
    _transformer_registry.set(registry)


def get_registered_transformers() -> dict[str, type["DataTransformer"]]:
    """Get all registered transformer implementations.

    Returns:
        Dictionary mapping transformer types to classes
    """
    return _transformer_registry.get().copy()


def get_transformer_class(transformer_type: str) -> type["DataTransformer"] | None:
    """Get a registered transformer class by type.

    Args:
        transformer_type: Transformer type identifier

    Returns:
        Transformer class if found, None otherwise
    """
    return _transformer_registry.get().get(transformer_type)


def _resolve_transformer_import(transformer_type: str) -> tuple[str, str]:
    """Resolve the module path and class name for a transformer type.

    Args:
        transformer_type: Transformer type identifier

    Returns:
        Tuple of (module_path, class_name)

    Raises:
        ValueError: If transformer type is unknown
    """
    # Static mapping of transformer types to implementations
    transformer_map = {
        "basic": ("acb.transformers.engine", "BasicTransformer"),
        "default": ("acb.transformers.engine", "BasicTransformer"),
    }

    if transformer_type not in transformer_map:
        msg = f"Unknown transformer type: {transformer_type}"
        raise ValueError(msg)

    return transformer_map[transformer_type]


def import_transformer(transformer_type: str | None = None) -> t.Any:
    """Dynamically import and return a data transformer class.

    Args:
        transformer_type: Type of transformer to import (default: "basic")

    Returns:
        DataTransformer class

    Raises:
        ValueError: If transformer type is unknown
        ImportError: If transformer module cannot be imported

    Example:
        >>> Transformer = import_transformer("basic")
        >>> transformer = Transformer(max_batch_size=2000)
        >>> await transformer.initialize()
    """
    # Default to basic transformer
    transformer_type = transformer_type or "basic"

    # Check for configuration override
    config = depends.get(Config)
    transformer_settings = config.settings_dict.get("transformers", {})
    override_type = transformer_settings.get("transformer_type")

    if override_type:
        transformer_type = override_type

    # Check if already registered
    registered_class = get_transformer_class(transformer_type)
    if registered_class:
        return registered_class

    # Resolve and import
    module_path, class_name = _resolve_transformer_import(transformer_type)

    try:
        module = importlib.import_module(module_path)
        transformer_class = getattr(module, class_name)

        # Register for future use
        register_transformer(transformer_type, transformer_class)

        return transformer_class
    except ImportError as e:
        msg = f"Failed to import transformer '{transformer_type}': {e}"
        raise ImportError(msg) from e
    except AttributeError as e:
        msg = f"Transformer class '{class_name}' not found in {module_path}: {e}"
        raise ImportError(msg) from e


def get_transformer_metadata(transformer_type: str) -> TransformerMetadata | None:
    """Get metadata for a specific transformer type.

    Args:
        transformer_type: Transformer type identifier

    Returns:
        TransformerMetadata if found, None otherwise
    """
    try:
        module_path, _ = _resolve_transformer_import(transformer_type)
        module = importlib.import_module(module_path)

        if hasattr(module, "MODULE_METADATA"):
            return module.MODULE_METADATA
    except (ValueError, ImportError):
        pass

    return None


def list_available_transformers() -> list[str]:
    """List all available transformer types.

    Returns:
        List of transformer type identifiers
    """
    return ["basic", "default"]


def get_transformers_by_capability(
    capability: TransformerCapability,
) -> list[tuple[str, TransformerMetadata]]:
    """Find all transformers supporting a specific capability.

    Args:
        capability: Capability to search for

    Returns:
        List of (transformer_type, metadata) tuples
    """
    results = []

    for transformer_type in list_available_transformers():
        metadata = get_transformer_metadata(transformer_type)
        if metadata and capability in metadata.capabilities:
            results.append((transformer_type, metadata))

    return results


def get_best_transformer_for_mode(mode: str) -> str:
    """Get the best transformer for a specific processing mode.

    Args:
        mode: Processing mode ("batch", "streaming", "real_time", "scheduled")

    Returns:
        Transformer type identifier
    """
    # Map modes to required capabilities
    capability_map = {
        "batch": TransformerCapability.BATCH_PROCESSING,
        "streaming": TransformerCapability.STREAMING,
        "real_time": TransformerCapability.REAL_TIME,
        "scheduled": TransformerCapability.SCHEDULED,
    }

    required_capability = capability_map.get(mode)
    if not required_capability:
        return "basic"

    # Find transformers with the required capability
    matching = get_transformers_by_capability(required_capability)

    if not matching:
        return "basic"

    # Return the first stable transformer, or first available
    for transformer_type, metadata in matching:
        if metadata.status == TransformerStatus.STABLE:
            return transformer_type

    return matching[0][0]


# Module-level constants
__all__ = [
    "TransformerCapability",
    "TransformerMetadata",
    "TransformerStatus",
    "generate_transformer_id",
    "get_best_transformer_for_mode",
    "get_registered_transformers",
    "get_transformer_class",
    "get_transformer_metadata",
    "get_transformers_by_capability",
    "import_transformer",
    "list_available_transformers",
    "register_transformer",
]
