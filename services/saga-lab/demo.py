"""Run a synthetic onboarding Saga and print each resulting state."""

from __future__ import annotations

import argparse
import json
import tempfile
import uuid
from pathlib import Path

from saga import OnboardingSaga


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fail-at", choices=("reserve_slot", "provision_access", "send_welcome"))
    parser.add_argument(
        "--fail-compensation-at",
        choices=("reserve_slot", "provision_access", "send_welcome"),
    )
    parser.add_argument(
        "--retry-compensation",
        action="store_true",
        help="retry incomplete compensation once after showing the failure state",
    )
    parser.add_argument(
        "--database",
        type=Path,
        help="optional SQLite file path; otherwise use a temporary database",
    )
    args = parser.parse_args()

    if args.database:
        database = args.database
        database.parent.mkdir(parents=True, exist_ok=True)
        run_demo(database, args)
    else:
        with tempfile.TemporaryDirectory(prefix="opsbridge-saga-") as temp_dir:
            run_demo(Path(temp_dir) / "saga.sqlite3", args)


def run_demo(database: Path, args: argparse.Namespace) -> None:
    saga = OnboardingSaga(database)
    try:
        saga_id = saga.create(f"demo-{uuid.uuid4()}", "synthetic-worker-001")
        result = saga.run(
            saga_id,
            fail_at=args.fail_at,
            fail_compensation_at=args.fail_compensation_at,
        )
        print("Initial result:")
        print(json.dumps(result, indent=2))

        if args.retry_compensation and result["status"] == "COMPENSATION_FAILED":
            print("\nAfter compensation retry:")
            print(json.dumps(saga.run(saga_id), indent=2))
    finally:
        saga.close()


if __name__ == "__main__":
    main()
