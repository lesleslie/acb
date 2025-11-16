"""Tests for LangChain reasoning adapter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from acb.adapters.reasoning._base import (
    ReasoningContext,
    ReasoningProvider,
    ReasoningRequest,
    ReasoningResponse,
    ReasoningStrategy,
    ToolDefinition,
)

# Mock LangChain imports
with patch.dict(
    "sys.modules",
    {
        "langchain.agents": MagicMock(),
        "langchain.agents.agent_types": MagicMock(),
        "langchain.callbacks": MagicMock(),
        "langchain.chains": MagicMock(),
        "langchain.chains.conversation.memory": MagicMock(),
        "langchain.llms.base": MagicMock(),
        "langchain.memory": MagicMock(),
        "langchain.prompts": MagicMock(),
        "langchain.schema": MagicMock(),
        "langchain.tools": MagicMock(),
        "langchain_community.llms": MagicMock(),
        "langchain_openai": MagicMock(),
    },
):
    from acb.adapters.reasoning.langchain import (
        LangChainCallback,
        LangChainReasoningSettings,
        Reasoning,
    )


class TestLangChainReasoningSettings:
    """Test LangChain reasoning settings."""

    def test_default_settings(self):
        """Test default settings."""
        settings = LangChainReasoningSettings()

        assert settings.agent_type == "react"
        assert settings.memory_type == "buffer"
        assert settings.max_memory_tokens == 2000
        assert settings.verbose is False

    def test_custom_settings(self):
        """Test custom settings."""
        settings = LangChainReasoningSettings(
            agent_type="zero-shot-react-description",
            memory_type="summary",
            verbose=True,
        )

        assert settings.agent_type == "zero-shot-react-description"
        assert settings.memory_type == "summary"
        assert settings.verbose is True


class TestLangChainCallback:
    """Test LangChain callback handler."""

    @pytest.fixture
    def mock_logger(self):
        """Mock logger."""
        return MagicMock()

    def test_callback_initialization(self, mock_logger):
        """Test callback initialization."""
        callback = LangChainCallback(mock_logger)

        assert callback.logger == mock_logger
        assert callback.steps == []
        assert callback.step_counter == 0

    @pytest.mark.asyncio
    async def test_chain_start_callback(self, mock_logger):
        """Test chain start callback."""
        callback = LangChainCallback(mock_logger)

        await callback.on_chain_start({"name": "TestChain"}, {"input": "test input"})

        assert callback.step_counter == 1
        assert callback.current_step is not None
        assert callback.current_step.step_id == "step_1"
        assert callback.current_step.description == "Chain started: TestChain"

    @pytest.mark.asyncio
    async def test_chain_end_callback(self, mock_logger):
        """Test chain end callback."""
        callback = LangChainCallback(mock_logger)

        # Start a chain first
        await callback.on_chain_start({"name": "TestChain"}, {"input": "test"})

        # End the chain
        await callback.on_chain_end({"output": "test output"})

        assert len(callback.steps) == 1
        assert callback.current_step is None
        assert callback.steps[0].output_data == {"output": "test output"}

    @pytest.mark.asyncio
    async def test_chain_error_callback(self, mock_logger):
        """Test chain error callback."""
        callback = LangChainCallback(mock_logger)

        # Start a chain first
        await callback.on_chain_start({"name": "TestChain"}, {"input": "test"})

        # Trigger error
        error = ValueError("Test error")
        await callback.on_chain_error(error)

        assert len(callback.steps) == 1
        assert callback.current_step is None
        assert callback.steps[0].error == "Test error"


class MockLangChainAdapter(Reasoning):
    """Mock LangChain adapter for testing."""

    def __init__(self, **kwargs):
        # Skip the LANGCHAIN_AVAILABLE check for testing
        super().__init__(**kwargs)

    async def _create_client(self):
        """Mock client creation."""
        mock_llm = MagicMock()
        mock_llm.arun = AsyncMock(return_value="Mock LLM response")
        return mock_llm


class TestLangChainReasoning:
    """Test LangChain reasoning adapter."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings."""
        return LangChainReasoningSettings(api_key="test-key")

    @pytest.fixture
    def mock_adapter(self, mock_settings):
        """Mock adapter."""
        adapter = MockLangChainAdapter(settings=mock_settings)
        return adapter

    @pytest.mark.asyncio
    async def test_adapter_initialization(self, mock_adapter):
        """Test adapter initialization."""
        assert mock_adapter._settings is not None
        assert isinstance(mock_adapter._agents, dict)
        assert isinstance(mock_adapter._chains, dict)
        assert isinstance(mock_adapter._memories, dict)

    @pytest.mark.asyncio
    async def test_client_creation(self, mock_adapter):
        """Test client creation."""
        with patch("acb.adapters.reasoning.langchain.ChatOpenAI") as mock_chat_openai:
            mock_llm = MagicMock()
            mock_chat_openai.return_value = mock_llm

            client = await mock_adapter._create_client()

            assert client == mock_llm
            mock_chat_openai.assert_called_once()

    @pytest.mark.asyncio
    async def test_chain_of_thought_reasoning(self, mock_adapter):
        """Test chain of thought reasoning."""
        with patch("acb.adapters.reasoning.langchain.LLMChain") as mock_chain:
            mock_chain_instance = MagicMock()
            mock_chain_instance.arun = AsyncMock(return_value="Test response")
            mock_chain.return_value = mock_chain_instance

            request = ReasoningRequest(
                query="What is 2+2?",
                strategy=ReasoningStrategy.CHAIN_OF_THOUGHT,
            )

            response = await mock_adapter._chain_of_thought_reasoning(
                request, MagicMock(), MagicMock()
            )

            assert response.final_answer == "Test response"
            assert response.strategy_used == ReasoningStrategy.CHAIN_OF_THOUGHT
            assert response.provider == ReasoningProvider.LANGCHAIN

    @pytest.mark.asyncio
    async def test_react_reasoning_with_tools(self, mock_adapter):
        """Test ReAct reasoning with tools."""
        with patch(
            "acb.adapters.reasoning.langchain.initialize_agent"
        ) as mock_init_agent:
            mock_agent = MagicMock()
            mock_agent.arun = AsyncMock(return_value="Tool-based response")
            mock_init_agent.return_value = mock_agent

            tools = [
                ToolDefinition(
                    name="calculator",
                    description="Performs calculations",
                    parameters={"type": "object"},
                )
            ]

            request = ReasoningRequest(
                query="Calculate 2+2",
                strategy=ReasoningStrategy.REACT,
                tools=tools,
            )

            response = await mock_adapter._react_reasoning(
                request, MagicMock(), MagicMock()
            )

            assert response.final_answer == "Tool-based response"
            assert response.strategy_used == ReasoningStrategy.REACT

    @pytest.mark.asyncio
    async def test_react_reasoning_without_tools(self, mock_adapter):
        """Test ReAct reasoning fallback without tools."""
        request = ReasoningRequest(
            query="Simple question",
            strategy=ReasoningStrategy.REACT,
            tools=None,
        )

        # Mock the chain of thought method
        mock_adapter._chain_of_thought_reasoning = AsyncMock(
            return_value=ReasoningResponse(
                final_answer="Fallback response",
                reasoning_chain=[],
                strategy_used=ReasoningStrategy.CHAIN_OF_THOUGHT,
                provider=ReasoningProvider.LANGCHAIN,
            )
        )

        response = await mock_adapter._react_reasoning(
            request, MagicMock(), MagicMock()
        )

        assert response.final_answer == "Fallback response"

    @pytest.mark.asyncio
    async def test_rag_workflow_reasoning(self, mock_adapter):
        """Test RAG workflow reasoning."""
        with patch("acb.adapters.reasoning.langchain.LLMChain") as mock_chain:
            mock_chain_instance = MagicMock()
            mock_chain_instance.arun = AsyncMock(return_value="RAG response")
            mock_chain.return_value = mock_chain_instance

            context = ReasoningContext(
                session_id="test-session",
                knowledge_base="test-kb",
                retrieved_contexts=[
                    {"content": "Context 1", "score": 0.9},
                    {"content": "Context 2", "score": 0.8},
                ],
            )

            request = ReasoningRequest(
                query="Question with context",
                strategy=ReasoningStrategy.RAG_WORKFLOW,
                context=context,
            )

            response = await mock_adapter._rag_workflow_reasoning(
                request, MagicMock(), MagicMock()
            )

            assert response.final_answer == "RAG response"
            assert response.strategy_used == ReasoningStrategy.RAG_WORKFLOW
            assert response.sources_cited is not None

    @pytest.mark.asyncio
    async def test_memory_operations(self, mock_adapter):
        """Test memory operations."""
        session_id = "test-session"

        # Update memory
        await mock_adapter._update_memory(session_id, "Hello", "Hi there")

        assert session_id in mock_adapter._memories

        # Get memory context
        context = await mock_adapter._get_memory_context(session_id)
        assert isinstance(context, str)

    @pytest.mark.asyncio
    async def test_tree_of_thoughts(self, mock_adapter):
        """Test tree of thoughts reasoning."""
        request = ReasoningRequest(
            query="Complex question",
            strategy=ReasoningStrategy.TREE_OF_THOUGHTS,
        )

        # Mock the _reason method to return different responses for each path
        mock_responses = [
            ReasoningResponse(
                final_answer=f"Path {i} response",
                reasoning_chain=[],
                strategy_used=ReasoningStrategy.CHAIN_OF_THOUGHT,
                provider=ReasoningProvider.LANGCHAIN,
                confidence_score=0.8 + i * 0.05,
            )
            for i in range(3)
        ]

        with patch.object(mock_adapter, "_reason", side_effect=mock_responses):
            with patch("acb.adapters.reasoning.langchain.LLMChain") as mock_chain:
                mock_chain_instance = MagicMock()
                mock_chain_instance.arun = AsyncMock(return_value="Synthesized answer")
                mock_chain.return_value = mock_chain_instance

                response = await mock_adapter._tree_of_thoughts(request, 3)

                assert response.strategy_used == ReasoningStrategy.TREE_OF_THOUGHTS
                assert response.final_answer == "Synthesized answer"
                assert response.confidence_score > 0.8

    @pytest.mark.asyncio
    async def test_error_handling(self, mock_adapter):
        """Test error handling in reasoning."""
        request = ReasoningRequest(
            query="Test query",
            strategy=ReasoningStrategy.CHAIN_OF_THOUGHT,
        )

        # Mock _ensure_client to raise an exception
        mock_adapter._ensure_client = AsyncMock(
            side_effect=Exception("Connection failed")
        )

        response = await mock_adapter._reason(request)

        assert response.error == "Connection failed"
        assert response.final_answer == ""

    @pytest.mark.asyncio
    async def test_full_reasoning_workflow(self, mock_adapter):
        """Test full reasoning workflow."""
        with patch.object(mock_adapter, "_chain_of_thought_reasoning") as mock_cot:
            mock_cot.return_value = ReasoningResponse(
                final_answer="Final answer",
                reasoning_chain=[],
                strategy_used=ReasoningStrategy.CHAIN_OF_THOUGHT,
                provider=ReasoningProvider.LANGCHAIN,
                confidence_score=0.9,
            )

            context = ReasoningContext(
                session_id="test-session",
                user_id="test-user",
            )

            request = ReasoningRequest(
                query="Test question",
                strategy=ReasoningStrategy.CHAIN_OF_THOUGHT,
                context=context,
                enable_memory=True,
            )

            response = await mock_adapter.reason(request)

            assert response.final_answer == "Final answer"
            assert response.confidence_score == 0.9
            assert response.total_duration_ms is not None


if __name__ == "__main__":
    pytest.main([__file__])
