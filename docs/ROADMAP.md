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
| Datastore | PostgreSQL (RDS/Aurora), raw psycopg3 (async) — no ORM; Alembic for migrations |
| GitHub API client | githubkit (async, typed, GitHub App auth + webhook models); replaces PyGithub |
| Vulnerability data | OSV.dev API (primary); PyPI JSON API / npm registry for latest versions |
| Version parsing | `packaging` (PEP 440) + `semantic-version` (npm ranges) |
| Transactional email | Resend |
| Observability | Native CloudWatch (logs, metrics, alarms, X-Ray) |
| Job orchestration | **Open** — DBOS Transact vs. Hatchet; decide alongside the M1 engine spike |

---

## M0 — Platform foundations

Replace the boilerplate internals with production plumbing. Everything else builds
on this.

- [ ] PostgreSQL persistence layer (psycopg3, Alembic migrations); delete the
      in-memory repo store
- [ ] Core data model: `organizations`, `users`, `installations`, `repositories`,
      `capability_configs`, `tasks`, `runs`, `audit_events`
- [ ] GitHub App installation lifecycle: install/uninstall webhooks create and
      tear down tenant state
- [ ] GitHub App auth: installation-token minting, caching, and refresh
- [ ] Webhook ingestion hardened: HMAC verification (exists), plus idempotency
      keys, replay protection, and dead-letter handling
- [ ] Background job orchestration (webhook events → durable workflows → workers);
      no work executes inside the request path. Engine choice (DBOS Transact vs.
      Hatchet) decided alongside the M1 spike — both are Postgres-backed and $0
      at V1 scale
- [ ] Backend deployment target on AWS (API + workers), IaC from day one

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

- [ ] Task lifecycle: `triggered → queued → planning → executing → pr_open →
      (merged | rejected | failed)` with persisted transitions
- [ ] Mode enforcement per capability per repo:
  - **Off**: events ignored, recorded as suppressed in audit log
  - **Assisted**: PR opened, task waits on human review; approval/close resolves it
  - **Autopilot**: PR merges automatically **only** behind merge gates
- [ ] Autopilot merge gates: CI green, no conflicts, respects branch protection,
      per-repo daily task cap
- [ ] Rollback: one-click revert PR for any Everpilot-merged change
- [ ] Full audit trail: every trigger, decision, PR, merge, and failure queryable
      per repo and per org
- [ ] Run logs and diffs viewable in the dashboard

## M3 — V1 capabilities

Both capabilities are thin layers over the M2 pipeline.

### Dependencies

- [ ] Ecosystem support at launch: Python (uv/pyproject) and JavaScript
      (npm/pnpm) — others post-V1
- [ ] Detect outdated/vulnerable dependencies on schedule and on lockfile-touching
      pushes (OSV.dev for advisories; PyPI JSON API / npm registry for versions)
- [ ] Upgrade PRs with changelog/breaking-change summaries, verified by the repo's
      own CI
- [ ] Batch strategy: group compatible minor/patch bumps; majors always solo PRs

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
- [ ] Public docs: setup guide, capability reference, mode semantics, billing FAQ
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

1. Job orchestration engine: DBOS Transact (in-process, Postgres-only, lowest ops)
   vs. Hatchet (separate orchestrator with dashboard, best per-repo concurrency
   keys). Decide alongside the M1 agent-engine spike.
2. LLM cost control: hard per-task token budget vs. adaptive? How is overrun
   surfaced to the customer?
3. Autopilot trust ladder: should repos have to earn Autopilot (N successful
   assisted merges first), or is opt-in enough?
4. Issue Triage on public repos: how to handle prompt-injection attempts from
   issue bodies?
5. Free tier shape: task count, repo count, or trial period?
