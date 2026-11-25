import asyncio
from pathlib import Path
import sys
from unittest import TestCase
from unittest.mock import patch
import uuid

import httpx
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent_tools import execute_tool


class AgentToolTests(TestCase):
    def test_allowlisted_lookup_forwards_tenant_actor_and_returns_minimized_fields(self):
        case_id = str(uuid.uuid4())
        observed = {}

        async def handler(request):
            observed["url"] = str(request.url)
            observed["tenant"] = request.headers["X-Tenant-Id"]
            observed["actor"] = request.headers["X-Actor-Id"]
            observed["correlation"] = request.headers["X-Correlation-Id"]
            return httpx.Response(200, json={
                "id": case_id, "status": "processing", "role": "Analyst", "country": "IN", "version": 3,
                "worker_name": "Private Name", "email": "private@example.test", "documents": [{"id": "secret"}],
            })

        async def run():
            transport = httpx.MockTransport(handler)
            with patch.dict("os.environ", {"COMPLIANCE_API_BASE_URL": "http://compliance.test"}):
                return await execute_tool(
                    "get_case_summary", {"case_id": case_id}, tenant_id="tenant-a", actor_id="actor-a",
                    correlation_id="trace-1", transport=transport,
                )

        result = asyncio.run(run())
        self.assertEqual(observed["url"], f"http://compliance.test/api/v1/cases/{case_id}")
        self.assertEqual(observed["tenant"], "tenant-a")
        self.assertEqual(observed["actor"], "actor-a")
        self.assertEqual(observed["correlation"], "trace-1")
        self.assertEqual(result, {"case_id": case_id, "status": "processing", "role": "Analyst", "country": "IN", "version": 3})
        self.assertNotIn("email", result)

    def test_unlisted_tool_is_rejected_without_making_http_request(self):
        async def run():
            return await execute_tool(
                "fetch_url", {"url": "https://attacker.test"}, tenant_id="tenant-a", actor_id="actor-a",
                transport=httpx.MockTransport(lambda _request: self.fail("network should not be called")),
            )

        with self.assertRaises(HTTPException) as raised:
            asyncio.run(run())
        self.assertEqual(raised.exception.status_code, 400)

    def test_tool_arguments_reject_extra_fields_and_invalid_case_ids(self):
        async def run(arguments):
            return await execute_tool(
                "get_case_summary", arguments, tenant_id="tenant-a", actor_id="actor-a",
                transport=httpx.MockTransport(lambda _request: self.fail("network should not be called")),
            )

        for arguments in (
            {"case_id": str(uuid.uuid4()), "url": "http://internal"},
            {"case_id": "not-a-uuid"},
        ):
            with self.subTest(arguments=arguments), self.assertRaises(HTTPException) as raised:
                asyncio.run(run(arguments))
            self.assertEqual(raised.exception.status_code, 422)

    def test_cross_tenant_not_found_is_returned_as_not_found(self):
        async def run():
            transport = httpx.MockTransport(lambda _request: httpx.Response(404, json={"error": "Case not found."}))
            with patch.dict("os.environ", {"COMPLIANCE_API_BASE_URL": "http://compliance.test"}):
                return await execute_tool(
                    "get_case_summary", {"case_id": str(uuid.uuid4())}, tenant_id="tenant-b", actor_id="actor-b",
                    transport=transport,
                )

        with self.assertRaises(HTTPException) as raised:
            asyncio.run(run())
        self.assertEqual(raised.exception.status_code, 404)


if __name__ == "__main__":
    import unittest
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    unittest.main()
