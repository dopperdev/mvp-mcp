"""MCP Security Gateway Server

This is an MCP server that provides security monitoring and validation tools
for Claude Desktop to use when interacting with other MCP servers.
"""

import asyncio
import json
from typing import Any, Sequence
from mcp.server import Server
from mcp.types import (
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
)
import mcp.server.stdio

# Import our security validation logic
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.gateway.validator import SecurityValidator, detect_pii, mask_pii

# Create server instance
server = Server("mcp-security-gateway")

# Initialize security validator
validator = SecurityValidator()

@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available security tools."""
    return [
        Tool(
            name="validate_sql_query",
            description="Validate a SQL query for potential SQL injection attacks",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The SQL query to validate"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="validate_file_path",
            description="Validate a file path for potential path traversal attacks",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The file path to validate"
                    }
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="validate_command",
            description="Validate a shell command for potential command injection",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to validate"
                    }
                },
                "required": ["command"]
            }
        ),
        Tool(
            name="scan_for_secrets",
            description="Scan text for potential secrets, credentials, or PII",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to scan for secrets"
                    },
                    "mask": {
                        "type": "boolean",
                        "description": "Whether to return masked version",
                        "default": False
                    }
                },
                "required": ["text"]
            }
        ),
        Tool(
            name="validate_mcp_request",
            description="Validate a complete MCP request for security issues",
            inputSchema={
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "description": "The MCP method being called"
                    },
                    "params": {
                        "type": "object",
                        "description": "The parameters for the MCP call"
                    },
                    "server_name": {
                        "type": "string",
                        "description": "The name of the target MCP server"
                    }
                },
                "required": ["method", "server_name"]
            }
        ),
        Tool(
            name="get_security_stats",
            description="Get statistics about security validations performed",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]

# Statistics tracking
stats = {
    "total_validations": 0,
    "blocked_requests": 0,
    "sql_injection_attempts": 0,
    "path_traversal_attempts": 0,
    "command_injection_attempts": 0,
    "pii_detections": 0
}

@server.call_tool()
async def call_tool(name: str, arguments: Any) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
    """Handle tool calls."""
    stats["total_validations"] += 1

    if name == "validate_sql_query":
        query = arguments["query"]
        is_valid, reason = validator.validate_request(
            "database.query",
            {"sql": query},
            "database"
        )

        if not is_valid:
            stats["blocked_requests"] += 1
            stats["sql_injection_attempts"] += 1

        return [
            TextContent(
                type="text",
                text=json.dumps({
                    "valid": is_valid,
                    "reason": reason,
                    "query": query,
                    "recommendation": "Use parameterized queries to prevent SQL injection" if not is_valid else None
                }, indent=2)
            )
        ]

    elif name == "validate_file_path":
        path = arguments["path"]
        is_valid, reason = validator.validate_request(
            "filesystem.read",
            {"path": path},
            "filesystem"
        )

        if not is_valid:
            stats["blocked_requests"] += 1
            stats["path_traversal_attempts"] += 1

        return [
            TextContent(
                type="text",
                text=json.dumps({
                    "valid": is_valid,
                    "reason": reason,
                    "path": path,
                    "recommendation": "Use absolute paths within a restricted base directory" if not is_valid else None
                }, indent=2)
            )
        ]

    elif name == "validate_command":
        command = arguments["command"]
        is_valid, reason = validator.validate_request(
            "system.execute",
            {"command": command},
            "system"
        )

        if not is_valid:
            stats["blocked_requests"] += 1
            stats["command_injection_attempts"] += 1

        return [
            TextContent(
                type="text",
                text=json.dumps({
                    "valid": is_valid,
                    "reason": reason,
                    "command": command,
                    "recommendation": "Use subprocess with argument lists instead of shell=True" if not is_valid else None
                }, indent=2)
            )
        ]

    elif name == "scan_for_secrets":
        text = arguments["text"]
        mask = arguments.get("mask", False)

        pii_found = detect_pii(text)
        if pii_found:
            stats["pii_detections"] += 1

        result = {
            "has_secrets": len(pii_found) > 0,
            "secrets_found": pii_found,
            "original_text": text if not mask else None,
            "masked_text": mask_pii(text) if mask else None,
            "recommendation": "Remove or mask sensitive data before logging or sharing" if pii_found else None
        }

        return [
            TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )
        ]

    elif name == "validate_mcp_request":
        method = arguments["method"]
        params = arguments.get("params", {})
        server_name = arguments["server_name"]

        is_valid, reason = validator.validate_request(method, params, server_name)

        if not is_valid:
            stats["blocked_requests"] += 1
            if "SQL" in reason:
                stats["sql_injection_attempts"] += 1
            elif "Path" in reason:
                stats["path_traversal_attempts"] += 1
            elif "Command" in reason:
                stats["command_injection_attempts"] += 1

        return [
            TextContent(
                type="text",
                text=json.dumps({
                    "valid": is_valid,
                    "reason": reason,
                    "method": method,
                    "server": server_name,
                    "severity": "high" if not is_valid else "none",
                    "recommendation": "Review and sanitize the request parameters" if not is_valid else "Request appears safe"
                }, indent=2)
            )
        ]

    elif name == "get_security_stats":
        return [
            TextContent(
                type="text",
                text=json.dumps({
                    "statistics": stats,
                    "threat_analysis": {
                        "total_threats_blocked": stats["blocked_requests"],
                        "block_rate": f"{(stats['blocked_requests'] / max(stats['total_validations'], 1) * 100):.1f}%",
                        "top_threats": {
                            "sql_injection": stats["sql_injection_attempts"],
                            "path_traversal": stats["path_traversal_attempts"],
                            "command_injection": stats["command_injection_attempts"]
                        }
                    }
                }, indent=2)
            )
        ]

    else:
        raise ValueError(f"Unknown tool: {name}")

async def main():
    """Run the MCP server."""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())
