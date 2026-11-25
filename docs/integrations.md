# Integration catalog

| Integration | Path | Responsibility |
|---|---|---|
| Stripe | Spring Boot `/api/v1/billing` | Hosted subscription Checkout and customer billing portal; allow-listed return URLs, idempotency key, tenant metadata. |
| Stripe webhooks | Hono `/webhooks/stripe` | Verifies signature and emits normalized event. |
| Twilio WhatsApp | Spring Boot `/api/v1/integrations/whatsapp/messages` | Sends consented operational updates; provider callback is signature checked. |
| WhatsApp Cloud API | Spring Boot `/api/v1/integrations/whatsapp-cloud/templates` | Sends an approved template by Meta Graph API; requires explicit consent, a configured token/phone-number ID, and an approved template. |
| SendGrid | Spring Boot `/api/v1/integrations/email` | Sends onboarding notifications. |
| Google Drive / Microsoft Graph | Integration adapter configuration | Document and calendar/workforce data integrations; credentials remain in server secrets. |
| DocuSign | Integration adapter configuration | E-signature workflow handoff. |
| Vapi | Voice workflow configuration | Voice intake and call status events; a human can take over. |
| Vodex.ai | Spring Boot `/api/v1/integrations/vodex/calls` and `/api/v1/integrations/vodex/calls/{callUuid}/transcript` | Consent-gated call trigger using the documented `Authorization` and `dburl` headers; retrieves a call transcript using the documented auth header. |
| MuleSoft APIkit process API lab | `services/mulesoft-process-api-lab` | Contract-first process API calls the Django case system API and transforms a tenant-scoped case response. Requires Anypoint Studio/APIkit import and trusted gateway/API Manager policy before use. |
| AWS S3 | Django storage backend | Private document object storage, server-side encryption, and lifecycle policy. |
| Kafka / RabbitMQ / NATS | Domain events / background jobs / internal messaging | Separate durability and delivery responsibilities. |
| SQS / SNS | Integration lab | Cloud queue and fan-out adapters. |

Set provider credentials only in backend environment. Connector health responses show whether a connector is configured without returning credentials or tokens. External side effects should be behind explicit user-triggered actions and use provider sandbox environments until a production owner configures live credentials.

Vodex call triggering and transcript retrieval now follow its published OpenAPI contract. Configure `VODEX_API_KEY` and `VODEX_ACCOUNT_URL` on the server; call requests must include `consentForCalls: true` and the provider's required contact, project, and account data. `VODEX_API_BASE_URL` can select a provider sandbox if Vodex supplies one. Local Compose reads these values from `.env`; the optional Terraform variable `vodex_credentials_secret_arn` injects them from JSON keys in AWS Secrets Manager. Source and mocked HTTP contract tests are present, but a credentialed call, provider callbacks/signature verification, call recording, and durable consent evidence are not implemented or verified. See [Vodex API documentation](https://docs.vodex.ai/) and its [published OpenAPI specification](https://docs.vodex.ai/openapi.json).
