"""Integration tests for embedding adapters."""

from unittest.mock import MagicMock, patch

import pytest

from acb.adapters import import_adapter
from acb.adapters.embedding import EmbeddingResult
from acb.depends import depends


@pytest.fixture
def mock_config():
    """Mock configuration for integration tests."""
    # Create a mock that mimics the Config class with necessary attributes
    config = MagicMock()
    config.debug = MagicMock()
    config.app = MagicMock()
    # For embedding configuration, we'll need to provide a way to access settings
    # by creating a nested structure similar to what is expected
    embedding_config = {
        "provider": "openai",
        "api_key": "test-key",
        "model": "text-embedding-3-small",
    }

    # Configure the mock to return the expected values when accessed
    config.embedding = embedding_config
    # Also make it work as an attribute or key access
    config.__getitem__ = (
        lambda self, key: embedding_config if key == "embedding" else getattr(self, key)
    )

    return config


@pytest.mark.asyncio
class TestEmbeddingAdapterIntegration:
    """Integration tests for embedding adapters."""

    async def test_import_adapter_discovery(self, mock_config):
        """Test embedding adapter discovery through import_adapter."""
        with (
            patch.object(depends, "get", return_value=mock_config),
            patch("acb.adapters.embedding.openai._openai_available", True),
        ):
            # Test that embedding adapter can be imported
            Embedding = import_adapter("embedding")
            assert Embedding is not None

    async def test_embedding_adapter_registry(self):
        """Test that all embedding adapters are properly registered."""
        from acb.adapters import STATIC_ADAPTER_MAPPINGS

        # Check that all embedding adapters are in static mappings
        embedding_adapters = [
            "embedding.openai",
            "embedding.huggingface",
            "embedding.sentence_transformers",
            "embedding.onnx",
            "embedding.lfm",
        ]

        for adapter_key in embedding_adapters:
            assert adapter_key in STATIC_ADAPTER_MAPPINGS
            module_path, class_name = STATIC_ADAPTER_MAPPINGS[adapter_key]
            assert module_path.startswith("acb.adapters.embedding.")
            assert class_name == "Embedding"

    async def test_embedding_capabilities(self):
        """Test that embedding capabilities are defined."""
        from acb.adapters import AdapterCapability

        # Check that embedding-specific capabilities exist
        embedding_capabilities = [
            AdapterCapability.BATCH_EMBEDDING,
            AdapterCapability.EDGE_OPTIMIZED,
            AdapterCapability.TEXT_PREPROCESSING,
            AdapterCapability.VECTOR_NORMALIZATION,
            AdapterCapability.DIMENSION_SCALING,
            AdapterCapability.SEMANTIC_SEARCH,
            AdapterCapability.SIMILARITY_COMPUTATION,
            AdapterCapability.DOCUMENT_CHUNKING,
            AdapterCapability.POOLING_STRATEGIES,
            AdapterCapability.MEMORY_EFFICIENT_PROCESSING,
        ]

        for capability in embedding_capabilities:
            assert capability.value is not None
            assert isinstance(capability.value, str)

    async def test_embedding_metadata_compliance(self):
        """Test that all embedding adapters have proper metadata."""
        from acb.adapters.embedding import (
            huggingface,
            lfm,
            onnx,
            openai,
            sentence_transformers,
        )

        modules = [openai, huggingface, sentence_transformers, onnx, lfm]

        for module in modules:
            assert hasattr(module, "MODULE_METADATA")
            metadata = module.MODULE_METADATA

            # Check required metadata fields
            assert metadata.name is not None
            assert metadata.category == "embedding"
            assert metadata.provider is not None
            assert metadata.version is not None
            assert metadata.acb_min_version is not None
            assert metadata.status is not None
            assert metadata.capabilities is not None
            assert metadata.required_packages is not None
            assert metadata.description is not None

    async def test_vector_database_integration_interface(self):
        """Test that embedding adapters provide interface for vector DB integration."""
        from acb.adapters.embedding._base import EmbeddingAdapter

        # Check that base adapter has methods needed for vector DB integration
        base_methods = [
            "embed_text",
            "embed_texts",
            "embed_documents",
            "compute_similarity",
        ]

        for method_name in base_methods:
            assert hasattr(EmbeddingAdapter, method_name)
            method = getattr(EmbeddingAdapter, method_name)
            assert callable(method)

    async def test_embedding_result_compatibility(self):
        """Test that embedding results are compatible with vector databases."""
        result = EmbeddingResult(
            text="test text",
            embedding=[0.1, 0.2, 0.3],
            model="test-model",
            dimensions=3,
        )

        # Check that result has fields needed for vector DB storage
        assert hasattr(result, "text")
        assert hasattr(result, "embedding")
        assert hasattr(result, "dimensions")
        assert hasattr(result, "metadata")

        # Check that embedding is a list of floats
        assert isinstance(result.embedding, list)
        assert all(isinstance(x, (int, float)) for x in result.embedding)

    async def test_performance_optimization_features(self):
        """Test that performance optimization features are available."""
        from acb.adapters.embedding._base import EmbeddingBaseSettings

        # Check that settings include performance optimization options
        settings = EmbeddingBaseSettings()

        performance_fields = [
            "batch_size",
            "cache_embeddings",
            "memory_limit_mb",
            "enable_model_caching",
            "normalize_embeddings",
        ]

        for field in performance_fields:
            assert hasattr(settings, field)

    async def test_edge_deployment_support(self):
        """Test that edge deployment features are available."""
        from acb.adapters.embedding.lfm import LiquidLFMEmbeddingSettings
        from acb.adapters.embedding.onnx import ONNXEmbeddingSettings

        # LFM settings should have edge optimization
        lfm_settings = LiquidLFMEmbeddingSettings()
        assert hasattr(lfm_settings, "edge_optimized")
        assert hasattr(lfm_settings, "memory_limit_mb")
        assert hasattr(lfm_settings, "cold_start_optimization")

        # ONNX settings should have optimization features
        onnx_settings = ONNXEmbeddingSettings(
            model_path="/fake/path", tokenizer_name="test-tokenizer"
        )
        assert hasattr(onnx_settings, "optimize_for_inference")
        assert hasattr(onnx_settings, "enable_quantization")
        assert hasattr(onnx_settings, "graph_optimization_level")


