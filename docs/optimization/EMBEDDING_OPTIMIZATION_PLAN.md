# Embedding Adapter Optimization Plan

## Current Complexity Analysis

### HuggingFace `_embed_texts` (Complexity: 27)

**Location:** `adapters/embedding/huggingface.py::226-315`

**Complexity Sources:**

1. Nested loop with batch processing (for loop)
1. Complex input preparation (tokenization + device movement)
1. Inline output processing and pooling
1. Mixed error handling and logging within loop
1. Result object construction inline
1. Token counting embedded in result creation

**Refactoring Strategy:**

- Extract tokenization logic → `_tokenize_batch()`
- Extract embedding generation → `_generate_embeddings()`
- Extract result creation → `_create_embedding_results()`
- Use generator expressions for memory efficiency
- Apply early returns for error cases

### ONNX `_embed_batch` (Complexity: 23)

**Location:** `adapters/embedding/onnx.py::230-339`

**Complexity Sources:**

1. Nested loop with batch processing
1. Complex ONNX input preparation (multiple input types)
1. Conditional input construction for token_type_ids
1. Inline token counting with error suppression
1. Result object construction inline
1. Mixed normalization and pooling logic

**Refactoring Strategy:**

- Extract ONNX input preparation → `_prepare_onnx_inputs()`
- Extract tokenization logic → `_tokenize_batch()`
- Extract token counting → `_count_tokens()`
- Extract result creation → `_create_embedding_results()`
- Simplify normalization flow

## Optimization Implementation

### Phase 1: Extract Helper Methods

#### HuggingFace Helpers

```python
async def _tokenize_batch(self, texts: list[str], tokenizer: t.Any) -> dict[str, t.Any]:
    """Tokenize batch of texts with standard parameters."""
    return await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=self._settings.max_seq_length,
            return_tensors="pt",
        ),
    )


async def _generate_embeddings(
    self,
    model: t.Any,
    inputs: dict[str, t.Any],
) -> torch.Tensor:
    """Generate embeddings from model inputs."""
    with torch.no_grad():
        outputs = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: model(**inputs),
        )

    embeddings = await self._apply_pooling(
        outputs.last_hidden_state,
        inputs["attention_mask"],
        self._settings.pooling_strategy,
    )

    return embeddings


def _create_embedding_result(
    self,
    text: str,
    embedding: list[float],
    model: str,
    tokenizer: t.Any,
) -> EmbeddingResult:
    """Create single embedding result with metadata."""
    return EmbeddingResult(
        text=text,
        embedding=embedding,
        model=model,
        dimensions=len(embedding),
        tokens=len(tokenizer.encode(text)),
        metadata={
            "pooling_strategy": self._settings.pooling_strategy.value,
            "device": self._device,
            "max_seq_length": self._settings.max_seq_length,
        },
    )
```

#### ONNX Helpers

```python
async def _tokenize_batch(
    self,
    texts: list[str],
    tokenizer: t.Any,
) -> dict[str, np.ndarray]:
    """Tokenize batch of texts for ONNX processing."""
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
```

### Phase 2: Refactor Main Methods

#### HuggingFace `_embed_texts` (Target Complexity ≤13)

```python
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

    # Process all batches
    results = await self._process_all_batches(
        texts,
        batch_size,
        model_obj,
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


async def _process_all_batches(
    self,
    texts: list[str],
    batch_size: int,
    model_obj: t.Any,
    tokenizer: t.Any,
    model: str,
    normalize: bool,
    logger: t.Any,
) -> list[EmbeddingResult]:
    """Process all text batches and return results."""
    results = []
    batches = self._batch_texts(texts, batch_size)

    for batch_texts in batches:
        batch_results = await self._process_single_batch(
            batch_texts,
            model_obj,
            tokenizer,
            model,
            normalize,
        )
        results.extend(batch_results)

        await logger.debug(
            f"HuggingFace embeddings batch completed: {len(batch_texts)} texts"
        )

    return results


async def _process_single_batch(
    self,
    batch_texts: list[str],
    model_obj: t.Any,
    tokenizer: t.Any,
    model: str,
    normalize: bool,
) -> list[EmbeddingResult]:
    """Process a single batch of texts."""
    # Tokenize
    inputs = await self._tokenize_batch(batch_texts, tokenizer)

    # Move to device
    inputs = {k: v.to(self._device) for k, v in inputs.items()}

    # Generate embeddings
    embeddings = await self._generate_embeddings(model_obj, inputs)

    # Normalize if requested
    if normalize:
        embeddings = F.normalize(embeddings, p=2, dim=1)

    # Convert and create results
    embeddings_list = embeddings.cpu().tolist()
    return [
        self._create_embedding_result(text, embedding, model, tokenizer)
        for text, embedding in zip(batch_texts, embeddings_list)
    ]
```

#### ONNX `_embed_texts` (Target Complexity ≤13)

```python
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
        batch_results = await self._process_single_batch(
            batch_texts,
            session,
            tokenizer,
            model,
            normalize,
        )
        results.extend(batch_results)

        await logger.debug(f"ONNX embeddings batch completed: {len(batch_texts)} texts")

    return results


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
        for text, embedding in zip(batch_texts, embeddings)
    ]
```

## Expected Improvements

### Complexity Reduction

- **HuggingFace**: 27 → ~12 (55% reduction)
- **ONNX**: 23 → ~11 (52% reduction)

### Code Quality Benefits

1. **Single Responsibility**: Each helper method has one clear purpose
1. **Testability**: Helper methods can be unit tested independently
1. **Maintainability**: Changes to tokenization/processing are localized
1. **Readability**: Main flow is now clear and concise
1. **Memory Efficiency**: Generator expressions and list comprehensions
1. **Type Safety**: All helper methods have proper type hints

### Memory Impact

- **Reduced**: Eliminated intermediate variables in hot loops
- **Optimized**: Generator expressions for result creation
- **Improved**: Explicit resource cleanup in helper methods

## Verification Strategy

### Unit Tests

```python
@pytest.mark.asyncio
async def test_tokenize_batch_huggingface():
    """Test HuggingFace batch tokenization."""
    adapter = HuggingFaceEmbedding()
    texts = ["test1", "test2"]
    result = await adapter._tokenize_batch(texts, mock_tokenizer)
    assert "input_ids" in result
    assert "attention_mask" in result


@pytest.mark.asyncio
async def test_prepare_onnx_inputs():
    """Test ONNX input preparation."""
    adapter = ONNXEmbedding(mock_settings)
    tokenized = {"input_ids": np.array([1, 2, 3])}
    result = adapter._prepare_onnx_inputs(tokenized)
    assert "input_ids" in result
    assert result["input_ids"].dtype == np.int64
```

### Integration Tests

- Verify end-to-end embedding generation still works
- Check memory usage with large batches
- Validate embedding accuracy unchanged
- Test error handling paths

### Performance Benchmarks

- Compare processing time before/after
- Measure memory usage with memory_profiler
- Verify no regression in embedding quality

## Implementation Checklist

- [ ] Create helper methods for HuggingFace adapter
- [ ] Create helper methods for ONNX adapter
- [ ] Refactor HuggingFace `_embed_texts` method
- [ ] Refactor ONNX `_embed_texts` method
- [ ] Add unit tests for new helper methods
- [ ] Run integration tests
- [ ] Verify complexity ≤13 for both adapters
- [ ] Run memory profiler and validate improvements
- [ ] Run crackerjack verification
- [ ] Document changes in commit message
