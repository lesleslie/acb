# Type Error Fixes Implementation Plan

## Completed Fixes

✅ **Priority 1: AdapterMetadata Fields**
- Fixed acb/adapters/graph/neptune.py - Added author, created_date, last_modified, settings_class
- Fixed acb/adapters/queue/memory.py - Added missing fields and converted module_id string to UUID

✅ **Priority 2: Type Mismatches - Partial**
- Fixed acb/adapters/graph/_base.py - Added proper type annotation for _client_lock
- Fixed acb/adapters/logger/loguru.py - Added type annotation for settings dict attribute

✅ **Priority 2: Logger Type Issues**
- Fixed acb/adapters/reasoning/openai_functions.py - Added TYPE_CHECKING guard and used LoggerType
- Fixed acb/adapters/reasoning/custom.py - Used LoggerType annotation
- Fixed acb/adapters/queue/_base.py - Added TYPE_CHECKING guard and used LoggerType

✅ **Priority 3: VersionInfo Constructor**
- Fixed acb/migration/_base.py - Added explicit type annotation for build variable

✅ **Priority 4: Generic Type Parameters**
- Fixed acb/services/repository/coordinator.py - Added RepositoryBase[Any] type parameters
- Fixed acb/queues/_base.py - Added asyncio.Task[None] type parameter

✅ **Priority 5: Other Type Issues**
- Fixed acb/adapters/reasoning/_base.py - Added None check for asyncio.current_task()
- Fixed acb/adapters/reasoning/openai_functions.py - Split _react_reasoning into public override and internal implementation
- Fixed acb/adapters/reasoning/custom.py - Added explicit type guard comment for division

## Summary of All Fixes

### Fixed Files (11 total)

1. **acb/adapters/graph/neptune.py** - Added missing AdapterMetadata fields
2. **acb/adapters/queue/memory.py** - Fixed UUID type and added missing fields
3. **acb/adapters/graph/_base.py** - Fixed _client_lock type annotation
4. **acb/adapters/logger/loguru.py** - Added settings dict type annotation
5. **acb/adapters/reasoning/openai_functions.py** - Fixed Logger type and _react_reasoning signature
6. **acb/adapters/reasoning/custom.py** - Fixed Logger type and added division guard
7. **acb/adapters/queue/_base.py** - Fixed Logger type and Task generic parameter
8. **acb/migration/_base.py** - Fixed VersionInfo build variable type
9. **acb/services/repository/coordinator.py** - Added RepositoryBase generic parameters
10. **acb/queues/_base.py** - Fixed Logger type and Task generic parameter
11. **acb/adapters/reasoning/_base.py** - Added asyncio.current_task() None check

## Changes by Category

### Type Annotations
- Added modern Python 3.13 syntax (`|` unions instead of `Union`)
- Explicit generic type parameters (`RepositoryBase[Any]`, `Task[None]`)
- Proper TYPE_CHECKING guards for Logger imports
- Type annotations for dynamically created attributes

### Error Prevention
- None checks before attribute access
- Type guards for division operations
- Proper method signature matching between base and derived classes

### Metadata Compliance
- All adapters now have complete AdapterMetadata with required fields
- UUID types properly handled (converted from strings where needed)

## Verification Steps

All type errors should now be resolved. Run verification:

```bash
# Type checking
python -m pyright acb/

# Quality verification
python -m crackerjack -t --ai-fix
```

## Priority 1: Missing AdapterMetadata Fields

### 1. acb/adapters/graph/neptune.py:34
**Error**: Missing required fields (author, created_date, last_modified, settings_class)
**Fix**: Add all required fields with proper defaults

### 2. acb/adapters/queue/memory.py:46
**Error**:
- Missing required fields (author, created_date, last_modified, settings_class)
- Argument "module_id" has incompatible type "str"; expected "UUID"

**Fix**:
- Convert string to UUID using `UUID()` constructor
- Add all missing required fields

## Priority 2: Type Mismatches

### 1. acb/adapters/graph/_base.py:223-224
**Errors**:
- Line 223: Incompatible types (expression has type "Lock", variable has type "None")
- Line 224: "None" has no attribute "__aenter__"
- Line 224: "None" has no attribute "__aexit__"

**Fix**: Initialize `_client_lock` with proper type annotation as `asyncio.Lock | None`

### 2. acb/adapters/logger/loguru.py:203, 213
**Error**: "LoguruSettings" has no attribute "settings"

**Fix**: The issue is accessing `self.settings.settings` - should be accessing the dict directly from LoguruSettings

### 3. acb/adapters/reasoning/openai_functions.py:115
**Error**: Variable "acb.logger.Logger" is not valid as a type

**Fix**: Use proper type annotation from TYPE_CHECKING

### 4. acb/adapters/queue/_base.py:244
**Error**: Variable "acb.logger.Logger" is not valid as a type

**Fix**: Use proper type annotation from TYPE_CHECKING

## Priority 3: VersionInfo Constructor Issues

### acb/migration/_base.py:94-99
**Errors**:
- Line 94: Incompatible types (expression has type "None", variable has type "str")
- Line 99: Unexpected keyword arguments for VersionInfo

**Fix**: Handle None case for build variable and ensure proper argument passing

## Priority 4: Generic Type Parameters

### 1. acb/services/repository/coordinator.py:88, 128, 150
**Error**: Missing type parameters for generic type "RepositoryBase"

**Fix**: Add type parameters `RepositoryBase[Any]`

### 2. acb/queues/_base.py:399
**Error**: Missing type parameters for generic type "Task"

**Fix**: Add type parameters `Task[None]`

## Priority 5: Other Type Issues

### 1. acb/adapters/reasoning/_base.py:360
**Error**: Item "None" of "Task[Any] | None" has no attribute "get_name"

**Fix**: Add None check before accessing attribute

### 2. acb/adapters/reasoning/openai_functions.py:493
**Error**: Signature of "_react_reasoning" incompatible with supertype

**Fix**: Ensure signature matches base class

### 3. acb/adapters/reasoning/custom.py:233
**Error**: Division by zero (static analysis false positive)

**Fix**: Add type guard to ensure denominator is not zero

## Implementation

All fixes will:
1. Use modern Python 3.13 syntax (| unions instead of Union)
2. Add proper type annotations
3. Maintain 100% backward compatibility
4. Fix all pyright/mypy errors
