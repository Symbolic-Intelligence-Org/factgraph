from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class BackendProfile:
    name: str = "default"
    # Capability keys are intentionally loose in PR-Profile-S1/S2.
    # Current notable key:
    # - "ruleref_policy": "allow" | "require_resolved" | "forbid"
    #   (currently enforced only by where/query validators in mode="souffle")
    # - "not_body_policy": "allow" | "require_correlated" | "forbid_or" | "forbid"
    #   (currently enforced only by where/query validators in mode="souffle")
    capabilities: dict[str, Any] = field(default_factory=dict)

    def to_capabilities(self) -> dict[str, Any]:
        return dict(self.capabilities)


PROFILE_DEFAULT = BackendProfile()

PROFILE_SOUFFLE_STRICT = BackendProfile(
    name="souffle_strict",
    capabilities={
        "ruleref_policy": "require_resolved",
        "not_body_policy": "forbid_or",
    },
)
