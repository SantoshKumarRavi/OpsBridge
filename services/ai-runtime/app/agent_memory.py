"""Small, stateful agent workflow with tenant- and actor-isolated threads."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph


SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,79}$")
MAX_STORED_MESSAGES = 40


def append_bounded(existing: list[dict[str, str]], update: list[dict[str, str]]) -> list[dict[str, str]]:
    """Keep the persisted thread bounded while preserving recent context."""
    return (existing + update)[-MAX_STORED_MESSAGES:]


class MemoryState(TypedDict, total=False):
    messages: Annotated[list[dict[str, str]], append_bounded]
    last_plan: list[Any]
    last_status: str
    last_tool_result: dict[str, Any] | None


def validate_session_id(value: str) -> str:
    if not SESSION_ID_PATTERN.fullmatch(value):
        raise ValueError("session_id must be 1-80 safe ASCII characters")
    return value


def scoped_thread_id(tenant_id: str, actor_id: str, session_id: str) -> str:
    """Hash identifiers so checkpointer metadata does not expose raw identities."""
    if not tenant_id or len(tenant_id) > 100 or not actor_id or len(actor_id) > 200:
        raise ValueError("valid tenant and actor context is required")
    validate_session_id(session_id)
    material = "\0".join((tenant_id, actor_id, session_id)).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


async def record_turn(state: MemoryState) -> dict[str, Any]:
    # This educational agent records a bounded, deterministic acknowledgment.
    # Read-only case lookup is handled by the allow-listed API adapter; write
    # actions remain disabled.
    tool_result = state.get("last_tool_result")
    if tool_result:
        reply = "Read-only tool result: " + json.dumps(tool_result, separators=(",", ":"))
    else:
        reply = "I recorded this request in the session. No external action was executed."
    return {"messages": [{"role": "assistant", "content": reply}]}


def build_memory_graph(checkpointer: Any):
    builder = StateGraph(MemoryState)
    builder.add_node("record_turn", record_turn)
    builder.add_edge(START, "record_turn")
    builder.add_edge("record_turn", END)
    return builder.compile(checkpointer=checkpointer)
