"""Comprehensive tests for hook_parser module."""

from __future__ import annotations

import pytest
from hook_parser import (
    HookResult,
    ParseError,
    extract_failed_hooks,
    parse_hook_line,
    parse_hook_output,
)


class TestParseHookLine:
    """Test parse_hook_line function with various inputs."""

    def test_simple_pass(self) -> None:
        """Test simple hook name with pass marker."""
        result = parse_hook_line("refurb................................................................ ✅")
        assert result == HookResult(hook_name="refurb", passed=True)

    def test_simple_fail(self) -> None:
        """Test simple hook name with fail marker."""
        result = parse_hook_line("refurb................................................................ ❌")
        assert result == HookResult(hook_name="refurb", passed=False)

    def test_dots_in_name_pass(self) -> None:
        """Test hook name containing dots with pass marker."""
        result = parse_hook_line("my...custom...hook.................................................... ✅")
        assert result == HookResult(hook_name="my...custom...hook", passed=True)

    def test_dots_in_name_fail(self) -> None:
        """Test hook name containing dots with fail marker."""
        result = parse_hook_line("test.integration.api.................................................. ❌")
        assert result == HookResult(hook_name="test.integration.api", passed=False)

    def test_single_dot_in_name(self) -> None:
        """Test hook name with single dots (common pattern)."""
        result = parse_hook_line("pytest.unit....................................................... Passed")
        assert result == HookResult(hook_name="pytest.unit", passed=True)

    def test_triple_dots_in_name(self) -> None:
        """Test hook name with triple dots (ellipsis)."""
        result = parse_hook_line("my...hook............................................................. ✅")
        assert result == HookResult(hook_name="my...hook", passed=True)

    def test_dashes_in_name(self) -> None:
        """Test hook name with dashes."""
        result = parse_hook_line("hook-with-dashes...................................................... ✅")
        assert result == HookResult(hook_name="hook-with-dashes", passed=True)

    def test_underscores_in_name(self) -> None:
        """Test hook name with underscores."""
        result = parse_hook_line("my_custom_hook........................................................ Failed")
        assert result == HookResult(hook_name="my_custom_hook", passed=False)

    def test_mixed_special_chars(self) -> None:
        """Test hook name with mixed special characters."""
        result = parse_hook_line("test-my.custom_hook................................................... ✅")
        assert result == HookResult(hook_name="test-my.custom_hook", passed=True)

    def test_text_status_passed(self) -> None:
        """Test with 'Passed' text status marker."""
        result = parse_hook_line("ruff.................................................................. Passed")
        assert result == HookResult(hook_name="ruff", passed=True)

    def test_text_status_failed(self) -> None:
        """Test with 'Failed' text status marker."""
        result = parse_hook_line("bandit................................................................ Failed")
        assert result == HookResult(hook_name="bandit", passed=False)

    def test_very_short_name(self) -> None:
        """Test very short hook name."""
        result = parse_hook_line("py.................................................................... ✅")
        assert result == HookResult(hook_name="py", passed=True)

    def test_very_long_name(self) -> None:
        """Test very long hook name with minimal padding."""
        result = parse_hook_line(
            "very.long.hook.name.with.many.segments.for.testing.purposes...... ✅",
        )
        assert result == HookResult(
            hook_name="very.long.hook.name.with.many.segments.for.testing.purposes", passed=True,
        )

    def test_minimal_padding(self) -> None:
        """Test hook with minimal dot padding."""
        result = parse_hook_line("longhookname.. ✅")
        assert result == HookResult(hook_name="longhookname", passed=True)

    def test_single_dot_padding(self) -> None:
        """Test hook with single dot padding."""
        result = parse_hook_line("hook. ✅")
        assert result == HookResult(hook_name="hook", passed=True)

    def test_numeric_in_name(self) -> None:
        """Test hook name with numbers."""
        result = parse_hook_line("test123........................................................... ✅")
        assert result == HookResult(hook_name="test123", passed=True)

    def test_unicode_in_name(self) -> None:
        """Test hook name with unicode characters."""
        result = parse_hook_line("test_émoji_🎯.................................................... ✅")
        assert result == HookResult(hook_name="test_émoji_🎯", passed=True)

    def test_leading_whitespace_stripped(self) -> None:
        """Test that leading whitespace is properly handled."""
        result = parse_hook_line("  refurb.............................................................. ✅")
        assert result == HookResult(hook_name="refurb", passed=True)

    def test_trailing_whitespace_stripped(self) -> None:
        """Test that trailing whitespace is properly handled."""
        result = parse_hook_line("refurb................................................................ ✅  ")
        assert result == HookResult(hook_name="refurb", passed=True)

    # Error cases

    def test_empty_line_error(self) -> None:
        """Test that empty line raises ParseError."""
        with pytest.raises(ParseError, match="Cannot parse empty line"):
            parse_hook_line("")

    def test_whitespace_only_error(self) -> None:
        """Test that whitespace-only line raises ParseError."""
        with pytest.raises(ParseError, match="Cannot parse empty line"):
            parse_hook_line("   \t\n  ")

    def test_no_status_marker_error(self) -> None:
        """Test that line without status marker raises ParseError."""
        with pytest.raises(ParseError, match="no space-separated status marker"):
            parse_hook_line("refurb................................................................")

    def test_invalid_status_marker_error(self) -> None:
        """Test that invalid status marker raises ParseError."""
        with pytest.raises(ParseError, match="Unknown status marker"):
            parse_hook_line("refurb................................................................ INVALID")

    def test_only_status_marker_error(self) -> None:
        """Test that line with only status marker raises ParseError."""
        with pytest.raises(ParseError, match="No hook name found"):
            parse_hook_line("✅")

    def test_only_dots_and_marker_error(self) -> None:
        """Test that line with only dots and marker raises ParseError."""
        with pytest.raises(ParseError, match="Hook name consists entirely of dots"):
            parse_hook_line("..................................................................... ✅")

    def test_no_space_before_marker_error(self) -> None:
        """Test that missing space before marker raises ParseError."""
        with pytest.raises(ParseError, match="no space-separated status marker"):
            parse_hook_line("refurb................................................................✅")

    def test_multiple_spaces_before_marker(self) -> None:
        """Test multiple spaces before marker (should work with rsplit)."""
        result = parse_hook_line("refurb...............................................................   ✅")
        assert result == HookResult(hook_name="refurb", passed=True)

    def test_emoji_status_only(self) -> None:
        """Test that emoji status markers work correctly."""
        # Test both emoji markers
        pass_result = parse_hook_line("test. ✅")
        fail_result = parse_hook_line("test. ❌")
        assert pass_result.passed is True
        assert fail_result.passed is False


