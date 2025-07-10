# Configuration Documentation

> **ACB Documentation**: [Main](../README.md) | [Core Systems](./README.md) | [Actions](./actions/README.md) | [Adapters](./adapters/README.md)

## Overview

ACB's configuration system is built on [Pydantic](https://pydantic-docs.helpmanual.io/) and [pydantic-settings](https://pydantic-settings.helpmanual.io/) to provide flexible, layered configuration management.

### ACB 0.16.17+ Configuration Changes

Starting with ACB 0.16.17, the configuration system includes significant improvements:

- **Library Usage Mode Detection**: ACB automatically detects when it's being used as a library vs. standalone application
- **Smart Initialization**: Configuration loading is optimized based on usage context
- **Better Error Handling**: Improved configuration loading with better error messages
- **Enhanced Adapter Integration**: Tighter integration between configuration and the new static adapter system

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

## Library vs. Application Usage Modes (ACB 0.16.17+)

ACB now automatically detects how it's being used and adjusts its behavior accordingly:

### Library Usage Mode

When ACB is used as a dependency in another project, it enters "library mode":

```python
# Automatic detection scenarios:
# - ACB installed via pip/pdm in another project
# - Import in setup.py, build scripts, or installation context
# - Used within another package without local ACB development
```

**Library Mode Behavior:**
- Minimal configuration loading
- No automatic settings file creation
- Reduced startup overhead
- Compatible with existing project structures

### Application Usage Mode

When ACB is used as the primary framework for an application:

```python
# Detection scenarios:
# - Running from main module in project root
# - ACB_LIBRARY_MODE environment variable not set
# - settings/ directory exists in current working directory
```

**Application Mode Behavior:**
- Full configuration loading from settings/ directory
- Automatic creation of default configuration files
- Complete adapter system initialization
- Comprehensive error reporting

### Manual Override

You can manually control the usage mode:

```bash
# Force library mode
export ACB_LIBRARY_MODE=true

# Force application mode (unset the variable)
unset ACB_LIBRARY_MODE
```

### Configuration Loading in Different Modes

| Feature | Library Mode | Application Mode |
|---------|-------------|------------------|
| Settings file auto-creation | No | Yes |
| Adapter configuration loading | Minimal | Full |
| Error reporting | Reduced | Comprehensive |
| Startup performance | Fast | Standard |
| Configuration validation | Basic | Full |

## Troubleshooting

### Common Issues

**Missing Configuration Files**: ACB will use defaults if configuration files are missing. In application mode, ACB will create default configuration files automatically.

**Library Mode Detection Issues**: If ACB incorrectly detects library mode when you want application mode, ensure you're running from the project root or set `ACB_LIBRARY_MODE=false`.

**Configuration Loading Errors**: Check that your current working directory has the expected structure for your usage mode.

**Secret Loading Errors**: Check file permissions and YAML syntax in secret files.

**Environment Variable Conflicts**: Use unique prefixes for different settings models.

**Validation Errors**: Review field types and custom validators when configuration fails to load.

### ACB 0.16.17+ Specific Issues

**Adapter Configuration Not Loading**: Ensure you're in application mode if you need full adapter configuration. Check for the presence of `settings/adapters.yml` file.

**Static Mapping Errors**: If you're getting "StaticImportError" exceptions, ensure your adapters are properly registered in the static mapping system.

**Library Integration Problems**: When integrating ACB into an existing project, ensure proper package registration if you're extending ACB with custom adapters.
