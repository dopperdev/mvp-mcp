# Installing MCP Security Gateway for Claude Desktop

This guide shows you how to add the MCP Security Gateway as an MCP server in Claude Desktop.

## What is This?

The MCP Security Gateway provides security validation tools that Claude Desktop can use to:
- ✅ Validate SQL queries for injection attacks
- ✅ Check file paths for traversal attacks
- ✅ Scan commands for injection vulnerabilities
- ✅ Detect PII and secrets in text
- ✅ Validate complete MCP requests
- ✅ Track security statistics

## Quick Install

### Option 1: Using Claude Desktop Settings

1. **Open Claude Desktop**

2. **Go to Settings** → **Developer** → **Edit Config**

3. **Add this configuration** to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mcp-security-gateway": {
      "command": "python",
      "args": [
        "-m",
        "mcp-server",
        "--directory",
        "/path/to/mvp-mcp"
      ]
    }
  }
}
```

**Replace `/path/to/mvp-mcp`** with the actual path to this repository.

4. **Restart Claude Desktop**

### Option 2: Manual Configuration

**macOS/Linux:**
```bash
# Edit Claude config
nano ~/Library/Application\ Support/Claude/claude_desktop_config.json

# Or on Linux:
nano ~/.config/Claude/claude_desktop_config.json
```

**Windows:**
```powershell
# Edit Claude config
notepad %APPDATA%\Claude\claude_desktop_config.json
```

Add the MCP server configuration as shown above.

### Option 3: Using Installation Script

```bash
# From the repository root
./install-mcp-server.sh

# Or on Windows:
python install-mcp-server.py
```

## Verification

After installation, Claude Desktop should show the MCP Security Gateway in the MCP servers list.

**Test it by asking Claude:**
> "Use the mcp-security-gateway to validate this SQL query: SELECT * FROM users WHERE id = 1 OR 1=1"

Claude should use the `validate_sql_query` tool and report that it's a SQL injection attempt.

## Available Tools

Once installed, Claude Desktop can use these security tools:

### 1. `validate_sql_query`
Checks SQL queries for injection attacks.

**Example:**
```
Query: "DROP TABLE users"
Result: ❌ Blocked - SQL Injection detected
```

### 2. `validate_file_path`
Checks file paths for traversal attacks.

**Example:**
```
Path: "../../etc/passwd"
Result: ❌ Blocked - Path traversal detected
```

### 3. `validate_command`
Checks shell commands for injection.

**Example:**
```
Command: "ls -la; rm -rf /"
Result: ❌ Blocked - Command injection detected
```

### 4. `scan_for_secrets`
Detects PII and secrets in text.

**Example:**
```
Text: "My email is john@example.com and SSN is 123-45-6789"
Result: ⚠️ Found: email, ssn
```

### 5. `validate_mcp_request`
Validates complete MCP requests.

**Example:**
```
Method: "database.query"
Params: {"sql": "SELECT * FROM users"}
Result: ✅ Safe
```

### 6. `get_security_stats`
Shows security validation statistics.

**Example:**
```json
{
  "total_validations": 42,
  "blocked_requests": 5,
  "sql_injection_attempts": 3,
  "path_traversal_attempts": 1,
  "command_injection_attempts": 1
}
```

## Configuration

### Basic Configuration

```json
{
  "mcpServers": {
    "mcp-security-gateway": {
      "command": "python",
      "args": ["-m", "mcp-server", "--directory", "/path/to/mvp-mcp"]
    }
  }
}
```

### Using Virtual Environment

```json
{
  "mcpServers": {
    "mcp-security-gateway": {
      "command": "/path/to/mvp-mcp/venv/bin/python",
      "args": ["-m", "mcp-server", "--directory", "/path/to/mvp-mcp"]
    }
  }
}
```

### With Custom Patterns

You can add custom security patterns by modifying `src/gateway/validator.py`.

## Troubleshooting

### Server Not Appearing in Claude Desktop

1. Check the config file syntax (must be valid JSON)
2. Verify the path to the repository is correct
3. Ensure Python and dependencies are installed:
   ```bash
   cd /path/to/mvp-mcp
   pip install -r requirements.txt
   pip install -r mcp-server/requirements.txt
   ```
4. Restart Claude Desktop completely

### Tools Not Working

1. Check Claude Desktop logs:
   - **macOS**: `~/Library/Logs/Claude/mcp-server-mcp-security-gateway.log`
   - **Linux**: `~/.local/state/Claude/logs/mcp-server-mcp-security-gateway.log`
   - **Windows**: `%APPDATA%\Claude\logs\mcp-server-mcp-security-gateway.log`

2. Test the server manually:
   ```bash
   python -m mcp-server --directory /path/to/mvp-mcp
   ```

3. Verify dependencies:
   ```bash
   pip install mcp
   ```

### Permission Errors

Make sure the server script is executable:
```bash
chmod +x mcp-server/__main__.py
```

## Uninstall

To remove the MCP Security Gateway:

1. Open `claude_desktop_config.json`
2. Remove the `mcp-security-gateway` entry
3. Restart Claude Desktop

## Security Considerations

**This MCP server:**
- ✅ Runs locally on your machine
- ✅ Does not send data to external services
- ✅ Only validates requests, doesn't modify them
- ✅ Provides read-only security analysis
- ✅ Open source - inspect the code yourself

**Best Practices:**
- Keep the security patterns updated
- Review the validation logs periodically
- Use in combination with other security tools
- Don't rely solely on automated validation

## Advanced Usage

### Multiple MCP Servers with Security

You can use the security gateway alongside other MCP servers:

```json
{
  "mcpServers": {
    "mcp-security-gateway": {
      "command": "python",
      "args": ["-m", "mcp-server", "--directory", "/path/to/mvp-mcp"]
    },
    "filesystem": {
      "command": "mcp-server-filesystem",
      "args": ["/home/user/documents"]
    },
    "database": {
      "command": "mcp-server-postgres",
      "args": ["postgresql://localhost/mydb"]
    }
  }
}
```

Claude can now validate requests before sending them to other MCP servers!

### Custom Validation Rules

Edit `src/gateway/validator.py` to add custom patterns:

```python
CUSTOM_PATTERNS = [
    re.compile(r"YOUR_PATTERN_HERE", re.IGNORECASE),
]
```

Then restart Claude Desktop to apply changes.

## Example Workflows

### 1. Safe Database Querying

**Before sending queries to a database MCP server:**
```
You: "Check if this query is safe: SELECT * FROM users WHERE id = $1"
Claude: *uses validate_sql_query*
Claude: "✅ This query appears safe. It uses parameterized queries."
```

### 2. File Access Validation

**Before accessing files:**
```
You: "Is this path safe: ../../../etc/passwd"
Claude: *uses validate_file_path*
Claude: "❌ Path traversal detected! This attempts to access system files."
```

### 3. Security Auditing

**Review security activity:**
```
You: "Show me security statistics"
Claude: *uses get_security_stats*
Claude: "In this session: 10 validations, 2 threats blocked (20% block rate)"
```

## Support

- **Documentation**: See [README.md](../README.md) and [SECURITY.md](../SECURITY.md)
- **Issues**: Report bugs on GitHub
- **Security**: For security issues, see SECURITY.md

---

**The MCP Security Gateway helps Claude Desktop make safer MCP calls!** 🛡️
