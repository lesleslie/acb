"""Shared fixtures for reasoning adapter tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from acb.adapters.reasoning._base import (
    DecisionRule,
    DecisionTree,
    ReasoningContext,
    ReasoningStep,
    ToolDefinition,
)


@pytest.fixture
def mock_config():
    """Mock config with reasoning settings."""
    config = MagicMock()

    # Common reasoning settings
    config.reasoning = MagicMock()
    config.reasoning.max_reasoning_depth = 10
    config.reasoning.enable_parallel_reasoning = True
    config.reasoning.confidence_threshold = 0.6
    config.reasoning.enable_self_reflection = True
    config.reasoning.temperature = 0.7
    config.reasoning.max_tokens = 2000

    return config


@pytest.fixture
def sample_reasoning_context():
    """Create a sample reasoning context."""
    return ReasoningContext(
        session_id="test_session",
        user_id="test_user",
        previous_memories=["Previous conversation about AI"],
        tools=["calculator", "search"],
        knowledge_base="test_kb",
        data={"age": 25, "status": "active"},
        decision_tree_id="test_tree",
        max_depth=5,
    )


@pytest.fixture
def sample_reasoning_steps():
    """Create sample reasoning steps."""
    return [
        ReasoningStep(
            step_number=1,
            description="Analyze the problem",
            reasoning="First, I need to understand what the user is asking",
            result="Problem identified: mathematical calculation",
            confidence=0.9,
            tools_used=["analysis_tool"],
            metadata={"complexity": "low"},
        ),
        ReasoningStep(
            step_number=2,
            description="Perform calculation",
            reasoning="Using the calculator tool to compute the result",
            result="Calculation complete: 42",
            confidence=0.95,
            tools_used=["calculator"],
            metadata={"operation": "addition"},
        ),
        ReasoningStep(
            step_number=3,
            description="Validate result",
            reasoning="Checking if the result makes sense",
            result="Result validated",
            confidence=0.8,
            tools_used=["validator"],
            metadata={"validation_passed": True},
        ),
    ]


@pytest.fixture
def sample_tool_definition():
    """Create a sample tool definition."""
    return ToolDefinition(
        name="calculator",
        description="A mathematical calculator tool",
        parameters={
            "operation": {
                "type": "string",
                "description": "Mathematical operation to perform",
                "required": True,
                "enum": ["add", "subtract", "multiply", "divide"],
            },
            "a": {
                "type": "number",
                "description": "First operand",
                "required": True,
            },
            "b": {
                "type": "number",
                "description": "Second operand",
                "required": True,
            },
            "precision": {
                "type": "integer",
                "description": "Number of decimal places",
                "required": False,
                "default": 2,
            },
        },
        return_schema={
            "result": {
                "type": "number",
                "description": "The calculation result",
                "required": True,
            },
            "operation_performed": {
                "type": "string",
                "description": "Description of the operation",
                "required": True,
            },
        },
    )


@pytest.fixture
def sample_decision_tree():
    """Create a sample decision tree."""
    return DecisionTree(
        name="Loan Approval Decision Tree",
        description="Decision tree for loan approval process",
        rules=[
            DecisionRule(
                condition="credit_score >= 650 and income >= 50000",
                action="approve_premium_loan",
                priority=1,
                metadata={"rate": "3.5%", "max_amount": 500000},
            ),
            DecisionRule(
                condition="credit_score >= 650 and income < 50000",
                action="approve_standard_loan",
                priority=2,
                metadata={"rate": "4.5%", "max_amount": 200000},
            ),
            DecisionRule(
                condition="credit_score < 650 and income >= 75000",
                action="require_manual_review",
                priority=3,
                metadata={"reviewer": "senior_underwriter"},
            ),
        ],
        default_action="reject_loan",
    )


@pytest.fixture
def patch_file_operations():
    """Patch file operations to prevent actual file creation."""
    with (
        patch("pathlib.Path.exists") as mock_exists,
        patch("pathlib.Path.mkdir") as mock_mkdir,
        patch("pathlib.Path.write_text") as mock_write,
        patch("pathlib.Path.read_text") as mock_read,
    ):
        mock_exists.return_value = True
        mock_read.return_value = "{}"
        yield {
            "exists": mock_exists,
            "mkdir": mock_mkdir,
            "write_text": mock_write,
            "read_text": mock_read,
        }


@pytest.fixture
def mock_llm_response():
    """Mock LLM response for testing."""
    response = MagicMock()
    response.content = "This is a test response from the LLM."
    response.text = "This is a test response from the LLM."
    response.response = "This is a test response from the LLM."
    return response


@pytest.fixture
def mock_async_callback():
    """Mock async callback for testing."""
    callback = AsyncMock()
    callback.on_llm_start = AsyncMock()
    callback.on_llm_end = AsyncMock()
    callback.on_llm_error = AsyncMock()
    callback.on_chain_start = AsyncMock()
    callback.on_chain_end = AsyncMock()
    callback.on_chain_error = AsyncMock()
    callback.on_tool_start = AsyncMock()
    callback.on_tool_end = AsyncMock()
    callback.on_tool_error = AsyncMock()
    return callback


@pytest.fixture
def mock_vector_store():
    """Mock vector store for testing."""
    store = MagicMock()
    store.add_documents = AsyncMock()
    store.similarity_search = AsyncMock(return_value=[])
    store.similarity_search_with_score = AsyncMock(return_value=[])
    return store


@pytest.fixture
def mock_embeddings():
    """Mock embeddings for testing."""
    embeddings = MagicMock()
    embeddings.embed_documents = AsyncMock(return_value=[[0.1, 0.2, 0.3]])
    embeddings.embed_query = AsyncMock(return_value=[0.1, 0.2, 0.3])
    return embeddings


@pytest.fixture
def mock_document():
    """Mock document for testing."""
    doc = MagicMock()
    doc.page_content = "This is a test document."
    doc.metadata = {"source": "test.txt", "page": 1}
    return doc
