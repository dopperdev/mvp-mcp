#!/bin/bash
# Installation script for MCP Security Gateway

set -e

echo "========================================"
echo "MCP Security Gateway Installer"
echo "========================================"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Detect OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    CONFIG_FILE="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    CONFIG_FILE="$HOME/.config/Claude/claude_desktop_config.json"
else
    echo "❌ Unsupported OS: $OSTYPE"
    echo "Please manually configure Claude Desktop."
    exit 1
fi

echo "📁 Repository path: $SCRIPT_DIR"
echo "⚙️  Config file: $CONFIG_FILE"
echo ""

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "📝 Creating new config file..."
    mkdir -p "$(dirname "$CONFIG_FILE")"
    echo '{"mcpServers":{}}' > "$CONFIG_FILE"
fi

# Backup existing config
BACKUP_FILE="${CONFIG_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
echo "💾 Backing up config to: $BACKUP_FILE"
cp "$CONFIG_FILE" "$BACKUP_FILE"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed"
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
pip3 install -q -r "$SCRIPT_DIR/mcp-server/requirements.txt"

# Add MCP server to config using Python
python3 << EOF
import json
import sys

config_file = "$CONFIG_FILE"
repo_path = "$SCRIPT_DIR"

# Read existing config
with open(config_file, 'r') as f:
    config = json.load(f)

# Ensure mcpServers key exists
if 'mcpServers' not in config:
    config['mcpServers'] = {}

# Add MCP Security Gateway
config['mcpServers']['mcp-security-gateway'] = {
    'command': 'python3',
    'args': [
        '-m',
        'mcp_server',
        '--directory',
        repo_path
    ]
}

# Write updated config
with open(config_file, 'w') as f:
    json.dump(config, f, indent=2)

print("✅ MCP Security Gateway added to config!")
EOF

echo ""
echo "========================================"
echo "✅ Installation Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. Restart Claude Desktop"
echo "  2. The MCP Security Gateway should appear in MCP servers"
echo "  3. Test it by asking Claude to validate a SQL query"
echo ""
echo "Example prompt:"
echo '  "Use mcp-security-gateway to check if this is safe: SELECT * FROM users WHERE id = 1 OR 1=1"'
echo ""
echo "To uninstall:"
echo "  1. Edit $CONFIG_FILE"
echo "  2. Remove the 'mcp-security-gateway' entry"
echo "  3. Restart Claude Desktop"
echo ""
echo "Backup saved to: $BACKUP_FILE"
echo ""
