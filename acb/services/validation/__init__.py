"""Validation Services Package.

This package provides comprehensive data validation services for ACB applications,
including schema validation, input sanitization, output contract validation,
and security-focused validation utilities.

Key Components:
    - ValidationService: Main validation service with dependency injection
    - ValidationSchema: Base schema validation system
    - InputSanitizer: XSS and injection prevention utilities
    - OutputValidator: API consistency through contract validation
    - ValidationDecorators: Easy integration decorators
    - ValidationResults: Result aggregation and error reporting

Performance:
    - <1ms validation for standard schemas
    - Optimized for high-throughput applications
    - Memory efficient with schema caching

Security:
    - XSS prevention through HTML sanitization
    - SQL injection protection
    - Path traversal prevention
    - Input validation for security compliance

Integration:
    - Services Layer: Full ServiceBase integration
    - Models Adapter: Pydantic, msgspec, SQLModel support
    - Health Check System: Monitoring and metrics
    - Dependency Injection: Seamless ACB integration
"""

from acb.services.validation._base import (
    ValidationConfig,
    ValidationLevel,
    ValidationResult,
    ValidationSettings,
)
from acb.services.validation.decorators import (
    sanitize_input,
    validate_contracts,
    validate_input,
    validate_output,
    validate_schema,
)
from acb.services.validation.results import (
    ValidationError,
    ValidationReport,
    ValidationWarning,
)
from acb.services.validation.service import ValidationService

__all__ = [
    # Configuration and settings
    "ValidationConfig",
    "ValidationError",
    "ValidationLevel",
    "ValidationReport",
    # Results and errors
    "ValidationResult",
    # Core service
    "ValidationService",
    "ValidationSettings",
    "ValidationWarning",
    "sanitize_input",
    "validate_contracts",
    # Decorators
    "validate_input",
    "validate_output",
    "validate_schema",
]
