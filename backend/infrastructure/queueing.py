from __future__ import annotations

from typing import Any, Callable


def integration_echo(value: str) -> str:
    """Importable no-op used by the real Redis/RQ integration gate."""
    return value


class JobQueue:
    def __init__(self, redis_client: Any, name: str, *, synchronous: bool = False):
        self.redis = redis_client
        self.name = name
        self.synchronous = synchronous

    def enqueue(
        self,
        function: Callable,
        *args: Any,
        job_id: str,
        retry_count: int = 3,
        **kwargs: Any,
    ) -> str:
        if self.synchronous:
            function(*args, **kwargs)
            return job_id
        if self.redis is None:
            raise RuntimeError("The durable queue is unavailable")
        from rq import Queue, Retry

        Queue(self.name, connection=self.redis).enqueue(
            function,
            *args,
            **kwargs,
            job_id=job_id,
            retry=Retry(max=retry_count, interval=[10, 30, 120]),
            job_timeout="30m",
            result_ttl=86400,
            failure_ttl=604800,
        )
        return job_id
