"""Audit logging for MCP Security Gateway.

This module provides async audit logging with PII detection and masking.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from loguru import logger
import json

from src.models import AuditLog, SecurityAlert, User, MCPServer
from src.database import get_db_context, get_async_connection, close_async_connection
from src.gateway.validator import detect_pii, mask_pii
from src.config import settings


class AuditLogger:
    """Async audit logger for MCP requests."""

    def __init__(self):
        """Initialize audit logger."""
        self.queue: asyncio.Queue = asyncio.Queue()
        self.worker_task: Optional[asyncio.Task] = None
        logger.info("Audit logger initialized")

    async def start(self):
        """Start the audit logger background worker."""
        self.worker_task = asyncio.create_task(self._worker())
        logger.info("Audit logger worker started")

    async def stop(self):
        """Stop the audit logger background worker."""
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
        logger.info("Audit logger worker stopped")

    async def log_request(
        self,
        user_id: Optional[int],
        username: str,
        server_id: Optional[int],
        server_name: str,
        method: str,
        params: Optional[Dict[str, Any]],
        response_status: int,
        response_time_ms: float,
        blocked: bool = False,
        block_reason: Optional[str] = None,
        client_ip: str = "unknown",
        user_agent: str = "unknown",
        request_id: str = "unknown"
    ):
        """
        Log MCP request asynchronously.

        Args:
            user_id: User ID
            username: Username
            server_id: MCP server ID
            server_name: MCP server name
            method: MCP method
            params: Request parameters
            response_status: HTTP response status
            response_time_ms: Response time in milliseconds
            blocked: Whether request was blocked
            block_reason: Reason for blocking
            client_ip: Client IP address
            user_agent: User agent string
            request_id: Unique request ID
        """
        log_entry = {
            "user_id": user_id,
            "username": username,
            "server_id": server_id,
            "server_name": server_name,
            "method": method,
            "params": params,
            "response_status": response_status,
            "response_time_ms": response_time_ms,
            "blocked": blocked,
            "block_reason": block_reason,
            "client_ip": client_ip,
            "user_agent": user_agent,
            "request_id": request_id,
            "timestamp": datetime.utcnow()
        }

        await self.queue.put(log_entry)

    async def _worker(self):
        """Background worker to write audit logs to database."""
        conn = None
        try:
            conn = await get_async_connection()

            while True:
                # Get log entry from queue
                log_entry = await self.queue.get()

                try:
                    # Detect PII if enabled
                    params_json = json.dumps(log_entry.get("params") or {})
                    contains_pii = []

                    if settings.pii_detection_enabled:
                        contains_pii = detect_pii(params_json)

                        # Mask PII for storage
                        if contains_pii:
                            params_json = mask_pii(params_json)
                            log_entry["params"] = json.loads(params_json)
                            logger.info(f"PII detected and masked in audit log: {contains_pii}")

                    # Insert audit log
                    await conn.execute(
                        """
                        INSERT INTO audit_logs (
                            timestamp, user_id, username, server_id, server_name,
                            method, params, response_status, response_time_ms,
                            blocked, block_reason, client_ip, user_agent, request_id
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                        """,
                        log_entry["timestamp"],
                        log_entry["user_id"],
                        log_entry["username"],
                        log_entry["server_id"],
                        log_entry["server_name"],
                        log_entry["method"],
                        json.dumps(log_entry["params"]),
                        log_entry["response_status"],
                        log_entry["response_time_ms"],
                        log_entry["blocked"],
                        log_entry["block_reason"],
                        log_entry["client_ip"],
                        log_entry["user_agent"],
                        log_entry["request_id"]
                    )

                    # Create security alert if blocked
                    if log_entry["blocked"]:
                        await self._create_security_alert(
                            conn,
                            log_entry["user_id"],
                            log_entry["username"],
                            log_entry["block_reason"],
                            log_entry
                        )

                except Exception as e:
                    logger.error(f"Failed to write audit log: {e}")

                finally:
                    self.queue.task_done()

        except asyncio.CancelledError:
            logger.info("Audit logger worker cancelled")
            raise
        except Exception as e:
            logger.error(f"Audit logger worker error: {e}")
        finally:
            if conn:
                await close_async_connection(conn)

    async def _create_security_alert(
        self,
        conn,
        user_id: Optional[int],
        username: str,
        block_reason: str,
        log_entry: Dict[str, Any]
    ):
        """Create security alert for blocked request."""
        try:
            # Determine severity based on block reason
            severity = "medium"
            if "SQL Injection" in block_reason:
                severity = "high"
            elif "Command Injection" in block_reason:
                severity = "critical"
            elif "Path Traversal" in block_reason:
                severity = "high"

            # Determine alert type
            alert_type = "unknown"
            if "SQL Injection" in block_reason:
                alert_type = "sql_injection"
            elif "Command Injection" in block_reason:
                alert_type = "command_injection"
            elif "Path Traversal" in block_reason:
                alert_type = "path_traversal"
            elif "Base64" in block_reason:
                alert_type = "base64_exploit"
            elif "JNDI" in block_reason:
                alert_type = "jndi_injection"

            await conn.execute(
                """
                INSERT INTO security_alerts (
                    timestamp, severity, alert_type, user_id, username,
                    description, details
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                datetime.utcnow(),
                severity,
                alert_type,
                user_id,
                username,
                block_reason,
                json.dumps({
                    "method": log_entry["method"],
                    "server": log_entry["server_name"],
                    "client_ip": log_entry["client_ip"],
                    "request_id": log_entry["request_id"]
                })
            )

            logger.warning(
                f"Security alert created: {alert_type} - {severity} - {username}"
            )

        except Exception as e:
            logger.error(f"Failed to create security alert: {e}")


def get_audit_logs(
    db: Session,
    limit: int = 100,
    offset: int = 0,
    user_id: Optional[int] = None,
    server_id: Optional[int] = None,
    blocked_only: bool = False,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> List[AuditLog]:
    """
    Get audit logs with filtering.

    Args:
        db: Database session
        limit: Maximum number of logs to return
        offset: Offset for pagination
        user_id: Filter by user ID
        server_id: Filter by server ID
        blocked_only: Only return blocked requests
        start_date: Start date filter
        end_date: End date filter

    Returns:
        List of audit logs
    """
    query = db.query(AuditLog)

    if user_id:
        query = query.filter(AuditLog.user_id == user_id)

    if server_id:
        query = query.filter(AuditLog.server_id == server_id)

    if blocked_only:
        query = query.filter(AuditLog.blocked == True)

    if start_date:
        query = query.filter(AuditLog.timestamp >= start_date)

    if end_date:
        query = query.filter(AuditLog.timestamp <= end_date)

    query = query.order_by(AuditLog.timestamp.desc())
    query = query.limit(limit).offset(offset)

    return query.all()


def get_security_alerts(
    db: Session,
    limit: int = 50,
    offset: int = 0,
    severity: Optional[str] = None,
    acknowledged: Optional[bool] = False
) -> List[SecurityAlert]:
    """
    Get security alerts with filtering.

    Args:
        db: Database session
        limit: Maximum number of alerts to return
        offset: Offset for pagination
        severity: Filter by severity
        acknowledged: Filter by acknowledged status

    Returns:
        List of security alerts
    """
    query = db.query(SecurityAlert)

    if severity:
        query = query.filter(SecurityAlert.severity == severity)

    if acknowledged is not None:
        query = query.filter(SecurityAlert.acknowledged == acknowledged)

    query = query.order_by(SecurityAlert.timestamp.desc())
    query = query.limit(limit).offset(offset)

    return query.all()


def cleanup_old_audit_logs(db: Session, retention_days: int = 30):
    """
    Clean up audit logs older than retention period.

    Args:
        db: Database session
        retention_days: Number of days to retain logs
    """
    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

    deleted = db.query(AuditLog).filter(
        AuditLog.timestamp < cutoff_date
    ).delete()

    db.commit()

    logger.info(f"Cleaned up {deleted} audit logs older than {retention_days} days")


# Global audit logger instance
audit_logger = AuditLogger()
