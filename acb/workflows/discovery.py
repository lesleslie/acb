"""Workflow Discovery and Dynamic Import System.

Provides workflow engine discovery, registration, and dynamic import capabilities
following ACB's discovery pattern. This enables workflow engines to be
discoverable, registerable, and overridable through configuration.

Features:
- Dynamic workflow engine loading via import_workflow_engine()
- Workflow engine registry with metadata support
- Auto-discovery and configuration
- Override capability through settings/workflows.yaml
- Thread-safe registry using ContextVar
"""

from contextvars import ContextVar
from enum import Enum
from functools import lru_cache
from uuid import UUID

import typing as t
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

# UUID7 support (backport to UUID4 if not available)
uuid_lib: t.Any
try:
    import uuid_utils

    _uuid7_available = True
    uuid_lib = uuid_utils
except ImportError:
    import uuid

    _uuid7_available = False
    uuid_lib = uuid


class WorkflowEngineStatus(Enum):
    """Workflow engine development/stability status."""

    ALPHA = "alpha"
    BETA = "beta"
    STABLE = "stable"
    DEPRECATED = "deprecated"
    EXPERIMENTAL = "experimental"


class WorkflowCapability(Enum):
    """Workflow engine capability enumeration."""

    # Core workflow capabilities
    STEP_EXECUTION = "step_execution"
    DEPENDENCY_RESOLUTION = "dependency_resolution"
    PARALLEL_EXECUTION = "parallel_execution"
    STATE_MANAGEMENT = "state_management"
    ERROR_HANDLING = "error_handling"

    # Execution control
    PAUSE_RESUME = "pause_resume"
    CANCELLATION = "cancellation"
    RETRY_LOGIC = "retry_logic"
    TIMEOUT_HANDLING = "timeout_handling"
    CONDITIONAL_EXECUTION = "conditional_execution"

    # Scheduling and triggers
    SCHEDULED_EXECUTION = "scheduled_execution"
    EVENT_TRIGGERED = "event_triggered"
    WEBHOOK_TRIGGERED = "webhook_triggered"
    CRON_SCHEDULING = "cron_scheduling"

    # State persistence
    STATE_PERSISTENCE = "state_persistence"
    CHECKPOINT_RECOVERY = "checkpoint_recovery"
    TRANSACTION_SUPPORT = "transaction_support"
    ROLLBACK_CAPABILITY = "rollback_capability"

    # Integration
    EVENT_INTEGRATION = "event_integration"
    TASK_QUEUE_INTEGRATION = "task_queue_integration"
    CACHE_INTEGRATION = "cache_integration"
    STORAGE_INTEGRATION = "storage_integration"

    # Monitoring and observability
    EXECUTION_TRACKING = "execution_tracking"
    METRICS_COLLECTION = "metrics_collection"
    AUDIT_LOGGING = "audit_logging"
    PERFORMANCE_MONITORING = "performance_monitoring"

    # Advanced features
    DYNAMIC_WORKFLOWS = "dynamic_workflows"
    WORKFLOW_TEMPLATES = "workflow_templates"
    NESTED_WORKFLOWS = "nested_workflows"
    WORKFLOW_VERSIONING = "workflow_versioning"
    HOT_RELOAD = "hot_reload"


