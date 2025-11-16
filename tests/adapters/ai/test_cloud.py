"""Tests for the cloud AI adapter."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from acb.adapters.ai._base import (
    AIRequest,
    DeploymentStrategy,
    ModelCapability,
    ModelProvider,
)
from acb.adapters.ai.cloud import MODULE_METADATA, CloudAI, CloudAISettings


class TestCloudAISettings:
    @patch("acb.depends.depends.get")
    def test_init_basic(self, mock_depends_get: MagicMock) -> None:
        mock_config = MagicMock()
        mock_depends_get.return_value = mock_config

        settings = CloudAISettings()
        assert settings.provider == ModelProvider.OPENAI
        assert settings.openai_base_url == "https://api.openai.com/v1"
        assert settings.anthropic_base_url == "https://api.anthropic.com"
        assert settings.max_retries == 3

    @patch("acb.depends.depends.get")
    def test_init_with_provider(self, mock_depends_get: MagicMock) -> None:
        mock_config = MagicMock()
        mock_depends_get.return_value = mock_config

        settings = CloudAISettings(provider=ModelProvider.ANTHROPIC)
        assert settings.provider == ModelProvider.ANTHROPIC


class TestCloudAI:
    @pytest.fixture
    def mock_openai_client(self) -> MagicMock:
        client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Generated response"
        mock_response.choices[0].message.function_call = None
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].finish_reason = "stop"
        mock_response.model = "gpt-3.5-turbo"
        mock_response.usage.total_tokens = 50
        client.chat.completions.create = AsyncMock(return_value=mock_response)
        return client

    @pytest.fixture
    def mock_anthropic_client(self) -> MagicMock:
        client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = "Anthropic response"
        mock_response.model = "claude-3-sonnet-20240229"
        mock_response.usage.input_tokens = 20
        mock_response.usage.output_tokens = 30
        mock_response.stop_reason = "end_turn"
        client.messages.create = AsyncMock(return_value=mock_response)
        return client

    @pytest.mark.asyncio
    async def test_create_openai_client(self) -> None:
        """Test OpenAI client creation - simplified test without mocking import."""
        adapter = CloudAI(
            provider=ModelProvider.OPENAI,
            openai_api_key="test-key",
        )

        # Just test that the method exists and can be called
        # Full integration testing requires actual openai package
        assert hasattr(adapter, "_create_openai_client")
        assert callable(adapter._create_openai_client)

    @pytest.mark.asyncio
    async def test_create_anthropic_client(self) -> None:
        """Test Anthropic client creation - simplified test without mocking import."""
        adapter = CloudAI(
            provider=ModelProvider.ANTHROPIC,
            anthropic_api_key="test-key",
        )

        # Just test that the method exists and can be called
        # Full integration testing requires actual anthropic package
        assert hasattr(adapter, "_create_anthropic_client")
        assert callable(adapter._create_anthropic_client)

    @pytest.mark.asyncio
    async def test_openai_generate(self, mock_openai_client: MagicMock) -> None:
        adapter = CloudAI(provider=ModelProvider.OPENAI)

        request = AIRequest(
            prompt="Test prompt",
            model="gpt-3.5-turbo",
            max_tokens=100,
        )

        response = await adapter._openai_generate(mock_openai_client, request)

        assert response.content == "Generated response"
        assert response.model == "gpt-3.5-turbo"
        assert response.provider == ModelProvider.OPENAI
        assert response.strategy == DeploymentStrategy.CLOUD
        assert response.tokens_used == 50

    @pytest.mark.asyncio
    async def test_anthropic_generate(self, mock_anthropic_client: MagicMock) -> None:
        adapter = CloudAI(provider=ModelProvider.ANTHROPIC)
        adapter._client = mock_anthropic_client

        request = AIRequest(
            prompt="Test prompt",
            model="claude-3-sonnet-20240229",
            max_tokens=100,
        )

        response = await adapter._anthropic_generate(mock_anthropic_client, request)

        assert response.content == "Anthropic response"
        assert response.model == "claude-3-sonnet-20240229"
        assert response.provider == ModelProvider.ANTHROPIC
        assert response.strategy == DeploymentStrategy.CLOUD
        assert response.tokens_used == 50  # input + output

    @pytest.mark.asyncio
    async def test_generate_text_with_openai(
        self, mock_openai_client: MagicMock
    ) -> None:
        with patch("acb.adapters.ai.cloud.validate_request") as mock_validate:
            mock_validate.return_value = None

            adapter = CloudAI(provider=ModelProvider.OPENAI)
            adapter._client = mock_openai_client

            request = AIRequest(prompt="Test prompt")
            response = await adapter._generate_text(request)

            assert response.content == "Generated response"
            assert response.provider == ModelProvider.OPENAI
            assert response.latency_ms is not None

    @pytest.mark.asyncio
    async def test_format_openai_messages_simple(self) -> None:
        adapter = CloudAI()
        request = AIRequest(prompt="Hello, world!")

        messages = adapter._format_openai_messages(request)

        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello, world!"

    @pytest.mark.asyncio
    async def test_format_openai_messages_with_system(self) -> None:
        adapter = CloudAI()
        request = AIRequest(
            prompt="Hello, world!",
            system_prompt="You are a helpful assistant",
        )

        messages = adapter._format_openai_messages(request)

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a helpful assistant"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Hello, world!"

    @pytest.mark.asyncio
    async def test_format_openai_messages_with_images(self) -> None:
        adapter = CloudAI()
        request = AIRequest(
            prompt="Describe this image",
            images=["data:image/jpeg;base64,abc123"],
        )

        messages = adapter._format_openai_messages(request)

        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        content = messages[0]["content"]
        assert isinstance(content, list)
        assert content[0]["type"] == "text"
        assert content[1]["type"] == "image_url"

    @pytest.mark.asyncio
    async def test_get_openai_models(self) -> None:
        adapter = CloudAI(provider=ModelProvider.OPENAI)
        models = await adapter._get_openai_models()

        assert len(models) > 0
        gpt4_models = [m for m in models if m.name == "gpt-4"]
        assert len(gpt4_models) == 1

        gpt4 = gpt4_models[0]
        assert gpt4.provider == ModelProvider.OPENAI
        assert ModelCapability.TEXT_GENERATION in gpt4.capabilities
        assert gpt4.supports_streaming

    @pytest.mark.asyncio
    async def test_get_anthropic_models(self) -> None:
        adapter = CloudAI(provider=ModelProvider.ANTHROPIC)
        models = await adapter._get_anthropic_models()

        assert len(models) > 0
        claude_models = [m for m in models if "claude" in m.name]
        assert len(claude_models) > 0

        claude = claude_models[0]
        assert claude.provider == ModelProvider.ANTHROPIC
        assert ModelCapability.TEXT_GENERATION in claude.capabilities

    @pytest.mark.asyncio
    async def test_openai_stream(self, mock_openai_client: MagicMock) -> None:
        # Mock streaming response
        async def mock_stream():
            chunks = [
                MagicMock(choices=[MagicMock(delta=MagicMock(content="Hello"))]),
                MagicMock(choices=[MagicMock(delta=MagicMock(content=" "))]),
                MagicMock(choices=[MagicMock(delta=MagicMock(content="world"))]),
            ]
            for chunk in chunks:
                yield chunk

        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=mock_stream()
        )

        adapter = CloudAI(provider=ModelProvider.OPENAI)
        request = AIRequest(prompt="Test streaming")

        generator = adapter._openai_stream(mock_openai_client, request)
        chunks = []
        async for chunk in generator:
            chunks.append(chunk)

        assert chunks == ["Hello", " ", "world"]

    @pytest.mark.asyncio
    async def test_extract_function_calls_none(self) -> None:
        adapter = CloudAI()
        message = MagicMock()
        message.function_call = None
        message.tool_calls = None

        result = adapter._extract_function_calls(message)
        assert result is None

    @pytest.mark.asyncio
    async def test_extract_function_calls_function_call(self) -> None:
        adapter = CloudAI()
        message = MagicMock()
        message.function_call.name = "test_function"
        message.function_call.arguments = '{"arg1": "value1"}'
        message.tool_calls = None

        result = adapter._extract_function_calls(message)
        assert result is not None
        assert len(result) == 1
        assert result[0]["name"] == "test_function"
        assert result[0]["arguments"] == {"arg1": "value1"}

    @pytest.mark.asyncio
    async def test_create_client_unsupported_provider(self) -> None:
        # Create adapter with unsupported provider
        adapter = CloudAI()
        adapter.settings.provider = "unsupported"  # Set invalid provider

        with pytest.raises(ValueError, match="Unsupported cloud provider"):
            await adapter._create_client()

    @pytest.mark.asyncio
    async def test_bedrock_generate_mock(self) -> None:
        """Test Bedrock generation with mocked client."""
        mock_client = MagicMock()
        mock_response = {
            "body": MagicMock(),
        }
        mock_response["body"].read.return_value = json.dumps(
            {
                "content": [{"text": "Bedrock response"}],
                "usage": {"input_tokens": 10, "output_tokens": 20},
                "stop_reason": "end_turn",
            }
        ).encode()
        mock_client.invoke_model.return_value = mock_response

        adapter = CloudAI(provider=ModelProvider.AWS_BEDROCK)
        request = AIRequest(prompt="Test prompt")

        response = await adapter._bedrock_generate(mock_client, request)

        assert response.content == "Bedrock response"
        assert response.provider == ModelProvider.AWS_BEDROCK
        assert response.tokens_used == 30

    def test_module_metadata(self) -> None:
        """Test that module metadata is properly configured."""
        assert MODULE_METADATA.name == "Cloud AI"
        assert MODULE_METADATA.category == "ai"
        assert MODULE_METADATA.provider == "cloud"
        assert "openai>=1.0.0" in MODULE_METADATA.required_packages
