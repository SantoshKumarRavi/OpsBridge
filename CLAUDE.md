# OpsBridge project instructions

OpsBridge is a synthetic-data portfolio project for workforce onboarding and compliance review. Keep PostgreSQL as the canonical business store and keep model output advisory; a human records the final decision.

## Repository map

- `apps/` contains separate web and mobile product surfaces.
- `services/` contains the API gateway, Django case service, Python AI/realtime services, Java integrations, Go telemetry, and isolated technology labs.
- `packages/contracts/` contains API and event contracts.
- `infra/` contains local Compose, cloud/IaC examples, and observability configuration.
- `docs/` records architecture, skill gaps, setup, deployment decisions, and interview explanations.

## Durable planning record

- Start project-level planning/repository/hosting questions from `docs/project-decisions.md`.
- Use `docs/final-plan.md` for architecture, `docs/job-description-skill-gap.md` for checklist evidence, and `docs/deployment-plan.md` for GitHub, hosting choices, and free-tier constraints.
- When a project-level question is answered or a decision changes, update the canonical doc and add a concise dated note to `docs/project-decisions.md` before finishing. Update README links when adding a canonical document. Do not record unrelated small talk.
- Preserve the user's preferences: NestJS excluded, one non-duplicated monorepo, free/zero-cost-first deployment, AI-assisted work and automated verification, synthetic data only. When the user asks to preserve app code for hosting, report blockers instead of silently changing it.

## Working rules

- Use synthetic records and documents only. Never read or expose `.env` credentials, tokens, or real customer data.
- Preserve tenant boundaries, audit events, validation, and human review when changing onboarding flows.
- Make one vertical change at a time. Update the contract and relevant docs when an API or event changes.
- Before reporting a change as verified, run the narrowest relevant check and report its exact result. For all web frontends, run `npm ci` followed by `npm run build:frontends`.
- The project Claude Code `PostToolUse` hook checks edited or written JSON files and returns parse errors as agent feedback. It validates syntax only; run the owning service's checks for schema or behavior validation.
- Claude Code auto-memory is local to the developer's Claude Code installation. Use `/memory` in a directly launched Claude Code session to inspect or enable it; do not commit machine-local memory as project configuration.
- Do not claim an integration, cloud deployment, or test suite is production-ready when only source/configuration exists.
- Do not deploy infrastructure or call real providers as part of an ordinary code change. Only do so when the user explicitly requests it; keep provider actions behind sandbox credentials and explicit user-triggered paths.

## Useful commands

- Install JS dependencies: `npm ci`
- Build six web frontends: `npm run build:frontends`
- Run browser E2E when Docker is available: `npm run test:e2e`
- Start local services when Docker is available: `docker compose -f infra/docker-compose.yml up --build`
