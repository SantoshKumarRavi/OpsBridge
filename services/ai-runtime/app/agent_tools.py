"""Allow-listed, tenant-scoped read-only tools available to the agent."""
from __future__ import annotations

import os
import re
from typing import Any

import httpx
from fastapi import HTTPException


CASE_ID_PATTERN = re.compile(r"^[0-9a-fA-F-]{36}$")
TOOL_NAMES = frozenset({"get_case_summary"})


async def execute_tool(
    tool_name: str,
    arguments: dict[str, Any],
    *,
    tenant_id: str,
    actor_id: str,
    correlation_id: str = "",
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    """Run exactly one known tool; never accept caller-supplied URLs or methods."""
    if tool_name not in TOOL_NAMES:
        raise HTTPException(400, "Tool is not allow-listed.")
    if set(arguments) != {"case_id"} or not isinstance(arguments.get("case_id"), str):
        raise HTTPException(422, "get_case_summary requires only a case_id argument.")
    case_id = arguments["case_id"]
    if not CASE_ID_PATTERN.fullmatch(case_id):
        raise HTTPException(422, "case_id must be a UUID.")
    if not tenant_id or len(tenant_id) > 100 or not actor_id or len(actor_id) > 200:
        raise HTTPException(400, "Valid tenant and actor context is required.")

    base_url = os.getenv("COMPLIANCE_API_BASE_URL", "http://localhost:8001").rstrip("/")
    headers = {
        "X-Tenant-Id": tenant_id,
        "X-Actor-Id": actor_id,
        "X-Correlation-Id": correlation_id[:100],
    }
    token = os.getenv("INTERNAL_SERVICE_TOKEN", "")
    if token:
        headers["X-Internal-Service-Token"] = token
    try:
        async with httpx.AsyncClient(transport=transport, timeout=5.0) as client:
            response = await client.get(f"{base_url}/api/v1/cases/{case_id}", headers=headers)
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Case lookup tool is temporarily unavailable.") from exc
    if response.status_code == 404:
        raise HTTPException(404, "Case not found in this tenant.")
    if response.status_code in {401, 403}:
        raise HTTPException(503, "Case lookup service rejected the trusted context.")
    if response.status_code >= 500:
        raise HTTPException(503, "Case lookup tool is temporarily unavailable.")
    if response.status_code != 200:
        raise HTTPException(502, "Case lookup tool returned an unexpected response.")

    row = response.json()
    # Minimize returned/persisted data; omit name, email, phone, documents and audit details.
    return {
        "case_id": row.get("id"),
        "status": row.get("status"),
        "role": row.get("role"),
        "country": row.get("country"),
        "version": row.get("version"),
    }
