# OpsBridge agent guidance

## Durable project record

- Read `docs/project-decisions.md` before answering questions that change or summarize project goals, stack, repository structure, deployment, testing, or interview strategy.
- Keep detailed architecture in `docs/final-plan.md`, checklist evidence in `docs/job-description-skill-gap.md` and `docs/job-description-checklist-status.md`, and hosting choices/costs in `docs/deployment-plan.md`.
- When a project-level clarification or decision is made in a conversation, update the relevant canonical doc before the final response. Add a short dated entry to `docs/project-decisions.md` when it changes a decision, priority, limitation, or verified status. Avoid logging unrelated small talk.
- Update README links when adding or renaming canonical project documents.

## User's persistent project preferences

- This is an educational portfolio project aimed at job interviews. Prefer a zero-cost option and disclose any service that can incur charges before recommending its use.
- Do not change application source solely to fit a free host when the user asks to preserve code; document the limitation and offer a deployment-only alternative. Ask before making an app-source change for hosting.
- Use one canonical monorepo unless the user explicitly changes this decision. Avoid duplicating primary data stores or services merely to claim more technologies.
- NestJS is intentionally excluded because the user has prior work experience with it.
- AI-assisted coding and automated verification are preferred. Record exact commands/results; never label configured or unrun CI/cloud paths as verified.
- Use synthetic data only. Never read or expose `.env` secrets or real personal/customer data.

## Reporting

For planning/advice that affects the repo, state what changed in the docs, distinguish the present implementation from future recommendations, and report material free-tier/security limitations. For code changes, follow the relevant local instructions, run only requested/relevant verification, and record its exact outcome.
