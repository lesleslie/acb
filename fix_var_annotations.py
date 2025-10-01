#!/usr/bin/env python3
"""Fix var-annotated errors by adding type annotations to variable assignments."""

import re
import subprocess
from pathlib import Path
from collections import defaultdict


def get_var_annotated_errors() -> dict[str, list[tuple[int, str]]]:
    """Get all var-annotated errors grouped by file.

    Returns:
        Dict mapping file paths to list of (line_no, variable_name) tuples
    """
    result = subprocess.run(
        ["zuban", "check", "acb/"],
        capture_output=True,
        text=True,
    )

    errors_by_file: dict[str, list[tuple[int, str]]] = defaultdict(list)

    for line in result.stderr.split("\n"):
        if "var-annotated" not in line:
            continue

        # Parse: acb/file.py:123: error: Need type annotation for "var_name"
        match = re.match(r"(.*?):(\d+):.*Need type annotation for \"(.*?)\"", line)
        if match:
            file_path, line_no, var_name = match.groups()
            errors_by_file[file_path].append((int(line_no), var_name))

    return errors_by_file


def fix_file(file_path: Path, errors: list[tuple[int, str]]) -> int:
    """Add type annotations to variables in file.

    Args:
        file_path: Path to file to fix
        errors: List of (line_no, var_name) tuples

    Returns:
        Number of fixes applied
    """
    content = file_path.read_text()
    lines = content.split("\n")
    fixes = 0

    # Check if typing imports exist
    has_typing_import = any(
        "from typing import" in line or "import typing" in line
        for line in lines
    )

    if not has_typing_import:
        # Add typing import after first import
        for i, line in enumerate(lines):
            if line.startswith(("import ", "from ")):
                lines.insert(i + 1, "from typing import Any")
                break

    for line_no, var_name in errors:
        line_idx = line_no - 1
        if line_idx >= len(lines):
            continue

        line = lines[line_idx]

        # Pattern: var = {}  →  var: dict[str, Any] = {}
        if f"{var_name} = {{}}" in line or f"{var_name} ={{}}" in line:
            new_line = line.replace(
                f"{var_name} =",
                f"{var_name}: dict[str, Any] ="
            )
            lines[line_idx] = new_line
            fixes += 1

        # Pattern: var = []  →  var: list[Any] = []
        elif f"{var_name} = []" in line or f"{var_name} =[]" in line:
            new_line = line.replace(
                f"{var_name} =",
                f"{var_name}: list[Any] ="
            )
            lines[line_idx] = new_line
            fixes += 1

        # Pattern: var = set()  →  var: set[Any] = set()
        elif f"{var_name} = set()" in line:
            new_line = line.replace(
                f"{var_name} =",
                f"{var_name}: set[Any] ="
            )
            lines[line_idx] = new_line
            fixes += 1

        # Pattern: var = something (generic case)
        # Try to infer type from context
        elif " = " in line:
            # Check for common patterns
            if "defaultdict(" in line:
                new_line = line.replace(
                    f"{var_name} =",
                    f"{var_name}: defaultdict[str, Any] ="
                )
            elif "Counter(" in line:
                new_line = line.replace(
                    f"{var_name} =",
                    f"{var_name}: Counter[str] ="
                )
            else:
                # Default to Any
                new_line = line.replace(
                    f"{var_name} =",
                    f"{var_name}: Any ="
                )

            lines[line_idx] = new_line
            fixes += 1

    if fixes > 0:
        file_path.write_text("\n".join(lines))

    return fixes


def main() -> None:
    """Fix all var-annotated errors."""
    print("Finding var-annotated errors...")
    errors_by_file = get_var_annotated_errors()

    if not errors_by_file:
        print("No var-annotated errors found!")
        return

    print(f"\nFound errors in {len(errors_by_file)} files")

    total_fixes = 0

    for file_path_str, errors in sorted(errors_by_file.items()):
        file_path = Path(file_path_str)
        if not file_path.exists():
            continue

        print(f"\nProcessing {file_path.name}...")
        print(f"  Variables: {', '.join(var for _, var in errors)}")

        fixes = fix_file(file_path, errors)
        if fixes > 0:
            print(f"  ✓ Applied {fixes} fixes")
            total_fixes += fixes

    print(f"\n✓ Total fixes: {total_fixes}")
    print("\nRunning zuban check to verify...")

    # Quick verification
    result = subprocess.run(
        ["zuban", "check", "acb/"],
        capture_output=True,
        text=True,
    )
    new_count = result.stderr.count("var-annotated")
    print(f"Remaining var-annotated errors: {new_count}")


if __name__ == "__main__":
    main()
