> **ACB Documentation**: [Main](../../../README.md) | [Core Systems](../../README.md) | [Actions](../../actions/README.md) | [Adapters](../README.md) | [App](./README.md)

# App Adapter

The App adapter provides core application management capabilities for ACB applications, handling bootstrapping, configuration, and lifecycle management.

## Overview

The ACB App adapter serves as the central coordination point for your application:

- Application initialization and bootstrapping
- Configuration loading and validation
- Application lifecycle management
- Environment detection (development vs. production)
- Integration with other ACB components

## Available Implementations

| Implementation | Description | Best For |
|----------------|-------------|----------|
| **Main** | Default application adapter | Most applications |

## Installation

The App adapter is automatically included with the core ACB installation:

```bash
# Install ACB (includes the App adapter)
pdm add acb
```

## Configuration

### Settings

The App adapter is typically enabled by default in your `settings/adapters.yml` file:

```yaml
# Use the default App implementation
app: main
```

### App Settings

The App adapter settings can be customized in your `settings/app.yml` file:

```yaml
app:
  # Application name (used for databases, logging, etc.)
  name: "myapp"

  # Application title (human-readable)
  title: "My Application"

  # Domain name
  domain: "example.com"

  # Platform identifier
  platform: "web"

  # Application version
  version: "1.0.0"

  # Secret key for encryption (automatically generated if not provided)
  secret_key: ""

  # Secure salt for HMAC (automatically generated if not provided)
  secure_salt: ""
```

## Basic Usage

The App adapter is typically used implicitly through the core ACB initialization process:

```python
from acb import register_pkg
from acb.depends import depends
from acb.config import Config

# Register your package with ACB (initializes the App adapter)
register_pkg()

# Access configuration through dependency injection
config = depends.get(Config)

# Access application settings
app_name = config.app.name
app_version = config.app.version
app_domain = config.app.domain
```

## Advanced Usage

### Custom App Initialization

For applications with specific initialization needs:

```python
from acb import register_pkg
from acb.depends import depends
from acb.adapters import import_adapter

# Import the App adapter
App = import_adapter("app")

# Get the App instance via dependency injection
app = depends.get(App)

# Perform application startup tasks
async def startup():
    # Initialize application
    await app.init()

    # Perform additional initialization
    await app.setup_database()
    await app.load_templates()
    await app.register_routes()

# Perform application shutdown tasks
async def shutdown():
    await app.cleanup()
```

### Environment-Specific Configuration

```python
from acb.depends import depends
from acb.config import Config

config = depends.get(Config)

# Check if the application is deployed in production
if config.deployed:
    # Use production settings
    db_host = config.sql.host
else:
    # Use development settings
    db_host = config.sql.local_host

# Or use environment-specific configuration values
cache_ttl = 3600 if config.deployed else 60
```

### Accessing App Metadata

```python
from acb.depends import depends
from acb.config import Config

config = depends.get(Config)

# Generate application metadata
metadata = {
    "name": config.app.name,
    "version": config.app.version,
    "environment": "production" if config.deployed else "development",
    "api_base_url": f"https://api.{config.app.domain}",
}
```

## Troubleshooting

### Common Issues

1. **Configuration Not Found**
   - **Problem**: `FileNotFoundError: settings/app.yml not found`
   - **Solution**: Create the settings directory and ensure app.yml exists

2. **Invalid Configuration**
   - **Problem**: `ValidationError: app.name field required`
   - **Solution**: Ensure all required fields are provided in your app.yml file

3. **Multiple Registration Attempts**
   - **Problem**: `RegistrationError: Package already registered`
   - **Solution**: Call `register_pkg()` only once in your application

4. **Initialization Order Issues**
   - **Problem**: Components accessed before initialization
   - **Solution**: Ensure `register_pkg()` is called before accessing any ACB components

## Implementation Details

The App adapter extends the base AdapterBase class, inheriting its core functionality:

```python
class AppBase(AdapterBase):
    # Inherited methods
    async def init(self) -> None: ...

    # Application-specific methods may include:
    async def setup_database(self) -> None: ...
    async def load_templates(self) -> None: ...
    async def register_routes(self) -> None: ...
    async def cleanup(self) -> None: ...
```

## Additional Resources

- [ACB Configuration Documentation](../../README.md#configuration-system)
- [ACB Dependency Injection](../../README.md#dependency-injection)
- [ACB Adapters Overview](../README.md)
