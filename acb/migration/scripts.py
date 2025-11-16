"""Migration scripts for automated configuration and code updates."""

from __future__ import annotations

import shutil
from abc import ABC, abstractmethod

import anyio
from typing import TYPE_CHECKING

from acb.depends import depends
from acb.logger import Logger as LoggerAdapter

if TYPE_CHECKING:
    pass

logger = depends.get_sync(LoggerAdapter)

if TYPE_CHECKING:
    from pathlib import Path

    from acb.migration._base import MigrationConfig


class MigrationScript(ABC):
    """Base class for migration scripts."""

    def __init__(self, name: str, description: str) -> None:
        """Initialize migration script.

        Args:
            name: Script name
            description: Script description
        """
        self.name = name
        self.description = description
        self.files_modified = 0

    @abstractmethod
    async def execute(
        self,
        project_root: Path,
        config: MigrationConfig,
    ) -> None:
        """Execute the migration script.

        Args:
            project_root: Project root directory
            config: Migration configuration
        """
        ...

    async def _backup_file(self, file_path: Path, backup_dir: Path) -> None:
        """Backup a file before modification.

        Args:
            file_path: File to backup
            backup_dir: Backup directory
        """
        if file_path.exists():
            backup_path = backup_dir / file_path.name
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file_path, backup_path)
            logger.debug(f"Backed up: {file_path} -> {backup_path}")


class ConfigurationMigrationScript(MigrationScript):
    """Migrate configuration files to new structure."""

    def __init__(self) -> None:
        super().__init__(
            name="configuration_migration",
            description="Migrate configuration files to settings/ directory",
        )

    async def execute(
        self,
        project_root: Path,
        config: MigrationConfig,
    ) -> None:
        """Execute configuration migration."""
        settings_dir = project_root / "settings"
        settings_dir.mkdir(exist_ok=True)

        # Migrate old config files
        migrations = [
            ("config.yaml", settings_dir / "app.yaml"),
            ("debug.yaml", settings_dir / "debug.yaml"),
            (".env", settings_dir / "secrets" / ".env"),
        ]

        for old_file, new_path in migrations:
            old_path = project_root / old_file
            if old_path.exists():
                # Backup if enabled
                if config.backup_directory:
                    await self._backup_file(old_path, config.backup_directory)

                # Move file
                new_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(old_path), str(new_path))
                self.files_modified += 1
                logger.info(
                    f"Migrated: {old_file} -> {new_path.relative_to(project_root)}"
                )


class AdapterMigrationScript(MigrationScript):
    """Update adapter configurations and imports."""

    def __init__(self) -> None:
        super().__init__(
            name="adapter_migration",
            description="Update adapter configurations to new format",
        )

    async def execute(
        self,
        project_root: Path,
        config: MigrationConfig,
    ) -> None:
        """Execute adapter migration."""
        settings_dir = project_root / "settings"
        adapters_yml = settings_dir / "adapters.yaml"

        # Create default adapters.yaml if missing
        if not adapters_yml.exists():
            default_config = """# ACB Adapter Configuration
# Specify which adapter implementations to use

# Caching
cache: redis  # or: memory

# Storage
storage: s3  # or: file, gcs, azure

# Database
sql: postgresql  # or: mysql, sqlite

# Models
models: true  # Enable models adapter

# NoSQL
# nosql: mongodb  # or: firestore, redis

# Logging
logger: loguru  # or: structlog
"""
            adapters_yml.parent.mkdir(parents=True, exist_ok=True)
            await anyio.Path(adapters_yml).write_text(default_config)
            self.files_modified += 1
            logger.info(f"Created default adapter configuration: {adapters_yml}")


class DependencyUpdateScript(MigrationScript):
    """Update project dependencies."""

    def __init__(self) -> None:
        super().__init__(
            name="dependency_update",
            description="Update dependencies to compatible versions",
        )

    async def execute(
        self,
        project_root: Path,
        config: MigrationConfig,
    ) -> None:
        """Execute dependency update."""
        # Check for pyproject.toml
        pyproject = project_root / "pyproject.toml"
        if not pyproject.exists():
            logger.warning("No pyproject.toml found, skipping dependency update")
            return

        logger.info("Dependencies should be updated using: uv sync")
        # Note: Actual dependency updates should be done by package manager


class MajorVersionUpgradeScript(MigrationScript):
    """Handle major version upgrades with breaking changes."""

    def __init__(self) -> None:
        super().__init__(
            name="major_version_upgrade",
            description="Apply breaking changes for major version upgrade",
        )

    async def execute(
        self,
        project_root: Path,
        config: MigrationConfig,
    ) -> None:
        """Execute major version upgrade."""
        logger.warning(
            "Major version upgrade may require manual code changes. "
            "Please review CHANGELOG.md and MIGRATION guide.",
        )

        # Run both configuration and adapter migrations
        config_script = ConfigurationMigrationScript()
        await config_script.execute(project_root, config)
        self.files_modified += config_script.files_modified

        adapter_script = AdapterMigrationScript()
        await adapter_script.execute(project_root, config)
        self.files_modified += adapter_script.files_modified


# Script registry
_MIGRATION_SCRIPTS: dict[str, type[MigrationScript]] = {
    "configuration_migration": ConfigurationMigrationScript,
    "adapter_migration": AdapterMigrationScript,
    "dependency_update": DependencyUpdateScript,
    "major_version_upgrade": MajorVersionUpgradeScript,
}


def get_migration_script(
    name: str,
    source_version: str,
    target_version: str,
) -> MigrationScript | None:
    """Get migration script by name.

    Args:
        name: Script name
        source_version: Source version
        target_version: Target version

    Returns:
        Migration script instance or None if not found
    """
    script_class = _MIGRATION_SCRIPTS.get(name)
    if script_class:
        return script_class()  # type: ignore[call-arg]

    logger.warning(f"Migration script not found: {name}")
    return None


def register_migration_script(name: str, script_class: type[MigrationScript]) -> None:
    """Register a custom migration script.

    Args:
        name: Script name
        script_class: Script class
    """
    _MIGRATION_SCRIPTS[name] = script_class
    logger.debug(f"Registered migration script: {name}")
