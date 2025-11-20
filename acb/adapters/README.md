# """ Adapter Module Structure

The adapters module has been reorganized to improve maintainability and readability.

Registry Module (registry.py):

- Contains all registry-related functions
- Manages adapter registration and caches
- Includes functions like get_adapter(), register_adapters(), etc.

Core Definitions (this file, __init__.py):

- Contains core classes and enums
- Adapter, AdapterMetadata, AdapterStatus, AdapterCapability
- Constants and exception classes
- Import functionality for backward compatibility

Note on Architecture:
The ACB framework has complex interdependencies between modules which makes
a full separation challenging. The current reorganization balances modularity
with maintaining the existing functionality and import chains.
"""
