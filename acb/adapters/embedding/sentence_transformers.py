"""Sentence Transformers embeddings adapter implementation."""

# Avoid static imports of optional heavy dependencies; detect availability
import importlib.util as _il_util
import time
from operator import itemgetter

import asyncio
import typing as t
from contextlib import suppress
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

SentenceTransformer = t.cast("t.Any", None)
_sentence_transformers_available = (
    _il_util.find_spec("sentence_transformers") is not None
)

MODULE_METADATA = AdapterMetadata(
    module_id=generate_adapter_id(),
    name="Sentence Transformers Embeddings",
    category="embedding",
    provider="sentence_transformers",
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
        AdapterCapability.STREAMING,
        AdapterCapability.METRICS,
        AdapterCapability.BATCH_EMBEDDING,
        AdapterCapability.EDGE_OPTIMIZED,
        AdapterCapability.SEMANTIC_SEARCH,
        AdapterCapability.SIMILARITY_COMPUTATION,
        AdapterCapability.POOLING_STRATEGIES,
        AdapterCapability.MEMORY_EFFICIENT_PROCESSING,
    ],
    required_packages=["sentence-transformers>=2.0.0", "torch>=2.0.0"],
    description="Sentence Transformers embeddings adapter optimized for semantic similarity and retrieval",
    settings_class="SentenceTransformersSettings",
)


class SentenceTransformersSettings(EmbeddingBaseSettings):
    """Sentence Transformers-specific embedding settings."""

    model: str = Field(default=EmbeddingModel.ALL_MINILM_L6_V2.value)
    device: str = Field(
        default="auto",
        description="Device to run model on (cpu, cuda, auto)",
    )
    cache_folder: str | None = Field(default=None, description="Model cache directory")
    use_auth_token: str | None = Field(default=None)
    revision: str | None = Field(default=None)
    trust_remote_code: bool = Field(default=False)

    # Model optimization
    normalize_embeddings: bool = Field(default=True)
    convert_to_numpy: bool = Field(default=True)
    convert_to_tensor: bool = Field(default=False)
    show_progress_bar: bool = Field(default=False)

    # Batch processing
    batch_size: int = Field(default=32)
    precision: str = Field(
        default="float32",
        description="Model precision (float32, float16)",
    )

    # Edge optimization
    enable_quantization: bool = Field(default=False)
    memory_efficient: bool = Field(default=True)

    model_config = {
        "env_prefix": "SENTENCE_TRANSFORMERS_",
    }


