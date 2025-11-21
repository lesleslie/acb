from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from datetime import datetime

from acb.migration._base import (
    MigrationConfig,
    MigrationMetrics,
    MigrationStatus,
    MigrationStep,
    VersionInfo,
)
from acb.migration.manager import MigrationManager


@pytest.mark.asyncio
async def test_create_rollback_point_disabled() -> None:
    manager = MigrationManager()
    cfg = MigrationConfig(
        source_version=VersionInfo.from_string("0.1.0"),
        target_version=VersionInfo.from_string("0.2.0"),
        backup_enabled=False,  # disabled
    )

    rb = await manager._create_rollback_point_if_enabled(cfg, "0.2.0")
    assert rb is None


@pytest.mark.asyncio
async def test_execute_migration_steps_triggers_rollback_on_error() -> None:
    manager = MigrationManager()

    steps = [MigrationStep(name="step1", description="d")]
    cfg = MigrationConfig(
        source_version=VersionInfo.from_string("0.1.0"),
        target_version=VersionInfo.from_string("0.2.0"),
    )
    metrics = MigrationMetrics(start_time=datetime.now())
    rollback_point = SimpleNamespace(id="rb1")

    # Force _execute_step to raise to simulate failure
    with patch.object(
        manager, "_execute_step", new=AsyncMock(side_effect=RuntimeError("boom"))
    ):
        with patch.object(
            manager.rollback_manager, "rollback", new=AsyncMock(return_value=None)
        ):
            result = await manager._execute_migration_steps(
                steps=steps,
                config=cfg,
                metrics=metrics,
                rollback_point=rollback_point,
                auto_rollback=True,
            )

    assert result is not None
    assert result.status == MigrationStatus.ROLLED_BACK
    assert metrics.steps_failed == 1
