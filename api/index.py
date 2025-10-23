"""Vercel serverless function to serve the MCP Security Gateway landing page."""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
import os

app = FastAPI(title="MCP Security Gateway")

# Read the landing page HTML from the same directory
def get_landing_page():
    """Read landing page HTML."""
    try:
        # In Vercel, the file will be in the same directory as this script
        landing_path = os.path.join(os.path.dirname(__file__), "landing.html")
        with open(landing_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        # Fallback error page
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>MCP Security Gateway</title>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                }
                .container {
                    text-align: center;
                    padding: 2rem;
                }
                h1 { font-size: 3rem; margin-bottom: 1rem; }
                p { font-size: 1.25rem; opacity: 0.9; }
                .error { background: rgba(255,255,255,0.1); padding: 1rem; border-radius: 8px; margin-top: 2rem; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🛡️ MCP Security Gateway</h1>
                <p>Enterprise-grade security proxy for MCP communications</p>
                <div class="error">
                    <p>Landing page file not found. Please check deployment.</p>
                </div>
            </div>
        </body>
        </html>
        """

# Load landing page at startup
LANDING_PAGE_HTML = get_landing_page()

@app.get("/", response_class=HTMLResponse)
async def landing_page():
    """Serve the landing page."""
    return LANDING_PAGE_HTML

@app.get("/health")
async def health():
    """Health check."""
    return JSONResponse({
        "status": "healthy",
        "service": "mcp-security-gateway",
        "platform": "vercel",
        "version": "0.1.0"
    })

@app.get("/api")
async def api_info():
    """API info."""
    return JSONResponse({
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
    })

# Vercel handler
from mangum import Mangum
handler = Mangum(app, lifespan="off")
