"""Autopilot merge gates (roadmap M2): every gate must pass before auto-merge."""

from pydantic import BaseModel

#: Per-repo autopilot task cap per UTC day; blocks runaway loops on one repo.
DEFAULT_DAILY_TASK_CAP = 10


class MergeGates(BaseModel):
    """Evaluated at merge time for Autopilot-mode tasks."""

    ci_green: bool
    no_conflicts: bool
    respects_branch_protection: bool
    under_daily_cap: bool

    @property
    def all_pass(self) -> bool:
        return (
            self.ci_green
            and self.no_conflicts
            and self.respects_branch_protection
            and self.under_daily_cap
        )

    @property
    def failures(self) -> list[str]:
        return [name for name, passed in self.model_dump().items() if not passed]
