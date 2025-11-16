"""Tests for the base AI adapter components."""

from unittest.mock import MagicMock, patch

import asyncio
import pytest
import typing as t

from acb.adapters.ai._base import (
    AIBase,
    AIBaseSettings,
    AIRequest,
    AIResponse,
    DeploymentStrategy,
    ModelCapability,
    ModelInfo,
    ModelProvider,
    PromptTemplate,
    StreamingResponse,
    calculate_cost,
    estimate_tokens,
    validate_request,
)


class TestModelInfo:
    def test_init(self) -> None:
        model = ModelInfo(
            name="test-model",
            provider=ModelProvider.OPENAI,
            capabilities=[ModelCapability.TEXT_GENERATION],
            context_length=4096,
        )
        assert model.name == "test-model"
        assert model.provider == ModelProvider.OPENAI
        assert model.context_length == 4096
        assert model.deployment_strategies == [DeploymentStrategy.CLOUD]  # Default

    def test_init_with_strategies(self) -> None:
        model = ModelInfo(
            name="edge-model",
            provider=ModelProvider.OLLAMA,
            capabilities=[ModelCapability.TEXT_GENERATION],
            context_length=2048,
            deployment_strategies=[DeploymentStrategy.EDGE],
        )
        assert model.deployment_strategies == [DeploymentStrategy.EDGE]


class TestAIRequest:
    def test_init_basic(self) -> None:
        request = AIRequest(prompt="Hello, world!")
        assert request.prompt == "Hello, world!"
        assert request.max_tokens == 1000
        assert request.temperature == 0.7
        assert not request.stream

    def test_init_with_all_params(self) -> None:
        request = AIRequest(
            prompt="Test prompt",
            model="gpt-4",
            max_tokens=500,
            temperature=0.5,
            stream=True,
            system_prompt="You are a helpful assistant",
            images=["test_image.jpg"],
            max_latency_ms=1000,
        )
        assert request.model == "gpt-4"
        assert request.max_tokens == 500
        assert request.temperature == 0.5
        assert request.stream
        assert request.system_prompt == "You are a helpful assistant"
        assert request.images == ["test_image.jpg"]
        assert request.max_latency_ms == 1000


class TestAIResponse:
    def test_init(self) -> None:
        response = AIResponse(
            content="Generated response",
            model="gpt-3.5-turbo",
            provider=ModelProvider.OPENAI,
            strategy=DeploymentStrategy.CLOUD,
        )
        assert response.content == "Generated response"
        assert response.model == "gpt-3.5-turbo"
        assert response.provider == ModelProvider.OPENAI
        assert response.strategy == DeploymentStrategy.CLOUD
        assert response.tokens_used is None
        assert response.cached is False


class TestStreamingResponse:
    @pytest.mark.asyncio
    async def test_streaming_basic(self) -> None:
        async def mock_generator() -> t.AsyncIterator[str]:
            yield "Hello"
            yield " "
            yield "world"

        response = StreamingResponse(mock_generator())
        chunks = []
        async for chunk in response:
            chunks.append(chunk)

        assert chunks == ["Hello", " ", "world"]

    @pytest.mark.asyncio
    async def test_complete(self) -> None:
        async def mock_generator() -> t.AsyncIterator[str]:
            yield "Hello"
            yield " "
            yield "world"

        response = StreamingResponse(mock_generator())
        complete_text = await response.complete()
        assert complete_text == "Hello world"

    @pytest.mark.asyncio
    async def test_stop(self) -> None:
        async def mock_generator() -> t.AsyncIterator[str]:
            yield "Hello"
            await asyncio.sleep(0.1)
            yield " "
            yield "world"

        response = StreamingResponse(mock_generator())
        chunks = []

        async def consume_with_stop() -> None:
            async for chunk in response:
                chunks.append(chunk)
                if chunk == "Hello":
                    await response.stop()

        await consume_with_stop()
        assert chunks == ["Hello"]


class TestPromptTemplate:
    def test_init(self) -> None:
        template = PromptTemplate(
            name="greeting",
            template="Hello, {name}! Welcome to {place}.",
            variables=["name", "place"],
        )
        assert template.name == "greeting"
        assert template.template == "Hello, {name}! Welcome to {place}."
        assert template.variables == ["name", "place"]
        assert template.version == "1.0.0"

    def test_render_basic(self) -> None:
        template = PromptTemplate(
            name="greeting",
            template="Hello, {name}!",
            variables=["name"],
        )
        result = template.render(name="Alice")
        assert result == "Hello, Alice!"

    def test_render_with_defaults(self) -> None:
        template = PromptTemplate(
            name="greeting",
            template="Hello, {name}! Welcome to {place}.",
            variables=["name", "place"],
            default_values={"place": "our service"},
        )
        result = template.render(name="Bob")
        assert result == "Hello, Bob! Welcome to our service."

    def test_render_override_defaults(self) -> None:
        template = PromptTemplate(
            name="greeting",
            template="Hello, {name}! Welcome to {place}.",
            variables=["name", "place"],
            default_values={"place": "our service"},
        )
        result = template.render(name="Bob", place="the party")
        assert result == "Hello, Bob! Welcome to the party."

    def test_render_missing_variables(self) -> None:
        template = PromptTemplate(
            name="greeting",
            template="Hello, {name}!",
            variables=["name"],
        )
        with pytest.raises(ValueError, match="Missing template variables"):
            template.render()


