#!/usr/bin/env python3
"""Fix syntax errors introduced by type annotation script."""

import re
import subprocess
from pathlib import Path


def fix_double_parens() -> int:
    """Fix double parentheses in function signatures."""
    result = subprocess.run(
        ["zuban", "check", "acb/"],
        capture_output=True,
        text=True,
    )

    fixed = 0
    files_to_fix: dict[str, list[int]] = {}

    # Find all syntax errors
    for line in (result.stdout + "\n" + result.stderr).splitlines():
        if "invalid syntax" in line:
            match = re.match(r"^(.+?):(\d+):", line)
            if match:
                file_path, line_num = match.groups()
                if file_path not in files_to_fix:
                    files_to_fix[file_path] = []
                files_to_fix[file_path].append(int(line_num))

    # Fix each file
    for file_path, line_nums in files_to_fix.items():
        path = Path(file_path)
        if not path.exists():
            continue

        content = path.read_text()
        lines = content.splitlines(keepends=True)

        for line_num in line_nums:
            if line_num > len(lines):
                continue

            target_line = lines[line_num - 1]

            # Fix double parentheses in function signatures
            # Pattern: def func((arg: Type))
            new_line = re.sub(r'\(\(([^)]+)\)\)', r'(\1)', target_line)

            # Fix extra space after def
            new_line = re.sub(r'def\s\s+', 'def ', new_line)

            # Fix __aexit__ signature
            new_line = re.sub(
                r'__aexit__\(\(self: Any, exc_type: Any, exc_val: Any, exc_tb: Any\)\)',
                '__aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any)',
                new_line
            )

            if new_line != target_line:
                lines[line_num - 1] = new_line
                fixed += 1

        path.write_text("".join(lines))

    return fixed


def main() -> None:
    """Fix syntax errors."""
    print("Fixing syntax errors...")
    fixed = fix_double_parens()
    print(f"Fixed {fixed} syntax errors")

    # Verify
    result = subprocess.run(
        ["zuban", "check", "acb/"],
        capture_output=True,
        text=True,
    )

    remaining_syntax = sum(
        1 for line in (result.stdout + result.stderr).splitlines()
        if "invalid syntax" in line
    )

    total_errors = sum(
        1 for line in (result.stdout + result.stderr).splitlines()
        if "error:" in line
    )

    print(f"\nRemaining syntax errors: {remaining_syntax}")
    print(f"Total errors: {total_errors}")


if __name__ == "__main__":
    main()
