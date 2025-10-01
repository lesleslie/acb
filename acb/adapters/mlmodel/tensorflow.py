"""TensorFlow Serving ML Model Adapter.

This adapter provides integration with TensorFlow Serving for scalable
model inference using both REST and gRPC protocols. It supports model
versioning, health monitoring, and performance optimization.
"""

from __future__ import annotations

import time
from typing import Any

import aiohttp
import grpc
import numpy as np
import pandas as pd
from pydantic import Field
from acb.adapters import (
    AdapterCapability,
    AdapterMetadata,
    AdapterStatus,
    generate_adapter_id,
)
from acb.adapters.mlmodel._base import (
    BaseMLModelAdapter,
    BatchPredictionRequest,
    BatchPredictionResponse,
    MLModelSettings,
    ModelHealth,
    ModelInfo,
    ModelPredictionRequest,
    ModelPredictionResponse,
)

try:
    from tensorflow.core.framework import tensor_pb2, types_pb2
    from tensorflow_serving.apis import (
        predict_pb2,
        prediction_service_pb2_grpc,
    )

    TENSORFLOW_SERVING_AVAILABLE = True
except ImportError:
    TENSORFLOW_SERVING_AVAILABLE = False


class TensorFlowServingSettings(MLModelSettings):
    """TensorFlow Serving specific settings."""

    # Protocol settings
    use_grpc: bool = Field(
        default=True,
        description="Use gRPC protocol (faster) vs REST",
    )
    grpc_port: int = Field(default=8500, description="gRPC port")
    rest_port: int = Field(default=8501, description="REST API port")

    # Model settings
    model_signature_name: str = Field(
        default="serving_default",
        description="Model signature name",
    )

    # Performance settings
    enable_model_warmup: bool = Field(
        default=True,
        description="Enable model warmup on startup",
    )
    warmup_requests: int = Field(default=5, description="Number of warmup requests")

    # gRPC specific settings
    grpc_max_receive_message_length: int = Field(
        default=4 * 1024 * 1024,
        description="Max gRPC message size (4MB)",
    )
    grpc_max_send_message_length: int = Field(
        default=4 * 1024 * 1024,
        description="Max gRPC send message size (4MB)",
    )