class TestAIBaseSettings:
    @patch("acb.depends.depends.get")
    def test_init_basic(self, mock_depends_get: MagicMock) -> None:
        mock_config = MagicMock()
        mock_depends_get.return_value = mock_config

        settings = AIBaseSettings()
        assert settings.deployment_strategy == DeploymentStrategy.CLOUD
        assert settings.default_model == "gpt-4"
        assert settings.max_tokens == 1000
        assert settings.temperature == 0.7

    @patch("acb.depends.depends.get")
    def test_init_with_ssl(self, mock_depends_get: MagicMock) -> None:
        mock_config = MagicMock()
        mock_depends_get.return_value = mock_config

        settings = AIBaseSettings(
            ssl_enabled=True,
            ssl_cert_path="/path/to/cert.pem",
            ssl_verify_mode="required",
        )
        assert settings.ssl_enabled


class MockAIAdapter(AIBase):
    """Mock AI adapter for testing."""

    def __init__(self, **kwargs: t.Any) -> None:
        super().__init__(**kwargs)
        self._settings = AIBaseSettings(**kwargs)
        self._mock_client = MagicMock()

    async def _create_client(self) -> t.Any:
        return self._mock_client

    async def _generate_text(self, request: AIRequest) -> AIResponse:
        return AIResponse(
            content="Mocked response",
            model=request.model or "mock-model",
            provider=ModelProvider.LOCAL,
            strategy=DeploymentStrategy.EDGE,
        )

    async def _generate_text_stream(self, request: AIRequest) -> StreamingResponse:
        async def mock_generator() -> t.AsyncIterator[str]:
            yield "Mocked"
            yield " "
            yield "stream"

        return StreamingResponse(mock_generator())

    async def _get_available_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(
                name="mock-model",
                provider=ModelProvider.LOCAL,
                capabilities=[ModelCapability.TEXT_GENERATION],
                context_length=2048,
            )
        ]


class TestAIBase:
    @pytest.mark.asyncio
    async def test_generate_text(self) -> None:
        adapter = MockAIAdapter()
        request = AIRequest(prompt="Test prompt")
        response = await adapter.generate_text(request)

        assert response.content == "Mocked response"
        assert response.strategy == DeploymentStrategy.EDGE

    @pytest.mark.asyncio
    async def test_generate_text_stream(self) -> None:
        adapter = MockAIAdapter()
        request = AIRequest(prompt="Test prompt")
        stream = await adapter.generate_text_stream(request)

        chunks = []
        async for chunk in stream:
            chunks.append(chunk)

        assert chunks == ["Mocked", " ", "stream"]

    @pytest.mark.asyncio
    async def test_get_available_models(self) -> None:
        adapter = MockAIAdapter()
        models = await adapter.get_available_models()

        assert len(models) == 1
        assert models[0].name == "mock-model"
        assert models[0].provider == ModelProvider.LOCAL

    @pytest.mark.asyncio
    async def test_get_model_info(self) -> None:
        adapter = MockAIAdapter()
        model = await adapter.get_model_info("mock-model")

        assert model is not None
        assert model.name == "mock-model"

    @pytest.mark.asyncio
    async def test_get_model_info_not_found(self) -> None:
        adapter = MockAIAdapter()
        model = await adapter.get_model_info("nonexistent-model")

        assert model is None

    @pytest.mark.asyncio
    async def test_register_and_render_template(self) -> None:
        adapter = MockAIAdapter()
        template = PromptTemplate(
            name="test",
            template="Hello, {name}!",
            variables=["name"],
        )

        await adapter.register_template(template)
        result = await adapter.render_template("test", name="World")

        assert result == "Hello, World!"

    @pytest.mark.asyncio
    async def test_render_template_not_found(self) -> None:
        adapter = MockAIAdapter()

        with pytest.raises(ValueError, match="Template 'nonexistent' not found"):
            await adapter.render_template("nonexistent", name="Test")

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        adapter = MockAIAdapter()
        health = await adapter.health_check()

        assert health["status"] == "healthy"
        assert health["deployment_strategy"] == DeploymentStrategy.CLOUD


class TestUtilityFunctions:
    @pytest.mark.asyncio
    async def test_estimate_tokens(self) -> None:
        text = "This is a test message with multiple words."
        tokens = await estimate_tokens(text)
        # Should be roughly text length / 4
        expected = len(text) // 4
        assert abs(tokens - expected) <= 1

    @pytest.mark.asyncio
    async def test_validate_request_valid(self) -> None:
        request = AIRequest(
            prompt="Valid prompt",
            max_tokens=100,
            temperature=0.8,
        )
        # Should not raise
        await validate_request(request)

    @pytest.mark.asyncio
    async def test_validate_request_empty_prompt(self) -> None:
        request = AIRequest(prompt="")
        with pytest.raises(ValueError, match="Prompt cannot be empty"):
            await validate_request(request)

    @pytest.mark.asyncio
    async def test_validate_request_invalid_max_tokens(self) -> None:
        request = AIRequest(prompt="Test", max_tokens=0)
        with pytest.raises(ValueError, match="max_tokens must be positive"):
            await validate_request(request)

    @pytest.mark.asyncio
    async def test_validate_request_invalid_temperature(self) -> None:
        request = AIRequest(prompt="Test", temperature=3.0)
        with pytest.raises(ValueError, match="temperature must be between 0.0 and 2.0"):
            await validate_request(request)

    @pytest.mark.asyncio
    async def test_calculate_cost_known_model(self) -> None:
        cost = await calculate_cost(1000, "gpt-4", ModelProvider.OPENAI)
        assert cost == 0.03  # 1000 tokens * $0.03 per 1K tokens

    @pytest.mark.asyncio
    async def test_calculate_cost_unknown_model(self) -> None:
        cost = await calculate_cost(1000, "unknown-model", ModelProvider.LOCAL)
        assert cost is None
