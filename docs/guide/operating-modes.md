# Operating modes

Every capability runs in one of three modes, set per repository. The mode
decides how much autonomy Everpilot has for that capability on that repo.

| Mode | What happens |
|---|---|
| **Off** | The capability is disabled. Matching events are ignored and recorded as suppressed in the audit log — so you can see what *would* have happened. |
| **Assisted** | Everpilot does the work and opens a pull request, then waits. Nothing merges until a human approves or closes it. |
| **Autopilot** | Fully autonomous. Everpilot opens the PR and merges it itself — but **only** when every safety gate passes. |

## Autopilot safety gates

An Autopilot change merges only when all of these hold:

- **CI is green** — the repository's own checks pass.
- **No conflicts** — the PR merges cleanly.
- **Branch protection respected** — Everpilot never bypasses your rules.
- **Under the daily task cap** — a per-repository limit stops runaway activity.

If any gate fails, the task is **held at the open-PR stage for a human** — a
failed gate is never treated as a task failure, and the block is recorded in the
audit trail with the reason.

## Earning Autopilot

The intended path to Autopilot is to earn it: a repository builds a track record
of successful Assisted merges before Autopilot becomes available. This mirrors
how trust actually builds — you watch Everpilot get it right in Assisted mode
first, then hand over the merge. (This trust ladder is the product's design
direction; today the mode is set directly per repository.)

## Rollback

Any change Everpilot merged can be rolled back with one click. Everpilot opens a
revert pull request — which is itself **never** auto-merged, so undoing an
autonomous change always gets human eyes.

Next: [Billing](billing.md)
