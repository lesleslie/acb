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
    print("🔧 ACB Adapter Metadata System Demo")
    print("=" * 40)

    # Import the Redis cache adapter (which now has metadata)
    try:
        Cache = import_adapter("cache")
        print(f"✅ Successfully imported cache adapter: {Cache.__name__}")
    except Exception as e:
        print(f"❌ Failed to import cache adapter: {e}")
        return

    print("\n📊 Adapter Information:")
    print("-" * 25)

    # Extract metadata
    metadata = extract_metadata_from_class(Cache)
    if metadata:
        print(f"🆔 Module ID: {metadata.module_id}")
        print(f"📦 Name: {metadata.name}")
        print(f"🏷️  Category: {metadata.category}")
        print(f"🔧 Provider: {metadata.provider}")
        print(f"📌 Version: {metadata.version}")
        print(f"📅 Created: {metadata.created_date}")
        print(f"👨‍💻 Author: {metadata.author}")
        print(f"🚦 Status: {metadata.status.value}")
    else:
        print("❌ No metadata found")
        return

    print("\n🎯 Capabilities Check:")
    print("-" * 22)

    # Check specific capabilities
    capabilities_to_check = [
        AdapterCapability.CONNECTION_POOLING,
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.CACHING,
        AdapterCapability.TRANSACTIONS,  # This should be False for cache
        AdapterCapability.METRICS,
    ]

    for capability in capabilities_to_check:
        has_capability = check_adapter_capability(Cache, capability)
        status = "✅" if has_capability else "❌"
        print(f"{status} {capability.value}")

    print("\n📋 All Capabilities:")
    print("-" * 18)
    all_capabilities = list_adapter_capabilities(Cache)
    for i, capability in enumerate(all_capabilities, 1):
        print(f"{i:2d}. {capability}")

    print("\n📄 Full Adapter Report:")
    print("-" * 22)
    report = generate_adapter_report(Cache)
    print(report)

    print("\n🔍 Compatibility Check:")
    print("-" * 21)
    from acb import __version__ as acb_version
    from acb.adapters import validate_version_compatibility

    is_compatible = validate_version_compatibility(metadata, acb_version)
    compat_status = "✅ Compatible" if is_compatible else "❌ Incompatible"
    print(f"ACB Version: {acb_version}")
    print(f"Required: {metadata.acb_min_version}+")
    print(f"Status: {compat_status}")

    print("\n🎯 Use Cases Demonstration:")
    print("-" * 28)

    # Example use cases
    print("1. Finding adapters with connection pooling:")
    if check_adapter_capability(Cache, AdapterCapability.CONNECTION_POOLING):
        print("   ✅ Cache adapter supports connection pooling")

    print("\n2. Getting adapter information for monitoring:")
    info = get_adapter_info(Cache)
    print(f"   📊 Adapter: {info['name']} v{info['version']}")
    print(f"   🏷️  ID: {info['module_id']}")
    print(f"   📦 Dependencies: {len(info['required_packages'])} packages")

    print("\n3. Runtime adapter identification:")
    print(f"   🆔 Unique Module ID: {metadata.module_id}")
    print("   🔄 This ID never changes for this specific adapter module")
    print("   📊 Perfect for tracking, logging, and debugging")

    print("\n✨ Demo Complete!")
    print("\nThe adapter metadata system provides:")
    print("• Unique identification for each adapter module")
    print("• Version tracking and compatibility checking")
    print("• Capability discovery and feature detection")
    print("• Comprehensive debugging and monitoring information")
    print("• Template system for new adapter development")


if __name__ == "__main__":
    asyncio.run(main())
