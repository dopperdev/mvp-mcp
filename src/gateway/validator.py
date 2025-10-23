"""Security validation for MCP requests.

This module implements detection and blocking of common security attacks:
- SQL injection
- Path traversal
- Command injection
- Base64 encoded exploits
- JNDI injection
"""

import re
import base64
import json
from typing import Tuple, Optional, List, Dict, Any
from loguru import logger


# SQL Injection Patterns
SQL_INJECTION_PATTERNS = [
    # DDL commands
    re.compile(r"\b(DROP|TRUNCATE|ALTER)\s+(TABLE|DATABASE|SCHEMA)", re.IGNORECASE),
    # DML commands with potential harm
    re.compile(r"\b(DELETE|UPDATE)\s+FROM", re.IGNORECASE),
    # SQL comments for evasion
    re.compile(r"(--|#|/\*|\*/)", re.IGNORECASE),
    # UNION-based injection
    re.compile(r"\bUNION\s+SELECT", re.IGNORECASE),
    # Boolean-based injection
    re.compile(r"(\bOR\b|\bAND\b)\s+[\d\w]+\s*=\s*[\d\w]+", re.IGNORECASE),
    # String concatenation attacks
    re.compile(r"'\s*\+\s*'", re.IGNORECASE),
    # Hex encoding
    re.compile(r"0x[0-9a-f]+", re.IGNORECASE),
    # SQL functions for data extraction
    re.compile(r"\b(CONCAT|CHAR|ASCII|SUBSTRING|BENCHMARK|SLEEP|WAITFOR)\s*\(", re.IGNORECASE),
    # Information schema access
    re.compile(r"INFORMATION_SCHEMA", re.IGNORECASE),
]

# Path Traversal Patterns
PATH_TRAVERSAL_PATTERNS = [
    # Directory traversal
    re.compile(r"\.\.[/\\]"),
    re.compile(r"\.\.\.", re.IGNORECASE),
    # URL encoded traversal
    re.compile(r"%2e%2e[/\\]", re.IGNORECASE),
    re.compile(r"%252e%252e[/\\]", re.IGNORECASE),
    # Absolute paths to sensitive files
    re.compile(r"/(etc|proc|sys|root)/", re.IGNORECASE),
    re.compile(r"[A-Z]:\\(Windows|System32|Users)", re.IGNORECASE),
    # Home directory access
    re.compile(r"~/"),
    # Null byte injection
    re.compile(r"%00", re.IGNORECASE),
    # Specific sensitive files
    re.compile(r"/(passwd|shadow|hosts|sudoers)", re.IGNORECASE),
]

# Command Injection Patterns
COMMAND_INJECTION_PATTERNS = [
    # Command separators
    re.compile(r"[;|&]"),
    # Command substitution
    re.compile(r"[`$]\("),
    re.compile(r"\$\{"),
    # Redirection
    re.compile(r"[<>]"),
    # Newline injection
    re.compile(r"\\n"),
    # Dangerous commands
    re.compile(r"\b(rm|dd|mkfs|fork|:()\{|wget|curl|nc|netcat|bash|sh|powershell|cmd)\b", re.IGNORECASE),
]

# Base64 Encoded Exploit Patterns
BASE64_EXPLOIT_KEYWORDS = [
    "bash", "sh", "exec", "eval", "system", "cmd", "powershell",
    "wget", "curl", "nc", "netcat", "rm -rf", "/bin/sh"
]

# JNDI Injection Patterns (Log4j style)
JNDI_PATTERNS = [
    re.compile(r"\$\{jndi:", re.IGNORECASE),
    re.compile(r"\$\{ldap:", re.IGNORECASE),
    re.compile(r"\$\{rmi:", re.IGNORECASE),
    re.compile(r"\$\{dns:", re.IGNORECASE),
]

# XXE (XML External Entity) Patterns
XXE_PATTERNS = [
    re.compile(r"<!ENTITY", re.IGNORECASE),
    re.compile(r"SYSTEM\s+[\"']", re.IGNORECASE),
    re.compile(r"<!DOCTYPE", re.IGNORECASE),
]


