# Allow-listed agent tools

The LangGraph agent can invoke one server-selected tool: `get_case_summary`. It is read-only and calls the compliance API's tenant-scoped case-detail endpoint. The client cannot provide a URL, HTTP method, header, or arbitrary tool name. The tool validates its exact argument shape and UUID, forwards tenant, actor, correlation, and internal-service context, and projects only case ID, status, role, country, and version into the response and memory. It omits names, email, phone, documents, and audit details.

The gateway authenticates the caller and supplies tenant/actor headers. The compliance API applies its own tenant filter, so a case belonging to another tenant returns not found. The AI runtime also requires the internal service token in production. Tool and HTTP response errors fail closed; the tool does not switch to a broader lookup.

The registered tool runs without approval because it cannot modify state. The agent endpoint still does not execute external write actions; `approved` does not enable a write tool. Adding a write tool requires a separate approval authority, audited idempotency, and a bounded adapter before it can be added to the registry.

Tests cover allow-list rejection, strict arguments, tenant/actor/correlation propagation, minimization of sensitive fields, upstream error mapping, and checkpointing the tool result. Local contract/API verification uses mocked HTTP; the complete AI-runtime-to-compliance-service call still needs Docker-backed verification.
