import json
import logging
import threading
import time
import uuid
from collections import defaultdict, deque
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from backend.responses import error_response
from backend.auth.security import ACCESS_COOKIE, decode_access_token
from backend.operations.repository import OperationsRepository
from backend.infrastructure.redis_client import RedisRateLimiter
from data.auth_repository import AuthRepository
from backend.config import settings


logger = logging.getLogger("nexus.requests")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


class SlidingWindowLimiter:
    def __init__(self):
        self._entries: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        now = time.monotonic()
        with self._lock:
            entries = self._entries[key]
            while entries and entries[0] <= now - window_seconds:
                entries.popleft()
            if len(entries) >= limit:
                return False
            entries.append(now)
            return True


limiter = SlidingWindowLimiter()


def install_operational_middleware(app):
    app.state.metrics = {"requests": 0, "errors": 0, "latency_ms_total": 0.0}

    @app.middleware("http")
    async def operational_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        path = request.url.path
        client_ip = request.client.host if request.client else "unknown"
        limit = 120
        sensitive = False
        if path in {
            "/api/auth/login",
            "/api/auth/forgot-password",
            "/api/auth/reset-password",
        }:
            limit = 10
            sensitive = True
        elif path.startswith("/api/ingestion/uploads"):
            limit = 10
            sensitive = True
        elif path.startswith("/api/ingestion/jobs") and path.endswith("/import"):
            limit = 10
            sensitive = True
        elif path.startswith("/api/exports") and request.method == "POST":
            limit = 10
            sensitive = True
        elif path.startswith("/api/analytics"):
            limit = 60
            sensitive = True
        elif path.startswith("/api/ai") or path == "/chat":
            limit = 20
            sensitive = True
        if settings.app_env == "test":
            limit = 10000
        rate_key = f"{client_ip}:{path}:{request.method}"
        active_limiter: Any = limiter
        if settings.app_env in {"staging", "production"} and sensitive:
            active_limiter = RedisRateLimiter(getattr(app.state, "redis", None))
        if not active_limiter.allow(rate_key, limit):
            return JSONResponse(
                status_code=429,
                content=error_response(
                    "RATE_LIMITED", "Too many requests; retry later"
                ),
                headers={"X-Request-ID": request_id, "Retry-After": "60"},
            )
        started = time.perf_counter()
        response = await call_next(request)
        latency = (time.perf_counter() - started) * 1000
        app.state.metrics["requests"] += 1
        app.state.metrics["latency_ms_total"] += latency
        if response.status_code >= 500:
            app.state.metrics["errors"] += 1
        log_user_id = None
        log_workspace_id = None
        if (
            request.method in {"POST", "PUT", "PATCH", "DELETE"}
            and response.status_code < 400
        ):
            try:
                authorization = request.headers.get("Authorization", "")
                token = (
                    authorization[7:]
                    if authorization.startswith("Bearer ")
                    else request.cookies.get(ACCESS_COOKIE)
                )
                if token:
                    payload = decode_access_token(token)
                    database_path = app.state.database_path
                    context = AuthRepository(database_path).session_context(
                        str(payload["sid"]), int(payload["sub"])
                    )
                    if context:
                        log_user_id = context["user_id"]
                        log_workspace_id = context["workspace_id"]
                        OperationsRepository(database_path).audit(
                            workspace_id=context["workspace_id"],
                            actor_user_id=context["user_id"],
                            action=f"HTTP_{request.method}",
                            resource_type="api_route",
                            resource_id=path[:300],
                            request_id=request_id,
                            metadata={"status": response.status_code},
                        )
            except Exception:
                logger.exception(
                    json.dumps(
                        {"event": "audit_write_failed", "request_id": request_id}
                    )
                )
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'"
        )
        resolved_route = request.scope.get("route")
        logger.info(
            json.dumps(
                {
                    "event": "http_request",
                    "request_id": request_id,
                    "method": request.method,
                    "path": path,
                    "route": getattr(resolved_route, "path", path),
                    "status": response.status_code,
                    "latency_ms": round(latency, 2),
                    "user_id": log_user_id,
                    "workspace_id": log_workspace_id,
                }
            )
        )
        return response
