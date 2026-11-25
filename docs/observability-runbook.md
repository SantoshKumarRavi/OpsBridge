# Observability and alerting runbook

## Start the local stack

From the repository root:

```powershell
docker compose -f infra/docker-compose.yml --profile observability up -d prometheus alertmanager mailpit grafana
```

- Prometheus: `http://localhost:9090`
- Alertmanager: `http://localhost:9093`
- Grafana: `http://localhost:3001` (demo credentials: `admin` / `admin`)
- Mailpit inbox: `http://localhost:8025`

The Compose Alertmanager receiver sends email to Mailpit. Mailpit captures messages for local inspection and does not deliver email externally. The demo SMTP route disables TLS only for this isolated local stack; do not reuse its config for a production SMTP server.

## Verify alert delivery

```powershell
python scripts/verify_alert_delivery.py
```

The verifier posts a uniquely labeled synthetic alert to Alertmanager and polls Mailpit's message-list API for the resulting email. The GitHub Actions observability smoke job performs the same check after validating Prometheus rules, readiness, and Grafana dashboard provisioning.

The Prometheus rules send alerts to Alertmanager when a gateway SLO threshold is breached, its metrics endpoint is unavailable, or a model provider's failure rate remains above 20% under sustained traffic. For `AIProviderFailureRateHigh`, inspect the provider-specific attempt counters and failure span events, then check configured provider fallbacks and credential/service status. Use the alert name and summary to locate the rule in `infra/observability/alerts.yml`, and follow the request correlation ID through traces when the deployed trace backend is available.

The AI runtime exposes `/metrics` for Prometheus. Provider metrics include attempt outcomes, latency, provider-reported token counts, cost estimates from `LLM_COST_PER_1K_INPUT_USD` / `LLM_COST_PER_1K_OUTPUT_USD`, and successful fallback counts. Provider failures also add a bounded `ai.provider.attempt` span event containing provider, attempt number, latency, outcome, and exception type. Prompts, responses, tenant IDs, and credentials are not metric labels or span-event fields. Cost values are estimates and remain zero when token pricing is not configured.

The Grafana dashboard `OpsBridge API and AI reliability` now plots provider failure rate, p95 attempt latency, and estimated cost by provider. Cost uses configured rates; check those values before interpreting the panel. Metrics appear after provider attempts have occurred.

The rules leave SLO ratios undefined when the measurement window has no requests, and treat an absent 5xx counter as zero errors when successful traffic exists. The CI job runs `promtool test rules` cases for no traffic, healthy traffic without a 5xx series, a sustained latency breach, and AI provider failures that only alert after both the failure-rate and volume thresholds hold for five minutes.

## Limits

This is a learning and CI notification path. The current repo does not configure an external email, Slack, PagerDuty, or other on-call destination; production SMTP credentials/TLS, ownership, escalation, and a searchable trace backend must be configured for a real deployment. The smoke alert verifies Alertmanager-to-SMTP delivery to the test inbox; it does not prove a real SLO breach or incident response process.
