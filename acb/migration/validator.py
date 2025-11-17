"""Migration validation and verification."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from typing import TYPE_CHECKING

from acb.depends import depends
from acb.logger import Logger as LoggerAdapter
from acb.migration._base import (
    MigrationConfig,
    MigrationSeverity,
)

if TYPE_CHECKING:
    from pathlib import Path

logger = depends.get_sync(LoggerAdapter)


class ValidationIssue(BaseModel):
    """Issue found during validation."""

    severity: MigrationSeverity
    component: str
    message: str
    fix_suggestion: str | None = None

    model_config = ConfigDict(frozen=True)


class ValidationResult(BaseModel):
    """Result of migration validation."""

    success: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
    checks_passed: int = 0
    checks_failed: int = 0

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def has_critical_issues(self) -> bool:
        """Check if validation has critical issues."""
        return any(
            issue.severity == MigrationSeverity.CRITICAL for issue in self.issues
        )

    @property
    def has_errors(self) -> bool:
        """Check if validation has errors."""
        return any(
            issue.severity in (MigrationSeverity.ERROR, MigrationSeverity.CRITICAL)
            for issue in self.issues
        )


class MigrationValidator:
    """Validates migration results and system state.

    Example:
        >>> validator = MigrationValidator()
        >>> result = await validator.validate_migration(
        ...     project_root=Path.cwd(),
        ...     config=migration_config,
        ... )
        >>> if not result.success:
        ...     print(f"Validation failed: {result.issues}")
    """

    def __init__(self) -> None:
        """Initialize migration validator."""
        self.issues: list[ValidationIssue] = []

    async def validate_migration(
        self,
        project_root: Path,
        config: MigrationConfig,
    ) -> ValidationResult:
        """Validate migration results.

        Args:
            project_root: Project root directory
            config: Migration configuration

        Returns:
            Validation result with any issues found
        """
        logger.info("Validating migration results")
        self.issues = []
        checks_passed = 0
        checks_failed = 0

        # Validate configuration structure
        if await self._validate_config_structure(project_root):
            checks_passed += 1
        else:
            checks_failed += 1

        # Validate adapter configuration
        if await self._validate_adapter_config(project_root):
            checks_passed += 1
        else:
            checks_failed += 1

        # Validate file permissions
        if await self._validate_file_permissions(project_root):
            checks_passed += 1
        else:
            checks_failed += 1

        # Validate dependencies
        if await self._validate_dependencies(project_root):
            checks_passed += 1
        else:
            checks_failed += 1

        # Validate backup integrity
        if config.backup_enabled and config.backup_directory:
            if await self._validate_backup_integrity(config.backup_directory):
                checks_passed += 1
            else:
                checks_failed += 1

        # Determine success
        success = not self.has_critical_issues()

        logger.info(
            f"Validation complete: {checks_passed} passed, {checks_failed} failed",
        )

        return ValidationResult(
            success=success,
            issues=self.issues.copy(),
            checks_passed=checks_passed,
            checks_failed=checks_failed,
        )

    async def _validate_config_structure(self, project_root: Path) -> bool:
        """Validate configuration directory structure.

        Args:
            project_root: Project root directory

        Returns:
            True if configuration structure is valid
        """
        settings_dir = project_root / "settings"

        if not settings_dir.exists():
            self._add_issue(
                severity=MigrationSeverity.ERROR,
                component="configuration",
                message="settings/ directory not found",
                fix_suggestion="Create settings/ directory and add configuration files",
            )
            return False

        # Check for required files
        required_files = ["app.yaml", "adapters.yaml"]
        missing_files = [
            required_file
            for required_file in required_files
            if not (settings_dir / required_file).exists()
        ]

        if missing_files:
            self._add_issue(
                severity=MigrationSeverity.WARNING,
                component="configuration",
                message=f"Missing configuration files: {', '.join(missing_files)}",
                fix_suggestion="Create missing configuration files in settings/",
            )
            return False

        return True

    async def _validate_adapter_config(self, project_root: Path) -> bool:
        """Validate adapter configuration.

        Args:
            project_root: Project root directory

        Returns:
            True if adapter configuration is valid
        """
        adapters_yml = project_root / "settings" / "adapters.yaml"

        if not adapters_yml.exists():
            self._add_issue(
                severity=MigrationSeverity.WARNING,
                component="adapters",
                message="adapters.yaml not found",
                fix_suggestion="Create settings/adapters.yaml with adapter selections",
            )
            return False

        # Check if file is readable
        try:
            content = adapters_yml.read_text()
            if not content.strip():
                self._add_issue(
                    severity=MigrationSeverity.WARNING,
                    component="adapters",
                    message="adapters.yaml is empty",
                    fix_suggestion="Add adapter configurations to adapters.yaml",
                )
                return False
        except Exception as e:
            self._add_issue(
                severity=MigrationSeverity.ERROR,
                component="adapters",
                message=f"Failed to read adapters.yaml: {e}",
                fix_suggestion="Check file permissions and YAML syntax",
            )
            return False

        return True

    async def _validate_file_permissions(self, project_root: Path) -> bool:
        """Validate file permissions.

        Args:
            project_root: Project root directory

        Returns:
            True if file permissions are valid
        """
        settings_dir = project_root / "settings"

        if not settings_dir.exists():
            return False

        # Check if settings directory is readable
        if not settings_dir.is_dir():
            self._add_issue(
                severity=MigrationSeverity.ERROR,
                component="filesystem",
                message="settings/ is not a directory",
                fix_suggestion="Remove settings file and create settings/ directory",
            )
            return False

        # Check secrets directory if it exists
        secrets_dir = settings_dir / "secrets"
        if secrets_dir.exists():
            try:
                # Check if we can read the directory
                list(secrets_dir.iterdir())
            except PermissionError:
                self._add_issue(
                    severity=MigrationSeverity.ERROR,
                    component="filesystem",
                    message="Cannot access settings/secrets/ directory",
                    fix_suggestion="Check directory permissions",
                )
                return False

        return True

    async def _validate_dependencies(self, project_root: Path) -> bool:
        """Validate project dependencies.

        Args:
            project_root: Project root directory

        Returns:
            True if dependencies are valid
        """
        pyproject = project_root / "pyproject.toml"

        if not pyproject.exists():
            self._add_issue(
                severity=MigrationSeverity.WARNING,
                component="dependencies",
                message="pyproject.toml not found",
                fix_suggestion="Create pyproject.toml with project dependencies",
            )
            return False

        # Check if file is readable
        try:
            content = pyproject.read_text()
            if "acb" not in content:
                self._add_issue(
                    severity=MigrationSeverity.INFO,
                    component="dependencies",
                    message="ACB not found in pyproject.toml dependencies",
                    fix_suggestion="Add acb to project dependencies",
                )
        except Exception as e:
            self._add_issue(
                severity=MigrationSeverity.ERROR,
                component="dependencies",
                message=f"Failed to read pyproject.toml: {e}",
                fix_suggestion="Check file permissions and TOML syntax",
            )
            return False

        return True

    async def _validate_backup_integrity(self, backup_dir: Path) -> bool:
        """Validate backup integrity.

        Args:
            backup_dir: Backup directory

        Returns:
            True if backup is valid
        """
        if not backup_dir.exists():
            self._add_issue(
                severity=MigrationSeverity.WARNING,
                component="backup",
                message="Backup directory not found",
                fix_suggestion="Check backup configuration",
            )
            return False

        # Check if backup directory is readable
        try:
            backups = list(backup_dir.iterdir())
            if not backups:
                self._add_issue(
                    severity=MigrationSeverity.INFO,
                    component="backup",
                    message="No backups found in backup directory",
                    fix_suggestion="Backups will be created during migration",
                )
        except PermissionError:
            self._add_issue(
                severity=MigrationSeverity.ERROR,
                component="backup",
                message="Cannot access backup directory",
                fix_suggestion="Check directory permissions",
            )
            return False

        return True

    def _add_issue(
        self,
        severity: MigrationSeverity,
        component: str,
        message: str,
        fix_suggestion: str | None = None,
    ) -> None:
        """Add validation issue.

        Args:
            severity: Issue severity
            component: Component name
            message: Issue message
            fix_suggestion: Optional fix suggestion
        """
        issue = ValidationIssue(
            severity=severity,
            component=component,
            message=message,
            fix_suggestion=fix_suggestion,
        )
        self.issues.append(issue)
        logger.debug(f"Validation issue: {severity.value} - {component} - {message}")

    def has_critical_issues(self) -> bool:
        """Check if there are critical issues.

        Returns:
            True if critical issues exist
        """
        return any(
            issue.severity == MigrationSeverity.CRITICAL for issue in self.issues
        )
