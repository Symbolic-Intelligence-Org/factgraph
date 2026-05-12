"""PyReason adapter-local rule extensions and compile helper."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from kernel.core.semantics import SemanticsProfile
from kernel.core.store.types import EngineExtBase
from kernel.sdk.dsl.expr import HeadCall, LogicVar, PredAtom
from kernel.sdk.dsl.rule import Rule


@dataclass(frozen=True)
class PyReasonRuleExt(EngineExtBase):
    """PyReason-specific rule definition parameters."""

    timestep_delay: int = 0
    body_predicate_bounds: dict[str, tuple[float, float] | list[float]] = field(default_factory=dict)
    head_bound: tuple[float, float] | list[float] | None = None
    branch_head_bounds: dict[int, tuple[float, float] | list[float]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.timestep_delay, bool) or not isinstance(self.timestep_delay, int):
            raise ValueError("timestep_delay must be int")
        if self.timestep_delay < 0:
            raise ValueError("timestep_delay must be >= 0")
        _normalize_body_predicate_bounds(self.body_predicate_bounds)
        if self.head_bound is not None:
            _validate_bound_pair(self.head_bound, "head_bound")
        object.__setattr__(
            self,
            "branch_head_bounds",
            _normalize_branch_head_bounds(self.branch_head_bounds),
        )


@dataclass(frozen=True)
class PyReasonFactDef:
    """Typed initial fact for PyReason reasoning."""

    atom: str
    name: str
    start: int = 0
    end: int = 0
    bound: tuple[float, float] | list[float] = (1.0, 1.0)

    def __post_init__(self) -> None:
        if not isinstance(self.atom, str) or not self.atom:
            raise ValueError("atom must be non-empty string")
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("name must be non-empty string")
        if isinstance(self.start, bool) or not isinstance(self.start, int):
            raise ValueError("start must be int")
        if isinstance(self.end, bool) or not isinstance(self.end, int):
            raise ValueError("end must be int")
        if not isinstance(self.bound, (list, tuple)) or len(self.bound) != 2:
            raise ValueError("bound must be [float, float]")
        lo_raw, hi_raw = self.bound
        if isinstance(lo_raw, bool) or not isinstance(lo_raw, (int, float)):
            raise ValueError("bound[0] must be numeric")
        if isinstance(hi_raw, bool) or not isinstance(hi_raw, (int, float)):
            raise ValueError("bound[1] must be numeric")
        lo = float(lo_raw)
        hi = float(hi_raw)
        if not 0.0 <= lo <= hi <= 1.0:
            raise ValueError("bound must satisfy 0.0 <= lower <= upper <= 1.0")


class PyReasonCompileError(Exception):
    """Raised when a WHERE atom cannot be compiled to PyReason syntax."""


def resolve_pyreason_engine_ext(
    *,
    where: list[Any],
    schema_ir: dict[str, Any],
    engine_ext: EngineExtBase | None,
    semantics_profile: SemanticsProfile | None = None,
) -> PyReasonRuleExt | None:
    """Resolve PyReason-specific rule projection carriers into ``PyReasonRuleExt``."""
    profile_ext = _materialize_profile_rule_ext(
        where=where,
        schema_ir=schema_ir,
        semantics_profile=semantics_profile,
    )
    explicit_ext = _normalize_pyreason_engine_ext(engine_ext)
    if profile_ext is not None and explicit_ext is not None and profile_ext != explicit_ext:
        raise ValueError(
            "Conflicting PyReason rule projection carriers: "
            "SemanticsProfile.rule_projection.pyreason and PyReasonRuleExt"
        )
    return profile_ext if profile_ext is not None else explicit_ext


def compile_pyreason_rule(rule: Rule, *, engine_ext: PyReasonRuleExt | None = None) -> tuple[str, str]:
    """Compile a Rule to ``(pyreason_rule_str, rule_name)``."""
    rule, ext = _resolve_rule_and_ext(rule, engine_ext=engine_ext)

    head = _compile_head(rule, head_bound=ext.head_bound)
    body = _compile_body(
        rule.where,
        body_predicate_bounds=_normalize_body_predicate_bounds(ext.body_predicate_bounds),
    )
    delay = ext.timestep_delay
    return (f"{head} <-{delay} {body}", rule.id)


def _resolve_rule_and_ext(rule: Rule, *, engine_ext: PyReasonRuleExt | None = None) -> tuple[Rule, PyReasonRuleExt]:
    if not isinstance(rule, Rule):
        raise PyReasonCompileError(f"Expected Rule, got {type(rule).__name__}")

    if engine_ext is None:
        return (rule, PyReasonRuleExt())
    if not isinstance(engine_ext, PyReasonRuleExt):
        raise PyReasonCompileError(
            f"engine_ext must be PyReasonRuleExt or None, got {type(engine_ext).__name__}"
        )
    return (rule, engine_ext)


def _normalize_pyreason_engine_ext(engine_ext: EngineExtBase | None) -> PyReasonRuleExt | None:
    if engine_ext is None:
        return None
    if not isinstance(engine_ext, PyReasonRuleExt):
        raise ValueError(
            f"PyReason engine_ext must be PyReasonRuleExt or None, got {type(engine_ext).__name__}"
        )
    return PyReasonRuleExt(
        timestep_delay=engine_ext.timestep_delay,
        body_predicate_bounds=dict(_normalize_body_predicate_bounds(engine_ext.body_predicate_bounds)),
        head_bound=_validate_bound_pair(engine_ext.head_bound, "head_bound")
        if engine_ext.head_bound is not None
        else None,
        branch_head_bounds=dict(_normalize_branch_head_bounds(engine_ext.branch_head_bounds)),
    )


def _materialize_profile_rule_ext(
    *,
    where: list[Any],
    schema_ir: dict[str, Any],
    semantics_profile: SemanticsProfile | None,
) -> PyReasonRuleExt | None:
    if semantics_profile is None:
        return None
    if not isinstance(semantics_profile, SemanticsProfile):
        raise ValueError(
            f"semantics_profile must be SemanticsProfile or None, got {type(semantics_profile).__name__}"
        )
    if semantics_profile.engine != "pyreason":
        raise ValueError(
            f"PyReason consumption expected SemanticsProfile.engine='pyreason', got {semantics_profile.engine!r}"
        )

    entries = semantics_profile.rule_projection.get("pyreason", [])
    if not entries:
        return None

    branches = _extract_profile_branches(where)
    body_predicate_bounds: dict[str, tuple[float, float]] = {}
    branch_head_bounds: dict[int, tuple[float, float]] = {}
    body_targets_seen: set[tuple[int, int]] = set()
    branch_targets_seen: set[int] = set()
    head_bound: tuple[float, float] | None = None
    timestep_delay = 0
    rule_delay_seen = False

    for idx, entry in enumerate(entries):
        path = f"SemanticsProfile.rule_projection.pyreason[{idx}]"
        target = entry.get("target")
        kind = entry.get("kind")
        value = entry.get("value")
        if target == "rule":
            if kind != "timestep_delay":
                raise ValueError(f"{path}.kind must be 'timestep_delay' for target='rule'")
            if rule_delay_seen:
                raise ValueError(f"{path}.target duplicate rule timestep_delay")
            timestep_delay = _normalize_profile_timestep_delay(value, path=path)
            rule_delay_seen = True
            continue
        if target == "head:0":
            if kind != "interval":
                raise ValueError(f"{path}.kind must be 'interval' for target='head:0'")
            if head_bound is not None:
                raise ValueError(f"{path}.target duplicate head:0")
            head_bound = _normalize_profile_interval(value, path=path)
            continue
        if isinstance(target, str) and target.startswith("branch:"):
            if kind != "interval":
                raise ValueError(f"{path}.kind must be 'interval' for branch targets")
            branch_idx = _parse_branch_target(target, path=path)
            if branch_idx >= len(branches):
                raise ValueError(f"rule_projection.pyreason[{idx}] branch index out of range")
            if branch_idx in branch_targets_seen:
                raise ValueError(f"{path}.target duplicate {target}")
            branch_targets_seen.add(branch_idx)
            branch_head_bounds[branch_idx] = _normalize_profile_interval(value, path=path)
            continue
        if isinstance(target, str) and target.startswith("body_atom:"):
            if kind != "interval_threshold":
                raise ValueError(f"{path}.kind must be 'interval_threshold' for body_atom targets")
            branch_idx, atom_idx = _parse_body_atom_target(target, path=path)
            if (branch_idx, atom_idx) in body_targets_seen:
                raise ValueError(f"{path}.target duplicate {target}")
            body_targets_seen.add((branch_idx, atom_idx))
            pred_id = _resolve_body_atom_pred_id(
                branches,
                branch_idx=branch_idx,
                atom_idx=atom_idx,
                path=path,
            )
            interval = _normalize_profile_interval(value, path=path)
            existing = body_predicate_bounds.get(pred_id)
            if existing is not None and existing != interval:
                raise ValueError(
                    f"{path}.target conflicts with another body_atom target for predicate {pred_id!r}"
                )
            body_predicate_bounds[pred_id] = interval
            continue
        raise ValueError(
            f"{path}.target must be 'body_atom:{{branch}}:{{atom}}', 'head:0', or 'rule'"
        )

    return PyReasonRuleExt(
        timestep_delay=timestep_delay,
        body_predicate_bounds=body_predicate_bounds,
        head_bound=head_bound,
        branch_head_bounds=branch_head_bounds,
    )


def _extract_profile_branches(where: list[Any]) -> list[list[Any]]:
    if not isinstance(where, list) or not where:
        raise ValueError("where must be non-empty list")
    if all(isinstance(item, list) for item in where):
        branches: list[list[Any]] = []
        for branch in where:
            if not branch:
                raise ValueError("where branch must be non-empty")
            branches.append(list(branch))
        return branches
    return [list(where)]


def _parse_body_atom_target(target: str, *, path: str) -> tuple[int, int]:
    parts = target.split(":")
    if len(parts) != 3 or parts[0] != "body_atom":
        raise ValueError(f"{path}.target must use body_atom:{{branch}}:{{atom}}")
    try:
        branch_idx = int(parts[1])
        atom_idx = int(parts[2])
    except ValueError as exc:
        raise ValueError(f"{path}.target must use body_atom:{{branch}}:{{atom}}") from exc
    if branch_idx < 0 or atom_idx < 0:
        raise ValueError(f"{path}.target body atom indexes must be non-negative")
    return (branch_idx, atom_idx)


def _parse_branch_target(target: str, *, path: str) -> int:
    parts = target.split(":")
    if len(parts) != 2 or parts[0] != "branch":
        raise ValueError(f"{path}.target must use branch:{{index}}")
    try:
        branch_idx = int(parts[1])
    except ValueError as exc:
        raise ValueError(f"{path}.target must use branch:{{index}}") from exc
    if branch_idx < 0:
        raise ValueError(f"{path}.target branch index must be non-negative")
    return branch_idx


def _resolve_body_atom_pred_id(
    branches: list[list[Any]],
    *,
    branch_idx: int,
    atom_idx: int,
    path: str,
) -> str:
    if branch_idx >= len(branches):
        raise ValueError(f"{path}.target body atom branch index out of range")
    branch = branches[branch_idx]
    if atom_idx >= len(branch):
        raise ValueError(f"{path}.target body atom index out of range")
    atom = branch[atom_idx]
    if not isinstance(atom, tuple) or len(atom) != 3 or atom[0] != "pred":
        raise ValueError(f"{path}.target body atom must point to pred atom")
    pred_id = atom[1]
    if not isinstance(pred_id, str) or not pred_id:
        raise ValueError(f"{path}.target body atom pred_id must be non-empty string")
    return pred_id


def _normalize_profile_interval(value: Any, *, path: str) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"{path}.value must be [lower, upper]")
    lower_raw, upper_raw = value
    if isinstance(lower_raw, bool) or not isinstance(lower_raw, (int, float)):
        raise ValueError(f"{path}.value lower bound must be numeric")
    if isinstance(upper_raw, bool) or not isinstance(upper_raw, (int, float)):
        raise ValueError(f"{path}.value upper bound must be numeric")
    lower = float(lower_raw)
    upper = float(upper_raw)
    if not 0.0 <= lower <= upper <= 1.0:
        raise ValueError(f"{path}.value must satisfy 0 <= lower <= upper <= 1")
    return (lower, upper)


def _normalize_profile_timestep_delay(value: Any, *, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{path}.value must be non-negative int for timestep_delay")
    return value


def _compile_head(
    rule: Rule,
    *,
    head_bound: tuple[float, float] | list[float] | None = None,
) -> str:
    if not rule.select:
        raise PyReasonCompileError("Rule.select is empty; need at least one head atom")

    head_item = rule.select[0]
    if isinstance(head_item, PredAtom):
        compiled = _compile_pred_atom(head_item)
    elif isinstance(head_item, HeadCall):
        field_name = head_item.field
        if not field_name or not head_item.kwargs:
            raise PyReasonCompileError("HeadCall head requires field name and kwargs")
        terms = [_compile_term(value) for value in head_item.kwargs.values()]
        compiled = f"{field_name}({', '.join(terms)})"
    else:
        raise PyReasonCompileError(
            f"Cannot compile head item of type {type(head_item).__name__} to PyReason syntax. "
            "v0 supports PredAtom or HeadCall only."
        )

    if head_bound is None:
        return compiled
    lo, hi = _validate_bound_pair(head_bound, "head_bound")
    return f"{compiled} : [{lo}, {hi}]"


def _compile_body(
    where: list[Any],
    *,
    body_predicate_bounds: dict[str, tuple[float, float]],
) -> str:
    if not where:
        raise PyReasonCompileError("Rule.where is empty")

    atoms: list[str] = []
    for atom in where:
        if isinstance(atom, PredAtom):
            atoms.append(_compile_body_pred_atom(atom, body_predicate_bounds=body_predicate_bounds))
            continue
        raise PyReasonCompileError(
            f"Cannot compile WHERE atom of type {type(atom).__name__}. "
            "v0 supports PredAtom only (no CompareExpr/NotExpr/RuleRefAtom)."
        )
    return ", ".join(atoms)


def _compile_pred_atom(atom: PredAtom) -> str:
    return _compile_pred_atom_with_interval(atom)


def _compile_body_pred_atom(
    atom: PredAtom,
    *,
    body_predicate_bounds: dict[str, tuple[float, float]],
) -> str:
    interval = body_predicate_bounds.get(atom.pred_id)
    return _compile_pred_atom_with_interval(atom, interval=interval)


def _compile_pred_atom_with_interval(
    atom: PredAtom,
    *,
    interval: tuple[float, float] | None = None,
) -> str:
    parts = atom.pred_id.split(":")
    field_name = parts[-1] if len(parts) > 1 else parts[0]
    terms = [_compile_term(term) for term in atom.terms]
    compiled = f"{field_name}({', '.join(terms)})"
    if interval is None:
        return compiled
    lo, hi = interval
    return f"{compiled} : [{lo}, {hi}]"


def _normalize_body_predicate_bounds(
    bounds: dict[str, tuple[float, float] | list[float]] | None,
) -> dict[str, tuple[float, float]]:
    if bounds is None:
        return {}
    if not isinstance(bounds, dict):
        raise ValueError("body_predicate_bounds must be dict[str, [float, float]]")

    normalized: dict[str, tuple[float, float]] = {}
    for pred_id, bound in bounds.items():
        if not isinstance(pred_id, str) or not pred_id:
            raise ValueError("body_predicate_bounds keys must be non-empty strings")
        normalized[pred_id] = _validate_bound_pair(bound, "body_predicate_bounds")
    return normalized


def _normalize_branch_head_bounds(
    bounds: dict[int, tuple[float, float] | list[float]] | None,
) -> dict[int, tuple[float, float]]:
    if bounds is None:
        return {}
    if not isinstance(bounds, dict):
        raise ValueError("branch_head_bounds must be dict[int, [float, float]]")

    normalized: dict[int, tuple[float, float]] = {}
    for branch_idx, bound in bounds.items():
        if isinstance(branch_idx, bool) or not isinstance(branch_idx, int) or branch_idx < 0:
            raise ValueError("branch_head_bounds keys must be non-negative integers")
        normalized[branch_idx] = _validate_bound_pair(bound, "branch_head_bounds")
    return normalized


def _validate_bound_pair(
    bound: tuple[float, float] | list[float],
    name: str,
) -> tuple[float, float]:
    if not isinstance(bound, (list, tuple)) or len(bound) != 2:
        raise ValueError(f"{name} must be [float, float]")
    lo_raw, hi_raw = bound
    if isinstance(lo_raw, bool) or not isinstance(lo_raw, (int, float)):
        raise ValueError(f"{name} lower bound must be numeric")
    if isinstance(hi_raw, bool) or not isinstance(hi_raw, (int, float)):
        raise ValueError(f"{name} upper bound must be numeric")
    lo = float(lo_raw)
    hi = float(hi_raw)
    if not 0.0 <= lo <= hi <= 1.0:
        raise ValueError(f"{name} must satisfy 0.0 <= lower <= upper <= 1.0")
    return (lo, hi)


def _compile_term(term: Any) -> str:
    if isinstance(term, LogicVar):
        token = term.token or term.label
        if not isinstance(token, str) or not token:
            raise PyReasonCompileError("LogicVar has neither token nor label")
        return token[1:] if token.startswith("$") else token
    if isinstance(term, str):
        return term
    if isinstance(term, (int, float)) and not isinstance(term, bool):
        return str(term)
    raise PyReasonCompileError(
        f"Cannot compile term of type {type(term).__name__}. "
        "v0 supports LogicVar and string/number literals."
    )
