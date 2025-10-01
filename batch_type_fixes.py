#!/usr/bin/env python3
"""Comprehensive batch type error fixes for ACB codebase.

This script systematically fixes the remaining type checking errors:
1. Duplicate definitions (no-redef) - 26 remaining
2. Missing type annotations (no-untyped-def) - 141 errors
3. Generic type parameters (type-arg) - 114 errors
4. Union type handling (union-attr) - 113 errors
5. Attribute errors (attr-defined) - 210 errors
"""

import re
import subprocess
from pathlib import Path
from collections import defaultdict


def get_errors_by_file() -> dict[str, list[tuple[int, str, str]]]:
    """Get all type errors grouped by file.

    Returns:
        Dict mapping file paths to list of (line_no, error_type, message) tuples
    """
    result = subprocess.run(
        ["zuban", "check", "acb/"],
        capture_output=True,
        text=True,
    )

    errors_by_file: dict[str, list[tuple[int, str, str]]] = defaultdict(list)

    for line in result.stderr.split("\n"):
        if "error:" not in line:
            continue

        # Parse: acb/file.py:123: error: Message [error-type]
        match = re.match(r"(.*?):(\d+): error: (.*?) \[(.*?)\]", line)
        if match:
            file_path, line_no, message, error_type = match.groups()
            errors_by_file[file_path].append((int(line_no), error_type, message))

    return errors_by_file


def fix_duplicate_definitions(file_path: Path) -> int:
    """Fix no-redef errors (duplicate definitions).

    Common patterns:
    - Variable redefinition in if/else blocks
    - Import shadowing
    - Loop variable reuse

    Returns:
        Number of fixes applied
    """
    content = file_path.read_text()
    lines = content.split("\n")
    fixes = 0

    # Pattern 1: Conditional redefinition - add type annotation to first occurrence
    # if condition:
    #     var = value1  # First definition
    # else:
    #     var = value2  # Redefines var

    # Pattern 2: Import shadowing - rename one of them
    # import foo
    # foo = something  # Shadows import

    # This is complex and file-specific, so we'll handle it manually
    return fixes


def fix_missing_annotations(file_path: Path, errors: list[tuple[int, str, str]]) -> int:
    """Fix no-untyped-def and var-annotated errors.

    Adds type annotations to functions and variables.

    Returns:
        Number of fixes applied
    """
    content = file_path.read_text()
    lines = content.split("\n")
    fixes = 0

    for line_no, error_type, message in errors:
        if error_type not in ("no-untyped-def", "var-annotated"):
            continue

        line_idx = line_no - 1
        if line_idx >= len(lines):
            continue

        line = lines[line_idx]

        # Pattern: Function missing return type
        if error_type == "no-untyped-def" and "def " in line:
            # def function(param) -> None:  # Add -> None if no return
            if " -> " not in line and ":" in line:
                line = line.replace(":", " -> None:", 1)
                lines[line_idx] = line
                fixes += 1

        # Pattern: Variable missing type annotation
        elif error_type == "var-annotated":
            # var = value  →  var: type = value
            # Requires context to determine type - skip for now
            pass

    if fixes > 0:
        file_path.write_text("\n".join(lines))

    return fixes


def fix_generic_types(file_path: Path, errors: list[tuple[int, str, str]]) -> int:
    """Fix type-arg errors (missing generic type parameters).

    Adds type parameters to generic collections:
    - list → list[Any]
    - dict → dict[str, Any]
    - set → set[Any]
    - tuple → tuple[Any, ...]

    Returns:
        Number of fixes applied
    """
    content = file_path.read_text()
    lines = content.split("\n")
    fixes = 0

    # Ensure typing imports
    if "from typing import Any" not in content and "import typing as t" not in content:
        # Find first import and add after it
        for i, line in enumerate(lines):
            if line.startswith("import ") or line.startswith("from "):
                lines.insert(i + 1, "from typing import Any")
                break

    for line_no, error_type, message in errors:
        if error_type != "type-arg":
            continue

        line_idx = line_no - 1
        if line_idx >= len(lines):
            continue

        line = lines[line_idx]

        # Pattern: Missing type parameter in annotation
        # variable: list = []  →  variable: list[Any] = []
        replacements = [
            (r"\blist\b(?!\[)", "list[Any]"),
            (r"\bdict\b(?!\[)", "dict[str, Any]"),
            (r"\bset\b(?!\[)", "set[Any]"),
            (r"\btuple\b(?!\[)", "tuple[Any, ...]"),
            (r"\bList\b(?!\[)", "List[Any]"),
            (r"\bDict\b(?!\[)", "Dict[str, Any]"),
            (r"\bSet\b(?!\[)", "Set[Any]"),
            (r"\bTuple\b(?!\[)", "Tuple[Any, ...]"),
        ]

        for pattern, replacement in replacements:
            new_line = re.sub(pattern, replacement, line)
            if new_line != line:
                lines[line_idx] = new_line
                fixes += 1
                break

    if fixes > 0:
        file_path.write_text("\n".join(lines))

    return fixes


def fix_union_attrs(file_path: Path, errors: list[tuple[int, str, str]]) -> int:
    """Fix union-attr errors (attribute access on Optional types).

    Adds None checks before attribute access:
    - if obj is not None: obj.attr
    - obj.attr if obj else default

    Returns:
        Number of fixes applied
    """
    content = file_path.read_text()
    lines = content.split("\n")
    fixes = 0

    for line_no, error_type, message in errors:
        if error_type != "union-attr":
            continue

        line_idx = line_no - 1
        if line_idx >= len(lines):
            continue

        line = lines[line_idx]

        # Pattern: Item "None" of "X | None" has no attribute "attr"
        match = re.search(r'Item "None" of ".*?" has no attribute "(.*?)"', message)
        if not match:
            continue

        attr_name = match.group(1)

        # Find the object being accessed
        # This is complex - often requires adding a None check earlier
        # Skip for now, handle manually
        pass

    return fixes


def fix_attr_defined_errors(file_path: Path, errors: list[tuple[int, str, str]]) -> int:
    """Fix attr-defined errors (attribute doesn't exist).

    Common patterns:
    - Settings class missing attributes
    - Mock objects missing attributes
    - Protocol violations

    Returns:
        Number of fixes applied
    """
    content = file_path.read_text()
    fixes = 0

    # This is highly file-specific and requires understanding the context
    # Most attr-defined errors need manual review

    return fixes


def main() -> None:
    """Run batch type fixes."""
    print("Analyzing type errors...")
    errors_by_file = get_errors_by_file()

    print(f"\nFound errors in {len(errors_by_file)} files")

    total_fixes = 0

    # Process each file
    for file_path_str, errors in sorted(errors_by_file.items()):
        if not file_path_str.startswith("acb/"):
            continue

        file_path = Path(file_path_str)
        if not file_path.exists():
            continue

        print(f"\nProcessing {file_path}...")

        # Apply fixes in order
        fixes = 0
        fixes += fix_duplicate_definitions(file_path)
        fixes += fix_missing_annotations(file_path, errors)
        fixes += fix_generic_types(file_path, errors)
        fixes += fix_union_attrs(file_path, errors)
        fixes += fix_attr_defined_errors(file_path, errors)

        if fixes > 0:
            print(f"  Applied {fixes} fixes")
            total_fixes += fixes

    print(f"\n✓ Total fixes applied: {total_fixes}")
    print("\nRun 'zuban check acb/' to verify fixes")


if __name__ == "__main__":
    main()
