"""Queue provider discovery system for ACB framework.

This module provides dynamic queue provider discovery and loading capabilities,
following ACB's adapter patterns with capability-based selection and
configuration overrides.
"""

import logging
from enum import Enum
from pathlib import Path
from uuid import UUID, uuid4

import typing as t
from contextlib import suppress
from pydantic import BaseModel, Field

from acb.config import Config
from acb.depends import depends

from ._base import QueueBase, QueueCapability, QueueMetadata, QueueSettings

logger = logging.getLogger(__name__)


class QueueProviderStatus(Enum):
    """Queue provider availability status."""

    AVAILABLE = "available"
    MISSING_DEPENDENCIES = "missing_dependencies"
    NOT_INSTALLED = "not_installed"
    DISABLED = "disabled"
    ERROR = "error"


class QueueProviderDescriptor(BaseModel):
    """Descriptor for a queue provider."""

    provider_id: UUID = Field(description="Unique provider identifier")
    name: str = Field(description="Provider name")
    module_path: str = Field(description="Python module path")
    class_name: str = Field(description="Queue class name")
    factory_function: str | None = Field(
        default=None,
        description="Factory function name",
    )

    # Metadata
    metadata: QueueMetadata | None = Field(
        default=None,
        description="Provider metadata",
    )
    status: QueueProviderStatus = Field(default=QueueProviderStatus.AVAILABLE)
    error_message: str | None = Field(
        default=None,
        description="Error message if unavailable",
    )

    # Configuration
    default_settings: dict[str, t.Any] = Field(default_factory=dict)
    config_schema: dict[str, t.Any] = Field(default_factory=dict)

    # Dependencies
    required_packages: list[str] = Field(default_factory=list)
    optional_packages: list[str] = Field(default_factory=list)


class QueueProviderNotFound(Exception):
    """Exception raised when a queue provider is not found."""

    def __init__(self, provider_name: str) -> None:
        self.provider_name = provider_name
        super().__init__(f"Queue provider not found: {provider_name}")


class QueueProviderNotInstalled(Exception):
    """Exception raised when a queue provider is not installed."""

    def __init__(self, provider_name: str, missing_packages: list[str]) -> None:
        self.provider_name = provider_name
        self.missing_packages = missing_packages
        super().__init__(
            f"Queue provider {provider_name} is not installed. "
            f"Missing packages: {', '.join(missing_packages)}",
        )


# Global provider registry
_provider_registry: dict[str, QueueProviderDescriptor] = {}
_provider_overrides: dict[str, str] = {}
_initialized = False


def generate_provider_id() -> UUID:
    """Generate a unique provider identifier.

    Returns:
        UUID7 identifier
    """
    return uuid4()


def create_queue_metadata_template() -> QueueMetadata:
    """Create a template QueueMetadata instance.

    Returns:
        QueueMetadata template
    """
    return QueueMetadata(
        queue_id=generate_provider_id(),
        name="Custom Queue Provider",
        description="Custom queue provider template",
        version="1.0.0",
        capabilities=[QueueCapability.BASIC_QUEUE],
    )


def register_queue_providers() -> None:
    """Register built-in queue providers."""
    global _provider_registry, _initialized

    if _initialized:
        return

    # Memory queue provider
    _provider_registry["memory"] = QueueProviderDescriptor(
        provider_id=generate_provider_id(),
        name="Memory Queue",
        module_path="acb.queues.memory",
        class_name="MemoryQueue",
        factory_function="create_memory_queue",
        required_packages=[],
        default_settings={
            "max_memory_usage": 100_000_000,
            "max_tasks_per_queue": 10_000,
        },
    )

    # Redis queue provider
    _provider_registry["redis"] = QueueProviderDescriptor(
        provider_id=generate_provider_id(),
        name="Redis Queue",
        module_path="acb.queues.redis",
        class_name="RedisQueue",
        factory_function="create_redis_queue",
        required_packages=["redis>=5.0.0"],
        default_settings={
            "redis_url": "redis://localhost:6379/0",
            "key_prefix": "acb:queue",
        },
    )

    # RabbitMQ queue provider
    _provider_registry["rabbitmq"] = QueueProviderDescriptor(
        provider_id=generate_provider_id(),
        name="RabbitMQ Queue",
        module_path="acb.queues.rabbitmq",
        class_name="RabbitMQQueue",
        factory_function="create_rabbitmq_queue",
        required_packages=["aio-pika>=9.0.0"],
        default_settings={
            "rabbitmq_url": "amqp://localhost:5672/",
            "exchange_name": "acb.tasks",
        },
    )

    _initialized = True
    logger.debug("Queue providers registered")


