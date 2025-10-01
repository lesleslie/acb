#!/usr/bin/env python3
"""Apply refurb FURB107 (exception suppression) transformations automatically."""

import re
import subprocess
from pathlib import Path

def get_files_with_furb107():
    """Get list of files with FURB107 violations."""
    result = subprocess.run(
        ["python", "-m", "refurb", "acb/"],
        capture_output=True,
        text=True,
    )

    files = set()
    for line in result.stdout.split("\n"):
        if "FURB107" in line:
            file_path = line.split(":")[0]
            files.add(file_path)

    return sorted(files)

def add_suppress_import(content: str) -> str:
    """Add suppress import if not present."""
    if "from contextlib import suppress" in content:
        return content

    # Find the first import line
    lines = content.split("\n")
    import_idx = -1
    for i, line in enumerate(lines):
        if line.startswith("import ") or line.startswith("from "):
            import_idx = i
            break

    if import_idx >= 0:
        # Find the end of the import block
        for i in range(import_idx + 1, len(lines)):
            if not lines[i].startswith(("import ", "from ")) and lines[i].strip():
                # Insert before first non-import line
                lines.insert(i, "from contextlib import suppress")
                return "\n".join(lines)

    # Fallback: add after first import
    lines.insert(import_idx + 1, "from contextlib import suppress")
    return "\n".join(lines)

def transform_suppress_pattern(content: str) -> str:
    """Transform try/except pass patterns to suppress()."""

    # Pattern 1: Simple single-line try/except
    # try:
    #     some_code()
    # except Exception:
    #     pass
    pattern1 = re.compile(
        r"(\s*)try:\n"
        r"(\s+)(.*?)\n"
        r"\1except ([\w, ]+):\n"
        r"\1    pass",
        re.MULTILINE
    )

    def replace_simple(match):
        indent = match.group(1)
        code_indent = match.group(2)
        code = match.group(3)
        exceptions = match.group(4)

        # Single line of code - use single line suppress
        return f"{indent}with suppress({exceptions}):\n{code_indent}{code}"

    content = pattern1.sub(replace_simple, content)

    # Pattern 2: Multi-line try/except blocks
    # More complex - need to handle indentation properly
    # This will require iterative processing

    return content

def process_file(file_path: str):
    """Process a single file."""
    path = Path(file_path)
    if not path.exists():
        print(f"Skipping {file_path} (not found)")
        return

    content = path.read_text()
    original = content

    # Add suppress import if needed
    content = add_suppress_import(content)

    # Apply transformations
    content = transform_suppress_pattern(content)

    if content != original:
        path.write_text(content)
        print(f"Updated {file_path}")
    else:
        print(f"No changes needed for {file_path}")

def main():
    """Main entry point."""
    files = get_files_with_furb107()
    print(f"Found {len(files)} files with FURB107 violations")

    for file_path in files:
        process_file(file_path)

if __name__ == "__main__":
    main()
