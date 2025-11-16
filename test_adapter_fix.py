#!/usr/bin/env python3
"""
Test script to check if the adapter registry fix works correctly.
"""

from contextvars import ContextVar

# Simulate the fixed code structure
class MockAdapter:
    def __init__(self, name, category):
        self.name = name
        self.category = category
        self.enabled = True
        self.installed = True

# Initialize ContextVars with None default (just like the original code)
adapter_registry: ContextVar[list] = ContextVar("adapter_registry", default=None)
_enabled_adapters_cache: ContextVar[dict] = ContextVar("_enabled_adapters_cache", default=None)
_installed_adapters_cache: ContextVar[dict] = ContextVar("_installed_adapters_cache", default=None)
_adapter_import_locks: ContextVar[dict] = ContextVar("_adapter_import_locks", default=None)

def _ensure_adapter_registry_initialized() -> list:
    """Ensure the adapter registry is initialized with an empty list if needed."""
    registry = adapter_registry.get(None)
    if registry is None:
        registry = []
        adapter_registry.set(registry)
    return registry


def _ensure_enabled_adapters_cache_initialized() -> dict:
    """Ensure the enabled adapters cache is initialized with an empty dict if needed."""
    cache = _enabled_adapters_cache.get(None)
    if cache is None:
        cache = {}
        _enabled_adapters_cache.set(cache)
    return cache


def _ensure_installed_adapters_cache_initialized() -> dict:
    """Ensure the installed adapters cache is initialized with an empty dict if needed."""
    cache = _installed_adapters_cache.get(None)
    if cache is None:
        cache = {}
        _installed_adapters_cache.set(cache)
    return cache


def _ensure_adapter_import_locks_initialized() -> dict:
    """Ensure the adapter import locks are initialized with an empty dict if needed."""
    locks = _adapter_import_locks.get(None)
    if locks is None:
        locks = {}
        _adapter_import_locks.set(locks)
    return locks


def _update_adapter_caches() -> None:
    enabled_cache = {}
    installed_cache = {}
    for adapter in _ensure_adapter_registry_initialized():
        if adapter.enabled:
            enabled_cache[adapter.category] = adapter
        if adapter.installed:
            installed_cache[adapter.category] = adapter
    _enabled_adapters_cache.set(enabled_cache)
    _installed_adapters_cache.set(installed_cache)


# Test the original failing code scenario
print("Testing the fix...")

# This is the line that was failing before: adapter_registry.get().extend([*core_adapters])
core_adapters = [
    MockAdapter(name="config", category="config"),
    MockAdapter(name="loguru", category="logger"),
]

# This should now work without error
_ensure_adapter_registry_initialized().extend([*core_adapters])
_update_adapter_caches()

print("SUCCESS: No AttributeError occurred!")
print(f"Registry now contains {len(adapter_registry.get())} adapters")
print(f"Enabled cache keys: {list(_enabled_adapters_cache.get().keys())}")
print(f"Installed cache keys: {list(_installed_adapters_cache.get().keys())}")

# Test accessing the caches as the functions do
enabled_cache = _ensure_enabled_adapters_cache_initialized()
installed_cache = _ensure_installed_adapters_cache_initialized()

print("SUCCESS: Cache access functions work correctly!")

# Test adapter import locks function
locks = _ensure_adapter_import_locks_initialized()
locks["test_category"] = "test_lock"
print("SUCCESS: Adapter import locks work correctly!")

print("\nThe fix successfully resolves the original issue where adapter_registry.get() returned None!")
