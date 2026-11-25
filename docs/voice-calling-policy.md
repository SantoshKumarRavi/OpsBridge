# Voice calling policy

## Register a tenant contact policy

Only callers with the `opsbridge-admin` or `compliance-reviewer` role can write a contact policy through the API gateway. The gateway derives tenant and actor identity from the authenticated session and relays the request to the compliance API.

```http
PUT /api/v1/voice/contacts
Authorization: Bearer <access-token>
Content-Type: application/json

{
  "phoneNumber": "+12025550100",
  "consentStatus": "granted",
  "consentRecordedAt": "2026-11-20T09:15:00Z",
  "consentSource": "signed onboarding form",
  "consentReference": "evidence-ref-42",
  "suppressed": false,
  "suppressionReason": ""
}
```

Phone numbers must use E.164 format. Granting consent requires a non-future timestamp and a source. Suppression requires a reason. To revoke consent, update `consentStatus` to `revoked`; each actual policy state change creates a separate audit event with actor, before/after state, timestamp, tenant, and correlation ID. To suppress a number, set `suppressed` to `true` and provide a reason. Consent and suppression records are tenant-scoped and stored in the compliance database.

The review endpoint is `GET /api/v1/voice/contacts/eligibility?phoneNumber=...`. It returns only `eligible` and a reason, and is restricted at the gateway to administrators and compliance reviewers.

The Angular compliance console at `/` in `apps/compliance-console` provides a form to load an existing tenant policy, update consent or suppression state, and check eligibility. Its browser workflow test mocks HTTP responses and passed axe WCAG 2.1 A/AA with zero automated violations; the separate gateway contract test exercises the backed API against SQLite.

## Outbound call gate

`POST /api/v1/integrations/voice/calls` accepts `{"customerNumber":"+12025550100"}`. The integration service checks the tenant's configured local-time calling window, then queries the compliance API with the tenant ID and internal service token. Vapi is called only when the tenant record has granted consent and is not suppressed. Missing records, revoked consent, suppression, and compliance API errors all stop the call; an unavailable eligibility service fails closed.

Calling windows are configured under `opsbridge.voice.tenants.<tenant-id>` in `services/integration-service/src/main/resources/application.yml`. The demo tenant uses `DEMO_VOICE_TIME_ZONE`, `DEMO_VOICE_ALLOWED_START`, and `DEMO_VOICE_ALLOWED_END`; defaults are `Asia/Kolkata`, `09:00`, and `17:00`. Window start is inclusive and window end is exclusive. An unconfigured tenant is denied.

## Scope and limitations

This is an educational record and policy workflow. It stores the source and reference supplied by an authorized operator but does not independently validate the underlying consent evidence, sync an external Do Not Call registry, apply jurisdiction-specific legal rules, or establish regulatory compliance. Production use needs an approved evidence-verification process and authoritative, regularly updated suppression sources. Provider credentials, callbacks, recording, and a live Vapi end-to-end run are not included in this local verification.

`VoiceCallPolicyTest` covers local calling-window behavior. `VoiceContactUpdate` API tests cover tenant isolation, grant, revoke, suppression, validation, and audit persistence. `VoiceConsentClientTest` and `IntegrationVoiceCallTest` verify the compliance eligibility lookup, fail-closed behavior, and that Vapi is not called after a denial. The gateway contract check exercises the public write/read paths against the compliance API.
