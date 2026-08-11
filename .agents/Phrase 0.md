You are working on the Nexus Analytics project.
Prompt 0 — Quy tắc chung cho coding agent
The project already has:
- Completed mobile UI
- Completed desktop UI
- Existing backend foundation
- Existing database/backend logic in some areas
- Some analytics screens still using mock data

Your task is to improve the EXISTING project, not rebuild it.

GLOBAL RULES:

1. Inspect the repository before modifying anything.
2. Preserve the approved Nexus Analytics UI.
3. Do NOT redesign screens unless a functional issue requires a minimal UI change.
4. Do NOT rewrite working backend modules without a concrete reason.
5. Prefer incremental refactoring over large rewrites.
6. Reuse existing utilities, components, schemas, conventions and infrastructure.
7. Do not introduce a second competing architecture.
8. Do not introduce AI features unless explicitly requested.
9. Do not connect Google Analytics, Facebook Ads, Salesforce or other external providers unless explicitly requested.
10. Never commit secrets.
11. Never put server secrets into client/public environment variables.
12. Database changes must use migrations.
13. Do not manually modify production database state.
14. Preserve backward compatibility when reasonable.
15. Avoid placeholder implementations that silently pretend to work.

Before coding:
- Inspect project structure
- Detect frontend stack
- Detect backend stack
- Detect database
- Detect auth implementation if any
- Detect existing API conventions
- Detect existing environment configuration
- Detect existing tests
- Detect CI configuration
- Detect current mock-data sources

Then write a short INITIAL FINDINGS section.

After implementation, run all available relevant checks:

- format
- lint
- typecheck
- unit tests
- integration tests where available
- production build
- database migration validation

Do not claim PASS for anything you did not actually execute.

At the end return:

1. Initial findings
2. Root causes / architectural issues found
3. Changes made
4. Files changed
5. Database migrations
6. Tests executed and exact results
7. Remaining risks
8. Blockers
9. GO / NO-GO for the current phase
10. Recommended next step

If the current phase cannot be completed safely, STOP and report the blocker instead of improvising.