---
id: 01K6GMDMJSCSJZDGRRR69N2JHT
---
______________________________________________________________________

## id: 01K6GKSRWDS9DK85JSJRJDMR1J

______________________________________________________________________

## id: 01K6GKJG2RKF32KW0J9YQNDS7J

______________________________________________________________________

## id: 01K6GJYCSAT68FJW3JHDJY37CW

______________________________________________________________________

## id: 01K6GGM8272JCFJCYHV38Q7MDZ

______________________________________________________________________

## id: 01K6G683B1PE6JAJ6DEDSM5X66

______________________________________________________________________

## id: 01K6G5HV7BRZJAHZK9AQ2Y8BJY

______________________________________________________________________

## id: 01K6G58K8SHP0BXP42AXZM593X

______________________________________________________________________

## id: 01K6G4MK32Q7068J5EM6PQP0HN

______________________________________________________________________

## id: 01K6FZP43132V4A2MQCWA1QAS4

______________________________________________________________________

## id: 01K6FY3RTYG91QKYY2CDFNVD0F

______________________________________________________________________

## id: 01K6FVE7KAVYZFYMBAEV5GRAM6

______________________________________________________________________

## id: 01K6FSH38NGNZ3NGGFV2D5YF53

______________________________________________________________________

## id: 01K6FSG4KZX9ZE5GBF8QKRP299

______________________________________________________________________

## id: 01K6FSARBH78QH15PNBMKBZCRD

______________________________________________________________________

## id: 01K6FRWDZVZAW58NJNX3XQQ9EZ

______________________________________________________________________

## id: 01K6FRSQD2WKWNACGRF9QYD1WY

______________________________________________________________________

## id: 01K6FRKV0KTC01ZEY4T9B3RN2S

______________________________________________________________________

## id: 01K6FRJ5WQWEHX71H7YDRNZX8V

______________________________________________________________________

## id: 01K6FRDXH9QMK2FT6BZ2WJX0RM

______________________________________________________________________

## id: 01K6FQVXRE1395EANB9QR4M2VW

______________________________________________________________________

## id: 01K6FQNXC5P3Z566K7WKDW66SZ

______________________________________________________________________

## id: 01K6FQ9CWXBXV7ZDBRZGPA6R2S

______________________________________________________________________

## id: 01K6FQ063W22FK6HA3B6FWBYJV

______________________________________________________________________

## id: 01K6FPYA20GA74D6E2ENMJM7R6

______________________________________________________________________

## id: 01K6FPVWKGMEG14YMK45BMYPGD

______________________________________________________________________

## id: 01K6FP90BSKSF8BZ5VCFSQBT0Q

______________________________________________________________________

## id: 01K6FP1YZTRMXTBNZ81Q49MYVP

______________________________________________________________________

## id: 01K6FP06NX5Z04MYXRJN96RFDV

______________________________________________________________________

## id: 01K6FNY68RGVBPECXMSSMM7GVP

______________________________________________________________________

## id: 01K6FND4YJX5QVV8Z0BRMT8TM3

______________________________________________________________________

## id: 01K6FN9CF45Z5FV7MY35J0YSZ7

______________________________________________________________________

## id: 01K6FM8SVDWRQZTJ753S6HZS04

______________________________________________________________________

## id: 01K6FM4FB8TV05DYF2DBQMWY2T

______________________________________________________________________

## id: 01K6FM33G5NZAJK46BYNWVYYYR

______________________________________________________________________

## id: 01K6FKYW78SPJBRJQ0EPX0WYNW

______________________________________________________________________

## id: 01K6FKXG0Q3PBCGVJRNHBWJD64

______________________________________________________________________

## id: 01K6FK4E3H1KQ8G33Q98Y3SEX0

# Phase 2 Type Error Fixes - Implementation Plan

## Overview

Fix 217 remaining Phase 2 "Moderate Complexity" type errors in ACB codebase.

## Error Categories

### 1. union-attr Errors (~113 remaining)

**Pattern**: Accessing attributes on optional types without None checks
**Solution**: Add proper type narrowing with None checks before attribute access

**Top Files to Fix**:

- acb/adapters/reasoning/llamaindex.py (36 errors)
- acb/adapters/reasoning/openai_functions.py (22 errors)
- acb/adapters/reasoning/langchain.py (22 errors)
- acb/adapters/reasoning/custom.py (13 errors)
- acb/adapters/nlp/transformers.py (10 errors)

