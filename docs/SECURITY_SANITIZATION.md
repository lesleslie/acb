# Security: Sanitization (acb.security.sanitization)

Security-focused sanitization utilities:

- `sanitize_input(value, *, max_length=None, allowed_chars=None, strip_html=False) -> str`
- `sanitize_path(path, *, base_dir=None, allow_absolute=False) -> Path`
- `mask_sensitive_data(text, *, visible_chars=4, patterns=None) -> str`
- `sanitize_output(data, *, mask_keys=True, mask_patterns=None) -> Any`
- `sanitize_dict_for_logging(data: dict, *, sensitive_keys=None) -> dict`
- `sanitize_html(value: str) -> str`
- `sanitize_sql(value: str) -> str`

## Examples

```python
from acb.security.sanitization import sanitize_input, sanitize_path

safe = sanitize_input("<script>hi</script>hello", strip_html=True)
safe_path = sanitize_path("../../etc/passwd", base_dir="/app/data")  # raises ValueError
```

Notes:

- `sanitize_sql` is not a replacement for parameterized queries; always bind parameters.
- `sanitize_output` and `sanitize_dict_for_logging` help avoid leaking secrets in logs.
