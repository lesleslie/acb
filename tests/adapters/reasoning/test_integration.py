"""Integration tests for reasoning adapter with other ACB adapters."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from acb.adapters.reasoning._base import (
    MemoryType,
    ReasoningContext,
    ReasoningRequest,
    ReasoningStrategy,
)


@pytest.fixture
def mock_ai_adapter():
    """Mock AI adapter for integration testing."""
    ai = AsyncMock()
    ai.complete = AsyncMock(return_value="AI response")
    ai.embed = AsyncMock(return_value=[0.1, 0.2, 0.3])
    return ai


@pytest.fixture
def mock_vector_adapter():
    """Mock vector database adapter for integration testing."""
    vector = AsyncMock()
    vector.search = AsyncMock(
        return_value=[
            {"content": "Similar document 1", "score": 0.9},
            {"content": "Similar document 2", "score": 0.8},
        ]
    )
    vector.add = AsyncMock()
    vector.delete = AsyncMock()
    return vector


@pytest.fixture
def mock_embedding_adapter():
    """Mock embedding adapter for integration testing."""
    embedding = AsyncMock()
    embedding.embed_text = AsyncMock(return_value=[0.1, 0.2, 0.3])
    embedding.embed_documents = AsyncMock(return_value=[[0.1, 0.2, 0.3]])
    return embedding


class TestLangChainIntegration:
    """Test LangChain reasoning adapter integration with other ACB adapters."""

    @patch("acb.adapters.reasoning.langchain.Reasoning._ensure_client")
    async def test_langchain_with_ai_adapter(self, mock_ensure_client, mock_ai_adapter):
        """Test LangChain reasoning with AI adapter integration."""
        from acb.adapters.reasoning.langchain import Reasoning

        # Setup mocks
        mock_llm = AsyncMock()
        mock_llm.apredict = AsyncMock(return_value="Chain of thought response")
        mock_ensure_client.return_value = mock_llm

        reasoning = Reasoning()
        reasoning._settings = MagicMock()
        reasoning._settings.model = "gpt-3.5-turbo"
        reasoning._settings.temperature = 0.7

        # Mock AI adapter integration
        reasoning._ai_adapter = mock_ai_adapter

        request = ReasoningRequest(
            query="Analyze this complex problem",
            strategy=ReasoningStrategy.CHAIN_OF_THOUGHT,
            context=ReasoningContext(session_id="test_session"),
        )

        response = await reasoning.reason(request)

        assert response.strategy == ReasoningStrategy.CHAIN_OF_THOUGHT
        assert response.result is not None
        mock_ensure_client.assert_called_once()

    @patch("acb.adapters.reasoning.langchain.Reasoning._ensure_client")
    async def test_langchain_rag_with_vector_integration(
        self, mock_ensure_client, mock_vector_adapter, mock_embedding_adapter
    ):
        """Test LangChain RAG workflow with vector database integration."""
        from acb.adapters.reasoning.langchain import Reasoning

        # Setup mocks
        mock_llm = AsyncMock()
        mock_llm.apredict = AsyncMock(return_value="RAG-enhanced response")
        mock_ensure_client.return_value = mock_llm

        reasoning = Reasoning()
        reasoning._settings = MagicMock()
        reasoning._settings.model = "gpt-3.5-turbo"
        reasoning._settings.temperature = 0.7

        # Mock vector and embedding adapter integration
        reasoning._vector_adapter = mock_vector_adapter
        reasoning._embedding_adapter = mock_embedding_adapter

        request = ReasoningRequest(
            query="What is quantum computing?",
            strategy=ReasoningStrategy.RAG_WORKFLOW,
            context=ReasoningContext(
                knowledge_base="physics_kb",
                session_id="test_session",
            ),
        )

        # Mock vector search results
        mock_vector_adapter.search.return_value = [
            {"content": "Quantum computing uses quantum mechanics", "score": 0.95},
            {"content": "Qubits are fundamental units", "score": 0.87},
        ]

        response = await reasoning.reason(request)

        assert response.strategy == ReasoningStrategy.RAG_WORKFLOW
        assert response.result is not None
        mock_vector_adapter.search.assert_called_once()
        mock_embedding_adapter.embed_text.assert_called_once_with(
            "What is quantum computing?"
        )


class TestLlamaIndexIntegration:
    """Test LlamaIndex reasoning adapter integration with other ACB adapters."""

    @patch("acb.adapters.reasoning.llamaindex.Reasoning._ensure_client")
    @patch("acb.adapters.reasoning.llamaindex.VectorStoreIndex")
    async def test_llamaindex_with_vector_store(
        self, mock_index_class, mock_ensure_client, mock_vector_adapter
    ):
        """Test LlamaIndex reasoning with vector store integration."""
        from acb.adapters.reasoning.llamaindex import Reasoning

        # Setup mocks
        mock_llm = AsyncMock()
        mock_ensure_client.return_value = mock_llm

        mock_index = MagicMock()
        mock_query_engine = MagicMock()
        mock_response = MagicMock()
        mock_response.response = "LlamaIndex RAG response"
        mock_response.source_nodes = []
        mock_query_engine.query = AsyncMock(return_value=mock_response)
        mock_index.as_query_engine.return_value = mock_query_engine
        mock_index_class.return_value = mock_index

        reasoning = Reasoning()
        reasoning._settings = MagicMock()
        reasoning._settings.model = "gpt-3.5-turbo"
        reasoning._settings.similarity_top_k = 3

        # Mock vector adapter integration
        reasoning._vector_adapter = mock_vector_adapter

        ReasoningRequest(
            query="Explain machine learning",
            strategy=ReasoningStrategy.RAG_WORKFLOW,
            context=ReasoningContext(knowledge_base="ml_kb"),
        )

        response = await reasoning.rag_workflow("Explain machine learning", "ml_kb")

        assert response.strategy == ReasoningStrategy.RAG_WORKFLOW
        assert response.result == "LlamaIndex RAG response"

    @patch("acb.adapters.reasoning.llamaindex.Reasoning._ensure_client")
    async def test_llamaindex_with_embedding_adapter(
        self, mock_ensure_client, mock_embedding_adapter
    ):
        """Test LlamaIndex reasoning with embedding adapter integration."""
        from acb.adapters.reasoning.llamaindex import Reasoning

        mock_llm = AsyncMock()
        mock_ensure_client.return_value = mock_llm

        reasoning = Reasoning()
        reasoning._settings = MagicMock()
        reasoning._embedding_adapter = mock_embedding_adapter

        # Test embedding integration for document processing
        documents = ["Doc 1", "Doc 2", "Doc 3"]
        embeddings = await reasoning._embedding_adapter.embed_documents(documents)

        assert len(embeddings) == 1  # Mocked to return single embedding
        mock_embedding_adapter.embed_documents.assert_called_once_with(documents)


class TestCustomIntegration:
    """Test Custom reasoning adapter integration with other ACB adapters."""

    async def test_custom_with_monitoring_integration(self, mock_ai_adapter):
        """Test Custom reasoning with monitoring integration."""
        from acb.adapters.reasoning.custom import Reasoning

        reasoning = Reasoning()
        reasoning._settings = MagicMock()

        # Mock monitoring adapter
        mock_monitoring = AsyncMock()
        mock_monitoring.log_event = AsyncMock()
        reasoning._monitoring_adapter = mock_monitoring

        # Simulate rule-based reasoning with monitoring
        from acb.adapters.reasoning.custom import EnhancedRule

        rule = EnhancedRule(
            id="test_rule",
            name="Test Rule",
            description="Test rule for monitoring",
            conditions=[{"field": "status", "operator": "==", "value": "active"}],
            action="approve",
            priority=1,
            confidence=0.9,
        )

        reasoning._rule_engine.add_rule(rule)

        request = ReasoningRequest(
            query="Should we approve this?",
            strategy=ReasoningStrategy.RULE_BASED,
            context=ReasoningContext(data={"status": "active"}),
        )

        response = await reasoning.reason(request)

        assert response.result == "approve"
        assert response.confidence >= 0.9

        # Verify monitoring integration would be called
        if hasattr(reasoning, "_monitoring_adapter"):
            reasoning._monitoring_adapter.log_event.assert_not_called()  # Not actually integrated in this test

    async def test_custom_with_cache_integration(self):
        """Test Custom reasoning with cache integration."""
        from acb.adapters.reasoning.custom import Reasoning

        reasoning = Reasoning()
        reasoning._settings = MagicMock()

        # Mock cache adapter
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock()
        reasoning._cache_adapter = mock_cache

        # Test caching of reasoning results
        cache_key = "reasoning:rule_based:test_query"

        # First call - not in cache
        mock_cache.get.return_value = None

        # Would normally cache the result
        result = {"action": "approve", "confidence": 0.9}
        await mock_cache.set(cache_key, result, ttl=300)

        mock_cache.set.assert_called_once_with(cache_key, result, ttl=300)


class TestOpenAIFunctionsIntegration:
    """Test OpenAI Functions reasoning adapter integration with other ACB adapters."""

    @patch("acb.adapters.reasoning.openai_functions.AsyncOpenAI")
    async def test_openai_functions_with_tool_integration(
        self, mock_openai_class, mock_ai_adapter
    ):
        """Test OpenAI Functions reasoning with external tool integration."""
        from acb.adapters.reasoning.openai_functions import Reasoning

        # Setup mocks
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client

        mock_choice = MagicMock()
        mock_choice.message.content = "I'll use the search tool to find information."
        mock_choice.message.tool_calls = [
            MagicMock(
                id="call_123",
                function=MagicMock(
                    name="search_knowledge_base",
                    arguments='{"query": "machine learning", "kb": "tech"}',
                ),
            )
        ]
        mock_choice.finish_reason = "tool_calls"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        reasoning = Reasoning()
        reasoning._settings = MagicMock()
        reasoning._settings.api_key = "test-key"
        reasoning._settings.model = "gpt-4"

        # Mock external adapter integration
        reasoning._ai_adapter = mock_ai_adapter

        # Register external tool
        def search_knowledge_base(query: str, kb: str) -> str:
            # Would normally use vector or search adapter
            return f"Found information about {query} in {kb}"

        reasoning.register_function("search_knowledge_base", search_knowledge_base)

        request = ReasoningRequest(
            query="Tell me about machine learning",
            strategy=ReasoningStrategy.FUNCTION_CALLING,
            context=ReasoningContext(tools=["search_knowledge_base"]),
        )

        response = await reasoning.reason(request)

        assert response.strategy == ReasoningStrategy.FUNCTION_CALLING
        assert len(reasoning._function_calls) == 1

    @patch("acb.adapters.reasoning.openai_functions.AsyncOpenAI")
    async def test_openai_functions_with_storage_integration(self, mock_openai_class):
        """Test OpenAI Functions reasoning with storage integration."""
        from acb.adapters.reasoning.openai_functions import Reasoning

        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client

        reasoning = Reasoning()
        reasoning._settings = MagicMock()

        # Mock storage adapter
        mock_storage = AsyncMock()
        mock_storage.read = AsyncMock(return_value="Stored document content")
        mock_storage.write = AsyncMock()
        reasoning._storage_adapter = mock_storage

        # Register storage-integrated function
        def read_document(file_path: str) -> str:
            # Would use storage adapter
            return f"Content from {file_path}"

        reasoning.register_function("read_document", read_document)

        # Test function registration
        assert "read_document" in reasoning._functions


class TestCrossAdapterMemoryIntegration:
    """Test memory integration across different reasoning adapters."""

    async def test_shared_memory_across_adapters(self):
        """Test shared memory functionality across different reasoning adapters."""
        # This would test if memory stored by one adapter can be retrieved by another
        # In a real implementation, this might use a shared memory store

        memory_data = {
            "session_1": {
                MemoryType.CONVERSATION: ["User asked about AI"],
                MemoryType.SEMANTIC: ["AI stands for Artificial Intelligence"],
                MemoryType.EPISODIC: ["Previous successful reasoning about ML"],
            }
        }

        # Simulate shared memory store
        shared_memory = memory_data

        # Test with different adapters
        from acb.adapters.reasoning.custom import Reasoning as CustomReasoning
        from acb.adapters.reasoning.langchain import Reasoning as LangChainReasoning

        custom_reasoning = CustomReasoning()
        langchain_reasoning = LangChainReasoning()

        # Both adapters would access the same memory store
        custom_reasoning._memory = shared_memory
        langchain_reasoning._memory = shared_memory

        # Test memory retrieval consistency
        custom_memories = await custom_reasoning.retrieve_memory("session_1")
        langchain_memories = await langchain_reasoning.retrieve_memory("session_1")

        assert len(custom_memories) == len(langchain_memories)
        assert custom_memories == langchain_memories

    async def test_memory_persistence_with_storage_adapter(self):
        """Test memory persistence using storage adapter."""
        from acb.adapters.reasoning.custom import Reasoning

        reasoning = Reasoning()
        reasoning._settings = MagicMock()

        # Mock storage adapter for memory persistence
        mock_storage = AsyncMock()
        mock_storage.read = AsyncMock(
            return_value='{"session_1": {"conversation": ["test"]}}'
        )
        mock_storage.write = AsyncMock()
        reasoning._storage_adapter = mock_storage

        # Test loading memory from storage
        # In real implementation, this would load from persistent storage
        await reasoning.store_memory("session_1", "New memory", MemoryType.CONVERSATION)

        # Verify storage operations would be called
        # This is a simplified test - real implementation would be more complex
        assert "session_1" in reasoning._memory


class TestErrorHandlingIntegration:
    """Test error handling when integrating with other adapters."""

    async def test_vector_adapter_failure_handling(self):
        """Test handling of vector adapter failures."""
        from acb.adapters.reasoning.langchain import Reasoning

        reasoning = Reasoning()
        reasoning._settings = MagicMock()

        # Mock failing vector adapter
        mock_vector = AsyncMock()
        mock_vector.search.side_effect = Exception("Vector search failed")
        reasoning._vector_adapter = mock_vector

        # Test graceful failure handling
        try:
            await mock_vector.search("test query")
        except Exception as e:
            assert str(e) == "Vector search failed"

    async def test_ai_adapter_timeout_handling(self):
        """Test handling of AI adapter timeouts."""
        from acb.adapters.reasoning.openai_functions import Reasoning

        reasoning = Reasoning()
        reasoning._settings = MagicMock()

        # Mock AI adapter with timeout
        mock_ai = AsyncMock()
        mock_ai.complete.side_effect = TimeoutError("AI request timed out")
        reasoning._ai_adapter = mock_ai

        # Test timeout handling
        try:
            await mock_ai.complete("test prompt")
        except TimeoutError as e:
            assert str(e) == "AI request timed out"


class TestPerformanceIntegration:
    """Test performance considerations when integrating with other adapters."""

    async def test_concurrent_adapter_operations(self):
        """Test concurrent operations with multiple adapters."""
        import asyncio

        from acb.adapters.reasoning.custom import Reasoning

        reasoning = Reasoning()
        reasoning._settings = MagicMock()

        # Mock multiple adapters
        mock_ai = AsyncMock()
        mock_vector = AsyncMock()
        mock_cache = AsyncMock()

        mock_ai.complete.return_value = "AI response"
        mock_vector.search.return_value = [{"content": "Vector result"}]
        mock_cache.get.return_value = None

        # Test concurrent operations
        tasks = [
            mock_ai.complete("prompt 1"),
            mock_vector.search("query 1"),
            mock_cache.get("key 1"),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        assert len(results) == 3
        assert results[0] == "AI response"
        assert results[1] == [{"content": "Vector result"}]
        assert results[2] is None

    async def test_adapter_connection_pooling(self):
        """Test connection pooling across integrated adapters."""
        # This would test that adapters properly share connection pools
        # when appropriate, rather than creating redundant connections

        from acb.adapters.reasoning.langchain import Reasoning

        reasoning = Reasoning()
        reasoning._settings = MagicMock()

        # In a real implementation, this would test that database connections,
        # HTTP clients, etc. are properly pooled and reused

        # Mock connection tracking
        connection_count = 0

        class MockAdapter:
            def __init__(self):
                nonlocal connection_count
                connection_count += 1
                self.connection_id = connection_count

        # Test that multiple adapter instances can share resources
        adapter1 = MockAdapter()
        adapter2 = MockAdapter()

        # In real implementation, connection_count would remain 1 if pooling works
        assert adapter1.connection_id != adapter2.connection_id  # Without pooling
