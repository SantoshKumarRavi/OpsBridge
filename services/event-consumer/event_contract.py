"""Validation helpers for the versioned onboarding event contract."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

CONTRACTS_PATH = Path(__file__).resolve().parents[2] / "packages" / "contracts" / "events"


def _load_validator(schema_name: str) -> Draft202012Validator:
    schema = json.loads((CONTRACTS_PATH / schema_name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


_VALIDATORS = {
    "opsbridge.domain.v1": _load_validator("onboarding-case.v1.json"),
    "opsbridge.domain.v2": _load_validator("onboarding-case.v2.json"),
    "opsbridge.external.v1": _load_validator("external-event.v1.json"),
}

_SCHEMA_VERSIONS = {
    "opsbridge.domain.v1": 1,
    "opsbridge.domain.v2": 2,
    "opsbridge.external.v1": 1,
}


def validate_event(event: Any, topic: str = "opsbridge.domain.v1") -> dict[str, Any]:
    """Validate one topic-specific versioned event and return it, or raise ValueError."""
    if not isinstance(event, dict):
        raise ValueError("event must be a JSON object")
    validator = _VALIDATORS.get(topic)
    if validator is None:
        raise ValueError(f"no event contract registered for topic {topic}")
    errors = sorted(validator.iter_errors(event), key=lambda error: (list(error.absolute_path), error.message))
    if errors:
        error = errors[0]
        field = ".".join(str(part) for part in error.absolute_path) or "event"
        raise ValueError(f"event contract violation at {field}: {error.message}")
    return event


def schema_version_for_topic(topic: str) -> int:
    try:
        return _SCHEMA_VERSIONS[topic]
    except KeyError as exc:
        raise ValueError(f"no event contract registered for topic {topic}") from exc


def safe_summary(event: dict[str, Any]) -> dict[str, Any]:
    """Keep only operational fields; never persist arbitrary provider payloads."""
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    allowed = ("status", "suggestedNextStep", "humanDecisionRequired", "provider", "type")
    return {key: payload[key] for key in allowed if key in payload}
