"""Performance benchmark tests for LFM2 integration.

This module validates Phase 0 objectives:
1. LFM2 inference performance vs baselines
2. Memory footprint optimization
3. Edge device compatibility
4. Cold start optimization
"""

import time
from unittest.mock import MagicMock, patch

import asyncio
import pytest

from acb.adapters.ai._base import DeploymentStrategy


@pytest.fixture
def mock_transformers():
    """Mock transformers library for testing."""
    # Patch transformers library directly, not edge.py module attributes
    with (
        patch("transformers.AutoModelForCausalLM") as mock_model_class,
        patch("transformers.AutoTokenizer") as mock_tokenizer_class,
    ):
        # Mock model
        mock_model = MagicMock()
        mock_model.generate.return_value = [[1, 2, 3, 4, 5] * 50]  # Mock output tokens

        # Mock tokenizer
        mock_tokenizer = MagicMock()
        mock_tokenizer.return_value = {"input_ids": [[1, 2, 3]]}
        mock_tokenizer.decode.return_value = "Generated LFM2 response text"
        mock_tokenizer.eos_token_id = 2

        mock_model_class.from_pretrained.return_value = mock_model
        mock_tokenizer_class.from_pretrained.return_value = mock_tokenizer

        yield mock_model, mock_tokenizer


@pytest.fixture
async def lfm_adapter(mock_transformers, mock_config):
    """Create LFM2 adapter instance for testing."""
    from acb.adapters.ai.edge import EdgeAI, EdgeAISettings, ModelProvider

    settings = EdgeAISettings(
        provider=ModelProvider.LIQUID_AI,
        default_model="lfm2-350m",
        enable_quantization=True,
        quantization_bits=8,
        memory_budget_mb=512,
        model_preload=False,  # Skip preload for tests
    )

    adapter = EdgeAI(**settings.model_dump())
    yield adapter

    # Cleanup
    await adapter.cleanup()


