# Billing FAQ

> V1 pricing. Exact dollar figures are finalized during the private beta; this
> page describes the model, which is settled.

## How does Everpilot charge?

Usage-based: you pay for the work Everpilot actually completes — per completed
task (and the pull request it produces) — not a flat per-seat or per-repo fee.
A "task" is one unit of autonomous work: a dependency-upgrade batch, an issue
triage-and-fix, and so on.

## Is there a free tier?

Yes. Every account gets a number of completed tasks free each month. You only
pay once you exceed that monthly allowance, and the allowance resets each
billing period. This lets a small project run entirely free.

## What counts as a billable task?

A task is billable when it **completes** — reaches a terminal state having done
its work (a PR opened in Assisted mode, or opened and merged in Autopilot).

- Tasks **suppressed** because a capability is Off are never billable.
- Tasks that **fail** are not billed for the failed work.
- A **rollback** (revert PR) is not a separate billable task.

## Can I cap what I spend?

Yes. You set a per-organization monthly budget cap. When usage reaches the cap,
Everpilot pauses agent work for that org until the next period (or until you
raise the cap), and alerts you before you get there. The cap is enforced by
Everpilot itself — you will not be surprised by an invoice.

## How is usage metered?

Each completed task and merged PR is recorded as a billable event with an
idempotency key, so retries and webhook redeliveries never double-count. You can
review every billable event against the audit trail.

## What payment methods are supported?

Card payment via Stripe, managed from the dashboard billing page.
