"""Cloud deployment strategy for AI models (OpenAI, Anthropic, Azure, etc.)."""

import json
from uuid import UUID

import asyncio
import typing as t
from pydantic import SecretStr

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
    calculate_cost,
    validate_request,
)

if t.TYPE_CHECKING:
    import httpx

MODULE_ID = UUID("0197ff44-8c12-7f30-af61-2d41c6c89a73")
MODULE_STATUS = AdapterStatus.STABLE

MODULE_METADATA = AdapterMetadata(
    module_id=MODULE_ID,
    name="Cloud AI",
    category="ai",
    provider="cloud",
    version="1.0.0",
    acb_min_version="0.19.0",
    author="lesleslie <les@wedgwoodwebworks.com>",
    created_date="2025-01-15",
    last_modified="2025-01-15",
    status=MODULE_STATUS,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.STREAMING,
        AdapterCapability.CONNECTION_POOLING,
        AdapterCapability.TEXT_GENERATION,
        AdapterCapability.VISION_PROCESSING,
        AdapterCapability.AUDIO_PROCESSING,
        AdapterCapability.MULTIMODAL_PROCESSING,
        AdapterCapability.PROMPT_TEMPLATING,
        AdapterCapability.FALLBACK_MECHANISMS,
        AdapterCapability.TLS_SUPPORT,
    ],
    required_packages=[
        "openai>=1.0.0",
        "anthropic>=0.5.0",
        "httpx[http2]>=0.28.0",
        "aiohttp>=3.9.0",
    ],
    description="Cloud-based AI adapter for OpenAI, Anthropic, Azure OpenAI, AWS Bedrock, and Google Vertex AI",
    settings_class="CloudAISettings",
    config_example={
        "provider": "openai",
        "api_key": "your-api-key-here",  # pragma: allowlist secret
        "default_model": "gpt-4",
        "max_tokens": 1000,
        "temperature": 0.7,
        "enable_streaming": True,
    },
)


class CloudAISettings(AIBaseSettings):
    """Settings for cloud AI deployment."""

    # Provider selection
    provider: ModelProvider = ModelProvider.OPENAI

    # OpenAI settings
    openai_api_key: SecretStr | None = None
    openai_organization: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"

    # Anthropic settings
    anthropic_api_key: SecretStr | None = None
    anthropic_base_url: str = "https://api.anthropic.com"

    # Azure OpenAI settings
    azure_api_key: SecretStr | None = None
    azure_endpoint: str | None = None
    azure_api_version: str = "2024-02-15-preview"
    azure_deployment_name: str | None = None

    # AWS Bedrock settings
    aws_access_key_id: SecretStr | None = None
    aws_secret_access_key: SecretStr | None = None
    aws_region: str = "us-east-1"

    # Google Vertex AI settings
    google_project_id: str | None = None
    google_location: str = "us-central1"
    google_credentials_path: str | None = None

    # Advanced settings
    max_retries: int = 3
    request_timeout: float = 60.0
    rate_limit_per_minute: int = 60


