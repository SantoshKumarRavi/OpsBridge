"""Verify LangGraph/PostgreSQL memory survives an AI container restart."""
from __future__ import annotations

import json
import hashlib
import os
import subprocess
import time
import urllib.error
import urllib.request
import uuid


BASE_URL = os.getenv("AI_RUNTIME_URL", "http://localhost:8002").rstrip("/")
COMPOSE_FILE = os.getenv("COMPOSE_FILE", "infra/docker-compose.yml")
TENANT = "agent-memory-ci-tenant"
ACTOR = "agent-memory-ci-actor"
SESSION = f"ci-{uuid.uuid4()}"


def request(method: str, path: str, *, body=None, tenant=TENANT, actor=ACTOR):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE_URL + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "X-Tenant-Id": tenant, "X-Actor-Id": actor},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status, json.loads(response.read()) if response.status != 204 else None
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def wait_healthy():
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(BASE_URL + "/health", timeout=3) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(2)
    raise RuntimeError("AI runtime did not become healthy after restart")


def restart_ai_runtime():
    subprocess.run(["docker", "compose", "-f", COMPOSE_FILE, "restart", "ai-runtime"], check=True)
    wait_healthy()


def main():
    status, created = request("POST", "/v1/agents/execute", body={
        "session_id": SESSION,
        "message": "Persist this synthetic CI thread across restart.",
        "requires_external_action": True,
        "plan": [{"step": "synthetic-review"}],
    })
    assert status == 200 and created["status"] == "awaiting_human_approval" and created["executed"] is False, created

    # A separate identity must not see the saved thread.
    status, _ = request("GET", f"/v1/agents/threads/{SESSION}", actor="different-actor")
    assert status == 404, f"thread leaked across actor boundary: HTTP {status}"

    restart_ai_runtime()

    status, restored = request("GET", f"/v1/agents/threads/{SESSION}")
    assert status == 200, f"thread did not survive restart: HTTP {status}"
    assert restored["status"] == "awaiting_human_approval", restored
    assert restored["plan"] == [{"step": "synthetic-review"}], restored
    assert any("Persist this synthetic CI thread" in item["content"] for item in restored["messages"]), restored

    status, _ = request("DELETE", f"/v1/agents/threads/{SESSION}")
    assert status == 204, f"thread cleanup failed: HTTP {status}"

    # Backdate a second thread's hashed activity marker, then prove startup TTL sweep
    # removes both its activity row and all LangGraph checkpoints.
    status, _ = request("POST", "/v1/agents/execute", body={
        "session_id": SESSION,
        "message": "Expire this synthetic thread in the cleanup test.",
    })
    assert status == 200
    thread_id = hashlib.sha256("\0".join((TENANT, ACTOR, SESSION)).encode()).hexdigest()
    ttl_days = int(os.getenv("AGENT_MEMORY_TTL_DAYS", "30"))
    sql = (
        "UPDATE opsbridge_agent_memory_activity "
        f"SET last_activity_at=now()-make_interval(days => {ttl_days + 1}) "
        f"WHERE thread_id='{thread_id}'"
    )
    backdate = subprocess.run([
        "docker", "compose", "-f", COMPOSE_FILE, "exec", "-T", "postgres",
        "psql", "-U", "opsbridge", "-d", "opsbridge", "-c", sql,
    ], check=True, capture_output=True, text=True)
    assert "UPDATE 1" in backdate.stdout, f"expected one thread activity marker to be backdated: {backdate.stdout}"
    restart_ai_runtime()
    status, _ = request("GET", f"/v1/agents/threads/{SESSION}")
    assert status == 404, f"stale thread was not expired on startup: HTTP {status}"
    print("LangGraph agent memory persistence, isolation, deletion, and PostgreSQL TTL expiry passed.")


if __name__ == "__main__":
    main()
