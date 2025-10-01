---
id: 01K6GSR7E6EKBHK2YMM8EEJRS8
---
______________________________________________________________________

## id: 01K6GSM1P1SGQR8HXVMJ7R1V13

______________________________________________________________________

## id: 01K6GPA0B9SXHDRRB68FCAF1D6

______________________________________________________________________

## id: 01K6GMDKPDECQ4NKEJWNTCJKCF

______________________________________________________________________

## id: 01K6GKSQQ9E2DDQA516D1S5DM8

______________________________________________________________________

## id: 01K6GKJES4KYJDWY6KRY09H9WQ

______________________________________________________________________

## id: 01K6GJYC07HWABP4WPS9R492ER

______________________________________________________________________

## id: 01K6GGM6QA6D74E7Z8KR1QSV3G

______________________________________________________________________

## id: 01K6G685P6NJ3Q0K7HA9XCMWB0

______________________________________________________________________

## id: 01K6G5HP9T3S43MM80MB30K7M9

______________________________________________________________________

## id: 01K6G58DXKTV23HZVV72G7B10B

______________________________________________________________________

## id: 01K6G4MDXH0H438N7VAE8AM36F

______________________________________________________________________

## id: 01K6G3R6DZR7E7EBDZ6RWKHDZT

______________________________________________________________________

## id: 01K6G399YCGBFFZWZAQ9MV4RWT

______________________________________________________________________

## id: 01K6FYNA16NY6WKJZM0G9MM0QA

# ACB Feature Deletion Summary

**Date**: 2025-10-01
**Context**: Architecture simplification to focus ACB on core adapter functionality

## Deleted Features

The following features have been removed from ACB as part of the v0.19.1+ architecture simplification:

### 1. Feature Store Adapters (`acb/adapters/feature_store/`)

- **Reason**: Over-engineering for core adapter framework
- **Files Deleted**:
  - `acb/adapters/feature_store/_base.py`
  - `acb/adapters/feature_store/feast.py`
  - `acb/adapters/feature_store/tecton.py`
  - `acb/adapters/feature_store/aws.py`
  - `acb/adapters/feature_store/vertex.py`
  - `acb/adapters/feature_store/custom.py`

### 2. ML Model Adapters (`acb/adapters/mlmodel/`)

- **Reason**: Outside core mission of providing clean adapter interfaces
- **Files Deleted**:
  - `acb/adapters/mlmodel/_base.py`
  - `acb/adapters/mlmodel/tensorflow.py`
  - `acb/adapters/mlmodel/torchserve.py`
  - `acb/adapters/mlmodel/mlflow.py`
  - `acb/adapters/mlmodel/bentoml.py`
  - `acb/adapters/mlmodel/kserve.py`

### 3. NLP Adapters (`acb/adapters/nlp/`)

- **Reason**: Overlap with AI adapter, outside core scope
- **Files Deleted**:
  - `acb/adapters/nlp/_base.py`
  - `acb/adapters/nlp/spacy.py`
  - `acb/adapters/nlp/transformers.py`

### 4. Experiment Tracking Adapters (`acb/adapters/experiment/`)

- **Reason**: MLOps infrastructure outside adapter framework scope
- **Files Deleted**:
  - `acb/adapters/experiment/_base.py`
  - `acb/adapters/experiment/mlflow.py`
  - `acb/adapters/experiment/wandb.py`
  - `acb/adapters/experiment/tensorboard.py`

### 5. Gateway System (`acb/gateway/` + `acb/adapters/gateway/`)

- **Reason**: Complex enterprise features not essential for adapter framework
- **Files Deleted**:
  - `acb/gateway/_base.py`
  - `acb/gateway/analytics.py`
  - `acb/gateway/auth.py`
  - `acb/gateway/cache.py`
  - `acb/gateway/discovery.py`
  - `acb/gateway/rate_limiting.py`
  - `acb/gateway/routing.py`
  - `acb/gateway/security.py`
  - `acb/gateway/service.py`
  - `acb/gateway/validation.py`
  - `acb/adapters/gateway/` (entire directory)

### 6. Transformers System (`acb/transformers/`)

- **Reason**: Data transformation outside core adapter mission
- **Files Deleted**:
  - `acb/transformers/_base.py`
  - `acb/transformers/engine.py`
  - `acb/transformers/discovery.py`

## Documentation Updates Required

The following documentation files need to be updated to remove references to deleted features:

### High Priority

1. **ACB_UNIFIED_PLAN.md** - Remove Phase 5 features (mlmodel, feature_store, experiment, nlp) and Phase 3/6 components (gateway, transformers)
1. **IMPLEMENTATION_STATUS.md** - Update phase completion status and remove deleted feature sections
1. **CLAUDE.md** - Update architecture overview and adapter category list

### Medium Priority

4. **README.md** - Update feature list and capability matrices
1. **docs/CORE_SYSTEMS_ARCHITECTURE.md** - Remove architecture references
1. **docs/MIGRATION-GUIDE.md** - Add migration notes for deleted features

### Low Priority

7. Planning documents (PHASE\_\*.md) - Update for historical accuracy

## Replacement Guidance

For users who were relying on deleted features:

### Feature Store → Use Direct Database Adapters

- Use SQL/NoSQL adapters directly for feature storage
- Implement custom feature management in application code

### ML Model Serving → Use External Services

- Use TensorFlow Serving, TorchServe, etc. directly
- Use AI adapter for LLM inference
- Implement custom model serving endpoints

### NLP Processing → Use AI Adapter + External Libraries

- Use AI adapter for LLM-based NLP tasks
- Use spaCy, NLTK, etc. directly in application code
- Implement custom NLP pipelines

### Experiment Tracking → Use External Tools

- Use MLflow, Weights & Biases, etc. directly
- Implement custom tracking via SQL/NoSQL adapters

### API Gateway → Use External Solutions

- Use Kong, Traefik, or cloud-native API gateways
- Implement rate limiting in application layer
- Use authentication libraries directly

### Data Transformation → Application Layer

- Implement transformations in application code
- Use pandas, polars, etc. directly
- Build custom ETL pipelines

## ACB's Focused Mission

After these deletions, ACB focuses on:

1. **Clean Adapter Interfaces** - Standardized interfaces for external systems
1. **Dependency Injection** - Simple DI framework for component wiring
1. **Configuration Management** - YAML-based configuration with hot-reloading
1. **Essential Infrastructure** - Basic SSL, cleanup, logging support
1. **Core Adapters** - Cache, SQL, NoSQL, Storage, Secret, Monitoring, AI, Embedding, Vector, Graph

This focused scope ensures ACB remains:

- **Simple** - Easy to understand and use
- **Reliable** - Less code means fewer bugs
- **Maintainable** - Focused codebase is easier to maintain
- **Flexible** - Users can add custom solutions without framework constraints
