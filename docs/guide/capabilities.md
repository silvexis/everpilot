# Capabilities

Each capability is independently toggleable per repository, with its own
[operating mode](operating-modes.md). Turn on only what you want.

## Available in V1

### 📦 Dependencies

Keeps third-party libraries current and absorbs Dependabot-style updates.

- **Ecosystems**: Python (`uv.lock`) and JavaScript (`package-lock.json`) at
  root of the repository.
- **Triggers**: a push to the default branch that touches a lockfile, plus a
  daily scan of every enabled repository.
- **What it finds**: outdated dependencies (via the PyPI and npm registries) and
  known vulnerabilities (via [OSV.dev](https://osv.dev)).
- **How it batches work**: security fixes and major-version bumps each become
  their own pull request; compatible minor/patch bumps are grouped into one PR
  per ecosystem, so routine updates don't flood your review queue.

### 🎫 Issue Triage

Reads new issues, classifies them, and — for issues it can handle confidently —
proposes and ships fixes.

- Classifies each new issue (bug / feature / question / duplicate) and applies
  labels.
- Comments with its analysis and, for eligible bugs, a proposed fix plan.
- For bugs it can fix confidently, runs a fix through the same task pipeline as
  every other change (your operating mode still applies).
- A confidence threshold controls what it attempts versus only comments on.

## Planned (post-V1)

- 🛡️ **Security** — continuous vulnerability review and fixes beyond dependency
  bumps.
- 🧪 **Test Hygiene** — runs the suite, diagnoses failures, opens fixes.
- ✨ **Freshness** — general modernization so the codebase never rots.

Next: [Operating modes](operating-modes.md)
