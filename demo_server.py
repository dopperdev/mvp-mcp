"""Simple demo server to showcase the landing page without database dependencies."""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI(title="MCP Security Gateway - Demo")

@app.get("/", response_class=HTMLResponse)
async def landing_page():
    """Serve the landing page."""
    try:
        with open("src/static/landing.html", "r") as f:
            return f.read()
    except FileNotFoundError:
        return HTMLResponse(
            content="<h1>Landing page not found</h1>",
            status_code=404
        )

@app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy", "service": "mcp-security-gateway-demo"}

@app.get("/api")
async def api_info():
    """API info."""
    return {
        "service": "MCP Security Gateway",
        "version": "0.1.0",
        "status": "demo mode - landing page only",
        "note": "Full functionality requires Docker Compose with PostgreSQL and Redis"
    }

if __name__ == "__main__":
    print("=" * 80)
    print("MCP Security Gateway - Landing Page Demo")
    print("=" * 80)
    print()
    print("Starting server at http://localhost:8000")
    print()
    print("Available endpoints:")
    print("  - Landing Page:  http://localhost:8000")
    print("  - API Info:      http://localhost:8000/api")
    print("  - Health Check:  http://localhost:8000/health")
    print()
    print("NOTE: This is demo mode showing only the landing page.")
    print("For full functionality, use: docker-compose up -d")
    print("=" * 80)
    print()

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
