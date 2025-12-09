"""ONNX Runtime embeddings adapter implementation for optimized inference."""

import time

import asyncio
import numpy as np
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
    EmbeddingResult,
    EmbeddingUtils,
    PoolingStrategy,
)
from acb.config import Config
from acb.depends import depends

try:
    import onnxruntime as ort

    from transformers import AutoTokenizer

    _onnx_available = True
except ImportError:
    ort = None
    AutoTokenizer = None  # type: ignore[assignment,misc,no-redef]
    _onnx_available = False

MODULE_METADATA = AdapterMetadata(
    module_id=generate_adapter_id(),
    name="ONNX Runtime Embeddings",
    category="embedding",
    provider="onnx",
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
        AdapterCapability.METRICS,
        AdapterCapability.BATCH_EMBEDDING,
        AdapterCapability.EDGE_OPTIMIZED,
        AdapterCapability.POOLING_STRATEGIES,
        AdapterCapability.MEMORY_EFFICIENT_PROCESSING,
        AdapterCapability.TEXT_PREPROCESSING,
        AdapterCapability.VECTOR_NORMALIZATION,
    ],
    required_packages=["onnxruntime>=1.16.0", "transformers>=4.0.0", "numpy>=1.24.0"],
    description="ONNX Runtime embeddings adapter for high-performance inference and edge deployment",
    settings_class="ONNXEmbeddingSettings",
)


class ONNXEmbeddingSettings(EmbeddingBaseSettings):
    """ONNX-specific embedding settings."""

    model_path: str = Field(description="Path to ONNX model file")
    tokenizer_name: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        description="HuggingFace tokenizer name",
    )
    providers: list[str] = Field(
        default_factory=lambda: ["CPUExecutionProvider"],
        description="ONNX execution providers",
    )

    # Model optimization
    enable_cpu_mem_arena: bool = Field(default=True)
    enable_mem_pattern: bool = Field(default=True)
    enable_profiling: bool = Field(default=False)
    inter_op_num_threads: int = Field(
        default=0,
        description="Number of threads for inter-op parallelism",
    )
    intra_op_num_threads: int = Field(
        default=0,
        description="Number of threads for intra-op parallelism",
    )

    # Processing settings
    max_seq_length: int = Field(default=512)
    pooling_strategy: PoolingStrategy = Field(default=PoolingStrategy.MEAN)
    batch_size: int = Field(default=32)

    # Edge optimization
    optimize_for_inference: bool = Field(default=True)
    enable_quantization: bool = Field(default=False)
    graph_optimization_level: str = Field(
        default="ORT_ENABLE_ALL",
        description="Graph optimization level",
    )

    model_config = {
        "env_prefix": "ONNX_",
    }


