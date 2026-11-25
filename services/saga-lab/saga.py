"""Durable, single-process onboarding Saga exercise using only the Python stdlib."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any


STEPS = ("reserve_slot", "provision_access", "send_welcome")


class IdempotencyConflict(ValueError):
    """Raised when a key is reused for a different onboarding request."""


class OnboardingSaga:
    """Persist a synthetic workflow and reverse completed effects after failure.

    Effects are deliberately stored in the same SQLite file to make the lab
    self-contained. Each effect is keyed by saga ID, so replay after a process
    restart is safe when an effect committed before its journal update.
    """

    def __init__(self, database: str | Path):
        self.database = str(database)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.database, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

    def close(self) -> None:
        self._db.close()

    def create(self, idempotency_key: str, worker_id: str) -> str:
        if not idempotency_key.strip() or not worker_id.strip():
            raise ValueError("idempotency_key and worker_id are required")

        with self._lock:
            existing = self._db.execute(
                "SELECT saga_id, worker_id FROM sagas WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if existing:
                if existing["worker_id"] != worker_id:
                    raise IdempotencyConflict(
                        "idempotency key already belongs to a different worker"
                    )
                return str(existing["saga_id"])

            saga_id = str(uuid.uuid4())
            self._db.execute("BEGIN IMMEDIATE")
            try:
                self._db.execute(
                    "INSERT INTO sagas (saga_id, idempotency_key, worker_id, status, "
                    "request_json) VALUES (?, ?, ?, 'RUNNING', ?)",
                    (saga_id, idempotency_key, worker_id, json.dumps({"worker_id": worker_id})),
                )
                self._db.executemany(
                    "INSERT INTO saga_steps (saga_id, step_name, ordinal, status) "
                    "VALUES (?, ?, ?, 'PENDING')",
                    [(saga_id, name, index) for index, name in enumerate(STEPS)],
                )
                self._db.execute("COMMIT")
            except Exception:
                self._db.execute("ROLLBACK")
                raise
            return saga_id

    def run(
        self,
        saga_id: str,
        *,
        fail_at: str | None = None,
        fail_compensation_at: str | None = None,
    ) -> dict[str, Any]:
        """Advance pending work, or resume compensations after a prior failure."""
        with self._lock:
            saga = self._get_saga(saga_id)
            if saga["status"] in ("SUCCEEDED", "COMPENSATED"):
                return self.snapshot(saga_id)
            if saga["status"] in ("COMPENSATING", "COMPENSATION_FAILED"):
                self._compensate(saga_id, fail_compensation_at)
                return self.snapshot(saga_id)

            for step in self._get_steps(saga_id):
                if step["status"] == "COMPLETED":
                    continue
                if fail_at == step["step_name"]:
                    self._fail(saga_id, f"synthetic failure at {fail_at}")
                    break
                self._apply_effect(saga_id, step["step_name"])
                self._db.execute(
                    "UPDATE saga_steps SET status = 'COMPLETED', error = NULL, "
                    "compensation_error = NULL WHERE saga_id = ? AND step_name = ?",
                    (saga_id, step["step_name"]),
                )

            current = self._get_saga(saga_id)
            if current["status"] == "RUNNING":
                self._db.execute(
                    "UPDATE sagas SET status = 'SUCCEEDED' WHERE saga_id = ?", (saga_id,)
                )
            elif current["status"] == "COMPENSATING":
                self._compensate(saga_id, fail_compensation_at)
            return self.snapshot(saga_id)

    def snapshot(self, saga_id: str) -> dict[str, Any]:
        saga = dict(self._get_saga(saga_id))
        saga["steps"] = [dict(row) for row in self._get_steps(saga_id)]
        saga["effects"] = {
            "reservation": self._effect_exists("reservations", saga_id),
            "access": self._effect_exists("access_grants", saga_id),
            "welcome": self._welcome_status(saga_id),
        }
        return saga

    def _create_schema(self) -> None:
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS sagas (
                saga_id TEXT PRIMARY KEY,
                idempotency_key TEXT NOT NULL UNIQUE,
                worker_id TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN (
                    'RUNNING', 'COMPENSATING', 'COMPENSATION_FAILED',
                    'COMPENSATED', 'SUCCEEDED'
                )),
                request_json TEXT NOT NULL,
                failure_reason TEXT
            );
            CREATE TABLE IF NOT EXISTS saga_steps (
                saga_id TEXT NOT NULL REFERENCES sagas(saga_id),
                step_name TEXT NOT NULL,
                ordinal INTEGER NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('PENDING', 'COMPLETED', 'COMPENSATED')),
                error TEXT,
                compensation_error TEXT,
                compensation_ordinal INTEGER,
                PRIMARY KEY (saga_id, step_name),
                UNIQUE (saga_id, ordinal)
            );
            CREATE TABLE IF NOT EXISTS reservations (
                saga_id TEXT PRIMARY KEY REFERENCES sagas(saga_id), worker_id TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS access_grants (
                saga_id TEXT PRIMARY KEY REFERENCES sagas(saga_id), worker_id TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS welcome_notifications (
                saga_id TEXT PRIMARY KEY REFERENCES sagas(saga_id),
                worker_id TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('SENT', 'CANCELLED'))
            );
            """
        )

    def _apply_effect(self, saga_id: str, step_name: str) -> None:
        worker_id = self._get_saga(saga_id)["worker_id"]
        if step_name == "reserve_slot":
            self._db.execute(
                "INSERT OR IGNORE INTO reservations (saga_id, worker_id) VALUES (?, ?)",
                (saga_id, worker_id),
            )
        elif step_name == "provision_access":
            self._db.execute(
                "INSERT OR IGNORE INTO access_grants (saga_id, worker_id) VALUES (?, ?)",
                (saga_id, worker_id),
            )
        elif step_name == "send_welcome":
            self._db.execute(
                "INSERT OR IGNORE INTO welcome_notifications (saga_id, worker_id, status) "
                "VALUES (?, ?, 'SENT')",
                (saga_id, worker_id),
            )
        else:
            raise ValueError(f"unknown Saga step: {step_name}")

    def _compensate(self, saga_id: str, fail_at: str | None) -> None:
        completed = self._db.execute(
            "SELECT step_name FROM saga_steps WHERE saga_id = ? AND status = 'COMPLETED' "
            "ORDER BY ordinal DESC",
            (saga_id,),
        ).fetchall()
        for row in completed:
            name = str(row["step_name"])
            if fail_at == name:
                self._db.execute(
                    "UPDATE saga_steps SET compensation_error = ? "
                    "WHERE saga_id = ? AND step_name = ?",
                    (f"synthetic compensation failure at {name}", saga_id, name),
                )
                self._db.execute(
                    "UPDATE sagas SET status = 'COMPENSATION_FAILED' WHERE saga_id = ?",
                    (saga_id,),
                )
                return
            self._undo_effect(saga_id, name)
            next_ordinal = self._db.execute(
                "SELECT COALESCE(MAX(compensation_ordinal), 0) + 1 "
                "FROM saga_steps WHERE saga_id = ?",
                (saga_id,),
            ).fetchone()[0]
            self._db.execute(
                "UPDATE saga_steps SET status = 'COMPENSATED', compensation_error = NULL, "
                "compensation_ordinal = ? "
                "WHERE saga_id = ? AND step_name = ?",
                (next_ordinal, saga_id, name),
            )
        self._db.execute(
            "UPDATE sagas SET status = 'COMPENSATED' WHERE saga_id = ?", (saga_id,)
        )

    def _undo_effect(self, saga_id: str, step_name: str) -> None:
        table = {
            "reserve_slot": "reservations",
            "provision_access": "access_grants",
        }.get(step_name)
        if table:
            self._db.execute(f"DELETE FROM {table} WHERE saga_id = ?", (saga_id,))
        elif step_name == "send_welcome":
            self._db.execute(
                "UPDATE welcome_notifications SET status = 'CANCELLED' WHERE saga_id = ?",
                (saga_id,),
            )
        else:
            raise ValueError(f"unknown Saga compensation: {step_name}")

    def _fail(self, saga_id: str, reason: str) -> None:
        self._db.execute(
            "UPDATE sagas SET status = 'COMPENSATING', failure_reason = ? WHERE saga_id = ?",
            (reason, saga_id),
        )

    def _get_saga(self, saga_id: str) -> sqlite3.Row:
        row = self._db.execute("SELECT * FROM sagas WHERE saga_id = ?", (saga_id,)).fetchone()
        if row is None:
            raise KeyError(f"Saga not found: {saga_id}")
        return row

    def _get_steps(self, saga_id: str) -> list[sqlite3.Row]:
        return self._db.execute(
            "SELECT * FROM saga_steps WHERE saga_id = ? ORDER BY ordinal", (saga_id,)
        ).fetchall()

    def _effect_exists(self, table: str, saga_id: str) -> bool:
        row = self._db.execute(
            f"SELECT 1 FROM {table} WHERE saga_id = ?", (saga_id,)
        ).fetchone()
        return row is not None

    def _welcome_status(self, saga_id: str) -> str | None:
        row = self._db.execute(
            "SELECT status FROM welcome_notifications WHERE saga_id = ?", (saga_id,)
        ).fetchone()
        return str(row["status"]) if row else None
