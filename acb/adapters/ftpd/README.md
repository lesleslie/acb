**ACB Documentation**: [Main](<../../../README.md>) | [Core Systems](<../../README.md>) | [Actions](<../../actions/README.md>) | [Adapters](<../README.md>) | [FTPD](<./README.md>)

# FTPD Adapter

The FTPD adapter provides a standardized interface for file transfer protocol operations in ACB applications, supporting both FTP (using aioftp) and SFTP (using asyncssh) implementations.

## Overview

The ACB FTPD adapter offers a consistent way to handle file transfers:

- FTP server functionality using aioftp
- SFTP server functionality using asyncssh
- File uploads and downloads
- Directory creation and navigation
- File management (renaming, deleting)
- Support for both standard FTP and secure SFTP
- Asynchronous operations
- Streaming file read/write capabilities

## Available Implementations

| Implementation | Description | Best For |
| -------------- | -------------------------------------------- | ------------------------------------------------------- |
| **FTP** | Standard File Transfer Protocol using aioftp | Basic file transfers, compatibility with legacy systems |
| **SFTP** | SSH File Transfer Protocol using asyncssh | Secure file transfers, modern applications |

## Installation

```bash
# Install with FTPD support
uv add acb --group ftpd

# Or include it with other dependencies
uv add acb --group ftpd --group storage
```

## Configuration

### Settings

Configure the FTPD adapter in your `settings/adapters.yaml` file:

```yaml
# Use FTP implementation
ftpd: ftp

# Or use SFTP implementation
ftpd: sftp

# Or disable FTPD
ftpd: null
```

### FTPD Settings

The FTPD adapter settings can be customized in your `settings/app.yaml` file:

```yaml
ftpd:
  # Common settings
  host: "127.0.0.1"
  port: 8021  # FTP default: 8021, SFTP default: 8022
  max_connections: 42
  username: "ftpuser"
  password: "ftppass"
  anonymous: false
  root_dir: "/tmp/ftp"

  # FTP specific settings
  passive_ports_min: 50000
  passive_ports_max: 50100
  timeout: 30
  use_tls: false
  cert_file: null
  key_file: null

  # SFTP specific settings
  server_host_keys: ["/path/to/ssh_host_key"]
  authorized_client_keys: "/path/to/authorized_keys"
  known_hosts: null
  client_keys: []
```

## Basic Usage

### Starting and Stopping the Server

```python
from acb.depends import depends
from acb.adapters import import_adapter

# Import the FTPD adapter
FTPD = import_adapter("ftpd")

# Get the FTPD instance via dependency injection
ftpd = depends.get(FTPD)

# Start the server
await ftpd.start()

# Stop the server
await ftpd.stop()
```

### File Operations

```python
from pathlib import Path

# Upload a file
await ftpd.upload(Path("/local/path/file.txt"), "/remote/path/file.txt")

# Download a file
await ftpd.download("/remote/path/file.txt", Path("/local/path/file.txt"))

# Read a file as text
content = await ftpd.read_text("/remote/path/file.txt")
print(content)

# Write text to a file
await ftpd.write_text("/remote/path/newfile.txt", "Hello, world!")

# Read a file as bytes
binary_data = await ftpd.read_bytes("/remote/path/image.jpg")

# Write bytes to a file
await ftpd.write_bytes("/remote/path/newimage.jpg", binary_data)

# Check if a file exists
if await ftpd.exists("/remote/path/file.txt"):
    print("File exists!")

# Get file information
file_info = await ftpd.stat("/remote/path/file.txt")
print(f"Name: {file_info.name}, Size: {file_info.size} bytes")

# Delete a file
await ftpd.delete("/remote/path/file.txt")

# Rename a file
await ftpd.rename("/remote/path/oldname.txt", "/remote/path/newname.txt")
```

### Directory Operations

