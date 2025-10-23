#!/usr/bin/env python3
"""MCP Security Gateway Server - Standalone executable"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Import and run the server
from mcp_server.server import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())
