import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from fastapi import HTTPException

from backend.config import Settings
from backend.infrastructure.redis_client import RedisRateLimiter, create_redis
from backend.infrastructure.storage import LocalStorage
from data.database import close_pools, _translate_parameters
from data.migrate import migration_status, run_migrations
from backend.operations.router import readiness


class SharedFakeRedis:
    def __init__(self, values=None):
        self.values = values if values is not None else {}

    def eval(self, _script, _keys, key, _ttl, limit):
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key] <= int(limit)


class StagingInfrastructureUnitTests(unittest.TestCase):
    def test_staging_configuration_requires_all_shared_infrastructure(self):
        with patch.dict(os.environ, {"APP_ENV": "staging"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "DATABASE_URL"):
                Settings.from_environment()

    def test_valid_staging_configuration_is_secure_and_postgres_only(self):
        environment = {
            "APP_ENV": "staging",
            "DATABASE_URL": "postgresql://db/nexus",
            "CORS_ORIGINS": "https://staging.example",
            "JWT_SECRET": "x" * 40,
            "REDIS_URL": "redis://redis/0",
            "STORAGE_BACKEND": "s3",
            "S3_BUCKET": "nexus-staging",
            "SENTRY_DSN": "https://public@example.invalid/1",
        }
        with patch.dict(os.environ, environment, clear=True):
            result = Settings.from_environment()
        self.assertTrue(result.cookie_secure)
        self.assertEqual("postgresql://db/nexus", result.database_path)

    def test_two_instances_share_rate_limit_state(self):
        state = {}
        first = RedisRateLimiter(SharedFakeRedis(state))
        second = RedisRateLimiter(SharedFakeRedis(state))
        self.assertTrue(first.allow("login:client", 2))
        self.assertTrue(second.allow("login:client", 2))
        self.assertFalse(first.allow("login:client", 2))

    def test_local_object_storage_blocks_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = LocalStorage(Path(directory))
            with self.assertRaises(ValueError):
                storage.exists("../private.txt")

    def test_readiness_fails_closed_when_storage_is_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "ready.db"
            run_migrations(database)
            storage = SimpleNamespace(health=lambda: False)
            state = SimpleNamespace(database_path=database, storage=storage, redis=None)
            request = SimpleNamespace(app=SimpleNamespace(state=state))
            with self.assertRaises(HTTPException) as raised:
                readiness(request)
            self.assertEqual(503, raised.exception.status_code)

    def test_postgres_query_translation(self):
        translated = _translate_parameters(
            "SELECT date(created_at) FROM events WHERE datetime(created_at)>=datetime(?)"
        )
        self.assertIn("substr(created_at,1,10)", translated)
        self.assertIn("created_at>=%s", translated)


@unittest.skipUnless(
    os.getenv("TEST_DATABASE_URL"), "TEST_DATABASE_URL is required for PostgreSQL"
)
class PostgreSQLMigrationIntegrationTests(unittest.TestCase):
    database_url = os.getenv("TEST_DATABASE_URL", "")

    def reset_schema(self):
        close_pools()
        import psycopg

        with psycopg.connect(self.database_url, autocommit=True) as conn:
            conn.execute("DROP SCHEMA public CASCADE")
            conn.execute("CREATE SCHEMA public")

    def tearDown(self):
        close_pools()

    def test_fresh_and_restart_safe_migrations(self):
        self.reset_schema()
        applied = run_migrations(self.database_url)
        self.assertGreaterEqual(len(applied), 7)
        self.assertTrue(migration_status(self.database_url)["current"])
        self.assertEqual(run_migrations(self.database_url), [])

    def test_upgrade_from_phase_6_schema(self):
        self.reset_schema()
        run_migrations(self.database_url, through_version="006")
        applied = run_migrations(self.database_url)
        self.assertEqual(["007_staging_operations.sql"], applied)
        self.assertEqual(run_migrations(self.database_url), [])


@unittest.skipUnless(
    os.getenv("TEST_REDIS_URL"), "TEST_REDIS_URL is required for Redis/RQ"
)
class RedisQueueIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.redis = create_redis(os.environ["TEST_REDIS_URL"])
        self.redis.flushdb()

    def tearDown(self):
        self.redis.flushdb()
        self.redis.close()

    def test_distributed_limit_with_real_redis(self):
        first = RedisRateLimiter(self.redis)
        second = RedisRateLimiter(create_redis(os.environ["TEST_REDIS_URL"]))
        self.assertTrue(first.allow("shared", 2, 60))
        self.assertTrue(second.allow("shared", 2, 60))
        self.assertFalse(first.allow("shared", 2, 60))
        second.client.close()

    def test_rq_job_is_durable_then_worker_completes_it(self):
        from rq import Queue, SimpleWorker

        from backend.infrastructure.queueing import integration_echo

        queue = Queue("nexus-ci", connection=self.redis)
        job = queue.enqueue(integration_echo, "ok", job_id="integration-job")
        self.assertEqual(job.get_status(refresh=True), "queued")
        SimpleWorker([queue], connection=self.redis).work(burst=True)
        job.refresh()
        self.assertEqual(job.result, "ok")
