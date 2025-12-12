# Sanitize Action

The `sanitize` action provides helpers for cleaning potentially sensitive
payloads before logging, persisting, or returning them to clients. The
implementation lives in `acb/actions/sanitize/__init__.py` and exposes the
`sanitize` singleton plus several static helpers on `Sanitize`.

## Features

- **HTML Sanitization**: Strip or escape unsafe tags from user-provided strings
  before rendering them in templates or logs.
- **Structured Scrubbing**: `dict_for_logging` walks nested dictionaries/lists
  and masks keys such as `password`, `token`, or any custom list you supply.
- **Safe Logging Utilities**: Helpers to convert arbitrary payloads to safe
  representations using configurable defaults.

## Basic Usage

```python
from acb.actions.sanitize import sanitize

unsafe_html = "<script>alert('xss')</script><div>OK</div>"
clean = sanitize.html(unsafe_html)
# clean == "<div>OK</div>"

payload = {
    "username": "alice",
    "password": "super-secret",
    "nested": {"api_key": "abc123"},
}
safe = sanitize.dict_for_logging(payload, sensitive_keys=["api_key"])
# password/api_key fields replaced with \"***\"
```

All helpers are synchronous, stateless, and safe to reuse across threads or
async tasks. Pair them with the [validate action](../validate/README.md) for
end-to-end input hardening.
