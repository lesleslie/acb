# Migration Guide: pyproject.toml Dependency Groups (v0.24.0)

## Breaking Change

ACB v0.24.0 migrates from `[project.optional-dependencies]` to `[dependency-groups]` following **PEP 735** and modern UV standards. This is a **breaking change** that requires updating installation commands.

## What Changed

### Old Syntax (No Longer Works)

```bash
uv add "acb[cache]"
uv add "acb[cache,sql,storage]"
uv add "acb[all]"
```

### New Syntax

```bash
uv add --group cache
uv add --group cache --group sql --group storage
uv add --group all
```

## Why This Change?

1. **PEP 735 Compliance**: Modern standard for dependency groups
1. **Zero Self-References**: Eliminates circular dependency errors
1. **UV Compatibility**: Full support for latest UV features
1. **Better Organization**: Dependencies grouped by category
1. **Explicit Dependencies**: No surprise installations

## Migration Steps

### 1. Update Installation Commands

#### Atomic Groups (Direct Replacement)

```bash
# Infrastructure
uv add --group cache
uv add --group dns
uv add --group ftpd
uv add --group monitoring
uv add --group requests
uv add --group secret
uv add --group smtp
uv add --group storage

# Databases
uv add --group sql
uv add --group nosql
uv add --group vector
uv add --group graph

# AI/ML
uv add --group ai
uv add --group embedding
uv add --group reasoning

# Frameworks
uv add --group models
uv add --group logger
uv add --group mcp
uv add --group demo
```

#### Queue Adapters

```bash
# Base APScheduler
uv add --group queue-apscheduler

# With persistence backends
uv add --group queue-apscheduler-sql
uv add --group queue-apscheduler-mongodb
uv add --group queue-apscheduler-redis
```

#### Composite Groups (Use Cases)

```bash
# Minimal setup
uv add --group minimal

# API development
uv add --group api

# Microservices
uv add --group microservice

# Web applications
uv add --group webapp
uv add --group webapp-plus  # With vector support

# Cloud-native
uv add --group cloud-native

# Data platform
uv add --group dataplatform

# GCP-specific
uv add --group gcp

# All adapters
uv add --group all
```

### 2. Update CI/CD Pipelines

If your CI/CD uses extras syntax, update your workflows:

**GitHub Actions (before)**:

```yaml
- name: Install dependencies
  run: uv add "acb[cache,sql,storage]"
```

**GitHub Actions (after)**:

```yaml
- name: Install dependencies
  run: uv add --group cache --group sql --group storage
```

### 3. Update Documentation

Update any internal documentation, README files, or setup scripts that reference the old syntax.

### 4. Reinstall Dependencies

After upgrading to v0.24.0, reinstall your dependency groups:

```bash
# Remove old installation
uv remove acb

# Install core ACB
uv add acb

# Add your required groups
uv add --group cache --group sql --group monitoring
```

## Key Differences

### Core Package Changes

**Before (v0.23.1)**:

- Core `acb` package included cache, dns, ftpd, monitoring, nosql, requests, secret, smtp, storage automatically
- Many adapters installed by default

**After (v0.24.0)**:

- Core `acb` package is minimal - only essential dependencies
- All adapters are opt-in via dependency groups
- You explicitly choose what you need

### Composite Groups

Composite groups (api, webapp, cloud-native, etc.) are now **fully flattened**:

**Before**:

- `acb[webapp]` referenced `acb[cache]`, `acb[sql]`, etc.
- Could cause circular dependency errors

**After**:

- `--group webapp` contains all dependencies explicitly
- Zero self-references, no circular dependencies

## Troubleshooting

### Error: "Unknown extra: cache"

**Problem**: Using old extras syntax

```bash
uv add "acb[cache]"  # ❌ Fails
```

**Solution**: Use new dependency group syntax

```bash
uv add --group cache  # ✅ Works
```

### Error: "Self-dependencies are not permitted"

**Problem**: Older UV version might have caching issues

**Solution**:

```bash
uv cache clean
uv remove acb
uv add acb
uv add --group cache
```

### Multiple Groups Installation

**Preferred approach** (install multiple groups at once):

```bash
uv add --group cache --group sql --group storage
```

**Alternative** (install one at a time):

```bash
uv add --group cache
uv add --group sql
uv add --group storage
```

## Benefits of This Change

1. **Faster installation**: UV handles dependency groups more efficiently
1. **Better control**: Explicitly choose what adapters you need
1. **Cleaner dependencies**: No circular references or surprise installations
1. **Modern standards**: Aligned with PEP 735 and UV best practices
1. **Easier maintenance**: Each group is self-contained and independent

## APScheduler Version Update

As part of this release, APScheduler dependency was updated:

- **Old**: `apscheduler>=3.10.0`
- **New**: `apscheduler>=4.0.0`

If you use APScheduler queue adapter, ensure your code is compatible with APScheduler 4.x API changes.

## Questions?

- See the main [README.md](<./README.md>) for updated installation examples
- Check [CHANGELOG.md](<./CHANGELOG.md>) for detailed release notes
- Review [CLAUDE.md](<./CLAUDE.md>) for development guidelines

## Migration Checklist

- [ ] Updated installation commands to use `--group` syntax
- [ ] Updated CI/CD pipelines
- [ ] Updated internal documentation
- [ ] Reinstalled dependencies with new syntax
- [ ] Verified application still works with new dependency structure
- [ ] Updated team documentation/onboarding guides

______________________________________________________________________

**Version**: 0.24.0
**Migration Difficulty**: Low (syntax change only)
**Estimated Time**: 5-10 minutes
