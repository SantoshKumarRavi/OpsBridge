# Local development

## Prerequisites

Install Docker Desktop with Compose v2, Node.js 22, Python 3.12, Java 21, and Go 1.23 for native editing. For the mobile app, install Flutter 3.50 or newer; Android APK builds also need an Android SDK and Java 17 or newer. Docker runs the services and their pinned local infrastructure. Create an `.env` file from `.env.example` when you want to configure external providers; Compose permits starting without it.

## Start the product

From the repository root:

```powershell
docker compose -f infra/docker-compose.yml up --build
```

## Verify the Go telemetry service

From the repository root, run the Go checks independently of Compose:

```powershell
Push-Location services/telemetry-service
go test ./...
go vet ./...
go build ./...
Pop-Location
```

On Linux or WSL with GCC installed, also run `go test -race ./...`. The handler tests cover trusted tenant context, malformed/oversized input, validation, metrics, and security headers. GitHub Actions runs the tests with race detection, `go vet`, and `go build` on pushes and pull requests.

## Verify the Flutter analytics app

From the repository root, run the Flutter analyzer and widget tests:

```powershell
Push-Location apps/flutter-analytics
flutter pub get
dart format --set-exit-if-changed lib test
flutter analyze --fatal-infos
flutter test
Pop-Location
```

GitHub Actions runs these same checks with Flutter 3.50.0. Android and iOS runner projects are generated. A local WSL Android debug APK build passes; run `flutter build apk --debug` for Android. iOS build/signing still requires macOS/Xcode. The AppAuth redirect is `opsbridgeflutter://oauth2redirect`; register it on the `opsbridge-flutter` Keycloak client. The Expo field app has its own `opsbridge://auth` redirect. Device OIDC login and refresh remain unverified.

Add `--profile apps` for the web surfaces. The operations dashboard is on `http://localhost:5173`, worker portal at `http://localhost:3000`, compliance console at `http://localhost:4200`, and integration console at `http://localhost:4173`. API gateway is `http://localhost:8080`.

To enable browser OIDC, set `VITE_KEYCLOAK_URL=http://localhost:8081` and `KEYCLOAK_PUBLIC_URL=http://localhost:8081` in the repo `.env`, then start with both `--profile apps --profile identity`. Keycloak imports the OpsBridge realm. The realm uses a six-digit, 30-second TOTP policy and marks `Configure OTP` as a default required action, so a user enrolling at first login must scan the QR code with a TOTP authenticator and verify a code before continuing; the browser flow then requests the configured OTP on later logins. The realm config is covered by `npm run verify:keycloak-realm`, but the first-login and repeat-login screens still need a live Keycloak verification. Create a local user in the admin console, set its `tenant_id` user attribute to `demo-tenant`, and assign a realm role such as `compliance-reviewer` before using the review console. The sample admin login comes from `KEYCLOAK_ADMIN` and `KEYCLOAK_ADMIN_PASSWORD`; change the local-only defaults. The Expo field app uses the `opsbridge://auth` redirect and needs `EXPO_PUBLIC_OIDC_ISSUER` set to a URL reachable from the device or emulator. The Flutter analytics app uses `OPSBRIDGE_OIDC_ISSUER` and the `opsbridgeflutter://oauth2redirect` callback; see its README for Android emulator URL examples. Without the respective issuer setting, each app uses the gateway's local-only demo identity.

Useful local endpoints are `/health` on each service, RabbitMQ management at `http://localhost:15672`, Kafka at `localhost:29092`, and the AI runtime at `http://localhost:8002/docs`.

The React operations dashboard also opens a 30-second, single-use WebSocket ticket through the gateway. The realtime service validates that ticket, consumes the tenant-specific Redis Pub/Sub channel, and sends minimal status events. Kafka remains the durable event stream; WebSocket updates are best-effort hints that prompt the dashboard to reload authoritative case data.

For a synthetic RAG exercise, run `python scripts/index-sample-policy.py` after starting the AI runtime and database, then `python scripts/evaluate_rag.py`. The harness reports retrieval quality, latency and a cross-tenant isolation probe; the CI job is configured but has not had a hosted run, and its small golden set needs human review.

