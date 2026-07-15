# Open Questions — autonomous roadmap run

Questions and feedback needed from Erik to complete the roadmap goal. Newest
first. Remove entries once resolved.

## ~~PR merges need human action~~ — RESOLVED 2026-07-15

Erik granted standing authorization: **auto-merge any PR once all GitHub
checks pass, except when human input is judged necessary** (e.g. destructive
changes, scope decisions, anything security-sensitive). All 12 queued PRs from
the autonomous run (#3, #15 replacing #4, #5–#14) were rebase-merged to main
in stack order; every merge had green CI.

## 2026-07-15 — Roadmap open questions still owner-less

Carried from `docs/ROADMAP.md` (not blocking current M0 work, will block M2+):

1. LLM cost control model (hard per-task token budget vs adaptive).
2. Autopilot trust ladder (earn autopilot vs opt-in) — affects M2 merge-gate design.
3. Prompt-injection handling for Issue Triage on public repos — affects M3 design.
4. Free tier shape (task count / repo count / trial) — affects M4 Stripe config.

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

## 2026-07-15 — IaC tooling never decided

The M0 item "Backend deployment target on AWS (API + workers), IaC from day
one" is blocked on your Terraform vs. CDK vs. Pulumi preference (flagged during
the stack research, never answered). Everything else in M0 is done.

## 2026-07-15 — Third-party account provisioning (M4)

M4 needs accounts + API keys only you can create: WorkOS (AuthKit), Stripe
(Billing Meters), Resend. Code can be built against their test modes once
sandbox keys exist. Without them, M4 items will be stubbed behind interfaces
like the agent engine is.

## 2026-07-15 — Anthropic API credentials

M1 spike and all agent execution need an Anthropic API key provisioned for the
project (and a decision on org account vs personal). Not needed for M0.
