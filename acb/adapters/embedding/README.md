> **ACB Documentation**: [Main](../../../README.md) | [Core Systems](../../README.md) | [Actions](../../actions/README.md) | [Adapters](../README.md) | [Embedding](./README.md)

# Embedding Adapter

> **Configuration**
> Choose the `embedding` implementation in `settings/adapters.yaml` and tune it via `settings/embedding.yaml`. Store secrets in `settings/secrets/` or via a secret manager so they never reach git.

The Embedding adapter standardizes vector generation across hosted APIs,
fine-tuned local models, and ONNX-optimized runtimes. It powers semantic search,
retrieval-augmented generation, clustering, and similarity services without
locking applications to a single provider.

## Table of Contents

- [Overview](#overview)
- [Core Types](#core-types)
- [Pooling & Normalization](#pooling--normalization)
- [Settings](#settings)
- [Built-in Implementations](#built-in-implementations)
- [Usage Examples](#usage-examples)
- [Vector Store Integration](#vector-store-integration)
- [Batching & Chunking](#batching--chunking)
- [Best Practices](#best-practices)
- [Related Adapters](#related-adapters)

## Overview

Implementations inherit `EmbeddingAdapter`, which manages async lifecycle,
client caching, and cleanup hooks. Requests can specify model IDs, batch sizes,
normalization rules, and pooling strategies while responses report metadata such
as token count, processing time, and embedding dimensions.

## Core Types

- `EmbeddingRequest` / `EmbeddingResponse`: Dataclasses used internally to pass
  prompts, batching hints, and results.
- `EmbeddingBatch`: Pydantic model containing per-text `EmbeddingResult`, total
  tokens, and runtime metrics.
- `EmbeddingModel`: Enum of canonical model identifiers spanning OpenAI,
  SentenceTransformers, ONNX exports, and Liquid AI LFM.
- `PoolingStrategy` & `VectorNormalization`: Provide consistent pooling and
  normalization semantics regardless of provider.

## Pooling & Normalization

- Pooling strategies include mean, max, CLS token, and weighted mean for
  sentence-transformer families.
- Normalization options (L2, L1, none) make it straightforward to prepare data
  for downstream vector databases that require pre-normalized vectors.

## Settings

`EmbeddingBaseSettings` drives runtime configuration:

- API credentials (`api_key`, `base_url`) for hosted backends with optional TLS
  configuration via `SSLConfigMixin`.
- Performance tuning (`batch_size`, `max_tokens_per_batch`, `timeout`) and cache
  controls (`cache_embeddings`, `cache_ttl`).
- Edge optimizations such as model prefetching, in-memory caching, and memory
  budgeting for constrained deployments.

Settings are typically supplied through `settings/adapters.yaml` or environment
overrides consumed by the DI container.

## Built-in Implementations

| Module | Description | Highlights |
| ------ | ----------- | ---------- |
| `openai` | Integrates with OpenAI embedding APIs. | High-quality English embeddings with token usage reporting. |
| `huggingface` | Uses hosted Inference API. | Access to thousands of community models. |
| `sentence_transformers` | Runs SentenceTransformers via `sentence-transformers`. | Balanced accuracy/performance for multilingual workloads. |
| `onnx` | Loads ONNX-optimized checkpoints. | Fast inference on CPU-only or edge environments. |
| `lfm` | Liquid AI Foundation Models. | Edge-friendly models tuned for low-resource hardware. |

## Usage Examples

```python
from acb.adapters import import_adapter
from acb.depends import depends

Embedding = import_adapter("embedding")


async def embed_texts(texts: list[str]) -> list[list[float]]:
    adapter = await depends.get(Embedding)
    batch = await adapter.embed_texts(texts, model="text-embedding-3-small")
    return [result.embedding for result in batch.results]
```

## Vector Store Integration

```python
from acb.adapters import import_adapter
from acb.depends import depends

Embedding = import_adapter("embedding")
Vector = import_adapter("vector")


async def upsert_vectors(documents: dict[str, str]) -> None:
    embedding_adapter = await depends.get(Embedding)
    vector_store = await depends.get(Vector)

    ids = list(documents.keys())
    texts = list(documents.values())
    batch = await embedding_adapter.embed_texts(texts)

    payloads = [
        {"id": doc_id, "embedding": result.embedding, "metadata": {"text": text}}
        for doc_id, text, result in zip(ids, texts, batch.results, strict=True)
    ]
    await vector_store.upsert(payloads)
```

## Batching & Chunking

- Call `embed_documents()` to apply automatic chunking with configurable chunk
  size and overlap; useful for long documents destined for RAG pipelines.
- `chunk_size` and `batch_size` parameters can be overridden per request for
  fine-grained control during ingestion or backfills.
- When caching is enabled, repeated requests reuse results to avoid duplicate
  billing from remote providers.

## Best Practices

- Align embedding model choice with your vector store dimensions to avoid
  runtime errors or reindexing.
- Normalize vectors when your similarity metric assumes unit length (cosine).
- Capture `EmbeddingBatch.processing_time` and `total_tokens` to monitor cost
  and throughput during ingestion jobs.
- For edge deployments, enable `prefetch_models` during service startup to
  reduce first-request latency.
- Use deterministic chunking parameters when embeddings feed long-term stores,
  ensuring reruns produce identical vectors.

## Related Adapters

- [AI](../ai/README.md)
- [Vector](../vector/README.md)
- [Storage](../storage/README.md)