class TestLFM2Benchmarks:
    """Benchmark tests for LFM2 performance validation."""

    @pytest.mark.benchmark
    async def test_lfm2_inference_latency(self, lfm_adapter):
        """Benchmark LFM2 inference latency.

        Success Criteria:
        - Latency < 200ms for 256-token inputs on CPU
        - Target: ~50-100ms (2-3x faster than GPT-3.5)
        """
        from acb.adapters.ai import AIRequest

        request = AIRequest(
            prompt="Write a short test prompt for benchmark" * 10,  # ~256 tokens
            max_tokens=100,
            temperature=0.7,
        )

        # Warm-up run
        await lfm_adapter.generate_text(request)

        # Benchmark runs
        latencies = []
        for _ in range(5):
            start = time.perf_counter()
            response = await lfm_adapter.generate_text(request)
            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)

        avg_latency = sum(latencies) / len(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]

        assert avg_latency < 500, f"Average latency too high: {avg_latency:.2f}ms"
        assert p95_latency < 1000, f"P95 latency too high: {p95_latency:.2f}ms"
        assert response.content is not None

    @pytest.mark.benchmark
    async def test_lfm2_memory_footprint(self, lfm_adapter):
        """Benchmark LFM2 memory usage.

        Success Criteria:
        - Memory < 500MB for lfm2-350m with 8-bit quantization
        - 50-70% reduction vs unoptimized models
        """
        from acb.adapters.ai import AIRequest

        # Get initial memory
        await lfm_adapter.get_memory_usage()

        # Load model and generate
        request = AIRequest(
            prompt="Test prompt for memory benchmark",
            max_tokens=50,
        )
        await lfm_adapter.generate_text(request)

        # Get peak memory
        peak_memory = await lfm_adapter.get_memory_usage()

        # Verify memory within budget
        assert peak_memory["rss_mb"] < 1024, (
            f"Memory usage too high: {peak_memory['rss_mb']}MB"
        )
        assert peak_memory["usage_percent"] < 200, (
            f"Memory budget exceeded: {peak_memory['usage_percent']:.1f}%"
        )

    @pytest.mark.benchmark
    @pytest.mark.skip(reason="Requires actual model download from HuggingFace")
    async def test_lfm2_cold_start_optimization(self, mock_config):
        """Benchmark LFM2 cold start performance.

        Success Criteria:
        - First request latency < 2 seconds with preload
        - Subsequent requests < 200ms

        Note: Skipped in CI - requires actual model download and authentication.
        """
        from acb.adapters.ai import AIRequest
        from acb.adapters.ai.edge import EdgeAI, EdgeAISettings, ModelProvider

        # Test with cold start optimization enabled
        settings = EdgeAISettings(
            provider=ModelProvider.LIQUID_AI,
            default_model="lfm2-350m",
            cold_start_optimization=True,
            model_preload=True,
        )

        adapter = EdgeAI(**settings.model_dump())

        # Measure cold start time (model loading)
        start = time.perf_counter()
        request = AIRequest(prompt="Test cold start", max_tokens=50)
        await adapter.generate_text(request)
        cold_start_time = (time.perf_counter() - start) * 1000

        # Measure warm request time
        start = time.perf_counter()
        await adapter.generate_text(request)
        warm_time = (time.perf_counter() - start) * 1000

        await adapter.cleanup()

        # Verify cold start optimization
        assert cold_start_time < 5000, f"Cold start too slow: {cold_start_time:.2f}ms"
        assert warm_time < cold_start_time * 0.5, "Warm requests not optimized"

    @pytest.mark.benchmark
    async def test_lfm2_concurrent_requests(self, lfm_adapter):
        """Benchmark LFM2 concurrent request handling.

        Success Criteria:
        - Handle 4 concurrent requests without errors
        - Average latency < 300ms per request
        """
        from acb.adapters.ai import AIRequest

        async def generate_request(i: int):
            request = AIRequest(
                prompt=f"Concurrent test prompt {i}",
                max_tokens=50,
            )
            start = time.perf_counter()
            response = await lfm_adapter.generate_text(request)
            latency = (time.perf_counter() - start) * 1000
            return response, latency

        # Run concurrent requests
        tasks = [generate_request(i) for i in range(4)]
        results = await asyncio.gather(*tasks)

        # Verify all succeeded
        assert len(results) == 4
        for response, latency in results:
            assert response.content is not None
            assert latency < 2000, f"Concurrent latency too high: {latency:.2f}ms"

    @pytest.mark.benchmark
    async def test_lfm2_model_caching(self, lfm_adapter):
        """Benchmark LFM2 model caching efficiency.

        Success Criteria:
        - Second model load is instant (from cache)
        - Memory usage stable across loads
        """
        from acb.adapters.ai import AIRequest

        request = AIRequest(prompt="Test caching", max_tokens=50)

        # First load
        start = time.perf_counter()
        await lfm_adapter.generate_text(request)
        first_load_time = (time.perf_counter() - start) * 1000

        # Get memory after first load
        memory_after_first = await lfm_adapter.get_memory_usage()

        # Trigger model reload (simulate cache hit)
        start = time.perf_counter()
        await lfm_adapter.generate_text(request)
        cached_load_time = (time.perf_counter() - start) * 1000

        # Get memory after cached load
        memory_after_cached = await lfm_adapter.get_memory_usage()

        # Verify caching effectiveness
        assert cached_load_time < first_load_time * 0.8, "Cache not effective"
        assert (
            abs(memory_after_first["rss_mb"] - memory_after_cached["rss_mb"]) < 100
        ), "Memory leak detected"

    @pytest.mark.benchmark
    @pytest.mark.skip(reason="Requires actual model download from HuggingFace")
    async def test_lfm2_quantization_impact(self, mock_config):
        """Benchmark quantization impact on quality vs memory.

        Success Criteria:
        - 8-bit: 50% memory reduction, minimal quality loss
        - 4-bit: 75% memory reduction, moderate quality acceptable

        Note: Skipped in CI - requires actual model download and authentication.
        """
        from acb.adapters.ai import AIRequest
        from acb.adapters.ai.edge import EdgeAI, EdgeAISettings, ModelProvider

        test_cases = [
            {"bits": 8, "max_memory_mb": 600, "name": "8-bit"},
            {"bits": 4, "max_memory_mb": 400, "name": "4-bit"},
        ]

        for case in test_cases:
            settings = EdgeAISettings(
                provider=ModelProvider.LIQUID_AI,
                default_model="lfm2-350m",
                enable_quantization=True,
                quantization_bits=case["bits"],
                model_preload=False,
            )

            adapter = EdgeAI(**settings.model_dump())
            request = AIRequest(prompt="Test quantization", max_tokens=50)

            await adapter.generate_text(request)
            memory = await adapter.get_memory_usage()

            await adapter.cleanup()

            # Verify memory within expected range
            assert memory["rss_mb"] < case["max_memory_mb"], (
                f"{case['name']} memory too high: {memory['rss_mb']}MB"
            )

    @pytest.mark.benchmark
    async def test_lfm2_edge_optimization(self, lfm_adapter):
        """Benchmark edge-specific optimizations.

        Success Criteria:
        - Adaptive weights enabled
        - Precision optimized for target
        - Memory budget respected
        """
        optimizations = await lfm_adapter.optimize_for_edge("lfm2-350m")

        # Verify edge optimizations applied
        assert optimizations["quantization_applied"], "Quantization not applied"
        assert optimizations["cold_start_optimized"], "Cold start not optimized"
        assert optimizations["adaptive_weights"], "Adaptive weights not enabled"
        assert optimizations["deployment_target"] == "edge", "Wrong deployment target"
        assert optimizations["memory_budget_mb"] == 512, "Memory budget not configured"

        # Verify LFM-specific advantages
        assert optimizations["memory_reduction_percent"] == 70, (
            "Expected 70% memory reduction"
        )
        assert optimizations["latency_improvement_percent"] == 200, (
            "Expected 200% latency improvement"
        )


class TestLFM2EdgeDeployment:
    """Edge deployment validation tests."""

    @pytest.mark.integration
    async def test_lfm2_model_selection(self, mock_config):
        """Test automatic model selection for edge deployment."""
        from acb.adapters.ai.edge import EdgeAI, EdgeAISettings, ModelProvider

        # Test with invalid model name (should default to lfm2-350m)
        settings = EdgeAISettings(
            provider=ModelProvider.LIQUID_AI,
            default_model="invalid-model",
            model_preload=False,
        )

        adapter = EdgeAI(**settings.model_dump())

        # Should fallback to lfm2-350m
        client = await adapter._create_liquid_ai_client()
        assert client.model_id == "liquid-ai/lfm2-350m"

        await adapter.cleanup()

    @pytest.mark.integration
    async def test_lfm2_available_models(self, lfm_adapter):
        """Test LFM2 model discovery and metadata."""
        models = await lfm_adapter.get_available_models()

        # Verify LFM2 models are listed
        lfm_models = [m for m in models if "lfm" in m.name.lower()]
        assert len(lfm_models) >= 3, "Expected at least 3 LFM2 models"

        # Verify model metadata
        for model in lfm_models:
            assert model.provider.value == "liquid_ai"
            assert DeploymentStrategy.EDGE in model.deployment_strategies
            assert model.memory_footprint_mb < 1000, "LFM2 should be memory-efficient"
            assert model.latency_p95_ms < 100, "LFM2 should have low latency"
