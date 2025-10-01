---
id: 01K6GSRAY0JSAFZF69GMQ02F0S
---
______________________________________________________________________

## id: 01K6GSM5R654BFP3R65XCP93XR

______________________________________________________________________

## id: 01K6GPA3ZDG2DMZPYFSW80JS0T

______________________________________________________________________

## id: 01K6GMDQFZEXRYZWXFAPED9R1N

______________________________________________________________________

## id: 01K6GKSVH75NY3KMZP1TWMWB3Z

______________________________________________________________________

## id: 01K6GKJJW33SN6AZTEBZ7VZNTV

______________________________________________________________________

## id: 01K6GJYFAE3VCPMT7JC3BQD09V

______________________________________________________________________

## id: 01K6GGMAA7BGD3B1BYF3R7EMVJ

______________________________________________________________________

## id: 01K6G685WTZ5X3TZYYB7S6Q0NS

______________________________________________________________________

## id: 01K6G5HV27Z35X0NR19Z7PD090

______________________________________________________________________

## id: 01K6G58K44C5S73VZ9Y5V6X5BK

______________________________________________________________________

## id: 01K6G4MK0BB6ETY05QFA6KYNT5

______________________________________________________________________

## id: 01K6G3R81TWVBSQ1M98RMGBB0W

______________________________________________________________________

## id: 01K6G39A6BZ3T12R7NZP133QP8

______________________________________________________________________

## id: 01K6FZP6K2SZTCR44W8T53BGSS

______________________________________________________________________

## id: 01K6FY3TDE3PYQRSACYHW5KX31

______________________________________________________________________

## id: 01K6FVE99PW0218R9FVXV1729B

______________________________________________________________________

## id: 01K6FSHD8YC89A9WMQ8T8D7M2Q

______________________________________________________________________

## id: 01K6FSGCE0JGT4TYD3Z30DQ1ZE

______________________________________________________________________

## id: 01K6FSAWMBYRGD70G5AGPY6PQB

______________________________________________________________________

## id: 01K6FRWJ1HF93P7A8RPN80CD8J

______________________________________________________________________

## id: 01K6FRSTGK173T9500F3HRBEX9

______________________________________________________________________

## id: 01K6FRKYVYQ4QEDQN39H9HT7QK

______________________________________________________________________

## id: 01K6FRJ8F5BBVKGER0ZT26CEJC

______________________________________________________________________

## id: 01K6FRE0WBN5NNHPSW9VWCX7DJ

______________________________________________________________________

## id: 01K6FQW06JPQTW60TF2K55JC0Y

______________________________________________________________________

## id: 01K6FQP09QZ14ZZBDZ7QR4SJSQ

______________________________________________________________________

## id: 01K6FQ9GBTHPNFHDMQ78WHB39J

______________________________________________________________________

## id: 01K6FQ0ASTJWE50RSK0VQ2GS5E

______________________________________________________________________

## id: 01K6FPYEEGS92HZ5XBNJD17KNB

______________________________________________________________________

## id: 01K6FPVZVEE8NTWM3C6GPDKEN8

______________________________________________________________________

## id: 01K6FP92WRTWCT2E0JGSHES5X7

______________________________________________________________________

## id: 01K6FP21PJA8D2C9Y1DRCJCMHZ

______________________________________________________________________

## id: 01K6FP09T3XR7HTK2ZA8WWKPG4

______________________________________________________________________

## id: 01K6FNY98K878QN1HP73TZPAM6

______________________________________________________________________

## id: 01K6FND819A94R8ZX419YDH6RH

______________________________________________________________________

## id: 01K6FN9FEEN74CJKT4K064GD52

______________________________________________________________________

## id: 01K6FM909REDJ70XCPH5KSPEBV

______________________________________________________________________

## id: 01K6FM4KQ977D49E6XKZBVEF3E

______________________________________________________________________

## id: 01K6FM380Z3FBRF664W8K7GQQ6

______________________________________________________________________

