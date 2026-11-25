# OpsBridge threat model (portfolio draft)

**Scope:** local and learning-cloud onboarding workflow. This draft is a design aid, not a security assessment or production approval. Data should be synthetic. Review it again whenever trust boundaries, identity, storage, or provider integrations change.

## Assets and trust boundaries

- Tenant-owned worker profile, case status, document metadata, audit history, and provider configuration.
- Uploaded identity/work-eligibility documents, which are sensitive even in a synthetic demo.
- OIDC access/refresh tokens, service credentials, webhook secrets, and cloud IAM identities.
- Public browser/mobile clients cross into the Express gateway. The gateway authenticates users and relays to internal services. Django/PostgreSQL own business records. Celery, Kafka, Redis and external providers are separate failure and trust boundaries.
- Provider callbacks cross from the public Internet through Hono; the gateway's one-use WebSocket ticket crosses from the browser to the realtime service.

## Main abuse cases and controls

| Threat | Current control/evidence | Remaining work |
|---|---|---|
| Cross-tenant case access | Gateway verifies JWT tenant claim; case queries include tenant; internal services use trusted headers; development header identity is disabled in production | Add adversarial cross-tenant API tests and review every service route/data export |
| Shared-cache tenant data leak | Express applies `Cache-Control: private, no-store` to `/api/`; real HTTP contract checks assert it on tenant case responses, conflicts, and tenant-isolation misses | Verify policy at the production CDN/reverse proxy and on every separately exposed service |
| Forged/expired/replayed auth | OIDC issuer/audience/JWKS checks; short access-token expiry is provider-configured; realtime tickets have short expiry, audience/issuer and one-use JTI | Bearer tokens can be replayed until expiry; add key rotation/session revocation review and production IdP configuration review |
| Unauthorized state changes | Role checks on sensitive gateway routes; Django decision requires a reason and writes audit/outbox rows | Review direct internal-service reachability and role-to-action policy end to end |
| Malicious/oversized upload | Gateway file-type and 15 MB limits; Django repeats content-type/size checks; content is not logged | Add malware scanning, MIME sniffing/content disarm, private object retention/expiry, and hostile-file tests |
| Forged/replayed provider webhook | Hono requires Stripe/Twilio verification secrets and validates signatures; generic callbacks require a shared secret; events carry provider ID | Add signature/replay tests for every provider; protect callback ingress with rate limits and strict event allow-lists |
| Secret leakage | Provider credentials stay server-side; `.env` is ignored; secure mobile token storage; Gitleaks scans repository history and Trivy scans current source for secrets in CI | Rotate all live credentials, review hosted scan findings, document access/retention, and verify crash/log redaction |
| LLM prompt injection or unsafe decision | Advisory-only model, tenant-filtered retrieval, structured schemas, human decision gate; MCP tools are read-only | Add malicious-document and retrieval-isolation evaluations; review provider retention/data-processing terms |
| Queue duplicate, poison message, or loss | Transactional outbox, retries; consumer deduplicates by event ID and sends invalid events to a DLQ before offset commit | Add replay/redrive controls, retention/alerting, schema compatibility and recovery tests |
| WebSocket ticket exposure | Ticket is one-use/short-lived and sent in the first message, not URL; allow-listed origin and tenant-specific Redis channel | Add connection limits, auth-failure metrics, proxy timeout policy and browser reconnection tests |
| Dependency/image compromise | GitHub CodeQL v4, dependency review, Trivy filesystem/IaC scanning, Trivy scans for nine application container images, per-image CycloneDX SBOM artifacts, and signed SBOM provenance on public repositories are configured | Hosted scan results have not been reviewed; container image attestations, pin action/base-image digests and documented vulnerability triage remain |

## Production prerequisites

Before handling real users or regulated documents, perform an independent security/privacy review; threat-model deployment networking; enforce private encrypted storage, retention/deletion and backups; configure MFA and strong session policy; test authorization and upload controls; apply least-privilege service/cloud identities; set trace/log redaction and audit retention; configure incident response and restore drills; review data residency/legal terms for AI and providers; and verify the production deployment against organization policy. None of those checks has been executed by this repository inventory.
