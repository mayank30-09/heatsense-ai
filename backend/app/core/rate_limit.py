"""In-memory rate limiting and throttling engine for authentication endpoints.

Architectural Note:
This module provides process-local rate limiting suitable for single-instance or single-worker
deployments. It tracks client request timestamps in an in-memory sliding window. In distributed,
multi-worker, or multi-pod environments (e.g. multiple Uvicorn workers behind NGINX or Kubernetes pods),
each worker process maintains its own independent memory window. For distributed rate limiting across
multiple workers/nodes, a shared store (such as Redis) should be integrated.
"""

from __future__ import annotations

import math
import threading
import time
from typing import Callable
from fastapi import Request

from backend.app.config import get_settings


class InMemoryRateLimiter:
    """Thread-safe sliding-window rate limiter with bounded in-memory storage."""

    def __init__(
        self,
        max_attempts: int = 5,
        window_seconds: int = 60,
        time_func: Callable[[], float] | None = None,
        max_tracked_keys: int = 10_000,
    ) -> None:
        if max_attempts <= 0:
            raise ValueError(f"max_attempts must be greater than 0, got {max_attempts}.")
        if window_seconds <= 0:
            raise ValueError(f"window_seconds must be greater than 0, got {window_seconds}.")
        if max_tracked_keys <= 0:
            raise ValueError(f"max_tracked_keys must be greater than 0, got {max_tracked_keys}.")

        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.max_tracked_keys = max_tracked_keys
        self.time_func = time_func or time.monotonic
        self._lock = threading.Lock()
        self._history: dict[str, list[float]] = {}

    def _cleanup_stale(self, now: float) -> None:
        """Internal cleanup helper executed under lock to prune expired keys and bound capacity."""
        cutoff = now - self.window_seconds
        stale_keys = [
            k for k, timestamps in self._history.items()
            if not timestamps or timestamps[-1] <= cutoff
        ]
        for k in stale_keys:
            self._history.pop(k, None)

        # If dictionary remains at or above capacity after pruning expired items, evict oldest entries
        if len(self._history) >= self.max_tracked_keys:
            sorted_keys = sorted(
                self._history.keys(),
                key=lambda k: self._history[k][-1] if self._history[k] else 0.0,
            )
            excess = len(self._history) - (self.max_tracked_keys // 2)
            for k in sorted_keys[:excess]:
                self._history.pop(k, None)

    def check_and_record(self, key: str) -> tuple[bool, int]:
        """Atomically check if request for key is permitted, and record attempt if within limit.

        This atomic check-and-increment eliminates TOCTOU race conditions during simultaneous requests.

        Returns:
            (is_allowed, retry_after_seconds)
        """
        now = self.time_func()
        cutoff = now - self.window_seconds

        with self._lock:
            if len(self._history) >= self.max_tracked_keys:
                self._cleanup_stale(now)

            timestamps = self._history.get(key, [])
            pruned = [t for t in timestamps if t > cutoff]

            if len(pruned) >= self.max_attempts:
                self._history[key] = pruned
                oldest = pruned[0]
                retry_after = max(1, int(math.ceil(oldest + self.window_seconds - now)))
                return False, retry_after

            pruned.append(now)
            self._history[key] = pruned
            return True, 0

    def is_allowed(self, key: str) -> tuple[bool, int]:
        """Check if request for key is permitted under the sliding-window limit without recording.

        Returns:
            (is_allowed, retry_after_seconds)
        """
        now = self.time_func()
        cutoff = now - self.window_seconds

        with self._lock:
            timestamps = self._history.get(key, [])
            pruned = [t for t in timestamps if t > cutoff]

            if not pruned:
                self._history.pop(key, None)
                return True, 0

            self._history[key] = pruned

            if len(pruned) >= self.max_attempts:
                oldest = pruned[0]
                retry_after = max(1, int(math.ceil(oldest + self.window_seconds - now)))
                return False, retry_after

            return True, 0

    def record_attempt(self, key: str) -> None:
        """Record an attempt timestamp for the specified key."""
        now = self.time_func()
        with self._lock:
            if len(self._history) >= self.max_tracked_keys:
                self._cleanup_stale(now)
            if key not in self._history:
                self._history[key] = []
            self._history[key].append(now)

    def reset(self, key: str | None = None) -> None:
        """Reset history for a specific key or clear all keys (primarily for testing)."""
        with self._lock:
            if key is not None:
                self._history.pop(key, None)
            else:
                self._history.clear()


def get_client_ip(request: Request) -> str:
    """Extract client IP address using authoritative socket peer address.

    Security Note:
    X-Forwarded-For is NOT trusted from arbitrary untrusted clients because doing so
    enables adversaries to bypass rate limiting and brute-force protections by spoofing
    arbitrary client IP headers. In the absence of a verified, deployment-specific trusted
    reverse proxy configuration, the socket peer address is strictly enforced.
    """
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


settings = get_settings()
auth_rate_limiter = InMemoryRateLimiter(
    max_attempts=settings.auth_rate_limit_max_attempts,
    window_seconds=settings.auth_rate_limit_window_seconds,
)
