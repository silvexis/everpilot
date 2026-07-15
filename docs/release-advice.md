# Release Advice

Project-specific instructions and lessons learned from past releases.
This file is automatically maintained by the /ship workflow.

## Standing Instructions

- Backend commands must run from `backend/` (uv project root); git commands from the repo root. Shell cwd persists between steps — `cd` explicitly.
- CI runs `ruff format --check` in addition to `ruff check` — always run both locally before pushing (format-check failures blocked CI on 2026-07-13).
- No release tags existed before v0.1.0; version bump analysis starts from that tag.

## Release Log

### v0.1.0 — 2026-07-15

**Tools run**: uv sync --upgrade, pytest (13 passed, 84% coverage), ruff check, ruff format --check, vite build
**Pre-commit configured**: no
**Issues**: none this release. Prior sessions hit two now-fixed problems worth remembering: `backend/uv.lock` was gitignored (fixed — must stay tracked), and `ruff format --check` failed in CI while `ruff check` passed locally.
**Recurring patterns**: none yet (first release)
**Suggestions**: consider adding pre-commit with ruff check + format to catch format drift before CI; add a `scripts/test.sh` wrapping backend+frontend checks so releases run one command.
