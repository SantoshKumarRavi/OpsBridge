# OpsBridge project decisions and status

Last consolidated: 2026-11-21. This is the durable index for project decisions made during planning and follow-up conversations. Use the linked detailed documents for implementation evidence and full inventories. Keep this page concise and update it when a project-level decision changes.

## Goal

Build one educational, interview-ready product that demonstrates technologies found across the supplied job-description checklist. Keep the product explainable and demonstrable end to end. Treat personal skill, production experience, and repository examples as separate kinds of evidence.

## Product and architecture decisions

- The product is **OpsBridge**, a tenant-aware worker onboarding and compliance-review workflow.
- The main story is: worker intake and synthetic document upload → validation and persistence → asynchronous extraction and advisory policy recommendation → human review → audited decision → durable event/integration path.
- PostgreSQL owns canonical cases, document metadata, audit history, decisions, and the transactional outbox. AI suggestions never make the final employment or compliance decision.
- Give each frontend or service a distinct responsibility. Keep alternate frameworks, databases, and messaging systems in isolated labs or adapters; do not create duplicate primary stores or duplicate services just to list technologies.
- The named skills index is represented broadly in code, configuration, or labs. A technology entry is not proof of production experience or personal mastery. See [the detailed checklist comparison](job-description-skill-gap.md).
- **NestJS is intentionally excluded** because the user already has NestJS work experience. Keep Express and Hono as the Node examples.
- Use synthetic data only. Do not enter real identity, financial, health, or customer information.

The service ownership and complete architecture are in [the final plan](final-plan.md); the concise skills comparison is in [the gap summary](job-description-gap-summary.md).

## Source repository decision

- Keep one canonical **public GitHub monorepo** named `opsbridge`. Shared packages, contracts, local Compose, tests, CI, and deployment references are coupled across the existing tree.
- Do not create a separate source repository per microservice, frontend, framework, or database. Hosting providers can create multiple deployment projects from subdirectories in the same monorepo.
- The repository was published to `https://github.com/SantoshKumarRavi/OpsBridge` on 2026-11-25 on the `main` branch. The initial commit is `d93110e`; `origin` tracks `main`. The branch is currently unprotected, and GitHub Actions checks were queued after the push.
- The repo `.gitignore` excludes `.env` and build/dependency output. Never commit real provider credentials or personal data; review `.env.example` before publication.
- GitHub Actions standard hosted runners are free for public repositories. Keep public CI limited to standard runners and do not place secrets in build output or logs.

Detailed hosting and free-tier assessment: [GitHub and deployment plan](deployment-plan.md).

## User preferences to preserve

- Prefer a zero-cost, education-focused demo. Identify any provider or cloud feature that can exceed a free allowance before recommending it.
- For deployment alternatives, preserve the interview code as the reference; do not change application source unless the user explicitly asks. State where configuration or a small code fix is unavoidable.
- The user prefers AI-assisted implementation and automated verification, with results recorded in the repo.
- When answering project-level architecture, checklist, GitHub, CI, testing, or deployment questions, update the relevant canonical document before wrapping up. Do not record casual unrelated chat.
- Keep job-specific application drafts in `docs/`, grounded in verified repo evidence, and clearly distinguish portfolio work from production experience.

## Current evidence snapshot

Verified locally in the current worktree:

- Flutter 3.50 formatting, analysis, two widget tests, and Android debug APK build.
- Spring synthetic-screening JUnit test (1 test); a GitHub Actions job is configured for it.
- Worker-to-reviewer browser flow: 6 Playwright tests passed in Chromium, Firefox, and WebKit using the no-Docker SQLite/eager-Celery/deterministic-AI harness.
- Other selected frontend, service, and infrastructure checks are recorded in [the verification checklist](job-description-checklist-status.md) and [detailed skill inventory](job-description-skill-gap.md).

Still unverified or constrained:

- The full Docker-backed PostgreSQL/RabbitMQ/Kafka/worker stack has not been run in this environment; Docker Desktop/Engine was not installed when checked.
- Cloud deployments have not been verified. The first GitHub Actions runs have completed but are not green; failures are recorded below. The `main` branch has no protection rules yet.
- iOS build/signing and device OIDC, external provider credentials, and AWS/GCP runtime deployment remain unverified.
- Some business-domain checklist topics are intentionally only synthetic examples or remain gaps; do not call them regulated or production capabilities.

The initial public push included source, configuration, tests, and documentation. Generated build/cache directories, local performance run output, Go binaries, Terraform provider caches/state, and `.env` files were excluded. The commit uses a GitHub-associated noreply author email.

## Conversation record

### 2026-11-20 — Free deployment and GitHub plan

