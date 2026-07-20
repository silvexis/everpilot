# Everpilot V1 Roadmap

> **Autopilot, not copilot, for your repositories.**

This document defines the minimum feature set for Everpilot **version 1: a public
SaaS launch**. Anything not listed under a V1 milestone is deliberately deferred —
see [Post-V1](#post-v1).

## V1 definition

V1 is done when a stranger can sign up, install the GitHub App on their org, enable
**Dependencies** and **Issue Triage** on a repo in **Autopilot**, **Assisted**, or
**Off** mode, watch Everpilot open (and in Autopilot, merge) real PRs, see every
action in an audit trail, and get billed for the work performed.

### Locked decisions

| Decision | Choice |
|---|---|
| Launch target | Public SaaS (self-serve signup) |
| V1 capabilities | Dependencies, Issue Triage |
| Operating modes | All three: Autopilot, Assisted, Off |
| Agent engine | Undecided — resolved by the M1 spike (see below) |
| Auth provider | WorkOS AuthKit (email/password + GitHub/Google OAuth, orgs/RBAC) |
| Billing | Stripe Billing Meters, usage-based (per completed task / merged PR); no third-party metering layer |
| Datastore | PostgreSQL (RDS/Aurora), raw psycopg3 (async) — no ORM |
| Migrations | Alembic (hand-written migrations; pulls in SQLAlchemy Core as a dependency only, ORM stays unused) |
| GitHub API client | githubkit (async, typed, GitHub App auth + webhook models); replaces PyGithub |
| Vulnerability data | OSV.dev API (primary); PyPI JSON API / npm registry for latest versions |
| Version parsing | `packaging` (PEP 440) + `semantic-version` (npm ranges) |
| Transactional email | Resend |
| Observability | Native CloudWatch (logs, metrics, alarms, X-Ray) |
| Job orchestration | DBOS Transact (in-process, Postgres-backed); revisit native AWS orchestration (Step Functions) if scale demands it |
| IaC | CloudFormation, following [CloudZero/cz-standards](https://github.com/Cloudzero/cz-standards) conventions (account architecture, tagging policy, SSM parameters, VPC networking) |
| Autopilot access | Earned: a repo needs N successful Assisted merges (default 5) before Autopilot can be enabled |
| LLM cost control | Hard per-task token cap by capability type; one automatic retry at a higher cap on overrun, then visible task failure |
| Free tier | N completed tasks/month free (default 10), then usage-priced — aligns 1:1 with the Stripe billing meter |

---

## M0 — Platform foundations

Replace the boilerplate internals with production plumbing. Everything else builds
on this.

- [x] PostgreSQL persistence layer (psycopg3, Alembic migrations); delete the
      in-memory repo store *(PR #4/#15 — store protocol + Postgres/in-memory impls;
      in-memory remains as the test/dev double, Postgres used when DATABASE_URL set)*
- [x] Core data model: `organizations`, `users`, `installations`, `repositories`,
      `capability_configs`, `tasks`, `runs`, `audit_events` *(PR #5 — migration
      0002 + domain models incl. task state machine with legal transitions)*
- [x] GitHub App installation lifecycle: install/uninstall webhooks create and
      tear down tenant state *(PR #7 — `InstallationService` handles
      created/deleted/suspend/unsuspend + repo add/remove, idempotent upserts)*
- [x] GitHub App auth: installation-token minting, caching, and refresh
      *(PR #6 — githubkit auth strategies via `GitHubAppClients` factory)*
- [x] Webhook ingestion hardened: HMAC verification (exists), plus idempotency
      keys, replay protection, and dead-letter handling *(PR #6 — fail-closed
      signature checks, delivery-GUID dedup w/ migration 0003; PR #8 — failed
      events persist as retriable DBOS workflows, covering dead-letter)*
- [x] Background job orchestration via DBOS Transact (webhook events → durable
      Python workflows checkpointed in Postgres); no work executes inside the
      request path. Keep workflow logic cleanly separated so a future migration
      to native AWS orchestration at scale stays tractable *(PR #8 —
      `EventDispatcher` protocol: inline for dev, DBOS queue when DATABASE_URL
      set; handlers stay engine-agnostic plain functions)*
- [x] Backend deployment target on AWS (API + workers), IaC from day one
      *(PR #20 — CloudFormation per cz-standards: network/ECR/app/OIDC stacks,
      ECS Fargate (API+DBOS), RDS Postgres, SSM-source secrets, in-VPC alembic
      migrations, `scripts/deploy.sh`, cfn-lint in CI. Account/domain choice
      deferred to open_questions)*

## M1 — Agent engine spike ⚠ decision gate

Two candidate engines; both get a time-boxed prototype driving one real
dependency-upgrade task end-to-end. **No M2+ execution work starts until this
decision is made and recorded as an ADR.**

| Candidate | Sketch |
|---|---|
| **Claude Agent SDK on AWS** | Backend dispatches jobs to containerized agent workers (ECS/Fargate). We own compute, isolation, and scaling. |
| **Claude Code in GitHub Actions** | Everpilot triggers headless Claude Code workflows; compute rides on Actions runners. Less infra to own; less control. |

Evaluation criteria:

- [ ] Cost per completed task (LLM tokens + compute)
- [ ] Isolation and security of untrusted repo code
- [ ] Latency from trigger to opened PR
- [ ] Repo access model (token scope, permissions blast radius)
- [ ] Observability: can we stream progress and capture full run logs?
- [ ] ADR written; losing candidate's assumptions removed from the codebase

## M2 — Task pipeline (engine-agnostic core)

The state machine every capability rides on.

- [x] Task lifecycle: `triggered → queued → planning → executing → pr_open →
      (merged | rejected | failed)` with persisted transitions *(PR #9 —
      `TaskPipeline` + `TaskStore` with optimistic-concurrency transitions)*
- [x] Mode enforcement per capability per repo: *(PR #9)*
  - **Off**: events ignored, recorded as suppressed in audit log
  - **Assisted**: PR opened, task waits on human review; approval/close resolves it
  - **Autopilot**: PR merges automatically **only** behind merge gates
- [x] Autopilot merge gates: CI green, no conflicts, respects branch protection,
      per-repo daily task cap *(PR #9 — `MergeGates`; a failed gate holds the
      task at pr_open with an auditable `task.merge_blocked` event)*
- [x] Rollback: one-click revert PR for any Everpilot-merged change *(PR #13 —
      `POST /tasks/{id}/rollback` via GraphQL revertPullRequest; revert PRs are
      never auto-merged; `task.rolled_back` audit event)*
- [x] Full audit trail: every trigger, decision, PR, merge, and failure queryable
      per repo and per org *(PR #18 — GET /api/v1/audit with repo/org/task/type
      filters + keyset pagination; `AuditRecorder` stamps organization_id at the
      append path so org feeds are complete; feed-serving indexes in migration 0004.
      ⚠ endpoint is pre-auth: M4 must add org-membership enforcement)*
- [x] Run logs and diffs viewable in the dashboard *(PR #10 — read API;
      PR #14 — Tasks list + detail pages with audit timeline and rollback button.
      Diff view links to the GitHub PR; full run-log streaming depends on the
      M1 engine choice)*

## M3 — V1 capabilities

Both capabilities are thin layers over the M2 pipeline.

### Dependencies

- [ ] Ecosystem support at launch: Python (uv/pyproject) and JavaScript
      (npm/pnpm) — others post-V1
- [x] Detect outdated/vulnerable dependencies on schedule and on lockfile-touching
      pushes (OSV.dev for advisories; PyPI JSON API / npm registry for versions)
      *(PR #11 — detection engine; PR #19 — triggers: lockfile-touching default-branch
      pushes + daily DBOS scheduled sweep, config-gated before any I/O, open-task
      dedup, truncation-safe push detection. Root lockfiles only — monorepo/nested
      and >1MB lockfiles tracked in open_questions)*
- [ ] Upgrade PRs with changelog/breaking-change summaries, verified by the repo's
      own CI
- [x] Batch strategy: group compatible minor/patch bumps; majors always solo PRs
      *(PR #12 — `plan_batches`: security solos first, then major solos, then one
      grouped minor/patch batch per ecosystem)*

### Issue Triage

- [ ] Classify new issues (bug / feature / question / duplicate) and apply labels
- [ ] Comment with analysis and, for eligible bugs, a proposed fix plan
- [ ] For bugs the agent can fix confidently: run a fix task through the M2
      pipeline (mode rules apply)
- [ ] Confidence threshold config: what the agent may attempt vs. only comment on

## M4 — SaaS layer

- [ ] Auth: WorkOS AuthKit — email/password + OAuth (GitHub, Google), hosted UI,
      orgs/RBAC; free to 1M MAU with per-connection SAML as the enterprise path
- [ ] Org/team model mapped to GitHub App installations; admin and member roles
- [ ] Self-serve onboarding: sign up → install GitHub App → pick repos → toggle
      capabilities and modes
- [ ] Usage metering: every completed task and merged PR recorded as a billable
      event
- [ ] Stripe integration: Billing Meters with per-event `identifier` idempotency;
      free monthly allowance as a $0 first pricing tier; payment method management
- [ ] Spend controls: per-org monthly budget cap that pauses agents when hit,
      with alerting before the cap. Enforced app-side against our own Postgres —
      Stripe (and every vendor surveyed) provides alerts only, not hard caps
- [ ] Transactional email via Resend (verification, notifications, receipts,
      budget alerts)

## M5 — Launch hardening

- [ ] Security review of the full surface (webhooks, token handling, agent
      sandbox, dashboard authz)
- [ ] Observability on native CloudWatch: structured logs, metrics, X-Ray tracing,
      alarms on task-failure rate and queue depth; log-retention policies set from
      day one to control cost
- [ ] Load testing on webhook bursts (org-wide installs, dependency-bot storms)
- [x] Public docs: setup guide, capability reference, mode semantics, billing FAQ
      *(PR #21 — docs/guide/: getting-started, capabilities, operating-modes, billing)*
- [ ] Marketing site + pricing page; ToS and privacy policy
- [ ] Status page and incident process

---

## Post-V1

Explicitly out of scope for V1, in rough priority order:

- **Security capability** (CVE scanning + fix PRs beyond dependency bumps)
- **Test Hygiene capability** (requires executing customer code — sandbox design)
- **Freshness capability** (general modernization)
- SSO/SAML and enterprise auth
- Additional dependency ecosystems (Go, Rust, Java, Ruby)
- GitLab / Bitbucket support
- Self-hosted agent runners
- Per-repo policy files (`.everpilot.yml`) checked into the repo

## Open questions

Tracked here until each has an owner and a decision:

1. Issue Triage on public repos: how to handle prompt-injection attempts from
   issue bodies? (Design doc in progress; all other launch questions are
   resolved in the locked-decisions table above.)
