> **ACB Documentation**: [Main](../README.md) | [Core Systems](./README.md) | [Actions](./actions/README.md) | [Adapters](./adapters/README.md)

# ACB: Core Systems

This document provides in-depth details about the core systems in the Asynchronous Component Base (ACB) package. It covers Configuration & Settings, Dependency Injection, Debugging Tools, and Logging.

## Table of Contents

- [Overview](#overview)
- [Configuration and Settings](#1-configuration-and-settings)
- [Dependency Injection](#2-dependency-injection)
- [Debugging Tools](#3-debugging-tools)
- [Logging](#4-logging)
- [Related Projects](#related-projects)
- [Further Reading](#further-reading)

## Overview

ACB provides a set of interconnected core systems that work together to simplify asynchronous application development:

- **Configuration**: Flexible, layered configuration with secret management
- **Dependency Injection**: Simplified component wiring with automatic resolution
- **Debugging**: Comprehensive tools for troubleshooting and performance monitoring
- **Logging**: Asynchronous, structured logging with multiple adapters

The diagram below illustrates how these systems interact:

```
┌─────────────────┐     ┌─────────────────┐
│  Configuration  │<────│  Secret Manager │
└───────┬─────────┘     └─────────────────┘
        │
        ▼
┌─────────────────┐     ┌─────────────────┐
│    Dependency   │────>│     Adapters    │
│    Injection    │     └─────────────────┘
└───────┬─────────┘
        │
        ▼
┌─────────────────┐     ┌─────────────────┐
│     Logging     │<────│     Debug       │
└─────────────────┘     └─────────────────┘
```

---

## 1. Configuration and Settings

ACB uses a robust configuration system based on [Pydantic](https://pydantic-docs.helpmanual.io/) and [pydantic-settings](https://pydantic-settings.helpmanual.io/) to allow flexible and layered configuration.

### Key Features

- **Dynamic Settings Sources**
  The configuration system aggregates settings from multiple sources:
  - **Initialization Parameters:** Passed in at startup.
  - **YAML Configuration Files:** Settings are read from YAML files (e.g., `app.yml` for application settings, or other adapter-specific YAML files).
  - **File-based Secrets:** Manages secrets stored in files within a designated secrets directory.
  - **External Secret Managers:** Optionally integrates with external secret managers using adapters (see the secret adapter in `acb/adapters/secret`).

- **Settings Models**
  Two main settings models extend from a common Base Settings class:
  - **`AppSettings`:** Defines application-wide settings including the app name, secret key, secure salt, title, domain, platform, and version.
  - **`DebugSettings`:** Provides configuration options for debugging, such as whether production mode is active or if secrets/logging should be enabled.

- **Initialization Routine**
  On startup, ACB performs initial setup tasks:
  - Registers the package via `register_pkg()`.
  - Ensures all required temporary and secrets directories are created.
  - Reads and aggregates settings from the various sources using custom classes: `InitSettingsSource`, `YamlSettingsSource`, `FileSecretSource`, and `ManagerSecretSource`.

### Installation with Configuration-Related Dependencies

```bash
# Install with secret management support
pdm add "acb[secret]"

# Install with YAML and configuration support
pdm add "acb[config]"

# Install with multiple configuration options
pdm add "acb[secret,config]"
```

For more detailed configuration information, refer to [Configuration Documentation](./configuration.md).

---

## 2. Dependency Injection

ACB utilizes a dependency injection system to simplify module wiring and promote decoupled design. The system is implemented in the `acb/depends.py` module and is built upon the [bevy](https://github.com/bevy-org/bevy) package.

### Core Components

- **`depends`**
  A central object that provides key functionality:
  - **`depends.inject`:** A decorator to automatically inject dependencies into functions.
  - **`depends.set`:** Registers a dependency into the dependency repository.
  - **`depends.get`:** Retrieves an instance of a registered dependency. It can even dynamically import adapters by name if needed.

### Usage

Developers decorate their functions or classes with `@depends.inject` to have components like configuration objects and loggers automatically provided. This reduces boilerplate and ensures consistency across the application.

### Example: Dependency Injection with Multiple Components

```python
from acb.depends import depends
from acb.config import Config
from acb.adapters import import_adapter

# Import multiple adapters
Cache = import_adapter("cache")
Storage = import_adapter("storage")

@depends.inject
def process_file(file_id, cache=depends(Cache), storage=depends(Storage), config=depends(Config)):
    # Use multiple injected dependencies together
    cached_data = await cache.get(f"file:{file_id}")
    if not cached_data:
        file_data = await storage.get_file(file_id)
        await cache.set(f"file:{file_id}", file_data, ttl=config.cache.ttl)
        return file_data
    return cached_data
```

For more information on dependency injection, please see the [Dependency Injection Documentation](./dependency-injection.md).

---

## 3. Debugging Tools

The debug module in ACB (`acb/debug.py`) is designed to provide insightful diagnostics for asynchronous components.

### Key Features

- **Custom Debug Output**
  ACB leverages third-party libraries such as `icecream` and `devtools` to provide formatted and, when needed, colorized debug output.

- **Dynamic Debugging**
  Utility functions like `get_calling_module` and `patch_record` help trace the origin of log messages, enabling context-specific debugging.

- **Timing Utility**
  The `timeit` decorator measures function execution duration and logs the time taken, which assists in performance monitoring.

- **Environment-aware Behavior**
  Debug output can be adjusted based on whether the application is in development mode or deployed in production.

### Example: Using the Timing Utility

```python
from acb.debug import timeit

@timeit
async def expensive_operation(data):
    # Your code here
    result = await process_data(data)
    return result

# Output will include execution time:
# expensive_operation took 1.23s
```

For detailed examples and further instructions, refer to the [Debug Documentation](./debug.md).

---

## 4. Logging

ACB comes with a default logging system powered by [Loguru](https://loguru.readthedocs.io/). Its logging module is implemented in the `acb/adapters/logger` package, providing robust and flexible logging capabilities.

### Default Logging System – Loguru

- **Asynchronous Logging**
  The Loguru adapter (`loguru.py`) includes an asynchronous sink that uses `aioconsole.aprint` to handle log messages without blocking asynchronous operations.

- **Dynamic Configuration**
  The logging settings are configurable via the ACB configuration system. The `LoggerSettings` class (derived from `LoggerBaseSettings`) determines log format, log level, and module-specific settings.

- **Intercepting Standard Logging**
  A custom `InterceptHandler` is used to capture standard Python logging and route it through Loguru, ensuring consistent logging output across the application.

- **Flexible Output Customization**
  With options for serialization, colorization, and custom formatting, Loguru is tailored to adapt to different environments (development vs. production).

### Extensibility

An alternative logging adapter using `structlog` is available as a placeholder, allowing teams to swap out Loguru if desired.

### Installation with Logging Options

```bash
# Install with Loguru support (default)
pdm add "acb[loguru]"

# Install with structlog support
pdm add "acb[structlog]"

# Install with multiple logging options for testing
pdm add "acb[loguru,structlog]"
```

For more details on logging configuration and customization, see the [Logging Documentation](./logging.md).

---

## Related Projects

ACB is used in several projects including:

- [**FastBlocks**](https://github.com/example/fastblocks): A rapid development framework that leverages ACB's asynchronous components to build scalable web applications.

---

## Further Reading

- [Main ACB Documentation](../README.md): Overview of the entire ACB framework
- [Actions Documentation](./actions/README.md): Details about built-in actions and creating custom ones
- [Adapters Documentation](./adapters/README.md): Information about adapter interfaces and implementations
- [Configuration Documentation](./configuration.md): Detailed guide to the configuration system
- [Dependency Injection Documentation](./dependency-injection.md): In-depth explanation of the dependency injection system
- [Debug Documentation](./debug.md): Guide to using the debugging tools effectively
- [Logging Documentation](./logging.md): Comprehensive information about logging configuration and customization
