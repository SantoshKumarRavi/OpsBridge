# Durable Saga lab

This isolated Python lab demonstrates an onboarding business Saga with durable orchestration and reverse-order compensation. It reserves a synthetic onboarding slot, provisions a synthetic access grant, and records a synthetic welcome notification. A failure compensates completed work; a failed compensation stays visible and can be retried after restarting the process.

The SQLite journal and simulated side effects share one local database so the example runs with the Python standard library. Effects are keyed by Saga ID to tolerate replay if the process stops after an effect commits but before its step journal is updated. An idempotency key returns the existing Saga and rejects reuse for a different worker.

Run from the repository root:

```bash
npm run test:saga
python services/saga-lab/demo.py
python services/saga-lab/demo.py --fail-at send_welcome
python services/saga-lab/demo.py --fail-at send_welcome --fail-compensation-at provision_access --retry-compensation
```

Or run `python -m unittest -v` from this directory. GitHub Actions runs the same unittest suite in its independent `saga-lab-unit-tests` job.

The tests cover success, reverse-order compensation, idempotency, process restart, and recovery after a compensation failure. All data is synthetic. The lab is single-process and does not claim distributed locking or a production-grade external side-effect delivery guarantee. A real deployment would need worker leases or optimistic concurrency, independent transactional stores per service, outbox delivery for external effects, secured retry/operations APIs, and monitoring.

To explore the sequence, set a breakpoint in `OnboardingSaga.run` and inspect `sagas`, `saga_steps`, and the effect tables in SQLite. The Saga coordinates local transactions; it does not create a distributed ACID transaction.
