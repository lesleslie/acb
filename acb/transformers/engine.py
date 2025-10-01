"""Basic data transformation engine implementation.

Provides a flexible transformation engine with:
- Pipeline-based transformations
- Streaming and batch processing
- Custom operation registration
- Template management
"""

import asyncio
import typing as t
from datetime import datetime

from acb.logger import Logger

from ._base import (
    DataTransformer,
    TransformationResult,
    TransformationState,
    TransformationStep,
    TransformationTemplate,
)


class BasicTransformer(DataTransformer):
    """Basic data transformation engine with pipeline processing."""

    def __init__(
        self,
        max_batch_size: int = 1000,
        stream_buffer_size: int = 100,
    ) -> None:
        """Initialize basic transformer.

        Args:
            max_batch_size: Maximum items per batch
            stream_buffer_size: Buffer size for streaming
        """
        self._max_batch_size = max_batch_size
        self._stream_buffer_size = stream_buffer_size
        self._operations: dict[str, t.Callable[..., t.Awaitable[t.Any]]] = {}
        self._templates: dict[str, TransformationTemplate] = {}
        self._logger = Logger()

        # Register built-in operations
        self._register_builtin_operations()

    def _register_builtin_operations(self) -> None:
        """Register built-in transformation operations."""

        # Identity transformation (pass-through)
        async def identity(data: t.Any, config: dict[str, t.Any]) -> t.Any:
            return data

        # Map transformation
        async def map_transform(data: t.Any, config: dict[str, t.Any]) -> t.Any:
            field_mapping = config.get("mapping", {})
            if isinstance(data, dict):
                return {field_mapping.get(k, k): v for k, v in data.items()}
            return data

        # Filter transformation
        async def filter_transform(
            data: t.Any,
            config: dict[str, t.Any],
        ) -> t.Any | None:
            conditions = config.get("conditions", {})
            if isinstance(data, dict):
                for field, expected_value in conditions.items():
                    if data.get(field) != expected_value:
                        return None
            return data

        # Aggregate transformation
        async def aggregate_transform(
            data: list[t.Any],
            config: dict[str, t.Any],
        ) -> t.Any:
            operation = config.get("operation", "count")
            field = config.get("field")

            if operation == "count":
                return {"count": len(data)}
            if operation == "sum" and field:
                return {
                    "sum": sum(
                        item.get(field, 0) for item in data if isinstance(item, dict)
                    ),
                }
            if operation == "avg" and field:
                values = [item.get(field, 0) for item in data if isinstance(item, dict)]
                return {"avg": sum(values) / len(values) if values else 0}

            return data

        self._operations["identity"] = identity
        self._operations["map"] = map_transform
        self._operations["filter"] = filter_transform
        self._operations["aggregate"] = aggregate_transform

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
        self._operations[name] = handler

    async def get_template(self, template_id: str) -> TransformationTemplate | None:
        """Retrieve a transformation template by ID.

        Args:
            template_id: Template identifier

        Returns:
            TransformationTemplate if found, None otherwise
        """
        return self._templates.get(template_id)

    async def save_template(self, template: TransformationTemplate) -> None:
        """Save a transformation template.

        Args:
            template: Template to save
        """
        self._templates[template.template_id] = template

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
        result = TransformationResult(
            transformation_id=template.template_id,
            state=TransformationState.RUNNING,
            started_at=datetime.now(),
        )

        try:
            # Process through transformation pipeline
            current_data = data
            context = context or {}

            for step in template.steps:
                try:
                    current_data = await self._execute_step(step, current_data, context)
                    if current_data is None and not step.continue_on_error:
                        break
                except Exception as e:
                    result.error_count += 1
                    if not step.continue_on_error:
                        result.state = TransformationState.FAILED
                        result.error = str(e)
                        return result

            result.state = TransformationState.COMPLETED
            result.output_count = 1
            result.metadata["output"] = current_data

        except Exception as e:
            result.state = TransformationState.FAILED
            result.error = str(e)

        finally:
            result.completed_at = datetime.now()
            if result.started_at:
                result.duration_seconds = (
                    result.completed_at - result.started_at
                ).total_seconds()

        return result

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
        result = TransformationResult(
            transformation_id=template.template_id,
            state=TransformationState.RUNNING,
            started_at=datetime.now(),
            input_count=len(data_batch),
        )

        try:
            context = context or {}
            transformed_items = []

            # Process each item through the pipeline
            for item in data_batch:
                try:
                    current_data = item
                    for step in template.steps:
                        current_data = await self._execute_step(
                            step,
                            current_data,
                            context,
                        )
                        if current_data is None:
                            break

                    if current_data is not None:
                        transformed_items.append(current_data)
                        result.output_count += 1

                except Exception as e:
                    result.error_count += 1
                    if not template.config.get("continue_on_error", False):
                        result.state = TransformationState.FAILED
                        result.error = str(e)
                        return result

            result.state = TransformationState.COMPLETED
            result.metadata["output"] = transformed_items

        except Exception as e:
            result.state = TransformationState.FAILED
            result.error = str(e)

        finally:
            result.completed_at = datetime.now()
            if result.started_at:
                result.duration_seconds = (
                    result.completed_at - result.started_at
                ).total_seconds()

        return result

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
        context = context or {}
        buffer = []

        async for item in data_stream:
            try:
                current_data = item
                for step in template.steps:
                    current_data = await self._execute_step(step, current_data, context)
                    if current_data is None:
                        break

                if current_data is not None:
                    buffer.append(current_data)

                    # Yield when buffer is full
                    if len(buffer) >= self._stream_buffer_size:
                        for buffered_item in buffer:
                            yield buffered_item
                        buffer = []

            except Exception as e:
                self._logger.exception(f"Error transforming stream item: {e}")
                if not template.config.get("continue_on_error", False):
                    raise

        # Yield remaining buffered items
        for buffered_item in buffer:
            yield buffered_item

    async def _execute_step(
        self,
        step: TransformationStep,
        data: t.Any,
        context: dict[str, t.Any],
    ) -> t.Any:
        """Execute a single transformation step.

        Args:
            step: Transformation step to execute
            data: Input data
            context: Execution context

        Returns:
            Transformed data
        """
        operation = self._operations.get(step.operation)
        if operation is None:
            msg = f"Unknown operation: {step.operation}"
            raise ValueError(msg)

        # Execute with timeout
        try:
            return await asyncio.wait_for(
                operation(data, step.config),
                timeout=step.timeout_seconds,
            )
        except TimeoutError:
            msg = f"Step {step.step_id} timed out after {step.timeout_seconds}s"
            raise TimeoutError(msg) from None
