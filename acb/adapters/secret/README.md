Error - Could not find the file by path /Users/les/Projects/acb/acb/adapters/secret/README.md for qodo_structured_read_files> **ACB Documentation**: [Main](../../../README.md) | [Core Systems](../../README.md) | [Actions](../../actions/README.md) | [Adapters](../README.md) | [Secret](./README.md)

# Secret Adapter

The Secret adapter provides a standardized interface for secure secret management in ACB applications, supporting local and cloud-based secret storage.

## Table of Contents

- [Overview](#overview)
- [Available Implementations](#available-implementations)
- [Installation](#installation)
- [Configuration](#configuration)
- [Basic Usage](#basic-usage)
- [Advanced Usage](#advanced-usage)
  - [Working with Adapter-Specific Secrets](#working-with-adapter-specific-secrets)
  - [Secret Versioning](#secret-versioning)
  - [Batch Operations](#batch-operations)
  - [Integration with ACB Configuration](#integration-with-acb-configuration)
- [Troubleshooting](#troubleshooting)
- [Implementation Details](#implementation-details)
- [Performance Considerations](#performance-considerations)
- [Related Adapters](#related-adapters)
- [Additional Resources](#additional-resources)

## Overview

The ACB Secret adapter offers:

- Secure storage and retrieval of sensitive information
- Support for multiple secret management backends
- Versioning of secrets
- Access control and audit logging
- Seamless integration with ACB configuration system

## Available Implementations

| Implementation | Description | Best For |
|----------------|-------------|----------|
| **Infisical** | Open-source secret management platform | Team-based development |
| **Secret Manager** | Cloud provider secret managers (GCP, AWS, Azure) | Cloud-based applications |

## Installation

```bash
# Install with Secret support
uv add "acb[secret]"

# Or with specific implementation
uv add "acb[infisical]"
uv add "acb[secretmanager]"

# Or include it with other dependencies
uv add "acb[secret,config]"
```

## Configuration

### Settings

Configure the Secret adapter in your `settings/adapters.yml` file:

```yaml
# Use Infisical implementation
secret: infisical

# Or use Secret Manager implementation
secret: secret_manager

# Or disable secret management (fall back to file-based secrets)
secret: null
```

### Secret Settings

The Secret adapter settings can be customized in your `settings/app.yml` file:

```yaml
secret:
  # Required adapters (will ensure these are loaded first)
  requires: ["logger"]

  # Infisical settings
  host: "https://app.infisical.com"  # Infisical host URL
  token: "your-infisical-token"  # API token for authentication
  client_id: "your-client-id"  # Optional: For Universal Auth
  client_secret: "your-client-secret"  # Optional: For Universal Auth
  project_id: "your-project-id"  # Infisical project ID
  environment: "dev"  # Environment (dev, staging, prod, etc.)
  secret_path: "/"  # Path to secrets in Infisical
  cache_ttl: 60  # Cache TTL in seconds

  # Secret Manager settings
  project_id: "my-gcp-project"
  secret_prefix: "myapp"

  # Common settings
  environment: "development"  # or "production", "staging", etc.
  cache_ttl: 300  # seconds to cache secrets
```

## Basic Usage

```python
from acb.depends import depends
from acb.adapters import import_adapter

# Import the Secret adapter
Secret = import_adapter("secret")

# Get the Secret instance via dependency injection
secret = depends.get(Secret)

# Get a secret value
api_key = await secret.get("api_key")
print(f"API Key: {api_key}")

# Create or update a secret
await secret.create("database_password", "secure-password-123")

# Update an existing secret
await secret.update("database_password", "even-more-secure-password-456")

# List available secrets for an adapter
secrets = await secret.list("sql")
for secret_name in secrets:
    print(f"Secret: {secret_name}")

# Delete a secret
await secret.delete("old_api_key")
```

## Advanced Usage

### Infisical-Specific Features

The Infisical adapter provides integration with the Infisical secret management platform:

```python
from acb.depends import depends
from acb.adapters import import_adapter

# Import the Secret adapter (configured to use Infisical)
Secret = import_adapter("secret")
secret = depends.get(Secret)

# Infisical organizes secrets by project, environment, and path
# These are configured in your settings/app.yml file

# Get a secret from the configured project, environment, and path
api_key = await secret.get("api_key")

# Create a secret in the configured project, environment, and path
await secret.create("new_secret", "secret-value")

# List secrets with a specific prefix (e.g., all SQL-related secrets)
sql_secrets = await secret.list("sql")
```

The Infisical adapter supports both token-based authentication and Universal Auth:

```yaml
# Token-based authentication
secret:
  token: "your-infisical-token"
  project_id: "your-project-id"

# OR Universal Auth
secret:
  client_id: "your-client-id"
  client_secret: "your-client-secret"
  project_id: "your-project-id"
```

### Working with Adapter-Specific Secrets

```python
from acb.depends import depends
from acb.adapters import import_adapter

Secret = import_adapter("secret")
secret = depends.get(Secret)

# Get secrets for a specific adapter
db_user = await secret.get("sql.username")
db_password = await secret.get("sql.password")

# Create adapter-specific secrets
await secret.create("smtp.username", "mail_user")
await secret.create("smtp.password", "mail_password")

# Update adapter-specific secrets
await secret.update("storage.access_key", "new-access-key")
```

### Secret Versioning

```python
# Get a specific version of a secret
api_key_v1 = await secret.get("api_key", version="1")
api_key_latest = await secret.get("api_key")  # Gets the latest version

# List versions of a secret
versions = await secret.list_versions("api_key")
for version in versions:
    print(f"Version: {version['version']}, Created: {version['created_at']}")
```

### Batch Operations

```python
# Create multiple secrets at once
secrets = {
    "db_host": "localhost",
    "db_port": "5432",
    "db_user": "postgres",
    "db_password": "secure-password"
}

for key, value in secrets.items():
    await secret.create(f"sql.{key}", value)

# Get multiple secrets
db_config = {}
secret_keys = ["sql.db_host", "sql.db_port", "sql.db_user", "sql.db_password"]

for key in secret_keys:
    short_key = key.split(".")[-1]  # Extract just the last part
    db_config[short_key] = await secret.get(key)

print(f"Host: {db_config['db_host']}, Port: {db_config['db_port']}")
```

### Integration with ACB Configuration

The Secret adapter automatically integrates with the ACB configuration system, allowing for seamless use of secrets in your application:

```python
from acb.depends import depends
from acb.config import Config

# Configuration automatically pulls from secrets when using SecretStr
config = depends.get(Config)

# Access secrets through config
api_key = config.api.key.get_secret_value()
db_password = config.sql.password.get_secret_value()
```

## Troubleshooting

### Common Issues

1. **Authentication Errors**
   - **Problem**: `AuthenticationError: Failed to authenticate with secret manager`
   - **Solution**: Verify your credentials and token validity

2. **Secret Not Found**
   - **Problem**: `SecretNotFoundError: Secret 'api_key' not found`
   - **Solution**: Check that the secret exists and the name is correct

3. **Permission Denied**
   - **Problem**: `PermissionError: Not authorized to access this secret`
   - **Solution**: Verify that your service account or user has appropriate permissions

4. **Secret Provider Unavailable**
   - **Problem**: `ConnectionError: Cannot connect to secret provider`
   - **Solution**: Check network connectivity and service status

## Implementation Details

The Secret adapter implements these core methods:

```python
class SecretBase:
    async def list(self, adapter: str) -> list[str]: ...
    async def create(self, name: str, value: str) -> None: ...
    async def update(self, name: str, value: str) -> None: ...
    async def get(self, name: str, version: Optional[str] = None) -> str: ...
    async def delete(self, name: str) -> None: ...
    async def list_versions(self, name: str) -> list[dict]: ...
```

## Performance Considerations

When working with the Secret adapter, keep these performance factors in mind:

1. **Caching Strategy**:
   - The Secret adapter implements caching to reduce API calls to the secret provider
   - Default cache TTL is configurable in settings (default: 300 seconds)
   - Adjust cache TTL based on your security requirements and access patterns

```yaml
# Configure secret caching in settings/app.yml
secret:
  cache_ttl: 300  # Cache secrets for 5 minutes
```

2. **Implementation Performance**:

| Implementation | Read Latency | Write Latency | Versioning Support | Best For |
|----------------|--------------|---------------|-------------------|----------|
| **Infisical** | Low | Low | Yes | Team development, self-hosted |
| **Secret Manager (GCP)** | Medium | Medium | Yes | GCP deployments, high security |
| **Secret Manager (AWS)** | Medium | Medium | Yes | AWS deployments, high security |
| **Secret Manager (Azure)** | Medium | Medium | Yes | Azure deployments, high security |

3. **Batch Operations**:
   - Group related secrets to minimize API calls
   - Use naming conventions to organize secrets by adapter or function

4. **Secret Size Considerations**:
   - Keep secrets small for better performance
   - For large secrets (e.g., certificates), consider storing references instead
   - Use the Storage adapter for larger sensitive files

5. **Access Patterns**:
   - Load secrets at startup when possible
   - Cache frequently used secrets in memory
   - Implement retry logic for cloud provider rate limits

```python
# Efficient secret loading at startup
class MyService:
    def __init__(self, secret=depends(Secret)):
        # Load secrets once at initialization
        self.api_credentials = await secret.get("api_credentials")
        self.encryption_key = await secret.get("encryption_key")

        # Now use these values throughout the service lifetime
```

## Related Adapters

The Secret adapter works well with these other ACB adapters:

- [**Config Adapter**](../../config/README.md): Use secrets in configuration via SecretStr
- [**SQL Adapter**](../sql/README.md): Store database credentials securely
- [**Storage Adapter**](../storage/README.md): Store cloud storage credentials
- [**Requests Adapter**](../requests/README.md): Secure API keys for external services

Integration example:

```python
# Using Secret and SQL adapters together
from acb.depends import depends
from acb.adapters import import_adapter
from sqlalchemy.ext.asyncio import create_async_engine

Secret = import_adapter("secret")
secret = depends.get(Secret)

async def get_database_connection():
    # Get database credentials from secret manager
    db_user = await secret.get("sql.username")
    db_password = await secret.get("sql.password")
    db_host = await secret.get("sql.host")
    db_name = await secret.get("sql.database")

    # Create connection string
    conn_str = f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}/{db_name}"

    # Create engine with credentials
    engine = create_async_engine(conn_str)
    return engine

# Using Secret and Requests adapters together
Requests = import_adapter("requests")
requests = depends.get(Requests)

async def call_external_api():
    # Get API key from secret manager
    api_key = await secret.get("external_api.key")

    # Use API key in request
    headers = {"Authorization": f"Bearer {api_key}"}
    response = await requests.get(
        "https://api.example.com/data",
        headers=headers
    )

    return response.json()
```

## Additional Resources

- [Infisical Documentation](https://infisical.com/docs/documentation/getting-started/introduction)
- [Google Secret Manager Documentation](https://cloud.google.com/secret-manager/docs)
- [AWS Secrets Manager Documentation](https://docs.aws.amazon.com/secretsmanager/latest/userguide/intro.html)
- [Azure Key Vault Documentation](https://docs.microsoft.com/en-us/azure/key-vault/)
- [OWASP Secrets Management Guide](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [ACB Configuration Documentation](../../README.md#configuration-system)
- [ACB SQL Adapter](../sql/README.md)
- [ACB Storage Adapter](../storage/README.md)
- [ACB Requests Adapter](../requests/README.md)