```python
# Create a directory
await ftpd.mkdir("/remote/path/newdir")

# List directory contents
files = await ftpd.list_dir("/remote/path")
for file in files:
    file_type = "Directory" if file.is_dir else "File"
    print(f"{file_type}: {file.name}, Size: {file.size} bytes")

# Remove a directory (non-recursive)
await ftpd.rmdir("/remote/path/emptydir")

# Remove a directory and all its contents (recursive)
await ftpd.rmdir("/remote/path/nonemptydir", recursive=True)
```

## Advanced Usage

### Using the Connect Context Manager

```python
# Use the connect context manager for efficient connection handling
async with ftpd.connect() as client:
    # All operations within this block use the same connection
    await client.mkdir("/remote/path/newdir")
    await client.write_text("/remote/path/newdir/file.txt", "Hello, world!")
    content = await client.read_text("/remote/path/newdir/file.txt")
    print(content)
```

### Custom Authentication

```yaml
# In your settings/app.yaml file:
ftpd:
  username: "custom_user"
  password: "custom_pass"
  anonymous: true  # Allow anonymous access (read-only)
  root_dir: "/path/to/ftp/root"
```

### Recursive Directory Operations

```python
# Copy a directory structure recursively
async def copy_directory(ftpd, source_dir, target_dir):
    # Create the target directory
    await ftpd.mkdir(target_dir)

    # List all files in the source directory
    files = await ftpd.list_dir(source_dir)

    # Process each file/directory
    for file in files:
        source_path = f"{source_dir}/{file.name}"
        target_path = f"{target_dir}/{file.name}"

        if file.is_dir:
            # Recursively copy subdirectories
            await copy_directory(ftpd, source_path, target_path)
        else:
            # Copy files
            content = await ftpd.read_bytes(source_path)
            await ftpd.write_bytes(target_path, content)


# Usage
await copy_directory(ftpd, "/remote/source", "/remote/target")
```

## Troubleshooting

### Common Issues

1. **Connection Refused**

   - **Problem**: `ConnectionRefusedError: Connection refused`
   - **Solution**: Verify server is running and firewall allows connections

1. **Authentication Failed**

   - **Problem**: `AuthenticationError: Login incorrect`
   - **Solution**: Check username and password in configuration

1. **Permission Denied**

   - **Problem**: `PermissionError: Permission denied`
   - **Solution**: Verify user has appropriate permissions on the server

1. **File Not Found**

   - **Problem**: `FileNotFoundError: Remote file not found`
   - **Solution**: Check that the file path is correct and the file exists

## Implementation Details

The FTPD adapter implements these core methods:

```python
class FtpdBase(AdapterBase):
    # Core methods include:
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def upload(self, local_path: Path, remote_path: str) -> None: ...
    async def download(self, remote_path: str, local_path: Path) -> None: ...
    async def list_dir(self, path: str) -> List[FileInfo]: ...
    async def mkdir(self, path: str) -> None: ...
    async def rmdir(self, path: str, recursive: bool = False) -> None: ...
    async def delete(self, path: str) -> None: ...
    async def rename(self, old_path: str, new_path: str) -> None: ...
    async def exists(self, path: str) -> bool: ...
    async def stat(self, path: str) -> FileInfo: ...
    async def read_text(self, path: str) -> str: ...
    async def read_bytes(self, path: str) -> bytes: ...
    async def write_text(self, path: str, content: str) -> None: ...
    async def write_bytes(self, path: str, content: bytes) -> None: ...
    async def connect(self) -> AsyncContextManager[FtpdBase]: ...
```

## Additional Resources

- [aioftp Documentation](https://aioftp.readthedocs.io/)
- [asyncssh Documentation](https://asyncssh.readthedocs.io/)
- [FTP Protocol Documentation](https://tools.ietf.org/html/rfc959)
- [SFTP Protocol Documentation](https://tools.ietf.org/html/draft-ietf-secsh-filexfer-13)
- [ACB Storage Adapter](<../storage/README.md>)
- [ACB Auth Adapter](../auth/README.md)
- [ACB Adapters Overview](<../README.md>)
