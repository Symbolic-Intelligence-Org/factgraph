from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from factpy.core.semantics import SemanticsProfile
from factpy.core.store.types import EngineExtBase

from .common import (
    JSONValue,
    ProtocolShapeError,
    _require_bool,
    _require_literal,
    _require_non_empty_str,
    _require_optional_non_empty_str,
    _validate_json_mapping,
    _validate_tuple_items,
)


@dataclass(frozen=True)
class CompiledHeadCall:
    target_pred_id: str
    head_var_names: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty_str(self.target_pred_id, field_name="target_pred_id")
        if not isinstance(self.head_var_names, tuple):
            raise ProtocolShapeError("head_var_names must be tuple")
        for idx, name in enumerate(self.head_var_names):
            _require_non_empty_str(name, field_name=f"head_var_names[{idx}]")


@dataclass(frozen=True)
class CompiledDerivationPlan:
    derivation_id: str
    version: str
    body_ir: list[Any]
    heads: tuple[CompiledHeadCall, ...]
    body_confidence: float | None = None
    head_spec: dict[str, Any] | None = None
    engine_ext: EngineExtBase | None = None
    engine_options: dict[str, JSONValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty_str(self.derivation_id, field_name="derivation_id")
        _require_non_empty_str(self.version, field_name="version")
        if not isinstance(self.body_ir, list):
            raise ProtocolShapeError("body_ir must be list")
        _validate_tuple_items(self.heads, field_name="heads", item_type=CompiledHeadCall)
        if not self.heads:
            raise ProtocolShapeError("heads must not be empty")
        if self.body_confidence is not None:
            if isinstance(self.body_confidence, bool) or not isinstance(self.body_confidence, (int, float)):
                raise ProtocolShapeError("body_confidence must be number or None")
            if not (0.0 <= float(self.body_confidence) <= 1.0):
                raise ProtocolShapeError("body_confidence must be in [0, 1]")
        if self.head_spec is not None:
            if not isinstance(self.head_spec, dict):
                raise ProtocolShapeError("head_spec must be dict[str, Any] or None")
            if len(self.heads) != 1:
                raise ProtocolShapeError(
                    "head_spec is only supported when len(heads) == 1; "
                    "multi-head plans must be expressed via the heads tuple or via separate plans"
                )
        if self.engine_ext is not None and not isinstance(self.engine_ext, EngineExtBase):
            raise ProtocolShapeError("engine_ext must be EngineExtBase or None")
        object.__setattr__(
            self,
            "engine_options",
            _validate_json_mapping(self.engine_options, field_name="engine_options"),
        )


@dataclass(frozen=True)
class DerivationEvaluateRequest:
    plans: tuple[CompiledDerivationPlan, ...]
    run_id: str | None = None
    engine: Literal["souffle", "problog", "pyreason", "native"] = "native"
    semantics_profile: SemanticsProfile | None = None

    def __post_init__(self) -> None:
        _validate_tuple_items(self.plans, field_name="plans", item_type=CompiledDerivationPlan)
        if not self.plans:
            raise ProtocolShapeError("plans must not be empty")
        _require_optional_non_empty_str(self.run_id, field_name="run_id")
        _require_literal(
            self.engine,
            field_name="engine",
            allowed=("souffle", "problog", "pyreason", "native"),
        )
        if self.semantics_profile is not None and not isinstance(self.semantics_profile, SemanticsProfile):
            raise ProtocolShapeError("semantics_profile must be SemanticsProfile or None")


@dataclass(frozen=True)
class DerivationAcceptRequest:
    accept_mode: Literal["atomic", "best_effort"] = "best_effort"
    idempotent_duplicate_ok: bool = True
    approved_by: str | None = None
    note: str | None = None
    dry_run: bool = False
    identity_override: dict[str, Any] | None = None
    meta: dict[str, JSONValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_literal(
            self.accept_mode,
            field_name="accept_mode",
            allowed=("atomic", "best_effort"),
        )
        _require_bool(self.idempotent_duplicate_ok, field_name="idempotent_duplicate_ok")
        _require_optional_non_empty_str(self.approved_by, field_name="approved_by")
        _require_optional_non_empty_str(self.note, field_name="note")
        _require_bool(self.dry_run, field_name="dry_run")
        if self.identity_override is not None and not isinstance(self.identity_override, dict):
            raise ProtocolShapeError("identity_override must be dict or None")
        object.__setattr__(self, "meta", _validate_json_mapping(self.meta, field_name="meta"))


__all__ = [
    "CompiledDerivationPlan",
    "CompiledHeadCall",
    "DerivationAcceptRequest",
    "DerivationEvaluateRequest",
]
