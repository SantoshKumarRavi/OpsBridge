import tempfile
import unittest
from pathlib import Path

from cqrs import CommandConflict, CommandStore, IdempotencyConflict, ProjectionWorker


class CqrsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.command_path = root / "commands.sqlite3"
        self.read_path = root / "read-model.sqlite3"
        self.commands = CommandStore(self.command_path)
        self.projection = ProjectionWorker(self.command_path, self.read_path)

    def tearDown(self):
        self.commands.close()
        self.projection.close()
        self.temp_dir.cleanup()

    def test_query_model_is_eventually_consistent_and_tenant_scoped(self):
        self.commands.open_case("tenant-a", "case-1", "worker-1", "open-1")

        self.assertIsNone(self.projection.get_case("tenant-a", "case-1"))
        self.assertEqual(self.projection.project_pending(), 1)
        self.assertEqual(self.projection.get_case("tenant-a", "case-1")["status"], "OPEN")
        self.assertIsNone(self.projection.get_case("tenant-b", "case-1"))

    def test_projection_advances_after_command_and_queries_filter(self):
        opened = self.commands.open_case("tenant-a", "case-1", "worker-1", "open-2")
        self.projection.project_pending()
        transitioned = self.commands.transition_case(
            "tenant-a", "case-1", "IN_REVIEW", 1, "review-1"
        )

        stale_read = self.projection.get_case("tenant-a", "case-1")
        self.assertEqual(stale_read["status"], "OPEN")
        self.assertEqual(stale_read["last_event_seq"], opened["event_seq"])

        self.assertEqual(self.projection.project_pending(), 1)
        current_read = self.projection.get_case("tenant-a", "case-1")
        self.assertEqual(current_read["status"], "IN_REVIEW")
        self.assertEqual(current_read["version"], 2)
        self.assertEqual(current_read["last_event_seq"], transitioned["event_seq"])
        self.assertEqual(self.projection.list_cases("tenant-a", "IN_REVIEW"), [current_read])
        self.assertEqual(self.projection.list_cases("tenant-b"), [])

    def test_command_idempotency_replays_response_and_rejects_key_reuse(self):
        first = self.commands.open_case("tenant-a", "case-1", "worker-1", "open-3")
        retry = self.commands.open_case("tenant-a", "case-1", "worker-1", "open-3")

        self.assertEqual(retry, first)
        with self.assertRaises(IdempotencyConflict):
            self.commands.open_case("tenant-a", "case-2", "worker-1", "open-3")

    def test_optimistic_version_prevents_lost_update_and_retry_is_safe(self):
        self.commands.open_case("tenant-a", "case-1", "worker-1", "open-4")
        result = self.commands.transition_case(
            "tenant-a", "case-1", "IN_REVIEW", 1, "review-2"
        )

        self.assertEqual(
            self.commands.transition_case(
                "tenant-a", "case-1", "IN_REVIEW", 1, "review-2"
            ),
            result,
        )
        with self.assertRaises(CommandConflict):
            self.commands.transition_case(
                "tenant-a", "case-1", "APPROVED", 1, "approve-stale"
            )

    def test_projection_can_be_rebuilt_from_command_event_log(self):
        self.commands.open_case("tenant-a", "case-1", "worker-1", "open-5")
        self.commands.transition_case("tenant-a", "case-1", "IN_REVIEW", 1, "review-3")
        self.commands.transition_case("tenant-a", "case-1", "APPROVED", 2, "approve-1")
        self.projection.project_pending(batch_size=2)
        self.assertEqual(self.projection.get_case("tenant-a", "case-1")["status"], "IN_REVIEW")

        replayed = self.projection.rebuild(batch_size=1)

        self.assertEqual(replayed, 3)
        rebuilt = self.projection.get_case("tenant-a", "case-1")
        self.assertEqual(rebuilt["status"], "APPROVED")
        self.assertEqual(rebuilt["version"], 3)
        self.assertEqual(self.projection.watermark(), 3)


if __name__ == "__main__":
    unittest.main()
