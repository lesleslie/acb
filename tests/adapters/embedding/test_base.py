"""Tests for base embedding adapter functionality."""

from unittest.mock import MagicMock

import pytest

from acb.adapters.embedding._base import (
    EmbeddingAdapter,
    EmbeddingBaseSettings,
    EmbeddingBatch,
    EmbeddingResult,
    EmbeddingUtils,
    VectorNormalization,
)


class MockEmbeddingAdapter(EmbeddingAdapter):
    """Mock embedding adapter for testing."""

    def __init__(self, settings=None):
        super().__init__(settings)
        self._mock_client = MagicMock()

    async def _ensure_client(self):
        self._client = self._mock_client
        return self._client

    async def _embed_texts(self, texts, model, normalize, batch_size, **kwargs):
        # Generate mock embeddings
        results = []
        for i, text in enumerate(texts):
            embedding = [0.1 + i * 0.1] * 384  # Mock 384-dimensional embedding
            if normalize:
                embedding = self._normalize_vector(embedding)

            result = EmbeddingResult(
                text=text,
                embedding=embedding,
                model=model,
                dimensions=len(embedding),
                tokens=len(text.split()),
                metadata={"mock": True},
            )
            results.append(result)

        return EmbeddingBatch(
            results=results,
            total_tokens=sum(len(text.split()) for text in texts),
            processing_time=0.1,
            model=model,
            batch_size=len(results),
        )

    async def _embed_documents(
        self, documents, chunk_size, chunk_overlap, model, **kwargs
    ):
        batches = []
        for i, document in enumerate(documents):
            chunks = self._chunk_text(document, chunk_size, chunk_overlap)
            # Generate embeddings for chunks using the base _embed_texts implementation
            original_batch = await self._embed_texts(
                chunks, model, normalize=True, batch_size=32, **kwargs
            )

            # Create new results with updated metadata
            updated_results = []
            for j, result in enumerate(original_batch.results):
                updated_result = EmbeddingResult(
                    text=result.text,
                    embedding=result.embedding,
                    model=result.model,
                    dimensions=result.dimensions,
                    tokens=result.tokens,
                    metadata={
                        **result.metadata,  # Preserve original metadata
                        "is_chunk": True,
                        "document_id": i,
                        "chunk_index": j,
                    },
                )
                updated_results.append(updated_result)

            # Create a new batch with updated results
            updated_batch = EmbeddingBatch(
                results=updated_results,
                total_tokens=original_batch.total_tokens,
                processing_time=original_batch.processing_time,
                model=original_batch.model,
                batch_size=original_batch.batch_size,
            )
            batches.append(updated_batch)
        return batches

    async def _embed_documents(
        self, documents, chunk_size, chunk_overlap, model, **kwargs
    ):
        batches = []
        for document in documents:
            chunks = self._chunk_text(document, chunk_size, chunk_overlap)
            batch = await self._embed_texts(chunks, model, True, 32, **kwargs)
            batches.append(batch)
        return batches

    async def _compute_similarity(self, embedding1, embedding2, method):
        if method == "cosine":
            return EmbeddingUtils.cosine_similarity(embedding1, embedding2)
        return 0.8

    async def _get_model_info(self, model):
        return {
            "name": model,
            "provider": "mock",
            "dimensions": 384,
        }

    async def _list_models(self):
        return [
            {"name": "mock-model", "provider": "mock", "dimensions": 384},
        ]


@pytest.fixture
async def mock_embedding_adapter():
    """Create a mock embedding adapter."""
    adapter = MockEmbeddingAdapter()
    yield adapter
    await adapter.cleanup()


