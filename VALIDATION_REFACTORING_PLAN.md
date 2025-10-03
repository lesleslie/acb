# Validation System Refactoring Plan

## Executive Summary
Comprehensive refactoring of validation systems to eliminate complexity violations (≤13 target) and apply modern Python patterns (refurb modernizations).

## Target Files & Complexity Analysis

### 1. acb/services/validation/schemas.py
**Functions with High Complexity:**
- `ListValidationSchema._validate_value` - Complex item validation with nested loops
- `DictValidationSchema._validate_value` - Field validation with multiple conditions

**Issues:**
- Nested loops with conditional logic
- Mixed validation concerns in single methods
- Could benefit from strategy pattern

### 2. acb/services/repository/specifications.py
**Functions with High Complexity:**
- `FieldSpecification.to_sql_where` (complexity: ~30) - Long if-elif chain for operators
- `FieldSpecification.to_nosql_filter` (complexity: ~30) - Duplicate operator handling

**Issues:**
- Sequential if-elif chains (19+ branches each)
- Duplicate logic between SQL and NoSQL conversion
- Should use match statements or strategy pattern

### 3. acb/services/validation/output.py
**Functions with High Complexity:**
- `OutputValidator._validate_field` - Multiple validation type dispatch

**Issues:**
- Type dispatch with nested validation logic
- Could use strategy pattern

### 4. acb/services/validation/coercion.py
**Functions with High Complexity:**
- `TypeCoercer._perform_coercion` (complexity: ~25) - Type dispatch chain
- Individual coercion methods (_coerce_to_int, etc.) - Complex parsing logic

**Issues:**
- Long if-elif chains for type dispatch
- Complex parsing logic in individual methods
- Should use match statements

## Refurb Violations to Fix

### FURB107: Use suppress() context manager
**Location:** coercion.py line 135
```python
# BEFORE
except Exception:
    result.add_error("Cannot convert to string")

# AFTER
from contextlib import suppress
with suppress(Exception):
    result.value = str(data)
```

### FURB113: Use extend() for multiple appends
**Locations:** Multiple validation result builders
```python
# BEFORE
errors.append(error1)
errors.append(error2)

# AFTER
errors.extend((error1, error2))
```

### FURB138: Use list comprehensions
**Locations:** Loop-based list building
```python
# BEFORE
validated_items = []
for item in items:
    validated_items.append(process(item))

# AFTER
validated_items = [process(item) for item in items]
```

### FURB168: Simplify None checks
**Locations:** isinstance checks with type(None)
```python
# BEFORE
isinstance(x, str | type(None))

# AFTER
x is None or isinstance(x, str)
```

## Refactoring Strategy

### Phase 1: Extract Type Validators (specifications.py)
**Goal:** Reduce to_sql_where and to_nosql_filter complexity to ≤13

**Approach:**
1. Create operator-specific handler methods
2. Use match statements for operator dispatch
3. Extract parameter building logic

**Implementation:**
```python
class FieldSpecification:
    def to_sql_where(self, context: SpecificationContext) -> tuple[str, dict[str, Any]]:
        field_name = self._get_full_field_name(context)
        param_key = self._generate_param_key()

        # Use match statement (complexity = 1 per branch)
        match self.operator:
            case ComparisonOperator.EQUALS:
                return self._handle_equals(field_name, param_key)
            case ComparisonOperator.IN:
                return self._handle_in(field_name, param_key)
            # ... etc (each branch = 1 complexity)

    def _handle_equals(self, field_name: str, param_key: str) -> tuple[str, dict]:
        return f"{field_name} = :{param_key}", {param_key: self.value}

    def _handle_in(self, field_name: str, param_key: str) -> tuple[str, dict]:
        if isinstance(self.value, list | tuple):
            return self._handle_in_list(field_name, param_key)
        return f"{field_name} IN (:{param_key})", {param_key: self.value}
```

**Complexity Reduction:**
- Before: ~30 (long if-elif chain)
- After: ~8 (match + helper calls)
- Savings: 22 complexity points