## id: 01K6FKZ04PTQA8GRVB0MGBAM5X

______________________________________________________________________

## id: 01K6FKXMYRPK3FTSHBP22K5ARS

______________________________________________________________________

## id: 01K6FD9EGEQW5GHRM93YQJCTDD

______________________________________________________________________

## id: 01K6FCP5PRAG0WF96YZY9D6CVK

______________________________________________________________________

## id: 01K6FBZ830M27DTMNHFW2CCC1Q

______________________________________________________________________

## id: 01K6FBRNC0T18DY900Y4V4A07H

______________________________________________________________________

## id: 01K6FBJEY1GN68NC2N4GZR4G2Y

______________________________________________________________________

## id: 01K6FB8H016MT3SS5PR0E2EAPJ

______________________________________________________________________

## id: 01K6F9NW8JZ62XCQ1T5Q16FN75

______________________________________________________________________

## id: 01K6F9JVRZZ1QZBH0QY4TAQ9K8

______________________________________________________________________

## id: 01K6F9HW9QM6J3D78PQXH7FPK6

______________________________________________________________________

## id: 01K6F9FDGWSK52NGWZ9NG5SGAN

______________________________________________________________________

## id: 01K6F9EFKDF0Z48M6QM4BWAP4S

______________________________________________________________________

## id: 01K6F8HFDYNE081QXQA05NGG1W

______________________________________________________________________

## id: 01K6F85RFFN5WNSK9252286XMX

______________________________________________________________________

## id: 01K6F6ZG4QAV0Y73C3BF4ZX7MA

______________________________________________________________________

## id: 01K6F6Y55XRDKEP6AM8QA9RAYF

______________________________________________________________________

## id: 01K6F0QEGCGXA9P9ZVWA2XZ8KT

______________________________________________________________________

## id: 01K6F05ZDZ5WE4WZYHWTWFA5KJ

______________________________________________________________________

## id: 01K6EZZRC0NDS4BD1467N0W5ZZ

______________________________________________________________________

## id: 01K6EZZ3VRQYV5EDYPHJ9ZEBR1

______________________________________________________________________

## id: 01K6EZMW3WYZ4D46VFSQ485PFB

______________________________________________________________________

## id: 01K6EZM28F757HWX0J00585ADK

______________________________________________________________________

## id: 01K6EZ6RCS8Q24DM6T0ED1R5B2

______________________________________________________________________

## id: 01K6EZ641D7CF7ACWEEMS0DQET

______________________________________________________________________

## id: 01K6EYSRJNKKY6PENSWQPM4FB4

# ACB Migration Guide

This guide provides comprehensive instructions for migrating ACB installations between versions.

## Overview

ACB's migration system provides automated tools for:

- **Version Detection**: Automatically detect current ACB version
- **Migration Assessment**: Analyze migration requirements and compatibility
- **Automated Migrations**: Run configuration and code migration scripts
- **Rollback Safety**: Create backups and rollback on failure
- **Validation**: Verify migration completed successfully

## Quick Start

### Basic Migration

```python
from acb.migration import MigrationManager

# Create migration manager
manager = MigrationManager()

# Migrate to specific version
result = await manager.migrate(target_version="0.20.0")

if result.success:
    print(f"Migration completed in {result.metrics.duration_seconds}s")
    print(f"Files modified: {result.metrics.files_modified}")
else:
    print(f"Migration failed: {result.errors}")
```

### Dry Run (Simulation)

```python
# Test migration without making changes
result = await manager.migrate(
    target_version="0.20.0",
    dry_run=True,  # Simulate without actual changes
)

print(f"Would modify {len(result.metrics.files_modified)} files")
```

### With Manual Rollback Control

```python
# Disable auto-rollback for manual control
result = await manager.migrate(target_version="0.20.0", auto_rollback=False)

if result.failed:
    # Manually review and rollback if needed
    rollback_points = manager.list_rollback_points()
    if rollback_points:
        await manager.rollback(rollback_points[0].id)
```

