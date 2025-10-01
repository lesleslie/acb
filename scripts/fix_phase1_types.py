#!/usr/bin/env python3
"""
Phase 1 Type Fixes - Quick Wins (275 errors)

Systematically fixes:
1. no-untyped-def (141 errors) - add -> None return types
2. type-arg (114 errors) - add generic type parameters
3. var-annotated (20 errors) - add variable type annotations
"""

import re
import subprocess
from pathlib import Path
from typing import Any


def get_phase1_errors() -> dict[str, list[tuple[str, int, str]]]:
    """Get all Phase 1 errors grouped by type."""
    result = subprocess.run(
        ["zuban", "check", "acb/"],
        capture_output=True,
        text=True,
    )

    errors: dict[str, list[tuple[str, int, str]]] = {
        "no-untyped-def": [],
        "type-arg": [],
        "var-annotated": [],
    }

    # Combine stdout and stderr
    output = result.stdout + "\n" + result.stderr

    for line in output.splitlines():
        if "error:" not in line:
            continue

        for error_type in errors:
            if f"[{error_type}]" in line:
                # Parse: file.py:123: error: message [error-type]
                match = re.match(r"^(.+?):(\d+):\s*error:\s*(.+?)\s*\[" + error_type + r"\]", line)
                if match:
                    file_path, line_num, message = match.groups()
                    errors[error_type].append((file_path, int(line_num), message))
                    break

    return errors


def fix_no_untyped_def(file_path: str, line_num: int, message: str) -> bool:
    """Fix no-untyped-def errors by adding type annotations."""
    path = Path(file_path)
    if not path.exists():
        return False

    content = path.read_text()
    lines = content.splitlines(keepends=True)

    if line_num > len(lines):
        return False

    target_line = lines[line_num - 1]

    # Pattern 1: Missing return type annotation
    if "missing a return type annotation" in message.lower():
        # Add -> None for functions without explicit return
        if "def " in target_line and "->" not in target_line:
            # Handle both sync and async functions
            match = re.match(r"^(\s*)(async\s+)?def\s+(\w+)\s*\([^)]*\)(\s*):", target_line)
            if match:
                indent, async_prefix, func_name, space = match.groups()
                async_prefix = async_prefix or ""
                # Insert -> None before the colon
                new_line = re.sub(
                    r"(\([^)]*\))(\s*):",
                    r"\1 -> None:",
                    target_line
                )
                if new_line != target_line:
                    lines[line_num - 1] = new_line
                    path.write_text("".join(lines))
                    return True

    # Pattern 2: Missing type annotation for arguments
    elif "missing a type annotation for" in message.lower():
        # Add Any for untyped parameters
        if "def " in target_line:
            # Find untyped parameters and add : Any
            def add_any_to_params(match: re.Match[str]) -> str:
                params = match.group(1)
                # Split by comma, handle each parameter
                new_params = []
                for param in params.split(","):
                    param = param.strip()
                    if param and ":" not in param and "=" not in param and "*" not in param:
                        # Simple parameter without type annotation
                        param = f"{param}: Any"
                    new_params.append(param)
                return "(" + ", ".join(new_params) + ")"

            # Check if we need to add Any import
            if "from typing import" not in content and "import typing" not in content:
                # Add Any import at the top
                import_line = "from typing import Any\n\n"
                lines.insert(0, import_line)
                line_num += 1  # Adjust line number

            new_line = re.sub(
                r"def\s+\w+\s*\(([^)]*)\)",
                lambda m: f"def {target_line.split('def')[1].split('(')[0]}({add_any_to_params(m)})",
                target_line
            )
            if new_line != target_line:
                lines[line_num - 1] = new_line
                path.write_text("".join(lines))
                return True

    # Pattern 3: Function is missing a type annotation (no args specified)
    elif "function is missing a type annotation" in message.lower() and "arguments" not in message.lower():
        # Add -> None to function definition
        if "def " in target_line and "->" not in target_line:
            new_line = re.sub(r"(\))\s*:", r"\1 -> None:", target_line)
            if new_line != target_line:
                lines[line_num - 1] = new_line
                path.write_text("".join(lines))
                return True

    return False


