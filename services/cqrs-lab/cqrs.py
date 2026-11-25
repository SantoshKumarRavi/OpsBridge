"""Minimal CQRS onboarding example with an event-backed read projection."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any, Callable


class CommandConflict(ValueError):
    """Raised when a command violates current aggregate state or version."""


class IdempotencyConflict(ValueError):
    """Raised when an idempotency key is reused for a different command."""


class CommandStore:
    """Authoritative write model and append-only event log."""

    def __init__(self, database: str | Path):
        self.database = str(database)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.database, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS cases (
                tenant_id TEXT NOT NULL,
                case_id TEXT NOT NULL,
                worker_id TEXT NOT NULL,
                status TEXT NOT NULL,
                version INTEGER NOT NULL,
                PRIMARY KEY (tenant_id, case_id)
            );
            CREATE TABLE IF NOT EXISTS domain_events (
                event_seq INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                tenant_id TEXT NOT NULL,
                aggregate_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS command_receipts (
                idempotency_key TEXT PRIMARY KEY,
                fingerprint TEXT NOT NULL,
                response_json TEXT NOT NULL
            );
            """
        )

    def close(self) -> None:
        self._db.close()

    def open_case(
        self, tenant_id: str, case_id: str, worker_id: str, idempotency_key: str
    ) -> dict[str, Any]:
        body = {"tenant_id": tenant_id, "case_id": case_id, "worker_id": worker_id}
        self._require_fields(body)

        def handle() -> dict[str, Any]:
            exists = self._db.execute(
                "SELECT 1 FROM cases WHERE tenant_id = ? AND case_id = ?",
                (tenant_id, case_id),
            ).fetchone()
            if exists:
                raise CommandConflict("case already exists")
            self._db.execute(
                "INSERT INTO cases (tenant_id, case_id, worker_id, status, version) "
                "VALUES (?, ?, ?, 'OPEN', 1)",
                (tenant_id, case_id, worker_id),
            )
            return self._append_event(
                "CaseOpened", tenant_id, case_id, worker_id, "OPEN", 1
            )

        return self._execute("OpenCase", body, idempotency_key, handle)

    def transition_case(
        self,
        tenant_id: str,
        case_id: str,
        new_status: str,
        expected_version: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        body = {
            "tenant_id": tenant_id,
            "case_id": case_id,
            "new_status": new_status,
            "expected_version": expected_version,
        }
        self._require_fields({key: value for key, value in body.items() if key != "expected_version"})

        def handle() -> dict[str, Any]:
            row = self._db.execute(
                "SELECT worker_id, status, version FROM cases "
                "WHERE tenant_id = ? AND case_id = ?",
                (tenant_id, case_id),
            ).fetchone()
            if row is None:
                raise KeyError("case not found for tenant")
            if row["version"] != expected_version:
                raise CommandConflict(
                    f"expected version {expected_version}, current version is {row['version']}"
                )
            allowed = {"OPEN": {"IN_REVIEW"}, "IN_REVIEW": {"APPROVED", "REJECTED"}}
            if new_status not in allowed.get(row["status"], set()):
                raise CommandConflict(f"transition {row['status']} -> {new_status} is not allowed")

            version = expected_version + 1
            updated = self._db.execute(
                "UPDATE cases SET status = ?, version = ? "
                "WHERE tenant_id = ? AND case_id = ? AND version = ?",
                (new_status, version, tenant_id, case_id, expected_version),
            ).rowcount
            if updated != 1:
                raise CommandConflict("case changed concurrently; reload and retry the command")
            return self._append_event(
                "CaseStatusChanged", tenant_id, case_id, row["worker_id"], new_status, version
            )

        return self._execute("TransitionCase", body, idempotency_key, handle)

    def _execute(
        self,
        command_name: str,
        body: dict[str, Any],
        idempotency_key: str,
        handler: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        if not idempotency_key.strip():
            raise ValueError("idempotency_key is required")
        fingerprint = hashlib.sha256(
            json.dumps({"command": command_name, **body}, sort_keys=True).encode("utf-8")
        ).hexdigest()
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                receipt = self._db.execute(
                    "SELECT fingerprint, response_json FROM command_receipts "
                    "WHERE idempotency_key = ?",
                    (idempotency_key,),
                ).fetchone()
                if receipt:
                    if receipt["fingerprint"] != fingerprint:
                        raise IdempotencyConflict("key already belongs to a different command")
                    result = json.loads(receipt["response_json"])
                    self._db.execute("COMMIT")
                    return result

                result = handler()
                self._db.execute(
                    "INSERT INTO command_receipts (idempotency_key, fingerprint, response_json) "
                    "VALUES (?, ?, ?)",
                    (idempotency_key, fingerprint, json.dumps(result)),
                )
                self._db.execute("COMMIT")
                return result
            except Exception:
                self._db.execute("ROLLBACK")
                raise

    def _append_event(
        self,
        event_type: str,
        tenant_id: str,
        case_id: str,
        worker_id: str,
        status: str,
        version: int,
    ) -> dict[str, Any]:
        event_id = str(uuid.uuid4())
        payload = {
            "tenant_id": tenant_id,
            "case_id": case_id,
            "worker_id": worker_id,
            "status": status,
            "version": version,
        }
        cursor = self._db.execute(
            "INSERT INTO domain_events "
            "(event_id, tenant_id, aggregate_id, event_type, payload_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (event_id, tenant_id, case_id, event_type, json.dumps(payload)),
        )
        return {"event_id": event_id, "event_seq": cursor.lastrowid, "version": version}

    @staticmethod
    def _require_fields(values: dict[str, Any]) -> None:
        if any(not isinstance(value, str) or not value.strip() for value in values.values()):
            raise ValueError("tenant_id, case_id, worker_id, and status are required")


class ProjectionWorker:
    """Asynchronously materialize query rows from the command event log."""

    PROJECTION_NAME = "case-list-v1"

    def __init__(self, command_database: str | Path, read_database: str | Path):
        self.command_database = str(command_database)
        self.read_database = str(read_database)
        self._lock = threading.Lock()
        self._commands = sqlite3.connect(self.command_database, isolation_level=None)
        self._commands.row_factory = sqlite3.Row
        self._read = sqlite3.connect(self.read_database, isolation_level=None)
        self._read.row_factory = sqlite3.Row
        self._read.executescript(
            """
            CREATE TABLE IF NOT EXISTS case_projection (
                tenant_id TEXT NOT NULL,
                case_id TEXT NOT NULL,
                worker_id TEXT NOT NULL,
                status TEXT NOT NULL,
                version INTEGER NOT NULL,
                last_event_seq INTEGER NOT NULL,
                PRIMARY KEY (tenant_id, case_id)
            );
            CREATE TABLE IF NOT EXISTS projected_events (
                event_id TEXT PRIMARY KEY,
                event_seq INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS projection_offsets (
                projection_name TEXT PRIMARY KEY,
                event_seq INTEGER NOT NULL
            );
            INSERT OR IGNORE INTO projection_offsets (projection_name, event_seq)
            VALUES ('case-list-v1', 0);
            """
        )

    def close(self) -> None:
        self._commands.close()
        self._read.close()

    def project_pending(self, batch_size: int = 100) -> int:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        with self._lock:
            offset = self._current_offset()
            events = self._commands.execute(
                "SELECT event_seq, event_id, event_type, payload_json "
                "FROM domain_events WHERE event_seq > ? ORDER BY event_seq LIMIT ?",
                (offset, batch_size),
            ).fetchall()
            if not events:
                return 0

            self._read.execute("BEGIN IMMEDIATE")
            try:
                applied = 0
                for event in events:
                    exists = self._read.execute(
                        "SELECT 1 FROM projected_events WHERE event_id = ?", (event["event_id"],)
                    ).fetchone()
                    if not exists:
                        self._apply_event(event)
                        self._read.execute(
                            "INSERT INTO projected_events (event_id, event_seq) VALUES (?, ?)",
                            (event["event_id"], event["event_seq"]),
                        )
                        applied += 1
                    self._read.execute(
                        "UPDATE projection_offsets SET event_seq = ? WHERE projection_name = ?",
                        (event["event_seq"], self.PROJECTION_NAME),
                    )
                self._read.execute("COMMIT")
                return applied
            except Exception:
                self._read.execute("ROLLBACK")
                raise

    def rebuild(self, batch_size: int = 100) -> int:
        """Delete the derived model and deterministically replay the event log."""
        with self._lock:
            self._read.execute("BEGIN IMMEDIATE")
            try:
                self._read.execute("DELETE FROM case_projection")
                self._read.execute("DELETE FROM projected_events")
                self._read.execute(
                    "UPDATE projection_offsets SET event_seq = 0 WHERE projection_name = ?",
                    (self.PROJECTION_NAME,),
                )
                self._read.execute("COMMIT")
            except Exception:
                self._read.execute("ROLLBACK")
                raise
        total = 0
        while True:
            applied = self.project_pending(batch_size)
            total += applied
            if applied == 0:
                return total

    def get_case(self, tenant_id: str, case_id: str) -> dict[str, Any] | None:
        row = self._read.execute(
            "SELECT tenant_id, case_id, worker_id, status, version, last_event_seq "
            "FROM case_projection WHERE tenant_id = ? AND case_id = ?",
            (tenant_id, case_id),
        ).fetchone()
        return dict(row) if row else None

    def list_cases(self, tenant_id: str, status: str | None = None) -> list[dict[str, Any]]:
        if status:
            rows = self._read.execute(
                "SELECT tenant_id, case_id, worker_id, status, version, last_event_seq "
                "FROM case_projection WHERE tenant_id = ? AND status = ? ORDER BY case_id",
                (tenant_id, status),
            ).fetchall()
        else:
            rows = self._read.execute(
                "SELECT tenant_id, case_id, worker_id, status, version, last_event_seq "
                "FROM case_projection WHERE tenant_id = ? ORDER BY case_id",
                (tenant_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def watermark(self) -> int:
        return self._current_offset()

    def _current_offset(self) -> int:
        row = self._read.execute(
            "SELECT event_seq FROM projection_offsets WHERE projection_name = ?",
            (self.PROJECTION_NAME,),
        ).fetchone()
        return int(row["event_seq"])

    def _apply_event(self, event: sqlite3.Row) -> None:
        payload = json.loads(event["payload_json"])
        if event["event_type"] not in ("CaseOpened", "CaseStatusChanged"):
            return
        self._read.execute(
            "INSERT INTO case_projection "
            "(tenant_id, case_id, worker_id, status, version, last_event_seq) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (tenant_id, case_id) DO UPDATE SET "
            "worker_id = excluded.worker_id, status = excluded.status, "
            "version = excluded.version, last_event_seq = excluded.last_event_seq "
            "WHERE excluded.version > case_projection.version",
            (
                payload["tenant_id"],
                payload["case_id"],
                payload["worker_id"],
                payload["status"],
                payload["version"],
                event["event_seq"],
            ),
        )
