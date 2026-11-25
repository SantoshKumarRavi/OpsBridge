"""Offline golden-set retrieval evaluation; calls the local AI search API."""
import asyncio
import json
import math
import os
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "services" / "ai-runtime" / "evals" / "rag-golden-set.json"


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    return ordered[max(0, math.ceil(p * len(ordered)) - 1)]


async def run() -> int:
    examples = json.loads(DATASET.read_text(encoding="utf-8"))
    base_url = os.getenv("AI_RUNTIME_URL", "http://localhost:8002").rstrip("/")
    headers = {"X-Tenant-Id": os.getenv("OPSBRIDGE_TENANT_ID", "demo-tenant")}
    if token := os.getenv("OPSBRIDGE_ACCESS_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    if token := os.getenv("INTERNAL_SERVICE_TOKEN"):
        headers["X-Internal-Service-Token"] = token

    latencies: list[float] = []
    details = []
    total_relevant = total_retrieved_relevant = 0
    reciprocal_ranks = []
    precision_values = []
    isolation_passed = True
    reranker_queries = 0
    async with httpx.AsyncClient(timeout=30) as client:
        for example in examples:
            query_headers = {**headers, "X-Tenant-Id": example.get("tenantId", headers["X-Tenant-Id"])}
            response = await client.post(
                f"{base_url}/v1/knowledge/search",
                headers=query_headers,
                json={"query": example["query"]},
            )
            response.raise_for_status()
            latencies.append(response.elapsed.total_seconds())
            rows = response.json().get("items", [])
            if any("rerankScore" in row for row in rows):
                reranker_queries += 1
            relevant = set(example["relevantTitles"])
            titles = [str(row.get("title", "")) for row in rows]
            if example.get("expectEmpty"):
                passed = not titles
                isolation_passed = isolation_passed and passed
                details.append({"id": example["id"], "tenantIsolationPassed": passed, "retrieved": titles})
                continue
            found = [title for title in titles if title in relevant]
            total_relevant += len(relevant)
            total_retrieved_relevant += len(set(found))
            first_rank = next((rank for rank, title in enumerate(titles, 1) if title in relevant), None)
            reciprocal_ranks.append(1 / first_rank if first_rank else 0.0)
            precision_values.append(len(set(found)) / max(1, min(5, len(rows))))
            details.append({"id": example["id"], "relevant": sorted(relevant), "retrieved": titles, "firstRelevantRank": first_rank})

    report = {
        "dataset": str(DATASET.relative_to(ROOT)),
        "queries": len(examples),
        "recallAt5": total_retrieved_relevant / max(1, total_relevant),
        "precisionAt5": sum(precision_values) / max(1, len(precision_values)),
        "meanReciprocalRank": sum(reciprocal_ranks) / max(1, len(reciprocal_ranks)),
        "p95LatencySeconds": percentile(latencies, 0.95),
        "tenantIsolationPassed": isolation_passed,
        "rerankerQueries": reranker_queries,
        "rerankerApplied": reranker_queries > 0,
        "details": details,
    }
    rendered_report = json.dumps(report, indent=2)
    print(rendered_report)
    if output_path := os.getenv("RAG_EVAL_OUTPUT_PATH"):
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(rendered_report + "\n", encoding="utf-8")
    if summary_path := os.getenv("GITHUB_STEP_SUMMARY"):
        with Path(summary_path).open("a", encoding="utf-8") as summary:
            summary.write(
                "## RAG retrieval evaluation\n\n"
                f"- Recall@5: {report['recallAt5']:.3f}\n"
                f"- Precision@5: {report['precisionAt5']:.3f}\n"
                f"- MRR: {report['meanReciprocalRank']:.3f}\n"
                f"- p95 latency: {report['p95LatencySeconds']:.3f}s\n"
                f"- Reranker applied to queries: {reranker_queries}/{len(examples)}\n"
                f"- Tenant isolation: {'passed' if isolation_passed else 'FAILED'}\n"
            )
    passed = (
        report["recallAt5"] >= float(os.getenv("MIN_RECALL_AT_5", "0.85"))
        and report["meanReciprocalRank"] >= float(os.getenv("MIN_MRR", "0.70"))
        and report["p95LatencySeconds"] <= float(os.getenv("MAX_P95_SECONDS", "2.0"))
        and isolation_passed
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
