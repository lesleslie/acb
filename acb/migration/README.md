> **ACB Documentation**: [Main](../../README.md) | [Core Systems](../README.md) | [Migration](./README.md) | [Adapters](../adapters/README.md) | [Events](../events/README.md)

# ACB: Migration

The migration layer helps teams move between ACB releases safely. It inspects
installed versions, plans upgrade steps, applies scripted changes, and enforces
compatibility guards so that breaking updates can be rolled out (or rolled back)
with confidence.

## Table of Contents

- [Overview](#overview)
- [Migration Capabilities](#migration-capabilities)
- [Assessment & Planning](#assessment--planning)
- [Running Migrations](#running-migrations)
- [Compatibility & Rollback](#compatibility--rollback)
- [Validation & Reporting](#validation--reporting)
- [Usage Example](#usage-example)
- [Best Practices](#best-practices)
- [Related Resources](#related-resources)

## Overview

The layer orchestrates version detection, configuration refactors, dependency
updates, and adapter rewrites while keeping a detailed audit trail. Pydantic
models (`MigrationAssessment`, `MigrationResult`, `MigrationMetrics`) encode
status so migration dashboards, CI jobs, or CLI tools can surface progress and
warnings in real time.

## Migration Capabilities

- `MigrationStatus`, `MigrationSeverity`, and `MigrationIssue` classify outcomes
  and annotate blockers with remediation hints.
- `MigrationStep` structures the ordered plan (dependencies, reversibility,
  time estimates) that both humans and automation can follow.
- `VersionInfo` compares SemVer data, with helpers to parse package metadata,
  `pyproject.toml`, and module-level `__version__` exports.
- Script harness (`MigrationScript` plus concrete implementations) handles file
  backups, adapter config generation, and dependency refreshes.

## Assessment & Planning

- `detect_version()` resolves the current ACB build by consulting the installed
  package, the project tree, or fallback metadata.
- `assess_migration()` evaluates compatibility, assembling `MigrationAssessment`
  that lists deprecated configs, required scripts, and estimated durations.
- Helper probes check Python runtime support, configuration layout, and adapter
  readiness so you can fix prerequisites before starting a migration window.

## Running Migrations

`MigrationManager` provides the high-level orchestration API:

- Builds a `MigrationConfig` from assessments and caller flags (dry run, force,
  auto rollback, backup directories).
- Coordinates scripts via `get_migration_script()` and captures metrics through
  `MigrationMetrics.complete()`.
- Streams activity into `acb.logger` so the existing logging pipeline records
  step-by-step progress.

```python
from acb.migration import MigrationManager

manager = MigrationManager()
result = await manager.migrate(target_version="0.20.0", dry_run=False)

if result.success:
    print(f"Migrated to {result.target_version} in {result.metrics.duration_seconds}s")
else:
    print("Migration failed:", result.errors)
```

## Compatibility & Rollback

- `CompatibilityLayer` and `get_compatibility_layer()` expose shims for
  deprecated APIs so mixed-version deployments can coexist during a rollout.
- `RollbackManager` snapshots files into `.acb_backups/` and can restore named
  `RollbackPoint`s when errors occur or when `auto_rollback_on_error` is set.
- Rollback metadata annotates `MigrationResult` so post-mortems know what was
  restored and why.

## Validation & Reporting

- `MigrationValidator` enforces post-migration checks (schema alignment,
  adapter status, configuration correctness) before finalizing a run.
- `ValidationResult` captures pass/fail state alongside remedial actions.
- Metrics such as files modified, steps completed, and retries feed dashboards
  or notifications for stakeholders monitoring the rollout.

## Usage Example

Running a pre-flight assessment without making changes:

```python
from acb.migration import assess_migration

assessment = await assess_migration(target_version="0.20.0")
if assessment.requires_migration:
    for issue in assessment.issues:
        print(f"[{issue.severity.value}] {issue.message}")
```

## Best Practices

- Always run in `dry_run` mode first and review the planned `MigrationStep`s,
  especially before major-version upgrades.
- Keep backups enabled; even reversible steps benefit from quick restoration
  during rehearsals or production incidents.
- Address `MigrationSeverity.CRITICAL` issues before forcing a migration—doing
  so avoids unsupported Python versions or missing adapter configs.
- Extend the script registry with custom subclasses when your project needs
  bespoke file transformations; the manager will pick them up automatically.
- Capture results in CI artifacts or deployment logs so teams can audit
  migrations against release notes.

## Related Resources

- [Adapters](../adapters/README.md)
- [Events](../events/README.md)
- [Services](../services/README.md)
- [Main Documentation](../../README.md)
