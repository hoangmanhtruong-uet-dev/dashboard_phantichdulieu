from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from threading import Lock


class LoginRateLimiter:
    def __init__(
        self, max_attempts: int = 5, window_minutes: int = 5, lock_minutes: int = 15
    ):
        self.max_attempts = max_attempts
        self.window = timedelta(minutes=window_minutes)
        self.lock_time = timedelta(minutes=lock_minutes)
        self._attempts: defaultdict[str, deque[datetime]] = defaultdict(deque)
        self._locked_until: dict[str, datetime] = {}
        self._lock = Lock()

    def _now(self):
        return datetime.now(timezone.utc)

    def is_blocked(self, key: str) -> bool:
        now = self._now()
        with self._lock:
            until = self._locked_until.get(key)
            if until and until > now:
                return True
            self._locked_until.pop(key, None)
            attempts = self._attempts[key]
            while attempts and attempts[0] < now - self.window:
                attempts.popleft()
            return False

    def fail(self, key: str) -> None:
        now = self._now()
        with self._lock:
            attempts = self._attempts[key]
            attempts.append(now)
            if len(attempts) >= self.max_attempts:
                self._locked_until[key] = now + self.lock_time
                attempts.clear()

    def success(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)
            self._locked_until.pop(key, None)


login_rate_limiter = LoginRateLimiter()
