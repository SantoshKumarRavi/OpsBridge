# Demo onboarding policy for synthetic records

This is a sample portfolio policy and is not legal, immigration, employment, or compliance advice.

## Identity record

- A readable identity record is required before a case can be marked ready for human approval.
- Extract the worker's name, document identifier, and expiration date only when visible in the provided document.
- If the name differs from the profile, the document has expired, or extraction confidence is below the configured threshold, request human review. Never infer a corrected identity.

## Work eligibility

- A work eligibility record is required for the selected country and role.
- A missing, expired, unreadable, or conflicting record must be sent to an authorized reviewer.
- AI output is a suggestion with evidence. It never approves or rejects a worker.

## Privacy and retention

- Use only the minimum fields needed for the onboarding case.
- Store document files in private storage and restrict access to the assigned tenant.
- Keep an audit event for file receipt, extraction, policy evaluation, reviewer action, and notification.
- Delete synthetic or expired portfolio documents according to the workspace retention setting.
