"""LLM cost pass-through (locked decision, 2026-07-25).

Platform-key usage is billed to the customer at our cost plus a 20% uplift.
BYOK usage incurs no LLM charge through Everpilot — the customer already pays
Anthropic directly.

All arithmetic in integer cents via Decimal — never floats for money.
"""

from decimal import ROUND_HALF_UP, Decimal

from everpilot.llm.keys import KeySource

#: Cost multiplier applied to platform-key usage (cost + 20%).
PLATFORM_UPLIFT = Decimal("1.20")


def billable_llm_cost(raw_cost_cents: int, source: KeySource) -> int:
    """What the customer owes for a task's LLM usage, in cents.

    raw_cost_cents is what Anthropic charged us (metered per task from token
    usage). BYOK tasks bill zero regardless of usage.
    """
    if raw_cost_cents < 0:
        raise ValueError("raw_cost_cents must be non-negative")
    if source == KeySource.BYOK:
        return 0
    uplifted = Decimal(raw_cost_cents) * PLATFORM_UPLIFT
    return int(uplifted.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
