"""Why-not capability helper builders."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from kernel.core.store._support import BindingItems, normalize_binding_items

from kernel.application.protocol import CompiledDerivationPlan

from .errors import CapabilityHelperError


def build_why_not_candidate_universe(
    plan: CompiledDerivationPlan,
    candidates: Sequence[Mapping[str, Any] | Sequence[Any]],
) -> tuple[BindingItems, ...]:
    """Normalize candidate rows against the plan's single head variable order."""

    if not isinstance(plan, CompiledDerivationPlan):
        raise CapabilityHelperError("plan must be CompiledDerivationPlan")
    if len(plan.heads) != 1:
        raise CapabilityHelperError("plan must contain exactly one head")
    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
        raise CapabilityHelperError("candidates must be a sequence of rows")

    head_vars = plan.heads[0].head_var_names
    universe: list[BindingItems] = []
    for idx, row in enumerate(candidates):
        values = _candidate_values(row, head_vars=head_vars, row_index=idx)
        universe.append(normalize_binding_items(tuple(zip(head_vars, values, strict=True))))
    return tuple(universe)


def _candidate_values(
    row: Mapping[str, Any] | Sequence[Any],
    *,
    head_vars: tuple[str, ...],
    row_index: int,
) -> tuple[Any, ...]:
    if isinstance(row, Mapping):
        missing = [name for name in head_vars if name not in row]
        if missing:
            raise CapabilityHelperError(
                f"candidate row {row_index} missing head variables: {missing}"
            )
        return tuple(row[name] for name in head_vars)

    if isinstance(row, Sequence) and not isinstance(row, (str, bytes)):
        if len(row) != len(head_vars):
            raise CapabilityHelperError(
                f"candidate row {row_index} must have {len(head_vars)} values"
            )
        return tuple(row)

    raise CapabilityHelperError(
        f"candidate row {row_index} must be mapping or non-string sequence"
    )



__all__ = [
    "build_why_not_candidate_universe",
]