@pytest.mark.asyncio
class TestEmbeddingWorkflows:
    """Test common embedding workflows."""

    @pytest.fixture
    async def mock_embedding_adapter(self):
        """Create a mock embedding adapter for workflow testing."""
        from tests.adapters.embedding.test_base import MockEmbeddingAdapter

        adapter = MockEmbeddingAdapter()
        yield adapter
        await adapter.cleanup()

    async def test_rag_preparation_workflow(self, mock_embedding_adapter):
        """Test workflow for preparing embeddings for RAG systems."""
        # Simulate document preparation for RAG
        documents = [
            "Python is a programming language.",
            "Machine learning uses algorithms to learn patterns.",
            "Vector databases store high-dimensional data efficiently.",
        ]

        # Step 1: Generate embeddings for documents
        embeddings_batch = await mock_embedding_adapter.embed_texts(documents)
        assert len(embeddings_batch.results) == 3

        # Step 2: Prepare query embedding
        query = "What is Python?"
        query_embedding = await mock_embedding_adapter.embed_text(query)
        assert len(query_embedding) == 384

        # Step 3: Compute similarities
        similarities = []
        for result in embeddings_batch.results:
            similarity = await mock_embedding_adapter.compute_similarity(
                query_embedding, result.embedding, "cosine"
            )
            similarities.append((result.text, similarity))

        # Should have computed similarities for all documents
        assert len(similarities) == 3
        assert all(isinstance(sim[1], float) for sim in similarities)

    async def test_semantic_search_workflow(self, mock_embedding_adapter):
        """Test semantic search workflow."""
        # Document corpus
        documents = [
            "The weather is sunny today.",
            "I love eating pizza and pasta.",
            "Python programming is fun and powerful.",
            "Artificial intelligence is transforming technology.",
            "The cat is sleeping on the couch.",
        ]

        # Generate document embeddings
        doc_batch = await mock_embedding_adapter.embed_texts(documents)

        # Search queries
        queries = [
            "programming languages",
            "food and cooking",
            "weather conditions",
        ]

        search_results = {}
        for query in queries:
            query_embedding = await mock_embedding_adapter.embed_text(query)

            # Find most similar documents
            similarities = []
            for result in doc_batch.results:
                similarity = await mock_embedding_adapter.compute_similarity(
                    query_embedding, result.embedding, "cosine"
                )
                similarities.append((result.text, similarity))

            # Sort by similarity
            similarities.sort(key=lambda x: x[1], reverse=True)
            search_results[query] = similarities[:2]  # Top 2 results

        # Should have results for all queries
        assert len(search_results) == 3
        for query, results in search_results.items():
            assert len(results) == 2
            assert all(isinstance(sim, float) for _, sim in results)

    async def test_document_chunking_workflow(self, mock_embedding_adapter):
        """Test document chunking workflow for large texts."""
        # Large document
        large_document = (
            """
        This is a very long document that needs to be chunked for embedding generation.
        It contains multiple paragraphs and sections that discuss various topics.
        The document is too long to process in a single embedding call.
        """
            * 50
        )  # Make it very long

        # Embed with chunking
        doc_batches = await mock_embedding_adapter.embed_documents(
            [large_document],
            chunk_size=200,
            chunk_overlap=50,
        )

        assert len(doc_batches) == 1
        batch = doc_batches[0]

        # Should have multiple chunks
        assert len(batch.results) > 1

        # All chunks should have metadata
        for result in batch.results:
            assert result.metadata["is_chunk"] is True
            assert "document_id" in result.metadata
            assert "chunk_size" in result.metadata
            assert "chunk_overlap" in result.metadata

    async def test_batch_processing_workflow(self, mock_embedding_adapter):
        """Test efficient batch processing workflow."""
        # Large number of texts to process
        texts = [
            f"Document {i}: This is content for document number {i}."
            for i in range(100)
        ]

        # Process in batches
        batch_size = 20
        all_results = []

        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i : i + batch_size]
            batch_result = await mock_embedding_adapter.embed_texts(batch_texts)
            all_results.extend(batch_result.results)

        # Should have processed all texts
        assert len(all_results) == 100

        # All should have valid embeddings
        for result in all_results:
            assert len(result.embedding) == 384
            assert result.dimensions == 384