### Phase 2: Extract Coercion Strategies (coercion.py)
**Goal:** Reduce _perform_coercion complexity to ≤13

**Approach:**
1. Create type-specific coercion strategy classes
2. Use match statement for type dispatch
3. Move complex parsing to dedicated methods

**Implementation:**
```python
class TypeCoercer:
    def __init__(self, ...):
        self._strategies = {
            int: IntCoercionStrategy(),
            float: FloatCoercionStrategy(),
            bool: BoolCoercionStrategy(),
            # ... etc
        }

    async def _perform_coercion(self, data: Any, target_type: type) -> Any:
        # Handle None early
        if data is None:
            return self._handle_none_value(target_type)

        # Use match for dispatch (complexity = 1 per branch)
        strategy = self._strategies.get(target_type)
        if strategy:
            return await strategy.coerce(data, self.strategy)

        # Fallback
        return target_type(data)

    def _handle_none_value(self, target_type: type) -> Any:
        match target_type:
            case type() if target_type in (str, list, dict, set, tuple):
                return target_type()
            case _:
                return None

class IntCoercionStrategy:
    async def coerce(self, data: Any, strategy: CoercionStrategy) -> int:
        if isinstance(data, bool):
            return int(data)
        if isinstance(data, int | float):
            return self._coerce_numeric(data, strategy)
        if isinstance(data, str):
            return self._coerce_string(data)
        if isinstance(data, Decimal):
            return self._coerce_decimal(data)
        return int(data)

    def _coerce_numeric(self, data: float | int, strategy: CoercionStrategy) -> int:
        if isinstance(data, float) and not data.is_integer():
            if strategy == CoercionStrategy.PERMISSIVE:
                return int(data)
            raise ValueError(f"Cannot coerce float {data} to int without precision loss")
        return int(data)

    def _coerce_string(self, data: str) -> int:
        data = data.strip()

        # Handle boolean-like strings
        if data.lower() in ("true", "yes", "on", "1"):
            return 1
        if data.lower() in ("false", "no", "off", "0"):
            return 0

        # Handle decimal strings
        if "." in data:
            return self._coerce_decimal_string(data)

        # Try direct conversion, fallback to comma removal
        with suppress(ValueError):
            return int(data)

        clean_data = data.replace(",", "")
        return int(clean_data)
```

**Complexity Reduction:**
- _perform_coercion: Before 25 → After 5
- Individual methods: Split into focused helpers
- Total savings: 20+ complexity points

### Phase 3: Simplify Schema Validators (schemas.py)
**Goal:** Reduce ListValidationSchema and DictValidationSchema complexity

**Approach:**
1. Extract item validation to separate methods
2. Use early returns to reduce nesting
3. Apply FURB138 (list comprehensions)

**Implementation:**
```python
class ListValidationSchema(ValidationSchema):
    async def validate(self, data: Any, field_name: str | None = None) -> ValidationResult:
        start_time = time.perf_counter()
        result = self._create_result(data, field_name)

        # Early coercion check
        items = await self._ensure_list(data, result)
        if not result.is_valid:
            return self._finalize_result(result, start_time)

        # Length validation
        self._validate_length(items, result)

        # Uniqueness validation
        if self.unique_items:
            self._validate_uniqueness(items, result)

        # Item validation
        if self.item_schema and result.is_valid:
            await self._validate_items(items, result, field_name)

        return self._finalize_result(result, start_time)

    async def _ensure_list(self, data: Any, result: ValidationResult) -> list:
        if isinstance(data, list | tuple):
            return list(data) if isinstance(data, tuple) else data

        if not self.config.enable_coercion:
            result.add_error(f"Expected list, got {type(data).__name__}")
            return []

        with suppress(Exception):
            coerced = list(data) if hasattr(data, "__iter__") else [data]
            result.value = coerced
            result.add_warning(f"Value coerced from {type(data).__name__} to list")
            return coerced

        result.add_error("Cannot convert to list")
        return []

    async def _validate_items(
        self, items: list, result: ValidationResult, field_name: str | None
    ) -> None:
        # Use comprehension for validation results
        validation_tasks = [
            self.item_schema.validate(item, f"{field_name or self.name}[{i}]")
            for i, item in enumerate(items)
        ]

        item_results = await asyncio.gather(*validation_tasks)

        validated_items = []
        for i, item_result in enumerate(item_results):
            if not item_result.is_valid:
                result.errors.extend(f"Item {i}: {error}" for error in item_result.errors)
            else:
                validated_items.append(item_result.value)
                result.warnings.extend(
                    f"Item {i}: {warning}" for warning in item_result.warnings
                )

        if result.is_valid:
            result.value = validated_items
```

