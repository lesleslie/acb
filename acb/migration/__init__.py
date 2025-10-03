"""ACB Migration and Compatibility Tools.

This module provides tools for migrating existing ACB installations to new
architectures and maintaining backward compatibility.

Key Components:
    - Migration assessment and version detection
    - Automated configuration migration
    - Compatibility layers for deprecated interfaces
    - Rollback mechanisms
    - Migration testing and validation

Usage:
    from acb.migration import MigrationManager, assess_migration

    # Assess current installation
    assessment = await assess_migration()

    # Perform migration
    manager = MigrationManager()
    result = await manager.migrate(target_version="0.20.0")
"""

from acb.migration._base import MigrationStatus
from acb.migration.assessment import (
    MigrationAssessment,
    assess_migration,
    detect_version,
)
from acb.migration.compatibility import CompatibilityLayer, get_compatibility_layer
from acb.migration.manager import (
    MigrationManager,
    MigrationResult,
)
from acb.migration.rollback import RollbackManager, RollbackPoint
from acb.migration.validator import MigrationValidator, ValidationResult

__all__ = [
    # Compatibility
    "CompatibilityLayer",
    # Assessment
    "MigrationAssessment",
    # Manager
    "MigrationManager",
    "MigrationResult",
    "MigrationStatus",
    # Validation
    "MigrationValidator",
    # Rollback
    "RollbackManager",
    "RollbackPoint",
    "ValidationResult",
    "assess_migration",
    "detect_version",
    "get_compatibility_layer",
]
