"""MCP proxy core - handles request forwarding to MCP servers."""

import time
import uuid
import httpx
from typing import Optional, Dict, Any, Tuple
from loguru import logger

from src.models import User, MCPRequest, MCPResponse
from src.gateway.validator import SecurityValidator
from src.gateway.auth import check_user_permission, get_user_rate_limit
from src.gateway.rate_limiter import rate_limiter
from src.gateway.audit import audit_logger
from sqlalchemy.orm import Session


class MCPProxy:
    """MCP proxy that forwards requests to upstream MCP servers."""

    def __init__(self):
        """Initialize MCP proxy."""
        self.validator = SecurityValidator()
        self.http_client = httpx.AsyncClient(timeout=30.0)
        logger.info("MCP proxy initialized")

    async def close(self):
        """Close HTTP client."""
        await self.http_client.aclose()
        logger.info("MCP proxy HTTP client closed")

    async def forward_request(
        self,
        db: Session,
        user: User,
        server_name: str,
        request: MCPRequest,
        upstream_url: str,
        client_ip: str = "unknown",
        user_agent: str = "unknown"
    ) -> Tuple[MCPResponse, bool, Optional[str]]:
        """
        Forward MCP request to upstream server.

        Args:
            db: Database session
            user: Authenticated user
            server_name: MCP server name
            request: MCP request
            upstream_url: Upstream MCP server URL
            client_ip: Client IP address
            user_agent: User agent string

        Returns:
            Tuple of (response, blocked, block_reason)
        """
        request_id = str(uuid.uuid4())
        start_time = time.time()

        # Step 1: Check user permissions
        has_permission, permission_reason = check_user_permission(
            db, user, server_name, "read"
        )

        if not has_permission:
            logger.warning(
                f"Permission denied for {user.username} on {server_name}: {permission_reason}"
            )

            # Log blocked request
            await audit_logger.log_request(
                user_id=user.id,
                username=user.username,
                server_id=None,
                server_name=server_name,
                method=request.method,
                params=request.params,
                response_status=403,
                response_time_ms=(time.time() - start_time) * 1000,
                blocked=True,
                block_reason=f"Permission denied: {permission_reason}",
                client_ip=client_ip,
                user_agent=user_agent,
                request_id=request_id
            )

            return MCPResponse(
                jsonrpc="2.0",
                error={
                    "code": -32001,
                    "message": "Permission denied",
                    "data": permission_reason
                },
                id=request.id
            ), True, permission_reason

        # Step 2: Check rate limit
        rate_limit_requests, rate_limit_period = get_user_rate_limit(
            db, user, server_name
        )

        rate_limit_key = f"user:{user.id}:server:{server_name}"
        is_allowed, remaining = rate_limiter.is_allowed(
            rate_limit_key, rate_limit_requests, rate_limit_period
        )

        if not is_allowed:
            logger.warning(
                f"Rate limit exceeded for {user.username} on {server_name}"
            )

            # Log blocked request
            await audit_logger.log_request(
                user_id=user.id,
                username=user.username,
                server_id=None,
                server_name=server_name,
                method=request.method,
                params=request.params,
                response_status=429,
                response_time_ms=(time.time() - start_time) * 1000,
                blocked=True,
                block_reason="Rate limit exceeded",
                client_ip=client_ip,
                user_agent=user_agent,
                request_id=request_id
            )

            return MCPResponse(
                jsonrpc="2.0",
                error={
                    "code": -32002,
                    "message": "Rate limit exceeded",
                    "data": f"Limit: {rate_limit_requests} requests per {rate_limit_period} seconds"
                },
                id=request.id
            ), True, "Rate limit exceeded"

        # Step 3: Validate request for security issues
        is_valid, block_reason = self.validator.validate_request(
            request.method, request.params, server_name
        )

        if not is_valid:
            logger.warning(
                f"Security validation failed for {user.username} on {server_name}: {block_reason}"
            )

            # Log blocked request
            await audit_logger.log_request(
                user_id=user.id,
                username=user.username,
                server_id=None,
                server_name=server_name,
                method=request.method,
                params=request.params,
                response_status=400,
                response_time_ms=(time.time() - start_time) * 1000,
                blocked=True,
                block_reason=block_reason,
                client_ip=client_ip,
                user_agent=user_agent,
                request_id=request_id
            )

            return MCPResponse(
                jsonrpc="2.0",
                error={
                    "code": -32003,
                    "message": "Request blocked by security policy",
                    "data": block_reason
                },
                id=request.id
            ), True, block_reason

        # Step 4: Forward request to upstream MCP server
        try:
            logger.info(
                f"Forwarding request from {user.username} to {server_name}: {request.method}"
            )

            response = await self.http_client.post(
                upstream_url,
                json=request.dict(exclude_none=True),
                headers={
                    "Content-Type": "application/json",
                    "X-MCP-Gateway-User": user.username,
                    "X-MCP-Gateway-Request-ID": request_id
                }
            )

            response_time_ms = (time.time() - start_time) * 1000

            # Parse response
            if response.status_code == 200:
                response_data = response.json()
                mcp_response = MCPResponse(**response_data)

                # Log successful request
                await audit_logger.log_request(
                    user_id=user.id,
                    username=user.username,
                    server_id=None,
                    server_name=server_name,
                    method=request.method,
                    params=request.params,
                    response_status=200,
                    response_time_ms=response_time_ms,
                    blocked=False,
                    block_reason=None,
                    client_ip=client_ip,
                    user_agent=user_agent,
                    request_id=request_id
                )

                logger.info(
                    f"Request successful: {user.username} -> {server_name} -> {request.method} ({response_time_ms:.2f}ms)"
                )

                return mcp_response, False, None

            else:
                # Upstream error
                error_message = f"Upstream server error: {response.status_code}"
                logger.error(f"{error_message} - {response.text}")

                # Log failed request
                await audit_logger.log_request(
                    user_id=user.id,
                    username=user.username,
                    server_id=None,
                    server_name=server_name,
                    method=request.method,
                    params=request.params,
                    response_status=response.status_code,
                    response_time_ms=response_time_ms,
                    blocked=False,
                    block_reason=None,
                    client_ip=client_ip,
                    user_agent=user_agent,
                    request_id=request_id
                )

                return MCPResponse(
                    jsonrpc="2.0",
                    error={
                        "code": -32004,
                        "message": error_message,
                        "data": response.text[:500]  # Limit error data
                    },
                    id=request.id
                ), False, None

        except httpx.TimeoutException:
            response_time_ms = (time.time() - start_time) * 1000
            error_message = "Upstream server timeout"
            logger.error(f"{error_message} for {server_name}")

            await audit_logger.log_request(
                user_id=user.id,
                username=user.username,
                server_id=None,
                server_name=server_name,
                method=request.method,
                params=request.params,
                response_status=504,
                response_time_ms=response_time_ms,
                blocked=False,
                block_reason=None,
                client_ip=client_ip,
                user_agent=user_agent,
                request_id=request_id
            )

            return MCPResponse(
                jsonrpc="2.0",
                error={
                    "code": -32005,
                    "message": error_message,
                    "data": "The upstream MCP server did not respond in time"
                },
                id=request.id
            ), False, None

        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            error_message = f"Proxy error: {str(e)}"
            logger.error(error_message)

            await audit_logger.log_request(
                user_id=user.id,
                username=user.username,
                server_id=None,
                server_name=server_name,
                method=request.method,
                params=request.params,
                response_status=500,
                response_time_ms=response_time_ms,
                blocked=False,
                block_reason=None,
                client_ip=client_ip,
                user_agent=user_agent,
                request_id=request_id
            )

            return MCPResponse(
                jsonrpc="2.0",
                error={
                    "code": -32006,
                    "message": "Internal proxy error",
                    "data": str(e)[:500]
                },
                id=request.id
            ), False, None


# Global proxy instance
mcp_proxy = MCPProxy()
