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

### Changed
- Repos API now uses dependency-injected storage instead of a module-global dict

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- N/A

### Security
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
