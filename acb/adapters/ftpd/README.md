Error - Could not find the file by path /Users/les/Projects/acb/acb/adapters/ftpd/README.md for qodo_structured_read_files> **ACB Documentation**: [Main](../../../README.md) | [Core Systems](../../README.md) | [Actions](../../actions/README.md) | [Adapters](../README.md) | [FTPD](./README.md)

# FTPD Adapter

The FTPD adapter provides a standardized interface for file transfer protocol operations in ACB applications, supporting both FTP and SFTP implementations.

## Overview

The ACB FTPD adapter offers a consistent way to handle file transfers:

- File uploads and downloads
- Directory creation and navigation
- File management (renaming, deleting)
- Support for both standard FTP and secure SFTP
- Asynchronous operations

## Available Implementations

| Implementation | Description | Best For |
|----------------|-------------|----------|
| **FTP** | Standard File Transfer Protocol | Basic file transfers |
| **SFTP** | SSH File Transfer Protocol | Secure file transfers |

## Installation

```bash
# Install with FTPD support
pdm add "acb[ftpd]"

# Or include it with other dependencies
pdm add "acb[ftpd,storage]"
```

## Configuration

### Settings

Configure the FTPD adapter in your `settings/adapters.yml` file:

```yaml
# Use FTP implementation
ftpd: ftp

# Or use SFTP implementation
ftpd: sftp

# Or disable FTPD
ftpd: null
```

### FTPD Settings

The FTPD adapter settings can be customized in your `settings/app.yml` file:

```yaml
ftpd:
  # Server port
  port: 8021

  # Maximum concurrent connections
  max_connections: 42

  # Host
  host: "127.0.0.1"

  # Credentials
  username: "ftpuser"
  password: "secure-password"

  # Root directory
  root_dir: "/var/ftp"

  # SSL/TLS settings (for secure connections)
  use_tls: true
  cert_file: "/path/to/cert.pem"
  key_file: "/path/to/key.pem"
```

## Basic Usage

```python
from acb.depends import depends
from acb.adapters import import_adapter
from aiopath import AsyncPath

# Import the FTPD adapter
FTPD = import_adapter("ftpd")

# Get the FTPD instance via dependency injection
ftpd = depends.get(FTPD)

# Upload a file
local_file = AsyncPath("local_document.pdf")
remote_path = "documents/document.pdf"
await ftpd.upload(local_file, remote_path)

# Download a file
downloaded_file = AsyncPath("downloaded_document.pdf")
await ftpd.download(remote_path, downloaded_file)

# List directory contents
files = await ftpd.list_dir("documents")
for file in files:
    print(f"File: {file.name}, Size: {file.size}")

# Delete a file
await ftpd.delete(remote_path)
```

## Advanced Usage

### Directory Operations

```python
from acb.depends import depends
from acb.adapters import import_adapter

FTPD = import_adapter("ftpd")
ftpd = depends.get(FTPD)

# Create a directory
await ftpd.mkdir("reports/2023")

# Check if a directory exists
exists = await ftpd.exists("reports/2023")

# List subdirectories
directories = await ftpd.list_dirs("reports")

# Remove a directory (and contents)
await ftpd.rmdir("reports/2022", recursive=True)
```

### File Operations

```python
# Get file information
file_info = await ftpd.stat("documents/report.pdf")
print(f"Size: {file_info.size}")
print(f"Modified: {file_info.mtime}")
print(f"Permissions: {file_info.permissions}")

# Move/rename a file
await ftpd.rename("old_path.txt", "new_path.txt")

# Check if a file exists
exists = await ftpd.exists("documents/report.pdf")

# Get file contents as string
content = await ftpd.read_text("config.json")

# Get file contents as bytes
binary_content = await ftpd.read_bytes("image.png")
```

### Batch Operations

```python
# Batch upload multiple files
files = [
    ("local1.txt", "remote/path1.txt"),
    ("local2.txt", "remote/path2.txt"),
    ("local3.txt", "remote/path3.txt")
]

async with ftpd.connect() as client:
    for local_path, remote_path in files:
        await client.upload(local_path, remote_path)
```

## Troubleshooting

### Common Issues

1. **Connection Refused**
   - **Problem**: `ConnectionRefusedError: Connection refused`
   - **Solution**: Verify server is running and firewall allows connections

2. **Authentication Failed**
   - **Problem**: `AuthenticationError: Login incorrect`
   - **Solution**: Check username and password in configuration

3. **Permission Denied**
   - **Problem**: `PermissionError: Permission denied`
   - **Solution**: Verify user has appropriate permissions on the server

4. **File Not Found**
   - **Problem**: `FileNotFoundError: Remote file not found`
   - **Solution**: Check that the file path is correct and the file exists

## Implementation Details

The FTPD adapter implements these core methods:

```python
class FtpdBase:
    async def connect(self) -> Any: ...
    async def upload(self, local_path: AsyncPath, remote_path: str) -> None: ...
    async def download(self, remote_path: str, local_path: AsyncPath) -> None: ...
    async def list_dir(self, path: str) -> list[FileInfo]: ...
    async def mkdir(self, path: str) -> None: ...
    async def rmdir(self, path: str, recursive: bool = False) -> None: ...
    async def delete(self, path: str) -> None: ...
    async def rename(self, old_path: str, new_path: str) -> None: ...
    async def exists(self, path: str) -> bool: ...
    async def stat(self, path: str) -> FileInfo: ...
    async def read_text(self, path: str) -> str: ...
    async def read_bytes(self, path: str) -> bytes: ...
```

## Additional Resources

- [FTP Protocol Documentation](https://tools.ietf.org/html/rfc959)
- [SFTP Protocol Documentation](https://tools.ietf.org/html/draft-ietf-secsh-filexfer-13)
- [ACB Adapters Overview](../README.md)
