"""Rate limiting for MCP Security Gateway using Redis."""

import time
from typing import Optional, Tuple
import redis
from loguru import logger

from src.config import settings


class RateLimiter:
    """Token bucket rate limiter using Redis."""

    def __init__(self, redis_url: Optional[str] = None):
        """
        Initialize rate limiter.

        Args:
            redis_url: Redis connection URL
        """
        self.redis_url = redis_url or settings.redis_url
        try:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
            self.redis_client.ping()
            logger.info(f"Rate limiter connected to Redis: {self.redis_url}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis_client = None

    def is_allowed(
        self,
        key: str,
        max_requests: int,
        period_seconds: int
    ) -> Tuple[bool, int]:
        """
        Check if request is allowed under rate limit.

        Uses sliding window algorithm for accurate rate limiting.

        Args:
            key: Unique key for rate limit (e.g., "user:123:server:db")
            max_requests: Maximum requests allowed
            period_seconds: Time period in seconds

        Returns:
            Tuple of (is_allowed, remaining_requests)
        """
        if not self.redis_client:
            # If Redis is not available, allow all requests
            logger.warning("Redis not available, rate limiting disabled")
            return True, max_requests

        try:
            now = time.time()
            window_start = now - period_seconds

            # Redis key for this rate limit
            redis_key = f"ratelimit:{key}"

            # Use Redis pipeline for atomic operations
            pipe = self.redis_client.pipeline()

            # Remove old entries outside the window
            pipe.zremrangebyscore(redis_key, 0, window_start)

            # Count requests in current window
            pipe.zcard(redis_key)

            # Add current request
            pipe.zadd(redis_key, {str(now): now})

            # Set expiration
            pipe.expire(redis_key, period_seconds + 1)

            results = pipe.execute()

            # Get count before adding current request
            current_count = results[1]

            if current_count < max_requests:
                remaining = max_requests - current_count - 1
                return True, remaining
            else:
                # Remove the request we just added since it's not allowed
                self.redis_client.zrem(redis_key, str(now))
                return False, 0

        except Exception as e:
            logger.error(f"Rate limiter error: {e}")
            # On error, allow the request to avoid blocking legitimate traffic
            return True, max_requests

    def get_remaining(self, key: str, max_requests: int, period_seconds: int) -> int:
        """
        Get remaining requests for a key.

        Args:
            key: Unique key for rate limit
            max_requests: Maximum requests allowed
            period_seconds: Time period in seconds

        Returns:
            Number of remaining requests
        """
        if not self.redis_client:
            return max_requests

        try:
            now = time.time()
            window_start = now - period_seconds
            redis_key = f"ratelimit:{key}"

            # Clean up old entries
            self.redis_client.zremrangebyscore(redis_key, 0, window_start)

            # Count current requests
            current_count = self.redis_client.zcard(redis_key)

            return max(0, max_requests - current_count)

        except Exception as e:
            logger.error(f"Error getting remaining requests: {e}")
            return max_requests

    def reset(self, key: str):
        """
        Reset rate limit for a key.

        Args:
            key: Unique key for rate limit
        """
        if not self.redis_client:
            return

        try:
            redis_key = f"ratelimit:{key}"
            self.redis_client.delete(redis_key)
            logger.info(f"Rate limit reset for key: {key}")
        except Exception as e:
            logger.error(f"Error resetting rate limit: {e}")

    def close(self):
        """Close Redis connection."""
        if self.redis_client:
            self.redis_client.close()
            logger.info("Rate limiter Redis connection closed")


# Global rate limiter instance
rate_limiter = RateLimiter()
