"""PyReason adapter-local rule extensions and compile helper."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from factpy_kernel.core.store.types import EngineExtBase
from factpy_kernel.sdk.dsl.expr import HeadCall, LogicVar, PredAtom
from factpy_kernel.sdk.dsl.rule import Rule


@dataclass(frozen=True)
class PyReasonRuleExt(EngineExtBase):
    """PyReason-specific rule definition parameters."""

    timestep_delay: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.timestep_delay, bool) or not isinstance(self.timestep_delay, int):
            raise ValueError("timestep_delay must be int")
        if self.timestep_delay < 0:
            raise ValueError("timestep_delay must be >= 0")


@dataclass(frozen=True)
class PyReasonRuleDef:
    """Adapter-local wrapper: shared Rule + PyReason extension."""

    rule: Rule
    ext: PyReasonRuleExt = field(default_factory=PyReasonRuleExt)

    def __post_init__(self) -> None:
        if not isinstance(self.rule, Rule):
            raise ValueError("PyReasonRuleDef.rule must be a Rule instance")
        if not isinstance(self.ext, PyReasonRuleExt):
            raise ValueError("PyReasonRuleDef.ext must be a PyReasonRuleExt instance")


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


def compile_pyreason_rule(rule_def: PyReasonRuleDef) -> tuple[str, str]:
    """Compile a ``PyReasonRuleDef`` to ``(pyreason_rule_str, rule_name)``."""
    if not isinstance(rule_def, PyReasonRuleDef):
        raise PyReasonCompileError("Expected PyReasonRuleDef")

    head = _compile_head(rule_def.rule)
    body = _compile_body(rule_def.rule.where)
    delay = rule_def.ext.timestep_delay
    return (f"{head} <-{delay} {body}", rule_def.rule.id)


def _compile_head(rule: Rule) -> str:
    if not rule.select:
        raise PyReasonCompileError("Rule.select is empty; need at least one head atom")

    head_item = rule.select[0]
    if isinstance(head_item, PredAtom):
        return _compile_pred_atom(head_item)
    if isinstance(head_item, HeadCall):
        field_name = head_item.field
        if not field_name or not head_item.kwargs:
            raise PyReasonCompileError("HeadCall head requires field name and kwargs")
        terms = [_compile_term(value) for value in head_item.kwargs.values()]
        return f"{field_name}({', '.join(terms)})"
    raise PyReasonCompileError(
        f"Cannot compile head item of type {type(head_item).__name__} to PyReason syntax. "
        "v0 supports PredAtom or HeadCall only."
    )


def _compile_body(where: list[Any]) -> str:
    if not where:
        raise PyReasonCompileError("Rule.where is empty")

    atoms: list[str] = []
    for atom in where:
        if isinstance(atom, PredAtom):
            atoms.append(_compile_pred_atom(atom))
            continue
        raise PyReasonCompileError(
            f"Cannot compile WHERE atom of type {type(atom).__name__}. "
            "v0 supports PredAtom only (no CompareExpr/NotExpr/RuleRefAtom)."
        )
    return ", ".join(atoms)


def _compile_pred_atom(atom: PredAtom) -> str:
    parts = atom.pred_id.split(":")
    field_name = parts[-1] if len(parts) > 1 else parts[0]
    terms = [_compile_term(term) for term in atom.terms]
    return f"{field_name}({', '.join(terms)})"


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
