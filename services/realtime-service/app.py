"""Tenant-scoped WebSocket fanout using one-time gateway tickets and Redis Pub/Sub."""
import asyncio
import hmac
import json
import os
import re
from contextlib import asynccontextmanager
from datetime import timedelta

import jwt
import redis.asyncio as redis
from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/3")
TICKET_SECRET = os.getenv("REALTIME_TICKET_SECRET", "")
INTERNAL_TOKEN = os.getenv("INTERNAL_SERVICE_TOKEN", "")
ALLOWED_ORIGINS = set(os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(","))
TENANT_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,100}$")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = redis.from_url(REDIS_URL, decode_responses=True, health_check_interval=30)
    yield
    await app.state.redis.aclose()


app = FastAPI(title="OpsBridge Realtime", version="1.0.0", lifespan=lifespan)


class LiveCaseEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    eventId: str = Field(min_length=1, max_length=100)
    eventType: str = Field(min_length=1, max_length=100)
    caseId: str = Field(min_length=1, max_length=100)
    tenantId: str = Field(min_length=1, max_length=100)
    status: str | None = Field(default=None, max_length=32)
    occurredAt: str | None = Field(default=None, max_length=64)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "realtime-service", "transport": "websocket+redis-pubsub"}


@app.post("/v1/publish", status_code=202)
async def publish(event: LiveCaseEvent, x_tenant_id: str = Header(...), x_internal_service_token: str = Header(default="")):
    if not TENANT_PATTERN.fullmatch(x_tenant_id) or event.tenantId != x_tenant_id:
        raise HTTPException(403, "Event tenant does not match trusted service context.")
    if os.getenv("APP_ENV") == "production":
        if not INTERNAL_TOKEN or not hmac.compare_digest(x_internal_service_token, INTERNAL_TOKEN):
            raise HTTPException(401, "Trusted service context required.")
    channel = f"opsbridge:tenant:{x_tenant_id}:cases"
    subscribers = await app.state.redis.publish(channel, event.model_dump_json())
    return {"published": True, "subscribers": subscribers, "durable": False, "eventId": event.eventId}


@app.websocket("/ws/cases")
async def case_updates(websocket: WebSocket):
    origin = websocket.headers.get("origin")
    if origin and origin not in ALLOWED_ORIGINS:
        await websocket.close(code=4403, reason="Origin is not allow-listed")
        return
    await websocket.accept()
    try:
        auth_message = await asyncio.wait_for(websocket.receive_json(), timeout=5)
        token = str(auth_message.get("ticket", "")) if auth_message.get("type") == "authenticate" else ""
        if not token or not TICKET_SECRET:
            raise ValueError("realtime ticket required")
        claims = jwt.decode(token, TICKET_SECRET, algorithms=["HS256"], audience="opsbridge-realtime", issuer="opsbridge-api-gateway", options={"require": ["exp", "iss", "aud", "jti", "tenant_id", "sub"]})
        tenant_id = str(claims["tenant_id"])
        if not TENANT_PATTERN.fullmatch(tenant_id):
            raise ValueError("invalid tenant")
        claimed_jti = str(claims["jti"])
        if not await app.state.redis.set(f"opsbridge:realtime-ticket:{claimed_jti}", "used", ex=60, nx=True):
            raise ValueError("ticket already used")
    except Exception:
        await websocket.close(code=4401, reason="Realtime ticket is invalid or expired")
        return

    channel = f"opsbridge:tenant:{tenant_id}:cases"
    pubsub = app.state.redis.pubsub()
    try:
        await pubsub.subscribe(channel)
        await websocket.send_json({"type": "connected", "tenantId": tenant_id})
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=15)
            if message and message.get("type") == "message":
                await websocket.send_text(message["data"])
            else:
                await websocket.send_json({"type": "heartbeat"})
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
