---
id: 01K6GMDS4TWMWQ8G4SQE4DW33F
---
______________________________________________________________________

## id: 01K6GKSX4MGAM6Z9Y4QWVCN536

______________________________________________________________________

## id: 01K6GKJPE7N54DXKWYTHWRJ86J

______________________________________________________________________

## id: 01K6GJYGZFYT3C18Q0ACYDTMC8

______________________________________________________________________

## id: 01K6GGMBRMDX2C65W8YFN9Z72S

______________________________________________________________________

## id: 01K6G68972M9K5F8RN7ZY8NJXG

______________________________________________________________________

## id: 01K6G5HSV89B0ZA2Y1QMDS6731

______________________________________________________________________

## id: 01K6G58HR8KS4KVGAAMNGC0REH

______________________________________________________________________

## id: 01K6G4MHE977Z87FC4QVNJA0A7

______________________________________________________________________

## id: 01K6G3RACJ7SKRWRW56VYN89G0

______________________________________________________________________

## id: 01K6G395SXVEY3XR9SFP72RVPA

______________________________________________________________________

## id: 01K6FZP76PKNFWHZ8B07N51BHR

______________________________________________________________________

## id: 01K6FY3TTEA93PA05YS3VV9TJE

______________________________________________________________________

## id: 01K6FVE9SN4565BDM5TMJCVB0N

______________________________________________________________________

## id: 01K6FSH4CP0BAWRN71XN0R8WXW

______________________________________________________________________

## id: 01K6FSG5ZPRD0K6HNB77V5C6D5

______________________________________________________________________

## id: 01K6FSAT5C4KY78CTEP18ZHCVS

______________________________________________________________________

## id: 01K6FRWEWR6DNNHNPJV74VVJBK

______________________________________________________________________

## id: 01K6FRSRHRYB53DZJX7XJPY18E

______________________________________________________________________

## id: 01K6FRKW0CB736BRWV5E92C7M8

______________________________________________________________________

## id: 01K6FRJ6DMNTPJ54AC5HHV6ZG1

______________________________________________________________________

## id: 01K6FRDYPXYHBYF4X2KB8XJZA1

______________________________________________________________________

## id: 01K6FQVYA5W2NP98SW1CGN3A1G

______________________________________________________________________

## id: 01K6FQNY8XGR72VPK89PQT9B30

______________________________________________________________________

## id: 01K6FQ9DQ5CCCEJGW94Z9HJAAX

______________________________________________________________________

## id: 01K6FQ07506FQJB9FA79RAZ6H6

______________________________________________________________________

## id: 01K6FPYBAAXR11QTWEV67WKAK8

______________________________________________________________________

## id: 01K6FPVXJKHMRFC3BT6BM4M0FY

______________________________________________________________________

## id: 01K6FP917GF6Z85CG0MP64W9MS

______________________________________________________________________

## id: 01K6FP1ZTDJC9NDHSGYEM814V0

______________________________________________________________________

## id: 01K6FP07N6T4BCKD3B53AKS38P

______________________________________________________________________

## id: 01K6FNY6Z4R3PJZHYZB1M0DG7R

______________________________________________________________________

## id: 01K6FND5VWDK9EKRY9BCHGAHWA

______________________________________________________________________

## id: 01K6FN9D80RXXDFZBBMRRSR37N

______________________________________________________________________

## id: 01K6FM8VV8CSZJDKMVZ8Z8G690

______________________________________________________________________

## id: 01K6FM4GMG187V993V3EBKBAE2

______________________________________________________________________

## id: 01K6FM34W32W6QT57NA0XPDC3T

______________________________________________________________________

## id: 01K6FKYX0SD1QDSA2C9EWRS4Z7

______________________________________________________________________

## id: 01K6FKXGY7MRMQZTH1N6NXP6Z6

______________________________________________________________________

## id: 01K6FD9HEHCDHMEDT9Z1TAABEK

______________________________________________________________________

## id: 01K6FCP8EHMKMMHWDY0QS948WP

______________________________________________________________________

## id: 01K6FBZATSSPGNGMNWH5G7DCW6

______________________________________________________________________

## id: 01K6FBRS6FY7BYDY756MH62G5X

______________________________________________________________________

## id: 01K6FBJHR2MMPF2PMFQRM6M44E

______________________________________________________________________

## id: 01K6FB8K5VBA8VEKGB848N469W

______________________________________________________________________

## id: 01K6F9NXWR8ZYEV0SYV69MVFFD

______________________________________________________________________

## id: 01K6F9JXDB6VC5XHJ0244W4RA1

______________________________________________________________________

## id: 01K6F9HZ38RYGR65E96EXWP54A

______________________________________________________________________

## id: 01K6F9FFJFDYZ3BBDY9X9W79D7

______________________________________________________________________

## id: 01K6F9EHSZTHDZAKCT8DQVHD6D

______________________________________________________________________

## id: 01K6F242YG5FJS7Q0ECMG545ER

# ACB Refurb Modernization Plan

## Overview

Applying Python 3.13+ modernizations using refurb suggestions (166 total).

**Note**: This document references several adapter types that were deleted in ACB v0.19.1+ (experiment, feature_store, mlmodel, nlp, gateway). The file list below is historical and reflects the codebase state when this plan was created.

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
- events/\_base.py
- events/discovery.py
- events/publisher.py
- gateway/\_base.py
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

- adapters/ai/\_base.py
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
- queues/\_base.py (multiple)
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
1. Batch 3 (Modern Datetime) - Security/deprecation fix
1. Batch 2 (Dict Merging) - High visibility
1. Batch 5 (Tuple Membership) - Quick wins
1. Batch 6 (Path.open()) - Best practice
1. Batch 4 (List Comprehensions) - Requires more careful review
1. Batch 7 (Simple Optimizations) - Low priority

## Testing Strategy

- Run tests after each batch: `python -m pytest`
- Run crackerjack verification: `python -m crackerjack -t --ai-fix`
- Verify no behavioral changes
