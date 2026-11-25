# LangGraph agent memory

The AI runtime stores agent sessions as LangGraph checkpoints. In Docker Compose, `AGENT_MEMORY_BACKEND=postgres` selects `AsyncPostgresSaver`; the saver schema is initialized during AI-runtime startup. `LANGGRAPH_STRICT_MSGPACK=true` enables LangGraph's safer msgpack handling. Local tests default to `InMemorySaver` and do not exercise PostgreSQL persistence.

## Session boundaries and API

- `POST /v1/agents/execute` requires `X-Tenant-Id`; `X-Actor-Id` comes from the authenticated gateway (direct local requests default to `service`). The session ID is bounded and hashed together with tenant and actor IDs before it becomes a checkpoint thread ID.
- The request can include a message, a plan, and approval flags. Messages, most recent plan, and current status are checkpointed. At most 40 messages are retained per thread; reads return the last 20.
- `GET /v1/agents/threads/{session_id}` reads only the caller's tenant/actor-scoped thread. `DELETE` explicitly removes that thread's checkpoints.
- PostgreSQL mode records a hashed thread ID and last-activity timestamp in `opsbridge_agent_memory_activity`. Threads expire after `AGENT_MEMORY_TTL_DAYS` (30 by default, bounded to 1–365 days); a startup sweep and hourly background sweep delete stale checkpoints in batches of 200. `AGENT_MEMORY_CLEANUP_INTERVAL_SECONDS` can change the sweep interval (60–86,400 seconds).
- External actions are never executed. `requires_external_action` without approval produces `awaiting_human_approval`; even with approval the response remains `executed: false` because no allow-listed action adapter exists.

## Verification

`npm run test:ai-runtime` verifies in-memory turn persistence, tenant/actor isolation, validation, approval status, expiry, and deletion. The `rag-retrieval-evaluation` GitHub Actions job runs `scripts/verify_ai_agent_memory.py`, which writes a synthetic thread, restarts the AI container, checks that PostgreSQL restored it, checks actor isolation, backdates a synthetic activity marker, restarts again, and verifies startup TTL cleanup removed the thread. This Docker-backed PostgreSQL gate still needs its first hosted CI run.

## Limits

This is thread-scoped short-term memory, not cross-session semantic/user memory. TTL cleanup and explicit deletion are implemented; Docker-backed cleanup still needs a hosted run. A production rollout should align the configured TTL with its retention policy. There is no LLM-driven planning or memory summarization. The read-only tool boundary and its limits are documented in [agent-tool-execution.md](agent-tool-execution.md).
