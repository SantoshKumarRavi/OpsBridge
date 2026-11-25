"""Wait for and verify the Compose-backed onboarding-to-Kafka projection path."""

from __future__ import annotations

import subprocess
import time
import json
import os
from datetime import datetime, timezone
from pathlib import Path


EXPECTED_EVENTS = {
    "case.created",
    "document.received",
    "document.processed",
    "case.ai_recommendation_updated",
}
QUERY = """
SELECT event_type || '=' || count(*)
FROM consumed_domain_events
WHERE tenant_id = 'demo-tenant'
  AND event_type IN (
    'case.created',
    'document.received',
    'document.processed',
    'case.ai_recommendation_updated'
  )
GROUP BY event_type;
"""
PRIVACY_QUERY = """
SELECT count(*)
FROM consumed_domain_events
WHERE tenant_id = 'demo-tenant'
  AND (summary ?| ARRAY['email', 'phone', 'ssn', 'documentId']);
"""


def query_postgres(sql: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "docker", "compose", "-f", "infra/docker-compose.yml",
            "--profile", "event-consumer-lab", "exec", "-T", "postgres",
            "psql", "-U", "opsbridge", "-d", "opsbridge", "-Atc", sql,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )


def main() -> None:
    deadline = time.monotonic() + 180
    last_error = "projection table is not ready"
    observed: dict[str, int] = {}
    while time.monotonic() < deadline:
        result = query_postgres(QUERY)
        if result.returncode == 0:
            observed = {
                name: int(count)
                for row in result.stdout.splitlines()
                if "=" in row
                for name, count in [row.strip().split("=", 1)]
            }
            if all(observed.get(event, 0) > 0 for event in EXPECTED_EVENTS):
                break
            last_error = f"expected all workflow events; observed {observed}"
        else:
            last_error = result.stderr.strip() or result.stdout.strip()
        time.sleep(3)
    else:
        raise RuntimeError(f"Kafka projection did not receive the complete workflow: {last_error}")

    privacy = query_postgres(PRIVACY_QUERY)
    if privacy.returncode != 0:
        raise RuntimeError(f"Could not verify projected-event privacy: {privacy.stderr.strip()}")
    leaked_rows = int(privacy.stdout.strip() or "0")
    if leaked_rows:
        raise RuntimeError(f"{leaked_rows} projected event rows contain disallowed personal or document fields")

    report_path = Path(os.getenv("EVENT_PROJECTION_REPORT_PATH", "artifacts/event-projection-e2e.json"))
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "status": "passed",
                "verifiedAt": datetime.now(timezone.utc).isoformat(),
                "tenantId": "demo-tenant",
                "projectedEventCounts": observed,
                "disallowedSummaryFieldRows": leaked_rows,
                "disallowedSummaryFields": ["email", "phone", "ssn", "documentId"],
            },
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    print(f"Complete onboarding event path verified: {observed}")
    print(f"Projected event privacy verified; report written to {report_path}")


if __name__ == "__main__":
    main()
