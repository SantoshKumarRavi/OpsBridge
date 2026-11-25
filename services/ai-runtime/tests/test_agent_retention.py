import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent_retention import AgentMemoryRetention


class FakeCheckpointer:
    def __init__(self):
        self.deleted = []

    async def adelete_thread(self, thread_id):
        self.deleted.append(thread_id)


class AgentMemoryRetentionTests(unittest.IsolatedAsyncioTestCase):
    async def test_expiry_removes_stale_threads_and_preserves_recent_activity(self):
        now = datetime(2026, 11, 20, tzinfo=timezone.utc)
        retention = AgentMemoryRetention(ttl_days=30)
        retention._memory_activity["stale"] = now - timedelta(days=31)
        retention._memory_activity["recent"] = now - timedelta(days=29)
        checkpointer = FakeCheckpointer()

        expired = await retention.expire(checkpointer, now=now)

        self.assertEqual(expired, 1)
        self.assertEqual(checkpointer.deleted, ["stale"])
        self.assertNotIn("stale", retention._memory_activity)
        self.assertIn("recent", retention._memory_activity)

    async def test_touch_refreshes_thread_and_explicit_delete_forgets_activity(self):
        retention = AgentMemoryRetention(ttl_days=1)
        await retention.touch("thread-a")
        previous = retention._memory_activity["thread-a"]
        await retention.touch("thread-a")
        self.assertGreaterEqual(retention._memory_activity["thread-a"], previous)
        await retention.forget("thread-a")
        self.assertNotIn("thread-a", retention._memory_activity)

    async def test_ttl_configuration_is_bounded(self):
        for days in (0, 366):
            with self.subTest(days=days), self.assertRaises(ValueError):
                AgentMemoryRetention(ttl_days=days)


if __name__ == "__main__":
    unittest.main()
