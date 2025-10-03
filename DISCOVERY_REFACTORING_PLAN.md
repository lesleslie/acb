# Discovery System Refactoring Plan

## Analysis Summary

All three discovery files (`events/discovery.py`, `services/discovery.py`, `testing/discovery.py`) share an **identical complex import pattern** in their main import functions:

- `import_event_handler()` - complexity 45
- `import_service()` - complexity 45
- `import_test_provider()` - complexity 45

## Identified Complexity Pattern

The complexity stems from:

1. **Type branching**: Handling `str`, `list[str]`, and `None` input types
1. **Context inspection**: File reading and parsing for auto-detection
1. **Registry iteration**: Loop matching variable names
1. **Nested error handling**: Multiple try/except blocks
1. **Conditional logic**: Deep nesting for each branch

## Root Cause: Code Duplication

The three functions are **structurally identical** with only these differences:

- Registry variable names (`event_handler_registry` vs `service_registry` vs `test_provider_registry`)
- Exception types (`EventHandlerNotFound` vs `ServiceNotFound` vs `TestNotFound`)
- Descriptor/class fetching functions
- Variable naming conventions

## Refactoring Strategy

### 1. Extract Shared Discovery Logic

Create `acb/discovery_common.py` with:

**RegistryConfig Protocol**: Define registry access interface

```python
class RegistryConfig(Protocol):
    def get_descriptor(category: str) -> Any | None
    def try_import(category: str, name: str | None) -> type[Any] | None
    def get_registry() -> list[Any]
    not_found_exception: type[Exception]
```

**Complexity Reducers**:

- `_import_single_category()`: Handle single category import (complexity ≤5)
- `_import_multiple_categories()`: Handle list import (complexity ≤5)
- `_auto_detect_from_context()`: Handle context inspection (complexity ≤8)
- `import_from_registry()`: Main coordinator (complexity ≤5)

### 2. Simplify Context Detection

Replace file reading with simpler heuristics:

```python
def _extract_variable_name_from_frame(frame) -> str | None:
    """Extract variable name from calling frame - max complexity 3"""
    # Use inspect.getframeinfo for safer parsing
    # Return normalized variable name or None
```

### 3. Apply Strategy Pattern

Each discovery module creates a config:

```python
# events/discovery.py
EVENT_REGISTRY_CONFIG = RegistryConfig(
    get_descriptor=get_event_handler_descriptor,
    try_import=try_import_event_handler,
    get_registry=lambda: event_handler_registry.get(),
    not_found_exception=EventHandlerNotFound,
)


def import_event_handler(categories):
    return import_from_registry(categories, EVENT_REGISTRY_CONFIG)
```

## Complexity Reduction Metrics

**Before**:

- `import_event_handler`: 45
- `import_service`: 45
- `import_test_provider`: 45
- **Total**: 135

**After** (target):

- `import_from_registry`: ≤5 (coordinator)
- `_import_single_category`: ≤5
- `_import_multiple_categories`: ≤5
- `_auto_detect_from_context`: ≤8
- `import_event_handler`: ≤3 (wrapper)
- `import_service`: ≤3 (wrapper)
- `import_test_provider`: ≤3 (wrapper)
- **Total**: ≤29 (78% reduction)

## Implementation Steps

1. **Create `acb/discovery_common.py`**:

   - Define `RegistryConfig` protocol
   - Implement helper functions with early returns
   - Use contextlib.suppress for error handling

1. **Refactor each discovery module**:

   - Create registry config
   - Replace complex function with config wrapper
   - Add type hints

1. **Verify backward compatibility**:

   - All existing tests must pass
   - Same error handling behavior
   - Same return types

## Benefits

- **DRY**: 135 lines of duplicated logic → 29 lines of shared logic
- **Complexity**: All functions ≤13
- **Testability**: Single implementation to test/maintain
- **Extensibility**: Easy to add new registry types
- **Type Safety**: Protocol-based contracts
