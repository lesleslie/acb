"""Tests for OpenAI embedding adapter."""

from unittest.mock import AsyncMock, MagicMock, patch

import asyncio
import pytest

from acb.adapters.embedding._base import EmbeddingBatch
from acb.adapters.embedding.openai import OpenAIEmbedding, OpenAIEmbeddingSettings
from acb.config import Config
from acb.depends import depends


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response."""
    response = MagicMock()
    response.data = [
        MagicMock(embedding=[0.1, 0.2, 0.3] * 128, index=0, object="embedding"),
        MagicMock(embedding=[0.2, 0.3, 0.4] * 128, index=1, object="embedding"),
    ]
    response.model = "text-embedding-3-small"
    response.usage = MagicMock(total_tokens=15)
    return response


@pytest.fixture
def mock_config():
    """Mock configuration."""
    config = MagicMock(spec=Config)
    config.get.return_value = {
        "api_key": "test-key",
        "model": "text-embedding-3-small",
    }
    return config


@pytest.fixture
async def openai_adapter(mock_config):
    """Create OpenAI embedding adapter with mocked dependencies."""
    with (
        patch("acb.adapters.embedding.openai._openai_available", True),
        patch("acb.adapters.embedding.openai.AsyncOpenAI") as mock_openai_class,
        patch.object(depends, "get") as mock_depends,
    ):
        mock_depends.return_value = mock_config

        # Mock the OpenAI client
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client

        settings = OpenAIEmbeddingSettings(
            api_key="test-key",
            model="text-embedding-3-small",
        )

        adapter = OpenAIEmbedding(settings)
        adapter._client = mock_client

        yield adapter, mock_client

        await adapter.cleanup()


@pytest.mark.asyncio
class TestOpenAIEmbedding:
    """Test cases for OpenAI embedding adapter."""

    async def test_initialization(self, mock_config):
        """Test adapter initialization."""
        with (
            patch("acb.adapters.embedding.openai._openai_available", True),
            patch.object(depends, "get", return_value=mock_config),
        ):
            settings = OpenAIEmbeddingSettings(
                api_key="test-key",
                model="text-embedding-3-small",
            )

            adapter = OpenAIEmbedding(settings)
            assert adapter._settings.api_key.get_secret_value() == "test-key"
            assert adapter._settings.model == "text-embedding-3-small"

    async def test_initialization_without_openai(self):
        """Test adapter initialization when OpenAI is not available."""
        with patch("acb.adapters.embedding.openai._openai_available", False):
            with pytest.raises(ImportError, match="OpenAI library not available"):
                OpenAIEmbedding()

    async def test_ensure_client(self, openai_adapter):
        """Test client initialization."""
        adapter, mock_client = openai_adapter

        with patch("acb.adapters.embedding.openai.AsyncOpenAI") as mock_openai_class:
            mock_openai_class.return_value = mock_client

            client = await adapter._ensure_client()
            assert client == mock_client

    async def test_embed_texts_success(self, openai_adapter, mock_openai_response):
        """Test successful text embedding."""
        adapter, mock_client = openai_adapter
        mock_client.embeddings.create = AsyncMock(return_value=mock_openai_response)

        texts = ["Hello world", "How are you?"]
        batch = await adapter._embed_texts(
            texts=texts,
            model="text-embedding-3-small",
            normalize=True,
            batch_size=10,
        )

        assert isinstance(batch, EmbeddingBatch)
        assert len(batch.results) == 2
        assert batch.model == "text-embedding-3-small"
        assert batch.total_tokens == 15

        # Check individual results
        for i, result in enumerate(batch.results):
            assert result.text == texts[i]
            assert len(result.embedding) == 384  # 3 * 128
            assert result.model == "text-embedding-3-small"
            assert result.dimensions == 384

    async def test_embed_texts_with_dimensions(
        self, openai_adapter, mock_openai_response
    ):
        """Test text embedding with custom dimensions."""
        adapter, mock_client = openai_adapter
        adapter._settings.dimensions = 256
        mock_client.embeddings.create = AsyncMock(return_value=mock_openai_response)

        texts = ["Test text"]
        await adapter._embed_texts(
            texts=texts,
            model="text-embedding-3-large",
            normalize=False,
            batch_size=1,
        )

        # Check that dimensions parameter was passed
        mock_client.embeddings.create.assert_called_once()
        call_args = mock_client.embeddings.create.call_args[1]
        assert call_args["dimensions"] == 256

    async def test_embed_documents(self, openai_adapter, mock_openai_response):
        """Test document embedding with chunking."""
        adapter, mock_client = openai_adapter
        mock_client.embeddings.create = AsyncMock(return_value=mock_openai_response)

        documents = ["This is a long document that should be chunked. " * 20]
        batches = await adapter._embed_documents(
            documents=documents,
            chunk_size=100,
            chunk_overlap=20,
            model="text-embedding-3-small",
        )

        assert len(batches) == 1
        batch = batches[0]
        assert len(batch.results) > 1  # Should be chunked

        # Check metadata
        for result in batch.results:
            assert result.metadata["is_chunk"] is True
            assert "document_id" in result.metadata

    async def test_compute_similarity(self, openai_adapter):
        """Test similarity computation."""
        adapter, _ = openai_adapter

        embedding1 = [1.0, 0.0, 0.0]
        embedding2 = [0.0, 1.0, 0.0]

        # Test cosine similarity
        similarity = await adapter._compute_similarity(embedding1, embedding2, "cosine")
        assert similarity == 0.0  # Orthogonal vectors

        # Test dot product
        dot = await adapter._compute_similarity(embedding1, embedding2, "dot")
        assert dot == 0.0

        # Test unsupported method
        with pytest.raises(ValueError, match="Unsupported similarity method"):
            await adapter._compute_similarity(embedding1, embedding2, "unsupported")

    async def test_get_model_info(self, openai_adapter):
        """Test getting model information."""
        adapter, _ = openai_adapter

        # Test text-embedding-3-small
        info = await adapter._get_model_info("text-embedding-3-small")
        assert info["name"] == "text-embedding-3-small"
        assert info["provider"] == "openai"
        assert info["max_dimensions"] == 1536
        assert "price_per_1k_tokens" in info

        # Test text-embedding-3-large
        info_large = await adapter._get_model_info("text-embedding-3-large")
        assert info_large["max_dimensions"] == 3072

    async def test_list_models(self, openai_adapter):
        """Test listing available models."""
        adapter, _ = openai_adapter

        models = await adapter._list_models()
        assert isinstance(models, list)
        assert len(models) == 3  # Three OpenAI models

        model_names = [model["name"] for model in models]
        assert "text-embedding-3-small" in model_names
        assert "text-embedding-3-large" in model_names
        assert "text-embedding-ada-002" in model_names

    async def test_rate_limiting(self, openai_adapter):
        """Test rate limiting functionality."""
        adapter, _ = openai_adapter
        adapter._settings.requests_per_minute = 60  # 1 request per second

        # First call should go through immediately
        start_time = asyncio.get_event_loop().time()
        await adapter._apply_rate_limit()
        asyncio.get_event_loop().time() - start_time

        # Second call should be rate limited
        start_time = asyncio.get_event_loop().time()
        await adapter._apply_rate_limit()
        second_call_time = asyncio.get_event_loop().time() - start_time

        # Second call should take at least 1 second due to rate limiting
        assert second_call_time >= 0.9  # Allow some tolerance

    async def test_health_check_success(self, openai_adapter, mock_openai_response):
        """Test successful health check."""
        adapter, mock_client = openai_adapter
        mock_client.embeddings.create = AsyncMock(return_value=mock_openai_response)

        health = await adapter.health_check()

        assert health["status"] == "healthy"
        assert health["provider"] == "openai"
        assert health["model"] == "text-embedding-3-small"
        assert "timestamp" in health

    async def test_health_check_failure(self, openai_adapter):
        """Test health check failure."""
        adapter, mock_client = openai_adapter
        mock_client.embeddings.create = AsyncMock(side_effect=Exception("API Error"))

        health = await adapter.health_check()

        assert health["status"] == "unhealthy"
        assert health["provider"] == "openai"
        assert "error" in health
        assert "timestamp" in health

    async def test_error_handling(self, openai_adapter):
        """Test error handling during embedding generation."""
        adapter, mock_client = openai_adapter
        mock_client.embeddings.create = AsyncMock(side_effect=Exception("API Error"))

        with pytest.raises(Exception, match="API Error"):
            await adapter._embed_texts(
                texts=["test"],
                model="text-embedding-3-small",
                normalize=True,
                batch_size=1,
            )

    async def test_cleanup(self, openai_adapter):
        """Test adapter cleanup."""
        adapter, mock_client = openai_adapter
        mock_client.close = AsyncMock()

        await adapter.cleanup()

        # Client should be cleaned up
        assert adapter._client is None

    async def test_batch_processing(self, openai_adapter, mock_openai_response):
        """Test batch processing with large number of texts."""
        adapter, mock_client = openai_adapter
        mock_client.embeddings.create = AsyncMock(return_value=mock_openai_response)

        # Create more texts than batch size
        texts = [f"Text {i}" for i in range(25)]
        batch = await adapter._embed_texts(
            texts=texts,
            model="text-embedding-3-small",
            normalize=True,
            batch_size=10,
        )

        # Should process all texts
        assert len(batch.results) == 25

        # Should make multiple API calls due to batching
        assert mock_client.embeddings.create.call_count > 1


@pytest.mark.asyncio
class TestOpenAIEmbeddingSettings:
    """Test cases for OpenAI embedding settings."""

    def test_settings_defaults(self):
        """Test default settings values."""
        settings = OpenAIEmbeddingSettings(api_key="test-key")

        assert settings.model == "text-embedding-3-small"
        assert settings.base_url == "https://api.openai.com/v1"
        assert settings.max_retries == 3
        assert settings.timeout == 30.0
        assert settings.batch_size == 100
        assert settings.encoding_format == "float"

    def test_settings_custom_values(self):
        """Test custom settings values."""
        settings = OpenAIEmbeddingSettings(
            api_key="custom-key",
            model="text-embedding-3-large",
            base_url="https://custom.openai.com/v1",
            batch_size=50,
            dimensions=256,
        )

        assert settings.api_key.get_secret_value() == "custom-key"
        assert settings.model == "text-embedding-3-large"
        assert settings.base_url == "https://custom.openai.com/v1"
        assert settings.batch_size == 50
        assert settings.dimensions == 256

    def test_environment_prefix(self):
        """Test environment variable prefix."""
        assert OpenAIEmbeddingSettings.Config.env_prefix == "OPENAI_"
