> **ACB Documentation**: [Main](../README.md) | [Core Systems](./README.md) | [Actions](./actions/README.md) | [Adapters](./adapters/README.md)

# ACB: Core Systems

This document provides in-depth details about the core systems in the Asynchronous Component Base (ACB) package. It covers Configuration & Settings, Dependency Injection, Debugging Tools, and Logging.

## Table of Contents

- [Overview](#overview)
- [Configuration and Settings](#1-configuration-and-settings)
- [Dependency Injection](#2-dependency-injection)
- [Debugging Tools](#3-debugging-tools)
- [Logging](#4-logging)
- [MCP Server](#5-mcp-server)
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

______________________________________________________________________

## 1. Configuration and Settings

ACB uses a robust configuration system based on [Pydantic](https://pydantic-docs.helpmanual.io/) and [pydantic-settings](https://pydantic-settings.helpmanual.io/) to allow flexible and layered configuration.

### Key Features

- **Dynamic Settings Sources**
  The configuration system aggregates settings from multiple sources:

  - **Initialization Parameters:** Passed in at startup.
  - **YAML Configuration Files:** Settings are read from YAML files (e.g., `app.yaml` for application settings, or other adapter-specific YAML files).
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
uv add acb --group secret

# Install with YAML and configuration support
uv add acb --group config

# Install with multiple configuration options
uv add acb --group secret --group config
```

For more detailed configuration information, refer to [Configuration Documentation](../docs/CONFIGURATION.md).

______________________________________________________________________

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

import typing as t

# Import multiple adapters
Cache = import_adapter("cache")
Storage = import_adapter("storage")


@depends.inject
async def process_file(
    file_id: str, cache=depends(Cache), storage=depends(Storage), config=depends(Config)
) -> bytes | None:
    # Use multiple injected dependencies together
    cached_data: bytes | None = await cache.get(f"file:{file_id}")
    if not cached_data:
        file_data: bytes | None = await storage.get_file(file_id)
        if file_data:
            await cache.set(f"file:{file_id}", file_data, ttl=config.cache.ttl)
        return file_data
    return cached_data
```

For more information on dependency injection, please see the [Dependency Injection Documentation](../docs/DEPENDENCY-INJECTION.md).

______________________________________________________________________

## 3. Debugging Tools

The debug module in ACB (`acb/debug.py`) is designed to provide insightful diagnostics for asynchronous components. It offers a comprehensive set of tools to help you troubleshoot your applications effectively.

### Key Features

- **Custom Debug Output**
  ACB leverages third-party libraries such as `icecream` and `devtools` to provide formatted and, when needed, colorized debug output. This makes complex data structures easier to read and understand during debugging.

- **Dynamic Debugging**
  Utility functions like `get_calling_module` and `patch_record` help trace the origin of log messages, enabling context-specific debugging. This is particularly useful in large applications where identifying the source of issues can be challenging.

- **Timing Utility**
  The `timeit` decorator measures function execution duration and logs the time taken, which assists in performance monitoring and optimization. This is invaluable for identifying bottlenecks in your application.

- **Environment-aware Behavior**
  Debug output can be adjusted based on whether the application is in development mode or deployed in production. This ensures that you get detailed information during development while avoiding performance impacts in production.

- **Integration with Logging System**
  The debug module integrates seamlessly with ACB's logging system, allowing debug information to be captured in your application logs when appropriate.

### Debug Configuration

ACB's debug behavior can be configured through your application settings in `settings/debug.yaml`:

```yaml
debug:
  enabled: true           # Enable/disable debugging globally
  production: false       # Production mode changes debug behavior
  log_level: "DEBUG"      # Set the debug log level
  # Module-specific debug settings
  cache: true             # Enable debugging for cache module
  storage: false          # Disable debugging for storage module
```

The configuration system allows you to enable or disable debugging for specific modules, which helps reduce noise and focus on the components you're currently working with.

### Debug Utilities

#### Basic Debugging with `debug`

The `debug` function (powered by icecream) provides enhanced debugging output:

```python
from acb.debug import debug

# Basic usage - prints the expression and its value
user_id = 123
debug(user_id)  # Output: debug: user_id = 123

# Debug multiple values
name = "John"
age = 30
debug(name, age)  # Output: debug: name = 'John', age = 30

# Debug complex objects
user_data = {"id": 123, "name": "John", "roles": ["admin", "editor"]}
debug(user_data)  # Outputs a nicely formatted representation of the dictionary
```

#### Performance Timing with `timeit`

The `timeit` decorator helps you measure function execution time:

```python
from acb.debug import timeit
import asyncio
import typing as t


@timeit
async def expensive_operation(data: dict[str, t.Any]) -> dict[str, t.Any]:
    # Your code here
    await asyncio.sleep(0.5)  # Simulate processing
    return {"result": "processed", "input_size": len(data)}


# When called, the execution time will be logged:
# expensive_operation took 0.501s
```

#### Pretty Printing with `pprint`

For complex objects, the asynchronous pretty printing function provides better readability:

```python
from acb.debug import pprint
import asyncio


async def main():
    complex_data = {
        "users": [
            {"id": 1, "name": "Alice", "roles": ["admin", "user"]},
            {"id": 2, "name": "Bob", "roles": ["user"]},
        ],
        "settings": {
            "theme": "dark",
            "notifications": True,
            "preferences": {"language": "en", "timezone": "UTC"},
        },
    }

    # Pretty print the complex data structure
    await pprint(complex_data)


asyncio.run(main())
```

#### Advanced Debugging Techniques

For more complex debugging scenarios:

```python
from acb.debug import get_calling_module, patch_record
from acb.depends import depends
from acb.logger import Logger

# Get the module that called the current function
module = get_calling_module()

# Patch log records with module information
logger = depends.get(Logger)
patch_record(module, "Debug message with module context")

# Initialize debug configuration
from acb.debug import init_debug

init_debug()  # Configures debug output based on environment
```

### Troubleshooting Tips

1. **Enable Module-Specific Debugging**: If you're having issues with a specific component, enable debugging just for that module in your debug settings.

1. **Check Environment Variables**: The `DEPLOYED` environment variable affects debug behavior. Set it to "False" during development for more verbose output.

1. **Use Colorized Output**: In development environments, colorized output makes it easier to spot important information. This is enabled by default in non-production environments.

1. **Combine with Logging**: For persistent debugging information, use the logging system alongside the debug utilities.

1. **Performance Considerations**: In production environments, be selective about what you debug to avoid performance impacts.

For detailed examples and further instructions, refer to the [Debug Documentation](../docs/DEBUG.md).

______________________________________________________________________

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
uv add acb --group logger

# Install with multiple logging options for testing (structlog via logger group)
uv add acb --group logger
```

For more details on logging configuration and customization, see the [Logging Documentation](../docs/LOGGING.md).

______________________________________________________________________

## 5. MCP Server

ACB includes a Model Context Protocol (MCP) server that provides a standardized interface for AI applications to interact with the ACB ecosystem. The MCP server acts as a central orchestration layer that exposes ACB's capabilities through the Model Context Protocol.

### Key Features

- **Component Discovery**: List all available actions, adapters, and services
- **Action Execution**: Execute any registered action with parameter validation
- **Adapter Management**: Enable, disable, or configure adapters dynamically
- **Workflow Orchestration**: Define and execute complex multi-step workflows
- **Health Monitoring**: Check the health status of system components
- **Resource Access**: Access component registry information and system metrics

### Architecture

The MCP server is built on top of ACB's existing architecture and integrates with:

- **Actions**: Business logic components that perform specific tasks
- **Adapters**: Interface components that connect to external systems
- **Services**: Background services that provide ongoing functionality
- **Events**: Event-driven communication between components
- **Configuration**: Centralized configuration management
- **Logging**: Structured logging and monitoring

For more details on the MCP server implementation, see the [MCP Server Documentation](./mcp/README.md).

______________________________________________________________________

## Related Projects

ACB is used in several projects including:

- [**FastBlocks**](https://github.com/lesleslie/fastblocks): A web application framework built on Starlette that leverages ACB's component architecture to create a powerful platform for server-side rendered HTMX applications. FastBlocks extends ACB with web-specific adapters for templates, routing, authentication, and admin interfaces.

______________________________________________________________________

## Further Reading

- [Main ACB Documentation](../README.md): Overview of the entire ACB framework
- [Actions Documentation](./actions/README.md): Details about built-in actions and creating custom ones
- [Adapters Documentation](./adapters/README.md): Information about adapter interfaces and implementations
