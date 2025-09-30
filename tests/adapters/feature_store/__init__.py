"""Feature Store Adapter Tests.

This module contains comprehensive tests for all feature store adapter implementations.

Test Structure:
- test_feature_store_base.py: Base adapter functionality and data models
- test_feast.py: Feast open-source feature store tests
- test_tecton.py: Tecton enterprise feature platform tests
- test_aws.py: AWS SageMaker Feature Store tests
- test_vertex.py: Google Cloud Vertex AI Feature Store tests
- test_custom.py: Custom file/SQLite-based implementation tests

Each test module covers:
- Adapter initialization and configuration
- Online and offline feature serving
- Feature registration and management
- Feature group and view operations
- Monitoring and data quality validation
- Error handling and health checks
- Context manager functionality

All tests use proper mocking to avoid external dependencies
and follow ACB testing patterns for adapter implementations.
"""