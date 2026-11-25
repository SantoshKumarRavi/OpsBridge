"""Run a small synthetic structured-extraction quality/cost/reliability comparison."""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.main import provider_cost_per_1k, provider_json


EXTRACTION_SYSTEM = (
    "Extract only information explicitly present in the supplied document. Do not infer missing values. "
    "Return JSON keys fields, confidence (0..1), warnings, evidence. Never output a final eligibility decision."
)
CASES = [
    {
        "id": "identity-complete",
        "document_type": "identity",
        "document_text": "Synthetic identity card: full name Asha Kumar; document number ID-381; expiry date 2030-08-01.",
        "expected_fields": ["full_name", "document_number", "expiry_date"],
        "expected": {"full_name": "Asha Kumar", "document_number": "ID-381", "expiry_date": "2030-08-01"},
        "absent": [],
    },
    {
        "id": "work-permit-missing-expiry",
        "document_type": "work_eligibility",
        "document_text": "Synthetic work permit for Dev Shah, number WP-77. No expiry date is printed.",
        "expected_fields": ["full_name", "document_number", "expiry_date"],
        "expected": {"full_name": "Dev Shah", "document_number": "WP-77"},
        "absent": ["expiry_date"],
    },
    {
        "id": "no-identity-values",
        "document_type": "receipt",
        "document_text": "Synthetic receipt. It contains no identity name, ID number, or expiration date.",
        "expected_fields": ["full_name", "document_number", "expiry_date"],
        "expected": {},
        "absent": ["full_name", "document_number", "expiry_date"],
    },
]
PROVIDER_KEYS = {"openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}


def score_extraction(result: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    fields = result.get("fields")
    schema_valid = (
        isinstance(fields, dict)
        and isinstance(result.get("confidence"), (int, float))
        and 0 <= result["confidence"] <= 1
        and isinstance(result.get("warnings"), list)
    )
    fields = fields if isinstance(fields, dict) else {}
    matches = sum(fields.get(key) == value for key, value in case["expected"].items())
    absent_ok = all(fields.get(key) in (None, "") for key in case["absent"])
    unexpected = [key for key in fields if key not in case["expected_fields"] and fields[key] not in (None, "")]
    expected_match = matches == len(case["expected"])
    passed = schema_valid and expected_match and absent_ok and not unexpected
    return {
        "passed": bool(passed),
        "schema_valid": bool(schema_valid),
        "expected_fields": len(case["expected"]),
        "exact_matches": matches,
        "absent_fields_verified": len(case["absent"]) if absent_ok else 0,
        "unsupported_fields": unexpected,
    }


def percentile95(values: list[int]) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[max(0, int(0.95 * len(ordered) + 0.999999) - 1)]


async def evaluate_provider(provider: str) -> dict[str, Any]:
    os.environ["DEFAULT_LLM_PROVIDER"] = provider
    os.environ["LLM_FALLBACK_PROVIDERS"] = ""
    rows = []
    for case in CASES:
        payload = {key: case[key] for key in ("document_type", "expected_fields", "document_text")}
        result = await provider_json(
            EXTRACTION_SYSTEM,
            json.dumps(payload, ensure_ascii=False),
            correlation_id=f"ai-eval-{case['id']}",
        )
        usage = result.get("_usage", {})
        rows.append({
            "case_id": case["id"],
            "score": score_extraction(result, case),
            "provider": usage.get("provider", result.get("provider", "unknown")),
            "model": usage.get("model", "unknown"),
            "latency_ms": usage.get("latency_ms", 0),
            "estimated_cost_usd": usage.get("estimated_cost_usd", 0.0),
            "cost_per_1k_input_usd": usage.get("cost_per_1k_input_usd", provider_cost_per_1k(provider, "input")),
            "cost_per_1k_output_usd": usage.get("cost_per_1k_output_usd", provider_cost_per_1k(provider, "output")),
            "fallback_used": usage.get("fallback_used", False),
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "attempts": usage.get("attempts", []),
            "failure_attribution": usage.get("failure_attribution", []),
        })
    latencies = [row["latency_ms"] for row in rows]
    return {
        "provider": provider,
        "model": next((row["model"] for row in rows if row["model"] != "unknown"), "unknown"),
        "cases": rows,
        "accuracy": sum(row["score"]["passed"] for row in rows) / len(rows),
        "completion_rate": sum(row["provider"] != "unavailable" for row in rows) / len(rows),
        "fallback_rate": sum(row["fallback_used"] for row in rows) / len(rows),
        "p95_latency_ms": percentile95(latencies),
        "estimated_cost_usd": round(sum(row["estimated_cost_usd"] for row in rows), 8),
        "pricing": {"input_per_1k_usd": rows[0]["cost_per_1k_input_usd"], "output_per_1k_usd": rows[0]["cost_per_1k_output_usd"]},
        "failed_attempts": sum(len(row["failure_attribution"]) for row in rows),
    }


async def run() -> dict[str, Any]:
    providers = [name for name, key in PROVIDER_KEYS.items() if os.getenv(key)]
    if not providers:
        raise RuntimeError("Configure at least one provider API key in the AI runtime environment.")
    original_provider = os.getenv("DEFAULT_LLM_PROVIDER")
    original_fallbacks = os.getenv("LLM_FALLBACK_PROVIDERS")
    try:
        reports = [await evaluate_provider(provider) for provider in providers]
    finally:
        if original_provider is None:
            os.environ.pop("DEFAULT_LLM_PROVIDER", None)
        else:
            os.environ["DEFAULT_LLM_PROVIDER"] = original_provider
        if original_fallbacks is None:
            os.environ.pop("LLM_FALLBACK_PROVIDERS", None)
        else:
            os.environ["LLM_FALLBACK_PROVIDERS"] = original_fallbacks
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": "opsbridge-synthetic-extraction-v1",
        "prompt_fingerprint": hashlib.sha256(EXTRACTION_SYSTEM.encode("utf-8")).hexdigest()[:16],
        "cases_per_provider": len(CASES),
        "pricing_note": "Cost uses configured per-1K token rates; zero rates yield zero estimates.",
        "providers": reports,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="/artifacts/ai-provider-reliability.json")
    parser.add_argument("--min-accuracy", type=float, default=0.66)
    parser.add_argument("--max-p95-ms", type=int, default=30000)
    args = parser.parse_args()
    try:
        report = asyncio.run(run())
    except Exception as exc:
        parser.error(str(exc))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    for provider in report["providers"]:
        print(f"{provider['provider']}/{provider['model']}: accuracy={provider['accuracy']:.2%}, p95={provider['p95_latency_ms']}ms, cost=${provider['estimated_cost_usd']:.6f}, failed_attempts={provider['failed_attempts']}")
    print(f"Report written to {output}")
    return int(any(p["accuracy"] < args.min_accuracy or p["p95_latency_ms"] > args.max_p95_ms for p in report["providers"]))


if __name__ == "__main__":
    raise SystemExit(main())
