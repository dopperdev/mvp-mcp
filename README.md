# MCP Security Gateway

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109.0-green.svg)](https://fastapi.tiangolo.com/)

Enterprise-grade security proxy for Model Context Protocol (MCP) communications. Provides authentication, authorization, request validation, rate limiting, and comprehensive audit logging for MCP servers.

## 🚀 Features

### Core Security Features

- **🔐 Authentication & Authorization**
  - JWT-based authentication
  - User-based access control lists (ACLs)
  - Granular permissions (read/write/execute per MCP server)
  - Service account support

- **🛡️ Request Validation & Sanitization**
  - SQL injection detection and blocking
  - Path traversal prevention
  - Command injection detection
  - Base64 encoded exploit detection
  - JNDI injection detection (Log4Shell style)
  - XXE (XML External Entity) prevention

- **⚡ Rate Limiting**
  - Configurable limits per user and MCP server
  - Token bucket algorithm using Redis
  - Graceful degradation with proper error messages

- **📊 Audit Logging**
  - Every request logged with full context
  - PII detection and automatic masking
  - Structured JSON logging
  - Configurable retention policies
  - Async logging for performance

- **📈 Real-time Monitoring**
  - Live dashboard with metrics visualization
  - Security alerts and notifications
  - Request tracking and performance metrics
  - Top users and servers analytics

- **🔍 Prometheus Metrics**
  - Request counters and histograms
  - Blocked request tracking
  - Custom metrics endpoint

## 🏗️ Architecture

```
┌─────────────┐
│   Client    │ (Claude Desktop, API clients, etc.)
└──────┬──────┘
       │ JWT Token
       ▼
┌─────────────────────────────────────────┐
│     MCP Security Gateway (Port 8000)     │
│  ┌────────────────────────────────────┐ │
│  │   1. JWT Authentication            │ │
│  │   2. Permission Check              │ │
│  │   3. Rate Limiting                 │ │
│  │   4. Security Validation           │ │
│  │      • SQL Injection               │ │
│  │      • Path Traversal              │ │
│  │      • Command Injection           │ │
│  │   5. Audit Logging                 │ │
│  └────────────────────────────────────┘ │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────┐     ┌─────────────┐
│ MCP Server  │     │ MCP Server  │
│ (Database)  │     │ (Filesystem)│
└─────────────┘     └─────────────┘
```

## 📋 Prerequisites

- Docker & Docker Compose (recommended)
- Python 3.11+ (for local development)
- PostgreSQL 16+ (included in Docker Compose)
- Redis 7+ (included in Docker Compose)

## 🚀 Quick Start

### Using Docker Compose (Recommended)

1. **Clone the repository**
```bash
git clone <repository-url>
cd mcp-security-gateway
```

2. **Create environment file**
```bash
cp .env.example .env
# Edit .env and set JWT_SECRET and other variables
```

3. **Start the gateway**
```bash
docker-compose up -d
```

4. **Verify it's running**
```bash
curl http://localhost:8000/health
```

5. **Get authentication token**
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}'
```

6. **Access the dashboard**
Open http://localhost:8000/dashboard in your browser

**⚠️ IMPORTANT**: Change default admin password immediately in production!

## 🔧 Configuration

### Environment Variables

Create a `.env` file based on `.env.example`:

```bash
# Database
DATABASE_URL=postgresql://mcp_user:mcp_password@postgres:5432/mcp_gateway

# Redis
REDIS_URL=redis://redis:6379/0

# Security
JWT_SECRET=your-super-secret-jwt-key-change-this-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Gateway
GATEWAY_HOST=0.0.0.0
GATEWAY_PORT=8000
LOG_LEVEL=INFO

# Rate Limiting
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_PERIOD=3600

# Audit
AUDIT_LOG_RETENTION_DAYS=30
PII_DETECTION_ENABLED=true
```

### YAML Configuration

Edit `config/default.yaml` for advanced configuration:

```yaml
# MCP Servers
servers:
  - name: "company-database"
    upstream_url: "http://localhost:9001"
    enabled: true
    allowed_tools: ["query", "schema"]
    blocked_patterns:
      - "DROP"
      - "DELETE FROM"

# User Policies
policies:
  - user: "data-scientist@company.com"
    servers: ["company-database"]
    permissions: ["read"]
    rate_limit: 100
```

## 📚 API Documentation

### Authentication

#### Login
```bash
POST /auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "admin"
}

# Response
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

#### Get Current User
```bash
GET /auth/me
Authorization: Bearer <token>

# Response
{
  "id": 1,
  "username": "admin",
  "email": "admin@example.com",
  "is_active": true,
  "is_admin": true
}
```

### MCP Proxy

#### Forward MCP Request
```bash
POST /mcp/{server_name}
Authorization: Bearer <token>
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "method": "tools/list",
  "params": {},
  "id": "1"
}

# Response
{
  "jsonrpc": "2.0",
  "result": { ... },
  "id": "1"
}
```

### Admin Endpoints

