# Open Questions — autonomous roadmap run

Questions and feedback needed from Erik to complete the roadmap goal. Newest
first. Remove entries once resolved.

## ~~PR merges need human action~~ — RESOLVED 2026-07-15

Erik granted standing authorization: **auto-merge any PR once all GitHub
checks pass, except when human input is judged necessary** (e.g. destructive
changes, scope decisions, anything security-sensitive). All 12 queued PRs from
the autonomous run (#3, #15 replacing #4, #5–#14) were rebase-merged to main
in stack order; every merge had green CI.

## ~~Roadmap open questions~~ — 3 of 4 RESOLVED 2026-07-19

Erik decided: LLM cost control = hard per-task cap + one retry-with-bump;
Autopilot access = earned via N successful Assisted merges; free tier = N
completed tasks/month. Recorded in the ROADMAP locked-decisions table.

Still open: **prompt-injection handling for Issue Triage on public repos**
(M3 design) — a design proposal will be drafted for Erik's review.

## 2026-07-15 — .env.example not updatable by agent

Claude Code's permission settings deny access to `.env*` files, so
`backend/.env.example` could not be updated with the new `DATABASE_URL`
variable (documented in README instead). Add it manually:
`DATABASE_URL=postgresql://everpilot:everpilot@localhost:5432/everpilot`

## 2026-07-15 — DBOS integration lacks integration tests

Unit tests cover the dispatch wiring with fakes, but DBOS's durable behavior
(checkpointing, recovery, queue concurrency) is untested — it requires a real
Postgres. Recommend: add a `postgres` service container to the CI workflow and
an integration-test marker (`pytest -m integration`) exercising one durable
workflow end-to-end before M2 builds the task pipeline on this foundation.

## ~~IaC tooling~~ — RESOLVED 2026-07-19

CloudFormation, following CloudZero/cz-standards conventions. The deployment
work should read the repo's `infra-account-architecture`,
`govern-tagging-policy`, `infra-ssm-parameters`, and `infra-vpc-networking`
standards before writing templates.

## 2026-07-19 — SECURITY: entire API is pre-auth; M4 must add tenancy enforcement

Every endpoint (repos, tasks, rollback, and now the cross-org /api/v1/audit
feed) has no authn/authz — acceptable only while nothing is deployed publicly.
The M4 WorkOS integration must ship API-wide auth middleware with org-membership
scoping (a caller may only pass organization_id / repository_id values they are
a member of) **before any public deployment**. Flagged during the audit-feed
code review: /api/v1/audit is the first deliberately cross-tenant surface.

## 2026-07-15 — Third-party account provisioning (M4)

M4 needs accounts + API keys only you can create: WorkOS (AuthKit), Stripe
(Billing Meters), Resend. Code can be built against their test modes once
sandbox keys exist. Without them, M4 items will be stubbed behind interfaces
like the agent engine is.

## 2026-07-15 — Anthropic API credentials

M1 spike and all agent execution need an Anthropic API key provisioned for the
project (and a decision on org account vs personal). Not needed for M0.
