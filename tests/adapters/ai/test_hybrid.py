"""Tests for the hybrid AI adapter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from acb.adapters.ai._base import (
    AIRequest,
    AIResponse,
    DeploymentStrategy,
    ModelCapability,
    ModelProvider,
)
from acb.adapters.ai.hybrid import (
    MODULE_METADATA,
    HybridAI,
    HybridAISettings,
    RoutingCriteria,
    RoutingDecision,
    RoutingResult,
    RoutingStrategy,
)


class TestHybridAISettings:
    @patch("acb.depends.depends.get")
    def test_init_basic(self, mock_depends_get: MagicMock) -> None:
        mock_config = MagicMock()
        mock_depends_get.return_value = mock_config

        settings = HybridAISettings()
        assert settings.routing_strategy == RoutingStrategy.PERFORMANCE
        assert settings.cloud_provider == ModelProvider.OPENAI
        assert settings.edge_provider == ModelProvider.OLLAMA
        assert settings.enable_adaptive_routing
        assert settings.latency_threshold_ms == 1000

    @patch("acb.depends.depends.get")
    def test_init_with_custom_thresholds(self, mock_depends_get: MagicMock) -> None:
        mock_config = MagicMock()
        mock_depends_get.return_value = mock_config

        settings = HybridAISettings(
            routing_strategy=RoutingStrategy.LATENCY,
            latency_threshold_ms=500,
            cost_threshold_per_token=0.000005,
        )
        assert settings.routing_strategy == RoutingStrategy.LATENCY
        assert settings.latency_threshold_ms == 500
        assert settings.cost_threshold_per_token == 0.000005


class TestRoutingCriteria:
    def test_init_basic(self) -> None:
        criteria = RoutingCriteria()
        assert criteria.max_latency_ms is None
        assert criteria.requires_privacy is False

    def test_init_with_params(self) -> None:
        criteria = RoutingCriteria(
            max_latency_ms=500,
            requires_privacy=True,
            model_capabilities=[ModelCapability.VISION],
        )
        assert criteria.max_latency_ms == 500
        assert criteria.requires_privacy
        assert ModelCapability.VISION in criteria.model_capabilities


class TestRoutingResult:
    def test_init(self) -> None:
        result = RoutingResult(
            decision=RoutingDecision.EDGE,
            strategy=DeploymentStrategy.EDGE,
            model="llama2:7b",
            confidence=0.8,
            reasoning="Low latency requirement",
        )
        assert result.decision == RoutingDecision.EDGE
        assert result.strategy == DeploymentStrategy.EDGE
        assert result.model == "llama2:7b"
        assert result.confidence == 0.8


class TestHybridAI:
    @pytest.fixture
    def mock_cloud_adapter(self) -> MagicMock:
        adapter = MagicMock()
        adapter._generate_text = AsyncMock(
            return_value=AIResponse(
                content="Cloud response",
                model="gpt-4",
                provider=ModelProvider.OPENAI,
                strategy=DeploymentStrategy.CLOUD,
                tokens_used=100,
            )
        )
        adapter.generate_text_stream = AsyncMock()
        adapter.health_check = AsyncMock(return_value={"status": "healthy"})
        return adapter

    @pytest.fixture
    def mock_edge_adapter(self) -> MagicMock:
        adapter = MagicMock()
        adapter._generate_text = AsyncMock(
            return_value=AIResponse(
                content="Edge response",
                model="llama2:7b",
                provider=ModelProvider.OLLAMA,
                strategy=DeploymentStrategy.EDGE,
                tokens_used=80,
            )
        )
        adapter.generate_text_stream = AsyncMock()
        adapter.health_check = AsyncMock(return_value={"status": "healthy"})
        return adapter

    @pytest.mark.asyncio
    async def test_create_client(self) -> None:
        with (
            patch("acb.adapters.ai.hybrid.CloudAI") as mock_cloud_ai,
            patch("acb.adapters.ai.hybrid.EdgeAI") as mock_edge_ai,
        ):
            mock_cloud_adapter = MagicMock()
            mock_edge_adapter = MagicMock()
            mock_cloud_ai.return_value = mock_cloud_adapter
            mock_edge_ai.return_value = mock_edge_adapter

            adapter = HybridAI()
            clients = await adapter._create_client()

            assert "cloud" in clients
            assert "edge" in clients
            assert adapter._cloud_adapter == mock_cloud_adapter
            assert adapter._edge_adapter == mock_edge_adapter

    @pytest.mark.asyncio
    async def test_extract_routing_criteria(self) -> None:
        adapter = HybridAI()
        request = AIRequest(
            prompt="Test prompt",
            max_latency_ms=500,
            memory_budget_mb=256,
            min_quality_score=0.9,
        )

        criteria = adapter._extract_routing_criteria(request)

        assert criteria.max_latency_ms == 500
        assert criteria.memory_budget_mb == 256
        assert criteria.min_quality_score == 0.9

    @pytest.mark.asyncio
    async def test_route_by_latency_low_requirement(self) -> None:
        adapter = HybridAI()
        criteria = RoutingCriteria(max_latency_ms=400)

        result = await adapter._route_by_latency(criteria, 1000, 200)

        assert result.decision == RoutingDecision.EDGE
        assert result.strategy == DeploymentStrategy.EDGE
        assert result.confidence == 0.9

    @pytest.mark.asyncio
    async def test_route_by_latency_edge_faster(self) -> None:
        adapter = HybridAI()
        criteria = RoutingCriteria(max_latency_ms=2000)

        # Edge significantly faster (200ms vs 1000ms)
        result = await adapter._route_by_latency(criteria, 1000, 200)

        assert result.decision == RoutingDecision.EDGE
        assert result.strategy == DeploymentStrategy.EDGE

    @pytest.mark.asyncio
    async def test_route_by_cost_very_low_requirement(self) -> None:
        adapter = HybridAI()
        criteria = RoutingCriteria(max_cost_per_token=0.0000001)
        request = AIRequest(prompt="Test")

        result = await adapter._route_by_cost(criteria, request)

        assert result.decision == RoutingDecision.EDGE
        assert result.confidence == 0.95

    @pytest.mark.asyncio
    async def test_route_by_cost_large_response(self) -> None:
        adapter = HybridAI()
        criteria = RoutingCriteria()
        request = AIRequest(prompt="Test", max_tokens=2000)

        result = await adapter._route_by_cost(criteria, request)

        assert result.decision == RoutingDecision.EDGE
        assert "Large response size" in result.reasoning

    @pytest.mark.asyncio
    async def test_route_by_quality_advanced_capabilities(self) -> None:
        adapter = HybridAI()
        criteria = RoutingCriteria(
            model_capabilities=[
                ModelCapability.FUNCTION_CALLING,
                ModelCapability.VISION,
            ]
        )
        request = AIRequest(prompt="Test")

        result = await adapter._route_by_quality(criteria, request)

        assert result.decision == RoutingDecision.CLOUD
        assert result.confidence == 0.9

    @pytest.mark.asyncio
    async def test_route_by_quality_high_requirement(self) -> None:
        adapter = HybridAI()
        criteria = RoutingCriteria(min_quality_score=0.95)
        request = AIRequest(prompt="Test")

        result = await adapter._route_by_quality(criteria, request)

        assert result.decision == RoutingDecision.CLOUD
        assert "High quality requirement" in result.reasoning

    @pytest.mark.asyncio
    async def test_route_by_performance_edge_wins(self) -> None:
        adapter = HybridAI()
        criteria = RoutingCriteria(max_latency_ms=400)

        # Edge has better performance score
        result = await adapter._route_by_performance(criteria, 1000, 200, 0.95, 0.98)

        assert result.decision == RoutingDecision.EDGE

    @pytest.mark.asyncio
    async def test_route_by_performance_privacy_requirement(self) -> None:
        adapter = HybridAI()
        criteria = RoutingCriteria(requires_privacy=True)

        result = await adapter._route_by_performance(criteria, 1000, 200, 0.99, 0.95)

        assert result.decision == RoutingDecision.EDGE  # Privacy boosts edge score

    @pytest.mark.asyncio
    async def test_route_by_availability_edge_only(self) -> None:
        adapter = HybridAI()

        with (
            patch.object(adapter, "_check_cloud_availability", return_value=False),
            patch.object(adapter, "_check_edge_availability", return_value=True),
        ):
            criteria = RoutingCriteria()
            result = await adapter._route_by_availability(criteria)

            assert result.decision == RoutingDecision.EDGE
            assert "Cloud unavailable" in result.reasoning

    @pytest.mark.asyncio
    async def test_route_by_availability_cloud_only(self) -> None:
        adapter = HybridAI()

        with (
            patch.object(adapter, "_check_cloud_availability", return_value=True),
            patch.object(adapter, "_check_edge_availability", return_value=False),
        ):
            criteria = RoutingCriteria()
            result = await adapter._route_by_availability(criteria)

            assert result.decision == RoutingDecision.CLOUD
            assert "Edge unavailable" in result.reasoning

    @pytest.mark.asyncio
    async def test_route_by_availability_none_available(self) -> None:
        adapter = HybridAI()

        with (
            patch.object(adapter, "_check_cloud_availability", return_value=False),
            patch.object(adapter, "_check_edge_availability", return_value=False),
        ):
            criteria = RoutingCriteria()

            with pytest.raises(
                RuntimeError, match="Neither cloud nor edge deployment available"
            ):
                await adapter._route_by_availability(criteria)

    @pytest.mark.asyncio
    async def test_route_adaptive_no_history(self) -> None:
        adapter = HybridAI()
        adapter._routing_history = []

        criteria = RoutingCriteria()
        request = AIRequest(prompt="Test")

        result = await adapter._route_adaptive(criteria, request)

        # Should fall back to performance routing
        assert result.decision in [RoutingDecision.CLOUD, RoutingDecision.EDGE]

    @pytest.mark.asyncio
    async def test_route_adaptive_with_history(self) -> None:
        adapter = HybridAI()
        adapter._routing_history = [
            {"strategy": "edge", "success": True},
            {"strategy": "edge", "success": True},
            {"strategy": "cloud", "success": False},
        ]

        criteria = RoutingCriteria()
        request = AIRequest(prompt="Test")

        result = await adapter._route_adaptive(criteria, request)

        assert result.decision == RoutingDecision.EDGE  # Edge has better success rate

    @pytest.mark.asyncio
    async def test_execute_cloud_request(self, mock_cloud_adapter: MagicMock) -> None:
        adapter = HybridAI()
        adapter._cloud_adapter = mock_cloud_adapter

        request = AIRequest(prompt="Test")
        routing = RoutingResult(
            decision=RoutingDecision.CLOUD,
            strategy=DeploymentStrategy.CLOUD,
            model="gpt-4",
            confidence=0.8,
            reasoning="Test",
        )

        response = await adapter._execute_cloud_request(request, routing)

        assert response.content == "Cloud response"
        assert response.provider == ModelProvider.OPENAI

    @pytest.mark.asyncio
    async def test_execute_edge_request(self, mock_edge_adapter: MagicMock) -> None:
        adapter = HybridAI()
        adapter._edge_adapter = mock_edge_adapter

        request = AIRequest(prompt="Test", max_tokens=1000)  # Will be limited
        routing = RoutingResult(
            decision=RoutingDecision.EDGE,
            strategy=DeploymentStrategy.EDGE,
            model="llama2:7b",
            confidence=0.8,
            reasoning="Test",
        )

        response = await adapter._execute_edge_request(request, routing)

        assert response.content == "Edge response"
        assert response.provider == ModelProvider.OLLAMA

        # Check that max_tokens was limited for edge
        call_args = mock_edge_adapter._generate_text.call_args[0][0]
        assert call_args.max_tokens <= 512  # Edge limits

    @pytest.mark.asyncio
    async def test_handle_fallback_cloud_to_edge(
        self, mock_cloud_adapter: MagicMock, mock_edge_adapter: MagicMock
    ) -> None:
        adapter = HybridAI(edge_fallback_enabled=True)
        adapter._cloud_adapter = mock_cloud_adapter
        adapter._edge_adapter = mock_edge_adapter

        request = AIRequest(prompt="Test")
        routing = RoutingResult(
            decision=RoutingDecision.CLOUD,
            strategy=DeploymentStrategy.CLOUD,
            model="gpt-4",
            confidence=0.8,
            reasoning="Test",
        )
        error = Exception("Cloud failed")

        response = await adapter._handle_fallback(request, routing, error)

        assert response.content == "Edge response"
        mock_edge_adapter._generate_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_fallback_edge_to_cloud(
        self, mock_cloud_adapter: MagicMock, mock_edge_adapter: MagicMock
    ) -> None:
        adapter = HybridAI(cloud_fallback_enabled=True)
        adapter._cloud_adapter = mock_cloud_adapter
        adapter._edge_adapter = mock_edge_adapter

        request = AIRequest(prompt="Test")
        routing = RoutingResult(
            decision=RoutingDecision.EDGE,
            strategy=DeploymentStrategy.EDGE,
            model="llama2:7b",
            confidence=0.8,
            reasoning="Test",
        )
        error = Exception("Edge failed")

        response = await adapter._handle_fallback(request, routing, error)

        assert response.content == "Cloud response"
        mock_cloud_adapter._generate_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_fallback_no_fallback_enabled(self) -> None:
        adapter = HybridAI(cloud_fallback_enabled=False, edge_fallback_enabled=False)

        request = AIRequest(prompt="Test")
        routing = RoutingResult(
            decision=RoutingDecision.CLOUD,
            strategy=DeploymentStrategy.CLOUD,
            model="gpt-4",
            confidence=0.8,
            reasoning="Test",
        )
        error = Exception("Primary failed")

        with pytest.raises(Exception, match="Primary failed"):
            await adapter._handle_fallback(request, routing, error)

    @pytest.mark.asyncio
    async def test_check_cloud_availability(
        self, mock_cloud_adapter: MagicMock
    ) -> None:
        adapter = HybridAI()
        adapter._cloud_adapter = mock_cloud_adapter

        available = await adapter._check_cloud_availability()
        assert available

    @pytest.mark.asyncio
    async def test_check_edge_availability(self, mock_edge_adapter: MagicMock) -> None:
        adapter = HybridAI()
        adapter._edge_adapter = mock_edge_adapter

        available = await adapter._check_edge_availability()
        assert available

    @pytest.mark.asyncio
    async def test_track_performance(self) -> None:
        adapter = HybridAI(track_performance=True)
        routing = RoutingResult(
            decision=RoutingDecision.EDGE,
            strategy=DeploymentStrategy.EDGE,
            model="llama2:7b",
            confidence=0.8,
            reasoning="Test",
        )

        await adapter._track_performance(routing, 150, True)

        # Check metrics were recorded
        assert len(adapter._performance_metrics["edge_latency"]) == 1
        assert adapter._performance_metrics["edge_latency"][0] == 150
        assert len(adapter._performance_metrics["edge_success_rate"]) == 1
        assert adapter._performance_metrics["edge_success_rate"][0] == 1.0

        # Check history was recorded
        assert len(adapter._routing_history) == 1
        history = adapter._routing_history[0]
        assert history["strategy"] == "edge"
        assert history["success"]

    @pytest.mark.asyncio
    async def test_get_average_metric(self) -> None:
        adapter = HybridAI()
        adapter._performance_metrics["test_metric"] = [100, 200, 300]

        avg = adapter._get_average_metric("test_metric", 0)
        assert avg == 200

        # Test with empty metric
        avg = adapter._get_average_metric("empty_metric", 42)
        assert avg == 42

    @pytest.mark.asyncio
    async def test_get_routing_stats(self) -> None:
        adapter = HybridAI()
        adapter._routing_history = [
            {
                "strategy": "edge",
                "decision": "edge",
                "success": True,
                "latency_ms": 150,
            }
        ]
        adapter._performance_metrics["edge_latency"] = [150, 200]

        stats = await adapter.get_routing_stats()

        assert stats["routing_strategy"] == RoutingStrategy.PERFORMANCE
        assert stats["routing_history_size"] == 1
        assert "performance_metrics" in stats
        assert "recent_decisions" in stats

    @pytest.mark.asyncio
    async def test_generate_text_with_routing(
        self, mock_cloud_adapter: MagicMock, mock_edge_adapter: MagicMock
    ) -> None:
        with (
            patch("acb.adapters.ai.hybrid.validate_request") as mock_validate,
            patch("acb.adapters.ai.hybrid.CloudAI") as mock_cloud_ai,
            patch("acb.adapters.ai.hybrid.EdgeAI") as mock_edge_ai,
        ):
            mock_validate.return_value = None
            mock_cloud_ai.return_value = mock_cloud_adapter
            mock_edge_ai.return_value = mock_edge_adapter

            adapter = HybridAI(routing_strategy=RoutingStrategy.LATENCY)
            await adapter._ensure_client()

            request = AIRequest(
                prompt="Test", max_latency_ms=400
            )  # Should route to edge
            await adapter._generate_text(request)

            # Should route to edge for low latency
            mock_edge_adapter._generate_text.assert_called_once()

    def test_module_metadata(self) -> None:
        """Test that module metadata is properly configured."""
        assert MODULE_METADATA.name == "Hybrid AI"
        assert MODULE_METADATA.category == "ai"
        assert MODULE_METADATA.provider == "hybrid"
        assert "openai>=1.0.0" in MODULE_METADATA.required_packages
        assert "ollama>=0.1.0" in MODULE_METADATA.required_packages
