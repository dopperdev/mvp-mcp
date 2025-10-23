"""Configuration management for MCP Security Gateway."""

from pydantic_settings import BaseSettings
from typing import Optional
import yaml
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "postgresql://mcp_user:mcp_password@localhost:5432/mcp_gateway"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Security
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24

    # Gateway
    gateway_host: str = "0.0.0.0"
    gateway_port: int = 8000
    log_level: str = "INFO"

    # Rate Limiting
    rate_limit_requests: int = 100
    rate_limit_period: int = 3600

    # Audit
    audit_log_retention_days: int = 30
    pii_detection_enabled: bool = True

    # Default Admin
    default_admin_username: str = "admin"
    default_admin_password: str = "admin"
    default_admin_email: str = "admin@example.com"

    class Config:
        env_file = ".env"
        case_sensitive = False


def load_yaml_config(config_path: str = "config/default.yaml") -> dict:
    """Load YAML configuration file."""
    path = Path(config_path)
    if path.exists():
        with open(path, 'r') as f:
            return yaml.safe_load(f)
    return {}


# Global settings instance
settings = Settings()
