import asyncio
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.policy_decisions import assess_policy, prepare_recommendation


def valid_identity(**field_overrides):
    fields = {"full_name": "Asha Kumar", "document_number": "ID-123", "expiry_date": "2099-12-31"}
    fields.update(field_overrides)
    return {"document_type": "identity", "fields": fields, "confidence": 0.99}


class PolicyDecisionTests(unittest.TestCase):
    def assess(self, documents, profile_name="Asha Kumar"):
        return assess_policy({"request": {
            "case_id": "case-1",
            "worker_profile": {"name": profile_name},
            "extracted_documents": documents,
            "policy_text": "Synthetic onboarding policy",
        }})

    def recommend(self, state):
        return asyncio.run(prepare_recommendation(state))["recommendation"]

    def test_complete_matching_documents_are_only_ready_for_human_approval(self):
        state = self.assess([valid_identity()])

        self.assertEqual(state["assessment"]["missing_fields"], [])
        self.assertEqual(state["assessment"]["review_flags"], [])
        recommendation = self.recommend(state)
        self.assertEqual(recommendation["suggested_next_step"], "ready_for_human_approval")
        self.assertTrue(recommendation["human_decision_required"])

    def test_missing_required_fields_request_changes(self):
        state = self.assess([valid_identity(document_number="")])

        self.assertEqual(state["assessment"]["missing_fields"], [
            {"document": "identity", "field": "document_number"},
        ])
        self.assertEqual(self.recommend(state)["suggested_next_step"], "request_changes")

    def test_low_confidence_and_name_mismatch_require_human_review(self):
        document = valid_identity(full_name="Asha K.")
        document["confidence"] = 0.6
        state = self.assess([document])

        reasons = [flag["reason"] for flag in state["assessment"]["review_flags"]]
        self.assertIn("Confidence is below review threshold.", reasons)
        self.assertIn("Document name differs from the worker profile.", reasons)
        self.assertEqual(self.recommend(state)["suggested_next_step"], "human_review")

    def test_expired_and_unparseable_dates_are_flagged(self):
        expired = valid_identity(expiry_date="2000-01-01")
        malformed = {"document_type": "work_eligibility", "fields": {
            "document_number": "WORK-1", "expiry_date": "not-a-date",
        }, "confidence": 0.99}
        state = self.assess([expired, malformed])

        reasons = [flag["reason"] for flag in state["assessment"]["review_flags"]]
        self.assertIn("Document appears expired; request human verification.", reasons)
        self.assertIn("Expiration date could not be interpreted.", reasons)
        self.assertEqual(self.recommend(state)["suggested_next_step"], "human_review")

    def test_work_eligibility_requires_document_number_and_expiry(self):
        state = self.assess([{"document_type": "work_eligibility", "fields": {}, "confidence": 0.99}])

        self.assertEqual(state["assessment"]["missing_fields"], [
            {"document": "work_eligibility", "field": "document_number"},
            {"document": "work_eligibility", "field": "expiry_date"},
        ])


if __name__ == "__main__":
    unittest.main()
