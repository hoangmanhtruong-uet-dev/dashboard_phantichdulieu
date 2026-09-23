from __future__ import annotations

from typing import Any


SENSITIVE_KEYS = {"authorization", "cookie", "password", "token", "secret"}


def _scrub(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[Filtered]" if key.lower() in SENSITIVE_KEYS else _scrub(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    return value


def before_send(event: dict, _hint: dict) -> dict:
    return _scrub(event)


def initialize_sentry(dsn: str, environment: str, *, worker: bool = False) -> None:
    if not dsn:
        return
    import sentry_sdk

    integrations = []
    if worker:
        from sentry_sdk.integrations.rq import RqIntegration

        integrations.append(RqIntegration())
    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        integrations=integrations,
        traces_sample_rate=0.1,
        send_default_pii=False,
        before_send=before_send,  # type: ignore[arg-type]
    )
