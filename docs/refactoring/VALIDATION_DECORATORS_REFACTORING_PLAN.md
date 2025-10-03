# Validation Decorators Refactoring Plan

## Current Complexity Analysis

### High Complexity Functions

1. **validate_contracts** (complexity: 45)

   - Multiple nested conditionals for input/output validation
   - Type checking and error message construction within loops
   - Duplicate wrapper creation pattern

1. **validate_input** (complexity: 39)

   - Complex schema type handling (dict vs single schema)
   - Validation result aggregation logic
   - Argument binding and updating logic
   - Duplicate wrapper creation pattern

1. **ValidationDecorators::validate_method** (complexity: 27)

   - Method signature inspection and parameter handling
   - Input/output validation with error handling
   - Self parameter filtering logic
   - Duplicate wrapper creation pattern

1. **validate_schema** (complexity: 27)

   - Schema lookup and validation
   - Data source determination (args vs kwargs)
   - Result value unpacking and argument updating
   - Duplicate wrapper creation pattern

1. **sanitize_input** (complexity: 16)

   - Parameter iteration and type checking
   - Config creation and field filtering
   - Duplicate wrapper creation pattern

## Root Causes of Complexity

1. **Duplicate Wrapper Pattern**: Every decorator creates identical async/sync wrappers
1. **Nested Conditionals**: Deep nesting for type checking and validation logic
1. **Inline Logic**: Validation, error handling, and argument updates all inline
1. **Mixed Concerns**: Binding, validation, error handling, and result updates in single functions

## Refactoring Strategy

### 1. Extract Common Patterns

- **Create wrapper factory**: Single function to create async/sync wrappers
- **Extract argument binding**: Separate function for signature binding
- **Extract validation reporting**: Separate error handling logic
- **Extract value updating**: Separate argument update logic

### 2. Decompose Complex Functions

- **validate_contracts**:

  - Extract `_validate_input_contract()`
  - Extract `_validate_output_contract()`
  - Extract `_check_type_match()`

- **validate_input**:

  - Extract `_get_validation_schemas()`
  - Extract `_execute_validations()`
  - Extract `_update_validated_arguments()`
  - Extract `_check_and_raise_errors()`

- **validate_method**:

  - Extract `_validate_method_inputs()`
  - Extract `_validate_method_output()`
  - Extract `_filter_method_params()`

- **validate_schema**:

  - Extract `_get_validation_data()`
  - Extract `_update_validated_data()`

- **sanitize_input**:

  - Extract `_create_sanitize_config()`
  - Extract `_sanitize_parameters()`

### 3. Apply Modern Python Patterns

- Use match statements for type-based dispatch
- Use walrus operator for conditional assignments
- Early returns to reduce nesting
- Type-safe helper functions with protocols

### 4. Quality Gates

- All functions ≤13 complexity
- 100% backward compatibility
- All existing tests pass
- Type hints on all new functions
- No performance degradation

## Implementation Order

1. Create helper functions for common patterns
1. Refactor validate_contracts (highest complexity)
1. Refactor validate_input (second highest)
1. Refactor validate_method (third highest)
1. Refactor validate_schema (fourth highest)
1. Refactor sanitize_input (lowest but still high)
1. Run full test suite and crackerjack verification

## Success Criteria

- [ ] All functions have complexity ≤13
- [ ] All tests pass without modification
- [ ] No breaking changes to public API
- [ ] Type hints complete and pyright clean
- [ ] Crackerjack verification passes
