# OpsBridge

Agentic enterprise operations platform. The first end-to-end business workflow is frontline worker onboarding: intake, document processing, policy checks, human review, communications, and an auditable outcome.

This repository is intentionally a broad learning and portfolio system. Each framework owns a distinct product surface or service; the stack focuses on technologies that expand beyond the owner's existing professional experience.

## Repository map

- `apps/`: React operations dashboard, Next.js worker portal and public careers site, Angular compliance console, Vue integration console, Expo field app, Flutter analytics microfrontend, React frontend patterns lab.
- `services/`: Express API gateway, Strawberry GraphQL BFF, Hono webhook ingress, FastAPI AI and realtime services, Django compliance API and Celery workers, Spring Boot integrations, Go telemetry, plus isolated MuleSoft, Spring, agent-framework, and Kafka consumer labs.
- `packages/contracts/`: OpenAPI, event schemas, shared types.
- `tests/`: Playwright end-to-end workflow, Postman API collection, and k6/Locust/JMeter load examples.
- `infra/`: Docker Compose, Terraform AWS baseline plus opt-in EC2/EKS/Route 53 examples, AWS CDK serverless/ETL/CDN labs, GCP Cloud Build and Azure Bicep examples, Kubernetes, and observability.
- `docs/`: architecture, local setup, integrations, privacy and demo playbooks.

The consolidated product, ownership, rollout, and interview plan is in [`docs/final-plan.md`](docs/final-plan.md).
The cross-conversation decisions and current project status are recorded in [`docs/project-decisions.md`](docs/project-decisions.md).
The GitHub repository strategy and zero-cost deployment assessment are in [`docs/deployment-plan.md`](docs/deployment-plan.md).
The item-by-item comparison against the supplied job-description skills checklist is in [`docs/job-description-skill-gap.md`](docs/job-description-skill-gap.md).
The short present/partial/missing comparison is in [`docs/job-description-skill-comparison.md`](docs/job-description-skill-comparison.md).
The test automation setup and AI-assisted test workflow are described in [`tests/README.md`](tests/README.md).
The separate interview and CS practice tracker is in [`docs/interview-prep-map.md`](docs/interview-prep-map.md).
The tailored, evidence-based draft answers for the Screenloop Senior AI Agent Engineer application are in [`docs/job-application-sr-ai-agent-engineer.md`](docs/job-application-sr-ai-agent-engineer.md); personal details and claims should be reviewed before submission.
Standalone Python DSA reference implementations and tests are in [`practice/dsa/README.md`](practice/dsa/README.md); they are study material, not evidence of unaided interview skill.
The portfolio threat model and open production-security work is in [`docs/security-threat-model.md`](docs/security-threat-model.md).
The local Prometheus/Alertmanager/Mailpit setup and notification smoke check are in [`docs/observability-runbook.md`](docs/observability-runbook.md).
The GitHub Actions, Jenkins, GitLab CI, and Bitbucket Pipelines examples use one shared frontend build command; setup notes are in [`docs/ci-cd-labs.md`](docs/ci-cd-labs.md).
AI coding assistant guidance and read-only review agents are configured for Claude Code and GitHub Copilot. See [`CLAUDE.md`](CLAUDE.md), [`.claude/skills/opsbridge-vertical-slice/SKILL.md`](.claude/skills/opsbridge-vertical-slice/SKILL.md), [`.claude/agents/opsbridge-reviewer.md`](.claude/agents/opsbridge-reviewer.md), and [`.github/copilot-instructions.md`](.github/copilot-instructions.md).

The isolated [durable Saga lab](services/saga-lab/README.md) demonstrates idempotent onboarding steps, reverse-order compensation, restart recovery, and compensation retry using Python and SQLite.

The [CQRS lab](services/cqrs-lab/README.md) separates command and query stores, projects an event log asynchronously, enforces tenant-scoped reads, and rebuilds the read model from events.

The [Spring Cloud discovery lab](services/spring-cloud-discovery-lab/README.md) uses Eureka, Spring Cloud Config, and LoadBalancer to discover and call two synthetic provider instances.

## Local development

Copy `.env.example` to `.env`, provide any desired provider credentials, then use Docker Compose. Provider integrations are disabled or use sandbox mode by default. External services such as Stripe, WhatsApp, email, S3, and LLMs require credentials to perform live operations. See `docs/development.md`.

Run `npm ci` and `npm run build:frontends` to build all six web frontends locally.

Local browser and mobile authentication uses the imported Keycloak OIDC realm when the `identity` Compose profile is enabled. A gateway demo-identity fallback is available only for local development and must not be used as production authentication. Identity is centralized through OIDC/JWT rather than duplicated across applications.

## Key workflows

1. Worker submits profile and documents in `apps/worker-portal`.
2. Express gateway routes requests to the compliance and AI services.
3. Django persists the tenant-scoped case and schedules asynchronous processing with Celery.
4. FastAPI extracts structured fields, retrieves policy guidance, and produces an explainable recommendation; deterministic policy rules and a human reviewer decide the outcome.
5. Kafka domain events update operational views and telemetry. RabbitMQ handles retryable document jobs. Hono validates and records external webhooks.
6. Spring Boot owns external integration adapters including Stripe billing, messaging, storage, and CRM/HRIS clients.

## Important

This is portfolio software. Use synthetic data. Configure each provider with its sandbox credentials before use. The implementation includes secure-by-default patterns, but real production deployment still requires organization-specific security review, secrets, identity, data retention, and legal approvals.
