"""Base data transformation engine for ACB data processing.

This module provides the foundation for data transformation, including:
- Data transformation pipelines
- Streaming and batch processing
- Integration with Task Queue and Workflow systems
- Template-based transformations
"""

import asyncio
import typing as t
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field
from acb.services._base import ServiceBase, ServiceConfig, ServiceSettings


class TransformationMode(Enum):
    """Data transformation processing mode."""

    BATCH = "batch"
    STREAMING = "streaming"
    REAL_TIME = "real_time"
    SCHEDULED = "scheduled"


class TransformationState(Enum):
    """Transformation execution state."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


@dataclass
class TransformationResult:
    """Result of a data transformation operation."""

    transformation_id: str
    state: TransformationState
    input_count: int = 0
    output_count: int = 0
    error_count: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: float = 0.0
    error: str | None = None
    metadata: dict[str, t.Any] = field(default_factory=dict)


@dataclass
class TransformationStep:
    """Individual transformation step in a pipeline."""

    step_id: str
    name: str
    operation: str  # Name of the transformation operation
    config: dict[str, t.Any] = field(default_factory=dict)
    input_schema: dict[str, t.Any] | None = None
    output_schema: dict[str, t.Any] | None = None
    retry_attempts: int = 3
    retry_delay: float = 1.0
    timeout_seconds: float = 300.0
    continue_on_error: bool = False


class TransformationTemplate(BaseModel):
    """Template for defining data transformation pipelines."""

    template_id: str = Field(..., description="Unique template identifier")
    name: str = Field(..., description="Template name")
    description: str = Field(default="", description="Template description")
    steps: list[TransformationStep] = Field(
        default_factory=list,
        description="Transformation steps",
    )
    mode: TransformationMode = Field(
        default=TransformationMode.BATCH,
        description="Processing mode",
    )
    input_schema: dict[str, t.Any] | None = Field(
        default=None,
        description="Input data schema",
    )
    output_schema: dict[str, t.Any] | None = Field(
        default=None,
        description="Output data schema",
    )
    config: dict[str, t.Any] = Field(
        default_factory=dict,
        description="Transformation configuration",
    )
    tags: list[str] = Field(default_factory=list, description="Template tags")


class DataTransformer(ABC):
    """Abstract base class for data transformation engines."""

    @abstractmethod
    async def transform(
        self,
        template: TransformationTemplate,
        data: t.Any,
        context: dict[str, t.Any] | None = None,
    ) -> TransformationResult:
        """Execute a data transformation.

        Args:
            template: Transformation template to execute
            data: Input data to transform
            context: Optional execution context

        Returns:
            TransformationResult with execution details
        """
        ...

    @abstractmethod
    async def transform_batch(
        self,
        template: TransformationTemplate,
        data_batch: list[t.Any],
        context: dict[str, t.Any] | None = None,
    ) -> TransformationResult:
        """Execute batch data transformation.

        Args:
            template: Transformation template to execute
            data_batch: Batch of input data
            context: Optional execution context

        Returns:
            TransformationResult with execution details
        """
        ...

    @abstractmethod
    async def transform_stream(
        self,
        template: TransformationTemplate,
        data_stream: t.AsyncIterator[t.Any],
        context: dict[str, t.Any] | None = None,
    ) -> t.AsyncIterator[t.Any]:
        """Execute streaming data transformation.

        Args:
            template: Transformation template to execute
            data_stream: Async iterator of input data
            context: Optional execution context

        Yields:
            Transformed data items
        """
        ...

    @abstractmethod
    async def register_operation(
        self,
        name: str,
        handler: t.Callable[..., t.Awaitable[t.Any]],
    ) -> None:
        """Register a custom transformation operation.

        Args:
            name: Operation name
            handler: Async function implementing the operation
        """
        ...

    @abstractmethod
    async def get_template(self, template_id: str) -> TransformationTemplate | None:
        """Retrieve a transformation template by ID.

        Args:
            template_id: Template identifier

        Returns:
            TransformationTemplate if found, None otherwise
        """
        ...

    @abstractmethod
    async def save_template(self, template: TransformationTemplate) -> None:
        """Save a transformation template.

        Args:
            template: Template to save
        """
        ...


class TransformationConfig(ServiceConfig):
    """Configuration for transformation service."""

    max_concurrent_transformations: int = Field(
        default=10,
        description="Maximum concurrent transformations",
    )
    max_batch_size: int = Field(default=1000, description="Maximum items per batch")
    stream_buffer_size: int = Field(
        default=100,
        description="Stream processing buffer size",
    )
    default_timeout: float = Field(
        default=300.0,
        description="Default transformation timeout (seconds)",
    )
    enable_caching: bool = Field(
        default=True,
        description="Enable transformation result caching",
    )
    cache_ttl: int = Field(default=3600, description="Cache TTL in seconds")


class TransformationSettings(ServiceSettings):
    """Settings for transformation service."""

    transformation_config: TransformationConfig = Field(
        default_factory=TransformationConfig,
    )


class TransformationService(ServiceBase):
    """Base service for data transformation management."""

    def __init__(self, settings: TransformationSettings | None = None) -> None:
        """Initialize transformation service.

        Args:
            settings: Service settings
        """
        super().__init__()
        self._settings = settings or TransformationSettings()
        self._transformer: DataTransformer | None = None
        self._active_transformations: dict[str, asyncio.Task] = {}
        self._templates: dict[str, TransformationTemplate] = {}
        self._transformation_semaphore: asyncio.Semaphore | None = None

    async def _initialize(self) -> None:
        """Initialize transformation service."""
        config = self._settings.transformation_config
        self._transformation_semaphore = asyncio.Semaphore(
            config.max_concurrent_transformations,
        )

    async def submit_transformation(
        self,
        template: TransformationTemplate,
        data: t.Any,
        context: dict[str, t.Any] | None = None,
    ) -> str:
        """Submit a transformation for execution.

        Args:
            template: Transformation template
            data: Input data
            context: Optional execution context

        Returns:
            Transformation ID
        """
        self.increment_requests()

        async with self._transformation_semaphore:
            task = asyncio.create_task(
                self._execute_transformation_with_tracking(template, data, context),
            )
            self._active_transformations[template.template_id] = task
            return template.template_id

    async def _execute_transformation_with_tracking(
        self,
        template: TransformationTemplate,
        data: t.Any,
        context: dict[str, t.Any] | None,
    ) -> TransformationResult:
        """Execute transformation with tracking."""
        try:
            if self._transformer is None:
                msg = "Transformer not initialized"
                raise RuntimeError(msg)

            return await self._transformer.transform(template, data, context)
        finally:
            self._active_transformations.pop(template.template_id, None)

    async def get_transformation_status(
        self,
        transformation_id: str,
    ) -> dict[str, t.Any]:
        """Get transformation execution status.

        Args:
            transformation_id: Transformation identifier

        Returns:
            Status information
        """
        task = self._active_transformations.get(transformation_id)
        if task is None:
            return {"status": "not_found"}

        return {
            "status": "running" if not task.done() else "completed",
            "done": task.done(),
        }

    async def cancel_transformation(self, transformation_id: str) -> bool:
        """Cancel a running transformation.

        Args:
            transformation_id: Transformation to cancel

        Returns:
            True if cancelled, False if not found or already complete
        """
        task = self._active_transformations.get(transformation_id)
        if task is None or task.done():
            return False

        task.cancel()
        return True

    async def register_template(self, template: TransformationTemplate) -> None:
        """Register a transformation template.

        Args:
            template: Template to register
        """
        self._templates[template.template_id] = template
        if self._transformer:
            await self._transformer.save_template(template)

    async def get_template(self, template_id: str) -> TransformationTemplate | None:
        """Get a registered template.

        Args:
            template_id: Template identifier

        Returns:
            TransformationTemplate if found, None otherwise
        """
        return self._templates.get(template_id)

    async def list_templates(self) -> list[TransformationTemplate]:
        """List all registered templates.

        Returns:
            List of transformation templates
        """
        return list(self._templates.values())
