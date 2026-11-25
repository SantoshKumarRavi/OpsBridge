# Test automation labs

Use synthetic data and an isolated local environment. Some checks have been run locally; the sections below distinguish those results from suites that still need the full stack. Inspect failures and record evidence before making deployment claims.

## Integration service and Vodex

Run `gradle test` in `services/integration-service` with Java 21 to execute the Spring integration service tests. GitHub Actions runs this job on pushes and pull requests. Four Vodex client tests use Spring's mock HTTP server to verify the call-trigger path, required provider headers and explicit consent, transcript retrieval, and fail-closed behavior when credentials are missing; no real call or provider credentials are used. For a local JDK that differs from Java 21, `-PjavaToolchainVersion=<installed-version>` can override the build toolchain for a compatibility smoke test. Such an override does not replace the Java 21 CI build.

## Spring Data synthetic screening lab

Run `mvn -f services/spring-data-lab/pom.xml test` with Java 21. The current unit test checks that a synthetic sanctions flag remains advisory and routes the case to manual review; it does not exercise Spring HTTP endpoints, persistence, or real screening providers. GitHub Actions runs this test on pushes and pull requests. See the lab README for its safety and scope limits.

## Security scanning (GitHub Actions)

The `Security analysis` workflow runs CodeQL v4, dependency review, Gitleaks across repository history, Trivy filesystem vulnerability/IaC/secret scans, and Trivy image scans for nine application services. Each image job generates a CycloneDX SBOM, uploads it with 30-day retention, and creates a signed provenance attestation for the SBOM when the repository is public. GitHub artifact attestations are not available for private repositories on Free/Pro/Team plans. Trivy SARIF reports are uploaded to GitHub code scanning; the scan steps report findings without failing solely on vulnerability severity so the results can be triaged. These hosted scans and SBOM/attestation jobs are configured but have not yet been executed in this environment. The image builds require a GitHub-hosted runner with Docker.

## Browser workflow (Playwright)

The Playwright test drives the real worker portal, Express gateway, Django case service, PostgreSQL, Celery worker and upload endpoint in Chromium, Firefox and WebKit. Start the local backend first, then run `npm install`, `npx playwright install chromium firefox webkit`, and `npm run test:e2e`. The GitHub Actions workflow starts the required backend services and runs this test automatically on pull requests and pushes. The test creates a synthetic case and uploads a synthetic text file, waits for the mock AI fallback to route it to human review, and verifies correlation IDs across the upload and worker audit events. It does not approve or reject anyone.

## Accessibility scan (axe-core + Playwright)

`npx playwright test tests/e2e/accessibility.spec.ts --project=chromium` scans the worker intake page for automated WCAG 2.1 A/AA violations. Install the matching Playwright browser first with `npx playwright install chromium`. The scan passes locally in Chromium, Firefox, and WebKit; it does not replace screen-reader or manual accessibility review.

The worker portal also has a browser-only keyboard navigation contract. Run both checks across all configured browser projects with `npx playwright test tests/e2e/worker-keyboard-navigation.spec.ts tests/e2e/accessibility.spec.ts`. The keyboard test mocks case creation at the HTTP boundary, so it does not require the gateway or database; it verifies focus order, native select keyboard use, Enter submission, and transition to document upload.

## Frontend bundle analysis (Next.js)

Run `npm run analyze:frontends` to generate Next.js 16's experimental Turbopack bundle reports for the worker portal and careers site. The static reports are written to `apps/worker-portal/.next/diagnostics/analyze/` and `apps/careers-site/.next/diagnostics/analyze/`. Open the interactive worker analyzer with `npm --workspace apps/worker-portal run analyze:interactive`; use `apps/careers-site` for the careers site. GitHub Actions runs the analyzer and uploads both hidden `.next` report trees as a 14-day artifact. These reports support route/module inspection; the project does not yet enforce bundle-size budgets or test low-end device performance. See the [Next.js package bundling guide](https://nextjs.org/docs/app/guides/package-bundling).

Run `npm run test:e2e:typecheck` to type-check the Playwright specs, including the worker upload fixture.

## Compliance API integration tests (Django REST Framework)

Run `npm run test:compliance-api` for the integration suite or `npm run test:compliance-api:coverage` to run it with branch coverage. The coverage command prints a per-module line/branch report and writes `services/compliance-api/htmlcov/`; CI uploads that HTML report as an artifact. Coverage excludes migrations and test code and currently measures the `onboarding` app. The test settings use an in-memory SQLite database and temporary media storage; external task dispatch and Kafka/realtime clients are mocked. The suite validates the OpenAPI 3.1 document and checks real response bodies against its schemas while covering trusted production gateway tokens, tenant-scoped reads, signed cursor pagination and stable ordering, invalid/tampered cursor rejection, case validation and transactional audit/outbox creation, Kafka delivery confirmation and failure handling, duplicate outbox dispatch, best-effort realtime publication, text and mocked PDF/OCR extraction, unreadable/empty document human-review fallback, AI recommendation state handling, pending-event selection, Celery retry handoff on AI/Kafka errors, correlation propagation, final-decision conflicts, upload type checks, and queued document audit/outbox behavior. The mocked OCR tests validate task routing logic, not native Tesseract accuracy or the production document-processing stack. Retry tests validate Celery's retry handoff, not broker scheduling or backoff timing. The SQLite suite does not replace PostgreSQL-backed workflow E2E.