class TestParseHookOutput:
    """Test parse_hook_output function with multiple lines."""

    def test_multiple_lines_mixed_status(self) -> None:
        """Test parsing multiple lines with mixed pass/fail status."""
        output = """refurb................................................................ ✅
bandit................................................................ ❌
pytest................................................................ Passed
ruff.................................................................. Failed"""

        results = parse_hook_output(output)

        assert len(results) == 4
        assert results[0] == HookResult(hook_name="refurb", passed=True)
        assert results[1] == HookResult(hook_name="bandit", passed=False)
        assert results[2] == HookResult(hook_name="pytest", passed=True)
        assert results[3] == HookResult(hook_name="ruff", passed=False)

    def test_empty_lines_skipped(self) -> None:
        """Test that empty lines are skipped."""
        output = """refurb................................................................ ✅

bandit................................................................ ❌

pytest................................................................ ✅"""

        results = parse_hook_output(output)
        assert len(results) == 3

    def test_whitespace_lines_skipped(self) -> None:
        """Test that whitespace-only lines are skipped."""
        output = """refurb................................................................ ✅

\t
bandit................................................................ ❌"""

        results = parse_hook_output(output)
        assert len(results) == 2

    def test_invalid_line_with_context(self) -> None:
        """Test that invalid line includes line number in error."""
        output = """refurb................................................................ ✅
invalid line here
bandit................................................................ ❌"""

        with pytest.raises(ParseError, match="Line 2:"):
            parse_hook_output(output)

    def test_empty_output(self) -> None:
        """Test empty output returns empty list."""
        assert parse_hook_output("") == []

    def test_single_line(self) -> None:
        """Test single line output."""
        output = "refurb................................................................ ✅"
        results = parse_hook_output(output)
        assert len(results) == 1
        assert results[0].hook_name == "refurb"