class WorkflowMetadata(BaseModel):
    """Metadata for workflow engine registration and discovery."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Identification
    engine_id: UUID = Field(description="Unique engine identifier (UUID7)")
    name: str = Field(description="Human-readable engine name")
    provider: str = Field(description="Engine provider/implementation name")
    version: str = Field(description="Engine version")

    # Status and compatibility
    status: WorkflowEngineStatus = Field(
        default=WorkflowEngineStatus.STABLE,
        description="Engine development status",
    )
    acb_min_version: str = Field(
        default="0.19.0",
        description="Minimum ACB version required",
    )

    # Capabilities
    capabilities: list[WorkflowCapability] = Field(
        default_factory=list,
        description="Supported workflow capabilities",
    )

    # Performance characteristics
    max_concurrent_workflows: int = Field(
        default=10,
        description="Maximum concurrent workflow executions",
    )
    max_concurrent_steps: int = Field(
        default=5,
        description="Maximum concurrent step executions per workflow",
    )
    default_timeout: float = Field(
        default=3600.0,
        description="Default workflow timeout in seconds",
    )

    # Dependencies
    required_packages: list[str] = Field(
        default_factory=list,
        description="Required Python packages",
    )
    optional_packages: list[str] = Field(
        default_factory=list,
        description="Optional packages for enhanced features",
    )

    # Documentation
    description: str = Field(description="Engine description")
    documentation_url: str | None = Field(
        default=None,
        description="Link to documentation",
    )
    examples_url: str | None = Field(default=None, description="Link to usage examples")

    # Registration info
    registered_at: datetime = Field(
        default_factory=datetime.now,
        description="Registration timestamp",
    )


# Thread-safe workflow engine registry
_workflow_engine_registry: ContextVar[dict[str, WorkflowMetadata] | None] = ContextVar(
    "_workflow_engine_registry",
    default=None,
)


def _ensure_workflow_engine_registry_initialized() -> dict[str, WorkflowMetadata]:
    """Ensure the workflow engine registry is initialized with an empty dict if needed."""
    registry = _workflow_engine_registry.get()
    if registry is None:
        registry = {}
        _workflow_engine_registry.set(registry)
    return registry


def generate_engine_id() -> UUID:
    """Generate a UUID7 identifier for workflow engine registration.

    Returns:
        UUID7 if available, otherwise UUID4 (as standard UUID)
    """
    if _uuid7_available:
        # Convert uuid_utils.UUID to standard uuid.UUID for pydantic compatibility
        uuid_obj: UUID = UUID(str(uuid_lib.uuid7()))
        return uuid_obj
    uuid_obj = uuid_lib.uuid4()
    return uuid_obj


def register_workflow_engine(metadata: WorkflowMetadata) -> None:
    """Register a workflow engine in the global registry.

    Args:
        metadata: Engine metadata for registration
    """
    registry = _ensure_workflow_engine_registry_initialized()
    registry[metadata.name] = metadata
    _workflow_engine_registry.set(registry)


def get_workflow_engine_descriptor(name: str) -> WorkflowMetadata | None:
    """Get workflow engine metadata by name.

    Args:
        name: Engine name to look up

    Returns:
        WorkflowMetadata if found, None otherwise
    """
    registry = _ensure_workflow_engine_registry_initialized()
    return registry.get(name)


def list_workflow_engines() -> list[WorkflowMetadata]:
    """List all registered workflow engines.

    Returns:
        List of all registered engine metadata
    """
    registry = _ensure_workflow_engine_registry_initialized()
    return list(registry.values())


def list_enabled_workflow_engines() -> list[WorkflowMetadata]:
    """List workflow engines that are not deprecated.

    Returns:
        List of active engine metadata
    """
    return [
        metadata
        for metadata in list_workflow_engines()
        if metadata.status != WorkflowEngineStatus.DEPRECATED
    ]


def list_available_workflow_engines(
    capability: WorkflowCapability | None = None,
) -> list[WorkflowMetadata]:
    """List available workflow engines, optionally filtered by capability.

    Args:
        capability: Optional capability filter

    Returns:
        List of matching engine metadata
    """
    engines = list_enabled_workflow_engines()

    if capability:
        engines = [e for e in engines if capability in e.capabilities]

    return engines


@lru_cache(maxsize=32)
def _resolve_workflow_engine_import(engine_type: str) -> tuple[str, str]:
    """Resolve workflow engine type to module and class name.

    Args:
        engine_type: Engine type identifier

    Returns:
        Tuple of (module_path, class_name)
    """
    # Static mappings for built-in engines
    static_mappings = {
        "basic": ("acb.workflows.engine", "BasicWorkflowEngine"),
        # Future engine types can be added here
    }

    if engine_type in static_mappings:
        return static_mappings[engine_type]

    # Default to basic engine if unknown
    return static_mappings["basic"]


def import_workflow_engine(engine_type: str | None = None) -> t.Any:
    """Dynamically import and return a workflow engine class.

    Args:
        engine_type: Engine type to import (defaults to 'basic')

    Returns:
        Workflow engine class

    Example:
        >>> WorkflowEngine = import_workflow_engine("basic")
        >>> engine = WorkflowEngine(max_concurrent_steps=5)
    """
    engine_type = engine_type or "basic"

    # Check for configuration override
    from acb.config import Config
    from acb.depends import depends

    config = depends.get_sync(Config)
    workflow_settings = config.settings_dict.get("workflows", {})
    override_engine = workflow_settings.get("engine_type")

    if override_engine:
        engine_type = override_engine

    # Resolve and import
    module_path, class_name = _resolve_workflow_engine_import(engine_type)

    try:
        import importlib

        module = importlib.import_module(module_path)
        return getattr(module, class_name)

    except (ImportError, AttributeError) as e:
        from acb.logger import Logger

        logger = depends.get_sync(Logger)
        logger.exception(f"Failed to import workflow engine {engine_type}: {e}")
        msg = (
            f"Could not import workflow engine: {engine_type}. "
            f"Module: {module_path}, Class: {class_name}"
        )
        raise ImportError(
            msg,
        ) from e


# Auto-register built-in engines
def _register_builtin_engines() -> None:
    """Register built-in workflow engines."""
    # Basic workflow engine
    basic_metadata = WorkflowMetadata(
        engine_id=generate_engine_id(),
        name="basic",
        provider="acb",
        version="1.0.0",
        status=WorkflowEngineStatus.STABLE,
        capabilities=[
            WorkflowCapability.STEP_EXECUTION,
            WorkflowCapability.DEPENDENCY_RESOLUTION,
            WorkflowCapability.PARALLEL_EXECUTION,
            WorkflowCapability.STATE_MANAGEMENT,
            WorkflowCapability.ERROR_HANDLING,
            WorkflowCapability.RETRY_LOGIC,
            WorkflowCapability.TIMEOUT_HANDLING,
            WorkflowCapability.EXECUTION_TRACKING,
        ],
        max_concurrent_workflows=10,
        max_concurrent_steps=5,
        default_timeout=3600.0,
        description="Basic workflow engine with dependency resolution and parallel execution",
    )
    register_workflow_engine(basic_metadata)


# Register on module import
_register_builtin_engines()


__all__ = [
    "WorkflowCapability",
    "WorkflowEngineStatus",
    "WorkflowMetadata",
    "generate_engine_id",
    "get_workflow_engine_descriptor",
    "import_workflow_engine",
    "list_available_workflow_engines",
    "list_enabled_workflow_engines",
    "list_workflow_engines",
    "register_workflow_engine",
]