### 2. no-redef Errors (~26 remaining)

**Pattern**: Duplicate imports and variable redefinitions
**Solution**: Use type: ignore comments or restructure imports

**Files Fixed**:

- ✅ acb/adapters/experiment/__init__.py (6 errors fixed)

**Remaining**:

- Various files with import conflicts

### 3. assignment Errors (~77 remaining)

**Pattern**: Type mismatches in variable assignments
**Solution**: Add proper type annotations and conversions

**Top Files to Fix**:

- acb/adapters/reasoning/openai_functions.py (settings attribute access)
- acb/adapters/ai/cloud.py (content variable type)
- acb/testing/providers/integration.py (collection assignments)

**Note**: `acb/adapters/feature_store/` was deleted in ACB v0.19.1+.

## Fixes Completed

### Logger Adapters ✅

- **acb/adapters/logger/\_base.py**: Added None check for level_per_module
- **acb/adapters/logger/loguru.py**: Added None check for level_colors

### Experiment Adapters ✅

- **acb/adapters/experiment/__init__.py**: Added type: ignore for import redefinitions

### AI Adapters ✅

- **acb/adapters/ai/\_base.py**: Fixed deployment_strategies type annotation
- **acb/adapters/ai/edge.py**: Added None check for \_http_client
- **acb/adapters/ai/cloud.py**: Added explicit type annotation for content variable
- **acb/adapters/ai/hybrid.py**: Added None checks for \_cloud_adapter and \_edge_adapter

## Remaining Work

### High Priority Files (36+ errors each)

1. **acb/adapters/reasoning/llamaindex.py** (36 errors)

   - Multiple \_settings attribute access without None checks
   - Need comprehensive type narrowing pattern

1. **acb/adapters/reasoning/openai_functions.py** (22 errors)

   - Settings attribute access patterns
   - getattr() usage for optional attributes

1. **acb/adapters/reasoning/langchain.py** (22 errors)

   - Similar patterns to llamaindex

### Medium Priority Files (5-14 errors each)

**Note**: Several files listed below were deleted in ACB v0.19.1+ (experiment, nlp, gateway, mlmodel, feature_store adapters).

4. **acb/adapters/reasoning/custom.py** (13 errors)
1. **acb/queues/__init__.py** (6 errors)
1. **acb/testing/providers/integration.py** (5 errors)
1. **acb/services/repository/service.py** (5 errors)
1. **acb/adapters/embedding/lfm.py** (5 errors)
1. **acb/adapters/embedding/huggingface.py** (5 errors)

### Low Priority Files (3-4 errors each)

16-30. Various files with 3-4 errors each

## Fix Patterns

### Pattern 1: Settings Attribute Access

```python
# Before
if self._settings.api_key:
    api_key = self._settings.api_key.get_secret_value()

# After
if self._settings is None:
    msg = "Settings not initialized"
    raise ValueError(msg)
if self._settings.api_key:
    api_key = self._settings.api_key.get_secret_value()
```

### Pattern 2: Optional Attribute with getattr

```python
# Before
max_retries = self._settings.max_retries

# After
max_retries = getattr(self._settings, "max_retries", 3)
```

### Pattern 3: Dict/List None Checks

```python
# Before
for key, value in self.settings.level_colors.items():

# After
if self.settings.level_colors is not None:
    for key, value in self.settings.level_colors.items():
```

### Pattern 4: Variable Type Annotations

```python
# Before
content = request.prompt  # str
if request.images:
    content = [...]  # list[dict]

# After
content: str | list[dict[str, Any]] = request.prompt
if request.images:
    content = [...]
```

## Progress Tracking

- **Initial Errors**: 224
- **Current Errors**: 217
- **Errors Fixed**: 7
- **Completion**: 3%

## Next Steps

**Note**: Several categories below reference deleted adapters (experiment, gateway, nlp) - these errors no longer exist in ACB v0.19.1+.

1. Fix top 3 reasoning adapters (llamaindex, openai_functions, langchain) - 80 errors
1. Fix queue adapters - 6 errors
1. Fix testing and repository service errors - 10 errors
1. Fix remaining embedding adapters - 10 errors
1. Fix all low-priority files - remaining errors

## Estimated Completion

**Target**: All 217 errors fixed
**Time Required**: 2-3 hours of systematic refactoring
**Verification**: `zuban check acb/ 2>&1 | grep -E "union-attr|no-redef|assignment" | wc -l` should return 0
