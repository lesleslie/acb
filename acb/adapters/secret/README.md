Error - Could not find the file by path /Users/les/Projects/acb/acb/adapters/secret/README.md for qodo_structured_read_files> **ACB Documentation**: [Main](../../../README.md) | [Core Systems](../../README.md) | [Actions](../../actions/README.md) | [Adapters](../README.md) | [Secret](./README.md)

# Secret Adapter

The Secret adapter provides a standardized interface for secure secret management in ACB applications, supporting local and cloud-based secret storage.

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
pdm add "acb[secret]"

# Or with specific implementation
pdm add "acb[infisical]"
pdm add "acb[secretmanager]"

# Or include it with other dependencies
pdm add "acb[secret,config]"
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
  infisical_token: "your-token"
  infisical_url: "https://infisical.example.com"

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

## Additional Resources

- [Infisical Documentation](https://infisical.com/docs/documentation/getting-started/introduction)
- [Google Secret Manager Documentation](https://cloud.google.com/secret-manager/docs)
- [AWS Secrets Manager Documentation](https://docs.aws.amazon.com/secretsmanager/latest/userguide/intro.html)
- [Azure Key Vault Documentation](https://docs.microsoft.com/en-us/azure/key-vault/)
- [ACB Configuration Documentation](../../README.md#configuration-system)
