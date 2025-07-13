# ACB Adapter Module Template

This template provides the standard structure for ACB adapter modules with hard-coded metadata identification.

## Module Header Template

Copy this template when creating new adapter modules:

```python
"""[Adapter Name] Adapter for ACB.

[Brief description of what this adapter does and what technology it integrates with.]

Example:
    Basic usage of this adapter:

    ```python
    from acb.depends import depends
    from acb.adapters import import_adapter

    Cache = import_adapter("cache")

    @depends.inject
    async def my_function(cache: Cache = depends()):
        await cache.set("key", "value")
        return await cache.get("key")
    ```

Features:
    - [List key features/capabilities]
    - [What makes this adapter special]
    - [Performance characteristics]

Requirements:
    - [External package requirements]
    - [Minimum ACB version]

Author: [Your Name] <[your.email@domain.com]>
Created: [YYYY-MM-DD]
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from acb.adapters import (
    AdapterCapability,
    AdapterMetadata,
    AdapterStatus,
    generate_adapter_id,
)

# =============================================================================
# MODULE METADATA - Hard-coded identification for this adapter
# =============================================================================

MODULE_METADATA = AdapterMetadata(
    # Unique identification (GENERATE NEW UUID7 FOR EACH ADAPTER)
    module_id=generate_adapter_id(),  # Generates UUID7 automatically

    # Basic information
    name="Example Adapter",
    category="example",  # cache, sql, storage, etc.
    provider="example-tech",  # redis, mysql, s3, etc.

    # Version information
    version="1.0.0",
    acb_min_version="0.18.0",
    acb_max_version=None,  # None = no upper limit

    # Development information
    author="Your Name <your.email@domain.com>",
    created_date="2025-01-12",  # ISO date
    last_modified="2025-01-12",  # Update when making significant changes

    # Status and capabilities
    status=AdapterStatus.ALPHA,  # alpha, beta, stable, deprecated, experimental
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.CONNECTION_POOLING,
        # Add relevant capabilities
    ],

    # Dependencies
    required_packages=[
        "example-sdk>=1.0.0",
    ],
    optional_packages={
        "example-extras": "Enhanced features and performance optimizations",
    },

    # Documentation
    description="Integrates ACB with ExampleTech for [specific use case]",
    documentation_url="https://docs.acb.dev/adapters/example",
    repository_url="https://github.com/your-org/acb-example-adapter",

    # Configuration
    settings_class="ExampleSettings",
    config_example={
        "host": "localhost",
        "port": 1234,
        "timeout": 30,
    },

    # Custom metadata for specific needs
    custom={
        "performance_tier": "high",
        "encryption_support": True,
        "cloud_native": True,
    }
)

# =============================================================================
# ADAPTER IMPLEMENTATION
# =============================================================================

# ... rest of your adapter implementation
```

## Metadata Field Guidelines

### Required Fields

| Field | Description | Example |
|-------|-------------|---------|
| `module_id` | **NEW UUID7 for each adapter** | `generate_adapter_id()` |
| `name` | Human-readable name | `"Redis Cache"` |
| `category` | ACB adapter category | `"cache"` |
| `provider` | Technology provider | `"redis"` |
| `version` | Adapter version (semver) | `"1.2.3"` |
| `author` | Creator/maintainer | `"Name <email>"` |
| `created_date` | Creation date (ISO) | `"2025-01-12"` |
| `description` | Brief description | `"Redis caching with..."` |

### Status Values

- `ALPHA` - Early development, breaking changes expected
- `BETA` - Feature complete, may have bugs
- `STABLE` - Production ready
- `DEPRECATED` - Scheduled for removal
- `EXPERIMENTAL` - Proof of concept

### Capability Categories

**Connection Management:**
- `CONNECTION_POOLING`
- `AUTO_RECONNECTION`
- `HEALTH_CHECKS`

**Data Operations:**
- `TRANSACTIONS`
- `BULK_OPERATIONS`
- `STREAMING`
- `COMPRESSION`
- `ENCRYPTION`

**Performance:**
- `CACHING`
- `ASYNC_OPERATIONS`
- `BATCHING`

**Observability:**
- `METRICS`
- `TRACING`
- `STRUCTURED_LOGGING`

## Version Updating Guidelines

When updating an adapter:

1. **Update `last_modified`** to current ISO date
2. **Increment `version`** following semver:
   - Patch: `1.0.0` → `1.0.1` (bug fixes)
   - Minor: `1.0.0` → `1.1.0` (new features)
   - Major: `1.0.0` → `2.0.0` (breaking changes)
3. **Update `acb_min_version`** if using new ACB features
4. **Add/remove capabilities** as features change
5. **Update dependencies** in `required_packages`

## Metadata Usage Examples

### Checking Compatibility
```python
from acb.adapters import validate_version_compatibility
from acb.adapters.cache.redis import MODULE_METADATA

is_compatible = validate_version_compatibility(MODULE_METADATA, "0.18.0")
```

### Feature Detection
```python
from acb.adapters import AdapterCapability

if AdapterCapability.CONNECTION_POOLING in MODULE_METADATA.capabilities:
    print("This adapter supports connection pooling")
```

### Runtime Information
```python
print(f"Adapter ID: {MODULE_METADATA.module_id}")
print(f"Version: {MODULE_METADATA.version}")
print(f"Author: {MODULE_METADATA.author}")
```