def _check_provider_dependencies(
    descriptor: QueueProviderDescriptor,
) -> tuple[QueueProviderStatus, str | None]:
    """Check if provider dependencies are available.

    Args:
        descriptor: Provider descriptor

    Returns:
        Tuple of (status, error_message)
    """
    import importlib.util

    missing_packages = []

    for package in descriptor.required_packages:
        # Extract package name (handle version specs)
        package_name = package.split(">=")[0].split("==")[0].split("<")[0].split(">")[0]

        spec = importlib.util.find_spec(package_name)
        if spec is None:
            missing_packages.append(package)

    if missing_packages:
        return (
            QueueProviderStatus.MISSING_DEPENDENCIES,
            f"Missing packages: {', '.join(missing_packages)}",
        )

    return QueueProviderStatus.AVAILABLE, None


def _load_provider_metadata(
    descriptor: QueueProviderDescriptor,
) -> QueueMetadata | None:
    """Load provider metadata from module.

    Args:
        descriptor: Provider descriptor

    Returns:
        QueueMetadata if available
    """
    try:
        import importlib

        module = importlib.import_module(descriptor.module_path)
        if hasattr(module, "MODULE_METADATA"):
            return module.MODULE_METADATA
    except Exception as e:
        logger.debug(f"Failed to load metadata for {descriptor.name}: {e}")

    return None


def get_queue_provider_class(provider_name: str) -> type[QueueBase]:
    """Get queue provider class by name.

    Args:
        provider_name: Provider name

    Returns:
        Queue class

    Raises:
        QueueProviderNotFound: If provider not found
        QueueProviderNotInstalled: If provider dependencies missing
    """
    register_queue_providers()

    # Check for override
    actual_provider = _provider_overrides.get(provider_name, provider_name)

    if actual_provider not in _provider_registry:
        raise QueueProviderNotFound(actual_provider)

    descriptor = _provider_registry[actual_provider]

    # Check dependencies
    status, _error_msg = _check_provider_dependencies(descriptor)
    if status == QueueProviderStatus.MISSING_DEPENDENCIES:
        raise QueueProviderNotInstalled(actual_provider, descriptor.required_packages)

    try:
        import importlib

        module = importlib.import_module(descriptor.module_path)
        queue_class = getattr(module, descriptor.class_name)

        # Update metadata if available
        if descriptor.metadata is None:
            descriptor.metadata = _load_provider_metadata(descriptor)

        return queue_class

    except ImportError as e:
        raise QueueProviderNotInstalled(
            actual_provider,
            descriptor.required_packages,
        ) from e
    except AttributeError as e:
        raise QueueProviderNotFound(actual_provider) from e


def get_queue_provider_descriptor(provider_name: str) -> QueueProviderDescriptor:
    """Get queue provider descriptor by name.

    Args:
        provider_name: Provider name

    Returns:
        QueueProviderDescriptor

    Raises:
        QueueProviderNotFound: If provider not found
    """
    register_queue_providers()

    # Check for override
    actual_provider = _provider_overrides.get(provider_name, provider_name)

    if actual_provider not in _provider_registry:
        raise QueueProviderNotFound(actual_provider)

    descriptor = _provider_registry[actual_provider]

    # Update status and metadata
    status, error_msg = _check_provider_dependencies(descriptor)
    descriptor.status = status
    descriptor.error_message = error_msg

    if descriptor.metadata is None:
        descriptor.metadata = _load_provider_metadata(descriptor)

    return descriptor