The API gateway, Django compliance API, Celery worker, and FastAPI AI runtime export OpenTelemetry traces to the local Collector over OTLP/HTTP. Run `npm ci` and `npm run test:otel` from `services/api-gateway` to smoke-test the gateway: it sends a relay request to a local mock compliance service and verifies `traceparent` propagation, related spans, request counts, and latency metrics. The Python/container path still needs a Docker run. The collector uses a debug exporter, so inspect its container logs for spans; trace data is not retained or sent to a hosted tracing backend.

Use `--profile observability` to add Prometheus, Alertmanager, Mailpit, and Grafana. Grafana provisions the OpsBridge gateway SLO dashboard at `http://localhost:3001`; the sample demo targets are 99.5% 30-day API availability (5xx responses count as failures; 4xx responses are excluded) and 95% of API requests under one second. These are learning targets, not a service commitment. Prometheus retains 45 days of local metrics to evaluate the 30-day windows. Alertmanager sends email to the local Mailpit inbox at `http://localhost:8025`; messages are captured and are not delivered externally. Run `python scripts/verify_alert_delivery.py` to check the alert-to-email route. This local configuration is not a production notification receiver. The same validated correlation ID is also carried into audit records and asynchronous workflow events. See `docs/observability-runbook.md` for the local runbook.

## Optional technology labs

- `--profile data-labs`: MongoDB, MySQL, DynamoDB Local, and adapter service.
- `--profile oracle-lab`: Oracle Free and adapter service.
- `--profile search-labs`: Elasticsearch and adapter service.
- `--profile graph-labs`: Neo4j, Memgraph, and adapter service.
- `--profile messaging-labs`: NATS and adapter service.
- `--profile aws-labs`: LocalStack for S3, SQS, SNS, Lambda, and selected AWS APIs.
- The OpenTelemetry Collector starts with the core services. `--profile observability` adds Prometheus, Alertmanager, Mailpit, and Grafana.
- `--profile spring-cloud-labs`: Spring Cloud Circuit Breaker + Resilience4j failure/fallback lab at port 8014. Set `DEMO_SIMULATE_FAILURE=true` to exercise the synthetic dependency outage path.
- `--profile event-consumer-lab`: Kafka domain/external event consumer with an idempotent PostgreSQL projection and invalid-event DLQ. Inspect `/health` on port 8092; Kafka commits only after the projection transaction or DLQ publish succeeds.
- AWS serverless/CDN/ETL examples are in `infra/cdk` and require `INCLUDE_SERVERLESS_LAB=true` to add the opt-in stack. Review its cost notes and generated diff before any cloud deployment; it is not part of local Compose.

Example adapter path: `POST http://localhost:8004/v1/adapters/mongodb/upsert` with header `X-Tenant-Id: demo-tenant` and JSON `{"key":"case-1","data":{"status":"open"}}`.

## External providers

Stripe uses a configured Price ID and hosted Checkout/Customer Portal. Stripe webhooks go to port 8787. Twilio WhatsApp, Meta WhatsApp Cloud API templates, SendGrid, S3, Google Drive, Microsoft Graph, DocuSign, Vapi, and Vodex are configured server-side. Vodex calls require `VODEX_API_KEY`, `VODEX_ACCOUNT_URL`, project/contact data, and explicit `consentForCalls: true`; the transcript route reads by call UUID. Use each provider's sandbox/test credentials; secrets belong only in `.env` locally or a deployment secret manager. Do not paste secrets into frontend environment variables, commits, issues, or screenshots.

The first external provider action should be a sandbox operation. Tenant context and return URLs are validated. The gateway enforces OIDC tokens when configured and permits a local demo identity only when `APP_ENV` is not production and `DEV_IDENTITY_ENABLED=true`.

## Production deployment

Terraform under `infra/terraform` describes an AWS baseline. Do not apply it without reviewing the region, cost, network, data retention, and secret values. Set production secrets in AWS Secrets Manager and switch storage to S3. Never deploy the local sample credentials, mock identities, debug settings, or unencrypted local databases.
