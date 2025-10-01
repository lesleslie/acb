"""HuggingFace transformers embeddings adapter implementation."""

import asyncio
import time
import typing as t
from contextlib import suppress
from datetime import datetime

import torch
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
    EmbeddingResult,
    EmbeddingUtils,
    PoolingStrategy,
)
from acb.config import Config
from acb.depends import depends

if t.TYPE_CHECKING:
    pass

try:
    import torch.nn.functional as F
    from transformers import AutoModel, AutoTokenizer, BatchEncoding

    _transformers_available = True
except ImportError:
    AutoModel = None  # type: ignore[assignment,misc]
    AutoTokenizer = None  # type: ignore[assignment,misc]
    BatchEncoding = None  # type: ignore[assignment,misc]
    F = None
    _transformers_available = False

MODULE_METADATA = AdapterMetadata(
    module_id=generate_adapter_id(),
    name="HuggingFace Transformers Embeddings",
    category="embedding",
    provider="huggingface",
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
        AdapterCapability.POOLING_STRATEGIES,
        AdapterCapability.MODEL_CACHING,
    ],
    required_packages=["transformers>=4.0.0", "torch>=2.0.0"],
    description="HuggingFace transformers embeddings adapter with local model support and edge optimization",
    settings_class="HuggingFaceEmbeddingSettings",
)


class HuggingFaceEmbeddingSettings(EmbeddingBaseSettings):
    """HuggingFace-specific embedding settings."""

    model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    device: str = Field(
        default="auto",
        description="Device to run model on (cpu, cuda, auto)",
    )
    trust_remote_code: bool = Field(default=False)
    cache_dir: str | None = Field(default=None, description="Model cache directory")
    local_files_only: bool = Field(default=False)
    revision: str = Field(default="main")

    # Model optimization
    use_auth_token: str | None = Field(default=None)
    torch_dtype: str = Field(
        default="auto",
        description="Torch data type (float32, float16, auto)",
    )
    model_kwargs: dict[str, t.Any] = Field(default_factory=dict)
    tokenizer_kwargs: dict[str, t.Any] = Field(default_factory=dict)

    # Processing settings
    max_seq_length: int = Field(default=512)
    pooling_strategy: PoolingStrategy = Field(default=PoolingStrategy.MEAN)
    batch_size: int = Field(default=16)  # Smaller batch size for memory efficiency

    # Edge optimization
    enable_quantization: bool = Field(default=False)
    enable_optimization: bool = Field(default=True)
    gradient_checkpointing: bool = Field(default=False)

    class Config:
        env_prefix = "HUGGINGFACE_"


