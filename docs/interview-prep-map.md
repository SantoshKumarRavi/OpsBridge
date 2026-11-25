# Interview preparation map for OpsBridge

Source code can demonstrate implementation exposure. It cannot establish that you can explain, adapt, debug, or collaborate. Use this map to turn the repo into interview evidence. Keep a short practice log: question/problem, first attempt, what failed, final reasoning, complexity/trade-off, and the next review date.

The isolated [Python DSA lab](../practice/dsa/README.md) now contains tested references for arrays/hash maps, sliding window, two pointers, binary search, sorting, linked lists, stacks, trees, BFS, heaps, tries, backtracking, and dynamic programming. Keep the checkboxes below unchecked until you can solve and explain representative problems independently; passing the reference tests is not proof of that skill.

## Technical deep dives to explain from the project

- **JavaScript/TypeScript and React:** event loop, promises/async-await, browser rendering, component/state boundaries, React Hooks, memoization, accessible forms, performance trade-offs, and API errors. Use the operations dashboard, worker portal, and frontend patterns lab.
- **Python backend:** request validation, Django models/migrations/transactions, tenant scoping, Celery retries/idempotency, FastAPI async I/O, and AI-service boundaries. Use the compliance API and AI runtime.
- **Java/Spring:** MVC/controller/service/repository layers, JPA/Hibernate persistence, Maven vs. Gradle, dependency injection, validation, and the Spring Cloud circuit-breaker/fallback lab. Explain which behavior is synthetic and which is core product code.
- **Go:** HTTP handler lifecycle, context/timeouts, concurrency/atomics, metrics, and why the telemetry endpoint does not claim durable queuing.
- **Databases:** normalization/data modeling, joins, transactions/ACID, indexes, isolation/locking, query plans, connection pools, migrations, replication, consistency, Mongo aggregation/indexes, Redis cache/Pub/Sub/queues/rate limits, graph traversal, and vector retrieval. Compare one primary store to one adapter instead of listing every database.
- **Distributed systems:** outbox, at-least-once delivery, deduplication, idempotency, DLQ/redrive, ordering, retry/backoff, circuit breaking, eventual consistency, Saga/CQRS trade-offs, partitioning, race conditions, deadlocks, availability, graceful degradation and recovery. Trace a case-created event through producer, Kafka, consumer transaction and offset commit. Use `services/saga-lab` to explain forward steps, the durable journal, reverse compensation, crash recovery and the limits of a single-process SQLite lab. Use `services/cqrs-lab` to explain command ownership, stale reads, projection checkpoints, tenant scoping and replay.
- **Security and identity:** OIDC/OAuth, JWT issuer/audience/tenant claims, RBAC, least privilege, secret handling, file-upload threats, webhook signatures, secure logs, audit retention and why the development identity header cannot be used in production.
- **AI/RAG:** provider abstraction, chunking, metadata filters, embeddings/vector search, retrieval quality, structured output validation, prompt/model fallback, evaluation set design, latency/cost tracking, trace attribution, and the human decision boundary.
- **Cloud and operations:** Docker image/runtime, Kubernetes manifests, Terraform/CDK diffs, cloud IAM, network boundaries, autoscaling, logs/metrics/traces, SLI/SLO/SLA, rollback, incident response, cost controls, and the exact scope of each cloud lab.

## DSA practice checklist

For each item, implement a solution without AI first, state time/space complexity, test edge cases, then use AI to review the reasoning and generate a second approach. Track problem links and review mistakes separately.

- [ ] Arrays and strings; two pointers; sliding window
- [ ] Hash maps and sets
- [ ] Linked lists; stacks; queues
- [ ] Binary search and sorting/searching algorithms
- [ ] Recursion and backtracking
- [ ] Trees, binary search trees, heaps, and tries
- [ ] Graph representation, BFS/DFS, shortest-path basics
- [ ] Dynamic programming fundamentals
- [ ] Time/space complexity and Big O explanations

## CS fundamentals and interview formats

- [ ] OOP, functional programming, SOLID, design patterns, memory management
- [ ] OS processes/threads, concurrency vs. parallelism, synchronization
- [ ] HTTP/HTTPS, DNS, TCP/IP, TLS, browser networking/rendering
- [ ] Database internals and transaction/concurrency fundamentals
- [ ] Frontend machine coding and frontend system design
- [ ] Backend API design, debugging and backend system design
- [ ] Full-stack/system design discussion with capacity and failure estimates
- [ ] Coding exercises, technical design walkthroughs and behavioral interviews

## Engineering practice and ownership evidence

Keep one concise example for each based on real work; do not present a portfolio simulation as employment or production ownership.

- [ ] Requirement discovery and translating a business need into acceptance criteria
- [ ] Estimation, task breakdown, sprint planning and Agile/Scrum collaboration
- [ ] Technical documentation, diagrams, decision records and clean maintainable code
- [ ] Code review, giving/receiving feedback and handling merge conflicts
- [ ] Debugging, root-cause analysis, incident response and recovery communication
- [ ] Product thinking, customer-facing communication and cross-functional coordination
- [ ] Ownership, mentoring and production support (use genuine work examples only)

## AI-assisted study loop

Ask Codex for a mock interviewer role and one question at a time. Answer aloud before requesting hints. After the answer, ask it to identify unsupported claims and probe trade-offs. For code exercises, request tests and review the tests before accepting them; AI output is not a substitute for reasoning you can explain without the assistant.
