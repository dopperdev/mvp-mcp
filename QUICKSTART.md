# Quick Start Guide - MCP Security Gateway

Get the MCP Security Gateway up and running in under 5 minutes!

## Prerequisites

- Docker and Docker Compose installed
- Basic understanding of MCP (Model Context Protocol)

## Step 1: Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd mcp-security-gateway

# Create environment file
cp .env.example .env

# (Optional) Edit .env to change default settings
# For local testing, the defaults work fine
```

## Step 2: Start the Gateway

```bash
# Start all services (PostgreSQL, Redis, Gateway)
docker-compose up -d

# Check if services are running
docker-compose ps

# Should see:
# - mcp-gateway (port 8000)
# - mcp-gateway-db (port 5432)
# - mcp-gateway-redis (port 6379)
```

## Step 3: Verify Installation

```bash
# Health check
curl http://localhost:8000/health

# Should return: {"status":"healthy","service":"mcp-security-gateway"}
```

## Step 4: Get Authentication Token

```bash
# Login with default admin credentials
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}'

# Response will include access_token
# {
#   "access_token": "eyJhbGc...",
#   "token_type": "bearer",
#   "expires_in": 86400
# }

# Save the token for later use
export TOKEN="eyJhbGc..."  # Replace with your actual token
```

## Step 5: Test the Gateway

### Example 1: Get Current User Info

```bash
curl -X GET http://localhost:8000/auth/me \
  -H "Authorization: Bearer $TOKEN"

# Returns your user information
```

### Example 2: List MCP Servers

```bash
curl -X GET http://localhost:8000/admin/servers \
  -H "Authorization: Bearer $TOKEN"

# Returns list of configured MCP servers
```

### Example 3: Send MCP Request (Demo)

```bash
# This will fail because no upstream MCP server is configured yet
# But it demonstrates the request flow
curl -X POST http://localhost:8000/mcp/example-filesystem \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "params": {},
    "id": "1"
  }'
```

### Example 4: Test Security Validation

```bash
# This request will be blocked due to SQL injection detection
curl -X POST http://localhost:8000/mcp/example-filesystem \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "database.query",
    "params": {
      "sql": "DROP TABLE users"
    },
    "id": "2"
  }'

# Response will indicate request was blocked:
# {
#   "jsonrpc": "2.0",
#   "error": {
#     "code": -32003,
#     "message": "Request blocked by security policy",
#     "data": "SQL Injection: Detected SQL injection pattern: DROP TABLE"
#   },
#   "id": "2"
# }
```

## Step 6: Access the Dashboard

1. Open your browser to: http://localhost:8000/dashboard

2. When prompted for a token, enter the JWT token from Step 4

3. You'll see real-time metrics:
   - Total requests
   - Blocked requests
   - Active users
   - Average response time
   - Security alerts

## Step 7: Configure Your First MCP Server

Add a real MCP server to proxy through the gateway:

```bash
# Connect to the database
docker-compose exec postgres psql -U mcp_user -d mcp_gateway

# Add an MCP server
INSERT INTO mcp_servers (name, upstream_url, description, is_active)
VALUES (
  'my-filesystem',
  'http://your-mcp-server:9000',  -- Replace with your MCP server URL
  'My filesystem MCP server',
  true
);

# Grant admin user access to the server
INSERT INTO user_permissions (user_id, server_id, can_read, can_write, can_execute)
SELECT u.id, s.id, true, true, true
FROM users u, mcp_servers s
WHERE u.username = 'admin' AND s.name = 'my-filesystem';

# Exit psql
\q
```

## Step 8: Send Real MCP Request

```bash
# Now send a request to your MCP server through the gateway
curl -X POST http://localhost:8000/mcp/my-filesystem \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "params": {},
    "id": "3"
  }'

# The gateway will:
# 1. Validate your JWT token
# 2. Check your permissions for "my-filesystem"
# 3. Check rate limits
# 4. Validate the request for security issues
# 5. Forward to your MCP server
# 6. Log the request in the audit log
# 7. Return the response
```

## Step 9: View Audit Logs

```bash
# Get recent audit logs
curl -X GET "http://localhost:8000/admin/audit-logs?limit=10" \
  -H "Authorization: Bearer $TOKEN"

# View security alerts
curl -X GET "http://localhost:8000/admin/security-alerts?limit=10" \
  -H "Authorization: Bearer $TOKEN"
```

## Step 10: Explore the API

Interactive API documentation is available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Common Next Steps

### Create Additional Users

```bash
# Register a new user (admin only)
curl -X POST http://localhost:8000/auth/register \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john.doe",
    "email": "john@example.com",
    "password": "SecurePassword123!",
    "is_admin": false
  }'
```

### Configure Rate Limits

```sql
-- Connect to database
docker-compose exec postgres psql -U mcp_user -d mcp_gateway

-- Set custom rate limit for a user
UPDATE user_permissions
SET rate_limit = 1000, rate_limit_period = 3600
WHERE user_id = 2 AND server_id = 1;
```

### Add Custom Blocked Patterns

```sql
-- Block specific SQL patterns for a server
INSERT INTO blocked_patterns (server_id, pattern, pattern_type, is_active)
VALUES (
  1,  -- server_id
  'DROP',
  'sql_injection',
  true
);
```

### Run Security Tests

```bash
# Run the test suite
docker-compose exec gateway pytest

# Run only security tests
docker-compose exec gateway pytest src/tests/test_security.py -v
```

## Troubleshooting

### Services won't start

```bash
# Check logs
docker-compose logs gateway
docker-compose logs postgres
docker-compose logs redis

# Restart services
docker-compose restart
```

### Can't connect to database

```bash
# Check database is ready
docker-compose exec postgres pg_isready -U mcp_user

# Reset database (WARNING: deletes all data)
docker-compose down -v
docker-compose up -d
```

### Authentication errors

```bash
# Verify user exists
docker-compose exec postgres psql -U mcp_user -d mcp_gateway \
  -c "SELECT username, is_active FROM users;"

# Reset admin password
docker-compose exec postgres psql -U mcp_user -d mcp_gateway \
  -c "UPDATE users SET hashed_password = '\$2b\$12\$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYqV5N5kGNy' WHERE username = 'admin';"
```

## Production Deployment

For production deployment, see:
- [README.md](README.md) - Full documentation
- [SECURITY.md](SECURITY.md) - Security best practices
- [k8s/](k8s/) - Kubernetes manifests

**⚠️ Important**: Change default admin password and JWT secret before production use!

## Need Help?

- Check logs: `docker-compose logs -f gateway`
- View API docs: http://localhost:8000/docs
- Read full documentation: [README.md](README.md)
- Security guide: [SECURITY.md](SECURITY.md)

---

Happy securing! 🛡️
