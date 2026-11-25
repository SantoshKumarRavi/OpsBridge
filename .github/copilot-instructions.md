# OpsBridge repository instructions for GitHub Copilot

OpsBridge is a synthetic-data portfolio project for workforce onboarding and compliance review. Read `README.md`, `AGENTS.md`, `docs/project-decisions.md`, `docs/architecture.md`, and the relevant service/UI files before changing behavior.

## Durable project decisions

- Keep project-level architecture, checklist, GitHub, and deployment answers in the repo. Update the relevant canonical document before finishing; add a concise dated entry to `docs/project-decisions.md` for material decisions/status changes.
- `docs/final-plan.md` is the architecture plan; `docs/job-description-skill-gap.md` is the detailed checklist evidence; `docs/deployment-plan.md` records repository and hosting decisions.
- Preserve user preferences: exclude NestJS, keep one non-duplicated monorepo, prefer zero-cost deployment, preserve application source when asked, use AI-assisted automated verification, and use synthetic data only.

## Architecture rules

- Django/PostgreSQL owns onboarding cases, documents' metadata, human decisions, audit events, and the transactional outbox. Do not add another source of truth.
- Preserve tenant scoping from the authenticated gateway through every backend query and event consumer.
- AI extraction and recommendations are advisory. A human reviewer owns final approval, rejection, or request for changes.
- Keep UI applications and provider/database adapters in their bounded product surfaces or isolated labs; don't combine unrelated stacks into one service.
- Use synthetic data only. Never read, output, or commit `.env` values, tokens, private keys, or real customer documents.

## Change and verification workflow

- Make a vertical change with clear acceptance criteria. Update OpenAPI/event contracts and docs when an external behavior changes.
- Add or update focused automated coverage for changed behavior. Do not report a check as passing unless it was run.
- For all web frontends, run `npm ci` and `npm run build:frontends`; the Angular build requires Node 22.22.3 or later in this workspace.
- Run Playwright E2E only when Docker and the local services are available. Provider integrations require sandbox credentials and explicit user-triggered actions.
- Do not deploy infrastructure, apply Terraform, or call live external providers as part of a code change.
- Only deploy infrastructure or use live providers when the user explicitly requests it. For hosting recommendations, disclose current free-tier limits, cost exposure, and what is not verified.
- Review diffs for tenant leakage, authentication/authorization gaps, credential exposure, validation omissions, and unrelated edits.

## Report

Summarize changed behavior, files, checks with exact results, remaining risks, and unverified work. Distinguish source/configuration from a completed and deployed integration.
