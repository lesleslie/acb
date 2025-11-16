"""Hybrid deployment strategy with intelligent routing between cloud and edge."""

from enum import Enum
from uuid import UUID

import asyncio
import typing as t
from dataclasses import dataclass
from pydantic import Field

from acb.adapters import AdapterCapability, AdapterMetadata, AdapterStatus
from acb.depends import depends

from ._base import (
    AIBase,
    AIBaseSettings,
    AIRequest,
    AIResponse,
    DeploymentStrategy,
    ModelCapability,
    ModelInfo,
    ModelProvider,
    StreamingResponse,
    validate_request,
)
from .cloud import CloudAI
from .edge import EdgeAI

MODULE_ID = UUID("0197ff44-8c12-7f30-af61-2d41c6c89a75")
MODULE_STATUS = AdapterStatus.STABLE

MODULE_METADATA = AdapterMetadata(
    module_id=MODULE_ID,
    name="Hybrid AI",
    category="ai",
    provider="hybrid",
    version="1.0.0",
    acb_min_version="0.19.0",
    author="lesleslie <les@wedgwoodwebworks.com>",
    created_date="2025-01-15",
    last_modified="2025-01-15",
    status=MODULE_STATUS,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.STREAMING,
        AdapterCapability.HYBRID_DEPLOYMENT,
        AdapterCapability.ADAPTIVE_ROUTING,
        AdapterCapability.FALLBACK_MECHANISMS,
        AdapterCapability.EDGE_INFERENCE,
        AdapterCapability.TEXT_GENERATION,
        AdapterCapability.VISION_PROCESSING,
        AdapterCapability.AUDIO_PROCESSING,
        AdapterCapability.MULTIMODAL_PROCESSING,
        AdapterCapability.PROMPT_TEMPLATING,
        AdapterCapability.MODEL_CACHING,
        AdapterCapability.COLD_START_OPTIMIZATION,
    ],
    required_packages=[
        "openai>=1.0.0",
        "anthropic>=0.5.0",
        "ollama>=0.1.0",
        "httpx[http2]>=0.28.0",
        "onnx>=1.14.0",
        "onnxruntime>=1.16.0",
    ],
    description="Hybrid AI adapter with intelligent routing between cloud and edge based on constraints and performance",
    settings_class="HybridAISettings",
    config_example={
        "cloud_provider": "openai",
        "edge_provider": "ollama",
        "routing_strategy": "performance",
        "latency_threshold_ms": 1000,
        "cost_threshold_per_token": 0.00001,
        "fallback_enabled": True,
    },
)


class RoutingStrategy(str, Enum):
    """Routing strategies for hybrid deployment."""

    LATENCY = "latency"  # Route based on latency requirements
    COST = "cost"  # Route based on cost optimization
    QUALITY = "quality"  # Route based on model quality/capabilities
    PERFORMANCE = "performance"  # Route based on overall performance
    AVAILABILITY = "availability"  # Route based on provider availability
    ADAPTIVE = "adaptive"  # Learn and adapt routing decisions


class RoutingDecision(str, Enum):
    """Routing decision outcomes."""

    CLOUD = "cloud"
    EDGE = "edge"
    FALLBACK_TO_CLOUD = "fallback_to_cloud"
    FALLBACK_TO_EDGE = "fallback_to_edge"


@dataclass
class RoutingCriteria:
    """Criteria for routing decisions."""

    max_latency_ms: int | None = None
    max_cost_per_token: float | None = None
    min_quality_score: float | None = None
    memory_budget_mb: int | None = None
    requires_privacy: bool = False
    requires_offline: bool = False
    model_capabilities: list[ModelCapability] | None = None
    preferred_strategy: DeploymentStrategy | None = None


@dataclass
class RoutingResult:
    """Result of routing decision."""

    decision: RoutingDecision
    strategy: DeploymentStrategy
    model: str
    confidence: float
    reasoning: str
    estimated_latency_ms: int | None = None
    estimated_cost: float | None = None