def get_queue_provider_info(provider_name: str) -> dict[str, t.Any]:
    """Get comprehensive information about a queue provider.

    Args:
        provider_name: Provider name

    Returns:
        Provider information dictionary
    """
    try:
        descriptor = get_queue_provider_descriptor(provider_name)

        info = {
            "name": descriptor.name,
            "provider_id": str(descriptor.provider_id),
            "module_path": descriptor.module_path,
            "class_name": descriptor.class_name,
            "status": descriptor.status.value,
            "required_packages": descriptor.required_packages,
            "optional_packages": descriptor.optional_packages,
            "default_settings": descriptor.default_settings,
        }

        if descriptor.error_message:
            info["error_message"] = descriptor.error_message

        if descriptor.metadata:
            info["metadata"] = {
                "version": descriptor.metadata.version,
                "description": descriptor.metadata.description,
                "capabilities": [cap.value for cap in descriptor.metadata.capabilities],
                "max_throughput": descriptor.metadata.max_throughput,
                "max_workers": descriptor.metadata.max_workers,
                "supports_clustering": descriptor.metadata.supports_clustering,
            }

        return info

    except QueueProviderNotFound:
        return {
            "name": provider_name,
            "status": QueueProviderStatus.NOT_INSTALLED.value,
            "error_message": f"Provider {provider_name} not found",
        }


def import_queue_provider(provider_name: str | None = None) -> type[QueueBase]:
    """Import a queue provider class with error handling.

    Args:
        provider_name: Provider name (default: from config)

    Returns:
        Queue class

    Raises:
        QueueProviderNotFound: If provider not found
        QueueProviderNotInstalled: If provider dependencies missing
    """
    if provider_name is None:
        # Get from configuration
        config = depends.get(Config)
        provider_name = getattr(config, "queue_provider", "memory")

    return get_queue_provider_class(provider_name or "memory")


def try_import_queue_provider(provider_name: str) -> type[QueueBase] | None:
    """Try to import a queue provider class without raising exceptions.

    Args:
        provider_name: Provider name

    Returns:
        Queue class or None if unavailable
    """
    try:
        return import_queue_provider(provider_name)
    except (QueueProviderNotFound, QueueProviderNotInstalled):
        return None


def list_queue_providers() -> list[str]:
    """List all available queue provider names.

    Returns:
        List of provider names
    """
    register_queue_providers()
    return list(_provider_registry.keys())


def list_available_queue_providers() -> list[str]:
    """List queue providers that have all dependencies available.

    Returns:
        List of available provider names
    """
    register_queue_providers()
    available = []

    for name, descriptor in _provider_registry.items():
        status, _ = _check_provider_dependencies(descriptor)
        if status == QueueProviderStatus.AVAILABLE:
            available.append(name)

    return available


def list_enabled_queue_providers() -> list[str]:
    """List enabled queue providers (same as available for now).

    Returns:
        List of enabled provider names
    """
    return list_available_queue_providers()


def list_queue_providers_by_capability(capability: QueueCapability) -> list[str]:
    """List queue providers that support a specific capability.

    Args:
        capability: Required capability

    Returns:
        List of provider names
    """
    register_queue_providers()
    matching = []

    for name, descriptor in _provider_registry.items():
        if descriptor.metadata and capability in descriptor.metadata.capabilities:
            # Check if dependencies are available
            status, _ = _check_provider_dependencies(descriptor)
            if status == QueueProviderStatus.AVAILABLE:
                matching.append(name)

    return matching


def enable_queue_provider(provider_name: str, target_provider: str) -> None:
    """Enable a queue provider override.

    Args:
        provider_name: Logical provider name
        target_provider: Actual provider to use
    """
    global _provider_overrides
    _provider_overrides[provider_name] = target_provider
    logger.info(
        f"Enabled queue provider override: {provider_name} -> {target_provider}",
    )


def disable_queue_provider(provider_name: str) -> None:
    """Disable a queue provider override.

    Args:
        provider_name: Provider name to disable override for
    """
    global _provider_overrides
    if provider_name in _provider_overrides:
        target = _provider_overrides.pop(provider_name)
        logger.info(f"Disabled queue provider override: {provider_name} -> {target}")


