---
id: 01K6FK4E3H1KQ8G33Q98Y3SEX0
---
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
- acb/adapters/feature_store/custom.py (connection type)
- acb/testing/providers/integration.py (collection assignments)

## Fixes Completed

### Logger Adapters ✅
- **acb/adapters/logger/_base.py**: Added None check for level_per_module
- **acb/adapters/logger/loguru.py**: Added None check for level_colors

### Experiment Adapters ✅
- **acb/adapters/experiment/__init__.py**: Added type: ignore for import redefinitions

### AI Adapters ✅
- **acb/adapters/ai/_base.py**: Fixed deployment_strategies type annotation
- **acb/adapters/ai/edge.py**: Added None check for _http_client
- **acb/adapters/ai/cloud.py**: Added explicit type annotation for content variable
- **acb/adapters/ai/hybrid.py**: Added None checks for _cloud_adapter and _edge_adapter

## Remaining Work

### High Priority Files (36+ errors each)
1. **acb/adapters/reasoning/llamaindex.py** (36 errors)
   - Multiple _settings attribute access without None checks
   - Need comprehensive type narrowing pattern

2. **acb/adapters/reasoning/openai_functions.py** (22 errors)
   - Settings attribute access patterns
   - getattr() usage for optional attributes

3. **acb/adapters/reasoning/langchain.py** (22 errors)
   - Similar patterns to llamaindex

### Medium Priority Files (5-14 errors each)
4. **acb/adapters/experiment/__init__.py** (14 errors - no-redef type)
5. **acb/adapters/reasoning/custom.py** (13 errors)
6. **acb/adapters/nlp/transformers.py** (10 errors)
7. **acb/adapters/gateway/gateway.py** (7 errors)
8. **acb/queues/__init__.py** (6 errors)
9. **acb/adapters/mlmodel/tensorflow.py** (6 errors)
10. **acb/testing/providers/integration.py** (5 errors)
11. **acb/services/repository/service.py** (5 errors)
12. **acb/adapters/nlp/__init__.py** (5 errors)
13. **acb/adapters/feature_store/aws.py** (5 errors)
14. **acb/adapters/embedding/lfm.py** (5 errors)
15. **acb/adapters/embedding/huggingface.py** (5 errors)

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
max_retries=self._settings.max_retries

# After
max_retries=getattr(self._settings, "max_retries", 3)
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

1. Fix top 3 reasoning adapters (llamaindex, openai_functions, langchain) - 80 errors
2. Fix remaining experiment adapter no-redef errors - 8 errors
3. Fix gateway and queue adapters - 13 errors
4. Fix testing and repository service errors - 10 errors
5. Fix remaining embedding and NLP adapters - 25 errors
6. Fix all low-priority files - 81 errors

## Estimated Completion

**Target**: All 217 errors fixed
**Time Required**: 2-3 hours of systematic refactoring
**Verification**: `zuban check acb/ 2>&1 | grep -E "union-attr|no-redef|assignment" | wc -l` should return 0
