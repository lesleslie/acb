"""Migration assessment and version detection."""

from __future__ import annotations

import importlib.metadata
import sys
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from acb.migration._base import (
    CompatibilityStatus,
    MigrationIssue,
    MigrationSeverity,
    MigrationStep,
    VersionInfo,
)


class MigrationAssessment(BaseModel):
    """Assessment of migration requirements."""

    current_version: VersionInfo
    target_version: VersionInfo | None = None
    compatibility_status: CompatibilityStatus
    issues: list[MigrationIssue] = Field(default_factory=list)
    required_steps: list[MigrationStep] = Field(default_factory=list)
    estimated_duration: int = Field(default=0, description="Total seconds")
    breaking_changes: list[str] = Field(default_factory=list)
    deprecated_features: list[str] = Field(default_factory=list)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def has_critical_issues(self) -> bool:
        """Check if assessment has critical issues."""
        return any(issue.severity == MigrationSeverity.CRITICAL for issue in self.issues)

    @property
    def requires_migration(self) -> bool:
        """Check if migration is required."""
        return self.compatibility_status in (
            CompatibilityStatus.MIGRATION_REQUIRED,
            CompatibilityStatus.INCOMPATIBLE,
        )


def detect_version() -> VersionInfo:
    """Detect currently installed ACB version.

    Returns:
        Current ACB version information

    Raises:
        RuntimeError: If version cannot be detected
    """
    try:
        # Try to get version from installed package
        version_str = importlib.metadata.version("acb")
        return VersionInfo.from_string(version_str)
    except importlib.metadata.PackageNotFoundError:
        # Fallback to checking __version__ in acb module
        try:
            import acb

            if hasattr(acb, "__version__"):
                return VersionInfo.from_string(acb.__version__)
        except ImportError:
            pass

        # Last resort: check pyproject.toml
        try:
            import tomllib

            pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
            if pyproject_path.exists():
                with open(pyproject_path, "rb") as f:
                    data = tomllib.load(f)
                    version_str = data["project"]["version"]
                    return VersionInfo.from_string(version_str)
        except Exception:
            pass

        msg = "Could not detect ACB version"
        raise RuntimeError(msg)


def _get_python_version_issues() -> list[MigrationIssue]:
    """Check Python version compatibility."""
    issues = []
    current_python = sys.version_info

    if current_python < (3, 13):
        issues.append(
            MigrationIssue(
                severity=MigrationSeverity.CRITICAL,
                message=f"Python {current_python.major}.{current_python.minor} is not supported. ACB requires Python 3.13+",
                component="python",
                fix_available=True,
                fix_description="Upgrade to Python 3.13 or later",
            ),
        )

    return issues


def _check_deprecated_config(config_dir: Path) -> list[MigrationIssue]:
    """Check for deprecated configuration files."""
    issues = []

    # Check for old config file locations
    old_configs = [
        ("config.yaml", "settings/app.yml"),
        ("debug.yaml", "settings/debug.yml"),
        (".env", "settings/secrets/.env"),
    ]

    for old_file, new_file in old_configs:
        old_path = config_dir / old_file
        if old_path.exists():
            issues.append(
                MigrationIssue(
                    severity=MigrationSeverity.WARNING,
                    message=f"Deprecated config file: {old_file}",
                    component="configuration",
                    fix_available=True,
                    fix_description=f"Move to {new_file}",
                ),
            )

    return issues


def _check_adapter_config(settings_dir: Path) -> list[MigrationIssue]:
    """Check adapter configuration for deprecated patterns."""
    issues = []

    adapters_yml = settings_dir / "adapters.yml"
    if not adapters_yml.exists():
        issues.append(
            MigrationIssue(
                severity=MigrationSeverity.WARNING,
                message="Missing settings/adapters.yml configuration",
                component="adapters",
                fix_available=True,
                fix_description="Create adapters.yml with adapter selections",
            ),
        )

    return issues


def _get_migration_steps(
    current: VersionInfo, target: VersionInfo,
) -> list[MigrationStep]:
    """Generate migration steps based on version gap."""
    steps = []

    # Major version migration
    if target.major > current.major:
        steps.append(
            MigrationStep(
                name="major_version_upgrade",
                description=f"Upgrade from v{current.major}.x to v{target.major}.x",
                required=True,
                reversible=False,
                estimated_duration=300,
            ),
        )

    # Minor version migrations (breaking changes)
    if target.minor > current.minor or target.major > current.major:
        steps.append(
            MigrationStep(
                name="configuration_migration",
                description="Migrate configuration files to new structure",
                required=True,
                reversible=True,
                estimated_duration=60,
            ),
        )

        steps.append(
            MigrationStep(
                name="adapter_migration",
                description="Update adapter configurations and imports",
                required=True,
                reversible=True,
                estimated_duration=120,
            ),
        )

    # Patch version (usually safe)
    if (
        target.patch > current.patch
        and target.minor == current.minor
        and target.major == current.major
    ):
        steps.append(
            MigrationStep(
                name="dependency_update",
                description="Update dependencies",
                required=True,
                reversible=True,
                estimated_duration=30,
            ),
        )

    return steps


async def assess_migration(
    target_version: str | None = None, config_dir: Path | None = None,
) -> MigrationAssessment:
    """Assess migration requirements for ACB installation.

    Args:
        target_version: Target version to migrate to (None = latest)
        config_dir: Configuration directory path (None = auto-detect)

    Returns:
        Migration assessment with issues and required steps

    Example:
        >>> assessment = await assess_migration(target_version="0.20.0")
        >>> if assessment.has_critical_issues:
        ...     print("Critical issues found!")
        >>> for issue in assessment.issues:
        ...     print(f"{issue.severity}: {issue.message}")
    """
    # Detect current version
    current = detect_version()

    # Parse target version
    target = VersionInfo.from_string(target_version) if target_version else None

    # Determine compatibility status
    if target is None:
        compatibility_status = CompatibilityStatus.COMPATIBLE
    elif target < current:
        compatibility_status = CompatibilityStatus.INCOMPATIBLE
    elif target == current:
        compatibility_status = CompatibilityStatus.COMPATIBLE
    elif target.major > current.major or target.minor > current.minor:
        compatibility_status = CompatibilityStatus.MIGRATION_REQUIRED
    else:
        compatibility_status = CompatibilityStatus.COMPATIBLE_WITH_WARNINGS

    # Collect issues
    issues: list[MigrationIssue] = []

    # Check Python version
    issues.extend(_get_python_version_issues())

    # Check configuration if directory provided
    if config_dir:
        settings_dir = config_dir / "settings"
        if settings_dir.exists():
            issues.extend(_check_deprecated_config(config_dir))
            issues.extend(_check_adapter_config(settings_dir))

    # Generate migration steps
    required_steps = []
    if target and target > current:
        required_steps = _get_migration_steps(current, target)

    # Calculate estimated duration
    estimated_duration = sum(step.estimated_duration for step in required_steps)

    # Identify breaking changes and deprecations
    breaking_changes = []
    deprecated_features = []

    if target and target.major > current.major:
        breaking_changes.append(
            "Major version upgrade may include breaking API changes",
        )

    if target and target.minor > current.minor:
        deprecated_features.append(
            "Some features may be deprecated in this version",
        )

    return MigrationAssessment(
        current_version=current,
        target_version=target,
        compatibility_status=compatibility_status,
        issues=issues,
        required_steps=required_steps,
        estimated_duration=estimated_duration,
        breaking_changes=breaking_changes,
        deprecated_features=deprecated_features,
    )