class SentenceTransformersEmbedding(EmbeddingAdapter):
    """Sentence Transformers embeddings adapter implementation."""

    def __init__(self, settings: SentenceTransformersSettings | None = None) -> None:
        if not _sentence_transformers_available:
            msg = "Sentence Transformers library not available. Install with: pip install sentence-transformers"
            raise ImportError(
                msg,
            )

        depends.get_sync("config")
        if settings is None:
            settings = SentenceTransformersSettings()

        super().__init__(settings)
        self._settings: SentenceTransformersSettings = settings
        self._model: t.Any | None = None
        self._device: str | None = None

    async def _ensure_client(self) -> t.Any:
        """Ensure Sentence Transformer model is loaded."""
        if self._model is None:
            await self._load_model()

        return self._model

    async def _load_model(self) -> None:
        """Load the Sentence Transformer model."""
        logger: t.Any = depends.get("logger")

        try:
            # Import dependencies dynamically to avoid static type errors
            import importlib

            torch = importlib.import_module("torch")  # type: ignore[assignment]
            st_mod = importlib.import_module("sentence_transformers")
            STClass = st_mod.SentenceTransformer

            # Determine device
            if self._settings.device == "auto":
                self._device = "cuda" if torch.cuda.is_available() else "cpu"
            else:
                self._device = self._settings.device

            await logger.info(
                f"Loading Sentence Transformer model: {self._settings.model} on {self._device}",
            )

            # Load model
            model_kwargs = {
                "device": self._device,
                "cache_folder": self._settings.cache_folder,
                "use_auth_token": self._settings.use_auth_token,
                "revision": self._settings.revision,
                "trust_remote_code": self._settings.trust_remote_code,
            }

            # Remove None values
            model_kwargs = {k: v for k, v in model_kwargs.items() if v is not None}

            self._model = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: STClass(self._settings.model, **model_kwargs),
            )

            # Apply optimizations
            if (
                self._settings.precision == "float16"
                and self._device == "cuda"
                and self._model is not None
            ):
                self._model.half()

            # Register for cleanup
            self.register_resource(self._model)

            await logger.info(
                f"Successfully loaded Sentence Transformer model: {self._settings.model}",
            )

        except Exception as e:
            await logger.exception(f"Error loading Sentence Transformer model: {e}")
            raise

    async def _embed_texts(
        self,
        texts: list[str],
        model: str,
        normalize: bool,
        batch_size: int,
        **kwargs: t.Any,
    ) -> EmbeddingBatch:
        """Generate embeddings for multiple texts using Sentence Transformers."""
        start_time = time.time()
        model_obj = await self._ensure_client()
        logger: t.Any = depends.get("logger")

        try:
            # Generate embeddings
            embeddings = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: model_obj.encode(
                    texts,
                    batch_size=batch_size,
                    show_progress_bar=self._settings.show_progress_bar,
                    normalize_embeddings=normalize,
                    convert_to_numpy=self._settings.convert_to_numpy,
                    convert_to_tensor=self._settings.convert_to_tensor,
                ),
            )

            # Convert to list format if numpy
            if hasattr(embeddings, "tolist"):
                embeddings_list = embeddings.tolist()
            else:
                embeddings_list = embeddings

            # Create results
            results = []
            for _i, (text, embedding) in enumerate(
                zip(texts, embeddings_list, strict=False),
            ):
                result = EmbeddingResult(
                    text=text,
                    embedding=embedding,
                    model=model,
                    dimensions=len(embedding),
                    tokens=None,  # Sentence Transformers doesn't provide token count
                    metadata={
                        "device": self._device,
                        "precision": self._settings.precision,
                        "normalized": normalize,
                    },
                )
                results.append(result)

            processing_time = time.time() - start_time

            await logger.debug(
                f"Sentence Transformers embeddings completed: {len(texts)} texts, model: {model}",
            )

            return EmbeddingBatch(
                results=results,
                total_tokens=None,  # Not available
                processing_time=processing_time,
                model=model,
                batch_size=len(results),
            )

        except Exception as e:
            await logger.exception(
                f"Error generating Sentence Transformers embeddings: {e}",
            )
            raise

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

    async def similarity_search(
        self,
        query: str,
        documents: list[str],
        top_k: int = 5,
    ) -> list[tuple[str, float]]:
        """Perform semantic similarity search using the model's built-in capabilities."""
        model_obj = await self._ensure_client()

        # Generate embeddings
        query_embedding = await self.embed_text(query)
        doc_embeddings = await self.embed_texts(documents)

        # Compute similarities using Sentence Transformers utilities
        similarities = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: model_obj.similarity(
                [query_embedding],
                [result.embedding for result in doc_embeddings.results],
            ),
        )

        # Get top-k results
        if hasattr(similarities, "tolist"):
            similarities = similarities.tolist()[0]
        else:
            similarities = similarities[0]

        # Sort by similarity (descending)
        results = list(zip(documents, similarities, strict=False))
        results.sort(key=itemgetter(1), reverse=True)

        return results[:top_k]

    async def _get_model_info(self, model: str) -> dict[str, t.Any]:
        """Get information about a Sentence Transformer model."""
        model_info = {
            "name": model,
            "provider": "sentence_transformers",
            "type": "embedding",
            "device": self._device,
            "local": True,
        }

        if self._model:
            with suppress(Exception):
                # Some models may not have these attributes
                model_info.update(
                    {
                        "max_seq_length": self._model.max_seq_length,
                        "dimensions": self._model.get_sentence_embedding_dimension(),
                        "tokenizer": type(self._model.tokenizer).__name__
                        if hasattr(self._model, "tokenizer")
                        else None,
                    },
                )

        return model_info

    async def _list_models(self) -> list[dict[str, t.Any]]:
        """List popular Sentence Transformer models."""
        models = [
            {
                "name": "all-MiniLM-L6-v2",
                "description": "Lightweight model, good performance/speed tradeoff",
                "dimensions": 384,
                "size": "80MB",
            },
            {
                "name": "all-mpnet-base-v2",
                "description": "Best quality model for many tasks",
                "dimensions": 768,
                "size": "420MB",
            },
            {
                "name": "multi-qa-mpnet-base-dot-v1",
                "description": "Optimized for question-answering retrieval",
                "dimensions": 768,
                "size": "420MB",
            },
            {
                "name": "all-distilroberta-v1",
                "description": "Good balance of quality and speed",
                "dimensions": 768,
                "size": "290MB",
            },
            {
                "name": "paraphrase-multilingual-mpnet-base-v2",
                "description": "Multilingual model for 50+ languages",
                "dimensions": 768,
                "size": "970MB",
            },
        ]

        return [
            model_info
            | {
                "provider": "sentence_transformers",
                "type": "embedding",
            }
            for model_info in models
        ]

    async def health_check(self) -> dict[str, t.Any]:
        """Perform health check on Sentence Transformers service."""
        try:
            # Test with a simple embedding request
            test_result = await self.embed_text("health check test")

            return {
                "status": "healthy",
                "provider": "sentence_transformers",
                "model": self._settings.model,
                "device": self._device,
                "dimensions": len(test_result),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "provider": "sentence_transformers",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    async def cleanup(self) -> None:
        """Clean up model resources."""
        if self._model is not None:
            del self._model
            self._model = None

        # Clear CUDA cache if using GPU
        # Best effort GPU cache cleanup if available
        from contextlib import suppress as _suppress

        with _suppress(Exception):
            import importlib

            torch = importlib.import_module("torch")
            if torch and torch.cuda.is_available():  # type: ignore[truthy-bool]
                torch.cuda.empty_cache()

        await super().cleanup()


# Factory function for dependency injection
async def create_sentence_transformers_embedding(
    config: Config | None = None,
) -> SentenceTransformersEmbedding:
    """Create Sentence Transformers embedding adapter instance."""
    if config is None:
        config = await depends.get("config")

    settings = SentenceTransformersSettings()
    return SentenceTransformersEmbedding(settings)


# Type alias
Embedding = SentenceTransformersEmbedding
EmbeddingSettings = SentenceTransformersSettings

depends.set(Embedding, "sentence_transformers")
