import tempfile
import unittest
from pathlib import Path

from saga import IdempotencyConflict, OnboardingSaga


class OnboardingSagaTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Path(self.temp_dir.name) / "saga.sqlite3"
        self.saga = OnboardingSaga(self.database)

    def tearDown(self):
        self.saga.close()
        self.temp_dir.cleanup()

    def test_success_completes_all_steps_and_effects(self):
        saga_id = self.saga.create("request-1", "worker-1")

        result = self.saga.run(saga_id)

        self.assertEqual(result["status"], "SUCCEEDED")
        self.assertEqual([step["status"] for step in result["steps"]], ["COMPLETED"] * 3)
        self.assertEqual(result["effects"], {
            "reservation": True,
            "access": True,
            "welcome": "SENT",
        })

    def test_failure_compensates_completed_steps_in_reverse_order(self):
        saga_id = self.saga.create("request-2", "worker-2")

        result = self.saga.run(saga_id, fail_at="send_welcome")

        self.assertEqual(result["status"], "COMPENSATED")
        self.assertEqual([step["status"] for step in result["steps"]], ["COMPENSATED", "COMPENSATED", "PENDING"])
        compensation_order = {
            step["step_name"]: step["compensation_ordinal"]
            for step in result["steps"]
            if step["compensation_ordinal"] is not None
        }
        self.assertEqual(compensation_order, {"provision_access": 1, "reserve_slot": 2})
        self.assertEqual(result["effects"], {
            "reservation": False,
            "access": False,
            "welcome": None,
        })

    def test_failed_compensation_can_resume_after_process_restart(self):
        saga_id = self.saga.create("request-3", "worker-3")
        first = self.saga.run(
            saga_id,
            fail_at="send_welcome",
            fail_compensation_at="provision_access",
        )
        self.assertEqual(first["status"], "COMPENSATION_FAILED")
        self.saga.close()

        self.saga = OnboardingSaga(self.database)
        recovered = self.saga.run(saga_id)

        self.assertEqual(recovered["status"], "COMPENSATED")
        self.assertFalse(recovered["effects"]["reservation"])
        self.assertFalse(recovered["effects"]["access"])

    def test_idempotency_key_returns_existing_saga_for_same_request(self):
        first_id = self.saga.create("request-4", "worker-4")

        self.assertEqual(self.saga.create("request-4", "worker-4"), first_id)
        with self.assertRaises(IdempotencyConflict):
            self.saga.create("request-4", "different-worker")

    def test_running_saga_resumes_after_engine_restart(self):
        saga_id = self.saga.create("request-5", "worker-5")
        self.saga.close()

        self.saga = OnboardingSaga(self.database)
        recovered = self.saga.run(saga_id)

        self.assertEqual(recovered["status"], "SUCCEEDED")
        self.assertTrue(recovered["effects"]["reservation"])
        self.assertTrue(recovered["effects"]["access"])

    def test_replay_is_safe_if_effect_committed_before_step_journal(self):
        saga_id = self.saga.create("request-6", "worker-6")
        self.saga._apply_effect(saga_id, "reserve_slot")
        self.saga.close()

        self.saga = OnboardingSaga(self.database)
        recovered = self.saga.run(saga_id)

        count = self.saga._db.execute(
            "SELECT COUNT(*) FROM reservations WHERE saga_id = ?", (saga_id,)
        ).fetchone()[0]
        self.assertEqual(recovered["status"], "SUCCEEDED")
        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
