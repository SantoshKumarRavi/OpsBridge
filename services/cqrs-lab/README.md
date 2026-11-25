# CQRS and projection lab

This isolated Python lab separates onboarding commands from query reads. The command side owns case state, optimistic versions, idempotency receipts, and an append-only event log in one SQLite database. A projection worker consumes that event log into a separate SQLite read model. Queries are tenant-scoped and can be stale until the projection catches up, demonstrating eventual consistency.

The projection records processed event IDs and advances its offset in the same read-store transaction as projection changes. It can rebuild the read model from the command event log. A rebuilt projection is deterministic for the event schema in this lab; the command database remains the source of truth.

Run from the repository root:

```bash
npm run test:cqrs
```

The tests cover command/read separation, stale reads, tenant filtering, idempotency, optimistic concurrency, projection checkpoints, and replay. The lab uses a single projection worker and local SQLite files; it does not demonstrate distributed database replication, multi-worker leasing, event schema evolution, or a production message broker. All records are synthetic.
