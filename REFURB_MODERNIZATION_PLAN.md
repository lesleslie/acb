---
id: 01K6F242YG5FJS7Q0ECMG545ER
---
# ACB Refurb Modernization Plan

## Overview
Applying Python 3.13+ modernizations using refurb suggestions (166 total).

## Batch 1: Exception Suppression (FURB107) - ~40 occurrences
**Pattern**: `try: ... except Exception: pass` → `with suppress(Exception): ...`
**Import**: `from contextlib import suppress`
**Impact**: High readability improvement, no behavioral change
**Risk**: Very low

### Files:
- adapters/embedding/huggingface.py
- adapters/embedding/sentence_transformers.py
- adapters/experiment/mlflow.py
- adapters/feature_store/aws.py
- adapters/feature_store/custom.py
- adapters/feature_store/feast.py
- adapters/feature_store/tecton.py
- adapters/feature_store/vertex.py
- adapters/mlmodel/bentoml.py
- adapters/mlmodel/mlflow.py
- adapters/nlp/spacy.py (multiple)
- adapters/nlp/transformers.py
- config.py
- console.py
- debug.py
- events/__init__.py
- events/_base.py
- events/discovery.py
- events/publisher.py
- gateway/_base.py
- gateway/auth.py
- gateway/discovery.py
- migration/assessment.py (multiple)
- queues/__init__.py (multiple)
- queues/discovery.py

## Batch 2: Dict Merging (FURB173) - ~10 occurrences
**Pattern**: `{**dict1, **dict2}` → `dict1 | dict2`
**Impact**: High readability, modern Python idiom
**Risk**: Very low (Python 3.13+ feature)

### Files:
- adapters/ai/_base.py
- adapters/embedding/huggingface.py (2 occurrences)
- adapters/embedding/lfm.py
- adapters/embedding/onnx.py
- adapters/embedding/sentence_transformers.py
- gateway/gateway.py

## Batch 3: Modern Datetime (FURB176) - ~10 occurrences
**Pattern**: `datetime.utcnow()` → `datetime.now(tz=timezone.utc)`
**Import**: `from datetime import timezone`
**Impact**: High (deprecated method replacement)
**Risk**: Very low

### Files:
- gateway/auth.py
- queues/_base.py (multiple)
- queues/memory.py (multiple)

## Batch 4: List Comprehensions (FURB138) - ~20 occurrences
**Pattern**: Convert append loops to list comprehensions
**Impact**: Medium readability improvement
**Risk**: Low (verify logic equivalence)

### Files:
- adapters/experiment/wandb.py (2)
- adapters/feature_store/aws.py (3)
- adapters/feature_store/custom.py (2)
- adapters/feature_store/feast.py
- adapters/feature_store/tecton.py
- adapters/feature_store/vertex.py
- adapters/nlp/transformers.py
- events/discovery.py
- events/subscriber.py
- gateway/cache.py (4)
- gateway/routing.py (3)
- gateway/validation.py
- migration/validator.py
- queues/memory.py

## Batch 5: Tuple Membership (FURB109) - ~10 occurrences
**Pattern**: `in [x, y, z]` → `in (x, y, z)`
**Impact**: Medium (slight performance improvement)
**Risk**: Very low

### Files:
- adapters/experiment/tensorboard.py
- adapters/feature_store/custom.py (2)
- adapters/gateway/auth.py
- adapters/mlmodel/kserve.py (2)
- adapters/mlmodel/torchserve.py
- adapters/nlp/spacy.py (2)
- adapters/reasoning/custom.py

## Batch 6: Path.open() (FURB117) - ~3 occurrences
**Pattern**: `open(path)` → `path.open()`
**Impact**: Medium (pathlib best practice)
**Risk**: Very low

### Files:
- adapters/feature_store/custom.py (3)
- migration/assessment.py

## Batch 7: Simple Optimizations (FURB123, FURB110, FURB183, etc.)
**Impact**: Low-medium
**Risk**: Very low

### Files:
- Various files with minor optimizations

## Execution Order
1. Batch 1 (Exception Suppression) - Most impactful
2. Batch 3 (Modern Datetime) - Security/deprecation fix
3. Batch 2 (Dict Merging) - High visibility
4. Batch 5 (Tuple Membership) - Quick wins
5. Batch 6 (Path.open()) - Best practice
6. Batch 4 (List Comprehensions) - Requires more careful review
7. Batch 7 (Simple Optimizations) - Low priority

## Testing Strategy
- Run tests after each batch: `python -m pytest`
- Run crackerjack verification: `python -m crackerjack -t --ai-fix`
- Verify no behavioral changes
