#!/usr/bin/env python3
"""Simple test to verify service discovery system works."""

import sys
import os

# Add the project root to Python path
sys.path.insert(0, '/Users/les/Projects/acb')

def test_service_discovery():
    """Test the service discovery system."""
    try:
        # Test import_service function
        from acb.services import import_service, list_services, enable_service, get_service_info

        print("✓ Service discovery imports successful")

        # List available services
        services = list_services()
        print(f"✓ Found {len(services)} registered services:")
        for service in services:
            print(f"  - {service.name} ({service.category}) - {'enabled' if service.enabled else 'disabled'}")

        # Enable a service and test import
        enable_service("performance", "performance_optimizer")

        # Test service import
        try:
            PerformanceOptimizer = import_service("performance")
            print(f"✓ Successfully imported service: {PerformanceOptimizer.__name__}")

            # Test service info
            info = get_service_info(PerformanceOptimizer)
            print(f"✓ Service info: {info['class_name']} from {info['module']}")

            # Test metadata if available
            if hasattr(PerformanceOptimizer, 'SERVICE_METADATA'):
                metadata = getattr(PerformanceOptimizer, 'SERVICE_METADATA')
                print(f"✓ Service metadata: {metadata.name} v{metadata.version}")

        except Exception as e:
            print(f"✗ Failed to import service: {e}")
            return False

        print("\n✓ Service discovery system is working correctly!")
        return True

    except Exception as e:
        print(f"✗ Service discovery test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_service_discovery()
    sys.exit(0 if success else 1)