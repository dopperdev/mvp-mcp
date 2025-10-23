"""Vercel serverless function to serve the MCP Security Gateway landing page."""

import os
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Read the landing page HTML at import time
def get_landing_page():
    """Read landing page HTML."""
    try:
        landing_path = os.path.join(os.path.dirname(__file__), "landing.html")
        with open(landing_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        # Fallback error page
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>MCP Security Gateway</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                }}
                .container {{
                    text-align: center;
                    padding: 2rem;
                    max-width: 600px;
                }}
                h1 {{ font-size: 3rem; margin-bottom: 1rem; }}
                p {{ font-size: 1.25rem; opacity: 0.9; }}
                .error {{ background: rgba(255,255,255,0.1); padding: 1rem; border-radius: 8px; margin-top: 2rem; font-size: 0.9rem; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🛡️ MCP Security Gateway</h1>
                <p>Enterprise-grade security proxy for MCP communications</p>
                <div class="error">
                    <p><strong>Error loading landing page</strong></p>
                    <p>Error: {str(e)}</p>
                    <p>Path: {os.path.dirname(__file__)}</p>
                    <p>Files: {os.listdir(os.path.dirname(__file__)) if os.path.exists(os.path.dirname(__file__)) else 'N/A'}</p>
                </div>
            </div>
        </body>
        </html>
        """

# Load landing page
LANDING_PAGE_HTML = get_landing_page()

class handler(BaseHTTPRequestHandler):
    """Vercel serverless function handler."""

    def do_GET(self):
        """Handle GET requests."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        # Health check endpoint
        if path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                "status": "healthy",
                "service": "mcp-security-gateway",
                "platform": "vercel",
                "version": "0.1.0"
            }
            import json
            self.wfile.write(json.dumps(response).encode())
            return

        # API info endpoint
        if path == '/api':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                "service": "MCP Security Gateway",
                "version": "0.1.0",
                "status": "deployed on Vercel",
                "description": "Enterprise-grade security proxy for MCP communications",
                "note": "This is a demo deployment showing the landing page. Full functionality requires self-hosting with Docker.",
                "documentation": {
                    "github": "https://github.com/your-repo/mcp-security-gateway",
                    "readme": "README.md",
                    "security": "SECURITY.md",
                    "deployment": "DEPLOYMENT.md"
                },
                "features": {
                    "authentication": "JWT-based with RBAC",
                    "security": "SQL injection, path traversal, command injection prevention",
                    "rate_limiting": "Token bucket algorithm with Redis",
                    "audit_logging": "Full audit trail with PII masking",
                    "monitoring": "Real-time dashboard with Prometheus metrics"
                }
            }
            import json
            self.wfile.write(json.dumps(response, indent=2).encode())
            return

        # Default: serve landing page
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(LANDING_PAGE_HTML.encode('utf-8'))
