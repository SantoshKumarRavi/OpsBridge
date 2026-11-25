"""Safe helpers for correlating application IDs with OpenTelemetry spans."""

import re

from opentelemetry import trace

_CORRELATION_ID = re.compile(r"^[A-Za-z0-9._:-]{1,100}$")


def tag_current_span(correlation_id: str | None) -> bool:
    """Attach a validated correlation ID without recording it in logs or baggage."""
    if not correlation_id or not _CORRELATION_ID.fullmatch(correlation_id):
        return False
    span = trace.get_current_span()
    if not span.is_recording():
        return False
    span.set_attribute("app.correlation_id", correlation_id)
    return True
