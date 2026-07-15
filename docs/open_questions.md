# Open Questions — autonomous roadmap run

Questions and feedback needed from Erik to complete the roadmap goal. Newest
first. Remove entries once resolved.

## 2026-07-15 — PR merges need human action

The autonomous loop cannot merge its own PRs (Claude Code's permission
classifier blocks self-merge without review, and working around it would
defeat the point). **Every completed roadmap item will be left as an open,
CI-green PR.** To unblock:

- **Option A (keep human in the loop):** review and merge queued PRs as they
  appear — `gh pr list` shows the queue; each is rebase-merge ready.
- **Option B (fully autonomous):** add a Bash permission rule allowing
  `gh pr merge` to project settings (the `/update-config` skill can do this),
  accepting that agent-authored code lands on main without review. Given
  Everpilot itself sells the Assisted-vs-Autopilot distinction, running our own
  repo in "Assisted" seems fitting until trust is established.

Currently queued: PR #3 (Release v0.1.0 — githubkit swap, CI green).

## 2026-07-15 — Roadmap open questions still owner-less

Carried from `docs/ROADMAP.md` (not blocking current M0 work, will block M2+):

1. LLM cost control model (hard per-task token budget vs adaptive).
2. Autopilot trust ladder (earn autopilot vs opt-in) — affects M2 merge-gate design.
3. Prompt-injection handling for Issue Triage on public repos — affects M3 design.
4. Free tier shape (task count / repo count / trial) — affects M4 Stripe config.

## 2026-07-15 — Anthropic API credentials

M1 spike and all agent execution need an Anthropic API key provisioned for the
project (and a decision on org account vs personal). Not needed for M0.
