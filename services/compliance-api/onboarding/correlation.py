import re
import uuid

CORRELATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,100}$")


def resolve_correlation_id(value: str | None) -> str:
    if value and CORRELATION_ID_PATTERN.fullmatch(value):
        return value
    return str(uuid.uuid4())