- Recommended a single public `opsbridge` monorepo; deploy apps from subdirectories as separate hosting projects where needed.
- A zero-cost portfolio demo is feasible. A no-cost, reliable production deployment for the entire stateful microservice stack is not established.
- Candidate public static/Next hosts: Cloudflare Pages for static builds and Vercel Hobby for personal/non-commercial Next.js demos. Supabase free Postgres and Render free services have limits that make them unsuitable for durable production data or the full worker stack.
- AWS Free Plan is temporary; GCP Cloud Run and Azure Container Apps have limited compute/request grants and separate billable dependencies. OCI Always Free is the closest single-VM candidate for a low-traffic Compose demo, subject to its CPU/RAM capacity, region availability, idle-reclamation rules, and security hardening.
- Current Compose settings are for development and must not be exposed publicly as-is. The Angular compliance console hardcodes `localhost` for its API and cannot work from an external browser without a source change or an unapproved workaround; deployment that preserves source code must omit that remote screen or keep it local.
- See [the detailed deployment plan](deployment-plan.md) for current official free-tier references, component mapping, and safe rollout order.

### 2026-11-21 — CI/CD and hosting clarification

- Keep one GitHub monorepo and create separate deployment projects/services per app root; this does not duplicate source or cause projects to overwrite one another.
- Baseline: GitHub Actions runs CI checks on pull requests and pushes; protect `main` with passing checks; Vercel Git integration deploys frontend previews and production from the configured branch.
- Cloudflare Pages is optional alternative static hosting with Git-triggered deploys and previews. It is not needed for CI/CD if Vercel is already used for the frontend demos.
- Render can deploy a backend service from the same monorepo with root/path filters, but the free tier is not a durable always-on backend for the full stack. Continue local Compose for full workflow verification; consider OCI only as a constrained, conditional single-VM demo.
- No hosting accounts, provider projects, source changes, GitHub remotes, or deployments were created. See [the detailed CI/CD and deployment guidance](deployment-plan.md#cicd-choice-one-monorepo-separate-deploy-targets).

### 2026-11-21 — Cloud and middleware placement

- Do not deploy every technology to each cloud. AWS is the full ECS/Fargate architecture/IaC reference; it is not selected for actual deployment under the strict $0 target. Its Terraform expects external private RabbitMQ, Redis/Valkey, and Kafka endpoints in addition to paid AWS infrastructure.
- GCP and Azure are focused Go telemetry portability labs (Cloud Run and Container Apps respectively). They do not currently deploy the business API, PostgreSQL, Kafka, RabbitMQ, or Redis. GKE is an optional billable GCP lab.
- Run the end-to-end middleware stack in local Compose: PostgreSQL/pgvector is canonical state; RabbitMQ/Celery handles background work; Kafka carries outbox domain events/projections; Redis handles transient state and rate-limit support. SQS/SNS are AWS adapter examples, not drop-in replacements.
- Vercel hosts frontend demos; Render can host only a limited optional backend experiment. For now the complete backend remains local. A restricted OCI VM is a future conditional public full-stack option, not deployed.
- See the detailed [cloud and middleware placement map](deployment-plan.md#cloud-by-cloud-deployment-map), including free-tier boundaries and staged rollout. No cloud resources were provisioned in this discussion.

### 2026-11-25 — First hosted CI results

- [`Security analysis`](https://github.com/SantoshKumarRavi/OpsBridge/actions/runs/45648700131) failed: Gitleaks flagged a `curl -u` localhost Grafana check (`curl-auth-user`), and CodeQL initialization failed because the configured `autobuild` mode is unsupported for JavaScript/TypeScript. Trivy source/IaC and container image scan jobs succeeded. The Gitleaks finding still needs review; do not treat it as resolved just because it is a local test URL.
- [`Integration E2E`](https://github.com/SantoshKumarRavi/OpsBridge/actions/runs/45648699979) completed with failures in `rag-retrieval-evaluation`, `spring-cloud-discovery-e2e`, `gateway-compliance-contract-e2e`, `architecture-labs-unit-tests`, `worker-onboarding`, and `compliance-console-voice-policy`. Other jobs in the workflow passed. The failures have not been diagnosed in this publishing task.
- The repository push succeeded despite failed CI jobs. CI must be triaged before describing the hosted workflows as passing. No application tests were run manually for the push task.

### 2026-11-21 — Senior AI Agent Engineer application draft

- Added a tailored answer set for the Screenloop application in [the application draft](job-application-sr-ai-agent-engineer.md), linked from README.
- Answers describe OpsBridge as portfolio work, state that no agent framework has been operated in production, describe the bounded LangGraph path rather than claiming an autonomous planning loop, and flag which evaluation/hosted checks remain unverified.
- Personal information, compensation, years of work experience, join date, recent-work selection, consent, and public GitHub URL must be supplied or confirmed by the user. The repo currently has no public remote.
