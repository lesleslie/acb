> **ACB Documentation**: [Main](../../../README.md) | [Core Systems](../../README.md) | [Actions](../README.md) | [Adapters](../../adapters/README.md)

# Hash Action

The Hash action provides secure hashing functions for data integrity and checksum verification in ACB applications, supporting multiple algorithms and input types.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Usage](#usage)
  - [Basic Hashing](#basic-hashing)
  - [File Hashing](#file-hashing)
  - [Checksum Verification](#checksum-verification)
- [API Reference](#api-reference)
  - [blake3](#blake3)
  - [crc32c](#crc32c)
  - [md5](#md5)
- [Examples](#examples)
- [Security Considerations](#security-considerations)
- [Performance Comparison](#performance-comparison)
- [Related Actions](#related-actions)

## Overview

The Hash action provides cryptographic hash functions and checksums for ensuring data integrity, verifying file contents, and generating unique identifiers. It offers a consistent interface for working with different hashing algorithms and handles various input types including strings, bytes, and file paths.

## Features

- **Multiple hashing algorithms**:
  - BLAKE3: Modern, high-performance cryptographic hash
  - CRC32C: Fast checksum algorithm (Google's implementation)
  - MD5: Legacy hash function for compatibility
- **Flexible input handling**: Hash strings, bytes, dictionaries, or file paths
- **Asynchronous operations**: Non-blocking file hashing
- **Consistent output formats**: Hexadecimal string or integer output
- **Streaming capability**: Efficiently hash large files without loading them entirely into memory

## Usage

Import the hash utility from the Hash action:

```python
from acb.actions.hash import hash
```

### Basic Hashing

```python
# Hash a string using BLAKE3 (default algorithm)
text = "Hash this text"
hash_value = await hash.blake3(text)
print(hash_value)  # Returns a hexadecimal string

# Hash a dictionary
data = {"user": "john", "id": 12345, "active": True}
data_hash = await hash.blake3(data)
print(data_hash)

# Hash bytes
bytes_data = b"Binary data to hash"
bytes_hash = await hash.blake3(bytes_data)
print(bytes_hash)
```

### File Hashing

```python
from anyio import Path as AsyncPath

# Hash a file using BLAKE3
file_path = AsyncPath("document.pdf")
file_hash = await hash.blake3(file_path)
print(file_hash)  # Returns the hash of the file's contents

# Hash a file using CRC32C (useful for Google Cloud Storage)
file_crc = await hash.crc32c(file_path)
print(file_crc)  # Returns an integer
```

### Checksum Verification

```python
from anyio import Path as AsyncPath

# Calculate file hash
file_path = AsyncPath("downloaded_file.zip")
calculated_hash = await hash.blake3(file_path)

# Compare with expected hash
expected_hash = "7d70c6d3..."
if calculated_hash == expected_hash:
    print("File integrity verified")
else:
    print("File may be corrupted or tampered with")
```

## API Reference

### blake3

Generates a BLAKE3 hash for the given object.

```python
async def blake3(obj: Union[str, bytes, dict, AsyncPath]) -> str
```

**Parameters:**
- `obj` (str | bytes | dict | AsyncPath): The object to hash

**Returns:**
- `str`: Hexadecimal string representation of the hash

### crc32c

Calculates a CRC32C checksum for the given object.

```python
async def crc32c(obj: Union[str, bytes, dict, AsyncPath]) -> int
```

**Parameters:**
- `obj` (str | bytes | dict | AsyncPath): The object to hash

**Returns:**
- `int`: Integer representation of the CRC32C checksum

### md5

Generates an MD5 hash for the given object.

```python
async def md5(obj: Union[str, bytes, dict, AsyncPath]) -> str
```

**Parameters:**
- `obj` (str | bytes | dict | AsyncPath): The object to hash

**Returns:**
- `str`: Hexadecimal string representation of the hash

## Examples

### Hashing Different Data Types

```python
from acb.actions.hash import hash

async def hash_examples():
    # String hashing
    text = "The quick brown fox jumps over the lazy dog"
    blake3_hash = await hash.blake3(text)
    crc32c_hash = await hash.crc32c(text)
    md5_hash = await hash.md5(text)

    print(f"BLAKE3: {blake3_hash}")
    print(f"CRC32C: {crc32c_hash}")
    print(f"MD5: {md5_hash}")

    # Dictionary hashing
    user_data = {
        "id": 12345,
        "name": "John Doe",
        "email": "john@example.com",
        "roles": ["admin", "user"]
    }

    data_hash = await hash.blake3(user_data)
    print(f"Data hash: {data_hash}")
```

### File Integrity Verification

```python
from acb.actions.hash import hash
from anyio import Path as AsyncPath

async def verify_file_integrity(file_path: str, expected_hash: str) -> bool:
    """Verify file integrity using BLAKE3 hash."""
    path = AsyncPath(file_path)

    if not await path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    actual_hash = await hash.blake3(path)

    if actual_hash == expected_hash:
        print(f"✅ File integrity verified: {file_path}")
        return True
    else:
        print(f"❌ File integrity check failed: {file_path}")
        print(f"  Expected: {expected_hash}")
        print(f"  Actual:   {actual_hash}")
        return False
```

### Batch File Hashing

```python
from acb.actions.hash import hash
from anyio import Path as AsyncPath
import asyncio

async def batch_hash_files(directory: str, algorithm: str = "blake3") -> dict:
    """Generate hashes for all files in a directory."""
    dir_path = AsyncPath(directory)
    results = {}

    if not await dir_path.exists() or not await dir_path.is_dir():
        raise ValueError(f"Invalid directory: {directory}")

    hash_func = getattr(hash, algorithm.lower())

    async def hash_file(file_path):
        file_hash = await hash_func(file_path)
        return file_path.name, file_hash

    tasks = []
    async for file_path in dir_path.glob("*"):
        if await file_path.is_file():
            tasks.append(hash_file(file_path))

    file_hashes = await asyncio.gather(*tasks)
    results = dict(file_hashes)

    return results
```

## Security Considerations

- **Algorithm Selection**:
  - BLAKE3: Recommended for security-critical applications
  - CRC32C: Suitable for checksums but not for cryptographic security
  - MD5: Not recommended for security purposes due to known vulnerabilities

- **Use Cases**:
  - File integrity verification: BLAKE3
  - Cloud storage checksums: CRC32C (compatible with Google Cloud Storage)
  - Legacy system compatibility: MD5

- **Security Levels**:
  | Algorithm | Security Level | Collision Resistance | Performance |
  |-----------|---------------|---------------------|-------------|
  | BLAKE3    | High          | Strong              | Very Fast   |
  | CRC32C    | Low           | Weak                | Fastest     |
  | MD5       | Very Low      | Broken              | Fast        |

## Performance Comparison

The Hash action's algorithms have different performance characteristics:

- **BLAKE3**: Extremely fast modern hash function, often faster than MD5 despite stronger security
- **CRC32C**: Fastest option, optimized for hardware acceleration on modern CPUs
- **MD5**: Fast but outdated hash function

Approximate performance for 1GB of data on modern hardware:

| Algorithm | Processing Speed | Relative Speed |
|-----------|-----------------|---------------|
| BLAKE3    | ~5-10 GB/s      | Very Fast     |
| CRC32C    | ~20 GB/s        | Fastest       |
| MD5       | ~1-2 GB/s       | Fast          |

## Related Actions

- [Compress Action](../compress/README.md): Compression and decompression utilities
- [Encode Action](../encode/README.md): Data serialization with formats like JSON, YAML, and MsgPack