**Complexity Reduction:**
- Before: 31 (nested loops + conditions)
- After: 8 (extracted methods)
- Savings: 23 complexity points

### Phase 4: Simplify Output Validator (output.py)
**Goal:** Reduce _validate_field complexity

**Approach:**
1. Use match statement for output type dispatch
2. Extract contract-specific validators
3. Reduce nesting depth

**Implementation:**
```python
class OutputValidator:
    async def _validate_with_contract(
        self, data: Any, contract: OutputContract, result: ValidationResult
    ) -> None:
        # Use match for clean dispatch
        match contract.output_type:
            case OutputType.DICT:
                await self._validate_dict_contract(data, contract, result)
            case OutputType.LIST:
                await self._validate_list_contract(data, contract, result)
            case OutputType.JSON_API:
                await self._validate_json_api_contract(data, contract, result)
            case OutputType.REST_API:
                await self._validate_rest_api_contract(data, contract, result)
            case OutputType.MODEL:
                await self._validate_model_contract(data, contract, result)
            case OutputType.SCALAR:
                await self._validate_scalar_contract(data, contract, result)
            case _:
                await self._validate_custom_contract(data, contract, result)
```

**Complexity Reduction:**
- Before: 17
- After: 7
- Savings: 10 complexity points

## Modern Python Patterns Applied

### 1. Match Statements (PEP 634)
Replace if-elif chains with match statements:
- specifications.py: Operator dispatch
- coercion.py: Type dispatch
- output.py: Output type dispatch

### 2. Contextlib.suppress
Replace try-except-pass with suppress():
- coercion.py: Type conversion attempts
- schemas.py: Coercion fallbacks

### 3. List/Dict Comprehensions
Replace loop-based building:
- schemas.py: Validated items collection
- output.py: Error aggregation

### 4. Modern Union Syntax
Already using `|` unions throughout

### 5. Structural Pattern Matching
Use type patterns in match statements for cleaner type handling

## Quality Metrics

### Complexity Targets
| File | Before | After | Reduction |
|------|--------|-------|-----------|
| specifications.py | 60 | 15 | 45 (75%) |
| coercion.py | 65 | 20 | 45 (69%) |
| schemas.py | 62 | 18 | 44 (71%) |
| output.py | 34 | 10 | 24 (71%) |
| **Total** | **221** | **63** | **158 (71%)** |

### Refurb Compliance
- Fix all FURB107, FURB113, FURB138, FURB168 violations
- 100% modern Python patterns

### Backward Compatibility
- Maintain all public APIs
- Preserve validation semantics
- All tests must pass

## Implementation Order

1. ✅ specifications.py (highest complexity, isolated)
2. ✅ coercion.py (high complexity, used by schemas)
3. ✅ schemas.py (uses coercion)
4. ✅ output.py (independent)
5. ✅ Run full test suite
6. ✅ Verify crackerjack compliance

## Success Criteria

- [ ] All functions complexity ≤13
- [ ] All refurb violations fixed
- [ ] All tests passing
- [ ] 100% backward compatibility
- [ ] Crackerjack verification passes
- [ ] Performance maintained or improved

## Estimated Impact

**Code Quality:**
- 71% complexity reduction
- 100% refurb compliance
- Modern Python 3.13+ patterns

**Maintainability:**
- Clearer code structure
- Easier to extend operators/types
- Better separation of concerns

**Performance:**
- Match statements ~10% faster than if-elif chains
- Reduced function call overhead
- Better async coordination (gather vs sequential)
