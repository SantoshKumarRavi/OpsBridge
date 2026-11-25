---
name: opsbridge-vertical-slice
description: Implement or review a bounded OpsBridge product change across its UI, API, contract, tests, and documentation.
---

# OpsBridge vertical slice workflow

Use this skill for a feature or bug that crosses one product workflow. Keep the change tied to a demonstrable user outcome.

1. Read `docs/architecture.md`, `docs/final-plan.md`, and the relevant service/UI source before editing. Identify the authoritative data owner and tenant boundary.
2. State the acceptance criteria and identify the contract, implementation, and test files that need to change.
3. Keep model recommendations advisory. Require a human decision for approval or rejection. Use synthetic records only.
4. Implement the smallest complete vertical slice. Add or update a focused automated test and the API/event contract when behavior changes.
5. Run the relevant automated checks. For UI changes, run the owning app's build; for a complete web UI pass, run `npm run build:frontends`. Run Compose E2E only when Docker is available.
6. Review the diff for tenant leakage, credential exposure, missing validation, unhandled failure paths, and unrelated changes.
7. Report changed behavior, commands and outcomes, known gaps, and any human review still needed. Never describe unrun checks as passing.
