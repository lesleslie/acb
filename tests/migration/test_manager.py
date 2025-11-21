from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from datetime import datetime

from acb.migration._base import MigrationSeverity, MigrationStatus, VersionInfo
from acb.migration.manager import MigrationManager, MigrationResult


def test_migration_result_properties() -> None:
    metrics_start = datetime.now()
    result = MigrationResult(
        status=MigrationStatus.COMPLETED,
        source_version=VersionInfo.from_string("0.1.0"),
        target_version=VersionInfo.from_string("0.2.0"),
        metrics=SimpleNamespace(start_time=metrics_start, end_time=metrics_start),  # type: ignore[arg-type]
    )

    assert result.success is True
    assert result.failed is False


def test_create_critical_issues_result() -> None:
    manager = MigrationManager()

    assessment = SimpleNamespace(
        current_version=VersionInfo.from_string("0.1.0"),
        target_version=VersionInfo.from_string("0.2.0"),
        issues=[
            SimpleNamespace(
                severity=MigrationSeverity.CRITICAL,
                message="breaking change in config schema",
            ),
            SimpleNamespace(
                severity=MigrationSeverity.WARNING,
                message="deprecated option detected",
            ),
        ],
    )

    metrics = SimpleNamespace(start_time=datetime.now())
    result = manager._create_critical_issues_result(
        assessment,
        target_version="0.2.0",
        metrics=metrics,  # type: ignore[arg-type]
    )

    assert result.status == MigrationStatus.FAILED
    # Only CRITICAL messages should be included
    assert result.errors == ["breaking change in config schema"]


@pytest.mark.asyncio
async def test_rollback_success_and_failure_paths() -> None:
    manager = MigrationManager()

    # Success path: rollback completes without raising
    with patch.object(
        manager.rollback_manager, "rollback", new=AsyncMock(return_value=None)
    ):
        ok = await manager.rollback("abc123")
        assert ok is True

    # Failure path: rollback raises
    async def _raise(*_a, **_kw):  # type: ignore[no-redef]
        raise RuntimeError("boom")

    with patch.object(
        manager.rollback_manager, "rollback", new=AsyncMock(side_effect=_raise)
    ):
        ok = await manager.rollback("abc123")
        assert ok is False


def test_version_info_parsing_and_ordering() -> None:
    v1 = VersionInfo.from_string("1.2.3")
    v2 = VersionInfo.from_string("1.2.4-alpha+build1")

    assert str(v1) == "1.2.3"
    assert str(v2) == "1.2.4-alpha+build1"
    # Pre-release is considered less than final of same triplet; here 1.2.3 < 1.2.4-alpha
    assert (v1 < v2) is True
