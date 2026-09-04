from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NativeRuleRefRowSupport:
    row_terms: tuple[Any, ...]
    child_support_digest: str | None = None
    unresolved_reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.row_terms, tuple) or not self.row_terms:
            raise ValueError("row_terms must be non-empty tuple")
        if self.child_support_digest is None and self.unresolved_reason is None:
            raise ValueError("row support must have child_support_digest or unresolved_reason")
        if self.child_support_digest is not None:
            if not isinstance(self.child_support_digest, str) or not self.child_support_digest.startswith("sha256:"):
                raise ValueError("child_support_digest must be sha256 token")
            if self.unresolved_reason is not None:
                raise ValueError("resolved row support must not carry unresolved_reason")
        if self.unresolved_reason is not None and (
            not isinstance(self.unresolved_reason, str) or not self.unresolved_reason
        ):
            raise ValueError("unresolved_reason must be non-empty string")


@dataclass(frozen=True)
class NativeRuleRefResolution:
    ruleref_condition_key: str
    rule_ref_id: str
    rule_ref_version: str
    row_supports: tuple[NativeRuleRefRowSupport, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.ruleref_condition_key, str) or not self.ruleref_condition_key:
            raise ValueError("ruleref_condition_key must be non-empty string")
        if not isinstance(self.rule_ref_id, str) or not self.rule_ref_id:
            raise ValueError("rule_ref_id must be non-empty string")
        if not isinstance(self.rule_ref_version, str) or not self.rule_ref_version:
            raise ValueError("rule_ref_version must be non-empty string")
        if not isinstance(self.row_supports, tuple):
            raise ValueError("row_supports must be tuple")  # noqa: TRY004 - RuleRef resolution DTO shares the ValueError family with its sort-order guard.
        expected = tuple(sorted(self.row_supports, key=lambda row: (row.row_terms, row.child_support_digest or "")))
        if self.row_supports != expected:
            raise ValueError("row_supports must be sorted by row_terms")


__all__ = [
    "NativeRuleRefResolution",
    "NativeRuleRefRowSupport",
]