class HybridAISettings(AIBaseSettings):
    """Settings for hybrid AI deployment."""

    # Routing configuration
    routing_strategy: RoutingStrategy = RoutingStrategy.PERFORMANCE
    enable_adaptive_routing: bool = True
    routing_history_size: int = 100

    # Thresholds for routing decisions
    latency_threshold_ms: int = 1000
    cost_threshold_per_token: float = 0.00001
    quality_threshold: float = 0.8
    memory_threshold_mb: int = 512

    # Cloud provider settings
    cloud_provider: ModelProvider = ModelProvider.OPENAI
    cloud_fallback_enabled: bool = True
    cloud_timeout_ms: int = 30000

    # Edge provider settings
    edge_provider: ModelProvider = ModelProvider.OLLAMA
    edge_fallback_enabled: bool = True
    edge_timeout_ms: int = 5000

    # Model mapping
    cloud_models: dict[str, str] = Field(
        default_factory=lambda: {
            "fast": "gpt-3.5-turbo",
            "smart": "gpt-4",
            "vision": "gpt-4-vision-preview",
        },
    )

    edge_models: dict[str, str] = Field(
        default_factory=lambda: {
            "fast": "llama2:7b",
            "smart": "lfm2",
            "vision": "lfm2-vl",
        },
    )

    # Performance tracking
    track_performance: bool = True
    performance_window_minutes: int = 60
    auto_optimization: bool = True


