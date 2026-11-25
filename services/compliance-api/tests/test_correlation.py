from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from onboarding.correlation import resolve_correlation_id
from onboarding.tracing import tag_current_span


class RecordingSpan:
    def __init__(self, recording=True):
        self.recording = recording
        self.attributes = {}

    def is_recording(self):
        return self.recording

    def set_attribute(self, key, value):
        self.attributes[key] = value


class CorrelationIdTests(unittest.TestCase):
    def test_valid_id_is_preserved(self):
        self.assertEqual(resolve_correlation_id("request-42:worker.2"), "request-42:worker.2")

    def test_invalid_or_oversized_id_is_replaced(self):
        for value in ("bad id", "x" * 101, ""):
            with self.subTest(value=value):
                generated = resolve_correlation_id(value)
                self.assertRegex(generated, r"^[0-9a-f-]{36}$")

    @patch("onboarding.tracing.trace.get_current_span")
    def test_valid_correlation_id_is_added_to_active_span(self, get_current_span):
        span = RecordingSpan()
        get_current_span.return_value = span

        self.assertTrue(tag_current_span("upload-flow-42"))
        self.assertEqual(span.attributes, {"app.correlation_id": "upload-flow-42"})

    @patch("onboarding.tracing.trace.get_current_span")
    def test_missing_or_oversize_correlation_id_is_not_recorded(self, get_current_span):
        self.assertFalse(tag_current_span(None))
        self.assertFalse(tag_current_span("x" * 101))
        get_current_span.assert_not_called()

    @patch("onboarding.tracing.trace.get_current_span")
    def test_non_recording_span_is_left_untouched(self, get_current_span):
        span = RecordingSpan(recording=False)
        get_current_span.return_value = span

        self.assertFalse(tag_current_span("upload-flow-42"))
        self.assertEqual(span.attributes, {})


if __name__ == "__main__":
    unittest.main()
