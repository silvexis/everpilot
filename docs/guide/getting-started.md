# Getting started with Everpilot

Everpilot is autopilot — not copilot — for your repositories. You delegate the
ongoing care of a codebase to it and choose, per capability and per repository,
whether it works fully autonomously or hands every change to a human for review.

## 1. Install the GitHub App

1. Visit the Everpilot dashboard and sign in.
2. Click **Install** and choose the organization (or personal account) whose
   repositories Everpilot should watch.
3. Select **All repositories** or pick specific ones. You can change this later
   from GitHub's app settings; Everpilot syncs the change automatically.

Everpilot needs these repository permissions:

| Permission | Why |
|---|---|
| Contents (read/write) | Read lockfiles and source; open branches for fixes |
| Pull requests (read/write) | Open, update, and revert PRs |
| Issues (read/write) | Read and triage issues, comment with analysis |
| Metadata (read) | Basic repository information |
| Webhooks | Receive push, issue, and PR events |

## 2. Enable capabilities

Everpilot does nothing until you turn a capability on. In the dashboard, open a
repository and toggle the capabilities you want, each with an operating mode
(see [Operating modes](operating-modes.md)).

New repositories start with **every capability Off** — an explicit opt-in, so
installing the app never changes your codebase on its own.

## 3. Watch it work

Once a capability is enabled in **Assisted** or **Autopilot**, Everpilot reacts
to repository activity (and a daily scan) by opening pull requests. Every action
Everpilot takes — every trigger, decision, PR, merge, and failure — is visible in
the **Tasks** view and queryable in the audit trail.

## What Everpilot will and won't do on its own

- It **never** merges a change in Assisted mode without your approval.
- In Autopilot mode it merges **only** when every safety gate passes (CI green,
  no conflicts, branch protection respected, under the daily task cap).
- Rolling back any Everpilot-merged change is one click — it opens a revert PR,
  which is itself never auto-merged.

Next: [Capabilities](capabilities.md) · [Operating modes](operating-modes.md)
