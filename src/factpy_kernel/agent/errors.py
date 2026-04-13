from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentContractError(ValueError):
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass
class AgentRuntimeError(RuntimeError):
    message: str
    kind: str = "runtime"
    path: str = "$"
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.message


@dataclass
class AgentRecoveryError(RuntimeError):
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass
class AgentScopeViolation(PermissionError):
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.message