class ONNXEmbedding(EmbeddingAdapter):
    """ONNX Runtime embeddings adapter implementation."""

    def __init__(self, settings: ONNXEmbeddingSettings | None = None) -> None:
        if not _onnx_available:
            msg = "ONNX Runtime or transformers library not available. Install with: pip install onnxruntime transformers"
            raise ImportError(
                msg,
            )

        depends.get_sync("config")
        if settings is None:
            msg = "ONNXEmbeddingSettings must be provided with model_path"
            raise ValueError(msg)

        super().__init__(settings)
        self._settings: ONNXEmbeddingSettings = settings
        self._session: t.Any = None
        self._tokenizer: t.Any = None
        self._input_names: list[str] = []
        self._output_names: list[str] = []

    async def _ensure_client(self) -> tuple[t.Any, t.Any]:
        """Ensure ONNX session and tokenizer are initialized."""
        if self._session is None or self._tokenizer is None:
            await self._load_model()

        return self._session, self._tokenizer

    async def _load_model(self) -> None:
        """Load the ONNX model and tokenizer."""
        logger: t.Any = depends.get("logger")

        try:
            await logger.info(f"Loading ONNX model from: {self._settings.model_path}")

            # Load tokenizer
            await self._load_tokenizer()

            # Load and configure ONNX model
            await self._load_onnx_model(logger)

            await logger.info(
                f"Successfully loaded ONNX model with providers: {self._settings.providers}",
            )
            await logger.debug(
                f"Model inputs: {self._input_names}, outputs: {self._output_names}",
            )

        except Exception as e:
            await logger.exception(f"Error loading ONNX model: {e}")
            raise

    async def _load_tokenizer(self) -> None:
        """Load the tokenizer for the ONNX model."""
        if AutoTokenizer is None:
            msg = "AutoTokenizer not available"
            raise ImportError(msg)
        self._tokenizer = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: AutoTokenizer.from_pretrained(  # type: ignore[no-untyped-call]  # nosec B615
                self._settings.tokenizer_name,
                revision=getattr(self._settings, "tokenizer_revision", "main"),
            ),
        )

    async def _load_onnx_model(self, logger: t.Any) -> None:
        """Load and configure the ONNX model."""
        if ort is None:
            msg = "ONNX Runtime not available"
            raise ImportError(msg)

        session_options = await self._configure_session_options()

        # Create ONNX session
        self._session = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: ort.InferenceSession(
                self._settings.model_path,
                sess_options=session_options,
                providers=self._settings.providers,
            ),
        )

        # Get input/output names
        if self._session is not None:
            self._input_names = [
                input_node.name for input_node in self._session.get_inputs()
            ]
            self._output_names = [
                output_node.name for output_node in self._session.get_outputs()
            ]

        # Register for cleanup
        self.register_resource(self._session)

    async def _configure_session_options(self) -> t.Any:
        """Configure ONNX session options."""
        session_options = ort.SessionOptions()
        session_options.enable_cpu_mem_arena = self._settings.enable_cpu_mem_arena
        session_options.enable_mem_pattern = self._settings.enable_mem_pattern
        session_options.enable_profiling = self._settings.enable_profiling

        if self._settings.inter_op_num_threads > 0:
            session_options.inter_op_num_threads = self._settings.inter_op_num_threads
        if self._settings.intra_op_num_threads > 0:
            session_options.intra_op_num_threads = self._settings.intra_op_num_threads

        self._set_graph_optimization_level(session_options)
        return session_options

    def _set_graph_optimization_level(self, session_options: t.Any) -> None:
        """Set the graph optimization level for the ONNX session."""
        if self._settings.graph_optimization_level == "ORT_DISABLE_ALL":
            session_options.graph_optimization_level = (
                ort.GraphOptimizationLevel.ORT_DISABLE_ALL
            )
        elif self._settings.graph_optimization_level == "ORT_ENABLE_BASIC":
            session_options.graph_optimization_level = (
                ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
            )
        elif self._settings.graph_optimization_level == "ORT_ENABLE_EXTENDED":
            session_options.graph_optimization_level = (
                ort.GraphOptimizationLevel.ORT_ENABLE_EXTENDED
            )
        else:  # ORT_ENABLE_ALL (default)
            session_options.graph_optimization_level = (
                ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            )

    async def _tokenize_batch(
        self,
        texts: list[str],
        tokenizer: t.Any,
    ) -> dict[str, np.ndarray]:
        """Tokenize batch of texts for ONNX processing."""
        if not callable(tokenizer):
            msg = "Tokenizer is not callable"
            raise TypeError(msg)

        return await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: tokenizer(
                texts,
                padding=True,
                truncation=True,
                max_length=self._settings.max_seq_length,
                return_tensors="np",
            ),
        )

    def _prepare_onnx_inputs(
        self,
        tokenized: dict[str, np.ndarray],
    ) -> dict[str, np.ndarray]:
        """Prepare inputs for ONNX inference."""
        onnx_inputs = {}

        for input_name in self._input_names:
            if input_name == "input_ids":
                onnx_inputs[input_name] = tokenized["input_ids"].astype(np.int64)
            elif input_name == "attention_mask":
                onnx_inputs[input_name] = tokenized["attention_mask"].astype(np.int64)
            elif input_name == "token_type_ids" and "token_type_ids" in tokenized:
                onnx_inputs[input_name] = tokenized["token_type_ids"].astype(np.int64)

        return onnx_inputs

    def _count_tokens_safe(
        self,
        text: str,
        tokenizer: t.Any,
    ) -> int | None:
        """Safely count tokens with error handling."""
        if not hasattr(tokenizer, "encode"):
            return None

        with suppress(Exception):
            return len(tokenizer.encode(text))

        return None

    def _create_embedding_result(
        self,
        text: str,
        embedding: np.ndarray,
        model: str,
        token_count: int | None,
    ) -> EmbeddingResult:
        """Create single embedding result with metadata."""
        return EmbeddingResult(
            text=text,
            embedding=embedding.tolist(),
            model=model,
            dimensions=len(embedding),
            tokens=token_count,
            metadata={
                "pooling_strategy": self._settings.pooling_strategy.value,
                "providers": self._settings.providers,
                "max_seq_length": self._settings.max_seq_length,
                "optimized": True,
            },
        )

    async def _process_single_batch(
        self,
        batch_texts: list[str],
        session: t.Any,
        tokenizer: t.Any,
        model: str,
        normalize: bool,
    ) -> list[EmbeddingResult]:
        """Process a single batch of texts."""
        # Tokenize
        inputs = await self._tokenize_batch(batch_texts, tokenizer)

        # Prepare ONNX inputs
        onnx_inputs = self._prepare_onnx_inputs(inputs)

        # Run inference
        outputs = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: session.run(self._output_names, onnx_inputs),
        )

        # Apply pooling
        embeddings = await self._apply_pooling(
            outputs[0],
            inputs["attention_mask"],
            self._settings.pooling_strategy,
        )

        # Normalize if requested
        if normalize:
            embeddings = self._normalize_embeddings(embeddings)

        # Create results with token counting
        return [
            self._create_embedding_result(
                text,
                embedding,
                model,
                self._count_tokens_safe(text, tokenizer),
            )
            for text, embedding in zip(batch_texts, embeddings, strict=False)
        ]

    async def _process_all_batches(
        self,
        texts: list[str],
        batch_size: int,
        session: t.Any,
        tokenizer: t.Any,
        model: str,
        normalize: bool,
        logger: t.Any,
    ) -> list[EmbeddingResult]:
        """Process all text batches and return results."""
        results = []
        batches = self._batch_texts(texts, batch_size)

        for batch_texts in batches:
            try:
                batch_results = await self._process_single_batch(
                    batch_texts,
                    session,
                    tokenizer,
                    model,
                    normalize,
                )
                results.extend(batch_results)

                await logger.debug(
                    f"ONNX embeddings batch completed: {len(batch_texts)} texts, model: {model}",
                )

            except Exception as e:
                await logger.exception(f"Error generating ONNX embeddings: {e}")
                raise

        return results

    async def _embed_texts(
        self,
        texts: list[str],
        model: str,
        normalize: bool,
        batch_size: int,
        **kwargs: t.Any,
    ) -> EmbeddingBatch:
        """Generate embeddings for multiple texts using ONNX Runtime."""
        start_time = time.time()
        session, tokenizer = await self._ensure_client()
        logger: t.Any = depends.get("logger")

        # Process all batches
        results = await self._process_all_batches(
            texts,
            batch_size,
            session,
            tokenizer,
            model,
            normalize,
            logger,
        )

        # Aggregate metrics
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
        token_embeddings: np.ndarray,
        attention_mask: np.ndarray,
        strategy: PoolingStrategy,
    ) -> np.ndarray:
        """Apply pooling strategy to token embeddings."""
        result: np.ndarray
        if strategy == PoolingStrategy.MEAN:
            # Mean pooling with attention mask
            input_mask_expanded = np.expand_dims(attention_mask, axis=-1)
            input_mask_expanded = np.repeat(
                input_mask_expanded,
                token_embeddings.shape[-1],
                axis=-1,
            )

            sum_embeddings = np.sum(token_embeddings * input_mask_expanded, axis=1)
            sum_mask = np.clip(
                np.sum(input_mask_expanded, axis=1),
                a_min=1e-9,
                a_max=None,
            )
            result = t.cast("np.ndarray", sum_embeddings / sum_mask)
            return result

        if strategy == PoolingStrategy.MAX:
            # Max pooling
            input_mask_expanded = np.expand_dims(attention_mask, axis=-1)
            input_mask_expanded = np.repeat(
                input_mask_expanded,
                token_embeddings.shape[-1],
                axis=-1,
            )

            token_embeddings = np.where(
                input_mask_expanded == 0,
                -1e9,
                token_embeddings,
            )
            result = np.max(token_embeddings, axis=1)
            return result

        if strategy == PoolingStrategy.CLS:
            # CLS token pooling (first token)
            result = token_embeddings[:, 0]
            return result

        if strategy == PoolingStrategy.WEIGHTED_MEAN:
            # Weighted mean (simple implementation)
            weights = np.expand_dims(attention_mask, axis=-1).astype(np.float32)
            weighted_embeddings = token_embeddings * weights
            sum_embeddings = np.sum(weighted_embeddings, axis=1)
            sum_weights = np.sum(weights, axis=1)
            result = t.cast(
                "np.ndarray",
                sum_embeddings / np.clip(sum_weights, a_min=1e-9, a_max=None),
            )
            return result

        msg = f"Unsupported pooling strategy: {strategy}"
        raise ValueError(msg)

    def _normalize_embeddings(self, embeddings: np.ndarray) -> np.ndarray:
        """Normalize embeddings using L2 normalization."""
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms = np.clip(norms, a_min=1e-12, a_max=None)
        result: np.ndarray = embeddings / norms
        return result

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
        """Get information about the ONNX model."""
        model_info = {
            "name": model,
            "provider": "onnx",
            "type": "embedding",
            "model_path": self._settings.model_path,
            "tokenizer": self._settings.tokenizer_name,
            "optimized": True,
        }

        if self._session:
            model_info.update(
                {
                    "providers": self._session.get_providers(),
                    "input_names": self._input_names,
                    "output_names": self._output_names,
                },
            )

        return model_info

    async def _list_models(self) -> list[dict[str, t.Any]]:
        """List common ONNX embedding models."""
        # These would typically be downloaded/converted models
        models = [
            {
                "name": "onnx-all-MiniLM-L6-v2",
                "description": "ONNX optimized version of all-MiniLM-L6-v2",
                "dimensions": 384,
                "performance": "High speed, low memory",
            },
            {
                "name": "onnx-all-mpnet-base-v2",
                "description": "ONNX optimized version of all-mpnet-base-v2",
                "dimensions": 768,
                "performance": "Balanced speed and quality",
            },
        ]

        return [
            model_info
            | {
                "provider": "onnx",
                "type": "embedding",
            }
            for model_info in models
        ]

    async def get_performance_metrics(self) -> dict[str, t.Any]:
        """Get ONNX runtime performance metrics."""
        if not self._session:
            return {}

        try:
            profiling_data = (
                self._session.end_profiling()
                if self._settings.enable_profiling
                else None
            )

            return {
                "providers": self._session.get_providers(),
                "input_names": self._input_names,
                "output_names": self._output_names,
                "profiling_enabled": self._settings.enable_profiling,
                "profiling_data": profiling_data,
                "session_options": {
                    "enable_cpu_mem_arena": self._settings.enable_cpu_mem_arena,
                    "enable_mem_pattern": self._settings.enable_mem_pattern,
                    "inter_op_threads": self._settings.inter_op_num_threads,
                    "intra_op_threads": self._settings.intra_op_num_threads,
                    "graph_optimization": self._settings.graph_optimization_level,
                },
            }
        except Exception as e:
            return {"error": str(e)}

    async def health_check(self) -> dict[str, t.Any]:
        """Perform health check on ONNX embeddings service."""
        try:
            # Test with a simple embedding request
            test_result = await self.embed_text("health check test")

            return {
                "status": "healthy",
                "provider": "onnx",
                "model_path": self._settings.model_path,
                "providers": self._session.get_providers() if self._session else [],
                "dimensions": len(test_result),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "provider": "onnx",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    async def cleanup(self) -> None:
        """Clean up ONNX session and tokenizer resources."""
        if self._session is not None:
            del self._session
            self._session = None

        if self._tokenizer is not None:
            del self._tokenizer
            self._tokenizer = None

        await super().cleanup()


# Factory function for dependency injection
async def create_onnx_embedding(
    config: Config | None = None,
    model_path: str = "",
) -> ONNXEmbedding:
    """Create ONNX embedding adapter instance."""
    if config is None:
        config = await depends.get("config")

    if not model_path:
        msg = "model_path is required for ONNX embedding"
        raise ValueError(msg)

    settings = ONNXEmbeddingSettings(model_path=model_path)
    return ONNXEmbedding(settings)


# Type alias
Embedding = ONNXEmbedding
EmbeddingSettings = ONNXEmbeddingSettings

depends.set(Embedding, "onnx")
