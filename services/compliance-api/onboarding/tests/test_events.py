import json
from unittest.mock import MagicMock, patch

import httpx
from django.test import TestCase

from onboarding.events import dispatch_outbox
from onboarding.models import EventOutbox


class DispatchOutboxTests(TestCase):
    def setUp(self):
        self.event = EventOutbox.objects.create(
            tenant_id="tenant-a",
            event_type="case.created",
            aggregate_id="case-123",
            payload={"status": "submitted", "correlationId": "trace-123"},
        )
        self.producer = MagicMock()
        self.producer.flush.return_value = 0

    @patch("onboarding.events._producer_class")
    def test_confirms_kafka_delivery_then_marks_event_published(self, producer_factory):
        producer_factory.return_value.return_value = self.producer

        dispatch_outbox(self.event.id)

        producer_factory.assert_called_once_with()
        producer_factory.return_value.assert_called_once_with(
            {
                "bootstrap.servers": "localhost:9092",
                "enable.idempotence": True,
                "acks": "all",
            }
        )
        args, kwargs = self.producer.produce.call_args
        self.assertEqual(args, ("opsbridge.domain.v1",))
        self.assertEqual(kwargs["key"], "case-123")
        message = json.loads(kwargs["value"])
        self.assertEqual(message["eventId"], str(self.event.id))
        self.assertEqual(message["eventType"], "case.created")
        self.assertEqual(message["tenantId"], "tenant-a")
        self.assertEqual(message["caseId"], "case-123")
        self.assertEqual(message["correlationId"], "trace-123")
        self.producer.flush.assert_called_once_with(10)

        self.event.refresh_from_db()
        self.assertEqual(self.event.attempts, 1)
        self.assertIsNotNone(self.event.published_at)

    @patch("onboarding.events._producer_class")
    def test_does_not_publish_an_already_published_event_again(self, producer_factory):
        self.event.published_at = self.event.created_at
        self.event.save(update_fields=["published_at"])

        dispatch_outbox(self.event.id)

        producer_factory.assert_not_called()
        self.event.refresh_from_db()
        self.assertEqual(self.event.attempts, 0)

    @patch("onboarding.events._producer_class")
    def test_leaves_event_pending_when_kafka_does_not_confirm_delivery(self, producer_factory):
        self.producer.flush.return_value = 1
        producer_factory.return_value.return_value = self.producer

        with self.assertRaisesRegex(RuntimeError, "Kafka did not confirm delivery"):
            dispatch_outbox(self.event.id)

        self.event.refresh_from_db()
        self.assertEqual(self.event.attempts, 0)
        self.assertIsNone(self.event.published_at)

    @patch.dict(
        "os.environ",
        {"REALTIME_SERVICE_URL": "http://realtime.test/", "INTERNAL_SERVICE_TOKEN": "internal-test"},
    )
    @patch("onboarding.events.httpx.post")
    @patch("onboarding.events._producer_class")
    def test_publishes_best_effort_realtime_update_after_kafka(self, producer_factory, realtime_post):
        producer_factory.return_value.return_value = self.producer
        realtime_post.return_value = MagicMock()

        dispatch_outbox(self.event.id)

        realtime_post.assert_called_once()
        args, kwargs = realtime_post.call_args
        self.assertEqual(args[0], "http://realtime.test/v1/publish")
        self.assertEqual(kwargs["headers"]["X-Tenant-Id"], "tenant-a")
        self.assertEqual(kwargs["headers"]["X-Internal-Service-Token"], "internal-test")
        self.assertEqual(kwargs["json"]["eventType"], "case.created")
        self.assertEqual(kwargs["json"]["correlationId"], "trace-123")
        self.assertEqual(kwargs["timeout"], 2)
        realtime_post.return_value.raise_for_status.assert_called_once_with()

    @patch.dict("os.environ", {"REALTIME_SERVICE_URL": "http://realtime.test"}, clear=True)
    @patch("onboarding.events.httpx.post", side_effect=httpx.ConnectError("realtime unavailable"))
    @patch("onboarding.events._producer_class")
    def test_realtime_failure_does_not_undo_confirmed_kafka_delivery(self, producer_factory, realtime_post):
        producer_factory.return_value.return_value = self.producer

        dispatch_outbox(self.event.id)

        realtime_post.assert_called_once()
        self.event.refresh_from_db()
        self.assertEqual(self.event.attempts, 1)
        self.assertIsNotNone(self.event.published_at)
