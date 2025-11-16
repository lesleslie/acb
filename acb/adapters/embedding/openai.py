"""OpenAI embeddings adapter implementation."""

import time

import asyncio
import typing as t
from datetime import datetime
from pydantic import Field

from acb.adapters import (
    AdapterCapability,
    AdapterMetadata,
    AdapterStatus,
    generate_adapter_id,
)
from acb.adapters.embedding._base import (
    EmbeddingAdapter,
    EmbeddingBaseSettings,
    EmbeddingBatch,
    EmbeddingModel,
    EmbeddingResult,
    EmbeddingUtils,
)
from acb.config import Config
from acb.depends import depends

if t.TYPE_CHECKING:
    from openai import AsyncOpenAI
else:
    try:
        from openai import AsyncOpenAI  # type: ignore[no-redef]

        _openai_available = True
    except ImportError:
        AsyncOpenAI = None  # type: ignore[assignment,misc,no-redef]
        _openai_available = False

MODULE_METADATA = AdapterMetadata(
    module_id=generate_adapter_id(),
    name="OpenAI Embeddings",
    category="embedding",
    provider="openai",
    version="1.0.0",
    acb_min_version="0.19.0",
    author="ACB Development Team",
    created_date="2025-09-30",
    last_modified="2025-09-30",
    status=AdapterStatus.STABLE,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.BATCHING,
        AdapterCapability.CACHING,
        AdapterCapability.TLS_SUPPORT,
        AdapterCapability.METRICS,
        AdapterCapability.BATCH_EMBEDDING,
        AdapterCapability.VECTOR_NORMALIZATION,
        AdapterCapability.TEXT_PREPROCESSING,
    ],
    required_packages=["openai>=1.0.0"],
    description="High-performance OpenAI embeddings adapter with batch processing and caching",
    settings_class="OpenAIEmbeddingSettings",
)


class OpenAIEmbeddingSettings(EmbeddingBaseSettings):
    """OpenAI-specific embedding settings."""

    # OpenAI-specific settings
    organization: str | None = Field(default=None, description="OpenAI organization ID")
    dimensions: int | None = Field(
        default=None,
        description="Embedding dimensions (for v3 models)",
    )
    encoding_format: str = Field(
        default="float",
        description="Encoding format (float or base64)",
    )

    # Rate limiting
    requests_per_minute: int = Field(default=3000)
    tokens_per_minute: int = Field(default=1000000)

    # Override base settings defaults
    model: str = Field(default=EmbeddingModel.TEXT_EMBEDDING_3_SMALL.value)
    batch_size: int = Field(default=100)  # OpenAI supports up to 2048 inputs

    class Config:
        env_prefix = "OPENAI_"


