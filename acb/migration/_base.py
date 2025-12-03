"""Base classes and types for migration system."""

from __future__ import annotations

from enum import Enum

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class MigrationStatus(str, Enum):
    """Migration status enumeration."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class MigrationSeverity(str, Enum):
    """Migration severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class CompatibilityStatus(str, Enum):
    """Compatibility status for version pairs."""

    COMPATIBLE = "compatible"
    COMPATIBLE_WITH_WARNINGS = "compatible_with_warnings"
    MIGRATION_REQUIRED = "migration_required"
    INCOMPATIBLE = "incompatible"


class MigrationIssue(BaseModel):
    """Migration issue or warning."""

    severity: MigrationSeverity
    message: str
    component: str | None = None
    fix_available: bool = False
    fix_description: str | None = None

    model_config = ConfigDict(frozen=True)


class MigrationStep(BaseModel):
    """Individual migration step."""

    name: str
    description: str
    required: bool = True
    reversible: bool = True
    estimated_duration: int = Field(default=0, description="Seconds")
    dependencies: list[str] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class VersionInfo(BaseModel):
    """Version information."""

    major: int
    minor: int
    patch: int
    pre_release: str | None = None
    build: str | None = None

    model_config = ConfigDict(frozen=True)

    @classmethod
    def from_string(cls, version: str) -> VersionInfo:
        """Parse version string into VersionInfo."""
        # Remove 'v' prefix if present
        version = version.lstrip("v")

        # Split on pre-release markers
        parts = version.split("-")
        core_version = parts[0]
        pre_release = parts[1] if len(parts) > 1 else None

        # Split on build marker
        build: str | None
        if pre_release and "+" in pre_release:
            pre_release, build = pre_release.split("+", 1)
        else:
            build = None

        # Parse core version
        major, minor, patch = map(int, core_version.split("."))

        return cls.model_validate(
            {
                "major": major,
                "minor": minor,
                "patch": patch,
                "pre_release": pre_release,
                "build": build,
            },
        )

    def __str__(self) -> str:
        """String representation."""
        version = f"{self.major}.{self.minor}.{self.patch}"
        if self.pre_release:
            version += f"-{self.pre_release}"
        if self.build:
            version += f"+{self.build}"
        return version

    def __lt__(self, other: VersionInfo) -> bool:
        """Compare versions."""
        if self.major != other.major:
            return self.major < other.major
        if self.minor != other.minor:
            return self.minor < other.minor
        if self.patch != other.patch:
            return self.patch < other.patch

        # Pre-release versions are less than release versions
        if self.pre_release and not other.pre_release:
            return True
        if not self.pre_release and other.pre_release:
            return False

        return False

    def __le__(self, other: object) -> bool:
        """Less than or equal comparison."""
        if not isinstance(other, VersionInfo):
            return NotImplemented
        return self < other or self == other  # type: ignore[comparison-overlap]

    def __gt__(self, other: VersionInfo) -> bool:
        """Greater than comparison."""
        return not self <= other

    def __ge__(self, other: VersionInfo) -> bool:
        """Greater than or equal comparison."""
        return not self < other


class MigrationConfig(BaseModel):
    """Migration configuration."""

    source_version: VersionInfo
    target_version: VersionInfo
    backup_enabled: bool = True
    backup_directory: Path | None = None
    auto_rollback_on_error: bool = True
    dry_run: bool = False
    force: bool = False
    skip_validation: bool = False

    model_config = ConfigDict(arbitrary_types_allowed=True)


class MigrationMetrics(BaseModel):
    """Migration performance metrics."""

    start_time: datetime
    end_time: datetime | None = None
    duration_seconds: float = 0.0
    steps_completed: int = 0
    steps_failed: int = 0
    steps_skipped: int = 0
    files_modified: int = 0
    files_backed_up: int = 0

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def is_complete(self) -> bool:
        """Check if migration is complete."""
        return self.end_time is not None

    def complete(self) -> None:
        """Mark migration as complete."""
        if self.end_time is None:
            self.end_time = datetime.now()
            self.duration_seconds = (self.end_time - self.start_time).total_seconds()
