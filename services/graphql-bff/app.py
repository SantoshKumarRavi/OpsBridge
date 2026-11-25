"""Strawberry GraphQL BFF that composes the tenant-aware REST API."""
from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

import httpx
import strawberry
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from strawberry.fastapi import GraphQLRouter
from strawberry.types import Info

API = os.getenv("API_GATEWAY_URL", "http://localhost:8080/api/v1").rstrip("/")


@strawberry.type
class OnboardingCase:
    id: strawberry.ID
    worker_name: str
    email: str
    role: str
    country: str
    status: str
    version: int


@strawberry.type
class CasePage:
    items: list[OnboardingCase]
    total: int


def case_from_json(row: dict[str, Any]) -> OnboardingCase:
    return OnboardingCase(
        id=strawberry.ID(str(row["id"])),
        worker_name=str(row.get("worker_name", "")),
        email=str(row.get("email", "")),
        role=str(row.get("role", "")),
        country=str(row.get("country", "")),
        status=str(row.get("status", "unknown")),
        version=int(row.get("version", 0)),
    )


def request_headers(info: Info) -> dict[str, str]:
    """Forward user credentials; gateway remains the JWT/tenant authority."""
    request: Request = info.context["request"]
    authorization = request.headers.get("authorization")
    headers = {}
    if request.headers.get("x-correlation-id"):
        headers["X-Correlation-Id"] = request.headers["x-correlation-id"]
    # Development tenant header is accepted only when the gateway's local
    # development identity mode is enabled; production identity uses JWT.
    if request.headers.get("x-tenant-id"):
        headers["X-Tenant-Id"] = request.headers["x-tenant-id"]
    if authorization:
        headers["Authorization"] = authorization
    return headers


@strawberry.type
class Query:
    @strawberry.field
    async def cases(self, info: Info, status: str | None = None, first: int = 20) -> CasePage:
        if not 1 <= first <= 100:
            raise ValueError("first must be between 1 and 100")
        params: dict[str, str | int] = {"limit": first}
        if status:
            params["status"] = status
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(f"{API}/cases", headers=request_headers(info), params=params)
        response.raise_for_status()
        data = response.json()
        rows = [case_from_json(row) for row in data.get("items", [])[:first]]
        return CasePage(items=rows, total=int(data.get("total", len(rows))))

    @strawberry.field
    async def case(self, info: Info, case_id: strawberry.ID) -> OnboardingCase:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(f"{API}/cases/{quote(str(case_id), safe='')}", headers=request_headers(info))
        response.raise_for_status()
        return case_from_json(response.json())


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def create_case(
        self,
        info: Info,
        worker_name: str,
        email: str,
        role: str,
        country: str = "IN",
    ) -> OnboardingCase:
        payload = {"workerName": worker_name, "email": email, "role": role, "country": country}
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(f"{API}/cases", headers=request_headers(info), json=payload)
        response.raise_for_status()
        return case_from_json(response.json())


async def context_getter(request: Request) -> dict[str, Any]:
    return {"request": request}


schema = strawberry.Schema(query=Query, mutation=Mutation)
graphql_router = GraphQLRouter(schema, context_getter=context_getter, allow_queries_via_get=False)
app = FastAPI(title="OpsBridge GraphQL BFF", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:4301,http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-Tenant-Id", "X-Correlation-Id"],
)
app.include_router(graphql_router, prefix="/graphql")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "graphql-bff"}
