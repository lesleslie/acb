# ACB (Asynchronous Component Base) - Project Context

## Project Overview

ACB is a modular Python framework for building asynchronous applications with pluggable components. It provides a collection of self-contained **actions** and flexible **adapters** that integrate with various systems, along with a dynamic configuration and dependency injection system.

The framework is designed around these key concepts:

1. **Actions**: Self-contained utility functions that perform specific tasks like compression, encoding, or hashing
1. **Adapters**: Standardized interfaces to external systems like databases, caching, or storage
1. **Dependency Injection**: A pattern that automatically provides components to your functions when needed
1. **Configuration System**: A way to configure your application using YAML files instead of hardcoding values

## Project Structure

```
acb/
├── actions/         # Reusable utility functions (compress, encode, hash, etc.)
│   ├── compress/    # Data compression utilities (gzip, brotli)
│   ├── encode/      # Data serialization (JSON, YAML, TOML, MsgPack)
│   ├── hash/        # Secure hashing functions (blake3, crc32c, md5)
│   └── ...
├── adapters/        # Integration modules for external systems
│   ├── cache/       # Memory and Redis caching
│   ├── dns/         # Domain name management
│   ├── sql/         # Database adapters (MySQL, PostgreSQL)
│   ├── nosql/       # NoSQL adapters (MongoDB, Firestore, Redis)
│   ├── storage/     # File storage (S3, GCS, Azure, local)
│   └── ...
├── core/            # Core infrastructure (cleanup, SSL configuration)
├── config.py        # Configuration system using Pydantic
├── depends.py       # Dependency injection framework
├── debug.py         # Debugging tools and utilities
└── logger.py        # Logging system based on Loguru

tests/               # Test suite with comprehensive coverage
docs/                # Documentation guides
examples/            # Example implementations
```

## Key Technologies

- **Python 3.13+**: Requires the latest Python version for modern features
- **AsyncIO**: Built for high-performance asynchronous operations
- **Pydantic**: For configuration management and type validation
- **Bevy**: Dependency injection framework
- **Loguru**: Structured logging system
- **UV**: Package management and virtual environment tool

## Development Environment

### Prerequisites

- Python 3.13 or later
- UV package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)

### Installation

```bash
# Install ACB with specific adapter dependencies
uv add "acb[cache,sql,storage]"

# Install all adapter dependencies
uv add "acb[all]"
```

### Project Setup

ACB works best with a specific directory structure:

```
myapp/                  # Root project directory
├── myapp/              # Your application package
│   ├── __init__.py     # Makes myapp a Python package
│   ├── actions/        # Directory for your custom actions
│   │   └── __init__.py # Makes actions a subpackage
│   ├── adapters/       # Directory for your custom adapters
│   │   └── __init__.py # Makes adapters a subpackage
│   └── main.py         # Your application entry point
└── settings/           # Configuration directory
    ├── app.yml         # Application settings
    ├── debug.yml       # Debug settings
    └── adapters.yml    # Adapter configuration
```

## Core Components

### 1. Actions

Actions are modular, self-contained utility functions that perform specific tasks:

```python
# Using compression actions
from acb.actions.compress import compress, decompress

# Compress data with brotli
compressed_data = compress.brotli("Hello, ACB!", level=4)

# Decompress it back
original_data = decompress.brotli(compressed_data)

# Using encoding actions
from acb.actions.encode import encode, decode

# Encode data as JSON
json_data = encode.json({"message": "Hello, ACB!"})

# Using hash actions
from acb.actions.hash import hash

# Generate a secure hash
file_hash = hash.blake3(b"file content")
```

### 2. Adapters

Adapters provide standardized interfaces to external systems:

