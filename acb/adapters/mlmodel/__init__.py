"""ML Model Adapter Package.

This package provides comprehensive ML model serving adapters for the ACB framework,
supporting multiple platforms and deployment patterns for production ML workloads.

Available Adapters:
- TensorFlow Serving: High-performance serving with gRPC and REST support
- TorchServe: PyTorch model serving with management API and auto-scaling
- MLflow: Model registry and serving with experiment tracking
- KServe: Kubernetes-native serving with auto-scaling and canary deployments
- BentoML: Model packaging and serving with automatic API generation

Key Features:
- Real-time and batch inference
- Model versioning and A/B testing
- Auto-scaling and canary deployments
- Health monitoring and performance metrics
- Production-ready deployment patterns
- Edge deployment optimization
- Hybrid cloud-edge architectures
"""

from ._base import (
    BaseMLModelAdapter,
    MLModelSettings,
    ModelPredictionRequest,
    ModelPredictionResponse,
    BatchPredictionRequest,
    BatchPredictionResponse,
    ModelInfo,
    ModelHealth,
)

__all__ = [
    "BaseMLModelAdapter",
    "MLModelSettings",
    "ModelPredictionRequest",
    "ModelPredictionResponse",
    "BatchPredictionRequest",
    "BatchPredictionResponse",
    "ModelInfo",
    "ModelHealth",
]