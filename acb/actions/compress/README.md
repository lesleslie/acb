> **ACB Documentation**: [Main](../../../README.md) | [Core Systems](../../README.md) | [Actions](../README.md) | [Adapters](../../adapters/README.md)

# Compress Action

The Compress action provides efficient data compression and decompression utilities for the ACB framework. It supports multiple compression algorithms and handles different input types.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Usage](#usage)
  - [Compression](#compression)
  - [Decompression](#decompression)
- [API Reference](#api-reference)
  - [Compress](#compress)
  - [Decompress](#decompress)
- [Examples](#examples)
- [Performance Considerations](#performance-considerations)
- [Related Actions](#related-actions)

## Overview

The Compress action enables efficient data compression and decompression in your applications. It provides a consistent interface for working with different compression algorithms, handling various input types including strings, bytes, and file paths.

## Features

- **Multiple compression algorithms**:
  - Gzip: Standard compression for broad compatibility
  - Brotli: High-compression ratio algorithm, ideal for web assets
- **Flexible input handling**: Process strings, bytes, or file paths
- **Configurable compression levels**: Adjust the balance between speed and compression ratio
- **Asynchronous-friendly**: Works seamlessly with async code

## Usage

Import the compress and decompress utilities from the Compress action:

```python
from acb.actions.compress import compress, decompress
```

### Compression

#### Gzip Compression

```python
# Compress a string using gzip with default compression level (6)
compressed_data = compress.gzip("Hello, ACB!")

# Compress with maximum compression level (9)
max_compressed = compress.gzip("Hello, ACB!", compresslevel=9)

# Compress bytes data
bytes_data = b"Binary data to compress"
compressed_bytes = compress.gzip(bytes_data)

# Compress with a filename (useful for extraction later)
named_compressed = compress.gzip("Hello, ACB!", path="greeting.txt")
```

#### Brotli Compression

```python
# Compress a string using brotli with default quality level (3)
compressed_data = compress.brotli("Hello, ACB!")

# Compress with higher quality level (0-11, with 11 being highest quality)
high_quality = compress.brotli("Hello, ACB!", level=10)

# Compress bytes data
bytes_data = b"Binary data to compress"
compressed_bytes = compress.brotli(bytes_data)
```

### Decompression

#### Gzip Decompression

```python
# Decompress gzipped data
original_data = decompress.gzip(compressed_data)
```

#### Brotli Decompression

```python
# Decompress brotli compressed data
original_data = decompress.brotli(compressed_data)
```

## API Reference

### Compress

#### `compress.gzip`

Compresses content using the gzip algorithm.

```python
def gzip(
    content: str | bytes,
    path: t.Optional[str | Path] = None,
    compresslevel: int = 6,
) -> bytes
```

**Parameters:**
- `content` (str | bytes): The data to compress
- `path` (str | Path, optional): Name of the file the compressed data came from
- `compresslevel` (int, default=6): Compression level (1-9, where 9 is highest compression)

**Returns:**
- `bytes`: The compressed data

#### `compress.brotli`

Compresses data using the Brotli algorithm.

```python
def brotli(data: bytes | str, level: int = 3) -> bytes
```

**Parameters:**
- `data` (bytes | str): The data to compress
- `level` (int, default=3): Compression quality level (0-11, where 11 is highest quality)

**Returns:**
- `bytes`: The compressed data

### Decompress

#### `decompress.gzip`

Decompresses gzipped content.

```python
def gzip(content: Any) -> str
```

**Parameters:**
- `content` (bytes): The compressed data

**Returns:**
- `str`: The decompressed content as a string

#### `decompress.brotli`

Decompresses Brotli-compressed data.

```python
def brotli(data: bytes) -> str
```

**Parameters:**
- `data` (bytes): The compressed data

**Returns:**
- `str`: The decompressed content as a string

## Examples

### Basic Compression and Decompression

```python
from acb.actions.compress import compress, decompress

# Original data
original_text = "This is a test string that will be compressed and then decompressed."

# Compress with gzip
gzipped = compress.gzip(original_text)
print(f"Original size: {len(original_text)} bytes")
print(f"Compressed size (gzip): {len(gzipped)} bytes")

# Decompress
decompressed = decompress.gzip(gzipped)
print(f"Decompressed matches original: {decompressed == original_text}")

# Compress with brotli
brotlied = compress.brotli(original_text)
print(f"Compressed size (brotli): {len(brotlied)} bytes")

# Decompress
decompressed_br = decompress.brotli(brotlied)
print(f"Decompressed matches original: {decompressed_br == original_text}")
```

### Compressing Large Text

```python
from acb.actions.compress import compress, decompress

# Generate large text
large_text = "Lorem ipsum dolor sit amet, " * 1000

# Compare compression algorithms and levels
for algorithm in ["gzip", "brotli"]:
    if algorithm == "gzip":
        for level in [1, 6, 9]:
            compressed = compress.gzip(large_text, compresslevel=level)
            ratio = len(compressed) / len(large_text)
            print(f"gzip (level {level}): {len(compressed)} bytes, {ratio:.2%} of original")
    else:
        for level in [1, 5, 11]:
            compressed = compress.brotli(large_text, level=level)
            ratio = len(compressed) / len(large_text)
            print(f"brotli (level {level}): {len(compressed)} bytes, {ratio:.2%} of original")
```

## Performance Considerations

- **Brotli vs. Gzip**: Brotli generally achieves better compression ratios than gzip, but may be slower for compression (especially at higher quality levels). Decompression is typically faster with Brotli.
- **Compression Levels**: Higher compression levels increase CPU usage and compression time but produce smaller output.
- **Memory Usage**: Very large inputs may require significant memory during compression/decompression operations.
- **Use Cases**:
  - Use Brotli for static content that will be compressed once and decompressed many times
  - Use gzip for general-purpose compression or when compatibility is important
  - Use lower compression levels for real-time applications where speed is critical

## Related Actions

- [Encode/Decode Action](../encode/README.md): Data serialization with formats like JSON, YAML, and MsgPack
- [Hash Action](../hash/README.md): Generate secure hashes and checksums for data integrity
