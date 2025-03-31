> **ACB Documentation**: [Main](../../../README.md) | [Core Systems](../../README.md) | [Actions](../README.md) | [Adapters](../../adapters/README.md)

# Encode Action

The Encode action provides data serialization and deserialization capabilities for the ACB framework, supporting multiple formats including JSON, YAML, TOML, MsgPack, and Pickle.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Usage](#usage)
  - [Encoding Data](#encoding-data)
  - [Decoding Data](#decoding-data)
  - [Working with Files](#working-with-files)
- [API Reference](#api-reference)
  - [Supported Formats](#supported-formats)
  - [Common Parameters](#common-parameters)
- [Examples](#examples)
- [Best Practices](#best-practices)
- [Related Actions](#related-actions)

## Overview

The Encode action simplifies data serialization and deserialization in your applications by providing a consistent interface across multiple formats. It handles the complexities of different serialization libraries and provides convenient methods for encoding and decoding data.

## Features

- **Multiple serialization formats**:
  - JSON: Standard data interchange format
  - YAML: Human-readable configuration format
  - TOML: Configuration file format
  - MsgPack: Binary serialization format
  - Pickle (dill): Python object serialization
- **File operations**: Read from and write to files asynchronously
- **Consistent API**: Similar syntax across all formats
- **Advanced options**: Format-specific options like sorting keys
- **High performance**: Uses msgspec for fast serialization
- **Unicode support**: Proper handling of Unicode characters
- **Type safety**: Reliable serialization of complex data types

## Usage

Import the encoding and decoding utilities from the Encode action:

```python
from acb.actions.encode import encode, decode
# - or -
from acb.actions.encode import dump, load  # Aliases for encode/decode
```

### Encoding Data

Encode a Python object to various formats:

```python
# Sample data
data = {
    "name": "ACB Framework",
    "version": "1.0.0",
    "features": ["actions", "adapters", "dependency injection"],
    "active": True,
    "timestamp": 1632152400
}

# Encode to different formats
json_data = await encode.json(data)
yaml_data = await encode.yaml(data, sort_keys=True)
toml_data = await encode.toml(data)
msgpack_data = await encode.msgpack(data)
pickle_data = await encode.pickle(data)
```

### Decoding Data

Decode serialized data back to Python objects:

```python
# Decode from various formats
json_obj = await decode.json(json_data)
yaml_obj = await decode.yaml(yaml_data)
toml_obj = await decode.toml(toml_data)
msgpack_obj = await decode.msgpack(msgpack_data, use_list=True)
pickle_obj = await decode.pickle(pickle_data)
```

### Working with Files

Read from and write to files using the AsyncPath parameter:

```python
from anyio import Path as AsyncPath

# Save data to files
config_path = AsyncPath("config.yaml")
await encode.yaml(data, path=config_path, sort_keys=True)

# Load data from files
loaded_config = await decode.yaml(config_path)
```

## API Reference

### Supported Formats

| Format | Encoding Method | Decoding Method | Library Used |
|--------|----------------|-----------------|--------------|
| JSON | `encode.json()` | `decode.json()` | msgspec.json |
| YAML | `encode.yaml()` | `decode.yaml()` | msgspec.yaml with enhanced yaml support |
| TOML | `encode.toml()` | `decode.toml()` | msgspec.toml |
| MsgPack | `encode.msgpack()` | `decode.msgpack()` | msgspec.msgpack |
| Pickle | `encode.pickle()` | `decode.pickle()` | dill |

### Common Parameters

#### Encoding Methods

```python
async def encode.format(
    obj: Any,
    path: Optional[AsyncPath] = None,
    sort_keys: bool = False,
    **kwargs
) -> bytes:
```

**Parameters:**
- `obj` (Any): Python object to encode
- `path` (AsyncPath, optional): File path to write encoded data to
- `sort_keys` (bool, default=False): Whether to sort dictionary keys (YAML only)
- `**kwargs`: Format-specific parameters passed to the underlying encoder

**Returns:**
- `bytes`: Encoded data (if path is not provided)

#### Decoding Methods

```python
async def decode.format(
    obj: Union[bytes, str, AsyncPath],
    use_list: bool = False,
    **kwargs
) -> Any:
```

**Parameters:**
- `obj` (bytes/str/AsyncPath): Data to decode or path to read from
- `use_list` (bool, default=False): Use lists instead of tuples for arrays (MsgPack only)
- `**kwargs`: Format-specific parameters passed to the underlying decoder

**Returns:**
- `Any`: Decoded Python object

## Examples

### Complete Serialization Example

```python
from acb.actions.encode import encode, decode
from anyio import Path as AsyncPath
import datetime

# Complex data with various types
data = {
    "name": "Example Project",
    "config": {
        "debug": True,
        "max_connections": 100,
        "timeout": 30.5
    },
    "tags": ["web", "api", "async"],
    "created_at": datetime.datetime.now(),
    "metadata": {
        "author": "ACB User",
        "version": "1.2.3"
    }
}

# Serialize to different formats
async def serialize_example():
    # JSON (compact)
    json_data = await encode.json(data)
    print(f"JSON size: {len(json_data)} bytes")

    # YAML (human-readable with sorted keys)
    yaml_data = await encode.yaml(data, sort_keys=True)
    print(f"YAML size: {len(yaml_data)} bytes")

    # TOML (configuration format)
    toml_data = await encode.toml(data)
    print(f"TOML size: {len(toml_data)} bytes")

    # MsgPack (binary, compact)
    msgpack_data = await encode.msgpack(data)
    print(f"MsgPack size: {len(msgpack_data)} bytes")

    # Save to files
    config_dir = AsyncPath("./config")
    await config_dir.mkdir(exist_ok=True)

    await encode.json(data, path=config_dir / "config.json")
    await encode.yaml(data, path=config_dir / "config.yaml", sort_keys=True)
    await encode.toml(data, path=config_dir / "config.toml")

    # Load back from file
    loaded_json = await decode.json(config_dir / "config.json")
    loaded_yaml = await decode.yaml(config_dir / "config.yaml")
    loaded_toml = await decode.toml(config_dir / "config.toml")

    # Verify data integrity
    assert loaded_json["name"] == data["name"]
    assert loaded_yaml["config"]["max_connections"] == 100
    assert loaded_toml["tags"] == ["web", "api", "async"]
```

### Config File Management

```python
from acb.actions.encode import load, dump
from anyio import Path as AsyncPath

async def update_config(config_path: AsyncPath, updates: dict):
    # Load existing config
    config = await load.yaml(config_path)

    # Update config values
    for section, values in updates.items():
        if section not in config:
            config[section] = {}
        for key, value in values.items():
            config[section][key] = value

    # Save updated config
    await dump.yaml(config, config_path, sort_keys=True)
    return config

# Usage
async def main():
    config_path = AsyncPath("settings.yaml")
    updates = {
        "app": {
            "debug": True,
            "log_level": "DEBUG"
        },
        "server": {
            "port": 8080,
            "workers": 4
        }
    }

    updated_config = await update_config(config_path, updates)
    print("Config updated successfully")
```

## Best Practices

- **Choose the right format for your use case**:
  - JSON: For APIs and data interchange
  - YAML: For configuration files and human readability
  - TOML: For structured configuration files
  - MsgPack: For efficient binary serialization and performance
  - Pickle: For Python-specific object serialization (use cautiously)

- **Security considerations**:
  - Never use `decode.pickle()` with untrusted data as it can execute arbitrary code
  - Prefer JSON or YAML for data from external sources

- **Performance tips**:
  - MsgPack is typically faster and produces smaller output than JSON
  - Set `sort_keys=True` only when needed for YAML human readability
  - For large files, read/write directly to paths rather than loading into memory

- **Error handling**:
  - Always handle potential encoding/decoding errors with try/except blocks
  - Validate data after decoding when working with external sources

## Related Actions

- [Compress Action](../compress/README.md): Compression and decompression utilities
- [Hash Action](../hash/README.md): Generate secure hashes and checksums for data integrity
