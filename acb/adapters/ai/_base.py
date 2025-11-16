"""Base AI adapter interface for unified AI/ML operations."""

from abc import ABC, abstractmethod
from enum import Enum

import typing as t
from asyncio import Event as AsyncEvent
from dataclasses import dataclass
from pydantic import BaseModel, Field, SecretStr

from acb.cleanup import CleanupMixin
from acb.config import Config, Settings
from acb.depends import Inject, depends
from acb.logger import Logger
from acb.ssl_config import SSLConfigMixin


class DeploymentStrategy(str, Enum):
    """AI deployment strategies."""

    CLOUD = "cloud"
    EDGE = "edge"
    HYBRID = "hybrid"


class ModelCapability(str, Enum):
    """AI model capabilities."""

    TEXT_GENERATION = "text_generation"
    TEXT_COMPLETION = "text_completion"
    CHAT_COMPLETION = "chat_completion"
    VISION = "vision"
    AUDIO = "audio"
    CODE_GENERATION = "code_generation"
    FUNCTION_CALLING = "function_calling"
    EMBEDDINGS = "embeddings"
    IMAGE_GENERATION = "image_generation"
    SPEECH_TO_TEXT = "speech_to_text"
    TEXT_TO_SPEECH = "text_to_speech"


class ModelProvider(str, Enum):
    """AI model providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE_OPENAI = "azure_openai"
    AWS_BEDROCK = "aws_bedrock"
    GOOGLE_VERTEX = "google_vertex"
    OLLAMA = "ollama"
    LIQUID_AI = "liquid_ai"
    HUGGINGFACE = "huggingface"
    LOCAL = "local"


@dataclass
class ModelInfo:
    """Model information and capabilities."""

    name: str
    provider: ModelProvider
    capabilities: list[ModelCapability]
    context_length: int
    cost_per_token: float | None = None
    deployment_strategies: list[DeploymentStrategy] | None = None
    memory_footprint_mb: int | None = None
    latency_p95_ms: int | None = None
    supports_streaming: bool = True
    supports_function_calling: bool = False
    max_tokens_per_request: int | None = None

    def __post_init__(self) -> None:
        if self.deployment_strategies is None:
            self.deployment_strategies = [DeploymentStrategy.CLOUD]


@dataclass
class AIRequest:
    """AI request with prompt and configuration."""

    prompt: str | list[dict[str, t.Any]]
    model: str | None = None
    max_tokens: int = 1000
    temperature: float = 0.7
    stream: bool = False
    system_prompt: str | None = None
    function_definitions: list[dict[str, t.Any]] | None = None
    images: list[str | bytes] | None = None
    audio: str | bytes | None = None
    response_format: str = "text"

    # Performance constraints for hybrid routing
    max_latency_ms: int | None = None
    min_quality_score: float | None = None
    memory_budget_mb: int | None = None
    preferred_strategy: DeploymentStrategy | None = None


@dataclass
class AIResponse:
    """AI response with metadata."""

    content: str
    model: str
    provider: ModelProvider
    strategy: DeploymentStrategy
    tokens_used: int | None = None
    latency_ms: int | None = None
    confidence_score: float | None = None
    finish_reason: str | None = None
    function_calls: list[dict[str, t.Any]] | None = None
    cost: float | None = None
    cached: bool = False


class StreamingResponse:
    """Streaming response handler for real-time AI responses."""

    def __init__(self, response_generator: t.AsyncGenerator[str]) -> None:
        self._generator = response_generator
        self._complete_response = ""
        self._stop_event = AsyncEvent()

    async def __aiter__(self) -> t.AsyncIterator[str]:
        """Async iterator for streaming chunks."""
        try:
            async for chunk in self._generator:
                if self._stop_event.is_set():
                    break
                self._complete_response += chunk
                yield chunk
        except Exception:
            self._stop_event.set()
            raise

    async def complete(self) -> str:
        """Get the complete response once streaming is finished."""
        async for _ in self:
            pass  # Consume all chunks
        return self._complete_response

    async def stop(self) -> None:
        """Stop the streaming response."""
        self._stop_event.set()


class PromptTemplate(BaseModel):
    """Template for AI prompts with versioning."""

    name: str
    template: str
    variables: list[str]
    version: str = "1.0.0"
    description: str = ""
    default_values: dict[str, t.Any] = Field(default_factory=dict)

    def render(self, **kwargs: t.Any) -> str:
        """Render template with provided variables."""
        # Merge default values with provided kwargs
        render_vars = self.default_values | kwargs

        # Validate all required variables are provided
        missing_vars = set(self.variables) - set(render_vars.keys())
        if missing_vars:
            msg = f"Missing template variables: {missing_vars}"
            raise ValueError(msg)

        return self.template.format(**render_vars)


class AIBaseSettings(Settings, SSLConfigMixin):
    """Base settings for AI adapters."""

    # Deployment configuration
    deployment_strategy: DeploymentStrategy = DeploymentStrategy.CLOUD
    fallback_strategy: DeploymentStrategy | None = None

    # Model configuration
    default_model: str = "gpt-4"
    max_tokens: int = 1000
    temperature: float = 0.7
    timeout_seconds: float = 30.0

    # Performance thresholds for hybrid routing
    max_latency_ms: int = 5000
    min_quality_score: float = 0.8
    memory_budget_mb: int = 1024

    # API configuration
    api_key: SecretStr | None = None
    base_url: str | None = None
    organization: str | None = None
    api_version: str | None = None

    # Connection settings
    max_connections: int = 50
    connect_timeout: float = 10.0
    read_timeout: float = 30.0
    retry_attempts: int = 3
    retry_delay: float = 1.0

    # Caching
    enable_caching: bool = True
    cache_ttl: int = 3600

    # Streaming
    enable_streaming: bool = True
    stream_buffer_size: int = 8192

    # SSL/TLS Configuration
    ssl_cert_path: str | None = None
    ssl_key_path: str | None = None
    ssl_ca_path: str | None = None
    ssl_verify_mode: str = "required"
    tls_version: str = "TLSv1.2"

    @depends.inject
    def __init__(self, config: Inject[Config], **values: t.Any) -> None:
        # Extract SSL configuration
        ssl_enabled = values.pop("ssl_enabled", False)
        ssl_cert_path = values.pop("ssl_cert_path", None)
        ssl_key_path = values.pop("ssl_key_path", None)
        ssl_ca_path = values.pop("ssl_ca_path", None)
        ssl_verify_mode = values.pop("ssl_verify_mode", "required")
        values.pop("tls_version", "TLSv1.2")

        super().__init__(**values)
        SSLConfigMixin.__init__(self)

        # Configure SSL if enabled
        if ssl_enabled:
            from acb.ssl_config import SSLVerifyMode

            verify_mode_map = {
                "none": SSLVerifyMode.NONE,
                "optional": SSLVerifyMode.OPTIONAL,
                "required": SSLVerifyMode.REQUIRED,
            }
            verify_mode = verify_mode_map.get(ssl_verify_mode, SSLVerifyMode.REQUIRED)

            self.configure_ssl(
                enabled=True,
                cert_path=ssl_cert_path,
                key_path=ssl_key_path,
                ca_path=ssl_ca_path,
                verify_mode=verify_mode,
                check_hostname=verify_mode == SSLVerifyMode.REQUIRED,
            )


class AIBase(CleanupMixin, ABC):
    """Base class for AI adapters with unified interface."""

    def __init__(self, **kwargs: t.Any) -> None:
        super().__init__()
        self._settings: AIBaseSettings | None = None
        self._client: t.Any = None
        self._models_cache: dict[str, ModelInfo] = {}
        self._template_cache: dict[str, PromptTemplate] = {}
        # Get logger if available, otherwise None (for testing)
        try:
            logger_instance = depends.get_sync(Logger)
            # Verify it's actually a logger instance, not a string
            if isinstance(logger_instance, str):
                self.logger = None
            else:
                self.logger = logger_instance
        except Exception:
            self.logger = None

    @property
    def settings(self) -> AIBaseSettings:
        """Get adapter settings."""
        if self._settings is None:
            msg = "Settings not initialized"
            raise RuntimeError(msg)
        return self._settings

    @abstractmethod
    async def _create_client(self) -> t.Any:
        """Create and configure the AI client."""

    async def _ensure_client(self) -> t.Any:
        """Ensure client is initialized."""
        if self._client is None:
            self._client = await self._create_client()
            self.register_resource(self._client)
        return self._client

    # Safe logging helpers (logger may be None in tests)
    def _log_info(self, msg: str) -> None:
        """Log info message if logger available."""
        if self.logger:
            self.logger.info(msg)  # type: ignore[attr-defined]

    def _log_warning(self, msg: str) -> None:
        """Log warning message if logger available."""
        if self.logger:
            self.logger.warning(msg)  # type: ignore[attr-defined]

    def _log_error(self, msg: str) -> None:
        """Log error message if logger available."""
        if self.logger:
            self.logger.error(msg)  # type: ignore[attr-defined]

    def _log_exception(self, msg: str) -> None:
        """Log exception message if logger available."""
        if self.logger:
            self.logger.exception(msg)  # type: ignore[attr-defined]

    # Public interface methods
    async def generate_text(self, request: AIRequest) -> AIResponse:
        """Generate text using AI model."""
        return await self._generate_text(request)

    async def generate_text_stream(self, request: AIRequest) -> StreamingResponse:
        """Generate text with streaming response."""
        return await self._generate_text_stream(request)

    async def process_multimodal(self, request: AIRequest) -> AIResponse:
        """Process multimodal input (text, images, audio)."""
        return await self._process_multimodal(request)

    async def get_available_models(self) -> list[ModelInfo]:
        """Get list of available models."""
        return await self._get_available_models()

    async def get_model_info(self, model_name: str) -> ModelInfo | None:
        """Get information about a specific model."""
        return await self._get_model_info(model_name)

    async def register_template(self, template: PromptTemplate) -> None:
        """Register a prompt template."""
        await self._register_template(template)

    async def render_template(self, template_name: str, **kwargs: t.Any) -> str:
        """Render a prompt template with variables."""
        return await self._render_template(template_name, **kwargs)

    async def health_check(self) -> dict[str, t.Any]:
        """Check adapter health and connectivity."""
        return await self._health_check()

    # Abstract methods for implementation by deployment strategies
    @abstractmethod
    async def _generate_text(self, request: AIRequest) -> AIResponse:
        """Implementation-specific text generation."""

    @abstractmethod
    async def _generate_text_stream(self, request: AIRequest) -> StreamingResponse:
        """Implementation-specific streaming text generation."""

    async def _process_multimodal(self, request: AIRequest) -> AIResponse:
        """Default multimodal processing - can be overridden."""
        # Default implementation falls back to text-only processing
        if request.images or request.audio:
            self._log_warning(
                "Multimodal processing not supported, falling back to text-only",
            )
        return await self._generate_text(request)

    @abstractmethod
    async def _get_available_models(self) -> list[ModelInfo]:
        """Get available models for this deployment strategy."""

    async def _get_model_info(self, model_name: str) -> ModelInfo | None:
        """Get model information from cache or provider."""
        if model_name in self._models_cache:
            return self._models_cache[model_name]

        models = await self._get_available_models()
        for model in models:
            self._models_cache[model.name] = model
            if model.name == model_name:
                return model
        return None

    async def _register_template(self, template: PromptTemplate) -> None:
        """Register template in cache."""
        self._template_cache[template.name] = template

    async def _render_template(self, template_name: str, **kwargs: t.Any) -> str:
        """Render template from cache."""
        if template_name not in self._template_cache:
            msg = f"Template '{template_name}' not found"
            raise ValueError(msg)
        return self._template_cache[template_name].render(**kwargs)

    async def _health_check(self) -> dict[str, t.Any]:
        """Default health check implementation."""
        try:
            client = await self._ensure_client()
            # Basic connectivity test
            models = await self._get_available_models()
            return {
                "status": "healthy",
                "client_initialized": client is not None,
                "models_available": len(models) > 0,
                "deployment_strategy": self.settings.deployment_strategy,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "deployment_strategy": self.settings.deployment_strategy,
            }


# Utility functions for AI operations
async def estimate_tokens(text: str, model: str = "gpt-4") -> int:
    """Estimate token count for text (rough approximation)."""
    # Simple estimation: ~4 characters per token for English text
    return len(text) // 4


async def validate_request(request: AIRequest) -> None:
    """Validate AI request parameters."""
    if not request.prompt:
        msg = "Prompt cannot be empty"
        raise ValueError(msg)

    if request.max_tokens <= 0:
        msg = "max_tokens must be positive"
        raise ValueError(msg)

    if not (0.0 <= request.temperature <= 2.0):
        msg = "temperature must be between 0.0 and 2.0"
        raise ValueError(msg)

    if request.function_definitions and not isinstance(
        request.function_definitions,
        list,
    ):
        msg = "function_definitions must be a list"
        raise ValueError(msg)


async def calculate_cost(
    tokens_used: int,
    model: str,
    provider: ModelProvider,
) -> float | None:
    """Calculate estimated cost for AI request."""
    # Cost calculation based on provider and model
    # This would typically be loaded from configuration or external pricing API
    cost_per_1k_tokens = {
        (ModelProvider.OPENAI, "gpt-4"): 0.03,
        (ModelProvider.OPENAI, "gpt-3.5-turbo"): 0.002,
        (ModelProvider.ANTHROPIC, "claude-3-opus"): 0.015,
        (ModelProvider.ANTHROPIC, "claude-3-sonnet"): 0.003,
    }

    rate = cost_per_1k_tokens.get((provider, model))
    if rate is None:
        return None

    return (tokens_used / 1000) * rate
