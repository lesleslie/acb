from typing import Any

"""Security Test Provider for ACB Testing.

Provides security testing utilities, vulnerability scanning,
and authentication testing for ACB applications.

Features:
- Security vulnerability scanning
- Authentication and authorization testing
- Input validation and sanitization testing
- SQL injection and XSS detection
- Security configuration validation
"""

import re
from unittest.mock import AsyncMock

import typing as t
from contextlib import asynccontextmanager

from acb.testing.discovery import (
    TestProviderCapability,
    create_test_provider_metadata_template,
)

# Provider metadata
PROVIDER_METADATA = create_test_provider_metadata_template(
    name="Security Test Provider",
    category="security",
    provider_type="security_test",
    author="ACB Testing Team",
    description="Security testing and vulnerability scanning utilities for ACB applications",
    version="1.0.0",
    capabilities=[
        TestProviderCapability.SECURITY_SCANNING,
        TestProviderCapability.VULNERABILITY_TESTING,
        TestProviderCapability.AUTH_TESTING,
    ],
    settings_class="SecurityTestProviderSettings",
)


class SecurityTestProvider:
    """Provider for security testing utilities."""

    PROVIDER_METADATA = PROVIDER_METADATA

    def __init__(self) -> None:
        self._scan_results: dict[str, t.Any] = {}
        self._vulnerability_patterns = self._load_vulnerability_patterns()

    def _load_vulnerability_patterns(self) -> dict[str, list[str]]:
        """Load vulnerability detection patterns."""
        return {
            "sql_injection": [
                r"(?i)(union\s+select|select.*from|insert\s+into|delete\s+from|drop\s+table)",
                r"(?i)(\'\s*or\s*\'\d+\'\s*=\s*\'\d+|\'\s*or\s*1\s*=\s*1)",
                r"(?i)(exec\s*\(|execute\s+immediate)",
            ],
            "xss": [
                r"<script[^>]*>.*?</script>",
                r"javascript:",
                r"on\w+\s*=",
                r"<iframe[^>]*>",
                r"<object[^>]*>",
            ],
            "path_traversal": [
                r"\.\./",
                r"\.\.\\",
                r"(?i)(etc/passwd|boot\.ini|windows/system32)",
            ],
            "command_injection": [
                r";\s*(cat|ls|dir|type|ping|wget|curl)",
                r"\|\s*(cat|ls|dir|type|ping|wget|curl)",
                r"&&\s*(cat|ls|dir|type|ping|wget|curl)",
                r"`.*`",
                r"\$\(.*\)",
            ],
        }

    def scan_for_vulnerabilities(self, input_data: str) -> dict[str, t.Any]:
        """Scan input data for common vulnerabilities."""
        vulnerabilities = []

        for vuln_type, patterns in self._vulnerability_patterns.items():
            for pattern in patterns:
                if re.search(
                    pattern,
                    input_data,
                ):  # REGEX OK: security vulnerability scanning
                    vulnerabilities.append(
                        {
                            "type": vuln_type,
                            "pattern": pattern,
                            "severity": self._get_severity(vuln_type),
                            "description": self._get_vulnerability_description(
                                vuln_type,
                            ),
                        },
                    )

        return {
            "input": input_data,
            "vulnerabilities_found": len(vulnerabilities),
            "vulnerabilities": vulnerabilities,
            "risk_level": self._calculate_risk_level(vulnerabilities),
            "scan_timestamp": "2024-01-01T12:00:00Z",
        }

    def _get_severity(self, vuln_type: str) -> str:
        """Get severity level for vulnerability type."""
        severity_map = {
            "sql_injection": "HIGH",
            "xss": "MEDIUM",
            "path_traversal": "HIGH",
            "command_injection": "CRITICAL",
        }
        return severity_map.get(vuln_type, "MEDIUM")

    def _get_vulnerability_description(self, vuln_type: str) -> str:
        """Get description for vulnerability type."""
        descriptions = {
            "sql_injection": "Potential SQL injection vulnerability detected",
            "xss": "Cross-site scripting (XSS) vulnerability detected",
            "path_traversal": "Path traversal vulnerability detected",
            "command_injection": "Command injection vulnerability detected",
        }
        return descriptions.get(vuln_type, "Unknown vulnerability type")

    def _calculate_risk_level(self, vulnerabilities: list[dict[str, Any]]) -> str:
        """Calculate overall risk level."""
        if not vulnerabilities:
            return "LOW"

        severity_scores: dict[str, int] = {
            "LOW": 1,
            "MEDIUM": 2,
            "HIGH": 3,
            "CRITICAL": 4,
        }
        max_severity = max(
            (severity_scores.get(v["severity"], 1) for v in vulnerabilities),
            default=1,
        )

        if max_severity >= 4:
            return "CRITICAL"
        if max_severity >= 3:
            return "HIGH"
        if max_severity >= 2:
            return "MEDIUM"
        return "LOW"

    def validate_input_sanitization(
        self,
        original: str,
        sanitized: str,
    ) -> dict[str, t.Any]:
        """Validate that input sanitization was effective."""
        original_vulns = self.scan_for_vulnerabilities(original)
        sanitized_vulns = self.scan_for_vulnerabilities(sanitized)

        return {
            "original_vulnerabilities": original_vulns["vulnerabilities_found"],
            "sanitized_vulnerabilities": sanitized_vulns["vulnerabilities_found"],
            "sanitization_effective": sanitized_vulns["vulnerabilities_found"] == 0,
            "risk_reduction": original_vulns["risk_level"]
            != sanitized_vulns["risk_level"],
            "original_risk": original_vulns["risk_level"],
            "sanitized_risk": sanitized_vulns["risk_level"],
        }

    def create_auth_test_mock(
        self,
        behavior: dict[str, t.Any] | None = None,
    ) -> AsyncMock:
        """Create a mock for authentication testing."""
        auth_mock = AsyncMock()

        default_behavior: dict[str, t.Any] = {
            "valid_tokens": ["valid_token_123", "admin_token_456"],
            "expired_tokens": ["expired_token_789"],
            "invalid_tokens": ["invalid_token_000"],
            "auth_delay": 0.01,  # 10ms auth check
        }

        if behavior:
            default_behavior.update(behavior)

        async def mock_validate_token(token: str) -> dict[str, Any]:
            import asyncio

            auth_delay = t.cast(float, default_behavior["auth_delay"])
            valid_tokens = t.cast(list[str], default_behavior["valid_tokens"])
            expired_tokens = t.cast(list[str], default_behavior["expired_tokens"])

            await asyncio.sleep(auth_delay)

            if token in valid_tokens:
                return {
                    "valid": True,
                    "user_id": "test_user",
                    "permissions": ["read", "write"],
                    "expires_at": "2024-12-31T23:59:59Z",
                }
            if token in expired_tokens:
                return {
                    "valid": False,
                    "error": "Token expired",
                    "error_code": "TOKEN_EXPIRED",
                }
            return {
                "valid": False,
                "error": "Invalid token",
                "error_code": "INVALID_TOKEN",
            }

        async def mock_check_permission(user_id: str, permission: str) -> bool:
            # Simple permission checking simulation
            admin_permissions = ["read", "write", "admin", "delete"]
            user_permissions = ["read"]

            if user_id == "admin_user":
                return permission in admin_permissions
            return permission in user_permissions

        auth_mock.validate_token.side_effect = mock_validate_token
        auth_mock.check_permission.side_effect = mock_check_permission

        return auth_mock

    def test_password_strength(self, password: str) -> dict[str, t.Any]:
        """Test password strength."""
        checks = {
            "length": len(password) >= 8,
            "uppercase": bool(
                re.search(r"[A-Z]", password),
            ),  # REGEX OK: password strength validation
            "lowercase": bool(
                re.search(r"[a-z]", password),
            ),  # REGEX OK: password strength validation
            "digits": bool(
                re.search(r"\d", password),
            ),  # REGEX OK: password strength validation
            "special_chars": bool(
                re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]", password),
            ),  # REGEX OK: password strength validation
            "no_common_patterns": not any(
                pattern in password.lower()
                for pattern in (
                    "password",
                    "123456",
                    "qwerty",
                    "admin",
                    "letmein",
                )
            ),
        }

        score = sum(checks.values())
        strength_levels = {
            0: "VERY_WEAK",
            1: "VERY_WEAK",
            2: "WEAK",
            3: "FAIR",
            4: "GOOD",
            5: "STRONG",
            6: "VERY_STRONG",
        }

        return {
            "password_length": len(password),
            "checks": checks,
            "score": score,
            "max_score": len(checks),
            "strength": strength_levels.get(score, "UNKNOWN"),
            "passed": score >= 4,  # Require at least 4 criteria
        }

    def generate_security_test_vectors(self, vuln_type: str) -> list[str]:
        """Generate test vectors for specific vulnerability types."""
        test_vectors = {
            "sql_injection": [
                "' OR 1=1 --",
                "'; DROP TABLE users; --",
                "1' UNION SELECT null, username, password FROM users --",
                "admin'/*",
                "1'; INSERT INTO users (username, password) VALUES ('hacker', 'password'); --",
            ],
            "xss": [
                "<script>alert('XSS')</script>",
                "<img src=x onerror=alert('XSS')>",
                "javascript:alert('XSS')",
                "<iframe src=\"javascript:alert('XSS')\"></iframe>",
                "<svg onload=alert('XSS')>",
            ],
            "path_traversal": [
                "../../../etc/passwd",
                "..\\..\\..\\windows\\system32\\config\\sam",
                "....//....//....//etc/passwd",
                "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
                "..%252f..%252f..%252fetc%252fpasswd",
            ],
            "command_injection": [
                "; cat /etc/passwd",
                "| ls -la",
                "&& ping -c 4 127.0.0.1",
                "`whoami`",
                "$(id)",
            ],
        }

        return test_vectors.get(vuln_type, [])

    def assert_no_vulnerabilities(self, scan_result: dict[str, t.Any]) -> None:
        """Assert that no vulnerabilities were found."""
        assert scan_result["vulnerabilities_found"] == 0, (
            f"Vulnerabilities found: {scan_result['vulnerabilities']}"
        )

    def assert_vulnerability_detected(
        self,
        scan_result: dict[str, t.Any],
        vuln_type: str,
    ) -> None:
        """Assert that a specific vulnerability type was detected."""
        found_types = [v["type"] for v in scan_result["vulnerabilities"]]
        assert vuln_type in found_types, f"Vulnerability type {vuln_type} not detected"

    @asynccontextmanager
    async def security_test_context(
        self, test_name: str
    ) -> t.AsyncGenerator[t.Callable[[dict[str, Any]], None]]:
        """Context manager for security testing."""
        scan_results: list[dict[str, Any]] = []

        def record_scan(result: dict[str, Any]) -> None:
            scan_results.append(result)

        try:
            yield record_scan
        finally:
            # Store test results
            self._scan_results[test_name] = {
                "scans": scan_results,
                "total_scans": len(scan_results),
                "vulnerabilities_found": sum(
                    s["vulnerabilities_found"] for s in scan_results
                ),
                "timestamp": "2024-01-01T12:00:00Z",
            }

    def get_scan_results(self, test_name: str) -> dict[str, t.Any] | None:
        """Get scan results for a specific test."""
        return self._scan_results.get(test_name)

    def get_all_scan_results(self) -> dict[str, dict[str, Any]]:
        """Get all scan results."""
        return self._scan_results.copy()

    def reset_scan_results(self) -> None:
        """Reset all scan data."""
        self._scan_results.clear()
