from __future__ import annotations

import time
from typing import Any


RATE_LIMIT_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return current <= tonumber(ARGV[2])
"""


def create_redis(url: str):
    if not url:
        return None
    try:
        import redis
        from redis.backoff import ExponentialBackoff
        from redis.retry import Retry
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Redis support requires redis-py") from exc
    return redis.Redis.from_url(
        url,
        decode_responses=False,
        socket_connect_timeout=3,
        socket_timeout=3,
        health_check_interval=30,
        retry=Retry(ExponentialBackoff(cap=2, base=0.1), retries=3),
        retry_on_timeout=True,
    )


class RedisRateLimiter:
    """Shared fixed-window limiter. Redis failure denies sensitive traffic."""

    def __init__(self, client: Any):
        self.client = client

    def allow(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        if self.client is None:
            return False
        bucket = int(time.time()) // window_seconds
        try:
            return bool(
                self.client.eval(
                    RATE_LIMIT_SCRIPT,
                    1,
                    f"nexus:rate:{key}:{bucket}",
                    window_seconds + 1,
                    limit,
                )
            )
        except Exception:
            return False


def redis_health(client: Any) -> bool:
    if client is None:
        return False
    try:
        return bool(client.ping())
    except Exception:
        return False


def close_redis(client: Any) -> None:
    if client is not None:
        client.close()