Install the test dependencies with `python -m pip install -r services/compliance-api/requirements-test.txt`, `npm ci --prefix services/api-gateway`, and `npm ci --workspace apps/worker-portal --include-workspace-root`. The test requirements include Celery's Redis extra because Django initializes the configured Redis result backend when upload tasks are queued, even when the task executes eagerly. Then run `npm run test:gateway-contract` to start the actual Express gateway and Django compliance API as separate local processes using a disposable SQLite database, and exercise case creation, paginated listing, detail, decisions, tenant isolation, `Cache-Control: private, no-store`, and OpenAPI response schemas over HTTP. This verifies the network relay without Docker; the gateway uses its local in-memory rate-limit fallback, so this command does not verify the Redis-backed store, Celery, PostgreSQL, or the full document-processing workflow. The Docker Compose browser workflow uses the Redis-backed gateway store. GitHub Actions runs these checks automatically.

Run `npx playwright install chromium firefox webkit`, then `npm run test:worker-contract-e2e:browsers` to exercise the backend-connected portal flow in all three browser engines without Docker. This local three-engine run passed. The command starts the disposable API stack and submits a worker case through the Next.js portal, Express gateway, and Django API; it uploads a synthetic document and verifies extraction, recommendation, human-review routing, tenant context, and correlation IDs. The runner serializes browser projects because they share one SQLite test database. For this no-Docker harness, Celery runs eagerly inside Django and the AI runtime is a deterministic HTTP stub. This exercises real application code and service boundaries, but does not verify RabbitMQ delivery, a separate worker process, PostgreSQL, or a live model. Use `npm run test:worker-contract-e2e` for the Chromium-only run. The Docker-backed Playwright suite remains the check for those runtime components.

## API exercise (Postman)

Import `postman/OpsBridge.postman_collection.json`, start the local stack, then run the requests in order. The collection uses the local demo tenant by default. For an OIDC setup, set `accessToken` and enable the Authorization headers. The file upload request reads the included synthetic fixture.

## Keycloak realm configuration

`npm run verify:keycloak-realm` validates the checked-in OpsBridge realm's TOTP policy, required first-login OTP enrollment, and public-client flow settings. GitHub Actions runs this structural check. It does not replace starting Keycloak and exercising OTP enrollment plus a repeat login in an authenticator app.

## Load/performance tools

- Run `python -m pip install -r tests/performance/requirements.txt`, then `npm run test:load:locust` for a bounded local load run. The harness starts the Express gateway and Django API with a temporary SQLite database, seeds 30 synthetic cases, runs 5 Locust users for 15 seconds, fails on request errors, and saves a final-summary JSON plus CSV files under `tests/performance/results/`. Override `LOAD_SEED_CASES`, `LOCUST_USERS`, `LOCUST_SPAWN_RATE`, and `LOCUST_RUN_TIME` to change the run. The checked-in run is a development baseline, not a PostgreSQL or production capacity result.
- Install k6 with the [official Grafana Windows instructions](https://grafana.com/docs/k6/latest/set-up/install-k6/), then run `npm run test:load:k6`. The harness uses the same disposable API and synthetic seed, runs 5 virtual users for 15 seconds, enforces the script's error and latency thresholds, and saves native k6 summary JSON, normalized baseline JSON, and a console log. Override `K6_BIN`, `LOAD_SEED_CASES`, `K6_VUS`, and `K6_DURATION` to configure the run. This remains a local SQLite baseline, not a PostgreSQL or production capacity result.
- Install Apache JMeter from the [official download page](https://jmeter.apache.org/download_jmeter.cgi) and Java 8+, set `JMETER_HOME` if it is not in the default local install directory, then run `npm run test:load:jmeter`. The harness runs the checked-in plan with 5 threads × 10 loops against the disposable API and saves JTL, logs, and a JSON summary. Override `JMETER_THREADS`, `JMETER_LOOPS`, and `LOAD_SEED_CASES`. This remains a local SQLite baseline, not a PostgreSQL or production capacity result.
- Locust: `locust -f tests/performance/locustfile.py --host http://localhost:8080/api/v1`; use only a disposable test environment. The harness command above provides the supported local setup.
- JMeter: open `tests/performance/cases-smoke.jmx`; host, port, tenant and optional Authorization value are JMeter properties. It sends only a small GET workload by default. The harness command above provides the supported local setup.

Performance thresholds are starting hypotheses, not an SLO. Measure a stable baseline, tune thresholds for the environment, and do not direct load tools at a public or shared service.

## AI-assisted test maintenance

When using Codex, ask it to read the acceptance criteria and current API contract, propose the smallest representative test first, then implement one workflow slice. Have it inspect the diff for test data privacy, tenant boundaries, retry/idempotency behavior and cleanup. Run the relevant test, share the failure output for a fix, then run the full gate at the end. AI-generated tests are evidence only after they actually execute and their assertions are reviewed.