def get_queue_provider_override(provider_name: str) -> str | None:
    """Get the override target for a provider.

    Args:
        provider_name: Provider name

    Returns:
        Override target or None
    """
    return _provider_overrides.get(provider_name)


def apply_queue_provider_overrides(config_path: str | Path | None = None) -> None:
    """Apply queue provider overrides from configuration.

    Args:
        config_path: Path to configuration file
    """
    if config_path is None:
        config_path = Path("settings/queues.yaml")
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        logger.debug(f"Queue configuration file not found: {config_path}")
        return

    try:
        import yaml

        with config_path.open() as f:
            config = yaml.safe_load(f)

        overrides = config.get("provider_overrides", {})
        for provider_name, target_provider in overrides.items():
            enable_queue_provider(provider_name, target_provider)

        logger.info(f"Applied queue provider overrides from {config_path}")

    except Exception as e:
        logger.exception(f"Failed to apply queue provider overrides: {e}")


# Factory functions
def create_queue_instance(
    provider_name: str | None = None,
    settings: QueueSettings | None = None,
    **kwargs: t.Any,
) -> QueueBase:
    """Create a queue instance.

    Args:
        provider_name: Provider name (default: from config)
        settings: Queue settings
        **kwargs: Additional settings

    Returns:
        Queue instance
    """
    queue_class = import_queue_provider(provider_name)

    if settings is None:
        # Try to get provider-specific settings class
        with suppress(Exception):
            descriptor = get_queue_provider_descriptor(provider_name or "memory")
            if descriptor.default_settings:
                import importlib

                module = importlib.import_module(descriptor.module_path)
                settings_class_name = f"{descriptor.class_name}Settings"

                if hasattr(module, settings_class_name):
                    settings_class = getattr(module, settings_class_name)
                    settings = settings_class(**descriptor.default_settings, **kwargs)

    return queue_class(settings)


async def create_queue_instance_async(
    provider_name: str | None = None,
    settings: QueueSettings | None = None,
    **kwargs: t.Any,
) -> QueueBase:
    """Create and start a queue instance asynchronously.

    Args:
        provider_name: Provider name (default: from config)
        settings: Queue settings
        **kwargs: Additional settings

    Returns:
        Started queue instance
    """
    queue = create_queue_instance(provider_name, settings, **kwargs)
    await queue.start()
    return queue


# Context manager for queue instances
class QueueContext:
    """Context manager for queue instances."""

    def __init__(
        self,
        provider_name: str | None = None,
        settings: QueueSettings | None = None,
        **kwargs: t.Any,
    ) -> None:
        self.provider_name = provider_name
        self.settings = settings
        self.kwargs = kwargs
        self.queue: QueueBase | None = None

    async def __aenter__(self) -> QueueBase:
        """Enter the context manager."""
        self.queue = await create_queue_instance_async(
            self.provider_name,
            self.settings,
            **self.kwargs,
        )
        return self.queue

    async def __aexit__(self, exc_type: t.Any, exc_val: t.Any, exc_tb: t.Any) -> None:
        """Exit the context manager."""
        if self.queue:
            await self.queue.stop()


def queue_context(
    provider_name: str | None = None,
    settings: QueueSettings | None = None,
    **kwargs: t.Any,
) -> QueueContext:
    """Create a queue context manager.

    Args:
        provider_name: Provider name (default: from config)
        settings: Queue settings
        **kwargs: Additional settings

    Returns:
        QueueContext instance
    """
    return QueueContext(provider_name, settings, **kwargs)


# Auto-discovery initialization
def initialize_queue_discovery() -> None:
    """Initialize queue provider discovery."""
    register_queue_providers()

    # Apply configuration overrides
    try:
        apply_queue_provider_overrides()
    except Exception as e:
        logger.debug(f"Failed to apply queue provider overrides: {e}")

    logger.debug("Queue provider discovery initialized")


# Initialize on import
initialize_queue_discovery()
