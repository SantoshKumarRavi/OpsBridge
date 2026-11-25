"""Age-based expiry for LangGraph agent threads."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


class AgentMemoryRetention:
    def __init__(self, *, ttl_days: int, connection: Any = None):
        if ttl_days < 1 or ttl_days > 365:
            raise ValueError("agent memory TTL must be between 1 and 365 days")
        self.ttl_days = ttl_days
        self.connection = connection
        self._memory_activity: dict[str, datetime] = {}

    async def initialize(self) -> None:
        if self.connection is not None:
            await self.connection.execute(
                "CREATE TABLE IF NOT EXISTS opsbridge_agent_memory_activity ("
                "thread_id varchar(64) PRIMARY KEY, last_activity_at timestamptz NOT NULL)"
            )

    async def touch(self, thread_id: str) -> None:
        if self.connection is not None:
            await self.connection.execute(
                "INSERT INTO opsbridge_agent_memory_activity(thread_id,last_activity_at) VALUES(%s,now()) "
                "ON CONFLICT(thread_id) DO UPDATE SET last_activity_at=EXCLUDED.last_activity_at",
                (thread_id,),
            )
        else:
            self._memory_activity[thread_id] = datetime.now(timezone.utc)

    async def forget(self, thread_id: str) -> None:
        if self.connection is not None:
            await self.connection.execute(
                "DELETE FROM opsbridge_agent_memory_activity WHERE thread_id=%s", (thread_id,)
            )
        self._memory_activity.pop(thread_id, None)

    async def expire(self, checkpointer: Any, *, now: datetime | None = None, batch_size: int = 200) -> int:
        cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=self.ttl_days)
        if self.connection is not None:
            cursor = await self.connection.execute(
                "SELECT thread_id FROM opsbridge_agent_memory_activity "
                "WHERE last_activity_at < %s ORDER BY last_activity_at LIMIT %s",
                (cutoff, batch_size),
            )
            thread_ids = [row["thread_id"] for row in await cursor.fetchall()]
        else:
            thread_ids = [
                thread_id for thread_id, last_activity in sorted(
                    self._memory_activity.items(), key=lambda item: item[1]
                ) if last_activity < cutoff
            ][:batch_size]

        for thread_id in thread_ids:
            # LangGraph's deletion removes checkpoints, blobs and pending writes.
            await checkpointer.adelete_thread(thread_id)
            await self.forget_if_stale(thread_id, cutoff)
        return len(thread_ids)

    async def forget_if_stale(self, thread_id: str, cutoff: datetime) -> None:
        if self.connection is not None:
            # The conditional delete preserves a concurrent touch after selection.
            await self.connection.execute(
                "DELETE FROM opsbridge_agent_memory_activity WHERE thread_id=%s AND last_activity_at < %s",
                (thread_id, cutoff),
            )
        else:
            last_activity = self._memory_activity.get(thread_id)
            if last_activity is not None and last_activity < cutoff:
                self._memory_activity.pop(thread_id, None)