```python
from acb.depends import depends, Inject
from acb.adapters import import_adapter

# Import adapter classes
Cache, Storage = import_adapter()  # Gets the configured cache and storage adapters


# Method 1: Using depends.get() directly
def direct_injection_example():
    # Get instances when you need them
    cache = depends.get()
    storage = depends.get()


# Method 2: Using the @depends.inject decorator (recommended)
@depends.inject
async def process_file(
    filename: str,
    cache: Inject[Cache],  # Injected automatically
    storage: Inject[Storage],  # Injected automatically
):
    # All dependencies are automatically provided
    # Check if file is cached
    content = await cache.get(f"file:{filename}")
    if not content:
        # If not in cache, get from storage
        content = await storage.get_file(filename)
        if content:
            # Store in cache for next time
            await cache.set(f"file:{filename}", content, ttl=3600)
    return content
```

### 3. Configuration

ACB's configuration system is built on Pydantic and supports multiple configuration sources:

```yaml
# settings/app.yml
app:
  name: "MyApp"
  title: "My ACB Application"
  domain: "myapp.example.com"
  version: "0.1.0"

# settings/adapters.yml
cache: memory          # Use in-memory cache
storage: file          # Use file system storage
```

### 4. Dependency Injection

ACB features a simple yet powerful dependency injection system:

```python
from acb.depends import depends, Inject
from acb.config import Config


# Inject dependencies into functions
@depends.inject
async def process_data(
    data: dict[str, Any],
    config: Inject[Config],  # Injected based on type
):
    # Now you can use config without manually creating it
    print(f"Processing data with app: {config.app.name}")
    # Process data...
    return result
```

## Testing

The project uses pytest for testing with comprehensive mocking fixtures:

```bash
# Run all tests
python -m pytest

# Run with verbose output
python -m pytest -v

# Run specific test file
python -m pytest tests/test_config.py
```

Test configuration is defined in `pyproject.toml` and `tests/conftest.py`. Tests use pytest fixtures to mock dependencies and prevent file system operations during testing.

## Building and Running

### Development Commands

```bash
# Run tests
python -m pytest

# Run tests with coverage
python -m pytest --cov=acb

# Run linting
ruff check .

# Run type checking
pyright

# Format code
ruff format .
```

### Production Deployment

For production deployment, ensure:

1. Debug mode is disabled
1. Appropriate adapter implementations are selected
1. Proper resource limits are configured
1. Health checks are implemented

## Common Patterns

### 1. Using Dependency Injection

```python
from acb.depends import depends, Inject
from acb.adapters import import_adapter

# Import adapters
Cache, Storage = import_adapter()


@depends.inject
async def process_file(
    filename: str,
    cache: Inject[Cache],
    storage: Inject[Storage],
):
    # Implementation here
    pass
```

### 2. Working with Configuration

```python
from acb.depends import depends
from acb.config import Config

# Get the configuration
config = depends.get(Config)

# Access standard app settings
app_name = config.app.name
app_version = config.app.version
```

### 3. Using Actions

```python
# Using compression actions
from acb.actions.compress import compress, decompress

# Compress data with brotli
compressed_data = compress.brotli("Hello, ACB!", level=4)

# Using encoding actions
from acb.actions.encode import encode, decode

# Encode data as JSON
json_data = await encode.json({"message": "Hello, ACB!"})
```

## Performance Considerations

1. **Use Connection Pooling**: Most adapters support connection pooling
1. **Implement Caching**: Use cache adapters for frequently accessed data
1. **Lazy Loading**: Initialize expensive resources only when needed
1. **Batch Operations**: Use batch operations when possible
1. **Proper Async Patterns**: Use asyncio.gather() for concurrent operations

## Troubleshooting

Common issues and solutions:

1. **Python Version**: Ensure Python 3.13+ is installed
1. **Dependencies**: Install required adapter dependencies with UV
1. **Configuration**: Check YAML syntax and file structure
1. **Adapter Issues**: Verify adapter configuration in settings/adapters.yml

## Documentation

For more detailed documentation:

- [Main ACB Documentation](./README.md)
- [Core Systems](./acb/README.md)
- [Actions](./acb/actions/README.md)
- [Adapters](./acb/adapters/README.md)
- [Performance Guide](./docs/PERFORMANCE-GUIDE.md)
- [Troubleshooting Guide](./docs/TROUBLESHOOTING.md)