class OpenAIEmbedding(EmbeddingAdapter):
    """OpenAI embeddings adapter implementation."""

    def __init__(self, settings: OpenAIEmbeddingSettings | None = None) -> None:
        if not _openai_available:
            msg = "OpenAI library not available. Install with: pip install openai"
            raise ImportError(
                msg,
            )

        if settings is None:
            settings = OpenAIEmbeddingSettings()

        super().__init__(settings)
        self._settings = settings
        self._client: t.Any = None
        self._rate_limiter = None
        self._last_request_time = 0.0

    async def _ensure_client(self) -> t.Any:
        """Ensure OpenAI client is initialized."""
        if self._client is None:
            if AsyncOpenAI is None:
                msg = "OpenAI library not available"
                raise ImportError(msg)
            # Cast settings to access OpenAI-specific fields
            settings = t.cast(OpenAIEmbeddingSettings, self._settings)
            self._client = AsyncOpenAI(  # type: ignore[assignment]
                api_key=self._settings.api_key.get_secret_value()
                if self._settings.api_key
                else "",
                organization=settings.organization,
                base_url=self._settings.base_url,
                timeout=self._settings.timeout,
                max_retries=self._settings.max_retries,
            )
            self.register_resource(self._client)

        return self._client

    async def _embed_texts(
        self,
        texts: list[str],
        model: str,
        normalize: bool,
        batch_size: int,
        **kwargs: t.Any,
    ) -> EmbeddingBatch:
        """Generate embeddings for multiple texts using OpenAI."""
        start_time = time.time()
        client = await self._ensure_client()
        logger: t.Any = depends.get("logger")

        results = []
        total_tokens = 0

        # Process texts in batches
        batches = self._batch_texts(texts, batch_size)

        for batch_texts in batches:
            try:
                await self._apply_rate_limit()

                # Process single batch
                batch_results, batch_tokens = await self._process_embedding_batch(
                    client,
                    batch_texts,
                    model,
                    normalize,
                )

                results.extend(batch_results)
                total_tokens += batch_tokens

                await logger.debug(
                    f"OpenAI embeddings batch completed: {len(batch_texts)} texts, model: {model}",
                )

            except Exception as e:
                await logger.exception(f"Error generating OpenAI embeddings: {e}")
                raise

        processing_time = time.time() - start_time

        return EmbeddingBatch(
            results=results,
            total_tokens=total_tokens if total_tokens > 0 else None,
            processing_time=processing_time,
            model=model,
            batch_size=len(results),
        )

    async def _process_embedding_batch(
        self,
        client: t.Any,
        batch_texts: list[str],
        model: str,
        normalize: bool,
    ) -> tuple[list[EmbeddingResult], int]:
        """Process a single batch of embeddings.

        Args:
            client: OpenAI client instance
            batch_texts: Texts to embed
            model: Model name
            normalize: Whether to normalize vectors

        Returns:
            Tuple of (embedding results, token count)
        """
        # Prepare and execute API request
        request_params = self._prepare_request_params(batch_texts, model)
        response: t.Any = await client.embeddings.create(**request_params)

        # Process response data
        results = self._extract_embedding_results(
            response,
            batch_texts,
            normalize,
        )

        # Extract token usage
        tokens = (
            response.usage.total_tokens
            if hasattr(response, "usage") and response.usage
            else 0
        )

        return results, tokens

    def _prepare_request_params(
        self,
        batch_texts: list[str],
        model: str,
    ) -> dict[str, t.Any]:
        """Prepare OpenAI API request parameters.

        Args:
            batch_texts: Texts to embed
            model: Model name

        Returns:
            Request parameters dictionary
        """
        settings = t.cast(OpenAIEmbeddingSettings, self._settings)
        request_params: dict[str, t.Any] = {
            "input": batch_texts,
            "model": model,
            "encoding_format": settings.encoding_format,
        }

        # Add dimensions for v3 models
        if settings.dimensions and model.startswith("text-embedding-3"):
            request_params["dimensions"] = settings.dimensions

        return request_params

    def _extract_embedding_results(
        self,
        response: t.Any,
        batch_texts: list[str],
        normalize: bool,
    ) -> list[EmbeddingResult]:
        """Extract embedding results from API response.

        Args:
            response: OpenAI API response
            batch_texts: Original texts
            normalize: Whether to normalize vectors

        Returns:
            List of embedding results
        """
        results = []

        for i, embedding_data in enumerate(response.data):
            embedding = embedding_data.embedding

            # Normalize if requested
            if normalize:
                embedding = self._normalize_vector(
                    embedding,
                    self._settings.normalization,
                )

            result = EmbeddingResult(
                text=batch_texts[i],
                embedding=embedding,
                model=response.model,
                dimensions=len(embedding),
                tokens=None,  # OpenAI doesn't provide token count per text
                metadata={
                    "index": embedding_data.index,
                    "object": embedding_data.object,
                },
            )
            results.append(result)

        return results

    async def _embed_documents(
        self,
        documents: list[str],
        chunk_size: int,
        chunk_overlap: int,
        model: str,
        **kwargs: t.Any,
    ) -> list[EmbeddingBatch]:
        """Embed large documents with chunking."""
        batches = []

        for document in documents:
            # Split document into chunks
            chunks = self._chunk_text(document, chunk_size, chunk_overlap)

            # Generate embeddings for chunks
            batch = await self._embed_texts(
                chunks,
                model=model,
                normalize=self._settings.normalize_embeddings,
                batch_size=self._settings.batch_size,
                **kwargs,
            )

            # Add document metadata
            for result in batch.results:
                result.metadata.update(
                    {
                        "document_id": hash(document),
                        "is_chunk": True,
                        "chunk_size": chunk_size,
                        "chunk_overlap": chunk_overlap,
                    },
                )

            batches.append(batch)

        return batches

    async def _compute_similarity(
        self,
        embedding1: list[float],
        embedding2: list[float],
        method: str,
    ) -> float:
        """Compute similarity between two embeddings."""
        if method == "cosine":
            return EmbeddingUtils.cosine_similarity(embedding1, embedding2)
        if method == "euclidean":
            return EmbeddingUtils.euclidean_distance(embedding1, embedding2)
        if method == "dot":
            return EmbeddingUtils.dot_product(embedding1, embedding2)
        if method == "manhattan":
            return EmbeddingUtils.manhattan_distance(embedding1, embedding2)
        msg = f"Unsupported similarity method: {method}"
        raise ValueError(msg)

    async def _get_model_info(self, model: str) -> dict[str, t.Any]:
        """Get information about an OpenAI embedding model."""
        model_info: dict[str, t.Any] = {
            "name": model,
            "provider": "openai",
            "type": "embedding",
        }

        # Add model-specific information
        if model == EmbeddingModel.TEXT_EMBEDDING_3_SMALL.value:
            model_info.update(
                {
                    "max_dimensions": 1536,
                    "default_dimensions": 1536,
                    "max_tokens": 8191,
                    "price_per_1k_tokens": 0.00002,
                    "description": "Most efficient embedding model with good performance",
                },
            )
        elif model == EmbeddingModel.TEXT_EMBEDDING_3_LARGE.value:
            model_info.update(
                {
                    "max_dimensions": 3072,
                    "default_dimensions": 3072,
                    "max_tokens": 8191,
                    "price_per_1k_tokens": 0.00013,
                    "description": "Most powerful embedding model with highest accuracy",
                },
            )
        elif model == EmbeddingModel.TEXT_EMBEDDING_ADA_002.value:
            model_info.update(
                {
                    "max_dimensions": 1536,
                    "default_dimensions": 1536,
                    "max_tokens": 8191,
                    "price_per_1k_tokens": 0.0001,
                    "description": "Legacy embedding model (v2)",
                },
            )

        return model_info

    async def _list_models(self) -> list[dict[str, t.Any]]:
        """List available OpenAI embedding models."""
        models = [
            EmbeddingModel.TEXT_EMBEDDING_3_SMALL.value,
            EmbeddingModel.TEXT_EMBEDDING_3_LARGE.value,
            EmbeddingModel.TEXT_EMBEDDING_ADA_002.value,
        ]

        return [await self._get_model_info(model) for model in models]

    async def _apply_rate_limit(self) -> None:
        """Apply rate limiting to API requests."""
        settings = t.cast(OpenAIEmbeddingSettings, self._settings)
        current_time = time.time()
        time_since_last = current_time - self._last_request_time

        # Simple rate limiting - ensure minimum time between requests
        min_interval = 60.0 / settings.requests_per_minute
        if time_since_last < min_interval:
            await asyncio.sleep(min_interval - time_since_last)

        self._last_request_time = time.time()

    async def health_check(self) -> dict[str, t.Any]:
        """Perform health check on OpenAI embeddings service."""
        try:
            # Test with a simple embedding request
            test_result = await self.embed_text("health check test")

            return {
                "status": "healthy",
                "provider": "openai",
                "model": self._settings.model,
                "dimensions": len(test_result),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "provider": "openai",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }


# Factory function for dependency injection
async def create_openai_embedding(config: Config | None = None) -> OpenAIEmbedding:
    """Create OpenAI embedding adapter instance."""
    if config is None:
        config = await depends.get("config")

    settings = OpenAIEmbeddingSettings()
    return OpenAIEmbedding(settings)


# Type alias
Embedding = OpenAIEmbedding
EmbeddingSettings = OpenAIEmbeddingSettings

depends.set(Embedding, "openai")
