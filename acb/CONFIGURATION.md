# Configuration Documentation

> **ACB Documentation**: [Main](../README.md) | [Core Systems](./README.md) | [Actions](./actions/README.md) | [Adapters](./adapters/README.md)

## Overview

ACB's configuration system is built on [Pydantic](https://pydantic-docs.helpmanual.io/) and [pydantic-settings](https://pydantic-settings.helpmanual.io/) to provide flexible, layered configuration management.

## Configuration Sources

The configuration system aggregates settings from multiple sources in order of precedence:

1. **Initialization Parameters**: Passed during application startup
2. **YAML Configuration Files**: Settings from `settings/` directory
3. **File-based Secrets**: Managed secrets from `settings/secrets/`
4. **External Secret Managers**: Integration with cloud secret services

## Settings Files Structure

```
settings/
├── app.yml          # Application-wide settings
├── debug.yml        # Debug configuration
├── adapters.yml     # Adapter implementation selection
└── secrets/         # Secret files (gitignored)
    ├── api_keys.yml
    └── database.yml
```

## Core Settings Models

### AppSettings

Defines application-wide configuration:

```python
from acb.config import Settings

class AppSettings(Settings):
    name: str = "MyApp"
    title: str = "My Application"
    version: str = "1.0.0"
    domain: str = "localhost"
    platform: Platform = Platform.gcp
    secret_key: SecretStr = SecretStr("")
    secure_salt: SecretStr = SecretStr("")
```

### DebugSettings

Controls debugging behavior:

```python
class DebugSettings(Settings):
    enabled: bool = True
    production: bool = False
    log_level: str = "DEBUG"
    secrets: bool = False
    logging: bool = True
```

## Configuration Usage

### Accessing Configuration

```python
from acb.depends import depends
from acb.config import Config

@depends.inject
async def my_function(config: Config = depends()):
    app_name = config.app.name
    debug_enabled = config.debug.enabled
    cache_ttl = config.cache.default_ttl
```

### Environment-Specific Configuration

Create environment-specific files:

```yaml
# settings/app.yml (development)
app:
  name: "MyApp-Dev"
  domain: "localhost:8000"

# settings/production/app.yml (production)
app:
  name: "MyApp"
  domain: "myapp.com"
```

## Secret Management

### File-based Secrets

Store sensitive data in `settings/secrets/`:

```yaml
# settings/secrets/database.yml
database:
  password: "super_secret_password"
  api_key: "secret_api_key"
```

### External Secret Managers

Configure cloud secret management:

```yaml
# settings/adapters.yml
secret: secret_manager  # or: infisical

# settings/app.yml
secret:
  project_id: "my-gcp-project"
  secret_names:
    - "database-password"
    - "api-keys"
```

## Advanced Configuration

### Custom Settings Models

Create domain-specific settings:

```python
from acb.config import Settings
from pydantic import SecretStr

class DatabaseSettings(Settings):
    host: str = "localhost"
    port: int = 5432
    username: str = "postgres"
    password: SecretStr = SecretStr("")
    database: str = "myapp"

    class Config:
        env_prefix = "DB_"  # DB_HOST, DB_PORT, etc.

class ApiSettings(Settings):
    base_url: str = "https://api.example.com"
    timeout: int = 30
    api_key: SecretStr = SecretStr("")
```

### Configuration Validation

```python
from pydantic import field_validator

class MySettings(Settings):
    port: int = 8000

    @field_validator('port')
    @classmethod
    def validate_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError('Port must be between 1 and 65535')
        return v
```

## Best Practices

1. **Use SecretStr for sensitive data** to prevent accidental logging
2. **Provide sensible defaults** for all configuration values
3. **Use environment prefixes** to avoid variable name conflicts
4. **Validate critical settings** with custom validators
5. **Keep secrets out of version control** using `.gitignore`
6. **Use environment-specific configurations** for different deployment stages
7. **Document all configuration options** with clear descriptions

## Troubleshooting

### Common Issues

**Missing Configuration Files**: ACB will use defaults if configuration files are missing.

**Secret Loading Errors**: Check file permissions and YAML syntax in secret files.

**Environment Variable Conflicts**: Use unique prefixes for different settings models.

**Validation Errors**: Review field types and custom validators when configuration fails to load.
