> **ACB Documentation**: [Main](../../../README.md) | [Core Systems](../../README.md) | [Actions](../../actions/README.md) | [Adapters](../README.md) | [Monitoring](./README.md)

# Monitoring Adapter

> **Configuration**
> Choose the `monitoring` implementation in `settings/adapters.yaml` and tune it via `settings/monitoring.yaml`. Store secrets in `settings/secrets/` or via a secret manager so they never reach git.

The Monitoring adapter provides a standardized interface for application monitoring, error tracking, and performance analysis in ACB applications.

## Overview

The ACB Monitoring adapter offers comprehensive application visibility:

- Error and exception tracking
- Performance monitoring
- Distributed tracing
- Custom event tracking
- Release and deployment tracking
- User context for errors and events

## Available Implementations

| Implementation | Description | Best For |
| -------------- | -------------------------------------- | ------------------------------ |
| **Sentry** | Error tracking and monitoring platform | Production applications |
| **Logfire** | Logging-based monitoring | Simple applications, debugging |

## Installation

```bash
# Install with Monitoring support
uv add acb --group monitoring

# Or include it with logger integration
uv add acb --group monitoring --group logger
```

## Configuration

### Settings

Configure the Monitoring adapter in your `settings/adapters.yaml` file:

```yaml
# Use Sentry implementation
monitoring: sentry

# Or use Logfire implementation
monitoring: logfire

# Or disable monitoring
monitoring: null
```

### Monitoring Settings

The Monitoring adapter settings can be customized in your `settings/app.yaml` file:

```yaml
monitoring:
  # Sampling rate for traces (0.0 to 1.0)
  traces_sample_rate: 0.1

  # DSN (Data Source Name) for Sentry
  dsn: "https://examplePublicKey@o0.ingest.sentry.io/0"

  # Environment name
  environment: "production"

  # Release identifier
  release: "myapp@1.0.0"

  # Server name
  server_name: "web-1"

  # Enable performance monitoring
  enable_performance: true

  # Integrations to enable
  integrations:
    - "sqlalchemy"
    - "aiohttp"
    - "asyncio"
```

## Basic Usage

```python
from acb.depends import depends
from acb.adapters import import_adapter

# Import the Monitoring adapter
Monitoring = import_adapter("monitoring")

# Get the Monitoring instance via dependency injection
monitoring = depends.get(Monitoring)

# Track an exception
try:
    # Some operation that might fail
    result = 1 / 0
except Exception as e:
    # Capture the exception
    monitoring.capture_exception(e)

    # Optionally add context
    monitoring.set_context("operation", {"name": "division", "input": 0})

    # Re-raise or handle as needed
    raise

# Track a custom event
monitoring.capture_message(
    "User login successful", level="info", tags={"user_id": "12345", "source": "web"}
)
```

## Advanced Usage

### Performance Monitoring

```python
from acb.depends import depends
from acb.adapters import import_adapter

Monitoring = import_adapter("monitoring")
monitoring = depends.get(Monitoring)

# Start a transaction for a web request
with monitoring.start_transaction(name="GET /api/users", op="http.server"):
    # Start a child span for database query
    with monitoring.start_span(description="fetch_users_from_db", op="db.query"):
        # Database operation here
        users = fetch_users_from_database()

    # Start another span for template rendering
    with monitoring.start_span(description="render_users_template", op="template"):
        # Template rendering here
        html = render_template("users.html", users=users)

    # The transaction automatically completes when the context exits
```

### User Context

```python
# Set user context for better error tracking
monitoring.set_user(
    {
        "id": "user-123",
        "email": "user@example.com",
        "username": "user123",
        "subscription": "premium",
    }
)

# Clear user context when user logs out
monitoring.clear_user()
```

### Release Tracking

```python
# Set release information
monitoring.set_release("myapp@1.2.0")

# Track a deployment
monitoring.track_deployment(
    {
        "environment": "production",
        "started": datetime.now().isoformat(),
        "commits": ["a1b2c3d4e5f6"],
        "deployer": "CI/CD Pipeline",
    }
)
```

### Custom Contexts and Tags

```python
# Add custom context
monitoring.set_context(
    "payment",
    {"provider": "stripe", "amount": 99.99, "currency": "USD", "success": True},
)

# Add tags (searchable key-value pairs)
monitoring.set_tags(
    {"feature_flag": "new_checkout", "experiment_group": "A", "user_tier": "premium"}
)
```

## Troubleshooting

### Common Issues

1. **DSN Configuration Error**

   - **Problem**: `ConfigurationError: DSN not configured`
   - **Solution**: Set a valid DSN in your settings/app.yaml file

1. **High Event Volume**

   - **Problem**: Too many events being sent, affecting performance or costs
   - **Solution**: Adjust the sampling rate or filter out noisy events

1. **Missing Context**

   - **Problem**: Events lack useful context for debugging
   - **Solution**: Add user context, tags, and additional data to events

1. **Integration Issues**

   - **Problem**: Certain integrations not working correctly
   - **Solution**: Check that required packages are installed and integrations are properly configured

## Implementation Details

The Monitoring adapter implements these core methods:

```python
class MonitoringBase:
    def capture_exception(self, exception: Exception, **kwargs) -> str: ...
    def capture_message(self, message: str, level: str = "info", **kwargs) -> str: ...
    def set_user(self, user: dict) -> None: ...
    def clear_user(self) -> None: ...
    def set_context(self, name: str, data: dict) -> None: ...
    def set_tags(self, tags: dict) -> None: ...
    def start_transaction(self, name: str, op: str = "", **kwargs) -> Transaction: ...
    def start_span(self, description: str, op: str = "", **kwargs) -> Span: ...
    def set_release(self, release: str) -> None: ...
    def track_deployment(self, data: dict) -> None: ...
```

## Additional Resources

- [Sentry Documentation](https://docs.sentry.io/platforms/python/)
- [Performance Monitoring Best Practices](https://docs.sentry.io/product/performance/)
- [ACB Logger Adapter](../logger/README.md)
- [ACB Adapters Overview](../README.md)