class SecurityValidator:
    """Security validator for MCP requests."""

    def __init__(self, custom_patterns: Optional[List[Dict[str, Any]]] = None):
        """
        Initialize security validator.

        Args:
            custom_patterns: Optional custom validation patterns
        """
        self.custom_patterns = custom_patterns or []
        logger.info("Security validator initialized")

    def validate_request(
        self,
        method: str,
        params: Optional[Dict[str, Any]],
        server_name: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate MCP request for security issues.

        Args:
            method: MCP method name
            params: Request parameters
            server_name: Target MCP server name

        Returns:
            Tuple of (is_valid, block_reason)
            - is_valid: True if request is safe, False if blocked
            - block_reason: Reason for blocking (None if valid)
        """
        if params is None:
            return True, None

        # Convert params to string for pattern matching
        params_str = json.dumps(params)

        # Check SQL injection
        is_valid, reason = self._check_sql_injection(params_str)
        if not is_valid:
            logger.warning(f"SQL injection detected in {method}: {reason}")
            return False, f"SQL Injection: {reason}"

        # Check path traversal
        is_valid, reason = self._check_path_traversal(params_str)
        if not is_valid:
            logger.warning(f"Path traversal detected in {method}: {reason}")
            return False, f"Path Traversal: {reason}"

        # Check command injection
        is_valid, reason = self._check_command_injection(params_str)
        if not is_valid:
            logger.warning(f"Command injection detected in {method}: {reason}")
            return False, f"Command Injection: {reason}"

        # Check base64 encoded exploits
        is_valid, reason = self._check_base64_exploits(params_str)
        if not is_valid:
            logger.warning(f"Base64 exploit detected in {method}: {reason}")
            return False, f"Base64 Exploit: {reason}"

        # Check JNDI injection
        is_valid, reason = self._check_jndi_injection(params_str)
        if not is_valid:
            logger.warning(f"JNDI injection detected in {method}: {reason}")
            return False, f"JNDI Injection: {reason}"

        # Check XXE
        is_valid, reason = self._check_xxe(params_str)
        if not is_valid:
            logger.warning(f"XXE attack detected in {method}: {reason}")
            return False, f"XXE Attack: {reason}"

        # Check custom patterns
        is_valid, reason = self._check_custom_patterns(params_str)
        if not is_valid:
            logger.warning(f"Custom pattern violation in {method}: {reason}")
            return False, f"Custom Pattern: {reason}"

        return True, None

    def _check_sql_injection(self, content: str) -> Tuple[bool, Optional[str]]:
        """Check for SQL injection patterns."""
        for pattern in SQL_INJECTION_PATTERNS:
            match = pattern.search(content)
            if match:
                return False, f"Detected SQL injection pattern: {match.group()}"
        return True, None

    def _check_path_traversal(self, content: str) -> Tuple[bool, Optional[str]]:
        """Check for path traversal patterns."""
        for pattern in PATH_TRAVERSAL_PATTERNS:
            match = pattern.search(content)
            if match:
                return False, f"Detected path traversal pattern: {match.group()}"
        return True, None

    def _check_command_injection(self, content: str) -> Tuple[bool, Optional[str]]:
        """Check for command injection patterns."""
        for pattern in COMMAND_INJECTION_PATTERNS:
            match = pattern.search(content)
            if match:
                return False, f"Detected command injection pattern: {match.group()}"
        return True, None

    def _check_base64_exploits(self, content: str) -> Tuple[bool, Optional[str]]:
        """Check for base64 encoded exploits."""
        # Find potential base64 strings (length > 20, alphanumeric + =)
        base64_pattern = re.compile(r'[A-Za-z0-9+/]{20,}={0,2}')
        matches = base64_pattern.findall(content)

        for match in matches:
            try:
                decoded = base64.b64decode(match).decode('utf-8', errors='ignore')
                decoded_lower = decoded.lower()

                for keyword in BASE64_EXPLOIT_KEYWORDS:
                    if keyword in decoded_lower:
                        return False, f"Detected base64 encoded exploit: {keyword}"
            except Exception:
                # Not valid base64 or not decodable, skip
                continue

        return True, None

    def _check_jndi_injection(self, content: str) -> Tuple[bool, Optional[str]]:
        """Check for JNDI injection patterns (Log4Shell style)."""
        for pattern in JNDI_PATTERNS:
            match = pattern.search(content)
            if match:
                return False, f"Detected JNDI injection pattern: {match.group()}"
        return True, None

    def _check_xxe(self, content: str) -> Tuple[bool, Optional[str]]:
        """Check for XXE (XML External Entity) attack patterns."""
        for pattern in XXE_PATTERNS:
            match = pattern.search(content)
            if match:
                return False, f"Detected XXE pattern: {match.group()}"
        return True, None

    def _check_custom_patterns(self, content: str) -> Tuple[bool, Optional[str]]:
        """Check for custom validation patterns."""
        for custom in self.custom_patterns:
            pattern_str = custom.get("pattern")
            is_regex = custom.get("is_regex", False)

            if is_regex:
                pattern = re.compile(pattern_str, re.IGNORECASE)
                match = pattern.search(content)
                if match:
                    return False, f"Detected custom pattern: {match.group()}"
            else:
                if pattern_str.lower() in content.lower():
                    return False, f"Detected custom pattern: {pattern_str}"

        return True, None

    def sanitize_params(self, params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Sanitize request parameters (currently a placeholder).

        Future implementations could:
        - Remove/escape dangerous characters
        - Normalize Unicode
        - Validate data types
        - Truncate long strings

        Args:
            params: Request parameters

        Returns:
            Sanitized parameters
        """
        if params is None:
            return {}

        # For MVP, we block rather than sanitize
        # In production, you might want to sanitize certain inputs
        return params


def detect_pii(content: str) -> List[str]:
    """
    Detect PII (Personally Identifiable Information) in content.

    Args:
        content: Content to check for PII

    Returns:
        List of PII types detected
    """
    pii_found = []

    # Email addresses
    if re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', content):
        pii_found.append("email")

    # SSN (US format)
    if re.search(r'\b\d{3}-\d{2}-\d{4}\b', content):
        pii_found.append("ssn")

    # Credit card numbers
    if re.search(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', content):
        pii_found.append("credit_card")

    # Phone numbers
    if re.search(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', content):
        pii_found.append("phone")

    # IP addresses (can be PII in some contexts)
    if re.search(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', content):
        pii_found.append("ip_address")

    return pii_found


def mask_pii(content: str) -> str:
    """
    Mask PII in content for safe logging.

    Args:
        content: Content with potential PII

    Returns:
        Content with PII masked
    """
    # Mask emails
    content = re.sub(
        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        '[EMAIL]',
        content
    )

    # Mask SSN
    content = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN]', content)

    # Mask credit cards
    content = re.sub(
        r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',
        '[CREDIT_CARD]',
        content
    )

    # Mask phone numbers
    content = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE]', content)

    # Mask IP addresses
    content = re.sub(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', '[IP_ADDRESS]', content)

    return content
