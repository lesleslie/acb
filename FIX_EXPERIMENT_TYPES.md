---
id: 01K6FQNSM5D85F1QMVKJW9KFG1
---
# Fix Experiment Adapter Type Errors

## Issues to Fix

### 1. Base Adapter (_base.py)
- Line 139: `__aenter__` should return `Self` not `None`
- Line 144: `__aexit__` missing type annotations for exc parameters

### 2. AdapterMetadata Missing Fields
All three implementations (mlflow.py, tensorboard.py, wandb.py) missing:
- `author`: str
- `created_date`: str (ISO format)
- `last_modified`: str (ISO format)
- `settings_class`: str

### 3. Wrong Capability Name
- `BATCH_OPERATIONS` should be `BATCHING` (correct enum value)

### 4. _run_sync Return Type Annotations
All three implementations have `_run_sync` methods missing proper return type:
- Should return `Any` not `None`
- Parameters need proper type annotations

### 5. Function Return Value Issues
Multiple functions declared to return values but `_run_sync` returns `None`:
- Need to use proper generic return type for `_run_sync`
- Fix all call sites to have correct return types

### 6. Import Handling in __init__.py
- Lines 112-119: Using wrong condition checks on class imports
- Should check `is not None` not truthiness

### 7. TensorBoard numpy Assignment
- Line 40: Can't assign None to module type variable
- Need proper conditional typing

## Changes Required

1. Fix base adapter async context manager types
2. Add missing metadata fields to all MODULE_METADATA
3. Change BATCH_OPERATIONS → BATCHING
4. Fix _run_sync with proper generic return type
5. Fix import condition checks in __init__.py
6. Fix numpy type annotation in tensorboard.py
