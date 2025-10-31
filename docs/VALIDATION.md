# Validation (acb.validation)

ACB provides model/Settings validation helpers under `acb.validation`. These helpers complement the pure validators under `acb.actions.validate` by focusing on Pydantic/Settings integration.

## Contents

- `ValidationMixin`: reusable methods for common Settings/model checks
- `create_pattern_validator(pattern)`: Pydantic field validator factory
- `create_length_validator(min_length, max_length)`: length constraints

## Usage

```python
from pydantic import BaseModel, field_validator
from acb.validation import ValidationMixin, create_pattern_validator


class MySettings(BaseModel, ValidationMixin):
    api_key: str

    _check_api_key = field_validator("api_key")(create_pattern_validator(r"^sk-\w+$"))

    def validate_config(self) -> None:
        self.validate_required_field("api_key", self.api_key, context="MyService")
```

## When to use actions vs validation

- Use `acb.actions.validate` for pure value checks (email/url/sql/xss/path).
- Use `acb.validation` when integrating with Pydantic or ACB Settings.
