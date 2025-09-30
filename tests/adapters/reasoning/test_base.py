"""Tests for base reasoning adapter functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from acb.adapters.reasoning._base import (
    ReasoningBase,
    ReasoningBaseSettings,
    ReasoningContext,
    ReasoningProvider,
    ReasoningRequest,
    ReasoningResponse,
    ReasoningStep,
    ReasoningStrategy,
    ToolDefinition,
    DecisionRule,
    DecisionTree,
    MemoryType,
    calculate_confidence_score,
    merge_reasoning_contexts,
    validate_reasoning_request,
)


class TestReasoningBaseSettings:
    """Test reasoning base settings."""

    def test_default_settings(self):
        """Test default settings initialization."""
        settings = ReasoningBaseSettings()

        assert settings.provider == ReasoningProvider.LANGCHAIN
        assert settings.default_strategy == ReasoningStrategy.CHAIN_OF_THOUGHT
        assert settings.max_reasoning_steps == 10
        assert settings.temperature == 0.7
        assert settings.enable_reflection is True
        assert settings.enable_memory is True

    def test_custom_settings(self):
        """Test custom settings."""
        settings = ReasoningBaseSettings(
            provider=ReasoningProvider.LLAMAINDEX,
            max_reasoning_steps=20,
            temperature=0.5,
            enable_reflection=False,
        )

        assert settings.provider == ReasoningProvider.LLAMAINDEX
        assert settings.max_reasoning_steps == 20
        assert settings.temperature == 0.5
        assert settings.enable_reflection is False


class TestReasoningDataStructures:
    """Test reasoning data structures."""

    def test_reasoning_request(self):
        """Test reasoning request creation."""
        context = ReasoningContext(
            session_id="test-session",
            user_id="test-user",
        )

        request = ReasoningRequest(
            query="What is the meaning of life?",
            strategy=ReasoningStrategy.CHAIN_OF_THOUGHT,
            context=context,
            max_steps=5,
        )

        assert request.query == "What is the meaning of life?"
        assert request.strategy == ReasoningStrategy.CHAIN_OF_THOUGHT
        assert request.context.session_id == "test-session"
        assert request.max_steps == 5

    def test_reasoning_response(self):
        """Test reasoning response creation."""
        step = ReasoningStep(
            step_id="step_1",
            description="First reasoning step",
            input_data={"query": "test"},
            output_data={"result": "processed"},
            reasoning="Applied logical analysis",
            confidence=0.9,
        )

        response = ReasoningResponse(
            final_answer="The answer is 42",
            reasoning_chain=[step],
            strategy_used=ReasoningStrategy.CHAIN_OF_THOUGHT,
            provider=ReasoningProvider.CUSTOM,
            confidence_score=0.9,
        )

        assert response.final_answer == "The answer is 42"
        assert len(response.reasoning_chain) == 1
        assert response.reasoning_chain[0].step_id == "step_1"
        assert response.confidence_score == 0.9

    def test_tool_definition(self):
        """Test tool definition creation."""
        tool = ToolDefinition(
            name="calculator",
            description="Performs mathematical calculations",
            parameters={
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "Math expression"}
                }
            },
            required_parameters=["expression"],
        )

        assert tool.name == "calculator"
        assert tool.description == "Performs mathematical calculations"
        assert "expression" in tool.parameters["properties"]
        assert tool.required_parameters == ["expression"]

    def test_decision_rule(self):
        """Test decision rule creation."""
        rule = DecisionRule(
            name="temperature_check",
            condition="temperature > 30",
            action="turn_on_ac",
            priority=1,
            description="Turn on AC when temperature is high",
        )

        assert rule.name == "temperature_check"
        assert rule.condition == "temperature > 30"
        assert rule.action == "turn_on_ac"
        assert rule.priority == 1

    def test_decision_tree(self):
        """Test decision tree creation."""
        rule1 = DecisionRule(
            name="rule1",
            condition="x > 5",
            action="action1",
            priority=1,
        )
        rule2 = DecisionRule(
            name="rule2",
            condition="x <= 5",
            action="action2",
            priority=2,
        )

        tree = DecisionTree(
            name="number_check",
            rules=[rule1, rule2],
            default_action="default",
            description="Check number value",
        )

        assert tree.name == "number_check"
        assert len(tree.rules) == 2
        assert tree.default_action == "default"


class MockReasoningAdapter(ReasoningBase):
    """Mock reasoning adapter for testing."""

    async def _create_client(self):
        """Mock client creation."""
        return MagicMock()

    async def _reason(self, request: ReasoningRequest) -> ReasoningResponse:
        """Mock reasoning implementation."""
        return ReasoningResponse(
            final_answer="Mock answer",
            reasoning_chain=[],
            strategy_used=request.strategy,
            provider=ReasoningProvider.CUSTOM,
            confidence_score=0.8,
        )


class TestReasoningBase:
    """Test base reasoning adapter functionality."""

    @pytest.fixture
    def mock_adapter(self):
        """Create mock reasoning adapter."""
        settings = ReasoningBaseSettings()
        adapter = MockReasoningAdapter()
        adapter._settings = settings
        return adapter

    @pytest.mark.asyncio
    async def test_adapter_initialization(self, mock_adapter):
        """Test adapter initialization."""
        assert mock_adapter._settings is not None
        assert isinstance(mock_adapter._memory_store, dict)
        assert isinstance(mock_adapter._tool_registry, dict)
        assert isinstance(mock_adapter._decision_trees, dict)

    @pytest.mark.asyncio
    async def test_reason_method(self, mock_adapter):
        """Test reason method."""
        request = ReasoningRequest(
            query="Test query",
            strategy=ReasoningStrategy.CHAIN_OF_THOUGHT,
        )

        response = await mock_adapter.reason(request)

        assert response.final_answer == "Mock answer"
        assert response.strategy_used == ReasoningStrategy.CHAIN_OF_THOUGHT
        assert response.provider == ReasoningProvider.CUSTOM

    @pytest.mark.asyncio
    async def test_chain_of_thought(self, mock_adapter):
        """Test chain of thought reasoning."""
        response = await mock_adapter.chain_of_thought("What is 2+2?")

        assert response.final_answer == "Mock answer"
        assert response.strategy_used == ReasoningStrategy.CHAIN_OF_THOUGHT

    @pytest.mark.asyncio
    async def test_memory_operations(self, mock_adapter):
        """Test memory operations."""
        session_id = "test-session"
        memory_type = MemoryType.CONVERSATION
        data = {"key": "value"}

        # Set memory
        await mock_adapter.set_memory(session_id, memory_type, data)

        # Get memory
        retrieved_data = await mock_adapter.get_memory(session_id, memory_type)
        assert retrieved_data == data

        # Clear memory
        await mock_adapter.clear_memory(session_id, memory_type)
        retrieved_data = await mock_adapter.get_memory(session_id, memory_type)
        assert retrieved_data is None

    @pytest.mark.asyncio
    async def test_tool_registration(self, mock_adapter):
        """Test tool registration."""
        tool = ToolDefinition(
            name="test_tool",
            description="Test tool",
            parameters={"type": "object"},
        )

        await mock_adapter.register_tool(tool)

        assert "test_tool" in mock_adapter._tool_registry
        assert mock_adapter._tool_registry["test_tool"] == tool

    @pytest.mark.asyncio
    async def test_decision_tree_registration(self, mock_adapter):
        """Test decision tree registration."""
        rule = DecisionRule(
            name="test_rule",
            condition="x > 0",
            action="positive",
        )
        tree = DecisionTree(
            name="test_tree",
            rules=[rule],
            default_action="default",
        )

        await mock_adapter.register_decision_tree(tree)

        assert "test_tree" in mock_adapter._decision_trees
        assert mock_adapter._decision_trees["test_tree"] == tree

    @pytest.mark.asyncio
    async def test_health_check(self, mock_adapter):
        """Test health check."""
        # Mock the _ensure_client method
        mock_adapter._ensure_client = AsyncMock(return_value=MagicMock())

        health = await mock_adapter.health_check()

        assert health["status"] == "healthy"
        assert health["client_initialized"] is True
        assert "registered_tools" in health
        assert "decision_trees" in health


class TestUtilityFunctions:
    """Test utility functions."""

    @pytest.mark.asyncio
    async def test_validate_reasoning_request(self):
        """Test request validation."""
        # Valid request
        valid_request = ReasoningRequest(
            query="Valid query",
            strategy=ReasoningStrategy.CHAIN_OF_THOUGHT,
            max_steps=5,
            temperature=0.7,
        )

        # Should not raise
        await validate_reasoning_request(valid_request)

        # Invalid request - empty query
        invalid_request = ReasoningRequest(
            query="",
            strategy=ReasoningStrategy.CHAIN_OF_THOUGHT,
        )

        with pytest.raises(ValueError, match="Query cannot be empty"):
            await validate_reasoning_request(invalid_request)

        # Invalid request - negative max_steps
        invalid_request = ReasoningRequest(
            query="Valid query",
            strategy=ReasoningStrategy.CHAIN_OF_THOUGHT,
            max_steps=-1,
        )

        with pytest.raises(ValueError, match="max_steps must be positive"):
            await validate_reasoning_request(invalid_request)

    @pytest.mark.asyncio
    async def test_calculate_confidence_score(self):
        """Test confidence score calculation."""
        # Empty chain
        empty_chain = []
        confidence = await calculate_confidence_score(empty_chain)
        assert confidence == 0.0

        # Chain with confidences
        chain_with_confidence = [
            ReasoningStep(
                step_id="step1",
                description="Step 1",
                input_data={},
                confidence=0.8,
            ),
            ReasoningStep(
                step_id="step2",
                description="Step 2",
                input_data={},
                confidence=0.9,
            ),
        ]
        confidence = await calculate_confidence_score(chain_with_confidence)
        assert confidence == 0.85  # (0.8 + 0.9) / 2

        # Chain without confidences
        chain_without_confidence = [
            ReasoningStep(
                step_id="step1",
                description="Step 1",
                input_data={},
            ),
        ]
        confidence = await calculate_confidence_score(chain_without_confidence)
        assert confidence == 0.5  # Default

    @pytest.mark.asyncio
    async def test_merge_reasoning_contexts(self):
        """Test context merging."""
        context1 = ReasoningContext(
            session_id="session1",
            user_id="user1",
            conversation_history=[{"role": "user", "content": "hello"}],
            metadata={"key1": "value1"},
        )

        context2 = ReasoningContext(
            session_id="session1",
            knowledge_base="kb1",
            conversation_history=[{"role": "assistant", "content": "hi"}],
            metadata={"key2": "value2"},
        )

        merged = await merge_reasoning_contexts(context1, context2)

        assert merged.session_id == "session1"
        assert merged.user_id == "user1"
        assert merged.knowledge_base == "kb1"
        assert len(merged.conversation_history) == 2
        assert merged.metadata == {"key1": "value1", "key2": "value2"}


if __name__ == "__main__":
    pytest.main([__file__])
