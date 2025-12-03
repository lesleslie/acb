"""Rollback mechanisms for failed migrations."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from acb.depends import depends
from acb.logger import Logger as LoggerAdapter

logger = depends.get_sync(LoggerAdapter)


class RollbackPoint(BaseModel):
    """A rollback point for restoring previous state."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    version: str
    created_at: datetime = Field(default_factory=datetime.now)
    description: str
    backup_path: Path
    file_count: int = 0

    model_config = ConfigDict(arbitrary_types_allowed=True)


class RollbackManager:
    """Manages rollback points for failed migrations.

    Example:
        >>> manager = RollbackManager()
        >>> point = await manager.create_rollback_point(
        ...     version="0.19.1", description="Pre-migration backup"
        ... )
        >>> # If migration fails:
        >>> await manager.rollback(point.id)
    """

    def __init__(self, backup_dir: Path | None = None) -> None:
        """Initialize rollback manager.

        Args:
            backup_dir: Directory for storing backups
        """
        self.backup_dir = backup_dir or Path.cwd() / ".acb_backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self._rollback_points: dict[str, RollbackPoint] = {}

    async def create_rollback_point(
        self,
        version: str,
        description: str,
        files_to_backup: list[Path] | None = None,
    ) -> RollbackPoint:
        """Create a rollback point by backing up current state.

        Args:
            version: Current version
            description: Rollback point description
            files_to_backup: Specific files to backup (None = auto-detect)

        Returns:
            Created rollback point
        """
        # Generate rollback ID
        rollback_id = str(uuid.uuid4())
        backup_path = self.backup_dir / rollback_id
        backup_path.mkdir(parents=True, exist_ok=True)

        # Determine files to backup
        if files_to_backup is None:
            files_to_backup = await self._auto_detect_files()

        # Backup files
        file_count = 0
        for file_path in files_to_backup:
            if file_path.exists():
                relative_path = file_path.relative_to(Path.cwd())
                target_path = backup_path / relative_path
                target_path.parent.mkdir(parents=True, exist_ok=True)

                if file_path.is_file():
                    shutil.copy2(file_path, target_path)
                    file_count += 1
                elif file_path.is_dir():
                    shutil.copytree(
                        file_path,
                        target_path,
                        dirs_exist_ok=True,
                        symlinks=True,
                    )
                    # Count files in directory
                    file_count += sum(1 for _ in target_path.rglob("*") if _.is_file())

        # Create rollback point
        point = RollbackPoint(
            id=rollback_id,
            version=version,
            description=description,
            backup_path=backup_path,
            file_count=file_count,
        )

        self._rollback_points[rollback_id] = point
        logger.info(
            f"Created rollback point {rollback_id}: {file_count} files backed up",
        )

        return point

    async def rollback(self, rollback_id: str) -> None:
        """Rollback to a previous state.

        Args:
            rollback_id: ID of rollback point to restore

        Raises:
            ValueError: If rollback point not found
        """
        point = self._rollback_points.get(rollback_id)
        if not point:
            msg = f"Rollback point not found: {rollback_id}"
            raise ValueError(msg)

        logger.info(f"Rolling back to version {point.version}")

        # Restore files from backup
        if not point.backup_path.exists():
            msg = f"Backup path not found: {point.backup_path}"
            raise ValueError(msg)

        restored_count = 0
        for backup_file in point.backup_path.rglob("*"):
            if backup_file.is_file():
                relative_path = backup_file.relative_to(point.backup_path)
                target_path = Path.cwd() / relative_path
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup_file, target_path)
                restored_count += 1

        logger.info(f"Rollback complete: {restored_count} files restored")

    def list_rollback_points(self) -> list[RollbackPoint]:
        """List all available rollback points.

        Returns:
            List of rollback points sorted by creation time
        """
        return sorted(
            self._rollback_points.values(),
            key=lambda p: p.created_at,
            reverse=True,
        )

    async def cleanup_old_rollbacks(self, keep_count: int = 5) -> int:
        """Cleanup old rollback points, keeping only recent ones.

        Args:
            keep_count: Number of recent rollback points to keep

        Returns:
            Number of rollback points removed
        """
        points = self.list_rollback_points()

        if len(points) <= keep_count:
            return 0

        # Remove oldest rollback points
        removed_count = 0
        for point in points[keep_count:]:
            try:
                # Remove backup directory
                if point.backup_path.exists():
                    shutil.rmtree(point.backup_path)

                # Remove from registry
                del self._rollback_points[point.id]
                removed_count += 1
                logger.debug(f"Removed old rollback point: {point.id}")

            except Exception as e:
                logger.warning(f"Failed to remove rollback point {point.id}: {e}")

        logger.info(f"Cleaned up {removed_count} old rollback points")
        return removed_count

    async def _auto_detect_files(self) -> list[Path]:
        """Auto-detect important files to backup.

        Returns:
            List of files to backup
        """
        files_to_backup: list[Path] = []
        cwd = Path.cwd()

        # Configuration files
        config_patterns = [
            "settings/",
            "pyproject.toml",
            "uv.lock",
            ".env",
            "*.yaml",
            "*.yaml",
        ]

        for pattern in config_patterns:
            if "/" in pattern:
                # Directory
                path = cwd / pattern.rstrip("/")
                if path.exists() and path.is_dir():
                    files_to_backup.append(path)
            else:
                # File pattern
                files_to_backup.extend(cwd.glob(pattern))

        return files_to_backup