def fix_type_arg(file_path: str, line_num: int, message: str) -> bool:
    """Fix type-arg errors by adding generic type parameters."""
    path = Path(file_path)
    if not path.exists():
        return False

    content = path.read_text()
    lines = content.splitlines(keepends=True)

    if line_num > len(lines):
        return False

    target_line = lines[line_num - 1]

    # Common generic type fixes
    replacements = {
        r'\bdict\b(?!\[)': 'dict[str, Any]',
        r'\bDict\b(?!\[)': 'Dict[str, Any]',
        r'\blist\b(?!\[)': 'list[Any]',
        r'\bList\b(?!\[)': 'List[Any]',
        r'\bset\b(?!\[)': 'set[Any]',
        r'\bSet\b(?!\[)': 'Set[Any]',
        r'\bCallable\b(?!\[)': 'Callable[..., Any]',
        r'\bTask\b(?!\[)': 'Task[None]',
        r'\btuple\b(?!\[)': 'tuple[Any, ...]',
        r'\bTuple\b(?!\[)': 'Tuple[Any, ...]',
    }

    new_line = target_line
    for pattern, replacement in replacements.items():
        new_line = re.sub(pattern, replacement, new_line)

    if new_line != target_line:
        lines[line_num - 1] = new_line

        # Ensure proper imports
        imports_needed = set()
        if "Dict[" in new_line or "List[" in new_line or "Set[" in new_line or "Tuple[" in new_line or "Callable[" in new_line:
            imports_needed.add("typing")
        if "Task[" in new_line:
            imports_needed.add("asyncio")
        if "Any" in new_line and "from typing import" not in content:
            imports_needed.add("typing")

        # Add imports if needed
        for import_type in imports_needed:
            if import_type == "typing":
                if "from typing import" not in content:
                    lines.insert(0, "from typing import Any, Callable, Dict, List, Set, Tuple\n")
            elif import_type == "asyncio":
                if "import asyncio" not in content and "from asyncio import" not in content:
                    lines.insert(0, "import asyncio\n")

        path.write_text("".join(lines))
        return True

    return False


def fix_var_annotated(file_path: str, line_num: int, message: str) -> bool:
    """Fix var-annotated errors by adding variable type annotations."""
    path = Path(file_path)
    if not path.exists():
        return False

    content = path.read_text()
    lines = content.splitlines(keepends=True)

    if line_num > len(lines):
        return False

    target_line = lines[line_num - 1]

    # Add type annotation to variable assignment
    # Pattern: var_name = value
    match = re.match(r'^(\s*)(\w+)\s*=\s*(.+)$', target_line)
    if match:
        indent, var_name, value = match.groups()

        # Infer type from value
        type_hint = "Any"
        value = value.strip()

        if value.startswith("{") and value.endswith("}"):
            type_hint = "dict[str, Any]"
        elif value.startswith("[") and value.endswith("]"):
            type_hint = "list[Any]"
        elif value.startswith("(") and value.endswith(")"):
            type_hint = "tuple[Any, ...]"
        elif value in ("True", "False"):
            type_hint = "bool"
        elif value.isdigit():
            type_hint = "int"
        elif value.startswith('"') or value.startswith("'"):
            type_hint = "str"

        new_line = f"{indent}{var_name}: {type_hint} = {value}\n"
        if new_line != target_line:
            lines[line_num - 1] = new_line

            # Ensure Any import
            if "Any" in type_hint and "from typing import" not in content:
                lines.insert(0, "from typing import Any\n")

            path.write_text("".join(lines))
            return True

    return False


def main() -> None:
    """Run Phase 1 type fixes."""
    print("Getting Phase 1 errors...")
    errors = get_phase1_errors()

    print(f"\nFound errors:")
    print(f"  no-untyped-def: {len(errors['no-untyped-def'])}")
    print(f"  type-arg: {len(errors['type-arg'])}")
    print(f"  var-annotated: {len(errors['var-annotated'])}")
    print(f"  Total: {sum(len(v) for v in errors.values())}")

    # Fix each error type
    fixed_count = 0

    print("\nFixing no-untyped-def errors...")
    for file_path, line_num, message in errors["no-untyped-def"]:
        if fix_no_untyped_def(file_path, line_num, message):
            fixed_count += 1
            if fixed_count % 10 == 0:
                print(f"  Fixed {fixed_count} errors...")

    print(f"\nFixing type-arg errors...")
    for file_path, line_num, message in errors["type-arg"]:
        if fix_type_arg(file_path, line_num, message):
            fixed_count += 1
            if fixed_count % 10 == 0:
                print(f"  Fixed {fixed_count} errors...")

    print(f"\nFixing var-annotated errors...")
    for file_path, line_num, message in errors["var-annotated"]:
        if fix_var_annotated(file_path, line_num, message):
            fixed_count += 1
            if fixed_count % 10 == 0:
                print(f"  Fixed {fixed_count} errors...")

    print(f"\nTotal fixes applied: {fixed_count}")

    # Verify
    print("\nVerifying...")
    result = subprocess.run(
        ["zuban", "check", "acb/"],
        capture_output=True,
        text=True,
    )

    remaining = sum(1 for line in result.stderr.splitlines() if "error:" in line)
    print(f"Remaining errors: {remaining}")
    print(f"Target: ~766 errors (275 reduction from 1041)")


if __name__ == "__main__":
    main()