@pytest.mark.asyncio
class TestEmbeddingPerformance:
    """Test performance-related features."""

    async def test_memory_efficiency_simulation(self):
        """Test memory efficiency features (simulation)."""
        from acb.adapters.embedding.lfm import LiquidLFMEmbeddingSettings

        # Test memory-efficient settings
        settings = LiquidLFMEmbeddingSettings(
            memory_limit_mb=128,
            edge_optimized=True,
            adaptive_precision=True,
        )

        assert settings.memory_limit_mb == 128
        assert settings.edge_optimized is True
        assert settings.adaptive_precision is True

    async def test_caching_simulation(self):
        """Test embedding caching features (simulation)."""
        from acb.adapters.embedding._base import EmbeddingBaseSettings

        settings = EmbeddingBaseSettings(
            cache_embeddings=True,
            cache_ttl=3600,
            enable_model_caching=True,
        )

        assert settings.cache_embeddings is True
        assert settings.cache_ttl == 3600
        assert settings.enable_model_caching is True

    async def test_optimization_features(self):
        """Test optimization features availability."""
        from acb.adapters.embedding.onnx import ONNXEmbeddingSettings

        settings = ONNXEmbeddingSettings(
            model_path="/fake/path",
            tokenizer_name="test-tokenizer",
            optimize_for_inference=True,
            enable_quantization=True,
            graph_optimization_level="ORT_ENABLE_ALL",
        )

        assert settings.optimize_for_inference is True
        assert settings.enable_quantization is True
        assert settings.graph_optimization_level == "ORT_ENABLE_ALL"
