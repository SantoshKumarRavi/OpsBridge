import asyncio
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from app.main import app, provider_cost_per_1k, provider_json


class ProviderReliabilityTests(unittest.TestCase):
    def test_fallback_success_reports_failure_attribution_latency_and_cost(self):
        fake = AsyncMock(side_effect=[TimeoutError(), ({"fields": {"full_name": "Asha"}}, "gemini-test", 10, 2)])
        isolated_totals = {"requests": 0, "attempts": 0, "failures": 0, "fallbacks": 0, "input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0.0, "providers": {}}
        environment = {
            "DEFAULT_LLM_PROVIDER": "openai", "LLM_FALLBACK_PROVIDERS": "gemini,anthropic",
            "OPENAI_API_KEY": "synthetic", "GEMINI_API_KEY": "synthetic", "ANTHROPIC_API_KEY": "",
            "LLM_COST_PER_1K_INPUT_USD": "0.002", "LLM_COST_PER_1K_OUTPUT_USD": "0.01",
            "GEMINI_COST_PER_1K_INPUT_USD": "0.002", "GEMINI_COST_PER_1K_OUTPUT_USD": "0.01",
        }
        with patch.dict("os.environ", environment), patch("app.main.invoke_provider", fake), patch("app.main.usage_totals", isolated_totals):
            result = asyncio.run(provider_json("synthetic system", "synthetic input", tenant_id="tenant-x", correlation_id="trace-x"))

        usage = result["_usage"]
        self.assertEqual(result["fields"], {"full_name": "Asha"})
        self.assertTrue(usage["fallback_used"])
        self.assertEqual(usage["provider"], "gemini")
        self.assertEqual(usage["failure_attribution"], [{"provider": "openai", "error_type": "TimeoutError"}])
        self.assertEqual([attempt["outcome"] for attempt in usage["attempts"]], ["failure", "success"])
        self.assertEqual(usage["input_tokens"], 10)
        self.assertEqual(usage["output_tokens"], 2)
        self.assertAlmostEqual(usage["estimated_cost_usd"], 0.00004)
        self.assertEqual(isolated_totals["failures"], 1)
        self.assertEqual(isolated_totals["fallbacks"], 1)

    def test_missing_credentials_returns_attribution_without_calling_provider(self):
        fake = AsyncMock()
        with patch.dict("os.environ", {"DEFAULT_LLM_PROVIDER": "openai", "LLM_FALLBACK_PROVIDERS": "", "OPENAI_API_KEY": ""}, clear=True), patch("app.main.invoke_provider", fake):
            result = asyncio.run(provider_json("system", "synthetic"))
        self.assertEqual(result["provider"], "unavailable")
        self.assertEqual(result["_usage"]["attempts"], [{"provider": "openai", "outcome": "skipped", "reason": "missing_credentials"}])
        self.assertEqual(result["_usage"]["failure_attribution"], [])
        fake.assert_not_awaited()

    def test_metrics_endpoint_exports_provider_metrics(self):
        with TestClient(app) as client:
            response = client.get("/metrics")
        self.assertEqual(response.status_code, 200)
        self.assertIn("opsbridge_ai_provider_attempts_total", response.text)
        self.assertIn("opsbridge_ai_provider_estimated_cost_usd_total", response.text)

    def test_provider_specific_price_overrides_shared_default(self):
        with patch.dict("os.environ", {
            "LLM_COST_PER_1K_INPUT_USD": "0.01",
            "GEMINI_COST_PER_1K_INPUT_USD": "0.003",
        }, clear=True):
            self.assertEqual(provider_cost_per_1k("gemini", "input"), 0.003)
            self.assertEqual(provider_cost_per_1k("gemini", "output"), 0.0)
            self.assertEqual(provider_cost_per_1k("openai", "input"), 0.01)


if __name__ == "__main__":
    unittest.main()
