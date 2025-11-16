"""Tests for LlamaIndex reasoning adapter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from acb.adapters.reasoning._base import (
    MemoryType,
    ReasoningContext,
    ReasoningRequest,
    ReasoningStrategy,
)
from acb.adapters.reasoning.llamaindex import Reasoning


class MockLlamaIndexSettings:
    """Mock settings for LlamaIndex adapter."""

    def __init__(self):
        self.model = "gpt-3.5-turbo"
        self.temperature = 0.7
        self.max_tokens = 2000
        self.vector_store_type = "simple"
        self.chunk_size = 1024
        self.chunk_overlap = 20
        self.similarity_top_k = 3
        self.response_mode = "compact"


@pytest.fixture
def mock_settings():
    """Mock adapter settings."""
    return MockLlamaIndexSettings()


@pytest.fixture
def mock_config(mock_settings):
    """Mock config with reasoning settings."""
    config = MagicMock()
    config.reasoning = mock_settings
    return config


@pytest.fixture
def mock_llm():
    """Mock LLM for testing."""
    llm = AsyncMock()
    llm.acomplete = AsyncMock()
    return llm


@pytest.fixture
def mock_vector_store():
    """Mock vector store for testing."""
    store = MagicMock()
    return store


@pytest.fixture
def mock_index():
    """Mock vector store index."""
    index = MagicMock()
    index.as_query_engine = MagicMock()
    index.as_chat_engine = MagicMock()
    return index


@pytest.fixture
def mock_storage_context():
    """Mock storage context."""
    context = MagicMock()
    return context


@pytest.fixture
def reasoning_adapter(mock_config):
    """Create reasoning adapter with mocked dependencies."""
    adapter = Reasoning()
    adapter._settings = mock_config.reasoning
    return adapter


class TestLlamaIndexSettings:
    """Test settings validation and initialization."""

    def test_settings_initialization(self, mock_settings):
        """Test settings are properly initialized."""
        assert mock_settings.model == "gpt-3.5-turbo"
        assert mock_settings.temperature == 0.7
        assert mock_settings.max_tokens == 2000
        assert mock_settings.vector_store_type == "simple"
        assert mock_settings.chunk_size == 1024
        assert mock_settings.chunk_overlap == 20
        assert mock_settings.similarity_top_k == 3
        assert mock_settings.response_mode == "compact"


class TestLlamaIndexClient:
    """Test LlamaIndex client initialization and management."""

    @patch("acb.adapters.reasoning.llamaindex.OpenAI")
    async def test_ensure_client_initialization(
        self, mock_openai_class, reasoning_adapter, mock_llm
    ):
        """Test client initialization."""
        mock_openai_class.return_value = mock_llm

        client = await reasoning_adapter._ensure_client()

        assert client is not None
        assert reasoning_adapter._client is not None
        mock_openai_class.assert_called_once_with(
            model=reasoning_adapter._settings.model,
            temperature=reasoning_adapter._settings.temperature,
            max_tokens=reasoning_adapter._settings.max_tokens,
        )

    @patch("acb.adapters.reasoning.llamaindex.OpenAI")
    async def test_ensure_client_reuses_existing(
        self, mock_openai_class, reasoning_adapter, mock_llm
    ):
        """Test client reuse."""
        mock_openai_class.return_value = mock_llm
        reasoning_adapter._client = mock_llm

        client = await reasoning_adapter._ensure_client()

        assert client is mock_llm
        mock_openai_class.assert_not_called()


class TestIndexManagement:
    """Test index creation and management."""

    @patch("acb.adapters.reasoning.llamaindex.VectorStoreIndex")
    @patch("acb.adapters.reasoning.llamaindex.SimpleVectorStore")
    @patch("acb.adapters.reasoning.llamaindex.StorageContext")
    async def test_get_or_create_index_new(
        self,
        mock_storage_context_class,
        mock_vector_store_class,
        mock_index_class,
        reasoning_adapter,
        mock_vector_store,
        mock_storage_context,
        mock_index,
    ):
        """Test creating new index."""
        mock_vector_store_class.return_value = mock_vector_store
        mock_storage_context_class.from_defaults.return_value = mock_storage_context
        mock_index_class.return_value = mock_index

        index = await reasoning_adapter._get_or_create_index("test_kb")

        assert index is mock_index
        assert "test_kb" in reasoning_adapter._indices
        mock_vector_store_class.assert_called_once()
        mock_storage_context_class.from_defaults.assert_called_once_with(
            vector_store=mock_vector_store
        )

    async def test_get_or_create_index_existing(self, reasoning_adapter, mock_index):
        """Test reusing existing index."""
        reasoning_adapter._indices["test_kb"] = mock_index

        index = await reasoning_adapter._get_or_create_index("test_kb")

        assert index is mock_index

    @patch("acb.adapters.reasoning.llamaindex.SimpleDirectoryReader")
    @patch("acb.adapters.reasoning.llamaindex.VectorStoreIndex")
    async def test_create_index_from_documents(
        self,
        mock_index_class,
        mock_reader_class,
        reasoning_adapter,
        mock_index,
    ):
        """Test creating index from documents."""
        mock_documents = [MagicMock(), MagicMock()]
        mock_reader = MagicMock()
        mock_reader.load_data.return_value = mock_documents
        mock_reader_class.return_value = mock_reader
        mock_index_class.from_documents.return_value = mock_index

        index = await reasoning_adapter.create_index_from_documents(
            "test_kb", "/path/to/docs"
        )

        assert index is mock_index
        assert "test_kb" in reasoning_adapter._indices
        mock_reader_class.assert_called_once_with("/path/to/docs")
        mock_reader.load_data.assert_called_once()
        mock_index_class.from_documents.assert_called_once_with(
            mock_documents, service_context=reasoning_adapter._service_context
        )


class TestQueryEngine:
    """Test query engine operations."""

    async def test_create_query_engine(self, reasoning_adapter, mock_index):
        """Test query engine creation."""
        reasoning_adapter._indices["test_kb"] = mock_index
        mock_query_engine = MagicMock()
        mock_index.as_query_engine.return_value = mock_query_engine

        engine = await reasoning_adapter.create_query_engine("test_kb")

        assert engine is mock_query_engine
        mock_index.as_query_engine.assert_called_once_with(
            similarity_top_k=reasoning_adapter._settings.similarity_top_k,
            response_mode=reasoning_adapter._settings.response_mode,
        )

    async def test_create_query_engine_nonexistent_kb(self, reasoning_adapter):
        """Test query engine creation with nonexistent knowledge base."""
        with pytest.raises(ValueError, match="Knowledge base 'nonexistent' not found"):
            await reasoning_adapter.create_query_engine("nonexistent")


class TestChatEngine:
    """Test chat engine operations."""

    async def test_create_chat_engine(self, reasoning_adapter, mock_index):
        """Test chat engine creation."""
        reasoning_adapter._indices["test_kb"] = mock_index
        mock_chat_engine = MagicMock()
        mock_index.as_chat_engine.return_value = mock_chat_engine

        engine = await reasoning_adapter.create_chat_engine("session_1", "test_kb")

        assert engine is mock_chat_engine
        assert "session_1" in reasoning_adapter._chat_sessions
        mock_index.as_chat_engine.assert_called_once_with(
            chat_mode="context", verbose=True
        )

    async def test_create_chat_engine_reuse(self, reasoning_adapter):
        """Test chat engine reuse."""
        mock_chat_engine = MagicMock()
        reasoning_adapter._chat_sessions["session_1"] = mock_chat_engine

        engine = await reasoning_adapter.create_chat_engine("session_1")

        assert engine is mock_chat_engine

    async def test_create_chat_engine_without_kb(self, reasoning_adapter):
        """Test chat engine creation without knowledge base."""
        mock_chat_engine = MagicMock()
        reasoning_adapter._chat_sessions["session_1"] = mock_chat_engine

        engine = await reasoning_adapter.create_chat_engine("session_1")

        assert engine is mock_chat_engine


class TestReasoningOperations:
    """Test core reasoning operations."""

    async def test_rag_workflow_reasoning(self, reasoning_adapter, mock_index):
        """Test RAG workflow reasoning."""
        reasoning_adapter._indices["test_kb"] = mock_index
        mock_query_engine = MagicMock()
        mock_response = MagicMock()
        mock_response.response = "Test response"
        mock_response.source_nodes = []
        mock_index.as_query_engine.return_value = mock_query_engine
        mock_query_engine.query = AsyncMock(return_value=mock_response)

        request = ReasoningRequest(
            query="Test query",
            strategy=ReasoningStrategy.RAG_WORKFLOW,
            context=ReasoningContext(knowledge_base="test_kb"),
        )

        response = await reasoning_adapter.reason(request)

        assert response.result == "Test response"
        assert response.strategy == ReasoningStrategy.RAG_WORKFLOW
        mock_query_engine.query.assert_called_once_with("Test query")

    async def test_chain_of_thought_reasoning(self, reasoning_adapter, mock_llm):
        """Test chain of thought reasoning."""
        reasoning_adapter._client = mock_llm
        mock_response = MagicMock()
        mock_response.text = "Step 1: Analysis\nStep 2: Conclusion"
        mock_llm.acomplete.return_value = mock_response

        request = ReasoningRequest(
            query="Solve this problem",
            strategy=ReasoningStrategy.CHAIN_OF_THOUGHT,
        )

        response = await reasoning_adapter.reason(request)

        assert "Step 1: Analysis" in response.result
        assert len(response.steps) == 2
        mock_llm.acomplete.assert_called_once()

    async def test_rag_workflow_helper(self, reasoning_adapter, mock_index):
        """Test RAG workflow helper method."""
        reasoning_adapter._indices["test_kb"] = mock_index
        mock_query_engine = MagicMock()
        mock_response = MagicMock()
        mock_response.response = "RAG response"
        mock_response.source_nodes = []
        mock_index.as_query_engine.return_value = mock_query_engine
        mock_query_engine.query = AsyncMock(return_value=mock_response)

        response = await reasoning_adapter.rag_workflow("Test query", "test_kb")

        assert response.result == "RAG response"
        assert response.strategy == ReasoningStrategy.RAG_WORKFLOW


class TestMemoryOperations:
    """Test memory management operations."""

    async def test_store_memory_conversation(self, reasoning_adapter):
        """Test storing conversation memory."""
        await reasoning_adapter.store_memory(
            "session_1", "Test memory", MemoryType.CONVERSATION
        )

        memories = reasoning_adapter._memory.get("session_1", {})
        assert MemoryType.CONVERSATION in memories
        assert "Test memory" in memories[MemoryType.CONVERSATION]

    async def test_retrieve_memory(self, reasoning_adapter):
        """Test retrieving memory."""
        reasoning_adapter._memory["session_1"] = {
            MemoryType.CONVERSATION: ["Memory 1", "Memory 2"]
        }

        memories = await reasoning_adapter.retrieve_memory("session_1")

        assert len(memories) == 2
        assert "Memory 1" in memories
        assert "Memory 2" in memories

    async def test_clear_memory(self, reasoning_adapter):
        """Test clearing memory."""
        reasoning_adapter._memory["session_1"] = {MemoryType.CONVERSATION: ["Memory 1"]}

        await reasoning_adapter.clear_memory("session_1")

        assert "session_1" not in reasoning_adapter._memory

    async def test_clear_memory_by_type(self, reasoning_adapter):
        """Test clearing memory by type."""
        reasoning_adapter._memory["session_1"] = {
            MemoryType.CONVERSATION: ["Conv memory"],
            MemoryType.EPISODIC: ["Episode memory"],
        }

        await reasoning_adapter.clear_memory("session_1", MemoryType.CONVERSATION)

        memories = reasoning_adapter._memory["session_1"]
        assert MemoryType.CONVERSATION not in memories
        assert MemoryType.EPISODIC in memories


class TestErrorHandling:
    """Test error handling scenarios."""

    async def test_rag_workflow_missing_knowledge_base(self, reasoning_adapter):
        """Test RAG workflow with missing knowledge base."""
        request = ReasoningRequest(
            query="Test query",
            strategy=ReasoningStrategy.RAG_WORKFLOW,
            context=ReasoningContext(knowledge_base="nonexistent"),
        )

        with pytest.raises(ValueError, match="Knowledge base 'nonexistent' not found"):
            await reasoning_adapter.reason(request)

    async def test_rag_workflow_missing_context(self, reasoning_adapter):
        """Test RAG workflow without context."""
        request = ReasoningRequest(
            query="Test query",
            strategy=ReasoningStrategy.RAG_WORKFLOW,
        )

        with pytest.raises(ValueError, match="Knowledge base must be specified"):
            await reasoning_adapter.reason(request)

    @patch("acb.adapters.reasoning.llamaindex.OpenAI")
    async def test_client_initialization_error(
        self, mock_openai_class, reasoning_adapter
    ):
        """Test client initialization error handling."""
        mock_openai_class.side_effect = Exception("API error")

        with pytest.raises(Exception, match="API error"):
            await reasoning_adapter._ensure_client()

    async def test_unsupported_strategy(self, reasoning_adapter):
        """Test unsupported reasoning strategy."""
        request = ReasoningRequest(
            query="Test query",
            strategy="unsupported_strategy",  # type: ignore
        )

        with pytest.raises(ValueError, match="Unsupported reasoning strategy"):
            await reasoning_adapter.reason(request)


class TestIntegration:
    """Test integration scenarios."""

    @patch("acb.adapters.reasoning.llamaindex.OpenAI")
    @patch("acb.adapters.reasoning.llamaindex.VectorStoreIndex")
    async def test_full_rag_workflow(
        self,
        mock_index_class,
        mock_openai_class,
        reasoning_adapter,
        mock_llm,
        mock_index,
    ):
        """Test complete RAG workflow."""
        mock_openai_class.return_value = mock_llm
        mock_index_class.return_value = mock_index

        # Setup mock responses
        mock_query_engine = MagicMock()
        mock_response = MagicMock()
        mock_response.response = "RAG workflow result"
        mock_response.source_nodes = []
        mock_index.as_query_engine.return_value = mock_query_engine
        mock_query_engine.query = AsyncMock(return_value=mock_response)

        # Create index
        await reasoning_adapter._get_or_create_index("test_kb")

        # Execute RAG workflow
        request = ReasoningRequest(
            query="Complex question",
            strategy=ReasoningStrategy.RAG_WORKFLOW,
            context=ReasoningContext(
                knowledge_base="test_kb",
                session_id="session_1",
            ),
        )

        response = await reasoning_adapter.reason(request)

        assert response.result == "RAG workflow result"
        assert response.strategy == ReasoningStrategy.RAG_WORKFLOW
        assert response.context.session_id == "session_1"

    async def test_memory_persistence_across_sessions(self, reasoning_adapter):
        """Test memory persistence across reasoning sessions."""
        # Store memory in first session
        await reasoning_adapter.store_memory(
            "session_1", "Important fact", MemoryType.CONVERSATION
        )

        # Retrieve in second session
        memories = await reasoning_adapter.retrieve_memory("session_1")

        assert "Important fact" in memories

        # Store additional memory
        await reasoning_adapter.store_memory(
            "session_1", "Another fact", MemoryType.EPISODIC
        )

        # Retrieve all memories
        all_memories = await reasoning_adapter.retrieve_memory("session_1")

        assert len(all_memories) == 2
        assert "Important fact" in all_memories
        assert "Another fact" in all_memories


class TestCleanup:
    """Test resource cleanup."""

    async def test_cleanup_resources(self, reasoning_adapter):
        """Test cleanup of adapter resources."""
        # Setup some resources
        reasoning_adapter._client = MagicMock()
        reasoning_adapter._indices["kb1"] = MagicMock()
        reasoning_adapter._chat_sessions["session1"] = MagicMock()

        # Perform cleanup
        await reasoning_adapter.cleanup()

        # Verify resources are cleared
        assert reasoning_adapter._client is None
        assert len(reasoning_adapter._indices) == 0
        assert len(reasoning_adapter._chat_sessions) == 0
        assert len(reasoning_adapter._memory) == 0
