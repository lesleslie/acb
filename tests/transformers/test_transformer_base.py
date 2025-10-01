"""Tests for base transformation components."""

import asyncio

import pytest

from acb.transformers import (
    BasicTransformer,
    TransformationMode,
    TransformationState,
    TransformationStep,
    TransformationTemplate,
)


@pytest.fixture
def transformer():
    """Create a basic transformer for testing."""
    return BasicTransformer(max_batch_size=100, stream_buffer_size=10)


@pytest.fixture
def simple_template():
    """Create a simple transformation template."""
    return TransformationTemplate(
        template_id="test-template",
        name="Test Template",
        description="Simple test template",
        steps=[
            TransformationStep(
                step_id="step1",
                name="Identity",
                operation="identity",
                config={},
            )
        ],
        mode=TransformationMode.BATCH,
    )


@pytest.fixture
def mapping_template():
    """Create a mapping transformation template."""
    return TransformationTemplate(
        template_id="mapping-template",
        name="Mapping Template",
        steps=[
            TransformationStep(
                step_id="map1",
                name="Map Fields",
                operation="map",
                config={"mapping": {"old_name": "new_name", "old_value": "new_value"}},
            )
        ],
    )


@pytest.fixture
def filter_template():
    """Create a filter transformation template."""
    return TransformationTemplate(
        template_id="filter-template",
        name="Filter Template",
        steps=[
            TransformationStep(
                step_id="filter1",
                name="Filter Active",
                operation="filter",
                config={"conditions": {"active": True}},
            )
        ],
    )


