# MCP Security Gateway - Server Component

This directory contains the MCP server implementation that can be added to Claude Desktop.

## What Does This Do?

The MCP Security Gateway server provides security validation tools that Claude Desktop can use to check requests for common security vulnerabilities before they're sent to other MCP servers.

## Features

- **SQL Injection Detection** - Validates SQL queries
- **Path Traversal Prevention** - Checks file paths
- **Command Injection Detection** - Validates shell commands
- **PII Detection** - Scans for sensitive data
- **Request Validation** - Validates complete MCP requests
- **Security Statistics** - Tracks threats blocked

## Installation

See [MCP_INSTALL.md](../MCP_INSTALL.md) for detailed installation instructions.

**Quick install:**
```bash
# From repository root
./install-mcp-server.sh

# Or on Windows
python install-mcp-server.py
```

## Manual Configuration

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mcp-security-gateway": {
      "command": "python3",
      "args": [
        "-m",
        "mcp_server",
        "--directory",
        "/path/to/mvp-mcp"
      ]
    }
  }
}
```

## Testing

Test the server directly:

```bash
# Run the server
python3 -m mcp_server

# It should start and wait for JSON-RPC commands on stdin
```

## Development

The server uses the MCP SDK and implements these tools:

- `validate_sql_query` - Check SQL for injection
- `validate_file_path` - Check paths for traversal
- `validate_command` - Check commands for injection
- `scan_for_secrets` - Detect PII and secrets
- `validate_mcp_request` - Validate full MCP requests
- `get_security_stats` - View security statistics

## Architecture

```
Claude Desktop
     ↓
MCP Protocol (stdio)
     ↓
mcp-server/server.py
     ↓
src/gateway/validator.py (Security validation logic)
```

## Security

This server:
- ✅ Runs locally only
- ✅ No network access required
- ✅ Read-only validation (doesn't modify requests)
- ✅ Open source and auditable

## Troubleshooting

**Server not appearing:**
- Check config file syntax
- Verify Python path
- Install dependencies: `pip install mcp`

**Tools not working:**
- Check Claude Desktop logs
- Verify repository path in config
- Test server manually

## License

MIT License - Same as parent project