class CloudAI(AIBase):
    """Cloud AI adapter implementation."""

    def __init__(self, **kwargs: t.Any) -> None:
        super().__init__(**kwargs)
        self._settings = CloudAISettings(**kwargs)
        self._http_client: httpx.AsyncClient | None = None

    @property
    def settings(self) -> CloudAISettings:
        """Get adapter settings with correct type."""
        if self._settings is None:
            msg = "Settings not initialized"
            raise RuntimeError(msg)
        return self._settings  # type: ignore[return-value]

    async def _create_client(self) -> t.Any:
        """Create cloud AI client based on provider."""
        if self.settings.provider == ModelProvider.OPENAI:
            return await self._create_openai_client()
        if self.settings.provider == ModelProvider.ANTHROPIC:
            return await self._create_anthropic_client()
        if self.settings.provider == ModelProvider.AZURE_OPENAI:
            return await self._create_azure_client()
        if self.settings.provider == ModelProvider.AWS_BEDROCK:
            return await self._create_bedrock_client()
        if self.settings.provider == ModelProvider.GOOGLE_VERTEX:
            return await self._create_vertex_client()
        msg = f"Unsupported cloud provider: {self.settings.provider}"
        raise ValueError(msg)

    async def _create_openai_client(self) -> t.Any:
        """Create OpenAI client."""
        try:
            import openai
        except ImportError:
            msg = "openai package required for OpenAI provider"
            raise ImportError(msg)

        api_key = self.settings.openai_api_key or self.settings.api_key
        if not api_key:
            msg = "OpenAI API key required"
            raise ValueError(msg)

        return openai.AsyncOpenAI(
            api_key=api_key.get_secret_value(),
            organization=self.settings.openai_organization
            or self.settings.organization,
            base_url=self.settings.openai_base_url or self.settings.base_url,
            timeout=self.settings.request_timeout,
            max_retries=self.settings.max_retries,
        )

    async def _create_anthropic_client(self) -> t.Any:
        """Create Anthropic client."""
        try:
            import anthropic
        except ImportError:
            msg = "anthropic package required for Anthropic provider"
            raise ImportError(msg)

        api_key = self.settings.anthropic_api_key or self.settings.api_key
        if not api_key:
            msg = "Anthropic API key required"
            raise ValueError(msg)

        return anthropic.AsyncAnthropic(
            api_key=api_key.get_secret_value(),
            base_url=self.settings.anthropic_base_url or self.settings.base_url,
            timeout=self.settings.request_timeout,
            max_retries=self.settings.max_retries,
        )

    async def _create_azure_client(self) -> t.Any:
        """Create Azure OpenAI client."""
        try:
            import openai
        except ImportError:
            msg = "openai package required for Azure OpenAI provider"
            raise ImportError(msg)

        api_key = self.settings.azure_api_key or self.settings.api_key
        if not api_key or not self.settings.azure_endpoint:
            msg = "Azure API key and endpoint required"
            raise ValueError(msg)

        return openai.AsyncAzureOpenAI(
            api_key=api_key.get_secret_value(),
            azure_endpoint=self.settings.azure_endpoint,
            api_version=self.settings.azure_api_version,
            timeout=self.settings.request_timeout,
            max_retries=self.settings.max_retries,
        )

    async def _create_bedrock_client(self) -> t.Any:
        """Create AWS Bedrock client."""
        try:
            import boto3
        except ImportError:
            msg = "boto3 package required for AWS Bedrock provider"
            raise ImportError(msg)

        session = boto3.Session(
            aws_access_key_id=self.settings.aws_access_key_id.get_secret_value()
            if self.settings.aws_access_key_id
            else None,
            aws_secret_access_key=self.settings.aws_secret_access_key.get_secret_value()
            if self.settings.aws_secret_access_key
            else None,
            region_name=self.settings.aws_region,
        )

        return session.client("bedrock-runtime")

    async def _create_vertex_client(self) -> t.Any:
        """Create Google Vertex AI client."""
        try:
            from vertexai import init
            from vertexai.generative_models import GenerativeModel
        except ImportError:
            msg = "google-cloud-aiplatform package required for Vertex AI provider"
            raise ImportError(
                msg,
            )

        if not self.settings.google_project_id:
            msg = "Google project ID required"
            raise ValueError(msg)

        init(
            project=self.settings.google_project_id,
            location=self.settings.google_location,
        )

        return GenerativeModel

    async def _generate_text(self, request: AIRequest) -> AIResponse:
        """Generate text using cloud provider."""
        await validate_request(request)
        client = await self._ensure_client()

        start_time = asyncio.get_event_loop().time()

        try:
            if self.settings.provider == ModelProvider.OPENAI:
                response = await self._openai_generate(client, request)
            elif self.settings.provider == ModelProvider.ANTHROPIC:
                response = await self._anthropic_generate(client, request)
            elif self.settings.provider == ModelProvider.AZURE_OPENAI:
                response = await self._azure_generate(client, request)
            elif self.settings.provider == ModelProvider.AWS_BEDROCK:
                response = await self._bedrock_generate(client, request)
            elif self.settings.provider == ModelProvider.GOOGLE_VERTEX:
                response = await self._vertex_generate(client, request)
            else:
                msg = f"Unsupported provider: {self.settings.provider}"
                raise ValueError(msg)

            latency_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            response.latency_ms = latency_ms

            # Calculate cost if possible
            if response.tokens_used:
                response.cost = await calculate_cost(
                    response.tokens_used,
                    response.model,
                    self.settings.provider,
                )

            return response

        except Exception as e:
            if self.logger is not None:
                self.logger.exception(f"Text generation failed: {e}")
            raise

    async def _generate_text_stream(self, request: AIRequest) -> StreamingResponse:
        """Generate streaming text response."""
        await validate_request(request)
        client = await self._ensure_client()

        if self.settings.provider == ModelProvider.OPENAI:
            generator = self._openai_stream(client, request)
        elif self.settings.provider == ModelProvider.ANTHROPIC:
            generator = self._anthropic_stream(client, request)
        elif self.settings.provider == ModelProvider.AZURE_OPENAI:
            generator = self._azure_stream(client, request)
        else:
            msg = f"Streaming not supported for provider: {self.settings.provider}"
            raise ValueError(
                msg,
            )

        return StreamingResponse(generator)

    async def _openai_generate(self, client: t.Any, request: AIRequest) -> AIResponse:
        """Generate text using OpenAI."""
        messages = self._format_openai_messages(request)

        response = await client.chat.completions.create(
            model=request.model or self.settings.default_model,
            messages=messages,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            functions=request.function_definitions,
            stream=False,
        )

        choice = response.choices[0]
        return AIResponse(
            content=choice.message.content or "",
            model=response.model,
            provider=ModelProvider.OPENAI,
            strategy=DeploymentStrategy.CLOUD,
            tokens_used=response.usage.total_tokens if response.usage else None,
            finish_reason=choice.finish_reason,
            function_calls=self._extract_function_calls(choice.message),
        )

    async def _anthropic_generate(
        self,
        client: t.Any,
        request: AIRequest,
    ) -> AIResponse:
        """Generate text using Anthropic."""
        system_prompt = request.system_prompt or ""
        user_prompt = (
            request.prompt if isinstance(request.prompt, str) else str(request.prompt)
        )

        response = await client.messages.create(
            model=request.model or self.settings.default_model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        return AIResponse(
            content=response.content[0].text if response.content else "",
            model=response.model,
            provider=ModelProvider.ANTHROPIC,
            strategy=DeploymentStrategy.CLOUD,
            tokens_used=response.usage.input_tokens + response.usage.output_tokens
            if response.usage
            else None,
            finish_reason=response.stop_reason,
        )

    async def _azure_generate(self, client: t.Any, request: AIRequest) -> AIResponse:
        """Generate text using Azure OpenAI."""
        messages = self._format_openai_messages(request)

        response = await client.chat.completions.create(
            model=self.settings.azure_deployment_name
            or request.model
            or self.settings.default_model,
            messages=messages,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            functions=request.function_definitions,
            stream=False,
        )

        choice = response.choices[0]
        return AIResponse(
            content=choice.message.content or "",
            model=response.model,
            provider=ModelProvider.AZURE_OPENAI,
            strategy=DeploymentStrategy.CLOUD,
            tokens_used=response.usage.total_tokens if response.usage else None,
            finish_reason=choice.finish_reason,
            function_calls=self._extract_function_calls(choice.message),
        )

    async def _bedrock_generate(self, client: t.Any, request: AIRequest) -> AIResponse:
        """Generate text using AWS Bedrock."""
        model_id = request.model or "anthropic.claude-3-sonnet-20240229-v1:0"
        user_prompt = (
            request.prompt if isinstance(request.prompt, str) else str(request.prompt)
        )

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "messages": [{"role": "user", "content": user_prompt}],
        }

        if request.system_prompt:
            body["system"] = request.system_prompt

        response = client.invoke_model(
            modelId=model_id,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )

        response_data = json.loads(response["body"].read())

        return AIResponse(
            content=response_data.get("content", [{}])[0].get("text", ""),
            model=model_id,
            provider=ModelProvider.AWS_BEDROCK,
            strategy=DeploymentStrategy.CLOUD,
            tokens_used=response_data.get("usage", {}).get("input_tokens", 0)
            + response_data.get("usage", {}).get("output_tokens", 0),
            finish_reason=response_data.get("stop_reason"),
        )

    async def _vertex_generate(
        self,
        client_class: t.Any,
        request: AIRequest,
    ) -> AIResponse:
        """Generate text using Google Vertex AI."""
        model = client_class(request.model or "gemini-pro")
        user_prompt = (
            request.prompt if isinstance(request.prompt, str) else str(request.prompt)
        )

        generation_config = {
            "max_output_tokens": request.max_tokens,
            "temperature": request.temperature,
        }

        response = await model.generate_content_async(
            user_prompt,
            generation_config=generation_config,
        )

        return AIResponse(
            content=response.text,
            model=request.model or "gemini-pro",
            provider=ModelProvider.GOOGLE_VERTEX,
            strategy=DeploymentStrategy.CLOUD,
            tokens_used=response.usage_metadata.total_token_count
            if hasattr(response, "usage_metadata")
            else None,
        )

    async def _openai_stream(
        self,
        client: t.Any,
        request: AIRequest,
    ) -> t.AsyncGenerator[str]:
        """Stream text generation from OpenAI."""
        messages = self._format_openai_messages(request)

        stream = await client.chat.completions.create(
            model=request.model or self.settings.default_model,
            messages=messages,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def _anthropic_stream(
        self,
        client: t.Any,
        request: AIRequest,
    ) -> t.AsyncGenerator[str]:
        """Stream text generation from Anthropic."""
        system_prompt = request.system_prompt or ""
        user_prompt = (
            request.prompt if isinstance(request.prompt, str) else str(request.prompt)
        )

        async with client.messages.stream(
            model=request.model or self.settings.default_model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def _azure_stream(
        self,
        client: t.Any,
        request: AIRequest,
    ) -> t.AsyncGenerator[str]:
        """Stream text generation from Azure OpenAI."""
        messages = self._format_openai_messages(request)

        stream = await client.chat.completions.create(
            model=self.settings.azure_deployment_name
            or request.model
            or self.settings.default_model,
            messages=messages,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def _get_available_models(self) -> list[ModelInfo]:
        """Get available models from cloud provider."""
        if self.settings.provider == ModelProvider.OPENAI:
            return await self._get_openai_models()
        if self.settings.provider == ModelProvider.ANTHROPIC:
            return await self._get_anthropic_models()
        if self.settings.provider == ModelProvider.AZURE_OPENAI:
            return await self._get_azure_models()
        if self.settings.provider == ModelProvider.AWS_BEDROCK:
            return await self._get_bedrock_models()
        if self.settings.provider == ModelProvider.GOOGLE_VERTEX:
            return await self._get_vertex_models()
        return []

    async def _get_openai_models(self) -> list[ModelInfo]:
        """Get OpenAI models."""
        return [
            ModelInfo(
                name="gpt-4",
                provider=ModelProvider.OPENAI,
                capabilities=[
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.CHAT_COMPLETION,
                    ModelCapability.FUNCTION_CALLING,
                ],
                context_length=8192,
                cost_per_token=0.00003,
                supports_streaming=True,
                supports_function_calling=True,
            ),
            ModelInfo(
                name="gpt-3.5-turbo",
                provider=ModelProvider.OPENAI,
                capabilities=[
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.CHAT_COMPLETION,
                    ModelCapability.FUNCTION_CALLING,
                ],
                context_length=4096,
                cost_per_token=0.000002,
                supports_streaming=True,
                supports_function_calling=True,
            ),
            ModelInfo(
                name="gpt-4-vision-preview",
                provider=ModelProvider.OPENAI,
                capabilities=[
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.CHAT_COMPLETION,
                    ModelCapability.VISION,
                ],
                context_length=128000,
                cost_per_token=0.00001,
                supports_streaming=True,
            ),
        ]

    async def _get_anthropic_models(self) -> list[ModelInfo]:
        """Get Anthropic models."""
        return [
            ModelInfo(
                name="claude-3-opus-20240229",
                provider=ModelProvider.ANTHROPIC,
                capabilities=[
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.CHAT_COMPLETION,
                ],
                context_length=200000,
                cost_per_token=0.000015,
                supports_streaming=True,
            ),
            ModelInfo(
                name="claude-3-sonnet-20240229",
                provider=ModelProvider.ANTHROPIC,
                capabilities=[
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.CHAT_COMPLETION,
                ],
                context_length=200000,
                cost_per_token=0.000003,
                supports_streaming=True,
            ),
        ]

    async def _get_azure_models(self) -> list[ModelInfo]:
        """Get Azure OpenAI models."""
        # Azure models are deployment-specific
        return [
            ModelInfo(
                name=self.settings.azure_deployment_name or "gpt-4",
                provider=ModelProvider.AZURE_OPENAI,
                capabilities=[
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.CHAT_COMPLETION,
                ],
                context_length=8192,
                cost_per_token=0.00003,
                supports_streaming=True,
            ),
        ]

    async def _get_bedrock_models(self) -> list[ModelInfo]:
        """Get AWS Bedrock models."""
        return [
            ModelInfo(
                name="anthropic.claude-3-sonnet-20240229-v1:0",
                provider=ModelProvider.AWS_BEDROCK,
                capabilities=[
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.CHAT_COMPLETION,
                ],
                context_length=200000,
                cost_per_token=0.000003,
            ),
        ]

    async def _get_vertex_models(self) -> list[ModelInfo]:
        """Get Google Vertex AI models."""
        return [
            ModelInfo(
                name="gemini-pro",
                provider=ModelProvider.GOOGLE_VERTEX,
                capabilities=[
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.CHAT_COMPLETION,
                ],
                context_length=32768,
                cost_per_token=0.0000005,
                supports_streaming=True,
            ),
            ModelInfo(
                name="gemini-pro-vision",
                provider=ModelProvider.GOOGLE_VERTEX,
                capabilities=[
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.CHAT_COMPLETION,
                    ModelCapability.VISION,
                ],
                context_length=16384,
                cost_per_token=0.00000025,
            ),
        ]

    def _format_openai_messages(self, request: AIRequest) -> list[dict[str, t.Any]]:
        """Format messages for OpenAI API."""
        messages: list[dict[str, t.Any]] = []

        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})

        if isinstance(request.prompt, str):
            if request.images:
                # Multimodal content
                multimodal_content: list[dict[str, t.Any]] = [
                    {"type": "text", "text": request.prompt},
                    *[
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": img
                                if isinstance(img, str)
                                else f"data:image/jpeg;base64,{img.decode('utf-8') if isinstance(img, bytes) else str(img)}",
                            },
                        }
                        for img in request.images
                    ],
                ]
                messages.append({"role": "user", "content": multimodal_content})
            else:
                messages.append({"role": "user", "content": request.prompt})
        else:
            messages.extend(request.prompt)

        return messages

    def _extract_function_calls(self, message: t.Any) -> list[dict[str, t.Any]] | None:
        """Extract function calls from OpenAI message."""
        if hasattr(message, "function_call") and message.function_call:
            return [
                {
                    "name": message.function_call.name,
                    "arguments": json.loads(message.function_call.arguments),
                },
            ]
        if hasattr(message, "tool_calls") and message.tool_calls:
            return [
                {
                    "name": call.function.name,
                    "arguments": json.loads(call.function.arguments),
                }
                for call in message.tool_calls
            ]
        return None


# Alias for backward compatibility and convention
Ai = CloudAI
AiSettings = CloudAISettings

depends.set(Ai, "cloud")
