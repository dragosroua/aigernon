"""Rate limiting for channel message handling."""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    max_requests: int = 30  # Maximum requests per window
    window_seconds: int = 60  # Time window in seconds
    burst_limit: int = 5  # Maximum burst requests in short window
    burst_window_seconds: int = 5  # Burst window in seconds
    enabled: bool = True


@dataclass
class UserRateState:
    """Track rate limit state for a user."""

    requests: list[float] = field(default_factory=list)

    def add_request(self, timestamp: float) -> None:
        """Record a request timestamp."""
        self.requests.append(timestamp)

    def cleanup(self, window_seconds: int, current_time: float) -> None:
        """Remove requests outside the window."""
        cutoff = current_time - window_seconds
        self.requests = [t for t in self.requests if t > cutoff]

    def count_in_window(self, window_seconds: int, current_time: float) -> int:
        """Count requests in the given window."""
        cutoff = current_time - window_seconds
        return sum(1 for t in self.requests if t > cutoff)


class RateLimiter:
    """
    Per-user rate limiter for message handling.

    Implements a sliding window rate limit with burst protection.
    """

    def __init__(self, config: RateLimitConfig | None = None):
        self.config = config or RateLimitConfig()
        self._state: dict[str, UserRateState] = defaultdict(UserRateState)
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # Cleanup every 5 minutes

    def check(self, user_id: str) -> tuple[bool, str | None]:
        """
        Check if a request from user_id is allowed.

        Args:
            user_id: The user identifier.

        Returns:
            Tuple of (allowed, reason). If not allowed, reason explains why.
        """
        if not self.config.enabled:
            return True, None

        current_time = time.time()
        state = self._state[user_id]

        # Periodic cleanup
        if current_time - self._last_cleanup > self._cleanup_interval:
            self._cleanup_all(current_time)

        # Clean up old requests for this user
        state.cleanup(self.config.window_seconds, current_time)

        # Check burst limit
        burst_count = state.count_in_window(self.config.burst_window_seconds, current_time)
        if burst_count >= self.config.burst_limit:
            logger.warning(f"Rate limit (burst) exceeded for user {user_id}: {burst_count}/{self.config.burst_limit}")
            return False, f"Too many requests. Please wait a few seconds. ({burst_count}/{self.config.burst_limit} in {self.config.burst_window_seconds}s)"

        # Check window limit
        window_count = state.count_in_window(self.config.window_seconds, current_time)
        if window_count >= self.config.max_requests:
            logger.warning(f"Rate limit (window) exceeded for user {user_id}: {window_count}/{self.config.max_requests}")
            return False, f"Rate limit exceeded. Please wait before sending more messages. ({window_count}/{self.config.max_requests} in {self.config.window_seconds}s)"

        # Allow and record
        state.add_request(current_time)
        return True, None

    def _cleanup_all(self, current_time: float) -> None:
        """Cleanup stale entries for all users."""
        stale_users = []
        for user_id, state in self._state.items():
            state.cleanup(self.config.window_seconds, current_time)
            if not state.requests:
                stale_users.append(user_id)

        for user_id in stale_users:
            del self._state[user_id]

        self._last_cleanup = current_time
        if stale_users:
            logger.debug(f"Rate limiter cleanup: removed {len(stale_users)} stale entries")

    def get_stats(self, user_id: str) -> dict[str, Any]:
        """Get rate limit stats for a user."""
        current_time = time.time()
        state = self._state.get(user_id)

        if not state:
            return {
                "requests_in_window": 0,
                "requests_in_burst_window": 0,
                "window_remaining": self.config.max_requests,
                "burst_remaining": self.config.burst_limit,
            }

        window_count = state.count_in_window(self.config.window_seconds, current_time)
        burst_count = state.count_in_window(self.config.burst_window_seconds, current_time)

        return {
            "requests_in_window": window_count,
            "requests_in_burst_window": burst_count,
            "window_remaining": max(0, self.config.max_requests - window_count),
            "burst_remaining": max(0, self.config.burst_limit - burst_count),
        }
