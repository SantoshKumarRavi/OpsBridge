# GitHub repository and deployment plan

Snapshot date: 2026-11-21. This is an education/portfolio hosting plan, not a production approval. Provider free tiers and policies change; the official links below were checked on the snapshot date.

## Recommendation

Use one public GitHub monorepo as the source of truth. Host static/front-end demos on free personal tiers, and keep the full service stack local or on one constrained Always Free VM for demonstrations. Do not describe this as a reliable production service: the repository's Compose stack is development-oriented, and free compute/data tiers do not provide a complete, backed-up, always-on platform for this architecture.

## GitHub repository plan

### Keep one repository

Publish this workspace as one public repository, for example `github.com/<username>/opsbridge`. Keep these together:

- `apps/`, `services/`, `packages/`, `policies/`
- `infra/`, `tests/`, `scripts/`, `.github/workflows/`
- `docs/`, interview material, and isolated technology labs

The API client and contracts are shared across multiple frontends and services. The end-to-end and security workflows also run across those boundaries. Splitting each service into a separate repository would make this portfolio harder to run and explain and would duplicate or fragment the shared contracts.

Create multiple **deployment projects** from the monorepo folders; that does not require multiple GitHub repositories. Vercel explicitly supports multiple projects connected to one monorepo and selecting a root directory per project: [Vercel monorepo guide](https://vercel.com/docs/monorepos).

### Initial publication checklist

At the time this plan was recorded, `git remote -v` returned no remote, `git log` showed no commit, all project files were untracked, and the current branch was `master`.

1. Review `.env.example` and scan the workspace for credentials. Keep the real `.env` out of Git; `.gitignore` already excludes `.env`.
2. Create a public GitHub repo named `opsbridge`; choose `main` as the default branch.
3. Make the initial commit from this workspace and add the GitHub repo as `origin`.
4. Push `main` and inspect the Actions tab. Public-repository standard GitHub-hosted Actions runners are free; larger runners are billed. See [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions).
5. Pin the repo README and demo/status docs. Do not add cloud/provider secrets to repository variables unless a specific workflow needs them; the current CI should default to mocks/synthetic data.

## What the current code can deploy without an app-source rewrite

| Surface | Candidate free host | Current constraint |
|---|---|---|
| Next.js worker portal | Vercel Hobby | Personal, non-commercial use only. `NEXT_PUBLIC_API_URL` and the Keycloak public URL must point to real public endpoints at build/runtime. The API must be deployed separately. [Hobby terms and quotas](https://vercel.com/docs/plans/hobby) |
| Next.js careers site | Vercel Hobby | Personal portfolio demo fits the plan; use a provider subdomain to avoid buying a custom domain. |
| React/Vite operations dashboard | Cloudflare Pages | Static build hosting is free within Pages limits. Set `VITE_API_URL`, `VITE_KEYCLOAK_URL`, CORS origin, and public WebSocket URL. [Pages limits](https://developers.cloudflare.com/pages/platform/limits/) |
| Vue/Vite integration console | Cloudflare Pages | Static build hosting is possible; API and OIDC environment configuration is still needed. Do not add provider secrets to browser variables. |
| Angular compliance console | Static host can serve built files, but remote API use is currently blocked | [main.ts](../apps/compliance-console/src/main.ts) hardcodes `http://localhost:8080/api/v1`; an external user's browser will call that user's own computer. Under the no-source-change constraint, leave this console local or omit it from the public demo. |
| Expo field app and Flutter analytics app | Free SDKs/build artifacts for study; host backend separately | These are clients, not server hosting. Their API/OIDC URLs must target the demo backend; store distribution and provider services can introduce costs. |
| PostgreSQL | Supabase Free for a small demo database | 500 MB per project, two free projects, 5 GB included egress; inactive free projects can pause after a week and backups are not included. Use synthetic, disposable demo data only. [Supabase billing](https://supabase.com/docs/guides/platform/billing-on-supabase), [pause policy](https://supabase.com/docs/guides/platform/free-project-pausing) |
| Render web services/Postgres | Render Free for isolated experiments | Services sleep after 15 idle minutes, the local filesystem is ephemeral, and free PostgreSQL expires after 30 days. Its own docs say Free instances are for testing/hobby use rather than production. [Render Free limits](https://render.com/docs/free) |

Cloudflare Pages currently lists 500 free builds/month and one concurrent build. Vercel Hobby currently lists free usage for personal projects, but its terms restrict Hobby use to personal/non-commercial use. Recruiter/interview demonstrations are the intended use here; do not use Hobby to host a paying client or commercial product.

## Full stack and cloud cost fit

The current [Compose file](../infra/docker-compose.yml) has a substantial base stack: PostgreSQL/pgvector, Redis, RabbitMQ, Kafka, Django API, Celery worker and beat, FastAPI AI and realtime services, Express gateway, GraphQL BFF, Spring integration service, Go telemetry, Hono webhooks, and OpenTelemetry Collector. Identity, frontends, observability, and data/messaging labs add more containers.

Compose currently starts app dev servers, sets `APP_ENV=development`/`DEV_IDENTITY_ENABLED=true` defaults, starts Keycloak with `start-dev`, uses local service URLs/secrets, and publishes many service ports. It is a local development/test topology. Do not expose these ports or the development identity path to the public Internet. A public host needs at minimum a restricted firewall, HTTPS/reverse proxy, production secrets and identity configuration, allowed public origins, persistent storage/backup decisions, and only the necessary public ingress.

| Cloud | Free facts checked | Fit for this repo |
|---|---|---|
| AWS | New Free Plan accounts get up to 6 months (or until eligible credits run out); some services/features are unavailable and the Free Plan ends. [AWS Free Tier terms](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier.html) | The existing ECS/Fargate Terraform plan also uses/load-balances services, RDS, Secrets Manager and externally managed Redis/RabbitMQ/Kafka. This is not a persistent $0 deployment. Keep AWS as an IaC learning lab; do not apply it for a strict-free demo. |
| GCP | Cloud Run has a monthly request-based free allowance; excess use in a paid billing account can be billed. Google Cloud requires a billing account for Free Tier. The separate $300 trial lasts 90 days and shuts resources down if not upgraded. [Cloud Run pricing](https://cloud.google.com/run/pricing), [billing requirement](https://docs.cloud.google.com/billing/docs), [trial behavior](https://cloud.google.com/signup-faqs) | Good for a small stateless service experiment. It does not supply free durable Postgres, RabbitMQ, Redis, Kafka, and an always-running Celery worker as one complete system. Network egress and non-free resources add risk. |
| Azure | Container Apps Consumption currently grants 180,000 vCPU-seconds, 360,000 GiB-seconds and 2 million requests per subscription/month; excess usage and supporting services can cost money. [Azure Container Apps billing](https://learn.microsoft.com/azure/container-apps/billing) | Possible for a small container experiment, not a complete no-bill deployment of this stateful stack. |
| OCI (Oracle Cloud) | Always Free A1 provides up to 2 OCPUs/12 GB RAM and 200 GB combined block storage. Idle instances can be reclaimed when all stated low CPU/network/memory conditions hold for seven days; regional capacity may be unavailable. [OCI Always Free limits](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm) | Closest zero-monthly-cost option for running a Docker-based demo on one VM without moving the app code. Treat this as a constrained single-node demo: 2 OCPUs, no high availability/SLA, limited capacity, security/configuration work required, and no guarantee the full profile runs acceptably. Use only resources labeled Always Free and confirm billing/resource limits before provisioning. |

The cloud free tiers are usage allowances, not a shared free managed platform for every component. A managed database, brokers, persistent file storage, background worker, and monitoring may each have separate allowances or charges.

## Cloud-by-cloud deployment map

The plan is **not** to deploy every container into every cloud. AWS is the main cloud architecture example; GCP and Azure are focused portability labs. No cloud resources have been created or applied. For the current $0 objective, the real multi-service path stays in local Compose. The public portfolio frontend can be on Vercel; a Render API is an optional sleeping/demo experiment, not the production backbone.

| Platform | What the repo targets | Network exposure and middleware | Current recommendation |
|---|---|---|---|
| **AWS main reference** | ECS/Fargate for gateway, Django API, AI, Spring integrations, Hono webhooks, Go telemetry, Celery worker/beat, realtime service, Kafka projection consumer; public HTTPS ALB; private RDS PostgreSQL and S3; CloudWatch, service discovery, IAM task roles, SQS/SNS examples | Only ALB API/WebSocket entry is public. ECS tasks and RDS are private. Existing Terraform expects externally supplied private RabbitMQ, Redis/Valkey, and Kafka endpoints/credentials; it does not provision these brokers. Main stack includes NAT/VPC endpoints and load-balanced/RDS resources, so not a $0 deployment. | Keep as architecture/IaC evidence and run mocked/local validation. Do not apply for the free-only demo. Optionally do a small, isolated AWS CDK serverless lab as a short educational exercise only after confirming account eligibility and a reviewed zero-cost plan; tear it down. |
| **GCP lab** | Cloud Build builds Go telemetry, Artifact Registry stores its image, Cloud Run deploys a private IAM-authenticated telemetry service. Separate optional Terraform lab shows GKE Autopilot + Secret Manager CSI + Workload Identity. | Not the OpsBridge API/data plane. No Kafka, RabbitMQ, Redis, or PostgreSQL deployment in this lab. Cloud Run can scale to zero; GKE is a separate billable exercise. | Cloud Run telemetry is the only candidate for a short live GCP service demo; monthly free allowance may cover low usage but billing account, build/storage/egress and overages need checking. Do not deploy the GKE lab for a strict $0 target. |
| **Azure lab** | ACR image + Container Apps app for Go telemetry, Log Analytics, system-assigned managed identity; Bicep template currently makes the telemetry endpoint externally reachable. | No OpsBridge API, DB, Kafka, Redis, RabbitMQ, or Service Bus in the current lab. Make access restrictions part of a future cloud exercise before using real data. | Optional short telemetry demo under Container Apps consumption grant. Grant is limited; logs, registry, networking and excess compute can add charges. Delete its resource group after the exercise. |
| **Vercel** | Next.js careers site and worker portal; optionally static frontend builds | Frontend only. Browser API/OIDC URLs must point at a reachable backend and be configured per project. | Use for portfolio UI previews/deploys, not the full backend or event stack. |
| **Render** | Optional one API/web service from its own monorepo root | No bundled Kafka/Redis/RabbitMQ/Postgres system. Free web service sleeps; filesystem is ephemeral; free DB expires. | Use only for a small backend connectivity experiment. Avoid relying on it for the end-to-end workflow or persistent records. |
| **OCI single VM** | Conditional Docker-based, restricted subset of Compose | Could colocate API + middleware in one host, but constrained CPU/RAM, security burden, idle reclamation, and single-node failure apply. | The closest cloud candidate for a public full-flow demo without changing the architecture, but not yet selected or provisioned. Validate resource fit and public hardening first. |

### Middleware and event-flow placement

| Component | Role in OpsBridge | Initial deployment location | Cloud mapping / cost decision |
|---|---|---|---|
| PostgreSQL + pgvector | Canonical cases, decisions, audit, outbox | Local Compose | AWS reference uses private RDS (paid); no cloud DB in GCP/Azure labs. Supabase is a separate small-demo option but does not deploy the whole application and may pause. |
| RabbitMQ | Celery work queue: document processing, retries, scheduled work | Local Compose | AWS ECS template expects a private externally managed RabbitMQ URL; no broker provisioned. Managed RabbitMQ is not part of the $0 plan. |
| Redis | Gateway rate-limit sharing, Celery result/task state, transient realtime Pub/Sub | Local Compose | AWS expects externally hosted Redis/Valkey endpoints. GCP Memorystore has no free tier. Keep local unless using a temporary self-hosted VM demo; never make Redis the source of truth. [Google Memorystore docs](https://docs.cloud.google.com/appengine/docs/standard/using-memorystore) |
| Kafka | Outbox domain-event stream, webhooks, optional idempotent projection consumer | Local Compose | AWS ECS template consumes an external private Kafka cluster; Amazon MSK has no free tier. A Confluent trial can support a time-boxed experiment, not ongoing $0 hosting. Keep the portfolio workflow on local Kafka unless a reviewed temporary trial is intentionally chosen. [Amazon MSK pricing](https://aws.amazon.com/msk/pricing/), [Confluent Kafka trial](https://docs.confluent.io/kafka/get-started.html) |
| SQS/SNS | AWS-native queue/topic adapter examples; optional cloud-specific messaging | Local mocks/examples; AWS CDK lab | Demonstrate AWS event patterns independently. They do not silently replace RabbitMQ or Kafka in the core flow; a code adapter and semantics/test coverage would be needed before swapping them. |
| S3 | Document object storage in AWS deployment reference | Local file storage in dev; S3 in AWS reference | Private bucket; scoped task role access to compliance API/Celery worker. Do not upload real identity documents. |
| OpenTelemetry/Prometheus/Grafana | Local traces, metrics, dashboard, alert exercises | Local Compose | Current cloud Terraform does not include the full observability backend; cloud logging is provider-specific (CloudWatch, Cloud Logging, Log Analytics). |

The event path stays deliberately split: PostgreSQL transaction writes the business change and outbox row; publisher sends the event to Kafka; the projection consumer handles duplicates idempotently. RabbitMQ/Celery is for retryable work, Kafka is for replayable domain events, and Redis carries transient coordination/status. A managed queue with a similar name is not automatically a drop-in substitute for either broker.

### If the core were moved to managed cloud services later

These are architectural equivalents to evaluate, **not current deployment choices**. They would require service-specific Terraform, credentials/network setup, pricing review, and in some cases application adapter/configuration changes:

| Need | AWS candidate | GCP candidate | Azure candidate | Why it is not in the first $0 deployment |
|---|---|---|---|---|
| Containerized services | ECS/Fargate (already represented) | Cloud Run for stateless request services; GKE for a broader cluster | Container Apps | Always-on workers, VPC networking, image storage, egress and supporting resources can exceed free grants. |
| PostgreSQL | RDS PostgreSQL (already represented) | Cloud SQL for PostgreSQL | Azure Database for PostgreSQL | Durable managed database is separately billed; current GCP/Azure labs do not provision it. |
| Documents | S3 (already represented) | Cloud Storage | Blob Storage | Fits cloud object storage, but storage/operations/egress and IAM still need setup. Synthetic data only. |
| Celery work queue | Amazon MQ RabbitMQ to preserve AMQP, or SQS only after using the existing AWS queue adapter deliberately | Pub/Sub would require an adapter; it is not RabbitMQ-compatible | Service Bus would require an adapter | A queue migration changes retry, acknowledgement, routing, and dead-letter semantics; avoid claiming equivalence without integration tests. |
| Kafka domain events | Amazon MSK | Managed Kafka vendor or a separately built Kafka cluster; Pub/Sub would need a new adapter | Managed Kafka vendor or a separately built Kafka cluster; Service Bus/Event Hubs requires a distinct adapter | MSK has no free tier and a managed Kafka cluster is out of the recurring $0 budget. Keep Kafka in local Compose for the complete event-driven demo. |
| Redis | ElastiCache/Valkey | Memorystore | Azure Managed Redis/cache offering | Managed cache is separately billed and only transient state; keep local Compose for now. |

Keep the public boundary narrow in any future AWS-style deployment: frontend and HTTPS API entry can be public; database, brokers, caches, workers, and internal service ports stay private. The existing AWS Terraform expresses this separation, but it still needs operator-provided broker endpoints, networking, and a real reviewed plan before an apply.

### Recommended staged exposure

1. **Complete end-to-end verification:** run the whole workflow locally through Compose, including Postgres, RabbitMQ/Celery, Kafka/outbox/consumer, Redis realtime/rate limit, and mock AI. This is the only $0 path in the current plan that exercises all boundaries together.
2. **Public portfolio UI:** deploy eligible frontend projects to Vercel. Explain that the full API/event backend is local until a safe public backend is set up; do not imply the deployed pages are a live workflow.
3. **Cloud interview evidence:** use AWS Terraform as the main deployment design and explain public ALB/private ECS/RDS/S3 plus the broker endpoints. Use GCP Cloud Run and Azure Container Apps only for the separate Go telemetry portability examples. These focused labs demonstrate build, identity, private service access, logs, and health checks without pretending the whole product has been ported.
4. **Temporary runtime exercise (optional):** if you later want a real hosted cloud check, choose one provider and one small, synthetic-data service, inspect the exact plan/free allowance, run it briefly, capture evidence, and delete resources. Do not deploy all three clouds or managed Kafka/Redis/RabbitMQ for a $0 goal.
5. **Public full-stack demo (conditional):** only if needed, assess a small OCI VM running a restricted Compose profile. This is separate from the Vercel frontend path and requires a security/resource review; it is not production-grade.

### Cost note for cloud-specific labs

Current AWS Free Plan eligibility is limited to new accounts and expires after six months or credit exhaustion; existing/legacy accounts have different terms. AWS MSK has no free tier. GCP Cloud Run has monthly free usage, while Memorystore for Redis has no free tier. Azure Container Apps has a monthly consumption grant, and usage beyond it is billable. None of these allowances jointly fund the full stack. Confirm the account plan and provider calculator before creating resources; for a strict no-payment requirement, stay with local Compose and static portfolio hosting. [AWS Free Tier](https://docs.aws.amazon.com/us_en/awsaccountbilling/latest/aboutv2/free-tier.html), [Cloud Run pricing](https://cloud.google.com/run/pricing), [Azure Container Apps pricing](https://azure.microsoft.com/en-us/pricing/details/container-apps/).

## CI/CD choice: one monorepo, separate deploy targets

**Recommended first setup:** keep one GitHub monorepo and use GitHub Actions for CI, with Vercel Git integration for the Next.js apps. Do not add Cloudflare Pages unless a static app benefits from a separate host. CI and CD are related but distinct: CI runs checks on commits/PRs; CD builds and publishes a deployment after the chosen branch is updated.

- **Vercel:** connect each supported frontend as its own Vercel project, all pointing to this same GitHub repository and each configured with its app's root directory/build settings. Vercel automatically makes preview deployments for branch/PR changes and production deployments from the selected production branch. Monorepo projects can skip unaffected builds when configured. Vercel is the simplest choice for the two Next.js apps; it does not replace GitHub Actions as the cross-repository test suite. [Git deployments](https://vercel.com/docs/git), [monorepos](https://vercel.com/docs/monorepos).
- **Cloudflare Pages:** this is an alternative Git-connected static frontend host, not a required CI service or a backend host for this architecture. It can automatically build/deploy from GitHub, create PR previews, and report status checks. Use it instead of Vercel for a static Vite build only if there is a concrete reason; using both adds provider setup without making the overall tests stronger. [Git integration](https://developers.cloudflare.com/pages/configuration/git-integration/).
- **Render:** it can connect a separate web service to the same monorepo, assign each service a root directory/build/start command, and filter auto-deploys to relevant paths. This avoids source-repository duplication or service collisions. However, its free web services sleep when idle and have ephemeral storage; free Postgres is temporary. It is suitable for an API experiment, not the complete always-on stack. Background workers/queues and durable data are the key free-tier blockers. [Monorepo support](https://render.com/docs/monorepo-support), [free limits](https://render.com/docs/free).
- **Full backend:** Vercel functions or Cloudflare Workers may run compatible stateless endpoints, but they are not drop-in hosts for this repo's Django/Celery, Spring, Go, Kafka/RabbitMQ, and persistent database topology. For the existing backend code, use local Compose for complete testing or the restricted OCI single-VM learning demo described below. Keep Render as an optional short-lived service experiment.

### CI gate and automatic release

Configure GitHub Actions to run relevant lint/typecheck/unit/build checks on pull requests and pushes. Require successful checks before merging to `main`; then the hosting provider's Git integration automatically deploys the merged app. This gives a simple, comprehensible CI→CD gate without relying on each provider to test the whole monorepo. Use path filters/matrices so a change to one app does not run unrelated expensive suites, while shared package changes run impacted suites.

Vercel also documents Deployment Checks that can hold production promotion until selected GitHub checks pass; that is a useful additional control if its setup fits the account, but branch protection plus GitHub Actions should be the baseline. [Vercel Deployment Checks](https://vercel.com/docs/deployment-checks). Cloudflare Git integration itself supplies build/deploy status checks. Render autodeploys can be limited by root directory/build filters. Avoid configuring two independent providers to deploy the same app on the same production branch.

### Suggested target mapping

| Target | Source | CI | CD | Initial decision |
|---|---|---|---|---|
| Next.js careers/worker portal | Same GitHub monorepo, one Vercel project per app root | GitHub Actions | Vercel Git integration; PR previews and `main` production | Use Vercel for eligible personal portfolio demos |
| React/Vite and Vue/Vite demos | Same monorepo, each app root | GitHub Actions | Vercel static projects for simplest single-provider setup; Cloudflare Pages is an equivalent optional alternative | Start on Vercel if supported by build settings; do not require Cloudflare |
| Django/API or other long-running service | Same monorepo, separate service root/config | GitHub Actions | Render can auto-deploy a small experiment; OCI VM/local Compose for the real multi-service flow | Keep complete backend local first; investigate OCI before public exposure |

Each deployment project/service has its own name, root directory, environment variables, and provider URL. Multiple projects from the same repository do not merge their files or overwrite one another. Shared package changes need explicit build inclusion/monorepo install settings and CI coverage; path filtering must not accidentally ignore shared dependencies.

## Deployment paths

### Path A — Zero cost, full local workflow (best first step)

Install Docker Desktop and run the existing local Compose/E2E environment. Docker Desktop is free for personal use and education under its current license terms. This uses the real service boundaries without paying for cloud brokers or databases. [Docker Desktop terms](https://docs.docker.com/desktop/setup/install/windows-install/)

For an interview, screen-share the local workflow. A Cloudflare Quick Tunnel can temporarily share one local HTTP origin; it provides a random `trycloudflare.com` hostname, has no uptime guarantee, and is documented for testing/development, not production. It can gate a visitor by email, but the current multi-frontend/API/OIDC setup still needs correct routing and public URL configuration, and the Angular hardcoded localhost API remains a blocker. [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)

### Path B — $0 public portfolio pages plus a private/local backend

1. Publish the monorepo on GitHub.
2. Deploy the careers site and selected frontend demos as separate Vercel projects from their app roots. Use Cloudflare Pages only as an optional alternative for static Vite projects; it is not needed to get automatic deploys or CI/CD.
3. Keep the complete worker-upload/review flow local until a remote backend has a safe public configuration. Do not claim a static page is a working full-stack deployment.

This path gives stable provider URLs without paying for a domain, but it does not make the private API or broker stack publicly available.

### Path C — OCI Always Free single-VM demo (closest public full-stack option)

If a public backend is required at exactly $0 recurring cost, try one OCI Always Free Ampere VM and run a carefully restricted subset of Compose. Use a reverse proxy and expose only HTTPS/HTTP ingress plus restricted SSH; block direct public access to PostgreSQL, Redis, RabbitMQ, Kafka, Keycloak admin, and internal service ports. Keep all data synthetic. Disable development identity and replace local secrets/URLs via environment/Compose deployment configuration before sharing it.

The VM is a single point of failure and low traffic could meet OCI's idle-reclamation criteria. Resource capacity may also require disabling optional labs and observability. This route is a learning/demo deployment, not production reliability. Do not create paid OCI resources or assume the trial credit is a recurring free tier.

## Cost policy

- Target **$0/month**. Use provider subdomains, mock LLM mode, sandbox payment/provider integrations, synthetic data, and public-repository standard GitHub runners.
- Do not activate AWS/GCP/Azure paid billing or upgrade an expiring trial merely to keep a demo alive. If using a cloud trial, treat it as a short lab and ensure it shuts down without charges.
- Do not add a custom domain, paid TLS/DNS add-on, always-on managed database, NAT gateway, managed Kafka/RabbitMQ/Redis, or provider API key without first disclosing its price and getting the user's explicit decision.
- Free-tier dashboards/alerts are not spending locks. Check active resources and billing after each cloud lab; delete trial resources when done.

## Decision status

- Selected: one public GitHub monorepo, free static/Next portfolio hosting, and local Compose for the first complete workflow demonstration.
- Conditional option: OCI Always Free single-node demo if a public API URL is needed and the resource, availability, security, and idle-reclamation limitations are acceptable.
- Not selected for $0 ongoing deployment: the current AWS ECS/RDS design, a full Render deployment, or a multi-service GCP/Azure deployment with managed data/brokers.
- Completed 2026-11-25: public GitHub repository created/populated with the initial code, tests, configuration, and documentation on `main`; `origin` tracks the repository. Generated build/cache output, local run reports, Go binaries, Terraform caches/state, and `.env` files were excluded.
- Not yet done: cloud account/resource creation, production-hardening configuration, hosted workflow verification, or public application deployment.

### 2026-11-21 — CI/CD and hosting clarification

- A single GitHub monorepo can feed independent Vercel projects, Cloudflare Pages projects, or Render services, each configured to build from an app/service directory. This is a normal monorepo deployment setup and does not require source repositories to be split.
- For the first iteration, prefer GitHub Actions for CI and Vercel Git integration for frontend CD. Vercel creates previews and deploys the configured production branch automatically. Protect `main` with passing Actions checks so CD follows tested changes.
- Cloudflare Pages is optional static hosting with its own Git-triggered builds/previews/status checks. It is not required alongside Vercel, and Pages does not host the current long-running multi-service backend as-is.
- Render can auto-deploy a backend service from the same monorepo and filter by root/path, but its free limits make it an experiment rather than a durable full-stack production host. Keep the full service flow in local Compose first; OCI remains the conditional public single-VM demo.
- No provider project, GitHub remote, workflow change, or deployment was created in this discussion. See the CI/CD choice section above for implementation order and boundaries.

### 2026-11-21 — Cloud and middleware placement

- Clarified that AWS is the full architecture/IaC reference, not a free deployment target: ECS/Fargate, ALB, RDS, S3, SQS/SNS examples, CloudWatch and service discovery are represented, while RabbitMQ, Redis/Valkey, and Kafka are external private endpoint inputs. Keep the AWS stack unapplied for the current $0 goal.
- GCP and Azure are separate Go telemetry portability labs only. GCP targets Artifact Registry + Cloud Build + private IAM Cloud Run; optional GKE/Secret Manager CSI is billable. Azure targets ACR + externally reachable Container Apps telemetry + managed identity/Log Analytics. Neither lab currently hosts the OpsBridge business API or middleware.
- Place canonical PostgreSQL, RabbitMQ/Celery, Kafka/outbox/consumer, and Redis locally in Compose for full end-to-end testing. Amazon MSK is not free; Google Memorystore has no free tier; managed Redis/RabbitMQ are not selected. SQS/SNS are AWS adapter examples, not automatic Kafka/RabbitMQ replacements.
- Recommended exposure: Vercel for frontend demos, local Compose for the complete backend/event flow, GCP/Azure telemetry only as short optional learning deployments, and a restricted OCI VM only as a conditional public full-stack experiment. No AWS/GCP/Azure resources were created or applied.
- For current eligibility and price limits, see the cloud-by-cloud map and its official sources in [the deployment plan](deployment-plan.md#cloud-by-cloud-deployment-map).

### 2026-11-25 — Initial repository publication

- Published the initial project snapshot to [GitHub](https://github.com/SantoshKumarRavi/OpsBridge) on `main`, commit `d93110e`.
- The public repository contains source, tests, infrastructure examples, and docs. `.env`, generated outputs, local test-run artifacts, and Terraform caches/state were excluded; Android Gradle wrapper files were included for reproducible builds.
- GitHub Actions `Security analysis` and `Integration E2E` ran and did not pass; see [the CI result notes](project-decisions.md#2026-11-25--first-hosted-ci-results). No cloud deployment was made.
