"""Independent durable RQ worker runtime for imports, exports and notifications."""

import json
import logging
import signal

from rq import Queue, Worker

from backend.config import settings
from backend.infrastructure.monitoring import initialize_sentry
from backend.infrastructure.redis_client import close_redis, create_redis
from data.database import close_pools


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger("nexus.worker")
    initialize_sentry(settings.sentry_dsn, settings.app_env, worker=True)
    redis_client = create_redis(settings.redis_url)
    if redis_client is None or not redis_client.ping():
        raise RuntimeError("Worker cannot start without Redis")
    worker = Worker(
        [Queue(settings.queue_name, connection=redis_client)],
        connection=redis_client,
        name=f"nexus-{settings.app_env}-worker",
    )

    def shutdown(signum, _frame):
        logger.info(json.dumps({"event": "worker_shutdown", "signal": signum}))
        worker.request_stop(signum, None)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    logger.info(
        json.dumps(
            {
                "event": "worker_started",
                "environment": settings.app_env,
                "queue": settings.queue_name,
            }
        )
    )
    try:
        worker.work(with_scheduler=True)
    finally:
        close_redis(redis_client)
        close_pools()


if __name__ == "__main__":
    main()
