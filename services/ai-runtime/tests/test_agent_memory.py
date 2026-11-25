import os
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, patch
import uuid

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent_memory import MAX_STORED_MESSAGES, append_bounded, scoped_thread_id, validate_session_id
from app.main import app


class AgentMemoryTests(unittest.TestCase):
    def setUp(self):
        self.previous_backend = os.environ.get("AGENT_MEMORY_BACKEND")
        os.environ["AGENT_MEMORY_BACKEND"] = "memory"
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        if self.previous_backend is None:
            os.environ.pop("AGENT_MEMORY_BACKEND", None)
        else:
            os.environ["AGENT_MEMORY_BACKEND"] = self.previous_backend

    def test_thread_id_is_scoped_to_tenant_actor_and_session(self):
        base = scoped_thread_id("tenant-a", "actor-a", "session-1")
        self.assertNotEqual(base, scoped_thread_id("tenant-b", "actor-a", "session-1"))
        self.assertNotEqual(base, scoped_thread_id("tenant-a", "actor-b", "session-1"))
        self.assertNotEqual(base, scoped_thread_id("tenant-a", "actor-a", "session-2"))

    def test_session_identifier_validation(self):
        self.assertEqual(validate_session_id("browser:session-1"), "browser:session-1")
        for invalid in ("", "../secret", "x" * 81, "contains space"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_session_id(invalid)

    def test_checkpoint_message_history_is_bounded(self):
        old = [{"role": "user", "content": str(i)} for i in range(MAX_STORED_MESSAGES)]
        bounded = append_bounded(old, [{"role": "assistant", "content": "new"}])
        self.assertEqual(len(bounded), MAX_STORED_MESSAGES)
        self.assertEqual(bounded[-1]["content"], "new")
        self.assertEqual(bounded[0]["content"], "1")

    def test_turns_persist_in_thread_and_external_action_stays_unexecuted(self):
        headers = {"X-Tenant-Id": "tenant-a", "X-Actor-Id": "actor-a"}
        first = self.client.post("/v1/agents/execute", headers=headers, json={
            "session_id": "session-1", "message": "Review application", "plan": [{"step": "review"}],
        })
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()["status"], "accepted")
        self.assertFalse(first.json()["executed"])

        second = self.client.post("/v1/agents/execute", headers=headers, json={
            "session_id": "session-1", "message": "Request approval", "requires_external_action": True,
        })
        self.assertEqual(second.json()["status"], "awaiting_human_approval")
        self.assertFalse(second.json()["executed"])
        self.assertEqual(len(second.json()["messages"]), 4)

        saved = self.client.get("/v1/agents/threads/session-1", headers=headers)
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(len(saved.json()["messages"]), 4)
        self.assertEqual(saved.json()["status"], "awaiting_human_approval")

    def test_oversized_plan_is_rejected(self):
        response = self.client.post("/v1/agents/execute", headers={"X-Tenant-Id": "tenant-a"}, json={
            "session_id": "session-1", "message": "Review", "plan": [{"step": "x" * 8100}],
        })
        self.assertEqual(response.status_code, 422)

    def test_allowlisted_tool_result_is_returned_and_checkpointed(self):
        summary = {"case_id": str(uuid.uuid4()), "status": "processing", "role": "Analyst", "country": "IN", "version": 2}
        with patch("app.main.execute_tool", new=AsyncMock(return_value=summary)) as run_tool:
            response = self.client.post("/v1/agents/execute", headers={
                "X-Tenant-Id": "tenant-a", "X-Actor-Id": "actor-a", "X-Correlation-Id": "trace-42",
            }, json={
                "session_id": "tool-session", "message": "Check this case", "tool_name": "get_case_summary",
                "tool_arguments": {"case_id": summary["case_id"]},
            })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["tool_result"], summary)
        self.assertTrue(response.json()["tool_executed"])
        self.assertFalse(response.json()["executed"])
        run_tool.assert_awaited_once_with(
            "get_case_summary", {"case_id": summary["case_id"]}, tenant_id="tenant-a", actor_id="actor-a", correlation_id="trace-42",
        )
        saved = self.client.get("/v1/agents/threads/tool-session", headers={"X-Tenant-Id": "tenant-a", "X-Actor-Id": "actor-a"})
        self.assertEqual(saved.json()["tool_result"], summary)

    def test_thread_is_invisible_to_other_tenant_or_actor_and_can_be_deleted(self):
        owner = {"X-Tenant-Id": "tenant-a", "X-Actor-Id": "actor-a"}
        self.client.post("/v1/agents/execute", headers=owner, json={
            "session_id": "session-1", "message": "Keep this private",
        })
        for headers in (
            {"X-Tenant-Id": "tenant-b", "X-Actor-Id": "actor-a"},
            {"X-Tenant-Id": "tenant-a", "X-Actor-Id": "actor-b"},
        ):
            response = self.client.get("/v1/agents/threads/session-1", headers=headers)
            self.assertEqual(response.status_code, 404)
        deleted = self.client.delete("/v1/agents/threads/session-1", headers=owner)
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(self.client.get("/v1/agents/threads/session-1", headers=owner).status_code, 404)


if __name__ == "__main__":
    unittest.main()