class HuggingFaceEmbedding(EmbeddingAdapter):
    """HuggingFace transformers embeddings adapter implementation."""

    def __init__(self, settings: HuggingFaceEmbeddingSettings | None = None) -> None:
        if not _transformers_available:
            msg = "Transformers library not available. Install with: pip install transformers torch"
            raise ImportError(
                msg,
            )

        if settings is None:
            settings = HuggingFaceEmbeddingSettings()

        super().__init__(settings)
        self._settings: HuggingFaceEmbeddingSettings = settings
        self._model: t.Any = None
        self._tokenizer: t.Any = None
        self._device: str | None = None

    async def _ensure_client(self) -> tuple[t.Any, t.Any]:
        """Ensure model and tokenizer are loaded."""
        if self._model is None or self._tokenizer is None:
            await self._load_model()

        return self._model, self._tokenizer

    async def _load_model(self) -> None:
        """Load the HuggingFace model and tokenizer."""
        logger: t.Any = depends.get("logger")

        try:
            # Determine device
            if self._settings.device == "auto":
                self._device = "cuda" if torch.cuda.is_available() else "cpu"
            else:
                self._device = self._settings.device

            await logger.info(
                f"Loading HuggingFace model: {self._settings.model} on {self._device}",
            )

            # Load tokenizer
            tokenizer_kwargs = {
                "trust_remote_code": self._settings.trust_remote_code,
                "revision": self._settings.revision,
                "cache_dir": self._settings.cache_dir,
                "local_files_only": self._settings.local_files_only,
                **self._settings.tokenizer_kwargs,
            }

            if self._settings.use_auth_token:
                tokenizer_kwargs["use_auth_token"] = self._settings.use_auth_token

            if AutoTokenizer is None:
                msg = "AutoTokenizer not available"
                raise ImportError(msg)

            self._tokenizer = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: AutoTokenizer.from_pretrained(  # type: ignore[no-untyped-call]
                    self._settings.model,
                    revision="main",  # nosec B615
                    **tokenizer_kwargs,
                ),
            )

            # Load model
            model_kwargs = {
                "trust_remote_code": self._settings.trust_remote_code,
                "revision": self._settings.revision,
                "cache_dir": self._settings.cache_dir,
                "local_files_only": self._settings.local_files_only,
                **self._settings.model_kwargs,
            }

            if self._settings.use_auth_token:
                model_kwargs["use_auth_token"] = self._settings.use_auth_token

            # Set torch dtype
            if self._settings.torch_dtype != "auto":
                if self._settings.torch_dtype == "float16":
                    model_kwargs["torch_dtype"] = torch.float16
                elif self._settings.torch_dtype == "float32":
                    model_kwargs["torch_dtype"] = torch.float32

            if AutoModel is None:
                msg = "AutoModel not available"
                raise ImportError(msg)

            self._model = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: AutoModel.from_pretrained(
                    self._settings.model,
                    revision="main",  # nosec B615
                    **model_kwargs,
                ),
            )

            # Move model to device and set to eval mode
            if self._model is not None:
                self._model.to(self._device)
                self._model.eval()

            # Enable optimizations
            if self._settings.enable_optimization:
                if hasattr(torch, "jit") and hasattr(torch.jit, "script"):
                    with suppress(Exception):
                        # Try to optimize with TorchScript (may not work for all models)
                        self._model = torch.jit.script(self._model)

            # Register for cleanup
            self.register_resource(self._model)

            await logger.info(
                f"Successfully loaded HuggingFace model: {self._settings.model}",
            )

        except Exception as e:
            await logger.exception(f"Error loading HuggingFace model: {e}")
            raise

    async def _embed_texts(
        self,
        texts: list[str],
        model: str,
        normalize: bool,
        batch_size: int,
        **kwargs: t.Any,
    ) -> EmbeddingBatch:
        """Generate embeddings for multiple texts using HuggingFace."""
        start_time = time.time()
        model_obj, tokenizer = await self._ensure_client()
        logger: t.Any = depends.get("logger")

        results = []

        # Process texts in batches
        batches = self._batch_texts(texts, batch_size)

        for batch_texts in batches:
            try:
                # Tokenize batch
                inputs = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: tokenizer(
                        batch_texts,
                        padding=True,
                        truncation=True,
                        max_length=self._settings.max_seq_length,
                        return_tensors="pt",
                    ),
                )

                # Move to device
                inputs = {k: v.to(self._device) for k, v in inputs.items()}

                # Generate embeddings
                with torch.no_grad():
                    outputs = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: model_obj(**inputs),
                    )

                # Apply pooling strategy
                embeddings = await self._apply_pooling(
                    outputs.last_hidden_state,
                    inputs["attention_mask"],
                    self._settings.pooling_strategy,
                )

                # Normalize if requested
                if normalize:
                    embeddings = F.normalize(embeddings, p=2, dim=1)

                # Convert to list format
                embeddings_list = embeddings.cpu().tolist()

                # Create results
                for i, embedding in enumerate(embeddings_list):
                    result = EmbeddingResult(
                        text=batch_texts[i],
                        embedding=embedding,
                        model=model,
                        dimensions=len(embedding),
                        tokens=len(tokenizer.encode(batch_texts[i])),
                        metadata={
                            "pooling_strategy": self._settings.pooling_strategy.value,
                            "device": self._device,
                            "max_seq_length": self._settings.max_seq_length,
                        },
                    )
                    results.append(result)

                await logger.debug(
                    f"HuggingFace embeddings batch completed: {len(batch_texts)} texts, model: {model}",
                )

            except Exception as e:
                await logger.exception(f"Error generating HuggingFace embeddings: {e}")
                raise

        processing_time = time.time() - start_time
        total_tokens = sum(result.tokens or 0 for result in results)

        return EmbeddingBatch(
            results=results,
            total_tokens=total_tokens if total_tokens > 0 else None,
            processing_time=processing_time,
            model=model,
            batch_size=len(results),
        )

    async def _apply_pooling(
        self,
        token_embeddings: torch.Tensor,
        attention_mask: torch.Tensor,
        strategy: PoolingStrategy,
    ) -> torch.Tensor:
        """Apply pooling strategy to token embeddings."""
        if strategy == PoolingStrategy.MEAN:
            # Mean pooling with attention mask
            input_mask_expanded = (
                attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
            )
            sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
            sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
            return sum_embeddings / sum_mask

        if strategy == PoolingStrategy.MAX:
            # Max pooling
            input_mask_expanded = (
                attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
            )
            token_embeddings[
                input_mask_expanded == 0
            ] = -1e9  # Set padding tokens to large negative value
            return torch.max(token_embeddings, 1)[0]

        if strategy == PoolingStrategy.CLS:
            # CLS token pooling (first token)
            return token_embeddings[:, 0]

        if strategy == PoolingStrategy.WEIGHTED_MEAN:
            # Weighted mean (simple implementation)
            weights = attention_mask.float().unsqueeze(-1)
            weighted_embeddings = token_embeddings * weights
            sum_embeddings = torch.sum(weighted_embeddings, 1)
            sum_weights = torch.sum(weights, 1)
            return sum_embeddings / torch.clamp(sum_weights, min=1e-9)

        msg = f"Unsupported pooling strategy: {strategy}"
        raise ValueError(msg)

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
        """Get information about a HuggingFace model."""
        model_info = {
            "name": model,
            "provider": "huggingface",
            "type": "embedding",
            "device": self._device,
            "local": True,
        }

        if self._model and self._tokenizer:
            model_info.update(
                {
                    "vocab_size": self._tokenizer.vocab_size,
                    "max_position_embeddings": getattr(
                        self._model.config,
                        "max_position_embeddings",
                        None,
                    ),
                    "hidden_size": getattr(self._model.config, "hidden_size", None),
                    "num_attention_heads": getattr(
                        self._model.config,
                        "num_attention_heads",
                        None,
                    ),
                    "num_hidden_layers": getattr(
                        self._model.config,
                        "num_hidden_layers",
                        None,
                    ),
                },
            )

        return model_info

    async def _list_models(self) -> list[dict[str, t.Any]]:
        """List commonly used HuggingFace embedding models."""
        models = [
            "sentence-transformers/all-MiniLM-L6-v2",
            "sentence-transformers/all-mpnet-base-v2",
            "sentence-transformers/multi-qa-mpnet-base-dot-v1",
            "sentence-transformers/all-distilroberta-v1",
            "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
            "microsoft/DialoGPT-medium",
            "distilbert-base-uncased",
            "bert-base-uncased",
        ]

        return [
            {"name": model, "provider": "huggingface", "type": "embedding"}
            for model in models
        ]

    async def health_check(self) -> dict[str, t.Any]:
        """Perform health check on HuggingFace embeddings service."""
        try:
            # Test with a simple embedding request
            test_result = await self.embed_text("health check test")

            return {
                "status": "healthy",
                "provider": "huggingface",
                "model": self._settings.model,
                "device": self._device,
                "dimensions": len(test_result),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "provider": "huggingface",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    async def cleanup(self) -> None:
        """Clean up model and tokenizer resources."""
        if self._model is not None:
            del self._model
            self._model = None

        if self._tokenizer is not None:
            del self._tokenizer
            self._tokenizer = None

        # Clear CUDA cache if using GPU
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        await super().cleanup()


# Factory function for dependency injection
async def create_huggingface_embedding(
    config: Config | None = None,
) -> HuggingFaceEmbedding:
    """Create HuggingFace embedding adapter instance."""
    if config is None:
        config = depends.get("config")

    settings = HuggingFaceEmbeddingSettings()
    return HuggingFaceEmbedding(settings)


# Type alias
Embedding = HuggingFaceEmbedding
