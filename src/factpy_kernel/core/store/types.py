from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
from typing import Any, Literal, TypedDict, TypeAlias

from factpy_kernel.core.derivation.candidates import CandidateSet

HeadVarsIR: TypeAlias = list[object]
WhereIR: TypeAlias = list[object]
HeadSpecIR: TypeAlias = dict[str, object]
BodyConfidencesIR: TypeAlias = list[float] | None
EngineOptionsIR: TypeAlias = dict[str, Any] | None
ConfidenceStrategy: TypeAlias = Literal["max", "mean", "median", "prefer_source"]
EvaluateMode: TypeAlias = Literal["native", "souffle", "problog", "pyreason"]
EngineEvaluatorFn: TypeAlias = Callable[..., list[CandidateSet]]


class EngineExtBase:
    """Base class for engine-specific rule/derivation extensions.

    Subclasses must be frozen dataclasses. The framework never inspects
    fields; only the target engine's adapter reads them.
    """


class RuleSpec(TypedDict, total=False):
    rule_id: str
    version: str
    select_vars: list[str]
    where: WhereIR
    expose: bool
    body_confidences: BodyConfidencesIR


class DerivationSpec(TypedDict, total=False):
    derivation_id: str
    version: str
    target_pred_id: str
    head_vars: HeadVarsIR
    where: WhereIR
    mode: EvaluateMode
    head: HeadSpecIR | None
    body_confidences: BodyConfidencesIR


@dataclass(frozen=True)
class ViewSpec:
    active: bool = True
    confidence_strategy: ConfidenceStrategy = "max"
    prefer_source: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.active, bool):
            raise ValueError("ViewSpec.active must be bool")
        if self.confidence_strategy not in {"max", "mean", "median", "prefer_source"}:
            raise ValueError("ViewSpec.confidence_strategy must be one of: max, mean, median, prefer_source")
        if self.prefer_source is not None and (not isinstance(self.prefer_source, str) or not self.prefer_source):
            raise ValueError("ViewSpec.prefer_source must be non-empty string or None")