class TestExtractFailedHooks:
    """Test extract_failed_hooks convenience function."""

    def test_extract_only_failed(self) -> None:
        """Test extraction of only failed hooks."""
        output = """refurb................................................................ ✅
bandit................................................................ ❌
pytest................................................................ Passed
ruff.................................................................. Failed
mypy.................................................................. ✅"""

        failed = extract_failed_hooks(output)
        assert failed == ["bandit", "ruff"]

    def test_all_passed_returns_empty(self) -> None:
        """Test that all passing hooks returns empty list."""
        output = """refurb................................................................ ✅
bandit................................................................ Passed
pytest................................................................ ✅"""

        failed = extract_failed_hooks(output)
        assert failed == []

    def test_all_failed_returns_all(self) -> None:
        """Test that all failing hooks returns all names."""
        output = """refurb................................................................ ❌
bandit................................................................ Failed
pytest................................................................ ❌"""

        failed = extract_failed_hooks(output)
        assert failed == ["refurb", "bandit", "pytest"]

    def test_empty_output_returns_empty(self) -> None:
        """Test empty output returns empty list."""
        assert extract_failed_hooks("") == []


class TestEdgeCases:
    """Test edge cases and unusual inputs."""

    def test_hook_name_ends_with_single_dot(self) -> None:
        """Test hook name that ends with a single dot."""
        result = parse_hook_line("hook....... ✅")
        assert result.hook_name == "hook"

    def test_hook_name_ends_with_multiple_dots(self) -> None:
        """Test hook name that ends with multiple dots."""
        result = parse_hook_line("my.hook....... ✅")
        assert result.hook_name == "my.hook"

    def test_consecutive_dots_in_middle(self) -> None:
        """Test hook name with consecutive dots in the middle."""
        result = parse_hook_line("my....test....hook................................ ✅")
        assert result.hook_name == "my....test....hook"

    def test_real_world_crackerjack_output(self) -> None:
        """Test with realistic crackerjack output format."""
        # Simulate actual crackerjack pre-commit output
        output = """refurb................................................................ ✅
bandit................................................................ ✅
pyright............................................................... ❌
ruff.................................................................. ✅
pyproject-fmt......................................................... ✅
vulture............................................................... ✅
creosote.............................................................. ✅"""

        results = parse_hook_output(output)
        assert len(results) == 7

        failed = [r.hook_name for r in results if not r.passed]
        assert failed == ["pyright"]

        passed = [r.hook_name for r in results if r.passed]
        assert len(passed) == 6

    def test_padding_alignment_verification(self) -> None:
        """Verify that parsing works regardless of padding length."""
        # Different length names should all parse correctly
        lines = [
            "a..................................................................... ✅",
            "abc................................................................... ✅",
            "abcdefghij............................................................ ✅",
            "very.long.hook.name.with.many.parts.................................. ✅",
        ]

        for line in lines:
            result = parse_hook_line(line)
            assert result.passed is True
            # Each should extract the correct hook name
            line.split(".")[0] if "." in line else line.split()[0]
            # For names with dots, we need to extract up to the padding
            left_part = line.rsplit(maxsplit=1)[0]
            expected_name = left_part.rstrip(".")
            assert result.hook_name == expected_name


class TestPerformance:
    """Performance characteristics tests."""

    def test_large_output_performance(self) -> None:
        """Test parsing large output is reasonably fast."""
        import time

        # Generate 1000 lines of output
        lines = [
            f"hook.name.{i}..................................................... ✅"
            for i in range(1000)
        ]
        output = "\n".join(lines)

        start = time.perf_counter()
        results = parse_hook_output(output)
        elapsed = time.perf_counter() - start

        assert len(results) == 1000
        # Should complete in well under 1 second for 1000 lines
        assert elapsed < 1.0, f"Parsing too slow: {elapsed:.3f}s for 1000 lines"

    def test_single_line_performance(self) -> None:
        """Test that single line parsing is fast (for hot path)."""
        import time

        line = "test.integration.api.................................................. ✅"

        # Parse 10000 times
        start = time.perf_counter()
        for _ in range(10000):
            parse_hook_line(line)
        elapsed = time.perf_counter() - start

        # Should complete 10k parses in well under 1 second
        assert elapsed < 1.0, f"Single line parsing too slow: {elapsed:.3f}s for 10k iterations"
