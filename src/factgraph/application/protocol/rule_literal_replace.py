"""Rule Literal Replace protocol DTOs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias

from factgraph.core.rules.rule_ir import RuleSpec
from factgraph.core.store._support import (
    BindingItems,
    SupportArtifact,
    normalize_binding_items,
)

from .common import (
    ErrorDTO,
    ProtocolShapeError,
    WarningDTO,
    _require_literal,
    _validate_tuple_items,
)
from .derivation_fact_overlay import EvaluationOverlay
from .proofframe import ProofFrameRecheckResult

RuleLiteralReplaceStatus: TypeAlias = Literal[
    "completed", "unsupported", "invalid_request"
]

_RULE_LITERAL_REPLACE_STATUSES = ("completed", "unsupported", "invalid_request")


def _validate_binding_items(value: Any, *, field_name: str) -> BindingItems:
    if not isinstance(value, tuple):
        raise ProtocolShapeError(f"{field_name} must be BindingItems tuple")

    seen: set[str] = set()
    for idx, item in enumerate(value):
        if not isinstance(item, tuple) or len(item) != 2:
            raise ProtocolShapeError(f"{field_name}[{idx}] must be tuple[str, Any]")
        key = item[0]
        if not isinstance(key, str) or not key:
            raise ProtocolShapeError(f"{field_name}[{idx}][0] must be non-empty string")
        if not key.startswith("$") or len(key) == 1:
            raise ProtocolShapeError(f"{field_name}[{idx}][0] must be $-prefixed variable")
        if key in seen:
            raise ProtocolShapeError(f"{field_name} must not contain duplicate variable names")
        seen.add(key)

    try:
        return normalize_binding_items(value)
    except ValueError as exc:
        raise ProtocolShapeError(f"{field_name} must be valid BindingItems") from exc


def _validate_variant_rows(
    value: Any, *, field_name: str
) -> tuple[BindingItems, ...]:
    if not isinstance(value, tuple):
        raise ProtocolShapeError(f"{field_name} must be tuple[BindingItems, ...]")
    return tuple(
        _validate_binding_items(row, field_name=f"{field_name}[{idx}]")
        for idx, row in enumerate(value)
    )


@dataclass(frozen=True)
class RuleLiteralReplaceRequest:
    rule_spec: RuleSpec
    support_artifact: SupportArtifact
    overlay: EvaluationOverlay

    def __post_init__(self) -> None:
        if not isinstance(self.rule_spec, RuleSpec):
            raise ProtocolShapeError("rule_spec must be RuleSpec")
        if not isinstance(self.support_artifact, SupportArtifact):
            raise ProtocolShapeError("support_artifact must be SupportArtifact")
        if not isinstance(self.overlay, EvaluationOverlay):
            raise ProtocolShapeError("overlay must be EvaluationOverlay")


@dataclass(frozen=True)
class RuleLiteralReplaceResult:
    status: RuleLiteralReplaceStatus
    variant_rows: tuple[BindingItems, ...]
    proof_frame: ProofFrameRecheckResult | None
    errors: tuple[ErrorDTO, ...] = field(default_factory=tuple)
    warnings: tuple[WarningDTO, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        status = _require_literal(
            self.status,
            field_name="status",
            allowed=_RULE_LITERAL_REPLACE_STATUSES,
        )
        object.__setattr__(
            self,
            "variant_rows",
            _validate_variant_rows(self.variant_rows, field_name="variant_rows"),
        )
        if self.proof_frame is not None and not isinstance(
            self.proof_frame, ProofFrameRecheckResult
        ):
            raise ProtocolShapeError("proof_frame must be ProofFrameRecheckResult or None")
        object.__setattr__(
            self,
            "errors",
            _validate_tuple_items(self.errors, field_name="errors", item_type=ErrorDTO),
        )
        object.__setattr__(
            self,
            "warnings",
            _validate_tuple_items(
                self.warnings, field_name="warnings", item_type=WarningDTO
            ),
        )

        if status == "completed":
            if self.proof_frame is None:
                raise ProtocolShapeError(
                    "completed RuleLiteralReplaceResult requires proof_frame"
                )
            if self.errors:
                raise ProtocolShapeError(
                    "completed RuleLiteralReplaceResult must not contain errors"
                )
            return

        if self.variant_rows:
            raise ProtocolShapeError(
                f"{status} RuleLiteralReplaceResult requires empty variant_rows"
            )
        if self.proof_frame is not None:
            raise ProtocolShapeError(
                f"{status} RuleLiteralReplaceResult requires proof_frame=None"
            )
        if not self.errors:
            raise ProtocolShapeError(f"{status} RuleLiteralReplaceResult requires errors")


__all__ = [
    "RuleLiteralReplaceRequest",
    "RuleLiteralReplaceResult",
    "RuleLiteralReplaceStatus",
]