class TestBasicTransformer:
    """Tests for BasicTransformer."""

    async def test_initialization(self, transformer):
        """Test transformer initialization."""
        assert transformer._max_batch_size == 100
        assert transformer._stream_buffer_size == 10
        assert "identity" in transformer._operations
        assert "map" in transformer._operations
        assert "filter" in transformer._operations

    async def test_simple_transform(self, transformer, simple_template):
        """Test simple identity transformation."""
        data = {"name": "test", "value": 123}
        result = await transformer.transform(simple_template, data)

        assert result.state == TransformationState.COMPLETED
        assert result.output_count == 1
        assert result.error_count == 0
        assert result.metadata["output"] == data

    async def test_mapping_transform(self, transformer, mapping_template):
        """Test field mapping transformation."""
        data = {"old_name": "John", "old_value": 42, "other": "unchanged"}
        result = await transformer.transform(mapping_template, data)

        assert result.state == TransformationState.COMPLETED
        output = result.metadata["output"]
        assert output["new_name"] == "John"
        assert output["new_value"] == 42
        assert output["other"] == "unchanged"

    async def test_filter_transform_pass(self, transformer, filter_template):
        """Test filter transformation with passing condition."""
        data = {"name": "test", "active": True}
        result = await transformer.transform(filter_template, data)

        assert result.state == TransformationState.COMPLETED
        assert result.metadata["output"] == data

    async def test_filter_transform_fail(self, transformer, filter_template):
        """Test filter transformation with failing condition."""
        data = {"name": "test", "active": False}
        result = await transformer.transform(filter_template, data)

        assert result.state == TransformationState.COMPLETED
        assert result.metadata["output"] is None

    async def test_batch_transform(self, transformer, simple_template):
        """Test batch transformation."""
        data_batch = [
            {"id": 1, "name": "item1"},
            {"id": 2, "name": "item2"},
            {"id": 3, "name": "item3"},
        ]

        result = await transformer.transform_batch(simple_template, data_batch)

        assert result.state == TransformationState.COMPLETED
        assert result.input_count == 3
        assert result.output_count == 3
        assert result.error_count == 0
        assert len(result.metadata["output"]) == 3

    async def test_batch_transform_with_filter(self, transformer, filter_template):
        """Test batch transformation with filtering."""
        data_batch = [
            {"id": 1, "active": True},
            {"id": 2, "active": False},
            {"id": 3, "active": True},
        ]

        result = await transformer.transform_batch(filter_template, data_batch)

        assert result.state == TransformationState.COMPLETED
        assert result.input_count == 3
        assert result.output_count == 2  # Only 2 items pass filter
        assert len(result.metadata["output"]) == 2

    async def test_stream_transform(self, transformer, simple_template):
        """Test streaming transformation."""

        async def data_generator():
            for i in range(5):
                yield {"id": i, "name": f"item{i}"}

        output_items = []
        async for item in transformer.transform_stream(
            simple_template, data_generator()
        ):
            output_items.append(item)

        assert len(output_items) == 5
        assert all("id" in item and "name" in item for item in output_items)

    async def test_stream_transform_with_buffer(self, transformer, simple_template):
        """Test streaming transformation with buffering."""
        # Create transformer with small buffer
        small_buffer_transformer = BasicTransformer(stream_buffer_size=3)

        async def data_generator():
            for i in range(10):
                yield {"id": i}

        output_items = []
        async for item in small_buffer_transformer.transform_stream(
            simple_template, data_generator()
        ):
            output_items.append(item)

        assert len(output_items) == 10

    async def test_pipeline_transform(self, transformer):
        """Test multi-step pipeline transformation."""
        template = TransformationTemplate(
            template_id="pipeline",
            name="Pipeline",
            steps=[
                TransformationStep(
                    step_id="map",
                    name="Map",
                    operation="map",
                    config={"mapping": {"old": "new"}},
                ),
                TransformationStep(
                    step_id="filter",
                    name="Filter",
                    operation="filter",
                    config={"conditions": {"active": True}},
                ),
            ],
        )

        data = {"old": "value", "active": True}
        result = await transformer.transform(template, data)

        assert result.state == TransformationState.COMPLETED
        output = result.metadata["output"]
        assert "new" in output
        assert output["new"] == "value"

    async def test_custom_operation_registration(self, transformer):
        """Test registering custom operations."""

        async def custom_operation(data, config):
            multiplier = config.get("multiplier", 1)
            if isinstance(data, dict) and "value" in data:
                return {"value": data["value"] * multiplier}
            return data

        await transformer.register_operation("custom_multiply", custom_operation)

        template = TransformationTemplate(
            template_id="custom",
            name="Custom",
            steps=[
                TransformationStep(
                    step_id="multiply",
                    name="Multiply",
                    operation="custom_multiply",
                    config={"multiplier": 3},
                )
            ],
        )

        data = {"value": 10}
        result = await transformer.transform(template, data)

        assert result.state == TransformationState.COMPLETED
        assert result.metadata["output"]["value"] == 30

    async def test_template_management(self, transformer, simple_template):
        """Test template save and retrieval."""
        await transformer.save_template(simple_template)

        retrieved = await transformer.get_template("test-template")
        assert retrieved is not None
        assert retrieved.template_id == "test-template"
        assert retrieved.name == "Test Template"

    async def test_unknown_operation_error(self, transformer):
        """Test error handling for unknown operations."""
        template = TransformationTemplate(
            template_id="error",
            name="Error",
            steps=[
                TransformationStep(
                    step_id="unknown",
                    name="Unknown",
                    operation="nonexistent",
                    config={},
                )
            ],
        )

        result = await transformer.transform(template, {})
        assert result.state == TransformationState.FAILED
        assert "Unknown operation" in result.error

    async def test_step_timeout(self, transformer):
        """Test step timeout handling."""

        async def slow_operation(data, config):
            await asyncio.sleep(2)
            return data

        await transformer.register_operation("slow", slow_operation)

        template = TransformationTemplate(
            template_id="timeout",
            name="Timeout",
            steps=[
                TransformationStep(
                    step_id="slow",
                    name="Slow",
                    operation="slow",
                    config={},
                    timeout_seconds=0.1,  # Very short timeout
                )
            ],
        )

        result = await transformer.transform(template, {})
        assert result.state == TransformationState.FAILED
        assert "timed out" in result.error

    async def test_continue_on_error(self, transformer):
        """Test continue_on_error behavior."""

        async def error_operation(data, config):
            raise ValueError("Test error")

        await transformer.register_operation("error_op", error_operation)

        template = TransformationTemplate(
            template_id="error-continue",
            name="Error Continue",
            steps=[
                TransformationStep(
                    step_id="error",
                    name="Error",
                    operation="error_op",
                    config={},
                    continue_on_error=True,
                ),
                TransformationStep(
                    step_id="identity",
                    name="Identity",
                    operation="identity",
                    config={},
                ),
            ],
        )

        data = {"value": 123}
        result = await transformer.transform(template, data)

        # Should complete despite error in first step
        assert result.state == TransformationState.COMPLETED
        assert result.error_count == 1

    async def test_aggregate_count(self, transformer):
        """Test aggregate count operation."""
        data = [{"id": 1}, {"id": 2}, {"id": 3}]

        template = TransformationTemplate(
            template_id="agg-count",
            name="Count",
            steps=[
                TransformationStep(
                    step_id="count",
                    name="Count",
                    operation="aggregate",
                    config={"operation": "count"},
                )
            ],
        )

        result = await transformer.transform(template, data)
        assert result.state == TransformationState.COMPLETED
        assert result.metadata["output"]["count"] == 3

    async def test_aggregate_sum(self, transformer):
        """Test aggregate sum operation."""
        data = [{"value": 10}, {"value": 20}, {"value": 30}]

        template = TransformationTemplate(
            template_id="agg-sum",
            name="Sum",
            steps=[
                TransformationStep(
                    step_id="sum",
                    name="Sum",
                    operation="aggregate",
                    config={"operation": "sum", "field": "value"},
                )
            ],
        )

        result = await transformer.transform(template, data)
        assert result.state == TransformationState.COMPLETED
        assert result.metadata["output"]["sum"] == 60