class TensorFlowServingAdapter(BaseMLModelAdapter):
    """TensorFlow Serving adapter for ML model inference.

    This adapter provides high-performance model serving using TensorFlow Serving
    with support for both REST and gRPC protocols, model versioning, and
    production-ready features like health monitoring and performance optimization.
    """

    def __init__(self, settings: TensorFlowServingSettings | None = None) -> None:
        """Initialize TensorFlow Serving adapter.

        Args:
            settings: TensorFlow Serving specific settings
        """
        self._tf_settings = settings or TensorFlowServingSettings()
        super().__init__(self._tf_settings)
        self._grpc_channel: grpc.aio.Channel | None = None
        self._grpc_stub = None
        self._http_session: aiohttp.ClientSession | None = None

    @property
    def tf_settings(self) -> TensorFlowServingSettings:
        """Get TensorFlow Serving specific settings."""
        return self._tf_settings

    async def _create_client(self) -> dict[str, Any]:
        """Create TensorFlow Serving client(s)."""
        clients = {}

        if self.tf_settings.use_grpc and TENSORFLOW_SERVING_AVAILABLE:
            # Create gRPC channel and stub
            grpc_options = [
                (
                    "grpc.max_receive_message_length",
                    self.tf_settings.grpc_max_receive_message_length,
                ),
                (
                    "grpc.max_send_message_length",
                    self.tf_settings.grpc_max_send_message_length,
                ),
            ]

            grpc_target = f"{self.tf_settings.host}:{self.tf_settings.grpc_port}"
            if self.tf_settings.use_tls:
                self._grpc_channel = grpc.aio.secure_channel(
                    grpc_target,
                    grpc.ssl_channel_credentials(),
                    options=grpc_options,
                )
            else:
                self._grpc_channel = grpc.aio.insecure_channel(
                    grpc_target,
                    options=grpc_options,
                )

            self._grpc_stub = prediction_service_pb2_grpc.PredictionServiceStub(
                self._grpc_channel,
            )
            clients["grpc"] = self._grpc_stub

        # Create HTTP session for REST API
        connector = aiohttp.TCPConnector(limit=self.tf_settings.connection_pool_size)
        timeout = aiohttp.ClientTimeout(total=self.tf_settings.timeout)
        headers = {"Content-Type": "application/json"}
        headers.update(self.tf_settings.custom_headers)

        self._http_session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=headers,
        )
        clients["http"] = self._http_session

        return clients

    def _get_rest_url(self, model_name: str, version: str | None = None) -> str:
        """Get REST API URL for model."""
        protocol = "https" if self.tf_settings.use_tls else "http"
        base_url = f"{protocol}://{self.tf_settings.host}:{self.tf_settings.rest_port}"

        if version:
            return f"{base_url}/v1/models/{model_name}/versions/{version}:predict"
        return f"{base_url}/v1/models/{model_name}:predict"

    def _prepare_grpc_request(
        self,
        model_name: str,
        inputs: dict[str, Any],
        version: str | None = None,
    ) -> predict_pb2.PredictRequest:
        """Prepare gRPC prediction request."""
        if not TENSORFLOW_SERVING_AVAILABLE:
            msg = "TensorFlow Serving gRPC libraries not available"
            raise RuntimeError(msg)

        request = predict_pb2.PredictRequest()
        request.model_spec.name = model_name
        request.model_spec.signature_name = self.tf_settings.model_signature_name

        if version:
            request.model_spec.version.value = int(version)

        # Convert inputs to tensor format
        for input_name, input_data in inputs.items():
            tensor = tensor_pb2.TensorProto()

            if isinstance(input_data, list | np.ndarray):
                input_array = np.array(input_data)
                tensor.dtype = types_pb2.DT_FLOAT
                tensor.tensor_shape.CopyFrom(
                    tensor_pb2.TensorShapeProto(
                        dim=[
                            tensor_pb2.TensorShapeProto.Dim(size=s)
                            for s in input_array.shape
                        ],
                    ),
                )
                tensor.float_val.extend(input_array.flatten().astype(float))
            else:
                # Handle other data types as needed
                tensor.dtype = types_pb2.DT_STRING
                tensor.string_val.append(str(input_data).encode("utf-8"))

            request.inputs[input_name].CopyFrom(tensor)

        return request

    def _process_grpc_response(
        self,
        response: predict_pb2.PredictResponse,
        model_name: str,
        version: str | None,
    ) -> dict[str, Any]:
        """Process gRPC prediction response."""
        outputs = {}

        for output_name, tensor in response.outputs.items():
            if tensor.dtype == types_pb2.DT_FLOAT:
                shape = [dim.size for dim in tensor.tensor_shape.dim]
                outputs[output_name] = (
                    np.array(tensor.float_val).reshape(shape).tolist()
                )
            elif tensor.dtype == types_pb2.DT_STRING:
                outputs[output_name] = [s.decode("utf-8") for s in tensor.string_val]
            else:
                # Handle other data types
                outputs[output_name] = tensor.string_val

        return outputs

    async def predict(self, request: ModelPredictionRequest) -> ModelPredictionResponse:
        """Perform real-time inference using TensorFlow Serving."""
        start_time = time.time()

        try:
            client = await self._ensure_client()

            if (
                self.tf_settings.use_grpc
                and TENSORFLOW_SERVING_AVAILABLE
                and "grpc" in client
            ):
                # Use gRPC for better performance
                grpc_request = self._prepare_grpc_request(
                    request.model_name,
                    request.inputs,
                    request.model_version,
                )

                response = await self._grpc_stub.Predict(
                    grpc_request,
                    timeout=request.timeout or self.tf_settings.timeout,
                )

                predictions = self._process_grpc_response(
                    response,
                    request.model_name,
                    request.model_version,
                )

            else:
                # Use REST API
                url = self._get_rest_url(request.model_name, request.model_version)
                payload = {
                    "signature_name": self.tf_settings.model_signature_name,
                    "inputs": request.inputs,
                }

                async with self._http_session.post(url, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        msg = f"TensorFlow Serving error: {error_text}"
                        raise RuntimeError(msg)

                    result = await response.json()
                    predictions = result.get("outputs", {})

            latency_ms = (time.time() - start_time) * 1000

            # Update metrics
            self._metrics["predictions_total"] = (
                self._metrics.get("predictions_total", 0) + 1
            )
            self._metrics["avg_latency_ms"] = (
                self._metrics.get("avg_latency_ms", 0) * 0.9 + latency_ms * 0.1
            )

            return ModelPredictionResponse(
                predictions=predictions,
                model_name=request.model_name,
                model_version=request.model_version or "latest",
                latency_ms=latency_ms,
                metadata=request.metadata,
            )

        except Exception as e:
            self._metrics["errors_total"] = self._metrics.get("errors_total", 0) + 1
            msg = f"TensorFlow Serving prediction failed: {e}"
            raise RuntimeError(msg)

    async def batch_predict(
        self,
        request: BatchPredictionRequest,
    ) -> BatchPredictionResponse:
        """Perform batch inference using TensorFlow Serving."""
        start_time = time.time()

        try:
            # Process in batches to optimize performance
            batch_size = min(
                request.batch_size or self.tf_settings.max_batch_size,
                len(request.inputs),
            )
            all_predictions = []

            for i in range(0, len(request.inputs), batch_size):
                batch_inputs = request.inputs[i : i + batch_size]

                # Combine batch inputs for efficient processing
                combined_inputs = {}
                for key in batch_inputs[0]:
                    combined_inputs[key] = [item[key] for item in batch_inputs]

                # Create prediction request for batch
                pred_request = ModelPredictionRequest(
                    inputs=combined_inputs,
                    model_name=request.model_name,
                    model_version=request.model_version,
                    timeout=request.timeout,
                    metadata=request.metadata,
                )

                pred_response = await self.predict(pred_request)

                # Split batch predictions back to individual predictions
                batch_predictions = []
                for j in range(len(batch_inputs)):
                    individual_pred = {}
                    for output_name, output_values in pred_response.predictions.items():
                        if isinstance(output_values, list) and len(output_values) > j:
                            individual_pred[output_name] = output_values[j]
                        else:
                            individual_pred[output_name] = output_values
                    batch_predictions.append(individual_pred)

                all_predictions.extend(batch_predictions)

            total_latency_ms = (time.time() - start_time) * 1000
            avg_latency_ms = total_latency_ms / len(request.inputs)

            return BatchPredictionResponse(
                predictions=all_predictions,
                model_name=request.model_name,
                model_version=request.model_version or "latest",
                batch_size=len(request.inputs),
                total_latency_ms=total_latency_ms,
                avg_latency_ms=avg_latency_ms,
                metadata=request.metadata,
            )

        except Exception as e:
            self._metrics["batch_errors_total"] = (
                self._metrics.get("batch_errors_total", 0) + 1
            )
            msg = f"TensorFlow Serving batch prediction failed: {e}"
            raise RuntimeError(msg)

    async def list_models(self) -> list[ModelInfo]:
        """List available models from TensorFlow Serving."""
        try:
            await self._ensure_client()

            # Use REST API to get model metadata
            protocol = "https" if self.tf_settings.use_tls else "http"
            url = f"{protocol}://{self.tf_settings.host}:{self.tf_settings.rest_port}/v1/models"

            async with self._http_session.get(url) as response:
                if response.status != 200:
                    error_text = await response.text()
                    msg = f"Failed to list models: {error_text}"
                    raise RuntimeError(msg)

                result = await response.json()
                models = []

                for model_info in result.get("models", []):
                    model_name = model_info.get("name", "")
                    versions = model_info.get("version_labels", {})

                    # Get detailed info for each version
                    for version, status in versions.items():
                        models.append(
                            ModelInfo(
                                name=model_name,
                                version=str(version),
                                status=status.get("state", "unknown").lower(),
                                framework="tensorflow",
                                metadata={
                                    "platform": "tensorflow_serving",
                                    "protocol": "grpc"
                                    if self.tf_settings.use_grpc
                                    else "rest",
                                },
                            ),
                        )

                return models

        except Exception as e:
            msg = f"Failed to list TensorFlow Serving models: {e}"
            raise RuntimeError(msg)

    async def get_model_info(
        self,
        model_name: str,
        version: str | None = None,
    ) -> ModelInfo:
        """Get detailed information about a specific model."""
        try:
            # Use REST API to get model metadata
            protocol = "https" if self.tf_settings.use_tls else "http"

            if version:
                url = f"{protocol}://{self.tf_settings.host}:{self.tf_settings.rest_port}/v1/models/{model_name}/versions/{version}/metadata"
            else:
                url = f"{protocol}://{self.tf_settings.host}:{self.tf_settings.rest_port}/v1/models/{model_name}/metadata"

            async with self._http_session.get(url) as response:
                if response.status != 200:
                    error_text = await response.text()
                    msg = f"Model not found: {error_text}"
                    raise RuntimeError(msg)

                result = await response.json()
                metadata = result.get("metadata", {})

                return ModelInfo(
                    name=model_name,
                    version=version or str(result.get("model_version", "latest")),
                    status="ready",
                    framework="tensorflow",
                    input_schema=metadata.get("signature_def", {}).get("inputs"),
                    output_schema=metadata.get("signature_def", {}).get("outputs"),
                    metadata={
                        "platform": "tensorflow_serving",
                        "protocol": "grpc" if self.tf_settings.use_grpc else "rest",
                        "signature_def": metadata.get("signature_def"),
                    },
                )

        except Exception as e:
            msg = f"Failed to get TensorFlow Serving model info: {e}"
            raise RuntimeError(msg)

    async def get_model_health(
        self,
        model_name: str,
        version: str | None = None,
    ) -> ModelHealth:
        """Get health status of a specific model."""
        try:
            # Use model status endpoint
            protocol = "https" if self.tf_settings.use_tls else "http"

            if version:
                url = f"{protocol}://{self.tf_settings.host}:{self.tf_settings.rest_port}/v1/models/{model_name}/versions/{version}"
            else:
                url = f"{protocol}://{self.tf_settings.host}:{self.tf_settings.rest_port}/v1/models/{model_name}"

            async with self._http_session.get(url) as response:
                if response.status != 200:
                    return ModelHealth(
                        model_name=model_name,
                        model_version=version or "latest",
                        status="unhealthy",
                        last_check=pd.Timestamp.now().isoformat(),
                    )

                result = await response.json()
                model_version_status = result.get("model_version_status", [])

                if model_version_status:
                    status_info = model_version_status[0]
                    state = status_info.get("state", "unknown").lower()
                    health_status = "healthy" if state == "available" else "unhealthy"
                else:
                    health_status = "unknown"

                # Get performance metrics from adapter metrics
                return ModelHealth(
                    model_name=model_name,
                    model_version=version or "latest",
                    status=health_status,
                    latency_p95=self._metrics.get("avg_latency_ms"),
                    error_rate=self._metrics.get("error_rate", 0.0),
                    last_check=pd.Timestamp.now().isoformat(),
                    metadata={
                        "state": state,
                        "platform": "tensorflow_serving",
                    },
                )

        except Exception as e:
            return ModelHealth(
                model_name=model_name,
                model_version=version or "latest",
                status="error",
                last_check=pd.Timestamp.now().isoformat(),
                metadata={"error": str(e)},
            )

    async def health_check(self) -> bool:
        """Perform adapter health check."""
        try:
            await self._ensure_client()

            # Check TensorFlow Serving health
            protocol = "https" if self.tf_settings.use_tls else "http"
            url = f"{protocol}://{self.tf_settings.host}:{self.tf_settings.rest_port}/v1/models"

            async with self._http_session.get(url) as response:
                return response.status == 200

        except Exception:
            return False

    async def cleanup(self) -> None:
        """Cleanup resources."""
        await super().cleanup()

        if self._grpc_channel:
            await self._grpc_channel.close()
            self._grpc_channel = None

        if self._http_session:
            await self._http_session.close()
            self._http_session = None


# Create the main adapter class alias for consistency
MLModel = TensorFlowServingAdapter

# Module metadata for the adapter
MODULE_METADATA = AdapterMetadata(
    module_id=generate_adapter_id(),
    name="TensorFlow Serving ML Model",
    category="mlmodel",
    provider="tensorflow",
    version="1.0.0",
    acb_min_version="0.19.0",
    author="ACB Framework",
    created_date="2025-01-20",
    last_modified="2025-01-20",
    status=AdapterStatus.STABLE,
    capabilities=[
        AdapterCapability.MODEL_SERVING,
        AdapterCapability.REAL_TIME_INFERENCE,
        AdapterCapability.BATCH_INFERENCE,
        AdapterCapability.MODEL_VERSIONING,
        AdapterCapability.MODEL_MONITORING,
        AdapterCapability.HEALTH_CHECKS,
        AdapterCapability.GRPC_SERVING,
        AdapterCapability.REST_SERVING,
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.CONNECTION_POOLING,
        AdapterCapability.PERFORMANCE_MONITORING,
        AdapterCapability.METRICS,
    ],
    required_packages=[
        "tensorflow-serving-api>=2.11.0",
        "grpcio>=1.50.0",
        "protobuf>=4.0.0",
        "aiohttp>=3.9.0",
        "numpy>=1.24.0",
        "pandas>=2.0.0",
    ],
    description="High-performance TensorFlow Serving adapter with gRPC and REST support for scalable ML model inference",
    settings_class="TensorFlowServingSettings",
    config_example={
        "host": "localhost",
        "grpc_port": 8500,
        "rest_port": 8501,
        "use_grpc": True,
        "use_tls": False,
        "timeout": 30.0,
        "default_model_name": "my_model",
        "model_signature_name": "serving_default",
        "enable_metrics": True,
        "enable_health_checks": True,
    },
)
