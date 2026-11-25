from pathlib import Path
import sys
import unittest
import asyncio
from unittest.mock import ANY, AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals.provider_reliability import CASES, evaluate_provider, percentile95, score_extraction


class ProviderEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.case = {
            "expected_fields": ["full_name", "document_number"],
            "expected": {"full_name": "Asha Kumar", "document_number": "ID-1"},
            "absent": ["expiry_date"],
        }

    def test_scores_exact_values_and_missing_fields_without_rewarding_hallucinations(self):
        answer = {"fields": {"full_name": "Asha Kumar", "document_number": "ID-1", "expiry_date": ""}, "confidence": 0.9, "warnings": []}
        self.assertTrue(score_extraction(answer, self.case)["passed"])
        hallucination = {"fields": {"full_name": "Asha Kumar", "document_number": "ID-1", "expiry_date": "2099-01-01"}, "confidence": 0.9, "warnings": []}
        self.assertFalse(score_extraction(hallucination, self.case)["passed"])

    def test_invalid_schema_or_incorrect_value_fails(self):
        self.assertFalse(score_extraction({"fields": [], "confidence": 0.9, "warnings": []}, self.case)["passed"])
        incorrect = {"fields": {"full_name": "Asha K", "document_number": "ID-1"}, "confidence": 0.9, "warnings": []}
        self.assertFalse(score_extraction(incorrect, self.case)["passed"])

    def test_p95_uses_nearest_rank_and_handles_empty_samples(self):
        self.assertEqual(percentile95([]), 0)
        self.assertEqual(percentile95([10, 20, 30, 40]), 40)

    def test_provider_report_aggregates_quality_latency_cost_and_failures(self):
        outputs = [
            {"fields": case["expected"], "confidence": 0.9, "warnings": [], "_usage": {
                "provider": "openai", "model": "synthetic-model", "latency_ms": 100 + index,
                "estimated_cost_usd": 0.00001, "cost_per_1k_input_usd": 0.001,
                "cost_per_1k_output_usd": 0.002, "input_tokens": 10, "output_tokens": 5,
                "fallback_used": index == 1, "attempts": [],
                "failure_attribution": [{"provider": "openai", "error_type": "TimeoutError"}] if index == 1 else [],
            }}
            for index, case in enumerate(CASES)
        ]
        fake = AsyncMock(side_effect=outputs)
        with patch("evals.provider_reliability.provider_json", fake):
            report = asyncio.run(evaluate_provider("openai"))
        self.assertEqual(report["accuracy"], 1.0)
        self.assertEqual(report["completion_rate"], 1.0)
        self.assertAlmostEqual(report["fallback_rate"], 1 / 3)
        self.assertEqual(report["p95_latency_ms"], 102)
        self.assertAlmostEqual(report["estimated_cost_usd"], 0.00003)
        self.assertEqual(report["failed_attempts"], 1)
        self.assertEqual(fake.await_count, len(CASES))
        fake.assert_awaited_with(ANY, ANY, correlation_id="ai-eval-no-identity-values")


if __name__ == "__main__":
    unittest.main()
