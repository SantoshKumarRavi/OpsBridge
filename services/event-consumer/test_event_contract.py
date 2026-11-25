"""Broker-free tests for the Kafka consumer's versioned event contract."""
import unittest

from event_contract import safe_summary, schema_version_for_topic, validate_event


def valid_event() -> dict:
    return {
        "eventId": "c2a5f6e9-4a1f-4e6e-a6f2-802d990a3a2a",
        "eventType": "case.review_required",
        "occurredAt": "2026-11-20T12:30:00Z",
        "tenantId": "tenant_42",
        "caseId": "d2a5f6e9-4a1f-4e6e-a6f2-802d990a3a2a",
        "correlationId": "corr-123",
        "payload": {
            "status": "review_required",
            "humanDecisionRequired": True,
            "suggestedNextStep": "review_document",
            "ssn": "must-not-be-projected",
        },
    }


class EventContractTests(unittest.TestCase):
    def test_accepts_valid_v1_event_and_returns_same_value(self):
        event = valid_event()
        self.assertIs(validate_event(event), event)

    def test_accepts_all_current_domain_event_families_and_case_statuses(self):
        event = valid_event()
        event_types = [
            "case.created", "document.received", "document.processed",
            "case.ai_recommendation_updated", "case.review_required",
            "case.approved", "case.rejected", "case.changes_requested",
        ]
        for event_type in event_types:
            with self.subTest(event_type=event_type):
                event["eventType"] = event_type
                validate_event(event)

    def test_v1_event_remains_valid_under_additive_v2_contract(self):
        event = valid_event()
        validate_event(event, "opsbridge.domain.v1")
        validate_event(event, "opsbridge.domain.v2")

    def test_v2_accepts_optional_aggregate_version_and_actor(self):
        event = valid_event()
        event["aggregateVersion"] = 3
        event["actor"] = {"id": "reviewer-7", "role": "compliance-reviewer"}
        self.assertIs(validate_event(event, "opsbridge.domain.v2"), event)
        with self.assertRaisesRegex(ValueError, "contract violation"):
            validate_event(event, "opsbridge.domain.v1")
        self.assertEqual(schema_version_for_topic("opsbridge.domain.v2"), 2)

    def test_v2_rejects_invalid_additive_fields(self):
        for field, value in [("aggregateVersion", 0), ("actor", {"id": "reviewer", "email": "private@example.test"})]:
            with self.subTest(field=field):
                event = valid_event()
                event[field] = value
                with self.assertRaisesRegex(ValueError, "contract violation"):
                    validate_event(event, "opsbridge.domain.v2")

    def test_accepts_the_provider_webhook_topic_contract(self):
        event = {
            "eventId": "c2a5f6e9-4a1f-4e6e-a6f2-802d990a3a2a",
            "eventType": "integration.stripe.received",
            "occurredAt": "2026-11-20T12:30:00Z",
            "tenantId": "unassigned",
            "payload": {"provider": "stripe", "type": "charge.succeeded"},
        }
        self.assertIs(validate_event(event, "opsbridge.external.v1"), event)

    def test_does_not_apply_domain_schema_to_provider_event_shapes(self):
        event = {
            "eventId": "c2a5f6e9-4a1f-4e6e-a6f2-802d990a3a2a",
            "eventType": "communication.delivery_status",
            "occurredAt": "2026-11-20T12:30:00Z",
            "tenantId": "unassigned",
            "payload": {"provider": "twilio", "status": "delivered"},
        }
        with self.assertRaisesRegex(ValueError, "contract violation"):
            validate_event(event, "opsbridge.domain.v1")
        self.assertIs(validate_event(event, "opsbridge.external.v1"), event)

    def test_rejects_unregistered_topics(self):
        with self.assertRaisesRegex(ValueError, "no event contract"):
            validate_event(valid_event(), "opsbridge.unknown.v1")

    def test_rejects_unknown_fields_in_strict_v1_envelope(self):
        event = valid_event()
        event["unexpected"] = "not in the v1 contract"
        with self.assertRaisesRegex(ValueError, "contract violation"):
            validate_event(event)

    def test_rejects_invalid_tenant_identifier(self):
        event = valid_event()
        event["tenantId"] = "tenant/with/slash"
        with self.assertRaisesRegex(ValueError, "tenantId"):
            validate_event(event)

    def test_rejects_invalid_identifiers_event_types_and_timestamps(self):
        cases = [
            ("eventId", "not-a-uuid"),
            ("eventType", "case.deleted"),
            ("occurredAt", "yesterday"),
        ]
        for field, value in cases:
            with self.subTest(field=field):
                event = valid_event()
                event[field] = value
                with self.assertRaisesRegex(ValueError, field):
                    validate_event(event)

    def test_rejects_non_object_events(self):
        with self.assertRaisesRegex(ValueError, "JSON object"):
            validate_event(["not", "an", "event"])

    def test_projection_summary_drops_unapproved_sensitive_fields(self):
        summary = safe_summary(valid_event())
        self.assertEqual(summary, {
            "status": "review_required",
            "humanDecisionRequired": True,
            "suggestedNextStep": "review_document",
        })
        self.assertNotIn("ssn", summary)

    def test_projection_summary_does_not_copy_v2_actor_identity(self):
        event = valid_event()
        event["actor"] = {"id": "reviewer-with-private-details", "role": "compliance-reviewer"}
        summary = safe_summary(event)
        self.assertNotIn("actor", summary)
        self.assertNotIn("reviewer-with-private-details", str(summary))


if __name__ == "__main__":
    unittest.main()
