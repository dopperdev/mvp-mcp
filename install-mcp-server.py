"""Windows installation script for MCP Security Gateway"""

import json
import os
import sys
from pathlib import Path
import shutil
from datetime import datetime

def get_config_path():
    """Get Claude Desktop config path for Windows."""
    appdata = os.getenv('APPDATA')
    if not appdata:
        print("❌ Could not find APPDATA directory")
        sys.exit(1)
    return Path(appdata) / 'Claude' / 'claude_desktop_config.json'

def main():
    print("=" * 50)
    print("MCP Security Gateway Installer (Windows)")
    print("=" * 50)
    print()

    # Get paths
    script_dir = Path(__file__).parent.absolute()
    config_file = get_config_path()

    print(f"📁 Repository path: {script_dir}")
    print(f"⚙️  Config file: {config_file}")
    print()

    # Create config directory if needed
    config_file.parent.mkdir(parents=True, exist_ok=True)

    # Create or read config
    if not config_file.exists():
        print("📝 Creating new config file...")
        config = {"mcpServers": {}}
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
    else:
        # Backup existing config
        backup_file = config_file.with_suffix(f'.backup.{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        print(f"💾 Backing up config to: {backup_file}")
        shutil.copy(config_file, backup_file)

        # Read config
        with open(config_file, 'r') as f:
            config = json.load(f)

    # Ensure mcpServers exists
    if 'mcpServers' not in config:
        config['mcpServers'] = {}

    # Check if Python is available
    python_cmd = sys.executable
    print(f"✅ Python found: {python_cmd}")
    print(f"   Version: {sys.version}")

    # Add MCP server to config
    config['mcpServers']['mcp-security-gateway'] = {
        'command': python_cmd,
        'args': [
            '-m',
            'mcp_server',
            '--directory',
            str(script_dir)
        ]
    }

    # Write updated config
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)

    print("✅ MCP Security Gateway added to config!")
    print()
    print("=" * 50)
    print("✅ Installation Complete!")
    print("=" * 50)
    print()
    print("Next steps:")
    print("  1. Restart Claude Desktop")
    print("  2. The MCP Security Gateway should appear in MCP servers")
    print("  3. Test it by asking Claude to validate a SQL query")
    print()
    print("Example prompt:")
    print('  "Use mcp-security-gateway to check if this is safe:')
    print('   SELECT * FROM users WHERE id = 1 OR 1=1"')
    print()
    print("To uninstall:")
    print(f"  1. Edit {config_file}")
    print("  2. Remove the 'mcp-security-gateway' entry")
    print("  3. Restart Claude Desktop")
    print()

if __name__ == "__main__":
    main()
