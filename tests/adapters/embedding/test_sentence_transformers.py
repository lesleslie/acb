"""Tests for Sentence Transformers embedding adapter."""

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from acb.adapters.embedding._base import EmbeddingBatch
from acb.adapters.embedding.sentence_transformers import (
    SentenceTransformersEmbedding,
    SentenceTransformersSettings,
)
from acb.depends import depends


@pytest.fixture
def mock_sentence_transformer():
    """Mock SentenceTransformer model."""
    model = MagicMock()
    model.max_seq_length = 512
    model.get_sentence_embedding_dimension.return_value = 384

    # Mock encode method
    def mock_encode(texts, **kwargs):
        embeddings = []
        for i, text in enumerate(texts):
            # Create deterministic embeddings
            embedding = np.array([0.1 + i * 0.1] * 384, dtype=np.float32)
            if kwargs.get("normalize_embeddings", False):
                embedding = embedding / np.linalg.norm(embedding)
            embeddings.append(embedding)
        return np.array(embeddings)

    model.encode = mock_encode
    return model


@pytest.fixture
def mock_config():
    """Mock configuration."""
    config = MagicMock()
    # Add necessary attributes that the sentence transformers adapter expects
    config.debug = MagicMock()
    config.app = MagicMock()
    config.app.name = "test_app"
    config.embedding = MagicMock()
    config.embedding.model = "all-MiniLM-L6-v2"
    config.embedding.device = "cpu"
    return config


@pytest.fixture
async def sentence_transformers_adapter(mock_config, mock_sentence_transformer):
    """Create Sentence Transformers embedding adapter with mocked dependencies."""
    with (
        patch(
            "acb.adapters.embedding.sentence_transformers._sentence_transformers_available",
            True,
        ),
        patch(
            "acb.adapters.embedding.sentence_transformers.SentenceTransformer"
        ) as mock_st_class,
        patch("acb.adapters.embedding.sentence_transformers.torch") as mock_torch,
        patch.object(depends, "get") as mock_depends,
    ):
        mock_depends.return_value = mock_config
        mock_torch.cuda.is_available.return_value = False
        mock_st_class.return_value = mock_sentence_transformer

        settings = SentenceTransformersSettings(
            model="all-MiniLM-L6-v2",
            device="cpu",
        )

        adapter = SentenceTransformersEmbedding(settings)
        adapter._model = mock_sentence_transformer
        adapter._device = "cpu"

        yield adapter, mock_sentence_transformer

        await adapter.cleanup()


