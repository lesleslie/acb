#!/usr/bin/env python3
"""Test runner script for ACB project with various execution options.

This script provides a streamlined way to run tests with different configurations
and options for development, CI/CD, and performance testing.
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_command(cmd: str, description: str = "") -> int:
    """Run a shell command and return the exit code."""
    if description:
        print(f"\n{description}")
        print(f"Running: {cmd}")

    result = subprocess.run(cmd, shell=True, cwd=Path(__file__).parent)
    return result.returncode


def configure_parser():
    """Configure and return the argument parser."""
    parser = argparse.ArgumentParser(description="ACB Test Runner")
    parser.add_argument(
        "--unit", action="store_true", help="Run only unit tests (fast)"
    )
    parser.add_argument(
        "--integration",
        action="store_true",
        help="Run integration tests (requires --run-external flag)",
    )
    parser.add_argument(
        "--external",
        action="store_true",
        help="Include tests that require external services",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run tests in parallel (use with caution on external tests)",
    )
    parser.add_argument(
        "--coverage", action="store_true", help="Run tests with coverage report"
    )
    parser.add_argument(
        "--architecture", action="store_true", help="Run architecture validation tests"
    )
    parser.add_argument("--quick", action="store_true", help="Run only quick tests")
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Run benchmark tests (excludes parallel)",
    )
    parser.add_argument("--actions", action="store_true", help="Run only actions tests")
    parser.add_argument(
        "--adapters", action="store_true", help="Run only adapters tests"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--files", nargs="*", help="Specific test files to run")
    return parser


def build_command(args):
    """Build the pytest command based on arguments."""
    # Base pytest command
    base_cmd = ["python", "-m", "pytest"]

    if args.verbose:
        base_cmd.append("-v")

    pytest_cmd = " ".join(base_cmd)

    # Build command based on flags
    cmd_parts = [pytest_cmd]

    if args.coverage:
        cmd_parts.append("--cov=acb --cov-report=term-missing")

    marker_parts = []
    if args.unit:
        marker_parts.append("unit")

    if args.integration:
        marker_parts.append("integration")

    if args.architecture:
        marker_parts.append("architecture")

    if args.quick:
        marker_parts.append("quick")

    if args.benchmark:
        marker_parts.append("benchmark")

    if args.actions:
        marker_parts.append("actions")

    if args.adapters:
        marker_parts.append("adapters")

    # Combine all markers with 'and' if multiple are specified
    if marker_parts:
        marker_expr = " and ".join(marker_parts)
        cmd_parts.append(f"-m '{marker_expr}'")

    if args.external:
        cmd_parts.append("--run-external")

    # Add parallel execution if requested and not running benchmarks
    if args.parallel and not args.benchmark:
        cmd_parts.append("-n auto --dist=loadfile")

    if args.files:
        # If specific files/test selectors are provided, use them directly
        cmd_parts.append(" ".join(args.files))
    else:
        # Otherwise run tests from the tests directory
        cmd_parts.append("tests")

    return " ".join(cmd_parts)


def print_run_info(args):
    """Print information about what tests will be run."""
    print("ACB Test Runner")
    print("=" * 50)

    if args.files:
        print(f"Running specific files: {args.files}")
    else:
        print("Running tests from: tests/")

    if args.unit:
        print("Running: Unit tests only")
    elif args.integration:
        print("Running: Integration tests only")
    elif args.architecture:
        print("Running: Architecture validation tests only")
    elif args.quick:
        print("Running: Quick tests only")
    elif args.benchmark:
        print("Running: Benchmark tests only")
    elif args.actions:
        print("Running: Actions tests only")
    elif args.adapters:
        print("Running: Adapters tests only")
    else:
        print("Running: All tests")

    if args.parallel and not args.benchmark:
        print("With: Parallel execution")
    if args.coverage:
        print("With: Coverage report")
    if args.external:
        print("With: External services")

    print()


def main():
    parser = configure_parser()
    args = parser.parse_args()

    final_cmd = build_command(args)

    print_run_info(args)

    # Run the tests
    result = run_command(final_cmd, "Executing tests...")

    if result != 0:
        print(f"\nTests failed with exit code: {result}")
        sys.exit(result)

    print("\nTests completed successfully!")


if __name__ == "__main__":
    main()
