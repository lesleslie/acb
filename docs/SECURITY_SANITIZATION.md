# Security: Sanitization (acb.actions.sanitize)

Security-focused sanitization utilities:

- `sanitize.input(value, *, max_length=None, allowed_chars=None, strip_html=False) -> str`
- `sanitize.path(path, *, base_dir=None, allow_absolute=False) -> Path`
- `sanitize.mask_sensitive_data(text, *, visible_chars=4, patterns=None) -> str`
- `sanitize.output(data, *, mask_keys=True, mask_patterns=None) -> Any`
- `sanitize.dict_for_logging(data: dict, *, sensitive_keys=None) -> dict`
- `sanitize.html(value: str) -> str`
- `sanitize.sql(value: str) -> str`

## Examples

```python
from acb.actions.sanitize import sanitize

safe = sanitize.input("<script>hi</script>hello", strip_html=True)
safe_path = sanitize.path("../../etc/passwd", base_dir="/app/data")  # raises ValueError
```

Notes:

- `sanitize.sql` is not a replacement for parameterized queries; always bind parameters.
- `sanitize.output` and `sanitize.dict_for_logging` help avoid leaking secrets in logs.
