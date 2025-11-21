from acb.actions.secure.security_patterns import (
    detect_path_traversal,
    detect_sql_injection,
    detect_xss,
)


class TestSecurityPatterns:
    def test_detect_sql_injection_safelist_examples(self) -> None:
        assert detect_sql_injection("hello world") is True
        # word boundary ensures "selective" does not trigger
        assert detect_sql_injection("selective columns") is True

    def test_detect_sql_injection_detects_common_payloads(self) -> None:
        payloads = [
            "SELECT * FROM users; --",
            "admin' OR '1'='1",
            "; DROP TABLE users; --",
        ]
        for p in payloads:
            assert detect_sql_injection(p) is False

    def test_detect_xss_safelist_examples(self) -> None:
        assert detect_xss("Click here to view") is True
        assert detect_xss("data:image/png;base64,aaaa") is True

    def test_detect_xss_detects_script_and_handlers(self) -> None:
        cases = [
            "<script>alert('x')</script>",
            "javascript:alert(1)",
            '<a onclick="do()">x</a>',
            "<iframe src='x'></iframe>",
        ]
        for c in cases:
            assert detect_xss(c) is False

    def test_detect_path_traversal_safe(self) -> None:
        assert detect_path_traversal("/usr/local/bin") is True
        assert detect_path_traversal("C:\\Windows\\System32") is True

    def test_detect_path_traversal_detects_sequences(self) -> None:
        cases = [
            "../../etc/passwd",
            "..\\..\\windows\\system.ini",
            "%2e%2e%2fetc%2fpasswd",
        ]
        for c in cases:
            assert detect_path_traversal(c) is False
