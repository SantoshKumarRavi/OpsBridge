"""Small helpers for adding safe application context to active spans."""

import re

from opentelemetry import trace

_CORRELATION_ID = re.compile(r"^[A-Za-z0-9._:-]{1,100}$")


def valid_correlation_id(value: str | None) -> bool:
    return bool(value and _CORRELATION_ID.fullmatch(value))


def tag_current_span(correlation_id: str | None) -> bool:
    if not valid_correlation_id(correlation_id):
        return False
    span = trace.get_current_span()
    if not span.is_recording():
        return False
    span.set_attribute("app.correlation_id", correlation_id)
    return True


def record_ai_provider_attempt(
    provider: str,
    outcome: str,
    attempt: int,
    latency_ms: int,
    *,
    error_type: str | None = None,
    fallback_used: bool = False,
) -> bool:
    """Add bounded provider outcome metadata to the active request span."""
    span = trace.get_current_span()
    if not span.is_recording():
        return False
    attributes = {
        "app.ai.provider": provider[:32],
        "app.ai.outcome": outcome,
        "app.ai.attempt": max(1, min(int(attempt), 20)),
        "app.ai.latency_ms": max(0, min(int(latency_ms), 600_000)),
        "app.ai.fallback_used": bool(fallback_used),
    }
    if error_type:
        attributes["app.ai.error_type"] = error_type[:80]
    span.add_event("ai.provider.attempt", attributes=attributes)
    return True
