"""Integration tests for AI adapters."""

from unittest.mock import AsyncMock, MagicMock, patch

import asyncio
import pytest

from acb.adapters.ai._base import (
    AIRequest,
    DeploymentStrategy,
    ModelProvider,
    PromptTemplate,
)


class TestAIAdapterIntegration:
    """Integration tests for the complete AI adapter system."""

    @pytest.mark.asyncio
    async def test_import_cloud_adapter(self) -> None:
        """Test importing cloud AI adapter."""
        try:
            from acb.adapters.ai.cloud import CloudAI

            assert CloudAI is not None
            assert CloudAI.__name__ == "CloudAI"
        except ImportError:
            pytest.skip("CloudAI dependencies not available")

    @pytest.mark.asyncio
    async def test_import_edge_adapter(self) -> None:
        """Test importing edge AI adapter."""
        try:
            from acb.adapters.ai.edge import EdgeAI

            assert EdgeAI is not None
            assert EdgeAI.__name__ == "EdgeAI"
        except ImportError:
            pytest.skip("EdgeAI dependencies not available")

    @pytest.mark.asyncio
    async def test_import_hybrid_adapter(self) -> None:
        """Test importing hybrid AI adapter."""
        try:
            from acb.adapters.ai.hybrid import HybridAI

            assert HybridAI is not None
            assert HybridAI.__name__ == "HybridAI"
        except ImportError:
            pytest.skip("HybridAI dependencies not available")

    @pytest.mark.asyncio
    async def test_cloud_adapter_full_workflow(self) -> None:
        """Test complete workflow with cloud adapter."""
        try:
            from acb.adapters.ai.cloud import CloudAI

            with patch("acb.adapters.ai.cloud.validate_request") as mock_validate:
                mock_validate.return_value = None

                # Mock OpenAI client and response
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = "Hello from OpenAI!"
                mock_response.choices[0].message.function_call = None
                mock_response.choices[0].message.tool_calls = None
                mock_response.choices[0].finish_reason = "stop"
                mock_response.model = "gpt-3.5-turbo"
                mock_response.usage.total_tokens = 25

                mock_client.chat.completions.create = AsyncMock(
                    return_value=mock_response
                )

                # Create adapter and test workflow
                adapter = CloudAI(
                    provider=ModelProvider.OPENAI,
                    openai_api_key="test-key",
                )
                # Set the mock client directly
                adapter._client = mock_client

                # Test text generation
                request = AIRequest(prompt="Hello, world!")
                response = await adapter.generate_text(request)

                assert response.content == "Hello from OpenAI!"
                assert response.provider == ModelProvider.OPENAI
                assert response.strategy == DeploymentStrategy.CLOUD

                # Test model listing
                models = await adapter.get_available_models()
                assert len(models) > 0

                # Test health check
                health = await adapter.health_check()
                assert health["status"] == "healthy"
        except ImportError:
            pytest.skip("CloudAI dependencies not available")

    @pytest.mark.asyncio
    async def test_edge_adapter_full_workflow(self) -> None:
        """Test complete workflow with edge adapter."""
        from acb.adapters.ai.edge import EdgeAI

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("acb.adapters.ai.edge.validate_request") as mock_validate,
        ):
            # Mock HTTP client for Ollama
            mock_client = MagicMock()

            # Mock tags response
            tags_response = MagicMock()
            tags_response.status_code = 200
            tags_response.json.return_value = {
                "models": [{"name": "llama2:7b", "size": 3800000000}]
            }

            # Mock generation response
            generate_response = MagicMock()
            generate_response.status_code = 200
            generate_response.json.return_value = {
                "response": "Hello from Ollama!",
                "model": "llama2:7b",
                "done": True,
                "eval_count": 15,
                "prompt_eval_count": 8,
            }

            mock_client.get = AsyncMock(return_value=tags_response)
            mock_client.post = AsyncMock(return_value=generate_response)
            mock_client_class.return_value = mock_client
            mock_validate.return_value = None

            # Create adapter and test workflow
            adapter = EdgeAI(
                provider=ModelProvider.OLLAMA,
                model_preload=False,  # Skip preload for test
            )

            # Test text generation
            request = AIRequest(prompt="Hello, edge!")
            response = await adapter.generate_text(request)

            assert response.content == "Hello from Ollama!"
            assert response.provider == ModelProvider.OLLAMA
            assert response.strategy == DeploymentStrategy.EDGE

            # Test optimization
            optimizations = await adapter.optimize_for_edge("llama2:7b")
            assert "quantization_applied" in optimizations

    @pytest.mark.asyncio
    async def test_hybrid_adapter_routing_workflow(self) -> None:
        """Test complete workflow with hybrid adapter including routing."""
        from acb.adapters.ai.hybrid import HybridAI, RoutingStrategy

        with (
            patch("acb.adapters.ai.hybrid.CloudAI") as mock_cloud_ai,
            patch("acb.adapters.ai.hybrid.EdgeAI") as mock_edge_ai,
            patch("acb.adapters.ai.hybrid.validate_request") as mock_validate,
        ):
            # Mock cloud adapter
            mock_cloud_adapter = MagicMock()
            mock_cloud_response = MagicMock()
            mock_cloud_response.content = "Cloud response"
            mock_cloud_response.provider = ModelProvider.OPENAI
            mock_cloud_response.strategy = DeploymentStrategy.CLOUD
            mock_cloud_adapter._generate_text = AsyncMock(
                return_value=mock_cloud_response
            )
            mock_cloud_adapter.health_check = AsyncMock(
                return_value={"status": "healthy"}
            )

            # Mock edge adapter
            mock_edge_adapter = MagicMock()
            mock_edge_response = MagicMock()
            mock_edge_response.content = "Edge response"
            mock_edge_response.provider = ModelProvider.OLLAMA
            mock_edge_response.strategy = DeploymentStrategy.EDGE
            mock_edge_adapter._generate_text = AsyncMock(
                return_value=mock_edge_response
            )
            mock_edge_adapter.health_check = AsyncMock(
                return_value={"status": "healthy"}
            )

            mock_cloud_ai.return_value = mock_cloud_adapter
            mock_edge_ai.return_value = mock_edge_adapter
            mock_validate.return_value = None

            # Create hybrid adapter
            adapter = HybridAI(routing_strategy=RoutingStrategy.LATENCY)

            # Test low-latency routing (should go to edge)
            request = AIRequest(prompt="Fast response needed", max_latency_ms=300)
            response = await adapter.generate_text(request)

            # Should route to edge for low latency
            mock_edge_adapter._generate_text.assert_called()
            assert response.content == "Edge response"

            # Test routing stats
            stats = await adapter.get_routing_stats()
            assert "routing_strategy" in stats
            assert "performance_metrics" in stats

    @pytest.mark.asyncio
    async def test_prompt_template_workflow(self) -> None:
        """Test prompt template system."""
        try:
            from acb.adapters.ai.cloud import CloudAI

            with patch("acb.adapters.ai.cloud.validate_request") as mock_validate:
                mock_validate.return_value = None

                # Mock OpenAI client
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = "Template response"
                mock_response.choices[0].message.function_call = None
                mock_response.choices[0].message.tool_calls = None
                mock_response.choices[0].finish_reason = "stop"
                mock_response.model = "gpt-3.5-turbo"
                mock_response.usage.total_tokens = 20

                mock_client.chat.completions.create = AsyncMock(
                    return_value=mock_response
                )

                adapter = CloudAI(
                    provider=ModelProvider.OPENAI,
                    openai_api_key="test-key",
                )
                # Set the mock client directly
                adapter._client = mock_client

                # Register template
                template = PromptTemplate(
                    name="greeting",
                    template="Hello, {name}! Welcome to {service}.",
                    variables=["name", "service"],
                    default_values={"service": "our AI service"},
                )
                await adapter.register_template(template)

                # Render template
                rendered = await adapter.render_template("greeting", name="Alice")
                assert rendered == "Hello, Alice! Welcome to our AI service."

                # Use template in request
                request = AIRequest(prompt=rendered)
                response = await adapter.generate_text(request)
                assert response.content == "Template response"
        except ImportError:
            pytest.skip("CloudAI dependencies not available")

    @pytest.mark.asyncio
    async def test_multimodal_processing(self) -> None:
        """Test multimodal processing capabilities."""
        try:
            from acb.adapters.ai.cloud import CloudAI

            with patch("acb.adapters.ai.cloud.validate_request") as mock_validate:
                mock_validate.return_value = None

                # Mock OpenAI client for vision
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = "I see an image of a cat"
                mock_response.choices[0].message.function_call = None
                mock_response.choices[0].message.tool_calls = None
                mock_response.choices[0].finish_reason = "stop"
                mock_response.model = "gpt-4-vision-preview"
                mock_response.usage.total_tokens = 30

                mock_client.chat.completions.create = AsyncMock(
                    return_value=mock_response
                )

                adapter = CloudAI(
                    provider=ModelProvider.OPENAI,
                    openai_api_key="test-key",
                )
                # Set the mock client directly
                adapter._client = mock_client

                # Test image processing
                request = AIRequest(
                    prompt="Describe this image",
                    model="gpt-4-vision-preview",
                    images=["data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD..."],
                )

                response = await adapter.process_multimodal(request)
                assert response.content == "I see an image of a cat"
        except ImportError:
            pytest.skip("CloudAI dependencies not available")

    @pytest.mark.asyncio
    async def test_error_handling_and_fallback(self) -> None:
        """Test error handling and fallback mechanisms."""
        from acb.adapters.ai.hybrid import HybridAI

        with (
            patch("acb.adapters.ai.hybrid.CloudAI") as mock_cloud_ai,
            patch("acb.adapters.ai.hybrid.EdgeAI") as mock_edge_ai,
            patch("acb.adapters.ai.hybrid.validate_request") as mock_validate,
        ):
            # Mock cloud adapter that fails
            mock_cloud_adapter = MagicMock()
            mock_cloud_adapter._generate_text = AsyncMock(
                side_effect=Exception("Cloud service unavailable")
            )

            # Mock edge adapter that succeeds
            mock_edge_adapter = MagicMock()
            mock_edge_response = MagicMock()
            mock_edge_response.content = "Fallback response"
            mock_edge_response.provider = ModelProvider.OLLAMA
            mock_edge_response.strategy = DeploymentStrategy.EDGE
            mock_edge_adapter._generate_text = AsyncMock(
                return_value=mock_edge_response
            )

            mock_cloud_ai.return_value = mock_cloud_adapter
            mock_edge_ai.return_value = mock_edge_adapter
            mock_validate.return_value = None

            # Create hybrid adapter with fallback enabled
            adapter = HybridAI(
                cloud_fallback_enabled=False,
                edge_fallback_enabled=True,  # Enable edge fallback
            )

            # Force routing to cloud (which will fail)
            request = AIRequest(
                prompt="Test", min_quality_score=0.95
            )  # Should route to cloud
            response = await adapter.generate_text(request)

            # Should fallback to edge
            assert response.content == "Fallback response"
            assert response.provider == ModelProvider.OLLAMA

    @pytest.mark.asyncio
    async def test_performance_tracking(self) -> None:
        """Test performance tracking and optimization."""
        from acb.adapters.ai.hybrid import HybridAI

        with (
            patch("acb.adapters.ai.hybrid.CloudAI") as mock_cloud_ai,
            patch("acb.adapters.ai.hybrid.EdgeAI") as mock_edge_ai,
            patch("acb.adapters.ai.hybrid.validate_request") as mock_validate,
        ):
            # Setup mock adapters
            mock_cloud_adapter = MagicMock()
            mock_edge_adapter = MagicMock()

            # Edge is faster
            mock_edge_response = MagicMock()
            mock_edge_response.content = "Fast edge response"
            mock_edge_response.provider = ModelProvider.OLLAMA
            mock_edge_response.strategy = DeploymentStrategy.EDGE
            mock_edge_adapter._generate_text = AsyncMock(
                return_value=mock_edge_response
            )

            # Cloud is slower
            async def slow_cloud_generate(*args, **kwargs):
                await asyncio.sleep(0.1)  # Simulate slower response
                response = MagicMock()
                response.content = "Slow cloud response"
                response.provider = ModelProvider.OPENAI
                response.strategy = DeploymentStrategy.CLOUD
                return response

            mock_cloud_adapter._generate_text = slow_cloud_generate

            mock_cloud_ai.return_value = mock_cloud_adapter
            mock_edge_ai.return_value = mock_edge_adapter
            mock_validate.return_value = None

            # Create adaptive hybrid adapter
            adapter = HybridAI(
                routing_strategy="adaptive",
                track_performance=True,
            )

            # Generate some history
            request = AIRequest(prompt="Test adaptive routing")

            # First few requests to build history
            for _ in range(5):
                await adapter.generate_text(request)

            # Check that performance is being tracked
            stats = await adapter.get_routing_stats()
            assert stats["routing_history_size"] > 0
            assert "performance_metrics" in stats

    @pytest.mark.asyncio
    async def test_dependency_injection_integration(self) -> None:
        """Test integration with ACB dependency injection system."""
        try:
            from acb.adapters.ai.cloud import CloudAI
            from acb.config import Config
            from acb.depends import depends

            # Create a mock config and register it in the container
            mock_config = MagicMock(spec=Config)
            mock_config.deployed = False

            # Temporarily set the config in the depends container
            original_config = None
            try:
                original_config = depends.get(Config)
            except Exception:
                pass

            depends.set(Config, mock_config)

            try:
                # Test dependency injection in settings
                adapter = CloudAI(
                    provider=ModelProvider.OPENAI,
                    openai_api_key="test-key",
                )

                # Verify adapter was created successfully with injected config
                assert adapter is not None
                assert adapter.settings.provider == ModelProvider.OPENAI
            finally:
                # Restore original config if it existed
                if original_config is not None:
                    depends.set(Config, original_config)
        except ImportError:
            pytest.skip("CloudAI dependencies not available")

    def test_adapter_metadata_completeness(self) -> None:
        """Test that all AI adapters have complete metadata."""
        from acb.adapters.ai.cloud import MODULE_METADATA as cloud_metadata
        from acb.adapters.ai.edge import MODULE_METADATA as edge_metadata
        from acb.adapters.ai.hybrid import MODULE_METADATA as hybrid_metadata

        for metadata in [cloud_metadata, edge_metadata, hybrid_metadata]:
            assert metadata.name
            assert metadata.category == "ai"
            assert metadata.provider
            assert metadata.version
            assert metadata.description
            assert metadata.required_packages
            assert metadata.capabilities
