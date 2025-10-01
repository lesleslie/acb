#!/usr/bin/env python3
"""Demo script showing the new ACB adapter metadata system.

This script demonstrates:
1. Loading adapters with metadata
2. Extracting adapter information
3. Checking capabilities
4. Generating reports

Run with: python examples/adapter_metadata_demo.py
"""

import asyncio

from acb.adapters import (
    AdapterCapability,
    check_adapter_capability,
    extract_metadata_from_class,
    generate_adapter_report,
    get_adapter_info,
    import_adapter,
    list_adapter_capabilities,
)


async def main() -> None:
    """Demonstrate the adapter metadata system."""
    # Import the Redis cache adapter (which now has metadata)
    try:
        Cache = import_adapter("cache")
    except Exception:
        return

    # Extract metadata
    metadata = extract_metadata_from_class(Cache)
    if metadata:
        pass
    else:
        return

    # Check specific capabilities
    capabilities_to_check = [
        AdapterCapability.CONNECTION_POOLING,
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.CACHING,
        AdapterCapability.TRANSACTIONS,  # This should be False for cache
        AdapterCapability.METRICS,
    ]

    for capability in capabilities_to_check:
        check_adapter_capability(Cache, capability)

    all_capabilities = list_adapter_capabilities(Cache)  # type: ignore[assignment]
    for _i, capability in enumerate(all_capabilities, 1):  # type: ignore[assignment]
        pass  # type: ignore[assignment]

    generate_adapter_report(Cache)

    from acb import __version__ as acb_version
    from acb.adapters import validate_version_compatibility

    validate_version_compatibility(metadata, acb_version)

    # Example use cases
    if check_adapter_capability(Cache, AdapterCapability.CONNECTION_POOLING):
        pass

    get_adapter_info(Cache)


if __name__ == "__main__":
    asyncio.run(main())
