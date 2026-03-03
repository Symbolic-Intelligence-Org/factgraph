from __future__ import annotations

from collections.abc import Callable
from typing import Literal, TypeAlias

from factpy_kernel.core.derivation.candidates import CandidateSet

HeadVarsIR: TypeAlias = list[object]
WhereIR: TypeAlias = list[object]
HeadSpecIR: TypeAlias = dict[str, object]
EvaluateMode: TypeAlias = Literal["python", "engine"]
EngineEvaluatorFn: TypeAlias = Callable[..., list[CandidateSet]]