class HybridAI(AIBase):
    """Hybrid AI adapter with intelligent routing."""

    def __init__(self, **kwargs: t.Any) -> None:
        super().__init__(**kwargs)
        self._settings = HybridAISettings(**kwargs)

        # Initialize cloud and edge adapters
        self._cloud_adapter: CloudAI | None = None
        self._edge_adapter: EdgeAI | None = None

        # Performance tracking
        self._routing_history: list[dict[str, t.Any]] = []
        self._performance_metrics: dict[str, list[float]] = {
            "cloud_latency": [],
            "edge_latency": [],
            "cloud_success_rate": [],
            "edge_success_rate": [],
        }

    @property
    def settings(self) -> HybridAISettings:
        """Get adapter settings with correct type."""
        if self._settings is None:
            msg = "Settings not initialized"
            raise RuntimeError(msg)
        return self._settings  # type: ignore[return-value]

    async def _create_client(self) -> t.Any:
        """Initialize cloud and edge clients."""
        # Initialize cloud adapter
        cloud_kwargs = {
            "provider": self.settings.cloud_provider,
            "api_key": self.settings.api_key,
            "base_url": self.settings.base_url,
            "default_model": self.settings.default_model,
            "timeout_seconds": self.settings.cloud_timeout_ms / 1000,
        }
        self._cloud_adapter = CloudAI(**cloud_kwargs)

        # Initialize edge adapter
        edge_kwargs = {
            "provider": self.settings.edge_provider,
            "default_model": self.settings.default_model,
            "memory_budget_mb": self.settings.memory_threshold_mb,
            "cold_start_optimization": True,
        }
        self._edge_adapter = EdgeAI(**edge_kwargs)

        # Register both adapters for cleanup
        self.register_resource(self._cloud_adapter)
        self.register_resource(self._edge_adapter)

        return {"cloud": self._cloud_adapter, "edge": self._edge_adapter}

    async def _generate_text(self, request: AIRequest) -> AIResponse:
        """Generate text with intelligent routing."""
        await validate_request(request)
        await self._ensure_client()

        # Determine routing criteria
        criteria = self._extract_routing_criteria(request)

        # Make routing decision
        routing_result = await self._route_request(criteria, request)

        self._log_info(
            f"Routing decision: {routing_result.decision} "
            f"(confidence: {routing_result.confidence:.2f}) - {routing_result.reasoning}",
        )

        # Execute request with selected adapter
        start_time = asyncio.get_event_loop().time()
        try:
            if routing_result.strategy == DeploymentStrategy.CLOUD:
                response = await self._execute_cloud_request(request, routing_result)
            elif routing_result.strategy == DeploymentStrategy.EDGE:
                response = await self._execute_edge_request(request, routing_result)
            else:
                msg = f"Unsupported strategy: {routing_result.strategy}"
                raise ValueError(msg)

            # Track performance
            latency_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            await self._track_performance(routing_result, latency_ms, True)

            return response

        except Exception as e:
            # Handle fallback
            latency_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            await self._track_performance(routing_result, latency_ms, False)

            return await self._handle_fallback(request, routing_result, e)

    async def _generate_text_stream(self, request: AIRequest) -> StreamingResponse:
        """Generate streaming text with routing."""
        await validate_request(request)
        await self._ensure_client()

        criteria = self._extract_routing_criteria(request)
        routing_result = await self._route_request(criteria, request)

        self._log_info(f"Streaming routing: {routing_result.decision}")

        try:
            return await self._execute_streaming_strategy(routing_result, request)
        except Exception as e:
            return await self._handle_streaming_fallback(routing_result, request, e)

    async def _execute_streaming_strategy(
        self, routing_result: RoutingResult, request: AIRequest
    ) -> StreamingResponse:
        """Execute streaming request with selected strategy."""
        if routing_result.strategy == DeploymentStrategy.CLOUD:
            if self._cloud_adapter is None:
                msg = "Cloud adapter not initialized"
                raise ValueError(msg)
            return await self._cloud_adapter.generate_text_stream(request)

        if routing_result.strategy == DeploymentStrategy.EDGE:
            if self._edge_adapter is None:
                msg = "Edge adapter not initialized"
                raise ValueError(msg)
            return await self._edge_adapter.generate_text_stream(request)

        msg = f"Unsupported streaming strategy: {routing_result.strategy}"
        raise ValueError(msg)

    async def _handle_streaming_fallback(
        self, routing_result: RoutingResult, request: AIRequest, error: Exception
    ) -> StreamingResponse:
        """Handle fallback when streaming fails."""
        self._log_warning(f"Streaming failed, attempting fallback: {error}")

        fallback_strategy = (
            DeploymentStrategy.EDGE
            if routing_result.strategy == DeploymentStrategy.CLOUD
            else DeploymentStrategy.CLOUD
        )

        if fallback_strategy == DeploymentStrategy.CLOUD:
            return await self._try_cloud_fallback(request)

        if fallback_strategy == DeploymentStrategy.EDGE:
            return await self._try_edge_fallback(request)

        raise error

    async def _try_cloud_fallback(self, request: AIRequest) -> StreamingResponse:
        """Try cloud fallback for streaming."""
        if not self.settings.cloud_fallback_enabled:
            msg = "Cloud fallback not enabled"
            raise ValueError(msg)

        if self._cloud_adapter is None:
            msg = "Cloud adapter not initialized"
            raise ValueError(msg)

        return await self._cloud_adapter.generate_text_stream(request)

    async def _try_edge_fallback(self, request: AIRequest) -> StreamingResponse:
        """Try edge fallback for streaming."""
        if not self.settings.edge_fallback_enabled:
            msg = "Edge fallback not enabled"
            raise ValueError(msg)

        if self._edge_adapter is None:
            msg = "Edge adapter not initialized"
            raise ValueError(msg)

        return await self._edge_adapter.generate_text_stream(request)

    async def _route_request(
        self,
        criteria: RoutingCriteria,
        request: AIRequest,
    ) -> RoutingResult:
        """Make intelligent routing decision."""
        # Get current performance metrics
        cloud_avg_latency = self._get_average_metric("cloud_latency", 1000)
        edge_avg_latency = self._get_average_metric("edge_latency", 200)

        cloud_success_rate = self._get_average_metric("cloud_success_rate", 0.99)
        edge_success_rate = self._get_average_metric("edge_success_rate", 0.95)

        # Routing logic based on strategy
        if self.settings.routing_strategy == RoutingStrategy.LATENCY:
            return await self._route_by_latency(
                criteria,
                cloud_avg_latency,
                edge_avg_latency,
            )

        if self.settings.routing_strategy == RoutingStrategy.COST:
            return await self._route_by_cost(criteria, request)

        if self.settings.routing_strategy == RoutingStrategy.QUALITY:
            return await self._route_by_quality(criteria, request)

        if self.settings.routing_strategy == RoutingStrategy.PERFORMANCE:
            return await self._route_by_performance(
                criteria,
                cloud_avg_latency,
                edge_avg_latency,
                cloud_success_rate,
                edge_success_rate,
            )

        if self.settings.routing_strategy == RoutingStrategy.AVAILABILITY:
            return await self._route_by_availability(criteria)

        if self.settings.routing_strategy == RoutingStrategy.ADAPTIVE:
            return await self._route_adaptive(criteria, request)

        # Default to performance routing
        return await self._route_by_performance(
            criteria,
            cloud_avg_latency,
            edge_avg_latency,
            cloud_success_rate,
            edge_success_rate,
        )

    async def _route_by_latency(
        self,
        criteria: RoutingCriteria,
        cloud_latency: float,
        edge_latency: float,
    ) -> RoutingResult:
        """Route based on latency requirements."""
        if criteria.max_latency_ms and criteria.max_latency_ms < 500:
            # Very low latency requirement - prefer edge
            return RoutingResult(
                decision=RoutingDecision.EDGE,
                strategy=DeploymentStrategy.EDGE,
                model=self.settings.edge_models.get("fast", "llama2:7b"),
                confidence=0.9,
                reasoning="Low latency requirement (<500ms) favors edge deployment",
                estimated_latency_ms=int(edge_latency),
            )

        if edge_latency < cloud_latency * 0.5:
            # Edge is significantly faster
            return RoutingResult(
                decision=RoutingDecision.EDGE,
                strategy=DeploymentStrategy.EDGE,
                model=self.settings.edge_models.get("fast", "llama2:7b"),
                confidence=0.8,
                reasoning=f"Edge latency ({edge_latency}ms) significantly better than cloud ({cloud_latency}ms)",
                estimated_latency_ms=int(edge_latency),
            )

        # Default to cloud for general latency requirements
        return RoutingResult(
            decision=RoutingDecision.CLOUD,
            strategy=DeploymentStrategy.CLOUD,
            model=self.settings.cloud_models.get("fast", "gpt-3.5-turbo"),
            confidence=0.7,
            reasoning="Cloud provides reliable latency for general use",
            estimated_latency_ms=int(cloud_latency),
        )

    async def _route_by_cost(
        self,
        criteria: RoutingCriteria,
        request: AIRequest,
    ) -> RoutingResult:
        """Route based on cost optimization."""
        if criteria.max_cost_per_token and criteria.max_cost_per_token < 0.000001:
            # Very low cost requirement - edge is essentially free
            return RoutingResult(
                decision=RoutingDecision.EDGE,
                strategy=DeploymentStrategy.EDGE,
                model=self.settings.edge_models.get("fast", "llama2:7b"),
                confidence=0.95,
                reasoning="Very low cost requirement favors edge deployment (near-zero cost)",
                estimated_cost=0.0,
            )

        if request.max_tokens > 1000:
            # Large response - edge saves significant cost
            return RoutingResult(
                decision=RoutingDecision.EDGE,
                strategy=DeploymentStrategy.EDGE,
                model=self.settings.edge_models.get("smart", "lfm2"),
                confidence=0.8,
                reasoning="Large response size makes edge more cost-effective",
                estimated_cost=0.0,
            )

        # Balance cost and quality
        return RoutingResult(
            decision=RoutingDecision.CLOUD,
            strategy=DeploymentStrategy.CLOUD,
            model=self.settings.cloud_models.get("fast", "gpt-3.5-turbo"),
            confidence=0.6,
            reasoning="Balanced cost-quality trade-off favors cloud",
        )

    async def _route_by_quality(
        self,
        criteria: RoutingCriteria,
        request: AIRequest,
    ) -> RoutingResult:
        """Route based on model quality requirements."""
        requires_advanced_capabilities = False

        if criteria.model_capabilities:
            advanced_caps = {
                ModelCapability.FUNCTION_CALLING,
                ModelCapability.VISION,
                ModelCapability.CODE_GENERATION,
            }
            requires_advanced_capabilities = bool(
                set(criteria.model_capabilities) & advanced_caps,
            )

        if requires_advanced_capabilities:
            return RoutingResult(
                decision=RoutingDecision.CLOUD,
                strategy=DeploymentStrategy.CLOUD,
                model=self.settings.cloud_models.get("smart", "gpt-4"),
                confidence=0.9,
                reasoning="Advanced capabilities require cloud deployment",
            )

        if criteria.min_quality_score and criteria.min_quality_score > 0.9:
            return RoutingResult(
                decision=RoutingDecision.CLOUD,
                strategy=DeploymentStrategy.CLOUD,
                model=self.settings.cloud_models.get("smart", "gpt-4"),
                confidence=0.85,
                reasoning="High quality requirement favors cloud models",
            )

        # Edge can handle general quality requirements
        return RoutingResult(
            decision=RoutingDecision.EDGE,
            strategy=DeploymentStrategy.EDGE,
            model=self.settings.edge_models.get("smart", "lfm2"),
            confidence=0.7,
            reasoning="General quality requirements can be met by edge models",
        )

    async def _route_by_performance(
        self,
        criteria: RoutingCriteria,
        cloud_latency: float,
        edge_latency: float,
        cloud_success: float,
        edge_success: float,
    ) -> RoutingResult:
        """Route based on overall performance metrics."""
        # Calculate performance scores
        cloud_score = (1 / cloud_latency) * cloud_success * 1000
        edge_score = (1 / edge_latency) * edge_success * 1000

        # Apply criteria weights
        if criteria.max_latency_ms and criteria.max_latency_ms < 500:
            edge_score *= 1.5  # Boost edge for low latency

        if criteria.memory_budget_mb and criteria.memory_budget_mb < 512:
            edge_score *= 1.3  # Boost edge for memory constraints

        if criteria.requires_privacy or criteria.requires_offline:
            edge_score *= 2.0  # Strong preference for edge

        if edge_score > cloud_score:
            return RoutingResult(
                decision=RoutingDecision.EDGE,
                strategy=DeploymentStrategy.EDGE,
                model=self.settings.edge_models.get("fast", "llama2:7b"),
                confidence=min(0.95, edge_score / (cloud_score + edge_score)),
                reasoning=f"Edge performance score ({edge_score:.2f}) better than cloud ({cloud_score:.2f})",
                estimated_latency_ms=int(edge_latency),
            )
        return RoutingResult(
            decision=RoutingDecision.CLOUD,
            strategy=DeploymentStrategy.CLOUD,
            model=self.settings.cloud_models.get("fast", "gpt-3.5-turbo"),
            confidence=min(0.95, cloud_score / (cloud_score + edge_score)),
            reasoning=f"Cloud performance score ({cloud_score:.2f}) better than edge ({edge_score:.2f})",
            estimated_latency_ms=int(cloud_latency),
        )

    async def _route_by_availability(self, criteria: RoutingCriteria) -> RoutingResult:
        """Route based on provider availability."""
        # Check cloud availability
        cloud_available = await self._check_cloud_availability()
        edge_available = await self._check_edge_availability()

        if edge_available and not cloud_available:
            return RoutingResult(
                decision=RoutingDecision.EDGE,
                strategy=DeploymentStrategy.EDGE,
                model=self.settings.edge_models.get("fast", "llama2:7b"),
                confidence=0.9,
                reasoning="Cloud unavailable, routing to edge",
            )
        if cloud_available and not edge_available:
            return RoutingResult(
                decision=RoutingDecision.CLOUD,
                strategy=DeploymentStrategy.CLOUD,
                model=self.settings.cloud_models.get("fast", "gpt-3.5-turbo"),
                confidence=0.9,
                reasoning="Edge unavailable, routing to cloud",
            )
        if edge_available and cloud_available:
            # Both available, prefer edge for lower dependency
            return RoutingResult(
                decision=RoutingDecision.EDGE,
                strategy=DeploymentStrategy.EDGE,
                model=self.settings.edge_models.get("fast", "llama2:7b"),
                confidence=0.7,
                reasoning="Both available, preferring edge for independence",
            )
        msg = "Neither cloud nor edge deployment available"
        raise RuntimeError(msg)

    async def _route_adaptive(
        self,
        criteria: RoutingCriteria,
        request: AIRequest,
    ) -> RoutingResult:
        """Adaptive routing based on learning from history."""
        # Simplified adaptive logic - would use ML in production
        recent_history = self._routing_history[-10:] if self._routing_history else []

        if not recent_history:
            # No history, use performance routing
            return await self._route_by_performance(criteria, 1000, 200, 0.99, 0.95)

        # Analyze recent successes
        edge_successes = sum(
            1 for h in recent_history if h["strategy"] == "edge" and h["success"]
        )
        cloud_successes = sum(
            1 for h in recent_history if h["strategy"] == "cloud" and h["success"]
        )

        total_edge = sum(1 for h in recent_history if h["strategy"] == "edge")
        total_cloud = sum(1 for h in recent_history if h["strategy"] == "cloud")

        edge_success_rate = edge_successes / max(total_edge, 1)
        cloud_success_rate = cloud_successes / max(total_cloud, 1)

        if edge_success_rate > cloud_success_rate:
            return RoutingResult(
                decision=RoutingDecision.EDGE,
                strategy=DeploymentStrategy.EDGE,
                model=self.settings.edge_models.get("fast", "llama2:7b"),
                confidence=edge_success_rate,
                reasoning=f"Adaptive learning favors edge (success rate: {edge_success_rate:.2f})",
            )
        return RoutingResult(
            decision=RoutingDecision.CLOUD,
            strategy=DeploymentStrategy.CLOUD,
            model=self.settings.cloud_models.get("fast", "gpt-3.5-turbo"),
            confidence=cloud_success_rate,
            reasoning=f"Adaptive learning favors cloud (success rate: {cloud_success_rate:.2f})",
        )

    async def _execute_cloud_request(
        self,
        request: AIRequest,
        routing: RoutingResult,
    ) -> AIResponse:
        """Execute request using cloud adapter."""
        if not self._cloud_adapter:
            msg = "Cloud adapter not initialized"
            raise RuntimeError(msg)

        # Override model if routing specified one
        if routing.model != request.model:
            request = AIRequest(
                prompt=request.prompt,
                model=routing.model,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                stream=request.stream,
                system_prompt=request.system_prompt,
                function_definitions=request.function_definitions,
                images=request.images,
                audio=request.audio,
                response_format=request.response_format,
            )

        return await self._cloud_adapter._generate_text(request)

    async def _execute_edge_request(
        self,
        request: AIRequest,
        routing: RoutingResult,
    ) -> AIResponse:
        """Execute request using edge adapter."""
        if not self._edge_adapter:
            msg = "Edge adapter not initialized"
            raise RuntimeError(msg)

        # Override model if routing specified one
        if routing.model != request.model:
            request = AIRequest(
                prompt=request.prompt,
                model=routing.model,
                max_tokens=min(request.max_tokens, 512),  # Edge limits
                temperature=request.temperature,
                stream=request.stream,
                system_prompt=request.system_prompt,
                response_format=request.response_format,
            )

        return await self._edge_adapter._generate_text(request)

    async def _handle_fallback(
        self,
        request: AIRequest,
        routing: RoutingResult,
        error: Exception,
    ) -> AIResponse:
        """Handle fallback when primary strategy fails."""
        self._log_warning(f"Primary strategy {routing.strategy} failed: {error}")

        if (
            routing.strategy == DeploymentStrategy.CLOUD
            and self.settings.edge_fallback_enabled
        ):
            self._log_info("Falling back to edge deployment")
            edge_routing = RoutingResult(
                decision=RoutingDecision.FALLBACK_TO_EDGE,
                strategy=DeploymentStrategy.EDGE,
                model=self.settings.edge_models.get("fast", "llama2:7b"),
                confidence=0.5,
                reasoning="Fallback to edge after cloud failure",
            )
            return await self._execute_edge_request(request, edge_routing)

        if (
            routing.strategy == DeploymentStrategy.EDGE
            and self.settings.cloud_fallback_enabled
        ):
            self._log_info("Falling back to cloud deployment")
            cloud_routing = RoutingResult(
                decision=RoutingDecision.FALLBACK_TO_CLOUD,
                strategy=DeploymentStrategy.CLOUD,
                model=self.settings.cloud_models.get("fast", "gpt-3.5-turbo"),
                confidence=0.5,
                reasoning="Fallback to cloud after edge failure",
            )
            return await self._execute_cloud_request(request, cloud_routing)

        # No fallback available
        raise error

    async def _check_cloud_availability(self) -> bool:
        """Check if cloud provider is available."""
        try:
            if self._cloud_adapter:
                health = await self._cloud_adapter.health_check()
                return health.get("status") == "healthy"
            return False
        except Exception:
            return False

    async def _check_edge_availability(self) -> bool:
        """Check if edge provider is available."""
        try:
            if self._edge_adapter:
                health = await self._edge_adapter.health_check()
                return health.get("status") == "healthy"
            return False
        except Exception:
            return False

    def _extract_routing_criteria(self, request: AIRequest) -> RoutingCriteria:
        """Extract routing criteria from request."""
        return RoutingCriteria(
            max_latency_ms=request.max_latency_ms,
            max_cost_per_token=getattr(request, "max_cost_per_token", None),
            min_quality_score=request.min_quality_score,
            memory_budget_mb=request.memory_budget_mb,
            requires_privacy=getattr(request, "requires_privacy", False),
            requires_offline=getattr(request, "requires_offline", False),
            preferred_strategy=request.preferred_strategy,
        )

    async def _track_performance(
        self,
        routing: RoutingResult,
        latency_ms: int,
        success: bool,
    ) -> None:
        """Track performance metrics for adaptive routing."""
        if not self.settings.track_performance:
            return

        # Track metrics by strategy
        strategy_key = f"{routing.strategy.value}_latency"
        success_key = f"{routing.strategy.value}_success_rate"

        if strategy_key in self._performance_metrics:
            self._performance_metrics[strategy_key].append(latency_ms)
            self._performance_metrics[success_key].append(1.0 if success else 0.0)

            # Keep only recent metrics
            max_size = 100
            for key in self._performance_metrics:
                if len(self._performance_metrics[key]) > max_size:
                    self._performance_metrics[key] = self._performance_metrics[key][
                        -max_size:
                    ]

        # Track routing history
        history_entry = {
            "strategy": routing.strategy.value,
            "decision": routing.decision.value,
            "latency_ms": latency_ms,
            "success": success,
            "confidence": routing.confidence,
            "timestamp": asyncio.get_event_loop().time(),
        }

        self._routing_history.append(history_entry)

        # Keep only recent history
        if len(self._routing_history) > self.settings.routing_history_size:
            self._routing_history = self._routing_history[
                -self.settings.routing_history_size :
            ]

    def _get_average_metric(self, metric_key: str, default: float) -> float:
        """Get average of recent metric values."""
        values = self._performance_metrics.get(metric_key, [])
        return sum(values) / len(values) if values else default

    async def _get_available_models(self) -> list[ModelInfo]:
        """Get available models from both cloud and edge."""
        models = []

        if self._cloud_adapter:
            cloud_models = await self._cloud_adapter._get_available_models()
            for model in cloud_models:
                model.deployment_strategies = [
                    DeploymentStrategy.CLOUD,
                    DeploymentStrategy.HYBRID,
                ]
            models.extend(cloud_models)

        if self._edge_adapter:
            edge_models = await self._edge_adapter._get_available_models()
            for model in edge_models:
                model.deployment_strategies = [
                    DeploymentStrategy.EDGE,
                    DeploymentStrategy.HYBRID,
                ]
            models.extend(edge_models)

        return models

    async def get_routing_stats(self) -> dict[str, t.Any]:
        """Get routing statistics and performance metrics."""
        return {
            "routing_strategy": self.settings.routing_strategy,
            "routing_history_size": len(self._routing_history),
            "performance_metrics": {
                key: {
                    "count": len(values),
                    "average": sum(values) / len(values) if values else 0,
                    "min": min(values) if values else 0,
                    "max": max(values) if values else 0,
                }
                for key, values in self._performance_metrics.items()
            },
            "recent_decisions": [
                {
                    "strategy": h["strategy"],
                    "decision": h["decision"],
                    "success": h["success"],
                    "latency_ms": h["latency_ms"],
                }
                for h in self._routing_history[-10:]
            ],
        }


# Alias for backward compatibility and convention
Ai = HybridAI
AiSettings = HybridAISettings

depends.set(Ai, "hybrid")
