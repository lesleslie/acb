# ACB Semantic Action Template and Documentation

This document provides a comprehensive guide for creating semantic actions following the ACB pattern used across ACB and FastBlocks frameworks.

## Semantic Action Pattern Overview

ACB actions follow a consistent semantic structure where actions are **verb-based** and methods are **operation-specific**. The calling convention is `action.method()` for a clean, discoverable API.

### Examples from ACB/FastBlocks
```python
# ACB Core Actions
from acb.actions.compress import compress, decompress
from acb.actions.hash import hash
from acb.actions.encode import encode, decode

compressed = compress.gzip("Hello, ACB!", compresslevel=9)
blake3_hash = await hash.blake3("some data")
json_data = await encode.json(data)

# FastBlocks Actions
from fastblocks.actions.minify import minify
from fastblocks.actions.gather import gather

minified_css = minify.css(css_content)
routes = await gather.routes()
templates = await gather.templates()
```

## Action Creation Template

### 1. Directory Structure
```
project/
├── actions/
│   ├── __init__.py          # Action registration system
│   ├── README.md            # Action documentation
│   └── action_name/         # Individual action directory
│       ├── __init__.py      # Action implementation
│       └── README.md        # Action-specific docs (optional)
```

### 2. Action Implementation Pattern

**File: `actions/action_name/__init__.py`**
```python
"""Action description and purpose."""

import typing as t
from pathlib import Path
# Additional imports as needed

__all__: list[str] = ["action_name"]  # Export list for auto-discovery

class ActionName:
    """Action class following semantic naming conventions."""

    @staticmethod
    def method_one(param: str, option: bool = True) -> str:
        """
        Brief description of what this method does.

        Args:
            param: Description of parameter
            option: Description of optional parameter

        Returns:
            Description of return value

        Raises:
            SpecificError: When specific condition occurs
        """
        # Implementation here
        try:
            # Your logic
            result = "processed result"
            return result
        except Exception as e:
            raise ValueError(f"Error in method_one: {e}")

    @staticmethod
    async def async_method(data: t.Any) -> t.Any:
        """
        Async method for I/O operations.

        Args:
            data: Input data to process

        Returns:
            Processed result
        """
        # Async implementation for I/O operations
        # Use async for file operations, network requests, etc.
        return processed_data

# Export an instance of the action (lowercase name)
action_name = ActionName()
```

### 3. Naming Conventions

#### Action Names (Verb-based)
- `compress` / `decompress` - Data compression operations
- `hash` - Hashing and checksum operations
- `encode` / `decode` - Data encoding/decoding operations
- `minify` - Code minification operations
- `gather` - Component collection operations
- `validate` - Data validation operations
- `transform` - Data transformation operations

#### Method Names (Operation-specific)
- **Format/type specific**: `hash.blake3()`, `encode.json()`, `minify.css()`
- **Algorithm specific**: `compress.gzip()`, `hash.md5()`, `encode.base64()`
- **Component specific**: `gather.routes()`, `gather.templates()`

### 4. Complete Example: Validate Action

```python
# actions/validate/__init__.py
"""Data validation utilities following ACB semantic patterns."""

import re
import typing as t
from email_validator import validate_email as _validate_email
from urllib.parse import urlparse
from pathlib import Path

__all__: list[str] = ["validate"]

class Validate:
    """Data validation action with semantic method organization."""

    @staticmethod
    def email(email: str, check_deliverability: bool = True) -> bool:
        """
        Validate an email address.

        Args:
            email: Email address to validate
            check_deliverability: Whether to check if domain exists

        Returns:
            True if email is valid, False otherwise
        """
        try:
            _validate_email(email, check_deliverability=check_deliverability)
            return True
        except Exception:
            return False

    @staticmethod
    def url(url: str, schemes: list[str] = None) -> bool:
        """
        Validate a URL.

        Args:
            url: URL to validate
            schemes: Allowed URL schemes (default: ['http', 'https'])

        Returns:
            True if URL is valid, False otherwise
        """
        if schemes is None:
            schemes = ['http', 'https']

        try:
            parsed = urlparse(url)
            return (
                parsed.scheme in schemes and
                bool(parsed.netloc) and
                len(url) <= 2048
            )
        except Exception:
            return False

    @staticmethod
    def phone(phone: str, country_code: str = "US") -> bool:
        """
        Validate a phone number.

        Args:
            phone: Phone number to validate
            country_code: Country code for validation

        Returns:
            True if phone number is valid, False otherwise
        """
        # Remove all non-digit characters
        digits_only = re.sub(r'\D', '', phone)

        if country_code == "US":
            # US phone numbers: 10 digits
            return len(digits_only) == 10

        # International: 7-15 digits
        return 7 <= len(digits_only) <= 15

    @staticmethod
    async def file_exists(path: t.Union[str, Path]) -> bool:
        """
        Validate that a file exists (async for I/O).

        Args:
            path: File path to check

        Returns:
            True if file exists, False otherwise
        """
        try:
            from anyio import Path as AsyncPath
            async_path = AsyncPath(path)
            return await async_path.exists() and await async_path.is_file()
        except Exception:
            return False

    @staticmethod
    def json_string(json_str: str) -> bool:
        """
        Validate a JSON string.

        Args:
            json_str: JSON string to validate

        Returns:
            True if valid JSON, False otherwise
        """
        try:
            import json
            json.loads(json_str)
            return True
        except (json.JSONDecodeError, TypeError):
            return False

# Export instance for semantic usage
validate = Validate()
```

