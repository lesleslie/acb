"""Production-ready parser for crackerjack hook output.

This module provides robust parsing of hook output lines in the format:
    hook_name + padding_dots + single_space + status_marker

The parser uses reverse string parsing to reliably extract hook names
regardless of their content (including dots, dashes, underscores, etc.).
"""

from __future__ import annotations

from typing import NamedTuple


class HookResult(NamedTuple):
    """Parsed hook result containing name and status.

    Attributes:
        hook_name: The name of the hook (may contain dots, dashes, etc.)
        passed: True if hook passed, False if failed
    """

    hook_name: str
    passed: bool


class ParseError(ValueError):
    """Raised when a line cannot be parsed as valid hook output."""



# Status marker definitions
_PASS_MARKERS = frozenset(["✅", "Passed"])
_FAIL_MARKERS = frozenset(["❌", "Failed"])
_ALL_MARKERS = _PASS_MARKERS | _FAIL_MARKERS


def parse_hook_line(line: str) -> HookResult:
    """Parse a crackerjack hook output line into name and status.

    The format is: hook_name + padding_dots + single_space + status_marker

    Examples:
        >>> parse_hook_line("refurb................................................................ ❌")
        HookResult(hook_name='refurb', passed=False)

        >>> parse_hook_line("my...custom...hook.................................................... ✅")
        HookResult(hook_name='my...custom...hook', passed=True)

        >>> parse_hook_line("test.integration.api.................................................. Passed")
        HookResult(hook_name='test.integration.api', passed=True)

    Args:
        line: A single line of hook output to parse

    Returns:
        HookResult with extracted hook_name and passed status

    Raises:
        ParseError: If line is empty, has no valid status marker, or is malformed
    """
    # Handle empty/whitespace-only lines
    stripped = line.strip()
    if not stripped:
        msg = "Cannot parse empty line"
        raise ParseError(msg)

    # Step 1: Extract status marker from end (reverse parse)
    # Status markers are always at the end after a space
    parts = stripped.rsplit(maxsplit=1)

    if len(parts) == 1:
        # Only one part means no space in the line
        # Check if it's just a status marker without hook name
        if parts[0] in _ALL_MARKERS:
            msg = "No hook name found before status marker"
            raise ParseError(msg)
        msg = f"Line has no space-separated status marker: {line!r}"
        raise ParseError(msg)

    if len(parts) != 2:
        msg = f"Line has no space-separated status marker: {line!r}"
        raise ParseError(msg)

    left_part, status_marker = parts

    # Step 2: Validate status marker
    if status_marker not in _ALL_MARKERS:
        msg = f"Unknown status marker: {status_marker!r}"
        raise ParseError(msg)

    passed = status_marker in _PASS_MARKERS

    # Step 3: Extract hook name from left part
    # The left part is: hook_name + padding_dots
    # We need to strip the padding dots from the right
    if not left_part:
        msg = "No hook name found before status marker"
        raise ParseError(msg)

    # Remove padding dots by stripping from the right
    # The hook name is everything before the continuous sequence of dots
    hook_name = left_part.rstrip(".")

    # Validate that we actually found a hook name
    if not hook_name:
        msg = "Hook name consists entirely of dots"
        raise ParseError(msg)

    # Edge case: Ensure there were actually padding dots
    # (otherwise the format is invalid - should have padding)
    if hook_name == left_part:
        # No dots were stripped, which means no padding - this might be valid
        # for very short hook names, but we should warn
        # For production, we'll allow it but could add logging here
        pass

    return HookResult(hook_name=hook_name, passed=passed)


def parse_hook_output(output: str) -> list[HookResult]:
    """Parse multiple lines of crackerjack hook output.

    Skips empty lines and returns parsed results for valid lines.
    Invalid lines raise ParseError with context.

    Args:
        output: Multi-line string of hook output

    Returns:
        List of HookResult objects in order

    Raises:
        ParseError: If any non-empty line cannot be parsed
    """
    results: list[HookResult] = []

    for line_num, line in enumerate(output.splitlines(), start=1):
        # Skip empty lines
        if not line.strip():
            continue

        try:
            result = parse_hook_line(line)
            results.append(result)
        except ParseError as e:
            # Add line number context for debugging
            msg = f"Line {line_num}: {e}"
            raise ParseError(msg) from e

    return results


# Convenience function for common use case
def extract_failed_hooks(output: str) -> list[str]:
    """Extract names of all failed hooks from output.

    Args:
        output: Multi-line string of hook output

    Returns:
        List of hook names that failed
    """
    results = parse_hook_output(output)
    return [result.hook_name for result in results if not result.passed]