@pytest.mark.asyncio
class TestSentenceTransformersEmbedding:
    """Test cases for Sentence Transformers embedding adapter."""

    async def test_initialization(self, mock_config):
        """Test adapter initialization."""
        with (
            patch(
                "acb.adapters.embedding.sentence_transformers._sentence_transformers_available",
                True,
            ),
            patch.object(depends, "get", return_value=mock_config),
        ):
            settings = SentenceTransformersSettings(
                model="all-MiniLM-L6-v2",
                device="cpu",
            )

            adapter = SentenceTransformersEmbedding(settings)
            assert adapter._settings.model == "all-MiniLM-L6-v2"
            assert adapter._settings.device == "cpu"

    async def test_initialization_without_sentence_transformers(self):
        """Test adapter initialization when Sentence Transformers is not available."""
        with patch(
            "acb.adapters.embedding.sentence_transformers._sentence_transformers_available",
            False,
        ):
            with pytest.raises(
                ImportError, match="Sentence Transformers library not available"
            ):
                SentenceTransformersEmbedding()

    async def test_load_model_cpu(self, mock_config):
        """Test model loading on CPU."""
        with (
            patch(
                "acb.adapters.embedding.sentence_transformers._sentence_transformers_available",
                True,
            ),
            patch("acb.adapters.embedding.sentence_transformers.SentenceTransformer"),
            patch("acb.adapters.embedding.sentence_transformers.torch") as mock_torch,
            patch.object(depends, "get", return_value=mock_config),
            patch("asyncio.get_event_loop") as mock_loop,
        ):
            mock_torch.cuda.is_available.return_value = False
            mock_executor = AsyncMock()
            mock_loop.return_value.run_in_executor = mock_executor

            settings = SentenceTransformersSettings(device="auto")
            adapter = SentenceTransformersEmbedding(settings)

            await adapter._load_model()

            assert adapter._device == "cpu"

    async def test_load_model_cuda(self, mock_config):
        """Test model loading on CUDA."""
        with (
            patch(
                "acb.adapters.embedding.sentence_transformers._sentence_transformers_available",
                True,
            ),
            patch("acb.adapters.embedding.sentence_transformers.SentenceTransformer"),
            patch("acb.adapters.embedding.sentence_transformers.torch") as mock_torch,
            patch.object(depends, "get", return_value=mock_config),
            patch("asyncio.get_event_loop") as mock_loop,
        ):
            mock_torch.cuda.is_available.return_value = True
            mock_executor = AsyncMock()
            mock_loop.return_value.run_in_executor = mock_executor

            settings = SentenceTransformersSettings(device="auto")
            adapter = SentenceTransformersEmbedding(settings)

            await adapter._load_model()

            assert adapter._device == "cuda"

    async def test_embed_texts_success(self, sentence_transformers_adapter):
        """Test successful text embedding."""
        adapter, mock_model = sentence_transformers_adapter

        texts = ["Hello world", "How are you?"]
        batch = await adapter._embed_texts(
            texts=texts,
            model="all-MiniLM-L6-v2",
            normalize=True,
            batch_size=10,
        )

        assert isinstance(batch, EmbeddingBatch)
        assert len(batch.results) == 2
        assert batch.model == "all-MiniLM-L6-v2"

        # Check individual results
        for i, result in enumerate(batch.results):
            assert result.text == texts[i]
            assert len(result.embedding) == 384
            assert result.model == "all-MiniLM-L6-v2"
            assert result.dimensions == 384
            assert result.metadata["device"] == "cpu"
            assert result.metadata["normalized"] is True

    async def test_embed_texts_without_normalization(
        self, sentence_transformers_adapter
    ):
        """Test text embedding without normalization."""
        adapter, mock_model = sentence_transformers_adapter

        texts = ["Test text"]
        batch = await adapter._embed_texts(
            texts=texts,
            model="all-MiniLM-L6-v2",
            normalize=False,
            batch_size=1,
        )

        result = batch.results[0]
        assert result.metadata["normalized"] is False

    async def test_embed_documents(self, sentence_transformers_adapter):
        """Test document embedding with chunking."""
        adapter, mock_model = sentence_transformers_adapter

        documents = ["This is a long document that should be chunked. " * 20]
        batches = await adapter._embed_documents(
            documents=documents,
            chunk_size=100,
            chunk_overlap=20,
            model="all-MiniLM-L6-v2",
        )

        assert len(batches) == 1
        batch = batches[0]
        assert len(batch.results) > 1  # Should be chunked

        # Check metadata
        for result in batch.results:
            assert result.metadata["is_chunk"] is True
            assert "document_id" in result.metadata

    async def test_similarity_search(self, sentence_transformers_adapter):
        """Test semantic similarity search."""
        adapter, mock_model = sentence_transformers_adapter

        # Mock similarity method
        def mock_similarity(query_embeddings, doc_embeddings):
            # Return mock similarities
            return np.array([[0.9, 0.7, 0.5]])

        mock_model.similarity = mock_similarity

        query = "test query"
        documents = ["similar document", "somewhat similar", "different text"]

        results = await adapter.similarity_search(query, documents, top_k=2)

        assert len(results) == 2
        assert results[0][1] > results[1][1]  # Should be sorted by similarity

    async def test_compute_similarity(self, sentence_transformers_adapter):
        """Test similarity computation."""
        adapter, _ = sentence_transformers_adapter

        embedding1 = [1.0, 0.0, 0.0]
        embedding2 = [0.0, 1.0, 0.0]

        # Test cosine similarity
        similarity = await adapter._compute_similarity(embedding1, embedding2, "cosine")
        assert similarity == 0.0  # Orthogonal vectors

        # Test unsupported method
        with pytest.raises(ValueError, match="Unsupported similarity method"):
            await adapter._compute_similarity(embedding1, embedding2, "unsupported")

    async def test_get_model_info(self, sentence_transformers_adapter):
        """Test getting model information."""
        adapter, mock_model = sentence_transformers_adapter

        info = await adapter._get_model_info("all-MiniLM-L6-v2")

        assert info["name"] == "all-MiniLM-L6-v2"
        assert info["provider"] == "sentence_transformers"
        assert info["device"] == "cpu"
        assert info["local"] is True
        assert info["max_position_embeddings"] is None  # Mock doesn't have this
        assert info["hidden_size"] is None  # Mock doesn't have this

    async def test_list_models(self, sentence_transformers_adapter):
        """Test listing available models."""
        adapter, _ = sentence_transformers_adapter

        models = await adapter._list_models()
        assert isinstance(models, list)
        assert len(models) > 0

        # Check model structure
        for model in models:
            assert "name" in model
            assert "provider" in model
            assert "description" in model
            assert model["provider"] == "sentence_transformers"

    async def test_health_check_success(self, sentence_transformers_adapter):
        """Test successful health check."""
        adapter, mock_model = sentence_transformers_adapter

        health = await adapter.health_check()

        assert health["status"] == "healthy"
        assert health["provider"] == "sentence_transformers"
        assert health["model"] == "all-MiniLM-L6-v2"
        assert health["device"] == "cpu"
        assert "timestamp" in health

    async def test_health_check_failure(self, sentence_transformers_adapter):
        """Test health check failure."""
        adapter, mock_model = sentence_transformers_adapter

        # Mock embed_text to raise an exception
        with patch.object(adapter, "embed_text", side_effect=Exception("Model error")):
            health = await adapter.health_check()

            assert health["status"] == "unhealthy"
            assert health["provider"] == "sentence_transformers"
            assert "error" in health
            assert "timestamp" in health

    async def test_cleanup(self, sentence_transformers_adapter):
        """Test adapter cleanup."""
        adapter, mock_model = sentence_transformers_adapter

        with patch("acb.adapters.embedding.sentence_transformers.torch") as mock_torch:
            mock_torch.cuda.is_available.return_value = True
            mock_torch.cuda.empty_cache = MagicMock()

            await adapter.cleanup()

            # Model should be cleaned up
            assert adapter._model is None
            assert adapter._tokenizer is None

            # CUDA cache should be cleared
            mock_torch.cuda.empty_cache.assert_called_once()

    async def test_error_handling(self, sentence_transformers_adapter):
        """Test error handling during embedding generation."""
        adapter, mock_model = sentence_transformers_adapter

        # Mock encode to raise an exception
        mock_model.encode = MagicMock(side_effect=Exception("Encoding error"))

        with pytest.raises(Exception, match="Encoding error"):
            await adapter._embed_texts(
                texts=["test"],
                model="all-MiniLM-L6-v2",
                normalize=True,
                batch_size=1,
            )

    async def test_precision_settings(self, mock_config):
        """Test model precision settings."""
        with (
            patch(
                "acb.adapters.embedding.sentence_transformers._sentence_transformers_available",
                True,
            ),
            patch(
                "acb.adapters.embedding.sentence_transformers.SentenceTransformer"
            ) as mock_st_class,
            patch.object(depends, "get", return_value=mock_config),
        ):
            mock_model = MagicMock()
            mock_model.half = MagicMock()
            mock_st_class.return_value = mock_model

            settings = SentenceTransformersSettings(
                device="cuda",
                precision="float16",
            )

            adapter = SentenceTransformersEmbedding(settings)
            adapter._device = "cuda"

            await adapter._load_model()

            # half() should be called for float16 precision on CUDA
            mock_model.half.assert_called_once()


