# Open Questions — autonomous roadmap run

Questions and feedback needed from Erik to complete the roadmap goal. Newest
first. Remove entries once resolved.

## 2026-07-19 — Roadmap status: everything unblocked is shipped

Every roadmap item is now either **complete** or **blocked on an entry below**.
Nothing else is buildable without your input:

| Item | Status | Blocker |
|---|---|---|
| M0 platform foundations | ✅ shipped | — |
| M1 agent-engine spike | ⛔ blocked | Anthropic API key + engine choice (below) |
| M2 task pipeline + audit | ✅ shipped | — |
| M3 Dependencies — detection/batching | ✅ shipped | — |
| M3 Dependencies — upgrade-PR generation | ⛔ blocked | needs M1 (an agent writes the change) |
| M3 Issue Triage | ⛔ blocked | needs M1 (LLM classifies/fixes) |
| M4 SaaS layer (auth, metering, billing, email) | ⛔ blocked | WorkOS/Stripe/Resend accounts + auth design (below) |
| M5 public docs | ✅ shipped | — |
| M5 security review | ✅ effectively covered | pre-auth surface tracked below; full audit wants a deployed env |
| M5 observability | ◐ partial | log group + 5xx alarm shipped in M0; tracing/dashboards need the deployed stack |
| M5 load testing | ⛔ blocked | needs a deployed environment (AWS account decision below) |
| M5 marketing site + pricing page, ToS/privacy | ⛔ blocked | product/design/legal decisions + final pricing |
| M5 status page + incident process | ⛔ blocked | needs a deploy + a status-page provider choice |

The specific decisions/credentials that unblock these are the dated entries
below (Anthropic key, M4 provisioning, AWS account/domains/NAT, prompt-injection
design, capability-config data model).

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

## 2026-07-19 — Capability-config data model split (design decision needed)

Capability modes live in the legacy `repo_configs` store keyed by
`repo_full_name`, while tenant state (orgs/installations/repositories) is keyed
by GitHub ids — and the `capability_configs` table from migration 0002 has no
readers or writers. Concrete hazard: a repo rename keeps `github_repo_id`
stable but breaks the `full_name` config lookup, silently flipping capabilities
to OFF. Proposal: migrate capability config onto `capability_configs`
(keyed by `repository_id`), update the repos API, and delete the legacy store.
Medium refactor; wants a decision before M4 builds onboarding on top.

## 2026-07-19 — Dependency scanning V1 limits

Root-directory lockfiles only (trigger and fetch deliberately agree on this),
and files >1MB are skipped with a warning (GitHub contents-API limit — needs
the git blobs API). Both are post-V1 unless design partners hit them early.

## 2026-07-19 — AWS deployment: account, domains, NAT cost (needed to actually deploy)

Templates and `scripts/deploy.sh` are complete and cfn-lint-clean, but a real
deploy needs: (1) which AWS account/org Everpilot deploys into (it's a Silvexis
product, so NOT a CloudZero cz-standards account — templates are account-
agnostic and tags carry a mixed cz:owner=erik@cloudzero.com / cz:repo=silvexis
identity that should be confirmed or corrected); (2) the domain names + ACM
certs (`live`/`alfa`); (3) the NAT-gateway cost tradeoff — kept for the
standards private-subnet posture (~$33/mo/namespace) but a fck-nat micro or
public-subnet task would cut it ~10x. Also: the hardcoded `cz:` prefix and
`aws-apn-id` (CloudZero's AWS Partner id) should become deploy.sh variables if
this ships under Silvexis billing.

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

## 2026-07-25 — LLM key management: interim-admin hardening for M4

PR #22 shipped the key layer with an interim shared-token admin guard. A code
review surfaced hardening that belongs with M4 (WorkOS employee SSO), not the
stopgap:

- **Admin token rotation needs a restart** — read from cached settings. For an
  emergency-revocation credential, live reads or short-TTL caching are better;
  acceptable while the token is off by default (fail-closed 503) and rotated via
  redeploy. Do NOT enable the admin token until the ALB has TLS.
- **Per-org BYOK keys in SSM are unbounded-cardinality** — SSM standard-param
  limits (~10k/account) and no caching. At scale, move BYOK keys to a
  KMS-encrypted DB column (or Secrets Manager) and cache platform-key reads.
- **No org-existence check on BYOK PUT** — a typo'd org id creates an orphan
  key; validate against the installation store once M4 wiring exists.
- **`settings.anthropic_api_key` is a second read path** — the M1 engine MUST
  call `app.state.llm_key_store.resolve()` (BYOK + uplift aware), never the
  settings field, which is boot-cached and bypasses BYOK. Deprecate the field
  when M1 lands.
- **Admin surface shares the pre-auth internet exposure** — mitigated by
  fail-closed default, `include_in_schema=False`, and the TLS warning above;
  real fix is M4 SSO + network restriction.

## 2026-07-25 — Anthropic API credentials (channel now built; key still needed)

Decided: platform key managed via an admin-only interface (Silvexis employees);
customer usage on it bills at cost + 20%; orgs may BYOK and pay no LLM costs.
PR #22 shipped the backend: SSM-backed key stores, BYOK→platform resolution,
uplift math, and admin endpoints behind an interim admin token (fail-closed).

Still needed from Erik to unblock M1: **the actual key** (org vs personal
account decision), provided via `backend/.env` locally or
`aws ssm put-parameter --name /cz/everpilot/<ns>/anthropic-api-key` (or the
admin API once a token is set) — never pasted in chat. The admin *frontend*
page is deferred until WorkOS employee SSO exists (M4).