### 5. Usage Examples

```python
# Import the action
from myproject.actions.validate import validate

# Use semantic method calls
is_valid_email = validate.email("user@example.com")
is_valid_url = validate.url("https://example.com")
is_valid_phone = validate.phone("555-123-4567", country_code="US")

# Async methods for I/O operations
file_exists = await validate.file_exists("/path/to/file.txt")

# Method chaining for validation workflows
def validate_user_data(data: dict) -> dict:
    return {
        "email_valid": validate.email(data.get("email", "")),
        "website_valid": validate.url(data.get("website", "")),
        "phone_valid": validate.phone(data.get("phone", "")),
    }
```

### 6. Action Registration System

The ACB action system automatically discovers and registers actions using the following pattern:

```python
# actions/__init__.py
"""Action registration and discovery system."""

import typing as t
from pathlib import Path
from anyio import Path as AsyncPath

class Action:
    """Action metadata container."""
    def __init__(self, name: str, path: AsyncPath):
        self.name = name
        self.path = path
        self.methods: list[str] = []

async def register_actions(path: AsyncPath) -> list[Action]:
    """
    Automatically discover and register actions.

    Args:
        path: Base path to scan for actions

    Returns:
        List of registered actions
    """
    actions_path = path / "actions"
    if not await actions_path.exists():
        return []

    # Discover action directories
    found_actions: dict[str, AsyncPath] = {
        a.stem: a
        async for a in actions_path.iterdir()
        if await a.is_dir() and not a.name.startswith("_")
    }

    registered_actions = []

    for action_name, action_path in found_actions.items():
        try:
            # Import the action module
            module_path = f"actions.{action_name}"
            module = __import__(module_path, fromlist=[action_name])

            # Create action metadata
            _action = Action(action_name, action_path)

            # Register exported methods from __all__
            if hasattr(module, "__all__"):
                _action.methods = module.__all__

                # Make action instances available globally
                for attr in [a for a in dir(module) if a in module.__all__]:
                    action_instance = getattr(module, attr)
                    # Register in global actions namespace
                    setattr(actions, attr, action_instance)

            registered_actions.append(_action)

        except Exception as e:
            print(f"Error registering action {action_name}: {e}")

    return registered_actions

# Global actions namespace for registration
class Actions:
    """Global namespace for all registered actions."""
    pass

actions = Actions()
```

### 7. Testing Pattern

```python
# tests/test_validate_action.py
"""Tests for validate action following ACB patterns."""

import pytest
from myproject.actions.validate import validate

class TestValidateAction:
    """Test suite for validate action."""

    def test_email_validation(self):
        """Test email validation methods."""
        # Valid emails
        assert validate.email("user@example.com") is True
        assert validate.email("test.email+tag@domain.co.uk") is True

        # Invalid emails
        assert validate.email("invalid-email") is False
        assert validate.email("@domain.com") is False
        assert validate.email("user@") is False

    def test_url_validation(self):
        """Test URL validation methods."""
        # Valid URLs
        assert validate.url("https://example.com") is True
        assert validate.url("http://localhost:8000/path") is True

        # Invalid URLs
        assert validate.url("not-a-url") is False
        assert validate.url("ftp://example.com") is False  # Not in default schemes

        # Custom schemes
        assert validate.url("ftp://example.com", schemes=["ftp"]) is True

    def test_phone_validation(self):
        """Test phone validation methods."""
        # Valid US phones
        assert validate.phone("555-123-4567") is True
        assert validate.phone("(555) 123-4567") is True
        assert validate.phone("5551234567") is True

        # Invalid phones
        assert validate.phone("123") is False
        assert validate.phone("555-123-456") is False

    @pytest.mark.asyncio
    async def test_file_validation(self):
        """Test async file validation."""
        # This would test with actual files in practice
        # assert await validate.file_exists("tests/fixtures/test.txt") is True
        assert await validate.file_exists("/nonexistent/file.txt") is False

    def test_json_validation(self):
        """Test JSON string validation."""
        # Valid JSON
        assert validate.json_string('{"key": "value"}') is True
        assert validate.json_string('[]') is True
        assert validate.json_string('null') is True

        # Invalid JSON
        assert validate.json_string('{"key": value}') is False  # Unquoted value
        assert validate.json_string('not json') is False
```

## Best Practices for ACB Semantic Actions

### 1. **Semantic Naming**
- Actions should be **verbs** describing what they do
- Methods should be **specific operations** within that action domain
- Use clear, descriptive names that indicate purpose

### 2. **Method Organization**
- Group related operations under a single action class
- Use static methods for stateless operations
- Use async methods only for I/O operations (file access, network requests)

### 3. **Error Handling**
- Always handle exceptions gracefully
- Provide meaningful error messages
- Use appropriate exception types

### 4. **Type Safety**
- Include comprehensive type hints for all parameters and return values
- Use `typing` module for complex types
- Document parameter and return types in docstrings

### 5. **Documentation**
- Include docstrings for all classes and methods
- Provide usage examples in docstrings
- Document exceptions that may be raised

### 6. **Testing**
- Create comprehensive test suites for all action methods
- Test both success and failure cases
- Use pytest for async test support when needed

### 7. **Export Pattern**
- Always include `__all__` list for auto-discovery
- Export action instances with lowercase names
- Keep action classes as implementation detail

This semantic action pattern provides a highly consistent, discoverable, and extensible system for organizing utility functions across ACB and FastBlocks frameworks.
