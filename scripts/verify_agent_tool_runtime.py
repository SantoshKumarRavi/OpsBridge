"""Exercise the AI tool over gateway -> AI runtime -> tenant-scoped compliance API."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid


BASE_URL = os.getenv("API_GATEWAY_URL", "http://localhost:8080").rstrip("/")


def request(method: str, path: str, tenant: str, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE_URL + path,
        data=data,
        method=method,
        headers={
            "Content-Type": "application/json",
            "X-Tenant-Id": tenant,
            "X-Correlation-Id": "agent-tool-runtime-ci",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def main():
    tenant = "agent-tool-ci-" + uuid.uuid4().hex[:12]
    status, case = request("POST", "/api/v1/cases", tenant, {
        "workerName": "Synthetic Agent Tool Check",
        "email": "tool-check@example.invalid",
        "role": "Read-only tool verification",
        "country": "US",
    })
    assert status == 201, case

    session_id = "tool-ci-" + uuid.uuid4().hex[:12]
    status, result = request("POST", "/api/v1/ai/agents/execute", tenant, {
        "session_id": session_id,
        "message": "Read the synthetic case status.",
        "tool_name": "get_case_summary",
        "tool_arguments": {"case_id": case["id"]},
    })
    assert status == 200, result
    assert result["tool_executed"] is True and result["executed"] is False, result
    assert result["tool_result"]["case_id"] == case["id"], result
    assert "email" not in result["tool_result"] and "worker_name" not in result["tool_result"], result

    status, thread = request("GET", f"/api/v1/ai/agents/threads/{session_id}", tenant)
    assert status == 200 and thread["tool_result"]["case_id"] == case["id"], thread

    other_tenant = "agent-tool-other-" + uuid.uuid4().hex[:10]
    status, denied = request("POST", "/api/v1/ai/agents/execute", other_tenant, {
        "session_id": session_id,
        "message": "Try a cross-tenant lookup.",
        "tool_name": "get_case_summary",
        "tool_arguments": {"case_id": case["id"]},
    })
    assert status == 404, f"cross-tenant tool lookup must be hidden: HTTP {status}, {denied}"
    print("Gateway-to-AI-to-compliance read-only tool, data minimization, and tenant isolation passed.")


if __name__ == "__main__":
    main()