## Migration Assessment

Before migrating, assess requirements and compatibility:

```python
from acb.migration import assess_migration

# Assess migration to specific version
assessment = await assess_migration(target_version="0.20.0", config_dir=Path.cwd())

print(f"Current version: {assessment.current_version}")
print(f"Target version: {assessment.target_version}")
print(f"Compatibility: {assessment.compatibility_status}")
print(f"Estimated duration: {assessment.estimated_duration}s")

# Check for critical issues
if assessment.has_critical_issues:
    print("\nCritical issues found:")
    for issue in assessment.issues:
        if issue.severity == "critical":
            print(f"- {issue.message}")
            if issue.fix_description:
                print(f"  Fix: {issue.fix_description}")

# Review required steps
if assessment.required_steps:
    print("\nMigration steps:")
    for step in assessment.required_steps:
        print(f"- {step.name}: {step.description}")
        print(f"  Duration: ~{step.estimated_duration}s")
        print(f"  Reversible: {step.reversible}")
```

## Version-Specific Migrations

### Migrating to 0.19.x

Key changes in 0.19.x:

- **Pydantic V2**: Use `model_config = ConfigDict()` instead of `class Config:`
- **Configuration Structure**: Move configs to `settings/` directory
- **Python 3.13+**: Minimum Python version requirement

```python
# Migration handles these automatically
result = await manager.migrate(target_version="0.19.0")

# Check what was changed
for step in result.required_steps:
    print(f"Completed: {step.name}")
```

#### Manual Configuration Migration

If you prefer manual migration:

```bash
# Create settings directory
mkdir -p settings/secrets

# Move configuration files
mv config.yaml settings/app.yml
mv debug.yaml settings/debug.yml
mv .env settings/secrets/.env

# Create adapter configuration
cat > settings/adapters.yml << EOF
# ACB Adapter Configuration
cache: redis
storage: s3
sql: postgresql
models: true
EOF
```

### Migrating to 0.20.x

Key changes in 0.20.x (future):

- Additional deprecations will be documented here
- Breaking changes will require migration steps
- Compatibility layer maintains backward compatibility

## Rollback Mechanisms

### Automatic Rollback

By default, migrations create backup points and rollback on error:

```python
result = await manager.migrate(
    target_version="0.20.0",
    auto_rollback=True,  # Default
)

if result.status == "rolled_back":
    print("Migration failed and was automatically rolled back")
    print(f"Errors: {result.errors}")
```

### Manual Rollback

```python
# List available rollback points
rollback_points = manager.list_rollback_points()

for point in rollback_points:
    print(f"ID: {point.id}")
    print(f"Version: {point.version}")
    print(f"Created: {point.created_at}")
    print(f"Description: {point.description}")
    print(f"Files backed up: {point.file_count}")
    print()

# Rollback to specific point
success = await manager.rollback(rollback_points[0].id)

if success:
    print("Rollback completed successfully")
else:
    print("Rollback failed - check logs")
```

### Cleanup Old Rollbacks

```python
from acb.migration import RollbackManager

rollback_mgr = RollbackManager()

# Keep only 5 most recent rollback points
removed = await rollback_mgr.cleanup_old_rollbacks(keep_count=5)
print(f"Removed {removed} old rollback points")
```

## Compatibility Layers

ACB provides compatibility layers for deprecated interfaces:

```python
from acb.migration import get_compatibility_layer

# Get compatibility layer for current version
compat = get_compatibility_layer("0.18.0")

# Warns about deprecated patterns
compat.old_config_class_pattern()  # Emits DeprecationWarning
compat.old_config_location("config.yaml")  # Warns about old location
```

### Version-Specific Compatibility

```python
from acb.migration.compatibility import V018CompatibilityLayer

# Use specific compatibility layer
compat = V018CompatibilityLayer()

# Check for deprecated cache methods
compat.old_cache_interface("get_or_set")  # Warns about deprecated method
```

