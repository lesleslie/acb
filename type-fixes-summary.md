---
id: 01K6FP4NBFFSH2VMGCSFEFAMK6
---
# Type Error Fixes Summary

## Overview
Fixed all mypy/zuban type errors in logger and events modules for Python 3.13+ compatibility.

## Files Fixed

### 1. acb/adapters/logger/_base.py
**Issue**: Incompatible assignment and comparison-overlap errors
- Fixed `target_level` type annotation (line 237: added explicit `str | None` type)
- Fixed comparison logic (lines 243-250: proper None checking and type narrowing)

**Changes**:
```python
# Before: target_level could be str | None but wasn't annotated
# After: Explicit type annotation and proper None/False checking
target_level: str | None = self._get_effective_level()
if target_level is None:
    return False
if not target_level or (isinstance(target_level, str) and target_level.upper() == "FALSE"):
    return False
```

### 2. acb/adapters/logger/structlog.py
**Issue**: Incompatible types for processor list items (~11 errors)
- Added explicit type annotation for `processors` list (line 60)

**Changes**:
```python
# Before: processors = []
# After: processors: list[t.Any] = []
```

**Explanation**: structlog processors are valid but mypy doesn't recognize their types without explicit Any annotation.

### 3. acb/adapters/logger/loguru.py
**Issue**: Method signature incompatibility, no-any-return, and unused type ignores
- Added `type: ignore[misc]` to class definition (line 66) to suppress base class incompatibility
- Fixed `_bind` method return type annotation (line 122)
- Removed unused `type: ignore` comments (lines 244, 253)

**Changes**:
```python
# Class definition with proper ignore
class Logger(_Logger, LoggerBase):  # type: ignore[misc]

# Fixed bind method with explicit type annotation
new_logger: Logger = self.bind(**context)  # type: ignore[no-untyped-call]

# Removed unnecessary type: ignore comments from emit method
```

### 4. acb/events/_base.py
**Issue**: Incompatible await type, arg-type for ServiceStatus, missing type parameters
- Fixed await compatibility in `FunctionalEventHandler.handle` (lines 290-313)
- Fixed ServiceStatus import (line 24) - imported correct enum from `acb.services.discovery`
- Fixed `event_handler` decorator type parameters (lines 488-522)

**Changes**:
```python
# Fixed await type handling
if self._is_async:
    result: EventHandlerResult | t.Awaitable[EventHandlerResult] = self._handler_func(event)
    if isinstance(result, EventHandlerResult):
        return result
    result = await result

# Fixed ServiceStatus import (discovery.ServiceStatus has STABLE, _base.ServiceStatus doesn't)
from acb.services.discovery import ServiceStatus

# Fixed decorator type parameters
def event_handler(
    event_type: str | None = None,
    predicate: t.Callable[[Event], bool] | None = None,
) -> t.Callable[
    [t.Callable[[Event], EventHandlerResult | t.Awaitable[EventHandlerResult]]],
    FunctionalEventHandler,
]:
```

### 5. acb/adapters/embedding/_base.py (bonus fix)
**Issue**: NameError for `Any` type
- Fixed `__aexit__` method type hints (lines 152-156)

**Changes**:
```python
# Before: self: Any
# After: self: t.Any
```

## Type Error Categories Fixed

1. **Assignment compatibility**: Fixed type narrowing and annotations
2. **Comparison overlap**: Fixed None/False checking logic
3. **List item types**: Added explicit Any annotations for structlog processors
4. **Method signature compatibility**: Added appropriate type: ignore for loguru
5. **Await compatibility**: Fixed async/sync handler result handling
6. **Enum usage**: Used correct ServiceStatus from discovery module
7. **Generic type parameters**: Added complete type annotations for decorators

## Modern Python 3.13+ Patterns Used

- Union types with `|` syntax
- Type narrowing with explicit checks
- Proper Optional handling with `None` checks
- Explicit type annotations for better type inference
- Strategic use of `type: ignore` comments where necessary

## Verification

All files pass mypy with no errors:
```bash
python -m mypy acb/adapters/logger/_base.py acb/adapters/logger/structlog.py \
    acb/adapters/logger/loguru.py acb/events/_base.py --no-error-summary
# Success: no issues found
```

## Notes

- structlog processor types require `list[t.Any]` because the processor types aren't fully typed
- loguru Logger multiple inheritance requires `type: ignore[misc]` due to signature differences
- ServiceStatus exists in two places: `_base.py` (lifecycle) and `discovery.py` (stability status)
- Type narrowing was key to fixing the comparison-overlap and assignment errors
