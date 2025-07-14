> **ACB Documentation**: [Main](../../../README.md) | [Core Systems](../../README.md) | [Actions](../../actions/README.md) | [Adapters](../README.md) | [Storage](./README.md)

# Storage Adapter

The Storage adapter provides a standardized interface for file and object storage operations in ACB applications, with support for local, in-memory, and cloud storage services.

## Table of Contents

- [Overview](#overview)
- [Available Implementations](#available-implementations)
- [Installation](#installation)
- [Configuration](#configuration)
- [Basic Usage](#basic-usage)
- [Advanced Usage](#advanced-usage)
  - [Working with File Metadata](#working-with-file-metadata)
  - [Generating URLs](#generating-urls)
  - [Listing Files](#listing-files)
  - [Using StorageFile Objects](#using-storagefile-objects)
- [Migration Between Storage Providers](#migration-between-storage-providers)
- [Security Best Practices](#security-best-practices)
- [Troubleshooting](#troubleshooting)
- [Performance Considerations](#performance-considerations)
- [Implementation Details](#implementation-details)
- [Related Adapters](#related-adapters)
- [Additional Resources](#additional-resources)

## Overview

The ACB Storage adapter offers a consistent way to interact with various storage backends:

- Abstract storage operations behind a consistent API
- Support for multiple storage implementations
- Bucket-based organization of files
- Asynchronous operation for non-blocking I/O
- Path-based API familiar to Python developers
- Secure access control to stored files

## Available Implementations

| Implementation | Description | Best For |
|----------------|-------------|----------|
| **File** | Local filesystem storage | Development, simple applications |
| **Memory** | In-memory storage | Testing, ephemeral storage needs |
| **S3** | Amazon S3 or S3-compatible storage | Production, cloud deployments |
| **Cloud Storage** | Google Cloud Storage | GCP deployments |
| **Azure** | Azure Blob Storage | Azure deployments |

## Installation

```bash
# Install with storage support
uv add "acb[storage]"

# With specific cloud provider
uv add "acb[storage,gcp]"  # For Google Cloud Storage
uv add "acb[storage,aws]"  # For Amazon S3
uv add "acb[storage,azure]"  # For Azure Blob Storage

# Or include it with other dependencies
uv add "acb[storage,redis,sql]"
```

## Configuration

### Settings

Configure the storage adapter in your `settings/adapters.yml` file:

```yaml
# Use local filesystem storage
storage: file

# Or use S3 storage
storage: s3

# Or use Google Cloud Storage
storage: cloud_storage

# Or use Azure Blob Storage
storage: azure

# Or use in-memory storage (for testing)
storage: memory
```

### Storage Settings

The storage adapter settings can be customized in your `settings/app.yml` file:

```yaml
storage:
  # Optional prefix for all storage paths
  prefix: "myapp"

  # Path for local storage (for file implementation)
  local_path: "/path/to/storage"

  # Used for billing with cloud providers
  user_project: "my-project-id"

  # Configure buckets
  buckets:
    media: "media-bucket-name"
    documents: "documents-bucket-name"
    logs: "logs-bucket-name"
    test: "test-bucket-name"

  # Cloud-specific settings
  region: "us-east-1"  # For S3
  project_id: "my-gcp-project"  # For GCS
  account_name: "myazureaccount"  # For Azure
```

## Basic Usage

```python
from acb.depends import depends
from acb.adapters import import_adapter
from anyio import Path as AsyncPath

# Import the storage adapter
Storage = import_adapter("storage")

# Get the storage instance via dependency injection
storage = depends.get(Storage)

# Write to a file in the "media" bucket
data = b"Hello, World!"
await storage.media.write(AsyncPath("greeting.txt"), data)

# Read from a file
content = await storage.media.open(AsyncPath("greeting.txt"))
print(content)  # b"Hello, World!"

# Check if a file exists
exists = await storage.media.exists(AsyncPath("greeting.txt"))
print(exists)  # True

# Delete a file
await storage.media.delete(AsyncPath("greeting.txt"))
```

## Advanced Usage

### Working with File Metadata

```python
from acb.depends import depends
from acb.adapters import import_adapter
from anyio import Path as AsyncPath

Storage = import_adapter("storage")
storage = depends.get(Storage)

# Get file statistics
file_path = AsyncPath("documents/report.pdf")
stat = await storage.documents.stat(file_path)
print(f"Size: {stat['size']} bytes")
print(f"Created: {stat['created']}")
print(f"Modified: {stat['modified']}")

# Get file size
size = await storage.documents.get_size(file_path)

# Get creation date
created = await storage.documents.get_date_created(file_path)

# Get last modified date
updated = await storage.documents.get_date_updated(file_path)

# Get file checksum
checksum = await storage.documents.get_checksum(file_path)
```

### Generating URLs

```python
# Get a direct URL to a file
url = storage.media.get_url(AsyncPath("images/logo.png"))
print(f"Direct URL: {url}")

# Generate a signed URL with expiration
signed_url = await storage.media.get_signed_url(
    AsyncPath("private/report.pdf"),
    expires=3600  # URL valid for 1 hour
)
print(f"Signed URL (expires in 1 hour): {signed_url}")
```

### Listing Files

```python
# List all files in a directory
files = await storage.documents.list(AsyncPath("reports/"))

# Process the files
for file_info in files:
    print(f"File: {file_info['name']}, Size: {file_info['size']}")

# Recursively list files with a specific extension
pdf_files = [f for f in await storage.documents.list(AsyncPath("reports/"), recursive=True)
             if f['name'].endswith('.pdf')]
print(f"Found {len(pdf_files)} PDF files")
```

### Using StorageFile Objects

```python
from acb.adapters.storage import StorageFile

# Create a StorageFile object
file = StorageFile(
    name="images/profile.jpg",
    storage=storage.media
)

# Work with the file
print(f"File name: {file.name}")
print(f"File path: {file.path}")

# Get file size
size = await file.size

# Get file checksum
checksum = await file.checksum

# Check if file exists
exists = await file.exists()

# Read file content
content = await file.open()

# Write to file
await file.write(new_content)

# Get a direct URL to the file
url = file.url

# Get a signed URL for temporary access
signed_url = await file.get_signed_url(expires=1800)  # 30 minutes
```

## Migration Between Storage Providers

The Storage adapter makes it easy to migrate files between different storage providers:

```python
from acb.depends import depends
from acb.adapters import import_adapter
from anyio import Path as AsyncPath

# Get access to storage (configured in settings/adapters.yml)
# Note: To use multiple storage adapters, you'd need custom configuration
Storage = import_adapter("storage")

storage = depends.get(Storage)

async def migrate_files(source_path: str, destination_path: str) -> None:
    """Migrate files from S3 to Google Cloud Storage"""
    # List all files in the source path
    files: list[dict[str, t.Any]] = await s3_storage.documents.list(AsyncPath(source_path), recursive=True)

    # Migrate each file
    for file_info in files:
        # Get the relative path
        relative_path = file_info['name'].replace(source_path, '', 1).lstrip('/')

        # Create the destination path
        dest_file_path = AsyncPath(f"{destination_path}/{relative_path}")

        # Read from source
        content = await s3_storage.documents.open(AsyncPath(file_info['name']))

        # Write to destination
        await gcs_storage.documents.write(dest_file_path, content)

        print(f"Migrated {file_info['name']} → {dest_file_path}")

    print(f"Migration complete: {len(files)} files migrated")
```

## Security Best Practices

When working with the Storage adapter, follow these security best practices:

1. **Use Signed URLs** for controlled temporary access to private files
   ```python
   # Generate a short-lived signed URL for download
   signed_url = await storage.documents.get_signed_url(
       AsyncPath("confidential/report.pdf"),
       expires=300  # 5 minutes only
   )
   ```

2. **Validate File Types** before storing user uploads
   ```python
   import magic

   async def save_user_upload(file_data, filename):
       # Check file type using magic numbers
       mime_type = magic.from_buffer(file_data[:2048], mime=True)

       # Allow only specific file types
       allowed_types = ['application/pdf', 'image/jpeg', 'image/png']
       if mime_type not in allowed_types:
           raise ValueError(f"Unsupported file type: {mime_type}")

       # Proceed with storage
       await storage.documents.write(AsyncPath(f"uploads/{filename}"), file_data)
   ```

3. **Implement Access Control** for sensitive files
   ```python
   async def get_document(document_id, user):
       # Check if user has permission to access this document
       if not await user_has_permission(user, document_id):
           raise PermissionError("Access denied")

       # Generate a short-lived URL for authorized access
       return await storage.documents.get_signed_url(
           AsyncPath(f"documents/{document_id}.pdf"),
           expires=60  # 1 minute only
       )
   ```

4. **Use Server-Side Encryption** for sensitive data
   ```python
   # Configure encryption in your app.yml
   # storage:
   #   encryption:
   #     enabled: true
   #     key_id: "my-encryption-key"
   ```

## Troubleshooting

### Common Issues

1. **Authentication Failure with Cloud Storage**
   - **Problem**: `AuthenticationError: Could not authenticate with cloud provider`
   - **Solution**:
     - Check your authentication credentials
     - Ensure the service account has appropriate permissions
     - Verify your environment variables (AWS_ACCESS_KEY_ID, GOOGLE_APPLICATION_CREDENTIALS, etc.)

2. **File Not Found**
   - **Problem**: `FileNotFoundError: File does not exist`
   - **Solution**:
     - Verify the file path and bucket name are correct
     - Check case sensitivity (especially important for S3)
     - Ensure the file hasn't been deleted or moved

3. **Permission Denied**
   - **Problem**: `PermissionError: Not authorized to access this resource`
   - **Solution**:
     - Check your IAM permissions for the storage bucket
     - Verify bucket policies and ACLs
     - Ensure your service account has the correct roles

4. **Bucket Does Not Exist**
   - **Problem**: `BucketNotFoundError: The specified bucket does not exist`
   - **Solution**:
     - Verify the bucket name in your configuration
     - Create the bucket if it doesn't exist
     - Check region specifications (some providers require this)

## Performance Considerations

When working with storage systems, keep these performance factors in mind:

1. **Implementation Performance**:
   | Implementation | Read Speed | Write Speed | Listing Speed | Best For |
   |----------------|------------|------------|---------------|----------|
   | **File** | Fast | Fast | Medium | Local files, development |
   | **Memory** | Very fast | Very fast | Very fast | Testing, small files |
   | **S3** | Medium | Medium | Slow | Production, scalability |
   | **Cloud Storage** | Medium | Medium | Slow | GCP integration |
   | **Azure** | Medium | Medium | Slow | Azure integration |

2. **Optimization Techniques**:
   - **File Chunking**: Break large files into smaller chunks for parallel upload/download
   - **Caching Metadata**: Cache file metadata to avoid repeated stat calls
   - **Bulk Operations**: Use multi-file operations when possible
   - **Compression**: Compress files before storage when appropriate

3. **Implementation Examples**:

```python
# Example: Chunked file upload for large files
async def upload_large_file(local_path, remote_path, chunk_size=8*1024*1024):
    """Upload a large file in chunks for better performance"""
    from aiofile import async_open

    # Get total file size
    local_file = AsyncPath(local_path)
    total_size = await local_file.stat().st_size

    # Prepare upload
    chunks = total_size // chunk_size + (1 if total_size % chunk_size else 0)

    async with async_open(local_path, 'rb') as f:
        for i in range(chunks):
            # Read a chunk
            await f.seek(i * chunk_size)
            chunk = await f.read(chunk_size)

            # Upload this chunk
            chunk_path = f"{remote_path}.part{i}"
            await storage.documents.write(AsyncPath(chunk_path), chunk)

            print(f"Uploaded chunk {i+1}/{chunks} ({len(chunk)} bytes)")

    # Implement provider-specific multipart completion
    # (This is simplified - actual implementation depends on the provider)
    # await storage.documents.complete_multipart(AsyncPath(remote_path), chunks)
```

## Implementation Details

The Storage adapter implements these core methods:

```python
class StorageBucket:
    async def open(self, path: AsyncPath) -> bytes: ...
    async def write(self, path: AsyncPath, data: t.Any) -> None: ...
    async def delete(self, path: AsyncPath) -> None: ...
    async def exists(self, path: AsyncPath) -> bool: ...
    async def stat(self, path: AsyncPath) -> dict[str, t.Any]: ...
    async def list(self, dir_path: AsyncPath) -> list[dict[str, t.Any]]: ...
    async def get_size(self, path: AsyncPath) -> int: ...
    async def get_date_created(self, path: AsyncPath) -> datetime.datetime: ...
    async def get_date_updated(self, path: AsyncPath) -> datetime.datetime: ...
    async def get_checksum(self, path: AsyncPath) -> str: ...
    async def get_signed_url(self, path: AsyncPath, expires: int = 3600) -> str: ...
    def get_url(self, path: AsyncPath) -> str: ...
    def get_path(self, path: AsyncPath) -> str: ...
```

## Related Adapters

The Storage adapter works well with these other ACB adapters:

- [**FTPD Adapter**](../ftpd/README.md): Transfer files between FTP servers and storage
- [**Cache Adapter**](../cache/README.md): Cache file metadata to improve performance
- [**SQL Adapter**](../sql/README.md): Store file metadata in a database
- [**Secret Adapter**](../secret/README.md): Manage credentials for cloud storage providers

Integration example:

```python
# Using Storage and Cache adapters together
async def get_file_with_caching(file_path):
    # Try to get file metadata from cache
    metadata_key = f"file:metadata:{file_path}"
    metadata = await cache.get(metadata_key)

    if not metadata:
        # Cache miss - get from storage
        file_path_obj = AsyncPath(file_path)

        # Get metadata and cache it
        metadata = await storage.documents.stat(file_path_obj)
        await cache.set(metadata_key, metadata, ttl=3600)

    # Get the actual file content (don't cache large files)
    content = await storage.documents.open(AsyncPath(file_path))
    return content, metadata
```

## Additional Resources

- [Amazon S3 Documentation](https://docs.aws.amazon.com/s3/)
- [Google Cloud Storage Documentation](https://cloud.google.com/storage/docs)
- [Azure Blob Storage Documentation](https://docs.microsoft.com/en-us/azure/storage/blobs/)
- [AIOHTTP Documentation](https://docs.aiohttp.org/)
- [ACB FTPD Adapter](../ftpd/README.md)
- [ACB Cache Adapter](../cache/README.md)
- [ACB Adapters Overview](../README.md)