## Migration Scripts

### Built-in Scripts

ACB includes several built-in migration scripts:

1. **configuration_migration**: Migrates config files to `settings/` directory
1. **adapter_migration**: Creates/updates `settings/adapters.yml`
1. **dependency_update**: Guides dependency updates via `uv sync`
1. **major_version_upgrade**: Handles breaking changes for major versions

### Custom Migration Scripts

Create custom migration scripts for project-specific needs:

```python
from acb.migration.scripts import MigrationScript, register_migration_script
from pathlib import Path


class CustomMigrationScript(MigrationScript):
    def __init__(self):
        super().__init__(
            name="custom_migration", description="Custom project-specific migration"
        )

    async def execute(self, project_root: Path, config: MigrationConfig) -> None:
        # Implement custom migration logic
        logger.info("Running custom migration")

        # Access migration config
        print(f"Migrating from {config.source_version} to {config.target_version}")

        # Perform migration steps
        # ... your migration code here ...

        # Track modified files
        self.files_modified += 1


# Register custom script
register_migration_script("custom_migration", CustomMigrationScript)
```

## Validation

### Post-Migration Validation

Migrations are automatically validated:

```python
from acb.migration import MigrationValidator

validator = MigrationValidator()

# Validate migration results
result = await validator.validate_migration(
    project_root=Path.cwd(), config=migration_config
)

if result.success:
    print(f"Validation passed: {result.checks_passed} checks")
else:
    print(f"Validation failed: {result.checks_failed} checks")

    for issue in result.issues:
        print(f"\n{issue.severity}: {issue.component}")
        print(f"  {issue.message}")
        if issue.fix_suggestion:
            print(f"  Fix: {issue.fix_suggestion}")
```

### Custom Validation

Add custom validation checks:

```python
class CustomValidator(MigrationValidator):
    async def validate_migration(self, project_root, config):
        # Run standard validations
        result = await super().validate_migration(project_root, config)

        # Add custom validation
        if await self._validate_custom_requirement(project_root):
            result.checks_passed += 1
        else:
            result.checks_failed += 1

        return result

    async def _validate_custom_requirement(self, project_root: Path) -> bool:
        # Implement custom validation logic
        return True
```

## Best Practices

### Before Migration

1. **Backup Your Project**: Create a backup before migrating

   ```bash
   tar -czf project-backup.tar.gz /path/to/project
   ```

1. **Review Breaking Changes**: Check CHANGELOG.md for version-specific changes

1. **Test in Development**: Test migration in development environment first

1. **Run Assessment**: Use `assess_migration()` to understand requirements

### During Migration

1. **Use Dry Run**: Test migration with `dry_run=True` first

1. **Monitor Progress**: Watch migration logs for issues

1. **Keep Rollback Enabled**: Use `auto_rollback=True` for safety

### After Migration

1. **Validate Results**: Check migration validation results

1. **Run Tests**: Run your test suite to verify functionality

1. **Update Dependencies**: Run `uv sync` to update dependencies

1. **Review Warnings**: Address any deprecation warnings

## Troubleshooting

### Common Issues

#### Python Version Mismatch

```
Error: Python 3.12 is not supported. ACB requires Python 3.13+
```

**Solution**: Upgrade to Python 3.13 or later:

```bash
uv python install 3.13
uv venv --python 3.13
```

#### Missing Configuration Files

```
Error: settings/adapters.yml not found
```

**Solution**: Create configuration files manually or run migration:

```bash
mkdir -p settings
touch settings/adapters.yml settings/app.yml
```

#### Migration Failed - Files in Use

```
Error: Failed to move config.yaml: File is in use
```

**Solution**: Close applications using config files and retry:

```bash
lsof | grep config.yaml  # Find processes using file
# Close the applications, then retry migration
```

#### Rollback Point Not Found

```
Error: Rollback point not found: abc123
```

**Solution**: List available rollback points:

```python
points = manager.list_rollback_points()
if points:
    await manager.rollback(points[0].id)
```