@pytest.mark.asyncio
class TestSentenceTransformersSettings:
    """Test cases for Sentence Transformers settings."""

    def test_settings_defaults(self):
        """Test default settings values."""
        settings = SentenceTransformersSettings()

        assert settings.model == "all-MiniLM-L6-v2"
        assert settings.device == "auto"
        assert settings.normalize_embeddings is True
        assert settings.convert_to_numpy is True
        assert settings.convert_to_tensor is False
        assert settings.batch_size == 32

    def test_settings_custom_values(self):
        """Test custom settings values."""
        settings = SentenceTransformersSettings(
            model="all-mpnet-base-v2",
            device="cuda",
            batch_size=64,
            normalize_embeddings=False,
        )

        assert settings.model == "all-mpnet-base-v2"
        assert settings.device == "cuda"
        assert settings.batch_size == 64
        assert settings.normalize_embeddings is False

    def test_environment_prefix(self):
        """Test environment variable prefix."""
        assert (
            SentenceTransformersSettings.Config.env_prefix == "SENTENCE_TRANSFORMERS_"
        )


@pytest.mark.asyncio
class TestSentenceTransformersIntegration:
    """Integration tests for Sentence Transformers adapter."""

    async def test_end_to_end_workflow(self, sentence_transformers_adapter):
        """Test complete embedding workflow."""
        adapter, mock_model = sentence_transformers_adapter

        # Single text embedding
        text = "Test embedding workflow"
        embedding = await adapter.embed_text(text)
        assert len(embedding) == 384

        # Multiple texts
        texts = ["First text", "Second text", "Third text"]
        batch = await adapter.embed_texts(texts)
        assert len(batch.results) == 3

        # Document chunking
        long_document = "This is a very long document. " * 50
        doc_batches = await adapter.embed_documents([long_document])
        assert len(doc_batches) == 1
        assert len(doc_batches[0].results) > 1

        # Model information
        info = await adapter.get_model_info()
        assert "name" in info

        # List models
        models = await adapter.list_models()
        assert len(models) > 0