@pytest.mark.asyncio
class TestEmbeddingAdapter:
    """Test cases for EmbeddingAdapter base class."""

    async def test_embed_text_single(self, mock_embedding_adapter):
        """Test embedding a single text."""
        text = "Hello world"
        embedding = await mock_embedding_adapter.embed_text(text)

        assert isinstance(embedding, list)
        assert len(embedding) == 384
        assert all(isinstance(x, float) for x in embedding)

    async def test_embed_texts_multiple(self, mock_embedding_adapter):
        """Test embedding multiple texts."""
        texts = ["Hello world", "How are you?", "Test embedding"]
        batch = await mock_embedding_adapter.embed_texts(texts)

        assert isinstance(batch, EmbeddingBatch)
        assert len(batch.results) == 3
        assert batch.batch_size == 3
        assert batch.model == "text-embedding-3-small"

        for i, result in enumerate(batch.results):
            assert result.text == texts[i]
            assert len(result.embedding) == 384
            assert result.dimensions == 384

    async def test_embed_documents_chunking(self, mock_embedding_adapter):
        """Test document embedding with chunking."""
        documents = ["This is a long document that should be chunked. " * 20]
        batches = await mock_embedding_adapter.embed_documents(
            documents, chunk_size=100
        )

        assert len(batches) == 1
        batch = batches[0]
        assert len(batch.results) > 1  # Should be chunked

        # Check metadata
        for result in batch.results:
            assert result.metadata["is_chunk"] is True
            assert "document_id" in result.metadata

    async def test_compute_similarity(self, mock_embedding_adapter):
        """Test similarity computation."""
        embedding1 = [1.0, 0.0, 0.0]
        embedding2 = [0.0, 1.0, 0.0]

        similarity = await mock_embedding_adapter.compute_similarity(
            embedding1, embedding2
        )
        assert isinstance(similarity, float)
        assert 0.0 <= similarity <= 1.0

    async def test_get_model_info(self, mock_embedding_adapter):
        """Test getting model information."""
        info = await mock_embedding_adapter.get_model_info("test-model")

        assert isinstance(info, dict)
        assert "name" in info
        assert "provider" in info
        assert "dimensions" in info

    async def test_list_models(self, mock_embedding_adapter):
        """Test listing available models."""
        models = await mock_embedding_adapter.list_models()

        assert isinstance(models, list)
        assert len(models) > 0
        assert all("name" in model for model in models)

    async def test_context_manager(self):
        """Test adapter as context manager."""
        async with MockEmbeddingAdapter() as adapter:
            assert adapter._client is not None
            embedding = await adapter.embed_text("test")
            assert len(embedding) == 384

    async def test_normalize_vector(self, mock_embedding_adapter):
        """Test vector normalization."""
        vector = [3.0, 4.0, 0.0]

        # L2 normalization
        normalized = mock_embedding_adapter._normalize_vector(
            vector, VectorNormalization.L2
        )
        assert abs(sum(x**2 for x in normalized) - 1.0) < 1e-6

        # L1 normalization
        normalized_l1 = mock_embedding_adapter._normalize_vector(
            vector, VectorNormalization.L1
        )
        assert abs(sum(abs(x) for x in normalized_l1) - 1.0) < 1e-6

        # No normalization
        no_norm = mock_embedding_adapter._normalize_vector(
            vector, VectorNormalization.NONE
        )
        assert no_norm == vector

    async def test_chunk_text(self, mock_embedding_adapter):
        """Test text chunking."""
        text = "This is a test document with multiple sentences. " * 10
        chunks = mock_embedding_adapter._chunk_text(text, chunk_size=100, overlap=20)

        assert len(chunks) > 1
        assert all(
            len(chunk) <= 100 for chunk in chunks[:-1]
        )  # All but last should be <= chunk_size

    async def test_batch_texts(self, mock_embedding_adapter):
        """Test text batching."""
        texts = [f"Text {i}" for i in range(25)]
        batches = mock_embedding_adapter._batch_texts(texts, batch_size=10)

        assert len(batches) == 3  # 25 texts / 10 batch_size = 3 batches
        assert len(batches[0]) == 10
        assert len(batches[1]) == 10
        assert len(batches[2]) == 5

    async def test_cleanup(self, mock_embedding_adapter):
        """Test adapter cleanup."""
        # Setup client
        await mock_embedding_adapter._ensure_client()
        assert mock_embedding_adapter._client is not None

        # Cleanup
        await mock_embedding_adapter.cleanup()
        assert mock_embedding_adapter._client is None