#### List MCP Servers
```bash
GET /admin/servers
Authorization: Bearer <admin-token>
```

#### Get Audit Logs
```bash
GET /admin/audit-logs?limit=100&blocked_only=false
Authorization: Bearer <admin-token>
```

#### Get Security Alerts
```bash
GET /admin/security-alerts?limit=50
Authorization: Bearer <admin-token>
```

#### Get Dashboard Metrics
```bash
GET /admin/metrics
Authorization: Bearer <token>
```

### OpenAPI Documentation

Interactive API documentation available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 🧪 Testing

### Run All Tests
```bash
# Using Docker
docker-compose exec gateway pytest

# Local development
pytest
```

### Run Security Tests Only
```bash
pytest src/tests/test_security.py -v
```

### Run with Coverage
```bash
pytest --cov=src --cov-report=html
```

### Expected Test Results
- ✅ 50+ security validation tests
- ✅ SQL injection detection (10 test cases)
- ✅ Path traversal detection (10 test cases)
- ✅ Command injection detection (5 test cases)
- ✅ Base64 exploit detection
- ✅ JNDI injection detection
- ✅ PII detection and masking
- ✅ Performance test (validation < 10ms)

## 🔒 Security Best Practices

### 1. Change Default Credentials
```bash
# In production, NEVER use default admin/admin
# Set strong passwords in environment variables
DEFAULT_ADMIN_PASSWORD=<strong-random-password>
```

### 2. Use Strong JWT Secrets
```bash
# Generate a strong secret
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Set in .env
JWT_SECRET=<generated-secret>
```

### 3. Configure TLS/SSL
In production, use a reverse proxy (nginx, Caddy) with TLS:

```nginx
server {
    listen 443 ssl;
    server_name gateway.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 4. Restrict Network Access
Use firewall rules to restrict access:
```bash
# Only allow specific IPs
iptables -A INPUT -p tcp --dport 8000 -s 10.0.0.0/8 -j ACCEPT
iptables -A INPUT -p tcp --dport 8000 -j DROP
```

### 5. Enable Audit Log Monitoring
Set up alerts for suspicious activity:
- Multiple blocked requests from same user
- High severity security alerts
- Unusual access patterns

## 📊 Monitoring & Observability

### Prometheus Metrics
Metrics available at `/metrics` endpoint:

```
# Request counters
mcp_gateway_requests_total{method="query", server="db", status="success"} 1234

# Request duration
mcp_gateway_request_duration_seconds{method="query", server="db"} 0.015

# Blocked requests
mcp_gateway_blocked_requests_total{reason="SQL Injection"} 42
```

### Dashboard
Access the real-time dashboard at http://localhost:8000/dashboard

Features:
- Total requests and blocked requests
- Active users count
- Average response time
- Requests per minute
- Top users and servers
- Recent security alerts

## 🚢 Deployment

### Docker Production Deployment

```bash
# Build production image
docker build -t mcp-gateway:latest .

# Run with production settings
docker run -d \
  --name mcp-gateway \
  -p 8000:8000 \
  --env-file .env.production \
  mcp-gateway:latest
```

### Kubernetes Deployment

```bash
# Apply Kubernetes manifests
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

## 🐛 Troubleshooting

### Gateway won't start
```bash
# Check logs
docker-compose logs gateway

# Check database connection
docker-compose exec postgres pg_isready

# Check Redis connection
docker-compose exec redis redis-cli ping
```

### Authentication failures
```bash
# Verify JWT secret is set
echo $JWT_SECRET

# Check user exists
docker-compose exec postgres psql -U mcp_user -d mcp_gateway \
  -c "SELECT username, is_active FROM users;"
```

### Requests blocked unexpectedly
```bash
# Check audit logs
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/admin/audit-logs?blocked_only=true

# Check blocked patterns
docker-compose exec postgres psql -U mcp_user -d mcp_gateway \
  -c "SELECT * FROM blocked_patterns WHERE is_active = true;"
```

## 🤝 Contributing

Contributions welcome! Please read CONTRIBUTING.md for guidelines.

## 📄 License

This project is licensed under the MIT License - see LICENSE file for details.

## 🙏 Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Uses Anthropic's [MCP SDK](https://github.com/anthropics/mcp)
- Inspired by enterprise security best practices

## 📞 Support

- Issues: GitHub Issues
- Documentation: [docs/](docs/)
- Security: security@example.com

## 🗺️ Roadmap

### v0.2.0 (Planned)
- [ ] AI-powered anomaly detection
- [ ] Multi-tenancy support
- [ ] Encrypted audit logs
- [ ] Compliance report generation (SOC2, HIPAA)
- [ ] MCP response validation
- [ ] Webhook alerts for security events

### v1.0.0 (Future)
- [ ] Advanced threat intelligence integration
- [ ] Machine learning for pattern detection
- [ ] GraphQL API support
- [ ] Advanced caching strategies
- [ ] Multi-region deployment support

---

**Built with ❤️ for the MCP community**
