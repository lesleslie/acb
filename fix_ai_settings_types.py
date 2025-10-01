#!/usr/bin/env python3
"""Fix AI adapter settings type inference issues.

This script adds property overrides to CloudAI, EdgeAI, and HybridAI classes
to specify their concrete settings types, fixing attr-defined errors.
"""

import re
from pathlib import Path


def add_settings_property(file_path: Path, class_name: str, settings_class: str) -> bool:
    """Add settings property override to AI adapter class.

    Args:
        file_path: Path to the file to modify
        class_name: Name of the AI adapter class (e.g., "CloudAI")
        settings_class: Name of the settings class (e.g., "CloudAISettings")

    Returns:
        True if file was modified, False otherwise
    """
    content = file_path.read_text()

    # Check if property already exists
    property_pattern = rf'^\s+@property\s+def settings\(self\) -> {settings_class}:'
    if re.search(property_pattern, content, re.MULTILINE):
        print(f"  ✓ {file_path.name}: Settings property already exists")
        return False

    # Find the __init__ method end to insert property after it
    init_pattern = rf'class {class_name}\(AIBase\):.*?def __init__\(self, \*\*kwargs: t\.Any\) -> None:.*?(?=\n    async def)'
    match = re.search(init_pattern, content, re.DOTALL)

    if not match:
        print(f"  ✗ {file_path.name}: Could not find {class_name}.__init__ method")
        return False

    # Insert property right after __init__
    init_end = match.end()
    property_code = f"""
    @property
    def settings(self) -> {settings_class}:
        \"\"\"Get adapter settings with correct type.\"\"\"
        if self._settings is None:
            msg = "Settings not initialized"
            raise RuntimeError(msg)
        return self._settings  # type: ignore[return-value]
"""

    new_content = content[:init_end] + property_code + content[init_end:]
    file_path.write_text(new_content)
    print(f"  ✓ {file_path.name}: Added settings property for {class_name}")
    return True


def main() -> None:
    """Fix AI adapter settings type issues."""
    print("Fixing AI adapter settings type inference...")

    base_path = Path(__file__).parent / "acb" / "adapters" / "ai"

    fixes = [
        (base_path / "cloud.py", "CloudAI", "CloudAISettings"),
        (base_path / "edge.py", "EdgeAI", "EdgeAISettings"),
        (base_path / "hybrid.py", "HybridAI", "HybridAISettings"),
    ]

    modified_count = 0
    for file_path, class_name, settings_class in fixes:
        if file_path.exists():
            print(f"\nProcessing {file_path.name}...")
            if add_settings_property(file_path, class_name, settings_class):
                modified_count += 1
        else:
            print(f"  ✗ {file_path}: File not found")

    print(f"\n✓ Modified {modified_count} files")


if __name__ == "__main__":
    main()
