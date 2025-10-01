---
id: 01K6GSRBSCAAD21MYRQ9SWACGK
---
______________________________________________________________________

## id: 01K6GSM6A43HW1TN2P8CZG68WT

______________________________________________________________________

## id: 01K6GPA4C98JQV6J7ASPCXZXGE

______________________________________________________________________

## id: 01K6GMDQXSQEP402N9ZK7EVWX0

______________________________________________________________________

## id: 01K6GKSVWPGQAE0HHH5EDYV34W

______________________________________________________________________

## id: 01K6GKJKK1APB3Y6P4NVNF1BEJ

______________________________________________________________________

## id: 01K6GJYFPZPMY5TJ39M3SXC37Z

______________________________________________________________________

## id: 01K6GGMAG0S2X23BKMZKJN4K67

______________________________________________________________________

## id: 01K6G688D57N3XNHWRP81R65JX

______________________________________________________________________

## id: 01K6G5HSCC406Q8X0REDNW9R9F

______________________________________________________________________

## id: 01K6G58HPM1T5QXJRR3YWFHZ5G

______________________________________________________________________

## id: 01K6G4MHD12QM7JD3BJDD604M4

______________________________________________________________________

## id: 01K6G3RA4BE5PQJBTZM30EVSBX

______________________________________________________________________

## id: 01K6G396MC6CB43W2GW1MJ89RK

______________________________________________________________________

## id: 01K6FZP5V4YC76393F1B3V6A04

______________________________________________________________________

## id: 01K6FY3SZ8XD22BGQ0M3MHNWDS

______________________________________________________________________

## id: 01K6FVE8Q66R16BK2MAXWSP6FQ

______________________________________________________________________

## id: 01K6FQNSM5D85F1QMVKJW9KFG1

# Fix Experiment Adapter Type Errors

## Issues to Fix

### 1. Base Adapter (\_base.py)

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

### 4. \_run_sync Return Type Annotations

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
1. Add missing metadata fields to all MODULE_METADATA
1. Change BATCH_OPERATIONS → BATCHING
1. Fix \_run_sync with proper generic return type
1. Fix import condition checks in __init__.py
1. Fix numpy type annotation in tensorboard.py