class TestEmbeddingUtils:
    """Test cases for EmbeddingUtils."""

    def test_cosine_similarity(self):
        """Test cosine similarity computation."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        vec3 = [1.0, 0.0, 0.0]

        # Orthogonal vectors
        assert abs(EmbeddingUtils.cosine_similarity(vec1, vec2)) < 1e-6

        # Identical vectors
        assert abs(EmbeddingUtils.cosine_similarity(vec1, vec3) - 1.0) < 1e-6

    def test_euclidean_distance(self):
        """Test Euclidean distance computation."""
        vec1 = [0.0, 0.0, 0.0]
        vec2 = [3.0, 4.0, 0.0]

        distance = EmbeddingUtils.euclidean_distance(vec1, vec2)
        assert abs(distance - 5.0) < 1e-6

    def test_dot_product(self):
        """Test dot product computation."""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [4.0, 5.0, 6.0]

        dot = EmbeddingUtils.dot_product(vec1, vec2)
        assert dot == 32.0  # 1*4 + 2*5 + 3*6 = 32

    def test_manhattan_distance(self):
        """Test Manhattan distance computation."""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [4.0, 6.0, 8.0]

        distance = EmbeddingUtils.manhattan_distance(vec1, vec2)
        assert distance == 12.0  # |1-4| + |2-6| + |3-8| = 3 + 4 + 5 = 12


class TestEmbeddingDataStructures:
    """Test cases for embedding data structures."""

    def test_embedding_result(self):
        """Test EmbeddingResult creation."""
        result = EmbeddingResult(
            text="test text",
            embedding=[0.1, 0.2, 0.3],
            model="test-model",
            dimensions=3,
            tokens=2,
            metadata={"test": True},
        )

        assert result.text == "test text"
        assert result.embedding == [0.1, 0.2, 0.3]
        assert result.model == "test-model"
        assert result.dimensions == 3
        assert result.tokens == 2
        assert result.metadata["test"] is True

    def test_embedding_batch(self):
        """Test EmbeddingBatch creation."""
        results = [
            EmbeddingResult(
                text=f"text {i}",
                embedding=[0.1 * i] * 3,
                model="test-model",
                dimensions=3,
            )
            for i in range(3)
        ]

        batch = EmbeddingBatch(
            results=results,
            total_tokens=10,
            processing_time=0.5,
            model="test-model",
            batch_size=3,
        )

        assert len(batch.results) == 3
        assert batch.total_tokens == 10
        assert batch.processing_time == 0.5
        assert batch.model == "test-model"
        assert batch.batch_size == 3

    def test_embedding_base_settings(self):
        """Test EmbeddingBaseSettings creation."""
        settings = EmbeddingBaseSettings(
            model="custom-model",
            batch_size=64,
            normalize_embeddings=False,
        )

        assert settings.model == "custom-model"
        assert settings.batch_size == 64
        assert settings.normalize_embeddings is False
        assert settings.timeout == 30.0  # Default value


@pytest.mark.asyncio
class TestEmbeddingAdapterIntegration:
    """Integration tests for embedding adapters."""

    async def test_end_to_end_workflow(self, mock_embedding_adapter):
        """Test complete embedding workflow."""
        # Single text embedding
        text = "Test embedding workflow"
        embedding = await mock_embedding_adapter.embed_text(text)
        assert len(embedding) == 384

        # Multiple texts
        texts = ["First text", "Second text", "Third text"]
        batch = await mock_embedding_adapter.embed_texts(texts)
        assert len(batch.results) == 3

        # Document chunking
        long_document = "This is a very long document. " * 50
        doc_batches = await mock_embedding_adapter.embed_documents([long_document])
        assert len(doc_batches) == 1
        assert len(doc_batches[0].results) > 1

        # Similarity computation
        emb1 = batch.results[0].embedding
        emb2 = batch.results[1].embedding
        similarity = await mock_embedding_adapter.compute_similarity(emb1, emb2)
        assert isinstance(similarity, float)

        # Model information
        info = await mock_embedding_adapter.get_model_info()
        assert "name" in info

        # List models
        models = await mock_embedding_adapter.list_models()
        assert len(models) > 0
