"""Authentication and authorization for MCP Security Gateway.

This module implements JWT-based authentication and user-based access control.
"""

from datetime import datetime, timedelta
from typing import Optional, Tuple
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from loguru import logger

from src.config import settings
from src.database import get_db
from src.models import User, UserPermission, MCPServer, TokenData


# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Bearer token security
security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token.

    Args:
        data: Data to encode in token
        expires_delta: Token expiration time

    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.jwt_expiration_hours)

    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm
    )

    return encoded_jwt


def decode_token(token: str) -> Optional[TokenData]:
    """
    Decode and validate JWT token.

    Args:
        token: JWT token string

    Returns:
        TokenData if valid, None otherwise
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm]
        )

        username: str = payload.get("sub")
        user_id: int = payload.get("user_id")
        is_admin: bool = payload.get("is_admin", False)

        if username is None:
            return None

        return TokenData(username=username, user_id=user_id, is_admin=is_admin)

    except JWTError as e:
        logger.warning(f"JWT decode error: {e}")
        return None


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """
    Authenticate user with username and password.

    Args:
        db: Database session
        username: Username
        password: Plain text password

    Returns:
        User object if authenticated, None otherwise
    """
    user = db.query(User).filter(User.username == username).first()

    if not user:
        logger.warning(f"Authentication failed: user not found - {username}")
        return None

    if not user.is_active:
        logger.warning(f"Authentication failed: user inactive - {username}")
        return None

    if not verify_password(password, user.hashed_password):
        logger.warning(f"Authentication failed: invalid password - {username}")
        return None

    logger.info(f"User authenticated successfully: {username}")
    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current authenticated user from JWT token.

    Args:
        credentials: Bearer token credentials
        db: Database session

    Returns:
        Current user

    Raises:
        HTTPException: If authentication fails
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials
    token_data = decode_token(token)

    if token_data is None or token_data.username is None:
        raise credentials_exception

    user = db.query(User).filter(User.username == token_data.username).first()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    return user


async def get_current_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current admin user.

    Args:
        current_user: Current authenticated user

    Returns:
        Current user if admin

    Raises:
        HTTPException: If user is not admin
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )

    return current_user


def check_user_permission(
    db: Session,
    user: User,
    server_name: str,
    permission_type: str = "read"
) -> Tuple[bool, Optional[str]]:
    """
    Check if user has permission to access MCP server.

    Args:
        db: Database session
        user: User object
        server_name: MCP server name
        permission_type: Type of permission (read, write, execute)

    Returns:
        Tuple of (has_permission, reason)
    """
    # Admin users have access to everything
    if user.is_admin:
        return True, None

    # Get server
    server = db.query(MCPServer).filter(MCPServer.name == server_name).first()
    if not server:
        return False, f"MCP server not found: {server_name}"

    if not server.is_active:
        return False, f"MCP server is inactive: {server_name}"

    # Get user permission for this server
    permission = db.query(UserPermission).filter(
        UserPermission.user_id == user.id,
        UserPermission.server_id == server.id
    ).first()

    if not permission:
        return False, f"No permission for server: {server_name}"

    # Check specific permission type
    if permission_type == "read" and not permission.can_read:
        return False, "Read permission denied"
    elif permission_type == "write" and not permission.can_write:
        return False, "Write permission denied"
    elif permission_type == "execute" and not permission.can_execute:
        return False, "Execute permission denied"

    return True, None


def get_user_rate_limit(db: Session, user: User, server_name: str) -> Tuple[int, int]:
    """
    Get user's rate limit for a specific server.

    Args:
        db: Database session
        user: User object
        server_name: MCP server name

    Returns:
        Tuple of (requests, period_in_seconds)
    """
    # Admin users get higher default limits
    if user.is_admin:
        return 1000, 3600

    # Get server
    server = db.query(MCPServer).filter(MCPServer.name == server_name).first()
    if not server:
        return settings.rate_limit_requests, settings.rate_limit_period

    # Get user permission for this server
    permission = db.query(UserPermission).filter(
        UserPermission.user_id == user.id,
        UserPermission.server_id == server.id
    ).first()

    if not permission:
        return settings.rate_limit_requests, settings.rate_limit_period

    return permission.rate_limit, permission.rate_limit_period


def create_user(
    db: Session,
    username: str,
    email: str,
    password: str,
    is_admin: bool = False
) -> User:
    """
    Create a new user.

    Args:
        db: Database session
        username: Username
        email: Email address
        password: Plain text password
        is_admin: Whether user is admin

    Returns:
        Created user

    Raises:
        ValueError: If user already exists
    """
    # Check if user exists
    existing_user = db.query(User).filter(
        (User.username == username) | (User.email == email)
    ).first()

    if existing_user:
        raise ValueError("User already exists")

    # Create user
    hashed_password = get_password_hash(password)
    user = User(
        username=username,
        email=email,
        hashed_password=hashed_password,
        is_admin=is_admin
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info(f"User created: {username}")
    return user