### Debug Mode

Enable debug logging for detailed migration information:

```python
from acb.logger import logger
import logging

# Enable debug logging
logger.setLevel(logging.DEBUG)

# Run migration with detailed output
result = await manager.migrate(target_version="0.20.0")
```

### Getting Help

- **GitHub Issues**: https://github.com/lesleslie/acb/issues
- **Documentation**: https://acb.readthedocs.io
- **Changelog**: See CHANGELOG.md for version-specific details

## Examples

### Complete Migration Workflow

```python
from pathlib import Path
from acb.migration import (
    MigrationManager,
    assess_migration,
    detect_version,
)
from acb.logger import logger


async def migrate_project():
    """Complete migration workflow example."""

    # 1. Detect current version
    current = detect_version()
    logger.info(f"Current ACB version: {current}")

    # 2. Assess migration requirements
    assessment = await assess_migration(target_version="0.20.0", config_dir=Path.cwd())

    logger.info(f"Compatibility: {assessment.compatibility_status}")
    logger.info(f"Estimated duration: {assessment.estimated_duration}s")

    if assessment.has_critical_issues:
        logger.error("Critical issues found - cannot proceed")
        for issue in assessment.issues:
            if issue.severity == "critical":
                logger.error(f"  {issue.message}")
        return False

    # 3. Run dry-run first
    manager = MigrationManager()
    dry_result = await manager.migrate(target_version="0.20.0", dry_run=True)

    logger.info(f"Dry run completed: {dry_result.status}")
    logger.info(f"Would modify {dry_result.metrics.files_modified} files")

    # 4. Confirm with user (in interactive mode)
    # proceed = input("Proceed with migration? (y/n): ")
    # if proceed.lower() != 'y':
    #     return False

    # 5. Run actual migration
    result = await manager.migrate(target_version="0.20.0", auto_rollback=True)

    if result.success:
        logger.info("✓ Migration completed successfully")
        logger.info(f"  Duration: {result.metrics.duration_seconds:.2f}s")
        logger.info(f"  Files modified: {result.metrics.files_modified}")
        logger.info(f"  Steps completed: {result.metrics.steps_completed}")

        if result.rollback_point:
            logger.info(f"  Rollback point: {result.rollback_point.id}")

        return True
    else:
        logger.error("✗ Migration failed")
        for error in result.errors:
            logger.error(f"  {error}")

        if result.status == "rolled_back":
            logger.info("  Changes were automatically rolled back")

        return False


# Run migration
if __name__ == "__main__":
    import asyncio

    success = asyncio.run(migrate_project())
    exit(0 if success else 1)
```

## Migration Checklist

Use this checklist when migrating:

- [ ] Review CHANGELOG.md for version-specific changes
- [ ] Backup project directory
- [ ] Check Python version (3.13+ required)
- [ ] Run migration assessment
- [ ] Review breaking changes and required steps
- [ ] Test migration with dry-run mode
- [ ] Run actual migration with auto-rollback enabled
- [ ] Validate migration results
- [ ] Run project test suite
- [ ] Update dependencies with `uv sync`
- [ ] Address deprecation warnings
- [ ] Update documentation if needed
- [ ] Commit migration changes

## Version Compatibility Matrix

| Current Version | Target Version | Migration Required | Notes |
|----------------|----------------|-------------------|-------|
| 0.18.x | 0.19.x | Yes | Config structure changes, Pydantic V2 |
| 0.19.x | 0.19.x | No | Patch updates are compatible |
| 0.19.x | 0.20.x | Yes | Future breaking changes (TBD) |
| < 0.18 | 0.19.x | Yes | Multi-step migration required |

## Additional Resources

- **CHANGELOG.md**: Detailed version history and breaking changes
- **MIGRATION-0.19.0.md**: Version-specific migration guide
- **API Reference**: https://acb.readthedocs.io/api/migration
- **Example Projects**: https://github.com/lesleslie/acb-examples
