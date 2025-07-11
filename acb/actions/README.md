> **ACB Documentation**: [Main](../../README.md) | [Core Systems](../README.md) | [Actions](./README.md) | [Adapters](../adapters/README.md)

# ACB: Actions

Actions are modular, self-contained utility functions that perform specific tasks in the ACB framework. They are automatically discovered and registered, making them immediately available throughout your application.

## Table of Contents

- [Overview](#overview)
- [Available Actions](#available-actions)
  - [Compress/Decompress](#compressdecompress)
  - [Encode/Decode](#encodedecode)
  - [Hash](#hash)
- [Creating Custom Actions](#creating-custom-actions)
- [Adapter-Agnostic Design](#adapter-agnostic-design)
- [Action Registration](#action-registration)
- [Best Practices](#best-practices)

## Overview

ACB actions provide utility functions for common operations like compression, serialization, and hashing. They are:

- **Self-contained**: Each action focuses on a specific functionality
- **Auto-registered**: Discovered and registered automatically
- **Easily extendable**: Add your own actions in your project
- **Consistently structured**: Similar patterns across all actions
- **Adapter-agnostic**: Actions avoid direct adapter imports and use dynamic adapter access when needed

## Available Actions

ACB comes with several built-in actions for common tasks:

| Action | Description | Methods |
|--------|-------------|---------|
| **Compress/Decompress** | Data compression utilities | `compress.gzip()`, `compress.brotli()`, `decompress.gzip()`, `decompress.brotli()` |
| **Encode/Decode** | Data serialization | `encode.json()`, `encode.yaml()`, `encode.toml()`, `encode.msgpack()`, `encode.pickle()` and corresponding decode methods |
| **Hash** | Secure hashing functions | `hash.blake3()`, `hash.crc32c()`, `hash.md5()` |

### Compress/Decompress

Efficient data compression and decompression utilities.

#### Available Methods:

**Compress:**
- `compress.gzip(content, path=None, compresslevel=6)`: Compress content using gzip
- `compress.brotli(data, level=3)`: Compress data using brotli algorithm

**Decompress:**
- `decompress.gzip(content)`: Decompress gzip content
- `decompress.brotli(data)`: Decompress brotli content

#### Usage Example:

```python
from acb.actions.compress import compress, decompress

# Compress some text data using brotli
text = "Hello, ACB! This is a test string that will be compressed."
compressed = compress.brotli(text, level=3)

# Decompress back to the original text
original = decompress.brotli(compressed)
print(original)  # "Hello, ACB! This is a test string that will be compressed."

# Compress using gzip
gzipped = compress.gzip("Hello, ACB!", compresslevel=9)

# Decompress gzip content
original_gzip = decompress.gzip(gzipped)
```

### Encode/Decode

Data serialization and deserialization with multiple formats.

#### Available Formats:

- **JSON**: Fast JSON encoding/decoding
- **YAML**: YAML serialization with Unicode support
- **TOML**: TOML configuration format
- **MsgPack**: Efficient binary serialization
- **Pickle** (using dill): Python object serialization

#### Usage Example:

```python
from acb.actions.encode import encode, decode
from anyio import Path as AsyncPath
import typing as t

async def example_usage() -> dict[str, t.Any]:
    # Sample data
    data: dict[str, t.Any] = {
        "name": "ACB Framework",
        "version": "1.0.0",
        "features": ["actions", "adapters", "dependency injection"],
        "active": True,
        "timestamp": 1632152400
    }

    # Encode to various formats
    json_data: str = await encode.json(data)
    yaml_data: str = await encode.yaml(data, sort_keys=True)
    msgpack_data: bytes = await encode.msgpack(data)
    toml_data: str = await encode.toml(data)
    pickle_data: bytes = await encode.pickle(data)

    # Decode from various formats
    json_decoded: dict[str, t.Any] = await decode.json(json_data)
    yaml_decoded: dict[str, t.Any] = await decode.yaml(yaml_data)
    msgpack_decoded: dict[str, t.Any] = await decode.msgpack(msgpack_data, use_list=True)
    toml_decoded: dict[str, t.Any] = await decode.toml(toml_data)
    pickle_decoded: dict[str, t.Any] = await decode.pickle(pickle_data)

    # You can also save directly to a file using AsyncPath
    path = AsyncPath("config.json")
    await encode.json(data, path=path)

    # And load from a file
    loaded_data: dict[str, t.Any] = await decode.json(path)
    return loaded_data
```

### Hash

Secure hashing functions for data integrity and checksum verification.

#### Available Methods:

- `hash.blake3(obj)`: Fast cryptographic hash function
- `hash.crc32c(obj)`: CRC32C checksum (Google's implementation)
- `hash.md5(obj)`: MD5 hash (note: not recommended for security-critical applications)

#### Usage Example:

```python
from acb.actions.hash import hash
from anyio import Path as AsyncPath
import typing as t

async def hash_examples() -> dict[str, str]:
    # Hash a string
    text = "Hash this text"
    blake3_hash: str = await hash.blake3(text)
    print(blake3_hash)  # Returns a hexadecimal string

    # Hash a file
    file_path = AsyncPath("document.pdf")
    file_hash: str = await hash.blake3(file_path)
    print(file_hash)  # Returns the hash of the file's contents

    # Get CRC32C checksum (useful for Google Cloud Storage)
    crc: str = await hash.crc32c("Checksum this")
    print(crc)  # Returns a hexadecimal string

    # Get MD5 hash (when compatibility is needed)
    md5sum: str = await hash.md5("Legacy hash")
    print(md5sum)  # Returns a hexadecimal string

    return {
        "blake3": blake3_hash,
        "crc32c": crc,
        "md5": md5sum
    }
```

## Creating Custom Actions

You can extend ACB with your own actions. Actions are automatically discovered and registered when you place them in your application's `actions` directory.

### Basic Structure

A typical action module follows this structure:

```python
from pydantic import BaseModel

# Define your action class
class MyAction(BaseModel):
    @staticmethod
    def method1(param1, param2):
        """Documentation for this method"""
        # Implementation
        return result

    @staticmethod
    def method2(param):
        """Documentation for this method"""
        # Implementation
        return result

# Export an instance of your action
my_action = MyAction()
```

### Example: Creating a Validate Action

Here's an example of creating a custom validation action:

```python
# myapp/actions/validate.py
from pydantic import BaseModel
import re
import typing as t

class Validate(BaseModel):
    @staticmethod
    def email(email: str) -> bool:
        """Validate an email address"""
        pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
        return bool(pattern.match(email))

    @staticmethod
    def url(url: str) -> bool:
        """Validate a URL"""
        pattern = re.compile(r"^(http|https)://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(/.*)?$")
        return bool(pattern.match(url))

    @staticmethod
    def phone(phone: str) -> bool:
        """Validate a phone number"""
        # Remove common separators
        cleaned = re.sub(r"[\s\-\(\)\.]+", "", phone)
        # Check for international or local format
        pattern = re.compile(r"^(\+\d{1,3})?(\d{10,15})$")
        return bool(pattern.match(cleaned))

# Export an instance
validate = Validate()
```

## Adapter-Agnostic Design

Actions in ACB follow an **adapter-agnostic design philosophy**. This means actions should be designed to work independently of specific adapter implementations while still being able to interact with adapters when necessary.

### Core Principles

1. **Avoid Direct Adapter Imports**: Actions should not import adapters directly using `from acb.adapters import X`
2. **Use Dynamic Adapter Access**: When adapter functionality is needed, use `depends.get()` for dynamic access
3. **Depend on Protocol Interfaces**: When possible, depend on protocol interfaces rather than concrete adapter implementations
4. **Keep Actions Pure**: Prefer pure utility functions that don't require external dependencies

### When Actions Need Adapters

When an action needs to interact with adapters, use dynamic imports via the dependency injection system:

```python
from acb.depends import depends
from pydantic import BaseModel
import typing as t

class FileAction(BaseModel):
    @staticmethod
    async def process_file(filename: str, data: bytes) -> dict[str, t.Any]:
        """Process and store a file using dynamic adapter access."""

        # Dynamic adapter access - adapter-agnostic approach
        try:
            storage = depends.get("storage")
            cache = depends.get("cache")

            # Process the file
            processed_data = await storage.put_file(filename, data)

            # Cache the result
            cache_key = f"file_process:{filename}"
            await cache.set(cache_key, processed_data, ttl=3600)

            return {
                "filename": filename,
                "size": len(data),
                "cached": True,
                "storage_path": processed_data.get("path")
            }
        except Exception as e:
            # Graceful fallback when adapters aren't available
            return {
                "filename": filename,
                "size": len(data),
                "cached": False,
                "error": str(e)
            }

# Export instance
file_action = FileAction()
```

### Protocol-Based Interfaces

When creating actions that work with multiple adapter types, define and use protocol interfaces:

```python
from typing import Protocol
from acb.depends import depends

class StorageProtocol(Protocol):
    async def put_file(self, filename: str, data: bytes) -> dict[str, t.Any]: ...
    async def get_file(self, filename: str) -> bytes: ...

class CloudAction(BaseModel):
    @staticmethod
    async def backup_data(data: bytes, filename: str) -> dict[str, t.Any]:
        """Backup data using any storage adapter that implements StorageProtocol."""

        # Get storage adapter dynamically
        storage: StorageProtocol = depends.get("storage")

        # Use protocol interface - works with any compatible adapter
        result = await storage.put_file(f"backup/{filename}", data)

        return {
            "backup_created": True,
            "backup_path": result.get("path"),
            "size": len(data)
        }
```

### Benefits of Adapter-Agnostic Design

- **Flexibility**: Actions work with different adapter implementations
- **Testability**: Actions can be tested independently of specific adapters
- **Maintainability**: Changes to adapters don't break actions
- **Reusability**: Actions can be used across different projects and configurations
- **Cloud Portability**: Switch between cloud providers without changing action code

## Action Registration

Actions are registered automatically when your application starts. The `register_actions()` function in `acb/actions/__init__.py` scans the actions directory and registers each action module.

You don't need to manually register actions — simply create your action module in the appropriate directory and ACB will handle the rest.

## Best Practices

Here are recommended best practices for creating and using actions:

### Design Principles

1. **Keep Actions Focused**: Each action should do one thing well
2. **Prefer Pure Functions**: Create stateless utility functions when possible
3. **Follow Adapter-Agnostic Design**: Avoid direct adapter imports; use `depends.get()` for dynamic access
4. **Use Protocol Interfaces**: Depend on protocol interfaces rather than concrete adapter implementations

### Code Quality

5. **Document Methods**: Include docstrings for all methods explaining parameters and return values
6. **Provide Type Hints**: Use Python type hints to improve code clarity and editor support
7. **Make Methods Static**: Action methods should typically be stateless and static
8. **Handle Exceptions**: Properly handle and document potential exceptions

### Performance and Architecture

9. **Consider Async**: Use async methods for I/O operations to maintain non-blocking behavior
10. **Use Consistent Naming**: Follow naming conventions across all action modules
11. **Add Validation**: Validate inputs to avoid unexpected behavior
12. **Graceful Degradation**: When adapters aren't available, provide meaningful fallbacks

### Adapter Integration

13. **Dynamic Adapter Access**: Use `depends.get("adapter_name")` instead of direct imports
14. **Error Handling for Missing Adapters**: Handle cases where required adapters aren't registered
15. **Protocol Compliance**: Ensure adapter dependencies follow established protocol interfaces
16. **Minimize Adapter Dependencies**: Keep actions functional even when adapters are unavailable

## Related Resources

- [Core Systems Documentation](../README.md)
- [Adapters Documentation](../adapters/README.md)
- [Main ACB Documentation](../../README.md)
