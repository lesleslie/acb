"""Tests for OpenAI Functions reasoning adapter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from acb.adapters.reasoning._base import (
    MemoryType,
    ReasoningContext,
    ReasoningRequest,
    ReasoningStrategy,
    ToolDefinition,
)
from acb.adapters.reasoning.openai_functions import Reasoning


class MockOpenAISettings:
    """Mock settings for OpenAI Functions adapter."""

    def __init__(self):
        self.api_key = "test-api-key"  # pragma: allowlist secret
        self.model = "gpt-4"
        self.temperature = 0.1
        self.max_tokens = 2000
        self.max_function_calls = 10
        self.parallel_tool_calls = True
        self.timeout = 30


@pytest.fixture
def mock_settings():
    """Mock adapter settings."""
    return MockOpenAISettings()


@pytest.fixture
def mock_config(mock_settings):
    """Mock config with reasoning settings."""
    config = MagicMock()
    config.reasoning = mock_settings
    return config


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    client = AsyncMock()
    client.chat = AsyncMock()
    client.chat.completions = AsyncMock()
    client.chat.completions.create = AsyncMock()
    return client


@pytest.fixture
def reasoning_adapter(mock_config):
    """Create reasoning adapter with mocked dependencies."""
    adapter = Reasoning()
    adapter._settings = mock_config.reasoning
    return adapter


@pytest.fixture
def sample_tool_definition():
    """Create a sample tool definition."""
    return ToolDefinition(
        name="calculate_sum",
        description="Calculate the sum of two numbers",
        parameters={
            "a": ToolParameter(
                type="number",
                description="First number",
                required=True,
            ),
            "b": ToolParameter(
                type="number",
                description="Second number",
                required=True,
            ),
        },
    )


@pytest.fixture
def sample_function_schema():
    """Create a sample function schema for OpenAI."""
    return {
        "type": "function",
        "function": {
            "name": "calculate_sum",
            "description": "Calculate the sum of two numbers",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "First number"},
                    "b": {"type": "number", "description": "Second number"},
                },
                "required": ["a", "b"],
            },
        },
    }


class TestOpenAISettings:
    """Test settings validation and initialization."""

    def test_settings_initialization(self, mock_settings):
        """Test settings are properly initialized."""
        assert mock_settings.api_key == "test-api-key"
        assert mock_settings.model == "gpt-4"
        assert mock_settings.temperature == 0.1
        assert mock_settings.max_tokens == 2000
        assert mock_settings.max_function_calls == 10
        assert mock_settings.parallel_tool_calls is True
        assert mock_settings.timeout == 30


class TestOpenAIClient:
    """Test OpenAI client initialization and management."""

    @patch("acb.adapters.reasoning.openai_functions.AsyncOpenAI")
    async def test_ensure_client_initialization(
        self, mock_openai_class, reasoning_adapter, mock_openai_client
    ):
        """Test client initialization."""
        mock_openai_class.return_value = mock_openai_client

        client = await reasoning_adapter._ensure_client()

        assert client is not None
        assert reasoning_adapter._client is not None
        mock_openai_class.assert_called_once_with(
            api_key=reasoning_adapter._settings.api_key,
            timeout=reasoning_adapter._settings.timeout,
        )

    @patch("acb.adapters.reasoning.openai_functions.AsyncOpenAI")
    async def test_ensure_client_reuses_existing(
        self, mock_openai_class, reasoning_adapter, mock_openai_client
    ):
        """Test client reuse."""
        reasoning_adapter._client = mock_openai_client

        client = await reasoning_adapter._ensure_client()

        assert client is mock_openai_client
        mock_openai_class.assert_not_called()


class TestToolManagement:
    """Test tool registration and management."""

    async def test_register_tool(self, reasoning_adapter, sample_tool_definition):
        """Test tool registration."""
        reasoning_adapter.register_tool(sample_tool_definition)

        assert "calculate_sum" in reasoning_adapter._tools
        assert reasoning_adapter._tools["calculate_sum"] == sample_tool_definition

    async def test_register_tool_with_function(self, reasoning_adapter):
        """Test tool registration with actual function."""

        def add_numbers(a: float, b: float) -> float:
            return a + b

        tool_def = ToolDefinition(
            name="add_numbers",
            description="Add two numbers",
            parameters={
                "a": ToolParameter(
                    type="number", description="First number", required=True
                ),
                "b": ToolParameter(
                    type="number", description="Second number", required=True
                ),
            },
        )

        reasoning_adapter.register_tool(tool_def)
        reasoning_adapter.register_function("add_numbers", add_numbers)

        assert "add_numbers" in reasoning_adapter._tools
        assert "add_numbers" in reasoning_adapter._functions

    async def test_convert_tool_to_openai_schema(
        self, reasoning_adapter, sample_tool_definition
    ):
        """Test converting tool definition to OpenAI schema."""
        reasoning_adapter.register_tool(sample_tool_definition)

        schema = reasoning_adapter._convert_tool_to_openai_schema(
            sample_tool_definition
        )

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "calculate_sum"
        assert schema["function"]["description"] == "Calculate the sum of two numbers"
        assert "parameters" in schema["function"]
        assert "properties" in schema["function"]["parameters"]
        assert "a" in schema["function"]["parameters"]["properties"]
        assert "b" in schema["function"]["parameters"]["properties"]
        assert schema["function"]["parameters"]["required"] == ["a", "b"]

    async def test_execute_function_call(self, reasoning_adapter):
        """Test executing a function call."""

        def multiply(a: float, b: float) -> float:
            return a * b

        reasoning_adapter.register_function("multiply", multiply)

        result = await reasoning_adapter._execute_function_call(
            "multiply", {"a": 5, "b": 3}
        )

        assert result == 15

    async def test_execute_nonexistent_function(self, reasoning_adapter):
        """Test executing a nonexistent function."""
        with pytest.raises(ValueError, match="Function 'nonexistent' not found"):
            await reasoning_adapter._execute_function_call("nonexistent", {})


class TestReasoningOperations:
    """Test core reasoning operations."""

    @patch("acb.adapters.reasoning.openai_functions.AsyncOpenAI")
    async def test_function_calling_reasoning(
        self,
        mock_openai_class,
        reasoning_adapter,
        mock_openai_client,
        sample_tool_definition,
    ):
        """Test function calling reasoning strategy."""
        mock_openai_class.return_value = mock_openai_client

        # Setup mock response with function call
        mock_choice = MagicMock()
        mock_choice.message.content = "I'll calculate the sum for you."
        mock_choice.message.tool_calls = [
            MagicMock(
                id="call_123",
                function=MagicMock(name="calculate_sum", arguments='{"a": 5, "b": 3}'),
            )
        ]
        mock_choice.finish_reason = "tool_calls"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_openai_client.chat.completions.create.return_value = mock_response

        # Register tool and function
        reasoning_adapter.register_tool(sample_tool_definition)
        reasoning_adapter.register_function("calculate_sum", lambda a, b: a + b)

        request = ReasoningRequest(
            query="What is 5 plus 3?",
            strategy=ReasoningStrategy.FUNCTION_CALLING,
            context=ReasoningContext(tools=["calculate_sum"]),
        )

        response = await reasoning_adapter.reason(request)

        assert response.strategy == ReasoningStrategy.FUNCTION_CALLING
        assert len(response.steps) >= 1
        # Function call should be tracked
        assert any("calculate_sum" in step.description for step in response.steps)

    @patch("acb.adapters.reasoning.openai_functions.AsyncOpenAI")
    async def test_structured_reasoning(
        self, mock_openai_class, reasoning_adapter, mock_openai_client
    ):
        """Test structured reasoning with schema."""
        mock_openai_class.return_value = mock_openai_client

        # Setup mock response
        mock_choice = MagicMock()
        mock_choice.message.content = '{"answer": "42", "confidence": 0.95}'
        mock_choice.finish_reason = "stop"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_openai_client.chat.completions.create.return_value = mock_response

        output_schema = {
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
                "confidence": {"type": "number"},
            },
            "required": ["answer", "confidence"],
        }

        response = await reasoning_adapter.structured_reasoning(
            "What is the meaning of life?", output_schema
        )

        assert response.result == '{"answer": "42", "confidence": 0.95}'
        assert response.strategy == ReasoningStrategy.STRUCTURED_OUTPUT

    @patch("acb.adapters.reasoning.openai_functions.AsyncOpenAI")
    async def test_chain_of_thought_reasoning(
        self, mock_openai_class, reasoning_adapter, mock_openai_client
    ):
        """Test chain of thought reasoning."""
        mock_openai_class.return_value = mock_openai_client

        # Setup mock response
        mock_choice = MagicMock()
        mock_choice.message.content = (
            "Let me think step by step:\n"
            "Step 1: Identify the problem\n"
            "Step 2: Analyze the data\n"
            "Step 3: Draw conclusions"
        )
        mock_choice.finish_reason = "stop"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_openai_client.chat.completions.create.return_value = mock_response

        request = ReasoningRequest(
            query="Solve this complex problem",
            strategy=ReasoningStrategy.CHAIN_OF_THOUGHT,
        )

        response = await reasoning_adapter.reason(request)

        assert response.strategy == ReasoningStrategy.CHAIN_OF_THOUGHT
        assert len(response.steps) == 3  # Should parse the steps
        assert "Identify the problem" in response.steps[0].description


class TestFunctionCalls:
    """Test function call tracking and execution."""

    async def test_track_function_call(self, reasoning_adapter):
        """Test tracking a function call."""
        call_info = {
            "id": "call_123",
            "name": "test_function",
            "arguments": {"param": "value"},
            "result": "success",
        }

        reasoning_adapter._track_function_call(call_info)

        assert len(reasoning_adapter._function_calls) == 1
        assert reasoning_adapter._function_calls[0] == call_info

    async def test_multiple_function_calls_tracking(self, reasoning_adapter):
        """Test tracking multiple function calls."""
        calls = [
            {"id": "call_1", "name": "func1", "arguments": {}, "result": "result1"},
            {"id": "call_2", "name": "func2", "arguments": {}, "result": "result2"},
        ]

        for call in calls:
            reasoning_adapter._track_function_call(call)

        assert len(reasoning_adapter._function_calls) == 2
        assert reasoning_adapter._function_calls[0]["name"] == "func1"
        assert reasoning_adapter._function_calls[1]["name"] == "func2"

    async def test_get_function_call_history(self, reasoning_adapter):
        """Test retrieving function call history."""
        call_info = {
            "id": "call_123",
            "name": "test_function",
            "arguments": {"param": "value"},
            "result": "success",
        }

        reasoning_adapter._track_function_call(call_info)

        history = reasoning_adapter.get_function_call_history()

        assert len(history) == 1
        assert history[0] == call_info

    async def test_clear_function_call_history(self, reasoning_adapter):
        """Test clearing function call history."""
        reasoning_adapter._track_function_call(
            {
                "id": "call_123",
                "name": "test_function",
                "arguments": {},
                "result": "result",
            }
        )

        reasoning_adapter.clear_function_call_history()

        assert len(reasoning_adapter._function_calls) == 0


class TestMemoryOperations:
    """Test memory management operations."""

    async def test_store_memory_conversation(self, reasoning_adapter):
        """Test storing conversation memory."""
        await reasoning_adapter.store_memory(
            "session_1", "User asked about math", MemoryType.CONVERSATION
        )

        memories = reasoning_adapter._memory.get("session_1", {})
        assert MemoryType.CONVERSATION in memories
        assert "User asked about math" in memories[MemoryType.CONVERSATION]

    async def test_store_memory_semantic(self, reasoning_adapter):
        """Test storing semantic memory."""
        await reasoning_adapter.store_memory(
            "global", "Calculator function adds two numbers", MemoryType.SEMANTIC
        )

        memories = reasoning_adapter._memory.get("global", {})
        assert MemoryType.SEMANTIC in memories
        assert "Calculator function adds two numbers" in memories[MemoryType.SEMANTIC]

    async def test_retrieve_memory(self, reasoning_adapter):
        """Test retrieving memory."""
        reasoning_adapter._memory["session_1"] = {
            MemoryType.CONVERSATION: ["Conv 1", "Conv 2"],
            MemoryType.SEMANTIC: ["Fact 1"],
        }

        memories = await reasoning_adapter.retrieve_memory("session_1")

        assert len(memories) == 3
        assert "Conv 1" in memories
        assert "Conv 2" in memories
        assert "Fact 1" in memories

    async def test_clear_memory(self, reasoning_adapter):
        """Test clearing memory."""
        reasoning_adapter._memory["session_1"] = {MemoryType.CONVERSATION: ["Memory 1"]}

        await reasoning_adapter.clear_memory("session_1")

        assert "session_1" not in reasoning_adapter._memory


class TestErrorHandling:
    """Test error handling scenarios."""

    async def test_unsupported_strategy(self, reasoning_adapter):
        """Test unsupported reasoning strategy."""
        request = ReasoningRequest(
            query="Test query",
            strategy="unsupported",  # type: ignore
        )

        with pytest.raises(ValueError, match="Unsupported reasoning strategy"):
            await reasoning_adapter.reason(request)

    @patch("acb.adapters.reasoning.openai_functions.AsyncOpenAI")
    async def test_api_error_handling(
        self, mock_openai_class, reasoning_adapter, mock_openai_client
    ):
        """Test API error handling."""
        mock_openai_class.return_value = mock_openai_client
        mock_openai_client.chat.completions.create.side_effect = Exception("API Error")

        request = ReasoningRequest(
            query="Test query",
            strategy=ReasoningStrategy.CHAIN_OF_THOUGHT,
        )

        with pytest.raises(Exception, match="API Error"):
            await reasoning_adapter.reason(request)

    async def test_function_execution_error(self, reasoning_adapter):
        """Test function execution error handling."""

        def failing_function():
            raise ValueError("Function failed")

        reasoning_adapter.register_function("failing_func", failing_function)

        with pytest.raises(ValueError, match="Function failed"):
            await reasoning_adapter._execute_function_call("failing_func", {})

    async def test_invalid_json_in_function_arguments(self, reasoning_adapter):
        """Test handling invalid JSON in function arguments."""
        reasoning_adapter.register_function("test_func", lambda x: x)

        with pytest.raises(Exception):  # JSON decode error
            await reasoning_adapter._execute_function_call("test_func", "invalid json")

    @patch("acb.adapters.reasoning.openai_functions.AsyncOpenAI")
    async def test_client_initialization_error(
        self, mock_openai_class, reasoning_adapter
    ):
        """Test client initialization error."""
        mock_openai_class.side_effect = Exception("Client init failed")

        with pytest.raises(Exception, match="Client init failed"):
            await reasoning_adapter._ensure_client()


class TestComplexScenarios:
    """Test complex reasoning scenarios."""

    @patch("acb.adapters.reasoning.openai_functions.AsyncOpenAI")
    async def test_multi_step_function_calling(
        self, mock_openai_class, reasoning_adapter, mock_openai_client
    ):
        """Test multi-step function calling scenario."""
        mock_openai_class.return_value = mock_openai_client

        # Setup multiple API calls for multi-step reasoning
        responses = []

        # First call - initial reasoning with function call
        choice1 = MagicMock()
        choice1.message.content = "I need to calculate something first."
        choice1.message.tool_calls = [
            MagicMock(
                id="call_1",
                function=MagicMock(name="calculate", arguments='{"value": 10}'),
            )
        ]
        choice1.finish_reason = "tool_calls"
        response1 = MagicMock()
        response1.choices = [choice1]
        responses.append(response1)

        # Second call - final reasoning
        choice2 = MagicMock()
        choice2.message.content = "Based on the calculation result, the answer is 20."
        choice2.finish_reason = "stop"
        response2 = MagicMock()
        response2.choices = [choice2]
        responses.append(response2)

        mock_openai_client.chat.completions.create.side_effect = responses

        # Register function
        reasoning_adapter.register_function("calculate", lambda value: value * 2)

        # Register tool
        tool_def = ToolDefinition(
            name="calculate",
            description="Perform calculation",
            parameters={
                "value": ToolParameter(
                    type="number",
                    description="Input value",
                    required=True,
                ),
            },
        )
        reasoning_adapter.register_tool(tool_def)

        request = ReasoningRequest(
            query="Double the number 10",
            strategy=ReasoningStrategy.FUNCTION_CALLING,
            context=ReasoningContext(tools=["calculate"]),
        )

        response = await reasoning_adapter.reason(request)

        assert response.strategy == ReasoningStrategy.FUNCTION_CALLING
        assert len(reasoning_adapter._function_calls) == 1
        assert reasoning_adapter._function_calls[0]["result"] == 20

    async def test_reasoning_with_memory_context(self, reasoning_adapter):
        """Test reasoning with memory context."""
        # Store some relevant memories
        await reasoning_adapter.store_memory(
            "user_123", "User prefers detailed explanations", MemoryType.CONVERSATION
        )
        await reasoning_adapter.store_memory(
            "user_123", "User is interested in mathematics", MemoryType.SEMANTIC
        )

        # Retrieve memories for context
        memories = await reasoning_adapter.retrieve_memory("user_123")

        request = ReasoningRequest(
            query="Explain calculus",
            strategy=ReasoningStrategy.CHAIN_OF_THOUGHT,
            context=ReasoningContext(
                session_id="user_123",
                previous_memories=memories,
            ),
        )

        # The memories would be used to inform the reasoning
        assert len(request.context.previous_memories) == 2


class TestIntegration:
    """Test integration scenarios."""

    @patch("acb.adapters.reasoning.openai_functions.AsyncOpenAI")
    async def test_full_reasoning_workflow(
        self, mock_openai_class, reasoning_adapter, mock_openai_client
    ):
        """Test complete reasoning workflow with tools and memory."""
        mock_openai_class.return_value = mock_openai_client

        # Setup mock response
        mock_choice = MagicMock()
        mock_choice.message.content = (
            "Let me analyze this step by step and use the calculator."
        )
        mock_choice.message.tool_calls = [
            MagicMock(
                id="call_1",
                function=MagicMock(
                    name="calculator",
                    arguments='{"operation": "add", "a": 15, "b": 25}',
                ),
            )
        ]
        mock_choice.finish_reason = "tool_calls"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_openai_client.chat.completions.create.return_value = mock_response

        # Register calculator function and tool
        def calculator(operation: str, a: float, b: float) -> float:
            if operation == "add":
                return a + b
            elif operation == "multiply":
                return a * b
            else:
                raise ValueError(f"Unsupported operation: {operation}")

        reasoning_adapter.register_function("calculator", calculator)

        tool_def = ToolDefinition(
            name="calculator",
            description="Perform mathematical calculations",
            parameters={
                "operation": ToolParameter(
                    type="string",
                    description="Mathematical operation",
                    required=True,
                ),
                "a": ToolParameter(
                    type="number",
                    description="First number",
                    required=True,
                ),
                "b": ToolParameter(
                    type="number",
                    description="Second number",
                    required=True,
                ),
            },
        )
        reasoning_adapter.register_tool(tool_def)

        # Store relevant memory
        await reasoning_adapter.store_memory(
            "calc_session",
            "User requested calculation assistance",
            MemoryType.CONVERSATION,
        )

        # Execute reasoning
        request = ReasoningRequest(
            query="What is 15 plus 25?",
            strategy=ReasoningStrategy.FUNCTION_CALLING,
            context=ReasoningContext(
                session_id="calc_session",
                tools=["calculator"],
            ),
        )

        response = await reasoning_adapter.reason(request)

        # Verify results
        assert response.strategy == ReasoningStrategy.FUNCTION_CALLING
        assert len(reasoning_adapter._function_calls) == 1
        assert reasoning_adapter._function_calls[0]["result"] == 40

        # Store the result in memory
        await reasoning_adapter.store_memory(
            "calc_session", "Calculated 15 + 25 = 40", MemoryType.EPISODIC
        )

        memories = await reasoning_adapter.retrieve_memory("calc_session")
        assert len(memories) == 2


class TestCleanup:
    """Test resource cleanup."""

    async def test_cleanup_resources(self, reasoning_adapter, sample_tool_definition):
        """Test cleanup of adapter resources."""
        # Setup resources
        reasoning_adapter.register_tool(sample_tool_definition)
        reasoning_adapter.register_function("test_func", lambda x: x)
        reasoning_adapter._memory["session1"] = {MemoryType.CONVERSATION: ["test"]}
        reasoning_adapter._track_function_call(
            {
                "id": "call_1",
                "name": "test",
                "arguments": {},
                "result": "test",
            }
        )

        # Perform cleanup
        await reasoning_adapter.cleanup()

        # Verify resources are cleared
        assert reasoning_adapter._client is None
        assert len(reasoning_adapter._tools) == 0
        assert len(reasoning_adapter._functions) == 0
        assert len(reasoning_adapter._memory) == 0
        assert len(reasoning_adapter._function_calls) == 0
