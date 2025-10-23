-- MCP Security Gateway Database Schema

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    is_admin BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- MCP Servers configuration
CREATE TABLE IF NOT EXISTS mcp_servers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    upstream_url VARCHAR(512) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User permissions for MCP servers
CREATE TABLE IF NOT EXISTS user_permissions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    server_id INTEGER REFERENCES mcp_servers(id) ON DELETE CASCADE,
    can_read BOOLEAN DEFAULT true,
    can_write BOOLEAN DEFAULT false,
    can_execute BOOLEAN DEFAULT false,
    rate_limit INTEGER DEFAULT 100,
    rate_limit_period INTEGER DEFAULT 3600,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, server_id)
);

-- Audit logs
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    username VARCHAR(255),
    server_id INTEGER REFERENCES mcp_servers(id) ON DELETE SET NULL,
    server_name VARCHAR(255),
    method VARCHAR(255),
    params JSONB,
    response_status INTEGER,
    response_time_ms FLOAT,
    blocked BOOLEAN DEFAULT false,
    block_reason TEXT,
    client_ip VARCHAR(45),
    user_agent TEXT,
    request_id VARCHAR(36)
);

-- Security alerts
CREATE TABLE IF NOT EXISTS security_alerts (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    severity VARCHAR(20) NOT NULL, -- 'low', 'medium', 'high', 'critical'
    alert_type VARCHAR(50) NOT NULL, -- 'sql_injection', 'path_traversal', etc.
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    username VARCHAR(255),
    description TEXT,
    details JSONB,
    acknowledged BOOLEAN DEFAULT false,
    acknowledged_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    acknowledged_at TIMESTAMP
);

-- Blocked patterns configuration
CREATE TABLE IF NOT EXISTS blocked_patterns (
    id SERIAL PRIMARY KEY,
    server_id INTEGER REFERENCES mcp_servers(id) ON DELETE CASCADE,
    pattern VARCHAR(512) NOT NULL,
    pattern_type VARCHAR(50) NOT NULL, -- 'sql_injection', 'path_traversal', 'command_injection', 'custom'
    is_regex BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX idx_audit_logs_timestamp ON audit_logs(timestamp DESC);
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_server_id ON audit_logs(server_id);
CREATE INDEX idx_audit_logs_blocked ON audit_logs(blocked);
CREATE INDEX idx_security_alerts_timestamp ON security_alerts(timestamp DESC);
CREATE INDEX idx_security_alerts_severity ON security_alerts(severity);
CREATE INDEX idx_security_alerts_acknowledged ON security_alerts(acknowledged);

-- Insert default admin user (password: admin - CHANGE IN PRODUCTION!)
-- Password hash for 'admin' using bcrypt
INSERT INTO users (username, email, hashed_password, is_admin)
VALUES ('admin', 'admin@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYqV5N5kGNy', true)
ON CONFLICT (username) DO NOTHING;

-- Insert example MCP server
INSERT INTO mcp_servers (name, upstream_url, description)
VALUES (
    'example-filesystem',
    'http://localhost:9000',
    'Example filesystem MCP server for testing'
)
ON CONFLICT (name) DO NOTHING;

-- Grant admin user full access to example server
INSERT INTO user_permissions (user_id, server_id, can_read, can_write, can_execute, rate_limit)
SELECT u.id, s.id, true, true, true, 1000
FROM users u, mcp_servers s
WHERE u.username = 'admin' AND s.name = 'example-filesystem'
ON CONFLICT (user_id, server_id) DO NOTHING;

-- Insert default blocked patterns
INSERT INTO blocked_patterns (server_id, pattern, pattern_type, is_regex) VALUES
-- SQL Injection patterns (global - server_id NULL for all servers)
(NULL, 'DROP TABLE', 'sql_injection', false),
(NULL, 'DROP DATABASE', 'sql_injection', false),
(NULL, 'DELETE FROM', 'sql_injection', false),
(NULL, 'TRUNCATE', 'sql_injection', false),
(NULL, 'UNION SELECT', 'sql_injection', false),
(NULL, 'OR 1=1', 'sql_injection', false),
(NULL, '--', 'sql_injection', false),
(NULL, '/*', 'sql_injection', false),

-- Path traversal patterns
(NULL, '../', 'path_traversal', false),
(NULL, '..\\', 'path_traversal', false),
(NULL, '%2e%2e', 'path_traversal', false),
(NULL, '/etc/passwd', 'path_traversal', false),
(NULL, '/etc/shadow', 'path_traversal', false),

-- Command injection patterns
(NULL, ';rm -rf', 'command_injection', false),
(NULL, '|bash', 'command_injection', false),
(NULL, '&&', 'command_injection', false),
(NULL, '$(', 'command_injection', false),
(NULL, '`', 'command_injection', false)
ON CONFLICT DO NOTHING;
