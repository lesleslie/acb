# Validate Action

The `validate` action provides pure utility functions for input validation, security checks, and data sanitization.

## Overview

This action includes validation functions for common data types and security checks to prevent injection attacks. All functions are stateless and can be used independently of ACB adapters.

## Usage

```python
from acb.actions.validate import validate

# Email validation
is_valid = validate.email("user@example.com")  # True
is_valid = validate.email("invalid-email")  # False

# URL validation
is_valid = validate.url("https://example.com")  # True
is_valid = validate.url("not-a-url")  # False

# Phone number validation
is_valid = validate.phone("+1 (555) 123-4567")  # True
is_valid = validate.phone("invalid")  # False

# Security validation
is_safe = validate.sql_injection("SELECT name FROM users")  # False
is_safe = validate.sql_injection("John Doe")  # True

is_safe = validate.xss("<script>alert('xss')</script>")  # False
is_safe = validate.xss("Hello World")  # True

is_safe = validate.path_traversal("../../../etc/passwd")  # False
is_safe = validate.path_traversal("document.pdf")  # True

# Length validation
is_valid = validate.length("password", min_length=8)  # True
is_valid = validate.length("pwd", min_length=8)  # False

# Pattern matching
is_valid = validate.pattern("ABC123", r"^[A-Z]{3}\d{3}$")  # True

# Sanitization
safe_html = validate.sanitize_html("<script>alert('xss')</script>")
# Returns: "&lt;script&gt;alert('xss')&lt;/script&gt;"

safe_sql = validate.sanitize_sql("O'Reilly")
# Returns: "O''Reilly"
```

## Available Methods

### Basic Validation

- `validate.email(email)` - Validate email address format
- `validate.url(url)` - Validate URL format
- `validate.phone(phone)` - Validate phone number format
- `validate.length(value, min_length, max_length)` - Validate string length
- `validate.pattern(value, pattern)` - Validate against regex pattern

### Security Validation

- `validate.sql_injection(value)` - Check for SQL injection patterns
- `validate.xss(value)` - Check for XSS/script injection patterns
- `validate.path_traversal(value)` - Check for path traversal patterns

### Sanitization

- `validate.sanitize_html(value)` - Escape HTML characters
- `validate.sanitize_sql(value)` - Basic SQL quote escaping

## Design Principles

- **Pure Functions**: All validation functions are stateless
- **Type Safe**: Functions handle invalid input types gracefully
- **Security Focused**: Includes common security validation patterns
- **Framework Agnostic**: Can be used outside of ACB
- **Performance Optimized**: Uses compiled regex patterns for efficiency

## Security Patterns

The security validation functions detect common attack patterns:

### SQL Injection Patterns

- SQL keywords (SELECT, UNION, DROP, etc.)
- SQL comments (-- and /\* \*/)
- Boolean logic patterns
- Stored procedure calls

### XSS Patterns

- Script tags
- JavaScript/VBScript protocols
- Event handlers (onclick, onload, etc.)
- Embedded objects and iframes

### Path Traversal Patterns

- Directory traversal sequences (../ and ..)
- URL-encoded traversal patterns
- Home directory references (~)

## Error Handling

All validation functions return boolean values rather than raising exceptions, making them safe to use in conditional logic. For sanitization functions, invalid input types are converted to strings.

## Examples

### Input Validation Pipeline

```python
from acb.actions.validate import validate


def validate_user_input(email: str, password: str, bio: str) -> dict:
    """Validate all user input."""
    results = {
        "email_valid": validate.email(email),
        "password_length": validate.length(password, min_length=8),
        "bio_safe": all(
            [
                validate.xss(bio),
                validate.sql_injection(bio),
                validate.length(bio, max_length=500),
            ]
        ),
    }
    return results


# Usage
result = validate_user_input(
    email="user@example.com", password="securepass123", bio="Hello, I'm a new user!"
)
```

### Data Sanitization

```python
from acb.actions.validate import validate


def sanitize_form_data(data: dict) -> dict:
    """Sanitize form data for safe storage."""
    sanitized = {}
    for key, value in data.items():
        if isinstance(value, str):
            # Apply both HTML and SQL sanitization
            sanitized[key] = validate.sanitize_sql(validate.sanitize_html(value))
        else:
            sanitized[key] = value
    return sanitized
```

## Related Actions

- [secure](../secure/README.md) - Cryptographic utilities and token generation
- [encode](../encode/README.md) - Data serialization and encoding
- [hash](../hash/README.md) - Hashing and checksum functions
