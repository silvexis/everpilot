# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- PostgreSQL persistence layer: `RepoConfigStore` protocol with psycopg3 (async pool)
  and in-memory implementations; Alembic migrations (`repo_configs` table)
- `DATABASE_URL` setting — Postgres store when set, in-memory store for development
- Core data model (migration 0002): organizations, users, org members, installations,
  repositories, capability configs, tasks, runs, audit events — with matching Pydantic
  domain models and a task state machine (`TaskState`, legal-transition map)
- GitHub App auth: `GitHubAppClients` factory (githubkit app/installation strategies)
- Webhook replay protection: delivery-GUID dedup store (in-memory + Postgres,
  migration 0003)
- Installation lifecycle: `installation` / `installation_repositories` webhook events
  now create, suspend, and tear down tenant state (orgs, installations, repositories)
- DBOS Transact orchestration: webhook events dispatch to durable Postgres-checkpointed
  workflows via an `EventDispatcher` protocol (inline execution in development)
- M2 task pipeline core: `TaskPipeline` with per-capability mode enforcement (Off
  suppression, Assisted human review, Autopilot merge gates), optimistic-concurrency
  state transitions, and a full audit trail (`task.created` / `state_changed` /
  `merge_blocked` / `suppressed`)
- Task read API for the dashboard: `GET /api/v1/tasks` (repository/state filters),
  `GET /api/v1/tasks/{id}`, `GET /api/v1/tasks/{id}/audit`
- Dependency detection engine (M3): uv.lock / package-lock.json parsers, OSV.dev
  batch vulnerability client, PyPI/npm registry latest-version lookups, and
  `DependencyDetector` producing outdated/vulnerable reports with bump classification
- Upgrade batch planning: security and major bumps as solo PRs, minor/patch grouped
  per ecosystem
- Rollback: `POST /api/v1/tasks/{id}/rollback` opens a revert PR (GraphQL
  `revertPullRequest`) for merged tasks; never auto-merged, fully audited
- Dashboard Tasks UI: task list with state filters, task detail with audit
  timeline and a rollback button for merged tasks
- Org/repo-wide audit feed: `GET /api/v1/audit` with repository/organization/task/
  event-type filters and keyset pagination; `AuditRecorder` resolves and stamps
  `organization_id` on every appended event; audit-feed indexes (migration 0004);
  `AuditStore.append` now returns the persisted event with id/created_at
- Dependency scan triggers (M3): lockfile-touching default-branch pushes and a
  daily DBOS scheduled sweep run detection and create one pipeline task per
  upgrade batch — capability-gated before any network I/O, deduped against open
  tasks, truncation-safe push parsing, honest 404-vs-outage error handling
- Webhook deliveries are un-recorded when dispatch fails, so GitHub redeliveries
  are processed instead of dropped as duplicates

### Fixed
- Audit trail recorded the wrong `from` state on transitions (post-mutation aliasing
  in the in-memory store); pipeline now captures the state before transitioning

### Changed
- Repos API now uses dependency-injected storage instead of a module-global dict
- Webhook signature verification now fails closed: missing signature is rejected when
  a secret is configured; unsigned webhooks are only accepted in development

### Security
- Fixed webhook verification bypass: deliveries without a signature header were
  previously accepted even with `GITHUB_WEBHOOK_SECRET` configured

### Deprecated
- N/A

### Removed
- N/A

## [0.1.0] - 2026-07-15
### Added
- V1 roadmap (`docs/ROADMAP.md`) with locked stack decisions
- Initial project setup and structure
- Python/FastAPI backend with uv package management
- React/TypeScript/Vite frontend
- Five core capabilities: Security, Issue Triage, Dependencies, Test Hygiene, Freshness
- Per-capability operating modes: Autopilot, Assisted, Off
- Repository install/uninstall API endpoints
- GitHub webhook receiver with HMAC signature verification
- AWS Amplify build configuration (`amplify.yml`)
- GitHub Actions CI workflow (backend tests + frontend build)
- Landing page with hero, capabilities grid, and mode explanations
- Dashboard page listing installed repositories
- Repo detail page with live capability toggles
- Comprehensive README with setup instructions, env var reference,
  GitHub App creation guide, API reference, and deployment docs

### Changed
- Upgrade backend to Python 3.13
- Replace PyGithub with githubkit (async, typed, GitHub App auth) per roadmap decision
- Track `backend/uv.lock` for reproducible builds
- Update GitHub Actions to latest majors (checkout v7, setup-uv v8, setup-node v7)

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- N/A

### Security
- N/A

## Notes
- This software is proprietary and confidential. All rights reserved by Silvexis.
