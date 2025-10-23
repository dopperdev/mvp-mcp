"""MCP Security Gateway - Main FastAPI Application."""

import sys
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from prometheus_client import Counter, Histogram, generate_latest
from loguru import logger
import uvicorn

from src.config import settings, load_yaml_config
from src.database import get_db, init_db
from src.models import (
    User, MCPServer, UserLogin, UserCreate, UserResponse,
    Token, MCPRequest, MCPResponse, DashboardMetrics
)
from src.gateway.auth import (
    authenticate_user, create_access_token, get_current_user,
    get_current_admin_user, create_user
)
from src.gateway.proxy import mcp_proxy
from src.gateway.audit import audit_logger, get_audit_logs, get_security_alerts
from src.gateway.rate_limiter import rate_limiter


# Configure logging
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=settings.log_level
)
logger.add(
    "logs/mcp-gateway.log",
    rotation="500 MB",
    retention="30 days",
    level=settings.log_level
)

# Prometheus metrics
request_counter = Counter(
    'mcp_gateway_requests_total',
    'Total MCP requests',
    ['method', 'server', 'status']
)
request_duration = Histogram(
    'mcp_gateway_request_duration_seconds',
    'Request duration in seconds',
    ['method', 'server']
)
blocked_requests = Counter(
    'mcp_gateway_blocked_requests_total',
    'Total blocked requests',
    ['reason']
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting MCP Security Gateway...")

    # Initialize database
    try:
        init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

    # Start audit logger
    try:
        await audit_logger.start()
        logger.info("Audit logger started")
    except Exception as e:
        logger.error(f"Failed to start audit logger: {e}")
        raise

    logger.info(f"MCP Security Gateway running on http://{settings.gateway_host}:{settings.gateway_port}")

    yield

    # Shutdown
    logger.info("Shutting down MCP Security Gateway...")

    # Stop audit logger
    await audit_logger.stop()

    # Close proxy
    await mcp_proxy.close()

    # Close rate limiter
    rate_limiter.close()

    logger.info("MCP Security Gateway stopped")


# Create FastAPI app
app = FastAPI(
    title="MCP Security Gateway",
    description="Enterprise-grade security proxy for MCP communications",
    version="0.1.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "mcp-security-gateway"}


@app.get("/ready")
async def readiness_check(db: Session = Depends(get_db)):
    """Readiness check endpoint."""
    try:
        # Check database connection
        db.execute("SELECT 1")
        return {"status": "ready", "database": "connected"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database not ready: {str(e)}"
        )


# Prometheus metrics endpoint
@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return generate_latest()


# Authentication endpoints
@app.post("/auth/login", response_model=Token)
async def login(user_login: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticate user and return JWT token.

    Default credentials:
    - Username: admin
    - Password: admin
    """
    user = authenticate_user(db, user_login.username, user_login.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    access_token_expires = timedelta(hours=settings.jwt_expiration_hours)
    access_token = create_access_token(
        data={
            "sub": user.username,
            "user_id": user.id,
            "is_admin": user.is_admin
        },
        expires_delta=access_token_expires
    )

    logger.info(f"User logged in: {user.username}")

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.jwt_expiration_hours * 3600
    }


@app.post("/auth/register", response_model=UserResponse)
async def register(
    user_create: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Register new user (admin only)."""
    try:
        user = create_user(
            db,
            user_create.username,
            user_create.email,
            user_create.password,
            user_create.is_admin
        )
        return user
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@app.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    return current_user


# MCP Proxy endpoint
@app.post("/mcp/{server_name}", response_model=MCPResponse)
async def proxy_mcp_request(
    server_name: str,
    request: MCPRequest,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Proxy MCP request to upstream server.

    This endpoint:
    1. Validates user permissions
    2. Checks rate limits
    3. Validates request for security issues
    4. Forwards to upstream MCP server
    5. Logs the request for audit
    """
    # Get server configuration
    server = db.query(MCPServer).filter(MCPServer.name == server_name).first()

    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MCP server not found: {server_name}"
        )

    if not server.is_active:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"MCP server is inactive: {server_name}"
        )

    # Get client info
    client_ip = req.client.host if req.client else "unknown"
    user_agent = req.headers.get("user-agent", "unknown")

    # Forward request through proxy
    response, blocked, block_reason = await mcp_proxy.forward_request(
        db=db,
        user=current_user,
        server_name=server_name,
        request=request,
        upstream_url=server.upstream_url,
        client_ip=client_ip,
        user_agent=user_agent
    )

    # Update metrics
    status_label = "blocked" if blocked else "success"
    request_counter.labels(
        method=request.method,
        server=server_name,
        status=status_label
    ).inc()

    if blocked:
        blocked_requests.labels(reason=block_reason or "unknown").inc()

    return response


# Admin endpoints
@app.get("/admin/servers", response_model=List[dict])
async def list_servers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """List all MCP servers (admin only)."""
    servers = db.query(MCPServer).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "upstream_url": s.upstream_url,
            "description": s.description,
            "is_active": s.is_active,
            "created_at": s.created_at
        }
        for s in servers
    ]


@app.get("/admin/audit-logs")
async def list_audit_logs(
    limit: int = 100,
    offset: int = 0,
    blocked_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Get audit logs (admin only)."""
    logs = get_audit_logs(
        db,
        limit=limit,
        offset=offset,
        blocked_only=blocked_only
    )

    return [
        {
            "id": log.id,
            "timestamp": log.timestamp,
            "username": log.username,
            "server_name": log.server_name,
            "method": log.method,
            "params": log.params,
            "response_status": log.response_status,
            "response_time_ms": log.response_time_ms,
            "blocked": log.blocked,
            "block_reason": log.block_reason,
            "client_ip": log.client_ip
        }
        for log in logs
    ]


@app.get("/admin/security-alerts")
async def list_security_alerts(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Get security alerts (admin only)."""
    alerts = get_security_alerts(db, limit=limit, offset=offset)

    return [
        {
            "id": alert.id,
            "timestamp": alert.timestamp,
            "severity": alert.severity,
            "alert_type": alert.alert_type,
            "username": alert.username,
            "description": alert.description,
            "details": alert.details,
            "acknowledged": alert.acknowledged
        }
        for alert in alerts
    ]


@app.get("/admin/metrics", response_model=DashboardMetrics)
async def get_dashboard_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get dashboard metrics."""
    from datetime import datetime, timedelta
    from sqlalchemy import func
    from src.models import AuditLog

    # Last 1 hour
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)

    # Total requests
    total_requests = db.query(func.count(AuditLog.id)).scalar()

    # Blocked requests
    blocked_requests_count = db.query(func.count(AuditLog.id)).filter(
        AuditLog.blocked == True
    ).scalar()

    # Active users (users who made requests in last hour)
    active_users = db.query(func.count(func.distinct(AuditLog.user_id))).filter(
        AuditLog.timestamp >= one_hour_ago
    ).scalar()

    # Average response time
    avg_response_time = db.query(func.avg(AuditLog.response_time_ms)).scalar() or 0.0

    # Requests per minute (last hour)
    recent_requests = db.query(func.count(AuditLog.id)).filter(
        AuditLog.timestamp >= one_hour_ago
    ).scalar()
    requests_per_minute = recent_requests / 60.0

    # Top users
    top_users_query = db.query(
        AuditLog.username,
        func.count(AuditLog.id).label('count')
    ).filter(
        AuditLog.timestamp >= one_hour_ago
    ).group_by(AuditLog.username).order_by(func.count(AuditLog.id).desc()).limit(5)

    top_users = [
        {"username": row.username, "requests": row.count}
        for row in top_users_query
    ]

    # Top servers
    top_servers_query = db.query(
        AuditLog.server_name,
        func.count(AuditLog.id).label('count')
    ).filter(
        AuditLog.timestamp >= one_hour_ago
    ).group_by(AuditLog.server_name).order_by(func.count(AuditLog.id).desc()).limit(5)

    top_servers = [
        {"server": row.server_name, "requests": row.count}
        for row in top_servers_query
    ]

    # Recent alerts
    recent_alerts_data = get_security_alerts(db, limit=10, offset=0)
    recent_alerts = [
        {
            "timestamp": alert.timestamp.isoformat(),
            "severity": alert.severity,
            "description": alert.description,
            "username": alert.username
        }
        for alert in recent_alerts_data
    ]

    return {
        "total_requests": total_requests or 0,
        "blocked_requests": blocked_requests_count or 0,
        "active_users": active_users or 0,
        "avg_response_time_ms": float(avg_response_time),
        "requests_per_minute": requests_per_minute,
        "top_users": top_users,
        "top_servers": top_servers,
        "recent_alerts": recent_alerts
    }


# Dashboard
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Serve the monitoring dashboard."""
    try:
        with open("src/dashboard/index.html", "r") as f:
            return f.read()
    except FileNotFoundError:
        return HTMLResponse(
            content="<h1>Dashboard not found</h1><p>Please ensure src/dashboard/index.html exists.</p>",
            status_code=404
        )


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "MCP Security Gateway",
        "version": "0.1.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "metrics": "/metrics",
            "login": "/auth/login",
            "dashboard": "/dashboard",
            "docs": "/docs"
        }
    }


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host=settings.gateway_host,
        port=settings.gateway_port,
        reload=True
    )
