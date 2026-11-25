from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.observability import record_ai_provider_attempt, tag_current_span, valid_correlation_id


class RecordingSpan:
    def __init__(self, recording=True):
        self.recording = recording
        self.attributes = {}
        self.events = []

    def is_recording(self):
        return self.recording

    def set_attribute(self, key, value):
        self.attributes[key] = value

    def add_event(self, name, attributes=None):
        self.events.append((name, attributes or {}))


class CorrelationSpanTests(unittest.TestCase):
    @patch("app.observability.trace.get_current_span")
    def test_adds_only_bounded_correlation_id_to_recording_span(self, get_current_span):
        span = RecordingSpan()
        get_current_span.return_value = span

        self.assertTrue(tag_current_span("upload-flow-42"))
        self.assertEqual(span.attributes, {"app.correlation_id": "upload-flow-42"})

    @patch("app.observability.trace.get_current_span")
    def test_skips_missing_oversize_and_non_recording_context(self, get_current_span):
        self.assertFalse(tag_current_span(None))
        self.assertFalse(tag_current_span("x" * 101))
        get_current_span.assert_not_called()

        span = RecordingSpan(recording=False)
        get_current_span.return_value = span
        self.assertFalse(tag_current_span("upload-flow-42"))
        self.assertEqual(span.attributes, {})

    def test_correlation_id_validator_rejects_header_control_characters(self):
        self.assertTrue(valid_correlation_id("upload-flow-42:retry.1"))
        self.assertFalse(valid_correlation_id("bad\nid"))
        self.assertFalse(valid_correlation_id("x" * 101))

    @patch("app.observability.trace.get_current_span")
    def test_provider_attempt_is_recorded_without_prompt_or_response_content(self, get_current_span):
        span = RecordingSpan()
        get_current_span.return_value = span
        self.assertTrue(record_ai_provider_attempt("openai", "failure", 2, 500, error_type="TimeoutError", fallback_used=True))
        self.assertEqual(span.events, [("ai.provider.attempt", {
            "app.ai.provider": "openai", "app.ai.outcome": "failure", "app.ai.attempt": 2,
            "app.ai.latency_ms": 500, "app.ai.fallback_used": True, "app.ai.error_type": "TimeoutError",
        })])
