"""Vercel serverless function to serve the MCP Security Gateway landing page."""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from mangum import Mangum
import os

app = FastAPI(title="MCP Security Gateway")

# Read the landing page HTML
def get_landing_page():
    """Read landing page from file."""
    landing_page_path = os.path.join(os.path.dirname(__file__), "..", "src", "static", "landing.html")
    try:
        with open(landing_page_path, "r") as f:
            return f.read()
    except FileNotFoundError:
        return """
        <html>
            <head><title>MCP Security Gateway</title></head>
            <body>
                <h1>MCP Security Gateway</h1>
                <p>Landing page not found. Path: {}</p>
            </body>
        </html>
        """.format(landing_page_path)

LANDING_PAGE_HTML = get_landing_page()

@app.get("/", response_class=HTMLResponse)
async def landing_page():
    """Serve the landing page."""
    return LANDING_PAGE_HTML

@app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy", "service": "mcp-security-gateway", "platform": "vercel"}

@app.get("/api")
async def api_info():
    """API info."""
    return {
        "service": "MCP Security Gateway",
        "version": "0.1.0",
        "status": "deployed on Vercel",
        "note": "This is a demo deployment. Full functionality requires self-hosting with Docker."
    }

# Vercel handler
handler = Mangum(app)
