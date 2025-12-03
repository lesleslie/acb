"""Migration manager for orchestrating migrations."""

from __future__ import annotations

from pathlib import Path

import typing as t
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from acb.depends import depends
from acb.logger import Logger as LoggerAdapter
from acb.migration._base import (
    MigrationConfig,
    MigrationMetrics,
    MigrationStatus,
    MigrationStep,
    VersionInfo,
)
from acb.migration.assessment import assess_migration
from acb.migration.rollback import RollbackManager, RollbackPoint
from acb.migration.scripts import get_migration_script
from acb.migration.validator import MigrationValidator

logger = depends.get_sync(LoggerAdapter)


class MigrationResult(BaseModel):
    """Result of a migration operation."""

    status: MigrationStatus
    source_version: VersionInfo
    target_version: VersionInfo
    metrics: MigrationMetrics
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    rollback_point: RollbackPoint | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def success(self) -> bool:
        """Check if migration was successful."""
        return self.status == MigrationStatus.COMPLETED

    @property
    def failed(self) -> bool:
        """Check if migration failed."""
        return self.status == MigrationStatus.FAILED


class MigrationManager:
    """Manages ACB migrations and upgrades.

    Example:
        >>> manager = MigrationManager()
        >>> result = await manager.migrate(target_version="0.20.0")
        >>> if result.success:
        ...     print(f"Migration completed in {result.metrics.duration_seconds}s")
        ... else:
        ...     print(f"Migration failed: {result.errors}")
    """

    def __init__(
        self,
        project_root: Path | None = None,
        backup_dir: Path | None = None,
    ) -> None:
        """Initialize migration manager.

        Args:
            project_root: Project root directory (auto-detected if None)
            backup_dir: Backup directory (auto-created if None)
        """
        self.project_root = project_root or Path.cwd()
        self.backup_dir = backup_dir or self.project_root / ".acb_backups"
        self.rollback_manager = RollbackManager(self.backup_dir)
        self.validator = MigrationValidator()

    async def migrate(
        self,
        target_version: str,
        dry_run: bool = False,
        force: bool = False,
        auto_rollback: bool = True,
    ) -> MigrationResult:
        """Migrate ACB installation to target version.

        Args:
            target_version: Version to migrate to (e.g., "0.20.0")
            dry_run: If True, simulate migration without changes
            force: If True, skip compatibility checks
            auto_rollback: If True, rollback on error

        Returns:
            Migration result with status and metrics
        """
        logger.info(f"Starting migration to version {target_version}")

        # Create metrics
        metrics = MigrationMetrics(start_time=datetime.now())

        try:
            # Assess migration
            assessment = await assess_migration(
                target_version=target_version,
                config_dir=self.project_root,
            )

            # Check for critical issues
            if assessment.has_critical_issues and not force:
                return self._create_critical_issues_result(
                    assessment,
                    target_version,
                    metrics,
                )

            # Create configuration
            config = self._create_migration_config(
                assessment,
                target_version,
                dry_run,
                auto_rollback,
            )

            # Create rollback point
            rollback_point = await self._create_rollback_point_if_enabled(
                config,
                target_version,
            )

            # Execute migration steps
            step_result = await self._execute_migration_steps(
                assessment.required_steps,
                config,
                metrics,
                rollback_point,
                auto_rollback,
            )

            if step_result:  # Early return on rollback
                return step_result

            # Complete metrics and return final result
            metrics.complete()
            return self._create_final_result(
                config,
                metrics,
                rollback_point,
            )

        except Exception as e:
            logger.exception("Migration failed with unexpected error")
            metrics.complete()
            return MigrationResult(
                status=MigrationStatus.FAILED,
                source_version=VersionInfo.from_string("0.0.0"),
                target_version=VersionInfo.from_string(target_version),
                metrics=metrics,
                errors=[str(e)],
            )

    def _create_critical_issues_result(
        self,
        assessment: t.Any,
        target_version: str,
        metrics: MigrationMetrics,
    ) -> MigrationResult:
        """Create result for critical issues detected.

        Args:
            assessment: Migration assessment
            target_version: Target version string
            metrics: Migration metrics

        Returns:
            MigrationResult indicating failure due to critical issues
        """
        logger.error("Critical issues detected, migration aborted")
        return MigrationResult(
            status=MigrationStatus.FAILED,
            source_version=assessment.current_version,
            target_version=assessment.target_version
            or VersionInfo.from_string(target_version),
            metrics=metrics,
            errors=[
                issue.message
                for issue in assessment.issues
                if issue.severity.value == "critical"
            ],
        )

    def _create_migration_config(
        self,
        assessment: t.Any,
        target_version: str,
        dry_run: bool,
        auto_rollback: bool,
    ) -> MigrationConfig:
        """Create migration configuration.

        Args:
            assessment: Migration assessment
            target_version: Target version string
            dry_run: Whether this is a dry run
            auto_rollback: Whether to auto-rollback on error

        Returns:
            MigrationConfig instance
        """
        return MigrationConfig(
            source_version=assessment.current_version,
            target_version=assessment.target_version
            or VersionInfo.from_string(target_version),
            backup_enabled=not dry_run,
            backup_directory=self.backup_dir,
            auto_rollback_on_error=auto_rollback,
            dry_run=dry_run,
            force=False,
        )

    async def _create_rollback_point_if_enabled(
        self,
        config: MigrationConfig,
        target_version: str,
    ) -> RollbackPoint | None:
        """Create rollback point if backups are enabled.

        Args:
            config: Migration configuration
            target_version: Target version string

        Returns:
            RollbackPoint if created, None otherwise
        """
        if not config.backup_enabled:
            return None

        rollback_point = await self.rollback_manager.create_rollback_point(
            version=str(config.source_version),
            description=f"Pre-migration backup before upgrading to {target_version}",
        )
        logger.info(f"Created rollback point: {rollback_point.id}")
        return rollback_point

    async def _execute_migration_steps(
        self,
        steps: list[MigrationStep],
        config: MigrationConfig,
        metrics: MigrationMetrics,
        rollback_point: RollbackPoint | None,
        auto_rollback: bool,
    ) -> MigrationResult | None:
        """Execute all migration steps.

        Args:
            steps: List of migration steps
            config: Migration configuration
            metrics: Migration metrics
            rollback_point: Optional rollback point
            auto_rollback: Whether to auto-rollback on error

        Returns:
            MigrationResult if rollback occurred, None otherwise
        """
        errors: list[str] = []

        for step in steps:
            logger.info(f"Executing step: {step.name}")

            try:
                await self._execute_step(step, config, metrics)
                metrics.steps_completed += 1
            except Exception as e:
                logger.exception(f"Step failed: {step.name} - {e}")
                errors.append(f"{step.name}: {e}")
                metrics.steps_failed += 1

                if auto_rollback and rollback_point:
                    return await self._perform_rollback(
                        config,
                        metrics,
                        errors,
                        rollback_point,
                    )
                break

        return None

    async def _perform_rollback(
        self,
        config: MigrationConfig,
        metrics: MigrationMetrics,
        errors: list[str],
        rollback_point: RollbackPoint,
    ) -> MigrationResult:
        """Perform rollback on migration failure.

        Args:
            config: Migration configuration
            metrics: Migration metrics
            errors: List of error messages
            rollback_point: Rollback point to restore

        Returns:
            MigrationResult indicating rollback
        """
        logger.warning("Auto-rollback triggered")
        await self.rollback_manager.rollback(rollback_point.id)
        return MigrationResult(
            status=MigrationStatus.ROLLED_BACK,
            source_version=config.source_version,
            target_version=config.target_version,
            metrics=metrics,
            errors=errors,
            rollback_point=rollback_point,
        )

    def _create_final_result(
        self,
        config: MigrationConfig,
        metrics: MigrationMetrics,
        rollback_point: RollbackPoint | None,
    ) -> MigrationResult:
        """Create final migration result.

        Args:
            config: Migration configuration
            metrics: Migration metrics
            rollback_point: Optional rollback point

        Returns:
            Final MigrationResult
        """
        status = MigrationStatus.COMPLETED
        logger.info(
            f"Migration completed successfully in {metrics.duration_seconds:.2f}s",
        )

        return MigrationResult(
            status=status,
            source_version=config.source_version,
            target_version=config.target_version,
            metrics=metrics,
            errors=[],
            warnings=[],
            rollback_point=rollback_point,
        )

    async def _execute_step(
        self,
        step: MigrationStep,
        config: MigrationConfig,
        metrics: MigrationMetrics,
    ) -> None:
        """Execute a single migration step.

        Args:
            step: Migration step to execute
            config: Migration configuration
            metrics: Metrics to update
        """
        if config.dry_run:
            logger.info(f"[DRY RUN] Would execute: {step.name}")
            return

        # Get migration script for this step
        script = get_migration_script(
            step.name,
            source_version=str(config.source_version),
            target_version=str(config.target_version),
        )

        if script:
            # Execute the migration script
            await script.execute(
                project_root=self.project_root,
                config=config,
            )

            # Update metrics based on script results
            if hasattr(script, "files_modified"):
                metrics.files_modified += script.files_modified

    async def rollback(self, rollback_id: str) -> bool:
        """Rollback to a previous state.

        Args:
            rollback_id: ID of rollback point to restore

        Returns:
            True if rollback successful, False otherwise
        """
        try:
            await self.rollback_manager.rollback(rollback_id)
            logger.info(f"Rollback successful: {rollback_id}")
            return True
        except Exception as e:
            logger.exception(f"Rollback failed: {e}")
            return False

    def list_rollback_points(self) -> list[RollbackPoint]:
        """List available rollback points.

        Returns:
            List of available rollback points
        """
        return self.rollback_manager.list_rollback_points()
