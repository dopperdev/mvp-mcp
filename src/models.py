"""Database models and Pydantic schemas."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Float, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from pydantic import BaseModel, EmailStr, Field

Base = declarative_base()


# SQLAlchemy Models
class User(Base):
    """User model for authentication and authorization."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    permissions = relationship("UserPermission", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")


class MCPServer(Base):
    """MCP Server configuration."""

    __tablename__ = "mcp_servers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    upstream_url = Column(String(512), nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    permissions = relationship("UserPermission", back_populates="server")
    audit_logs = relationship("AuditLog", back_populates="server")
    blocked_patterns = relationship("BlockedPattern", back_populates="server")


class UserPermission(Base):
    """User permissions for MCP servers."""

    __tablename__ = "user_permissions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    server_id = Column(Integer, ForeignKey("mcp_servers.id", ondelete="CASCADE"))
    can_read = Column(Boolean, default=True)
    can_write = Column(Boolean, default=False)
    can_execute = Column(Boolean, default=False)
    rate_limit = Column(Integer, default=100)
    rate_limit_period = Column(Integer, default=3600)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="permissions")
    server = relationship("MCPServer", back_populates="permissions")


class AuditLog(Base):
    """Audit log for all MCP requests."""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    username = Column(String(255))
    server_id = Column(Integer, ForeignKey("mcp_servers.id", ondelete="SET NULL"), nullable=True)
    server_name = Column(String(255))
    method = Column(String(255))
    params = Column(JSON)
    response_status = Column(Integer)
    response_time_ms = Column(Float)
    blocked = Column(Boolean, default=False, index=True)
    block_reason = Column(Text)
    client_ip = Column(String(45))
    user_agent = Column(Text)
    request_id = Column(String(36))

    user = relationship("User", back_populates="audit_logs")
    server = relationship("MCPServer", back_populates="audit_logs")


class SecurityAlert(Base):
    """Security alerts for suspicious activities."""

    __tablename__ = "security_alerts"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    severity = Column(String(20), nullable=False, index=True)
    alert_type = Column(String(50), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    username = Column(String(255))
    description = Column(Text)
    details = Column(JSON)
    acknowledged = Column(Boolean, default=False, index=True)
    acknowledged_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)


class BlockedPattern(Base):
    """Blocked patterns configuration."""

    __tablename__ = "blocked_patterns"

    id = Column(Integer, primary_key=True, index=True)
    server_id = Column(Integer, ForeignKey("mcp_servers.id", ondelete="CASCADE"), nullable=True)
    pattern = Column(String(512), nullable=False)
    pattern_type = Column(String(50), nullable=False)
    is_regex = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    server = relationship("MCPServer", back_populates="blocked_patterns")


# Pydantic Schemas
class UserLogin(BaseModel):
    """User login request."""
    username: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=3)


class UserCreate(BaseModel):
    """User creation request."""
    username: str = Field(..., min_length=3, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8)
    is_admin: bool = False


class UserResponse(BaseModel):
    """User response."""
    id: int
    username: str
    email: str
    is_active: bool
    is_admin: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    """JWT token data."""
    username: Optional[str] = None
    user_id: Optional[int] = None
    is_admin: bool = False


class MCPRequest(BaseModel):
    """MCP request schema."""
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[str] = None


class MCPResponse(BaseModel):
    """MCP response schema."""
    jsonrpc: str = "2.0"
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    id: Optional[str] = None


class AuditLogCreate(BaseModel):
    """Audit log creation."""
    user_id: Optional[int] = None
    username: str
    server_id: Optional[int] = None
    server_name: str
    method: str
    params: Optional[Dict[str, Any]] = None
    response_status: int
    response_time_ms: float
    blocked: bool = False
    block_reason: Optional[str] = None
    client_ip: str
    user_agent: str
    request_id: str


class SecurityAlertCreate(BaseModel):
    """Security alert creation."""
    severity: str = Field(..., pattern="^(low|medium|high|critical)$")
    alert_type: str
    user_id: Optional[int] = None
    username: str
    description: str
    details: Optional[Dict[str, Any]] = None


class DashboardMetrics(BaseModel):
    """Dashboard metrics response."""
    total_requests: int
    blocked_requests: int
    active_users: int
    avg_response_time_ms: float
    requests_per_minute: float
    top_users: List[Dict[str, Any]]
    top_servers: List[Dict[str, Any]]
    recent_alerts: List[Dict[str, Any]]
