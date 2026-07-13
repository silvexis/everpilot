from enum import StrEnum

from pydantic import BaseModel, Field


class CapabilityMode(StrEnum):
    """Operating mode for a capability."""

    AUTOPILOT = "autopilot"  # Fully autonomous, no human review
    ASSISTED = "assisted"  # Does the work, waits for human approval before commit
    OFF = "off"  # Disabled


class Capability(StrEnum):
    """The five core Everpilot capabilities."""

    SECURITY = "security"  # Continuously reviews for vulnerabilities and lands fixes
    ISSUE_TRIAGE = "issue_triage"  # Reads issues, classifies, proposes and ships fixes
    DEPENDENCIES = "dependencies"  # Keeps third-party libraries current
    TEST_HYGIENE = "test_hygiene"  # Runs tests, diagnoses failures, opens fixes
    FRESHNESS = "freshness"  # General modernization so the codebase never rots


class CapabilityConfig(BaseModel):
    """Configuration for a single capability."""

    capability: Capability
    mode: CapabilityMode = CapabilityMode.OFF
    enabled: bool = Field(default=False, description="Whether this capability is active")

    @property
    def is_active(self) -> bool:
        return self.enabled and self.mode != CapabilityMode.OFF


DEFAULT_CAPABILITIES: list[CapabilityConfig] = [
    CapabilityConfig(capability=cap, mode=CapabilityMode.OFF, enabled=False) for cap in Capability
]
