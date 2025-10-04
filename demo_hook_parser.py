#!/usr/bin/env python3
"""Demo script showing hook_parser in action with realistic examples."""  # noqa: EXE001

from __future__ import annotations

from hook_parser import extract_failed_hooks, parse_hook_line, parse_hook_output

# Example 1: Single line parsing
print("=" * 70)  # noqa: T201
print("Example 1: Single Line Parsing")  # noqa: T201
print("=" * 70)  # noqa: T201

examples = [
    "refurb................................................................ ✅",
    "my...custom...hook.................................................... ❌",
    "test.integration.api.................................................. Passed",
    "hook-with-dashes...................................................... Failed",
]

for example in examples:
    result = parse_hook_line(example)
    status_symbol = "✅" if result.passed else "❌"
    status_text = "PASS" if result.passed else "FAIL"
    print(f"{status_symbol} {result.hook_name:30} | Status: {status_text}")  # noqa: T201

print()  # noqa: T201

# Example 2: Realistic crackerjack output
print("=" * 70)  # noqa: T201
print("Example 2: Realistic Crackerjack Output")  # noqa: T201
print("=" * 70)  # noqa: T201

# fmt: off
crackerjack_output = (
    "refurb................................................................ ✅\n"
    "bandit................................................................ ✅\n"
    "pyright............................................................... ❌\n"
    "ruff.................................................................. ✅\n"
    "pyproject-fmt......................................................... ✅\n"
    "vulture............................................................... ❌\n"
    "creosote.............................................................. ✅\n"
    "complexipy............................................................ ✅\n"
    "codespell............................................................. ✅\n"
    "detect-secrets........................................................ ✅"
)
# fmt: on

results = parse_hook_output(crackerjack_output)

print(f"Total hooks: {len(results)}")  # noqa: T201
passed_count = sum(1 for r in results if r.passed)
failed_count = sum(1 for r in results if not r.passed)
print(f"Passed: {passed_count}")  # noqa: T201
print(f"Failed: {failed_count}")  # noqa: T201
print()  # noqa: T201

print("Detailed results:")  # noqa: T201
for result in results:
    status = "✅ PASS" if result.passed else "❌ FAIL"
    print(f"  {status:9} | {result.hook_name}")  # noqa: T201

print()  # noqa: T201

# Example 3: Extract failed hooks only
print("=" * 70)  # noqa: T201
print("Example 3: Extract Failed Hooks")  # noqa: T201
print("=" * 70)  # noqa: T201

failed = extract_failed_hooks(crackerjack_output)
if failed:
    print(f"❌ {len(failed)} hook(s) failed:")  # noqa: T201
    for hook in failed:
        print(f"  - {hook}")  # noqa: T201
else:
    print("✅ All hooks passed!")  # noqa: T201

print()  # noqa: T201

# Example 4: Edge cases demonstration
print("=" * 70)  # noqa: T201
print("Example 4: Edge Cases")  # noqa: T201
print("=" * 70)  # noqa: T201

# fmt: off
edge_cases = [
    ("Very short name", "py.................................................................... ✅"),  # noqa: E501
    ("Very long name", "very.long.hook.name.with.many.segments.for.testing.purposes...... ✅"),  # noqa: E501
    ("Triple dots in name", "my...custom...hook........................................................ ❌"),  # noqa: E501
    ("Mixed special chars", "test-my.custom_hook_123................................................... ✅"),  # noqa: E501
    ("Unicode characters", "test_émoji_🎯.............................................................. ✅"),  # noqa: E501
    ("Minimal padding", "verylonghookname.. ✅"),
]
# fmt: on

for description, line in edge_cases:
    result = parse_hook_line(line)
    status = "✅" if result.passed else "❌"
    print(f"{status} {description:25} | Hook name: '{result.hook_name}'")  # noqa: T201

print()  # noqa: T201

# Example 5: Error handling
print("=" * 70)  # noqa: T201
print("Example 5: Error Handling")  # noqa: T201
print("=" * 70)  # noqa: T201

# fmt: off
invalid_lines = [
    ("Empty line", ""),
    ("No status marker", "refurb................................................................"),  # noqa: E501
    ("Invalid marker", "refurb................................................................ INVALID"),  # noqa: E501
    ("Only status", "✅"),
    ("Only dots", "..................................................................... ✅"),  # noqa: E501
]
# fmt: on

for description, line in invalid_lines:
    try:
        parse_hook_line(line)
        print(f"❌ {description:25} | Should have raised error!")  # noqa: T201
    except Exception as e:
        error_type = type(e).__name__
        print(f"✅ {description:25} | Correctly raised: {error_type}")  # noqa: T201

print()  # noqa: T201
print("=" * 70)  # noqa: T201
print("Demo complete!")  # noqa: T201
print("=" * 70)  # noqa: T201
