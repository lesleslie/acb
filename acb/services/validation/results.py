"""Validation result aggregation and error handling.

This module provides comprehensive result handling for the validation system,
including error reporting, warning aggregation, and validation reporting.
"""

from __future__ import annotations

import typing as t
from dataclasses import dataclass, field

if t.TYPE_CHECKING:
    from acb.services.validation._base import ValidationResult


class ValidationError(Exception):
    """Exception raised when validation fails."""

    def __init__(
        self,
        message: str,
        field_name: str | None = None,
        validation_result: ValidationResult | None = None,
    ) -> None:
        super().__init__(message)
        self.field_name = field_name
        self.validation_result = validation_result


class ValidationWarning(UserWarning):
    """Warning raised for non-critical validation issues."""

    def __init__(self, message: str, field_name: str | None = None) -> None:
        super().__init__(message)
        self.field_name = field_name


@dataclass
class ValidationReport:
    """Aggregated report of multiple validation results."""

    results: list[ValidationResult] = field(default_factory=list)
    total_time_ms: float = 0.0
    metadata: dict[str, t.Any] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        """Check if all validations passed."""
        return all(result.is_valid for result in self.results)

    @property
    def has_errors(self) -> bool:
        """Check if any results have errors."""
        return any(result.has_errors() for result in self.results)

    @property
    def has_warnings(self) -> bool:
        """Check if any results have warnings."""
        return any(result.has_warnings() for result in self.results)

    @property
    def error_count(self) -> int:
        """Get total number of errors."""
        return sum(len(result.errors) for result in self.results)

    @property
    def warning_count(self) -> int:
        """Get total number of warnings."""
        return sum(len(result.warnings) for result in self.results)

    @property
    def failed_validations(self) -> list[ValidationResult]:
        """Get list of failed validation results."""
        return [result for result in self.results if not result.is_valid]

    @property
    def successful_validations(self) -> list[ValidationResult]:
        """Get list of successful validation results."""
        return [result for result in self.results if result.is_valid]

    @property
    def average_validation_time_ms(self) -> float:
        """Get average validation time across all results."""
        if not self.results:
            return 0.0
        return sum(result.validation_time_ms for result in self.results) / len(
            self.results,
        )

    @property
    def max_validation_time_ms(self) -> float:
        """Get maximum validation time from all results."""
        if not self.results:
            return 0.0
        return max(result.validation_time_ms for result in self.results)

    def get_all_errors(self) -> list[str]:
        """Get all error messages from all results."""
        errors = []
        for result in self.results:
            for error in result.errors:
                field_info = (
                    f" (field: {result.field_name})" if result.field_name else ""
                )
                errors.append(f"{error}{field_info}")
        return errors

    def get_all_warnings(self) -> list[str]:
        """Get all warning messages from all results."""
        warnings = []
        for result in self.results:
            for warning in result.warnings:
                field_info = (
                    f" (field: {result.field_name})" if result.field_name else ""
                )
                warnings.append(f"{warning}{field_info}")
        return warnings

    def get_errors_by_field(self) -> dict[str, list[str]]:
        """Get errors grouped by field name."""
        errors_by_field: dict[str, list[str]] = {}
        for result in self.results:
            field_name = result.field_name or "unknown"
            if result.errors:
                errors_by_field.setdefault(field_name, []).extend(result.errors)
        return errors_by_field

    def get_warnings_by_field(self) -> dict[str, list[str]]:
        """Get warnings grouped by field name."""
        warnings_by_field: dict[str, list[str]] = {}
        for result in self.results:
            field_name = result.field_name or "unknown"
            if result.warnings:
                warnings_by_field.setdefault(field_name, []).extend(result.warnings)
        return warnings_by_field

    def add_result(self, result: ValidationResult) -> None:
        """Add a validation result to the report."""
        self.results.append(result)

    def add_results(self, results: list[ValidationResult]) -> None:
        """Add multiple validation results to the report."""
        self.results.extend(results)

    def to_dict(self) -> dict[str, t.Any]:
        """Convert report to dictionary representation."""
        return {
            "is_valid": self.is_valid,
            "has_errors": self.has_errors,
            "has_warnings": self.has_warnings,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "total_validations": len(self.results),
            "successful_validations": len(self.successful_validations),
            "failed_validations": len(self.failed_validations),
            "total_time_ms": self.total_time_ms,
            "average_validation_time_ms": self.average_validation_time_ms,
            "max_validation_time_ms": self.max_validation_time_ms,
            "errors": self.get_all_errors(),
            "warnings": self.get_all_warnings(),
            "errors_by_field": self.get_errors_by_field(),
            "warnings_by_field": self.get_warnings_by_field(),
            "metadata": self.metadata,
        }

    def to_summary(self) -> str:
        """Generate a human-readable summary of the report."""
        lines = [
            f"Validation Report: {'PASSED' if self.is_valid else 'FAILED'}",
            f"Total validations: {len(self.results)}",
            f"Successful: {len(self.successful_validations)}",
            f"Failed: {len(self.failed_validations)}",
        ]

        if self.has_errors:
            lines.append(f"Errors: {self.error_count}")
            for error in self.get_all_errors()[:5]:  # Show first 5 errors
                lines.append(f"  - {error}")
            if self.error_count > 5:
                lines.append(f"  ... and {self.error_count - 5} more errors")

        if self.has_warnings:
            lines.append(f"Warnings: {self.warning_count}")
            for warning in self.get_all_warnings()[:3]:  # Show first 3 warnings
                lines.append(f"  - {warning}")
            if self.warning_count > 3:
                lines.append(f"  ... and {self.warning_count - 3} more warnings")

        lines.append(
            f"Performance: {self.average_validation_time_ms:.2f}ms avg, "
            f"{self.max_validation_time_ms:.2f}ms max",
        )

        return "\n".join(lines)


class ValidationResultBuilder:
    """Builder for constructing validation results and reports."""

    def __init__(self) -> None:
        self._results: list[ValidationResult] = []
        self._total_time_ms: float = 0.0
        self._metadata: dict[str, t.Any] = {}

    def add_result(self, result: ValidationResult) -> ValidationResultBuilder:
        """Add a validation result."""
        self._results.append(result)
        self._total_time_ms += result.validation_time_ms
        return self

    def add_results(self, results: list[ValidationResult]) -> ValidationResultBuilder:
        """Add multiple validation results."""
        self._results.extend(results)
        self._total_time_ms += sum(result.validation_time_ms for result in results)
        return self

    def set_metadata(self, key: str, value: t.Any) -> ValidationResultBuilder:
        """Set metadata for the report."""
        self._metadata[key] = value
        return self

    def set_all_metadata(self, metadata: dict[str, t.Any]) -> ValidationResultBuilder:
        """Set all metadata for the report."""
        self._metadata = metadata.copy()
        return self

    def build(self) -> ValidationReport:
        """Build the validation report."""
        return ValidationReport(
            results=self._results.copy(),
            total_time_ms=self._total_time_ms,
            metadata=self._metadata.copy(),
        )

    def build_and_raise_on_error(self) -> ValidationReport:
        """Build the report and raise ValidationError if any validation failed."""
        report = self.build()

        if not report.is_valid:
            errors = report.get_all_errors()
            error_message = (
                f"Validation failed with {len(errors)} errors: " + "; ".join(errors[:3])
            )
            if len(errors) > 3:
                error_message += f" ... and {len(errors) - 3} more errors"

            raise ValidationError(error_message)

        return report
